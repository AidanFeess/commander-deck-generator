import asyncio
import time
from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

from models import InventoryItem, CommanderRequest, CommanderResponse, CommanderDetails, DeckSettings, Deck, LogMessage, Card
from database import init_db, add_inventory_item, get_inventory, delete_inventory_item, create_deck, update_deck_status, get_deck, get_all_decks
from mtg_api import get_card_data, search_scryfall
from ollama_client import client
from agents import DeckBuilder

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, process_id: str):
        await websocket.accept()
        if process_id not in self.active_connections:
            self.active_connections[process_id] = []
        self.active_connections[process_id].append(websocket)

    def disconnect(self, websocket: WebSocket, process_id: str):
        if process_id in self.active_connections:
            self.active_connections[process_id].remove(websocket)

    async def broadcast(self, message: LogMessage, process_id: str):
        if process_id in self.active_connections:
            for connection in self.active_connections[process_id]:
                await connection.send_json(message.model_dump())

manager = ConnectionManager()

@app.on_event("startup")
def on_startup():
    init_db()

# Inventory Endpoints
@app.get("/api/inventory", response_model=List[InventoryItem])
def list_inventory():
    return get_inventory()

@app.post("/api/inventory/add")
def add_card(card_name: str):
    data = get_card_data(card_name)
    if not data:
        raise HTTPException(status_code=404, detail=f"Card '{card_name}' not found.")

    item = InventoryItem(**data)
    add_inventory_item(item)
    return item

@app.delete("/api/inventory/{item_id}")
def delete_card(item_id: int):
    delete_inventory_item(item_id)
    return {"status": "success"}

@app.post("/api/inventory/import")
def import_cards(text: str):
    failed = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        # Simple parsing: "1 Card Name" or "Card Name"
        parts = line.split(' ', 1)
        qty = 1
        name = line
        if parts[0].isdigit():
            qty = int(parts[0])
            name = parts[1]

        data = get_card_data(name)
        if data:
            data['quantity'] = qty
            item = InventoryItem(**data)
            add_inventory_item(item)
        else:
            failed.append(name)

    if failed:
        return JSONResponse(status_code=207, content={"failed": failed, "message": "Some cards failed to import."})
    return {"status": "success"}

# Deck Generation Endpoints
@app.post("/api/generate/commander", response_model=CommanderResponse)
async def generate_commander(request: CommanderRequest):
    # Step 1: Formulate a Search Query
    query_prompt = (
        f"The user wants a commander deck with this description: '{request.prompt}'.\n"
        f"Create a Scryfall search query to find candidates. "
        f"The query MUST include 't:legendary' and ('t:creature' or 'o:can be your commander'). "
        f"Include color constraints if specified in the description (e.g. 'c>=br' or 'id:g'). "
        f"Output ONLY the raw query string."
    )
    raw_query = await client.generate(query_prompt)
    search_query = raw_query.strip().replace("Query:", "").replace("`", "").strip()

    # Fallback to general search if prompt is weird
    if "t:legendary" not in search_query:
        search_query += " t:legendary (t:creature or o:\"can be your commander\")"

    # Step 2: Search Scryfall
    candidates = await asyncio.to_thread(search_scryfall, search_query, limit=10)

    # If search fails, fallback to old method (direct prompt) or simple search
    if not candidates:
        fallback_query = "t:legendary (t:creature or o:\"can be your commander\")"
        candidates = await asyncio.to_thread(search_scryfall, fallback_query, limit=10)

    # Step 3: AI Selection
    # Format candidates for the LLM
    candidate_text = ""
    for c in candidates:
        candidate_text += f"- {c['name']} (ID: {c.get('color_identity')}, Type: {c['type_line']}): {c['oracle_text'][:100]}...\n"

    selection_prompt = (
        f"The user wants a deck described as: '{request.prompt}'.\n"
        f"Here are valid commander candidates found via search:\n"
        f"{candidate_text}\n"
        f"Select the single best fit (or a legal partner pair from the list if applicable).\n"
        f"Return the response in exactly two lines:\n"
        f"Line 1: The name(s) of the chosen card(s) ONLY.\n"
        f"Line 2: A 1-2 sentence reasoning."
    )

    response_text = await client.generate(selection_prompt)
    lines = response_text.strip().split('\n')
    name_line = lines[0].replace("Commander:", "").strip()
    reasoning = " ".join(lines[1:]).replace("Reasoning:", "").strip()

    # Step 4: Verification
    commander_names = [n.strip() for n in name_line.split('+')]
    commanders_details = []
    primary_image = None

    for c_name in commander_names:
        # We can look up in our candidates list first to save a call, but get_card_data is cached/fast enough
        data = await asyncio.to_thread(get_card_data, c_name)
        if data:
            # Re-verify validity (double check)
            type_line = data.get('type_line', '').lower()
            oracle_text = data.get('oracle_text', '').lower()
            is_valid = ("legendary" in type_line and "creature" in type_line) or \
                       ("planeswalker" in type_line and "can be your commander" in oracle_text)

            img = data.get('image_uri')
            commanders_details.append(CommanderDetails(name=data['name'], image_uri=img))
            if not primary_image:
                primary_image = img
        else:
             commanders_details.append(CommanderDetails(name=c_name, image_uri=None))

    if not commanders_details:
        # Total failure fallback
        clean_name = "Unknown Commander"
    else:
        clean_name = " + ".join([c.name for c in commanders_details])

    return CommanderResponse(
        name=clean_name,
        reasoning=reasoning,
        image_uri=primary_image,
        commanders=commanders_details
    )

async def run_deck_generation(deck_id: int, settings: DeckSettings):
    process_id = str(deck_id)

    async def log_callback(agent_name: str, message: str):
        log_msg = LogMessage(
            process_id=process_id,
            agent_name=agent_name,
            message=message,
            timestamp=time.time()
        )
        await manager.broadcast(log_msg, process_id)

    builder = DeckBuilder(settings, log_callback)

    update_deck_status(deck_id, "generating")
    try:
        deck = await builder.generate_deck()
        update_deck_status(deck_id, "completed", deck.cards, deck.combos)
    except Exception as e:
        await log_callback("System", f"Error: {str(e)}")
        update_deck_status(deck_id, "failed")

@app.post("/api/generate/deck")
def start_deck_generation(settings: DeckSettings, background_tasks: BackgroundTasks):
    primary_deck_id = None
    count = max(1, min(4, settings.num_decks))

    for i in range(count):
        deck = Deck(commander=settings.commander_name, cards=[], combos=[], status="pending")
        deck_id = create_deck(deck)
        if i == 0:
            primary_deck_id = deck_id

        background_tasks.add_task(run_deck_generation, deck_id, settings)

    return {"deck_id": primary_deck_id}

@app.get("/api/deck/{deck_id}", response_model=Deck)
def get_deck_details(deck_id: int):
    deck = get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck

@app.get("/api/decks", response_model=List[Deck])
def list_decks():
    return get_all_decks()

@app.websocket("/ws/process/{process_id}")
async def websocket_endpoint(websocket: WebSocket, process_id: str):
    await manager.connect(websocket, process_id)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket, process_id)
