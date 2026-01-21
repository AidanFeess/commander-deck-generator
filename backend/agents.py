import asyncio
import random
from typing import List, Callable
from models import Deck, Card, Combo
from ollama_client import client
from mtg_api import get_card_data
from database import get_inventory

# Personalities
PERSONALITIES = [
    "Aggressive", "Control-freak", "Combo-lover", "Budget-conscious",
    "Flavor-obsessed", "Chaos-bringer"
]

class Agent:
    def __init__(self, name: str, personality: str):
        self.name = name
        self.personality = personality

    async def think(self, context: str, log_callback: Callable):
        await log_callback(self.name, f"Thinking with personality: {self.personality}...")
        prompt = f"You are a Magic: The Gathering deck builder with a {self.personality} personality. {context}"
        response = await client.generate(prompt)
        await log_callback(self.name, f"Suggestion: {response}")
        return response

class DeckBuilder:
    def __init__(self, settings, log_callback: Callable):
        self.settings = settings
        self.log_callback = log_callback
        self.agents = []

        # Initialize agents
        num_agents = max(1, min(3, self.settings.num_agents))
        selected_personalities = random.sample(PERSONALITIES, num_agents)
        for i, p in enumerate(selected_personalities):
            self.agents.append(Agent(f"Agent-{i+1}", p))

    async def generate_deck(self) -> Deck:
        commander = self.settings.commander_name
        mode = self.settings.mode

        await self.log_callback("System", f"Starting deck generation for {commander} in {mode} mode.")

        cards = []

        # Step 1: Strategy Formulation
        strategy_context = f"We are building a Commander deck for {commander}."
        if mode == "Thinking":
            await self.log_callback("System", "Researching strategy...")
            # Simulate "Thinking" steps: Retrieve -> Think -> Retrieve
            strategy_prompt = f"What is the best strategy for a commander deck built around {commander}? Summarize it in one sentence."
            strategy_response = await client.generate(strategy_prompt)
            strategy_context += f" Research suggests: {strategy_response}"
            await self.log_callback("System", f"Strategy Research: {strategy_response}")
            await asyncio.sleep(1)

        # Step 2: Agent Collaboration
        conversation = []
        for agent in self.agents:
            suggestion = await agent.think(strategy_context, self.log_callback)
            conversation.append(f"{agent.name}: {suggestion}")
            if len(self.agents) > 1:
                 # Simulate conversation
                 await asyncio.sleep(0.5)

        # Step 3: Card Selection
        await self.log_callback("System", "Compiling card list...")

        owned_cards_context = ""
        owned_card_names = []
        if self.settings.use_owned_cards:
            await self.log_callback("System", "Checking inventory for owned cards...")
            inventory = get_inventory()
            owned_card_names = [item.name for item in inventory]
            if owned_card_names:
                # Provide a sample of owned cards to guide the LLM, or we can filter later.
                # Since passing the whole DB is too big, we'll ask for recommendations and then prioritize/filter or
                # ask the LLM to choose from a provided subset if the list is small enough.
                # For this implementation, we will append a constraint to the prompt.
                owned_cards_context = f" PREFER cards from this list if they fit: {', '.join(owned_card_names[:50])}..."
            else:
                await self.log_callback("System", "Inventory is empty. Ignoring 'Use Owned Cards'.")

        prompt = f"Create a list of 60 distinct card names (excluding basic lands) for a {commander} EDH deck based on these suggestions: {' '.join(conversation)}. {owned_cards_context} Output just the names separated by commas. Ensure there are exactly 60 names."
        card_names_text = await client.generate(prompt)

        # Parse and verify cards
        card_names = [name.strip() for name in card_names_text.split(',') if name.strip()]

        # Ensure we have some cards even if LLM fails (Fallback list)
        if len(card_names) < 10 or "mock" in card_names_text.lower():
             card_names = ["Sol Ring", "Arcane Signet", "Command Tower", "Swords to Plowshares", "Cultivate", "Kodama's Reach", "Beast Within", "Generous Gift", "Chaos Warp", "Blasphemous Act"]

        verified_cards = []
        for name in card_names:
            # If strict owned mode is simpler:
            if self.settings.use_owned_cards and owned_card_names:
                 # Check if name is in owned_card_names (fuzzy check would be better but exact for now)
                 # Or just prioritize adding them. The prompt asked the LLM to prefer them.
                 # Let's check availability.
                 pass

            # Use thread pool to avoid blocking
            card_data = await asyncio.to_thread(get_card_data, name)
            if card_data:
                await self.log_callback("System", f"Added {name} to deck.")
                verified_cards.append(Card(**card_data))
            else:
                await self.log_callback("System", f"Could not find card {name}.")

        # Fill remaining with Lands (Logic Simplified)
        colors = [] # Would fetch commander colors
        # Just add 35-40 basic lands for now to reach ~100
        land_count = 100 - len(verified_cards)
        if land_count > 0:
             await self.log_callback("System", f"Adding {land_count} lands...")
             # Just add placeholders or basic lands if we knew colors.
             # For mock/demo, adding generic lands.
             verified_cards.append(Card(name="Command Tower", quantity=1, type_line="Land", image_uri="https://cards.scryfall.io/normal/front/b/5/b53a112c-558c-4966-998f-38f96773de56.jpg?1691516763"))
             verified_cards.append(Card(name="Basic Lands (Placeholder)", quantity=land_count-1, type_line="Land", image_uri=""))

        # Step 4: Combo Generation
        await self.log_callback("System", "Searching for combos...")
        combo_prompt = f"List a famous combo for {commander}. Output ONLY in this format: CardName1 + CardName2 + ... | Result | Instructions"
        combo_text = await client.generate(combo_prompt)

        combos = []
        # Basic parsing
        try:
            lines = combo_text.strip().split('\n')
            for line in lines:
                if "|" in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        card_names_str = parts[0].strip()
                        result = parts[1].strip()
                        instructions = parts[2].strip()

                        combo_card_names = [n.strip() for n in card_names_str.split('+')]
                        combo_cards = []
                        for name in combo_card_names:
                            c_data = await asyncio.to_thread(get_card_data, name)
                            if c_data:
                                combo_cards.append(Card(**c_data))

                        if combo_cards:
                            combos.append(Combo(cards=combo_cards, result=result, instructions=instructions))
                            await self.log_callback("System", f"Found combo: {card_names_str} -> {result}")
        except Exception as e:
            await self.log_callback("System", f"Error parsing combos: {e}")

        # Fallback if no combos found
        if not combos:
             # Try to find a simple interaction from the deck list
             if len(verified_cards) >= 2:
                  c1 = verified_cards[0]
                  c2 = verified_cards[1]
                  combos.append(Combo(cards=[c1, c2], result="Synergy", instructions=f"Play {c1.name} and {c2.name} together."))

        deck = Deck(
            commander=commander,
            cards=verified_cards,
            combos=combos,
            status="completed"
        )

        await self.log_callback("System", "Deck generation complete.")
        return deck
