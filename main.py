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
                dates_changed = aspace_tools.update_dates(obj_json, begin_date, end_date, date_expression, Config)

                # --- UPDATE EXTENTS ---
                extent_changed = aspace_tools.update_extent(obj_json, extent, Config)

                # --- UPDATE PARENT DATES IF NEEDED ---
                #update the direct parent of the obj_json (ao)
                parent_json = aspace_tools.get_parent_json(obj_json)
                parent_changed = aspace_tools.update_ancestor_dates_if_needed(parent_json, begin_date, end_date)
                #update the resource record for the AO. 
                #We only really want to post YYYY - YYYY dates to resource records since that's the SCRC norm.
                begin_date_year = datetime.strptime(begin_date, "%Y-%m-%d").year
                end_date_year = datetime.strptime(end_date, "%Y-%m-%d").year
                resource_json = aspace_tools.get_resource_json(obj_json)    
                resource_changed = aspace_tools.update_ancestor_dates_if_needed(resource_json, begin_date_year, end_date_year)

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