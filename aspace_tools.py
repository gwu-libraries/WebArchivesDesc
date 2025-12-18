from asnake.aspace import ASpace
from config import Config
import re

# Initialize aspace client once
aspace = ASpace(
    baseurl=Config.aspace_host,
    username=Config.aspace_user,
    password=Config.aspace_pass
)

def search_ao_by_subject(repo_id: int, subject_term: str):
    """
    Search archival objects in the given repository by subject term.
    
    Args:
        repo_id: The repository ID in ArchivesSpace.
        subject_term: The subject term or phrase to search for.
                      If multiword, no need to add quotes — function adds them.
    
    Returns:
        list: List of archival object results (asnake jsonmodelobjects).
    """
    repo = aspace.repositories(repo_id)

    # Ensure multiword phrases are quoted for exact matching
    if ' ' in subject_term and not (subject_term.startswith('"') and subject_term.endswith('"')):
        subject_term = f'"{subject_term}"'

    query = f"primary_type:archival_object AND subjects:{subject_term}"
    search_results = repo.search.with_params(q=query)
    
    return list(search_results)

def extract_notes_by_label_or_type(archival_object, label=None, note_type=None, label_regex=False):
    """
    Extracts note content from an archival object filtered by note label and/or type.
    
    Args:
        archival_object (dict): The archival object JSON.
        label (str, optional): The label of the note to match.
        note_type (str, optional): The type of the note to match.
        label_regex (bool): If True, treat label as a regex pattern.
    
    Returns:
        List[str]: A list of cleaned note contents that match the criteria.
    """
    results = []

    notes = archival_object.get("notes", [])
    for note in notes:
        if label:
            note_label = note.get("label", "")
            if label_regex:
                if not re.search(label, note_label):
                    continue
            else:
                if note_label != label:
                    continue
        if note_type and note.get("type") != note_type:
            continue

        for subnote in note.get("subnotes", []):
            if subnote.get("jsonmodel_type") == "note_text":
                content = subnote.get("content", "").strip()
                if content:
                    results.append(content)

    return results

def get_digital_object_instance(ao_json):
    instances = ao_json.get('instances', [])
    for inst in instances:
        if inst.get('instance_type') == 'digital_object' and 'digital_object' in inst:
            return inst
    return None

def fetch_digital_object(digital_object_ref):
    return aspace.client.get(digital_object_ref).json()

def create_new_dao(file_uri, digital_object_id, title, repo_id, ao_json, uri):
    """
    Creates a digital object record and links it to an archival object.
    """
    dao_json = {
        "jsonmodel_type": "digital_object",
        "title": title,
        "digital_object_id": digital_object_id,
        "file_versions": [
            {
                "jsonmodel_type": "file_version",
                "file_uri": file_uri,
                "use_statement": "webarchives_access_replay",
                "xlink_actuate_attribute": "onRequest",
                "xlink_show_attribute": "new",
                "publish": True,
                "is_representative": False,
            }
        ],
        "publish": True
    }

    response = aspace.client.post(f"/repositories/{repo_id}/digital_objects", json=dao_json)

    if response.status_code == 200:
        dao_ref = response.json().get("uri")
        print(f"Created new DAO record: {dao_ref}")
        return dao_ref
    else:
        print(f"Failed to create DAO. Status: {response.status_code}")
        print(f"Response text: {response.text}")
        return None
    
def link_dao_to_ao(dao_ref, ao_json, uri):
    instances = ao_json.get("instances", [])
    instances.append({
        "instance_type": "digital_object",
        "digital_object": {"ref": dao_ref}
    })
    ao_json["instances"] = instances

    response = aspace.client.post(uri, json=ao_json)
    if response.status_code == 200: 
        return response.json()
    else:
        print(f"Failed to link DAO to AO. Status: {response.status_code}")
        print(f"Response text: {response.text}")
        return None
    
