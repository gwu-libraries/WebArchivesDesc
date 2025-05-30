import re
from datetime import datetime
from asnake.aspace import ASpace
from config import Config
import aspace_tools
import at_tools
import json

# Initialize ArchivesSpace client once
aspace = ASpace(
    baseurl=Config.aspace_host,
    username=Config.aspace_user,
    password=Config.aspace_pass
)

def update_dates(ao_json, begin_date, end_date, date_expression, config):
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
            'label' :  'creation',
            'date_type': 'inclusive',
            'begin': begin_date,
            'end': end_date,
            'expression': date_expression,
        }
        ao_json['dates'] = [new_date]
        return True


def update_extent(ao_json, new_extent_number, config):
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
        }
        extents.append(new_extent)
        ao_json['extents'] = extents
        return True
    
def update_parent_dates_if_needed(child_json, begin_date, end_date, config):
    """
    Ensure the parent AO's date range includes the child's date range.
    If the parent date is missing or narrower, update it and return True.
    """
    parent_ref = child_json.get('parent', {}).get('ref')
    if not parent_ref:
        return False  # No parent to update

    parent = aspace.client.get(parent_ref).json()
    parent_dates = parent.get('dates', [])
    needs_update = False

    if not parent_dates:
        # No dates exist — create a new one with required fields
        new_date = {
            'jsonmodel_type': 'date',
            'date_type': 'inclusive',
            'label': 'creation',
            'begin': begin_date,
            'end': end_date,
            'expression': f"{begin_date} - {end_date}" if end_date else begin_date
        }
        parent['dates'] = [new_date]
        needs_update = True

    else:
        # Update existing date if it doesn't span the child's date
        date_obj = parent_dates[0]
        parent_begin = date_obj.get('begin')
        parent_end = date_obj.get('end')

        if parent_begin:
            if begin_date < parent_begin:
                date_obj['begin'] = begin_date
                needs_update = True
        else:
            date_obj['begin'] = begin_date
            needs_update = True

        if end_date:
            if not parent_end or end_date > parent_end:
                date_obj['end'] = end_date
                needs_update = True

        if needs_update:
            date_obj['expression'] = f"{date_obj['begin']} - {date_obj.get('end', '')}".strip(" -")

    if needs_update:
        post_response = aspace.client.post(parent_ref, json=parent)
        if post_response.status_code == 200:
            print(f"Updated parent AO: {parent_ref}")
            return True
        else:
            print(f"Failed to update parent AO {parent_ref}. Status: {post_response.status_code}")
            print(f"Response text: {post_response.text}")
            return False

    return False

def sync_aos():
    repo_id = Config.aspace_repo
    subject = Config.subject

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
                dates_changed = update_dates(obj_json, begin_date, end_date, date_expression, Config)

                # --- UPDATE EXTENTS ---
                extent_changed = update_extent(obj_json, extent, Config)

                # --- UPDATE PARENT DATES IF NEEDED ---
                parent_changed = update_parent_dates_if_needed(obj_json, begin_date, end_date, Config)

                if dates_changed or extent_changed:
                    #debug
                    #print("Posting updated AO:")
                    #print(json.dumps(obj_json, indent=2))
                    # Save updated archival object back to aspace once per object
                    response = aspace.client.post(uri, json=obj_json)
                    print(f"Updated archival object {uri}")
                    #debug
                    print(f"POST response: {response.status_code}")
                    print(response.text)
                    #re-fetch the ao json since we just changed it -- to avoid 409
                    obj_json = aspace.client.get(uri).json()
                else:
                    print(f"No updates needed for {uri}")

                print(f"Date Expression: {date_expression}")
                print(f"Begin Date: {begin_date}")
                print(f"End Date:   {end_date}")
                print(f"Extent:     {extent} crawls")

                # --- UPDATE DIGITAL OBJECTS ---
                #construct link to wayback calendar 
                wayback_uri = at_tools.build_wayback_url(collection_id, note_url)
                #logic for updating or creating DAO records will go here.
                dao_instances = aspace_tools.get_digital_object_instance(obj_json)
                #if no DAO, we can create a new DAO instane and attach it to the AO
                if dao_instances == None:
                    print(f"No DAO record attached to {uri} -> Creating DAO to hold Wayback file version!")
            
                    new_dao_id = obj_json.get('ref_id') #setting the DAO identifier as the refid of the AO we are attaching to
                    new_dao_title = (f"Web Archives Replay Calendar - {note_url}")
                    dao_ref = aspace_tools.create_new_dao(wayback_uri, new_dao_id, new_dao_title , repo_id, obj_json, uri)
                    aspace_tools.link_dao_to_ao(dao_ref, obj_json, uri)
                if not dao_instances == None:
                    print("There's already DAO attached!!")
                    #check DAO file versions for wayback URI. If not not present, create new DAO to hold wayback URI. If present, we can just pass. 
        
                    
        except Exception as e:
            print(f"Failed to process object {getattr(obj, 'uri', '[No URI]')}: {e}")


if __name__ == "__main__":
    sync_aos()