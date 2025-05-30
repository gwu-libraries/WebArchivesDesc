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