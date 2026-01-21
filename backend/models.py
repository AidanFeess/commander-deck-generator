from pydantic import BaseModel
from typing import List, Optional, Dict

class Card(BaseModel):
    name: str
    set_code: Optional[str] = None
    collector_number: Optional[str] = None
    image_uri: Optional[str] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    mana_cost: Optional[str] = None
    cmc: Optional[float] = None
    colors: Optional[List[str]] = None
    quantity: int = 1

class InventoryItem(Card):
    id: Optional[int] = None

class CommanderRequest(BaseModel):
    prompt: str

class CommanderDetails(BaseModel):
    name: str
    image_uri: Optional[str] = None

class CommanderResponse(BaseModel):
    name: str
    reasoning: str
    image_uri: Optional[str] = None
    commanders: List[CommanderDetails] = []

class DeckSettings(BaseModel):
    commander_name: str
    mode: str # "Thinking" or "Fast"
    num_agents: int = 1
    num_decks: int = 1
    use_owned_cards: bool = False

class Combo(BaseModel):
    cards: List[Card]
    result: str
    instructions: str

class Deck(BaseModel):
    id: Optional[int] = None
    commander: str
    cards: List[Card]
    combos: List[Combo] = []
    status: str = "pending" # pending, generating, completed, failed
    created_at: str = ""

class LogMessage(BaseModel):
    process_id: str
    agent_name: str
    message: str
    timestamp: float
