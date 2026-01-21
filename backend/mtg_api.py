import requests
import time
from typing import Optional, Dict, List

SCRYFALL_API_URL = "https://api.scryfall.com"

def parse_card_data(data: Dict) -> Dict:
    """Helper to parse raw Scryfall data into our dictionary format."""
    # Extract relevant fields
    image_uri = ""
    if 'image_uris' in data and 'normal' in data['image_uris']:
        image_uri = data['image_uris']['normal']
    elif 'card_faces' in data:
        # Handle double-faced cards (MDFCs, Transform)
        if 'image_uris' in data['card_faces'][0]:
            image_uri = data['card_faces'][0]['image_uris']['normal']

    # Fallback
    if not image_uri and 'image_uris' in data:
            image_uri = data['image_uris'].get('normal', '')

    oracle_text = data.get('oracle_text', "")
    if not oracle_text and 'card_faces' in data:
        # Combine oracle text of faces
        oracle_text = "\n//\n".join([face.get('oracle_text', '') for face in data['card_faces']])

    return {
        "name": data['name'],
        "set_code": data['set'],
        "collector_number": data['collector_number'],
        "image_uri": image_uri,
        "type_line": data['type_line'],
        "oracle_text": oracle_text,
        "mana_cost": data.get('mana_cost', ""),
        "cmc": data.get('cmc', 0),
        "colors": data.get('colors', []),
        "color_identity": data.get('color_identity', []),
    }

def get_card_data(card_name: str) -> Optional[Dict]:
    """
    Fetch card data from Scryfall.
    """
    try:
        # Fuzzy search is better for user input
        response = requests.get(f"{SCRYFALL_API_URL}/cards/named", params={"fuzzy": card_name})
        if response.status_code == 200:
            return parse_card_data(response.json())
        else:
            return None
    except Exception as e:
        print(f"Error fetching card {card_name}: {e}")
        return None

def search_scryfall(query: str, limit: int = 50) -> List[Dict]:
    """
    Search Scryfall using their advanced search syntax.
    Returns a list of parsed card dictionaries.
    """
    try:
        # Use /cards/search endpoint
        # Scryfall returns 175 cards per page max.
        response = requests.get(f"{SCRYFALL_API_URL}/cards/search", params={"q": query})

        if response.status_code == 200:
            json_data = response.json()
            data_list = json_data.get('data', [])

            # Limit results
            results = []
            for item in data_list[:limit]:
                results.append(parse_card_data(item))
            return results
        else:
            print(f"Scryfall search error ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        print(f"Error searching scryfall for '{query}': {e}")
        return []

def search_card(query: str) -> Optional[Dict]:
    # Similar to get_card_data but maybe for commander search
    return get_card_data(query)
