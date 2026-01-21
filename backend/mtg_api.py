import requests
import time
from typing import Optional, Dict

SCRYFALL_API_URL = "https://api.scryfall.com"

def get_card_data(card_name: str) -> Optional[Dict]:
    """
    Fetch card data from Scryfall.
    """
    try:
        # Fuzzy search is better for user input
        response = requests.get(f"{SCRYFALL_API_URL}/cards/named", params={"fuzzy": card_name})
        if response.status_code == 200:
            data = response.json()
            # Extract relevant fields
            image_uri = ""
            if 'image_uris' in data and 'normal' in data['image_uris']:
                image_uri = data['image_uris']['normal']
            elif 'card_faces' in data:
                # Handle double-faced cards (MDFCs, Transform)
                # Some have images on faces, some just have one main image (rare case)
                if 'image_uris' in data['card_faces'][0]:
                    image_uri = data['card_faces'][0]['image_uris']['normal']

            # Fallback
            if not image_uri and 'image_uris' in data:
                 image_uri = data['image_uris'].get('normal', '')

            oracle_text = data.get('oracle_text', "")
            if not oracle_text and 'card_faces' in data:
                # Combine oracle text of faces
                oracle_text = "\n//\n".join([face.get('oracle_text', '') for face in data['card_faces']])

            colors = data.get('colors', [])
            if not colors and 'card_faces' in data:
                 # Start with empty list and add colors from all faces?
                 # Actually color identity is better for commander checks, but 'colors' is usually on faces for transform
                 pass

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
            }
        else:
            return None
    except Exception as e:
        print(f"Error fetching card {card_name}: {e}")
        return None

def search_card(query: str) -> Optional[Dict]:
    # Similar to get_card_data but maybe for commander search
    return get_card_data(query)
