import re
from asnake.aspace import ASpace
from config import Config
import aspace_tools
import at_tools

# Initialize ArchivesSpace client once
aspace = ASpace(
    baseurl=Config.aspace_host,
    username=Config.aspace_user,
    password=Config.aspace_pass
)

def update_dates(ao_json, begin_date, end_date, date_expression, config, user):
    """
    Update or create the first date subrecord on the archival object JSON.
    Returns True if changes were made, False otherwise.
    """

    dates = ao_json.get('dates', [])

    if dates:
        date_obj = dates[0]
        needs_update = False

        if date_obj.get('begin') != begin_date:
            date_obj['begin'] = begin_date
            needs_update = True

        if date_obj.get('end') != end_date:
            date_obj['end'] = end_date
            needs_update = True

        if date_obj.get('expression') != date_expression:
            date_obj['expression'] = date_expression
            needs_update = True

        return needs_update

    else:
        # No date subrecords exist — create one
        new_date = {
            'jsonmodel_type': 'date',
            'date_type': 'inclusive',
            'begin': begin_date,
            'end': end_date,
            'expression': date_expression,
            'created_by': user,
            'last_modified_by': user
        }
        ao_json['dates'] = [new_date]
        return True


def update_extent(ao_json, new_extent_number, config, user):
    """
    Update or create extent subrecord on archival object JSON.
    Returns True if changes were made, False otherwise.
    """

    extents = ao_json.get('extents', [])
    extent_type = config.extent_type

    existing_extent = None
    for extent in extents:
        if extent.get('extent_type') == extent_type:
            existing_extent = extent
            break

    if existing_extent:
        if existing_extent.get('number') != str(new_extent_number):
            existing_extent['number'] = str(new_extent_number)
            return True
        else:
            return False
    else:
        # Create new extent subrecord
        new_extent = {
            'jsonmodel_type': 'extent',
            'number': str(new_extent_number),
            'extent_type': extent_type,
            'portion': 'whole',
            'created_by': user,
            'last_modified_by': user
        }
        extents.append(new_extent)
        ao_json['extents'] = extents
        return True


def sync_aos():
    repo_id = Config.aspace_repo
    subject = Config.subject
    user = Config.aspace_user

    seeds = at_tools.get_all_seeds()
    results = aspace_tools.search_ao_by_subject(repo_id, subject)

    print(f"Found {len(results)} archival objects for subject '{subject}':\n")

    for obj in results:
        try:
            obj_json = obj.json()
            title = obj_json.get("title", "[No title]")
            uri = obj.uri

            notes = aspace_tools.extract_notes_by_label_or_type(
                obj_json,
                label=Config.phystech_label_scrc,
                note_type="phystech",
                label_regex=False
            )

            for note_url in notes:
                print(f"Note (URL): {note_url}")

                seed = at_tools.find_seed_by_url(seeds, note_url)
                if seed:
                    collection_id = seed['collection']
                    print(f"Found collection {collection_id} for URL.")
                else:
                    collection_id = at_tools.infer_collection_from_similar_seeds(seeds, note_url)
                    if collection_id:
                        print(f"Inferred collection {collection_id} for URL.")
                    else:
                        print("Could not determine collection for URL — skipping further processing.")
                        continue

                records = at_tools.fetch_cdx_records(collection_id, note_url)
                if not records:
                    print("No CDX records found for URL.")
                    continue

                begin_date = at_tools.get_earliest_date(records)
                end_date = at_tools.get_latest_date(records)

                date_expression = f"{begin_date} - {end_date}" if end_date else begin_date
                extent = len(records)

                # --- UPDATE DATES ---
                dates_changed = update_dates(obj_json, begin_date, end_date, date_expression, Config, user)

                # --- UPDATE EXTENTS ---
                extent_changed = update_extent(obj_json, extent, Config, user)

                if dates_changed or extent_changed:
                    # Save updated archival object back to aspace once per object
                    aspace.client.post(uri, json=obj_json)
                    print(f"Updated archival object {uri}")
                else:
                    print(f"No updates needed for {uri}")

                print(f"Date Expression: {date_expression}")
                print(f"Begin Date: {begin_date}")
                print(f"End Date:   {end_date}")
                print(f"Extent:     {extent} crawls")

        except Exception as e:
            print(f"Failed to process object {getattr(obj, 'uri', '[No URI]')}: {e}")


if __name__ == "__main__":
    sync_aos()
