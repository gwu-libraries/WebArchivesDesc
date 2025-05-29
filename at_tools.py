import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from urllib.parse import urlparse
from collections import Counter
import tldextract
from config import Config

# Archive-It API credentials
USERNAME = Config.AI_user
PASSWORD = Config.AI_pass

# Partner API endpoint
SEED_API_URL = 'https://partner.archive-it.org/api/seed'
SEED_PARAMS = {'sort': 'created_date', 'limit': -1}


def get_all_seeds():
    try:
        response = requests.get(SEED_API_URL, auth=HTTPBasicAuth(USERNAME, PASSWORD), params=SEED_PARAMS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching seeds: {e}")
        return []


def find_seed_by_url(seeds, target_url):
    return next((s for s in seeds if s.get('url') == target_url), None)


def extract_domain(url):
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"


def infer_collection_from_similar_seeds(seeds, target_url):
    target_domain = extract_domain(target_url)
    similar = [s for s in seeds if extract_domain(s['url']) == target_domain]
    
    if not similar:
        return None

    # Count collections in similar seeds
    collections = [s['collection'] for s in similar]
    most_common = Counter(collections).most_common(1)
    return most_common[0][0] if most_common else None


def fetch_cdx_records(collection_id, url):
    endpoint = f"https://wayback.archive-it.org/{collection_id}/timemap/cdx"
    params = {"url": url, "fl": "timestamp,length"}

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        return [tuple(line.split()) for line in lines if len(line.split()) == 2]
    except requests.RequestException as e:
        print(f"Error querying CDX API: {e}")
        return []


def get_earliest_date(records):
    timestamps = sorted(ts for ts, _ in records)
    return datetime.strptime(timestamps[0], "%Y%m%d%H%M%S").date().isoformat() if timestamps else None


def get_latest_date(records):
    timestamps = sorted(ts for ts, _ in records)
    return datetime.strptime(timestamps[-1], "%Y%m%d%H%M%S").date().isoformat() if timestamps else None


def summarize_url_activity(url, seeds):
    seed = find_seed_by_url(seeds, url)
    if seed:
        collection_id = seed['collection']
        print(f"Found seed for URL in collection {collection_id}")
    else:
        print(f"No seed found for URL: {url}")
        collection_id = infer_collection_from_similar_seeds(seeds, url)
        if collection_id:
            print(f"Inferred collection: {collection_id}")
        else:
            print("Could not infer collection — skipping")
            return

    records = fetch_cdx_records(collection_id, url)
    if not records:
        print("No CDX records found.")
        return

    print(f"Begin Date: {get_earliest_date(records)}")
    print(f"End Date:   {get_latest_date(records)}")
    print(f"Extent:     {len(records)} crawls")

def build_wayback_url(collection_id, url):
    return f"https://wayback.archive-it.org/{collection_id}/*/{url}"


if __name__ == "__main__":
    target_url = input("Enter the URL to analyze: ").strip()
    seeds = get_all_seeds()
    summarize_url_activity(target_url, seeds)