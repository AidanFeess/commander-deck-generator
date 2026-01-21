import sqlite3
import json
from typing import List, Optional
from models import InventoryItem, Deck, Card, Combo

DB_NAME = "mtg_app.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Inventory Table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        set_code TEXT,
        collector_number TEXT,
        image_uri TEXT,
        type_line TEXT,
        oracle_text TEXT,
        mana_cost TEXT,
        cmc REAL,
        colors TEXT,
        quantity INTEGER DEFAULT 1
    )''')

    # Decks Table
    c.execute('''CREATE TABLE IF NOT EXISTS decks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        commander TEXT NOT NULL,
        cards_json TEXT,
        combos_json TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

def add_inventory_item(card: InventoryItem):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Check if exists
    c.execute("SELECT id, quantity FROM inventory WHERE name = ?", (card.name,))
    row = c.fetchone()
    if row:
        new_qty = row[1] + card.quantity
        c.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, row[0]))
    else:
        c.execute('''INSERT INTO inventory (name, set_code, collector_number, image_uri, type_line, oracle_text, mana_cost, cmc, colors, quantity)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (card.name, card.set_code, card.collector_number, card.image_uri, card.type_line, card.oracle_text, card.mana_cost, card.cmc, json.dumps(card.colors), card.quantity))
    conn.commit()
    conn.close()

def get_inventory() -> List[InventoryItem]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM inventory")
    rows = c.fetchall()
    conn.close()

    inventory = []
    for row in rows:
        item = InventoryItem(
            id=row['id'],
            name=row['name'],
            set_code=row['set_code'],
            collector_number=row['collector_number'],
            image_uri=row['image_uri'],
            type_line=row['type_line'],
            oracle_text=row['oracle_text'],
            mana_cost=row['mana_cost'],
            cmc=row['cmc'],
            colors=json.loads(row['colors']) if row['colors'] else [],
            quantity=row['quantity']
        )
        inventory.append(item)
    return inventory

def delete_inventory_item(item_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def create_deck(deck: Deck) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    cards_json = json.dumps([c.model_dump() for c in deck.cards])
    combos_json = json.dumps([c.model_dump() for c in deck.combos])
    c.execute("INSERT INTO decks (commander, cards_json, combos_json, status) VALUES (?, ?, ?, ?)",
              (deck.commander, cards_json, combos_json, deck.status))
    deck_id = c.lastrowid
    conn.commit()
    conn.close()
    return deck_id

def update_deck_status(deck_id: int, status: str, cards: List[Card] = None, combos: List[Combo] = None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if cards is not None:
        cards_json = json.dumps([c.model_dump() for c in cards])
        c.execute("UPDATE decks SET status = ?, cards_json = ? WHERE id = ?", (status, cards_json, deck_id))
    if combos is not None:
        combos_json = json.dumps([c.model_dump() for c in combos])
        c.execute("UPDATE decks SET status = ?, combos_json = ? WHERE id = ?", (status, combos_json, deck_id))
    else:
        c.execute("UPDATE decks SET status = ? WHERE id = ?", (status, deck_id))
    conn.commit()
    conn.close()

def get_deck(deck_id: int) -> Optional[Deck]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM decks WHERE id = ?", (deck_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return Deck(
            id=row['id'],
            commander=row['commander'],
            cards=[Card(**c) for c in json.loads(row['cards_json'])],
            combos=[Combo(**c) for c in json.loads(row['combos_json'])] if row['combos_json'] else [],
            status=row['status'],
            created_at=str(row['created_at'])
        )
    return None

def get_all_decks() -> List[Deck]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM decks ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()

    decks = []
    for row in rows:
        decks.append(Deck(
            id=row['id'],
            commander=row['commander'],
            cards=[Card(**c) for c in json.loads(row['cards_json'])],
            combos=[Combo(**c) for c in json.loads(row['combos_json'])] if row['combos_json'] else [],
            status=row['status'],
            created_at=str(row['created_at'])
        ))
    return decks