def update_dates(ao_json, begin_date, end_date, date_expression, crawl_date_label):
    """
    Update or create a "captured" date subcrecord on the archival object JSON. 
    """

    dates = ao_json.get('dates', [])

    #look for exsisting date subrecord that represents capture/crawl date information
    target_date_obj = None
    for date in dates:
        #if an exsisting subrecord matches the label, use that one to check against web capture dates
        if date.get('label') == crawl_date_label:
            target_date_obj = date
            break
    #if found exsisting date subrecord, check if it needs to be updated
    if target_date_obj:
        needs_update = False

        if target_date_obj.get('begin') != begin_date:
            target_date_obj['begin'] = begin_date
            needs_update = True 

        if target_date_obj.get('end') != end_date:
            target_date_obj['end'] = end_date
            needs_update = True 

        if target_date_obj.get('expression') != date_expression:
            target_date_obj['expression'] = date_expression
            needs_update = True
        
        return needs_update
    else: #if no subrecord with a capture date label we sound then we need to create a new date subrecord to hold the web capture dates
        new_capture_dates = {
            'jsonmodel_type': 'date',
            'date_type': 'inclusive',
            'label': crawl_date_label,
            'begin': begin_date,
            'end': end_date,
            'expression': date_expression
        }
        ao_json['dates'].append(new_capture_dates)
        return True  #new date created, so return true to indicate change made



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
    
def get_parent_json(child_json):
    '''Takes a child JSON, finds the parent ref, and retrieves the parent JSON'''
    parent_ref = child_json.get('parent', {}).get('ref')
    if not parent_ref:
        return False  # No parent to update

    parent_json = aspace.client.get(parent_ref).json()
    return parent_json

def get_resource_json(child_json):  
    resource_ref = child_json.get('resource', {}).get('ref')
    if not resource_ref:
        return False
    resource_json = aspace.client.get(resource_ref).json()
    return resource_json

def update_ancestor_dates_if_needed(ancestor_json, begin_date, end_date):
    """
    Ensure the ancestor (another AO or resource record) range includes the child's date range.
    If the parent date is missing or narrower, update it and return True.
    """
    parent_dates = ancestor_json.get('dates', [])
    needs_update = False

    # Ensure begin and end are strings
    begin_date = str(begin_date) if begin_date is not None else None
    end_date = str(end_date) if end_date is not None else None

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
        ancestor_json['dates'] = [new_date]
        needs_update = True

    else:
        # Update existing date if it doesn't span the child's date
        date_obj = parent_dates[0]
        parent_begin = date_obj.get('begin')
        parent_end = date_obj.get('end')

        if begin_date:
            if not parent_begin or begin_date < parent_begin:
                date_obj['begin'] = begin_date
                needs_update = True

        if end_date:
            if not parent_end or end_date > parent_end:
                date_obj['end'] = end_date
                needs_update = True

        if needs_update:
            expression = date_obj['begin']
            if 'end' in date_obj and date_obj['end']:
                expression += f" - {date_obj['end']}"
            date_obj['expression'] = expression

    if needs_update:
        response = aspace.client.post(ancestor_json['uri'], json=ancestor_json)
        if response.status_code == 200:
            print(f"Updated parent AO {ancestor_json['uri']} with expanded date range.")
        else:
            print(f"Failed to update parent AO {ancestor_json['uri']}. Status: {response.status_code}")
            print(response.text)

    return needs_update

def makeMultiNote(obj_dict, note_type, text, label=None):
    note = {
        "type": note_type,
        "jsonmodel_type": "note_multipart",
        "publish": True,
        "subnotes": [
            {"content": text, "jsonmodel_type": "note_text", "publish": True}
        ]
    }
    if label is not None:
        note["label"] = label

    if "notes" not in obj_dict or obj_dict["notes"] is None:
        obj_dict["notes"] = [note]
    else:
        obj_dict["notes"].append(note)



def update_or_create_note(obj_dict, note_type, expected_text, label=None):
    notes = obj_dict.get("notes", [])
    updated = False
    for note in notes:
        if (
            note.get("type") == note_type
            and note.get("jsonmodel_type") == "note_multipart"
            and (label is None or note.get("label") == label)
        ):
            for subnote in note.get("subnotes", []):
                if subnote.get("jsonmodel_type") == "note_text":
                    if subnote.get("content") != expected_text:
                        subnote["content"] = expected_text
                        updated = True
                        print("Note updated.")
                    else:
                        print("Note already matches.")
                    return updated  # Exit after first matching note

    # No matching note found — create a new one
    makeMultiNote(obj_dict, note_type, expected_text, label)
    print("New note created.")
    return True


