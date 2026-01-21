import asyncio
import time
from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

from models import InventoryItem, CommanderRequest, CommanderResponse, DeckSettings, Deck, LogMessage, Card
from database import init_db, add_inventory_item, get_inventory, delete_inventory_item, create_deck, update_deck_status, get_deck, get_all_decks
from mtg_api import get_card_data
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
    prompt = f"You are an advanced Magic: The Gathering commander deckbuilder. Suggest a Magic: The Gathering Commander based on this request: {request.prompt}. Valid commanders are Legendary Creatures or Planeswalkers with the text 'This can be a commander'. Return ONLY the name of the card in the first line, and a 1-2 sentence reasoning in the second line."
    response_text = await client.generate(prompt)
    lines = response_text.strip().split('\n')
    name = lines[0].replace("Commander:", "").strip()
    reasoning = " ".join(lines[1:]).replace("Reasoning:", "").strip()

    # Verify card exists (use async or thread pool for IO)
    data = await asyncio.to_thread(get_card_data, name)
    image_uri = data.get('image_uri') if data else None

    return CommanderResponse(name=name, reasoning=reasoning, image_uri=image_uri)

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
        # Store log in DB? (Simplified: Not storing logs in DB for now, just streaming)

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
    # Create initial deck entry (or entries based on num_decks)
    # The UI only tracks one ID, so we return the first one.
    # Future improvements: return list of IDs or handle batch generation UI.

    primary_deck_id = None

    count = max(1, min(4, settings.num_decks))

    for i in range(count):
        deck = Deck(commander=settings.commander_name, cards=[], combos=[], status="pending")
        deck_id = create_deck(deck)
        if i == 0:
            primary_deck_id = deck_id

        # Start generation for each deck
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
            await websocket.receive_text() # Keep connection open
    except Exception:
        manager.disconnect(websocket, process_id)

# Serve Frontend (Build output or Static)
# For this dev setup, we will just mount the frontend folder if we built it.
# But since we are using Vite in dev mode for logs, we might just proxy or let user run vite.
# However, for a "Sleek Web App" deliverable, I should probably build the frontend.

# For now, I won't mount static files yet until I build the frontend.
