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
        label_regex (bool): If True, treat `label` as a regex pattern.
    
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