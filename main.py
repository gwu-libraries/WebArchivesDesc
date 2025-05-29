from asnake.aspace import ASpace
from config import config

# Initialize ArchivesSpace client once
aspace = ASpace(
    baseurl=config['aspace_host'],
    username=config['aspace_user'],
    password=config['aspace_pass']
)

def search_archival_objects_by_subject(repo_id: int, subject_term: str):
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

# Example usage
if __name__ == "__main__":
    repo_id = config['aspace_repo']
    subject = "Web Archives"
    results = search_archival_objects_by_subject(repo_id, subject)
    print(f"Found {len(results)} archival objects for subject '{subject}':")
    for obj in results:
        try:
            print(obj)
        except AttributeError:
            print("no obj")
