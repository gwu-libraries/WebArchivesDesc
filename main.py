import argparse
from asnake.aspace import ASpace
from config import Config
import aspace_tools
import at_tools
from datetime import datetime

# Initialize ArchivesSpace client
aspace = ASpace(
    baseurl=Config.aspace_host,
    username=Config.aspace_user,
    password=Config.aspace_pass
)


def process_archival_object(obj_json, seeds, repo_id, subject):
    uri = obj_json['uri']

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

        #these aspace_tools functions return false/true depending on if they updated anything
        dates_changed = aspace_tools.update_dates(obj_json, begin_date, end_date, date_expression, Config.crawl_date_label)
        extent_changed = aspace_tools.update_extent(obj_json, extent, Config)
        note1_changed = aspace_tools.update_or_create_note(obj_json, "phystech", Config.data_access_note_scrc, Config.data_access_label)
        note2_changed = aspace_tools.update_or_create_note(obj_json, "acqinfo", Config.acq_note_scrc, Config.acq_note_label)

        #if any of the above = TRUE, an update is required. Post new AO
        if any([dates_changed, extent_changed, note1_changed, note2_changed]):
            response = aspace.client.post(uri, json=obj_json)
            print(f"Updated archival object {uri}: {response.status_code}")
            obj_json = aspace.client.get(uri).json()  # refetch to avoid conflicts
        else:
            print(f"No changes detected for {uri}. Skipping save.")

        # Update parent and resource record dates
        parent_json = aspace_tools.get_parent_json(obj_json)
        if parent_json:
            aspace_tools.update_ancestor_dates_if_needed(parent_json, begin_date, end_date)

        resource_json = aspace_tools.get_resource_json(obj_json)
        if resource_json:
            begin_year = datetime.strptime(begin_date, "%Y-%m-%d").year
            end_year = datetime.strptime(end_date, "%Y-%m-%d").year
            aspace_tools.update_ancestor_dates_if_needed(resource_json, begin_year, end_year)

        # Update or create DAO
        wayback_uri = at_tools.build_wayback_url(collection_id, note_url)
        dao_instances = aspace_tools.get_digital_object_instance(obj_json)

        if dao_instances is None:
            print(f"No DAO attached to {uri}. Creating new DAO.")
            dao_ref = aspace_tools.create_new_dao(
                wayback_uri,
                obj_json.get('ref_id'),
                f"Web Archives Replay Calendar - {note_url}",
                repo_id,
                obj_json,
                uri
            )
            aspace_tools.link_dao_to_ao(dao_ref, obj_json, uri)
        else:
            print("DAO already exists — skipping DAO creation.")


def update_all_webarchive_aos():
    repo_id = Config.aspace_repo
    subject = Config.subject
    seeds = at_tools.get_all_seeds()

    results = aspace_tools.search_ao_by_subject(repo_id, subject)
    print(f"Found {len(results)} archival objects for subject '{subject}':\n")

    for obj in results:
        try:
            obj_json = obj.json()
            process_archival_object(obj_json, seeds, repo_id, subject)
        except Exception as e:
            print(f"Failed to process object {getattr(obj, 'uri', '[No URI]')}: {e}")

def update_single_archival_object(refid):
    repo_id = Config.aspace_repo
    seeds = at_tools.get_all_seeds()

    try:
        find_url = f"/repositories/{repo_id}/find_by_id/archival_objects?ref_id[]={refid}"
        response = aspace.client.get(find_url)
        response.raise_for_status()
        results = response.json()

        archival_objects = results.get("archival_objects", [])
        if len(archival_objects) != 1:
            print(f"{len(archival_objects)} results found for ref_id '{refid}'. Expected exactly 1.")
            return

        uri = archival_objects[0]["ref"]
        print(f"Found archival object: {uri}")

        obj_json = aspace.client.get(uri).json()
        process_archival_object(obj_json, seeds, repo_id, subject=Config.subject)

    except Exception as e:
        print(f"Error updating AO with refid '{refid}': {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync records that describe web archives in ArchivesSpace using Archive-it intergrations")
    parser.add_argument("--all", action="store_true", help="Update all web archives records.")
    parser.add_argument("--refid", type=str, help="Update a single archival object by ref_id.")

    args = parser.parse_args()

    if args.all:
        update_all_webarchive_aos()
    elif args.refid:
        update_single_archival_object(args.refid)
    else:
        parser.print_help()
