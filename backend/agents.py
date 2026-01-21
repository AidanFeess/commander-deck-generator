import asyncio
import random
from typing import List, Callable, Dict, Set
from models import Deck, Card, Combo
from ollama_client import client
from mtg_api import get_card_data, search_scryfall
from database import get_inventory

# Personalities
PERSONALITIES = [
    "Aggressive", "Control-freak", "Combo-lover", "Budget-conscious",
    "Flavor-obsessed", "Chaos-bringer", "Normal"
]

class Agent:
    def __init__(self, name: str, personality: str):
        self.name = name
        self.personality = personality

    async def analyze_candidates(self, candidates: List[Dict], strategy: str, log_callback: Callable) -> List[str]:
        """
        Analyze a batch of cards and vote on them.
        Returns a list of card names that this agent approves.
        """
        # Simplify candidate data for the LLM to save context
        simplified_candidates = []
        for c in candidates:
            simplified_candidates.append(f"{c['name']} ({c['type_line']}): {c['oracle_text'][:150]}")

        prompt = (
            f"You are a Magic: The Gathering deck builder with a {self.personality} personality.\n"
            f"Strategy: {strategy}\n"
            f"Analyze these cards and pick the ones that fit the deck:\n"
            f"{' | '.join(simplified_candidates)}\n"
            f"Return ONLY the names of the cards you approve, separated by commas. If none, return 'None'."
        )

        response = await client.generate(prompt)
        await log_callback(self.name, f"Analyzed batch. Approved: {response}")

        approved = [name.strip() for name in response.split(',') if name.strip() and name.lower() != 'none']
        return approved

class DeckBuilder:
    def __init__(self, settings, log_callback: Callable):
        self.settings = settings
        self.log_callback = log_callback
        self.agents = []
        self.commander_colors: Set[str] = set()
        self.commander_names: List[str] = []

        # Initialize agents
        num_agents = max(1, min(3, self.settings.num_agents))
        selected_personalities = random.sample(PERSONALITIES, num_agents)
        for i, p in enumerate(selected_personalities):
            self.agents.append(Agent(f"Agent-{i+1}", p))

    async def get_commander_identity(self):
        names = [n.strip() for n in self.settings.commander_name.split('+')]
        self.commander_names = names

        for name in names:
            data = await asyncio.to_thread(get_card_data, name)
            if data:
                self.commander_colors.update(data.get('color_identity', []))

        await self.log_callback("System", f"Commander Identity established: {', '.join(self.commander_colors) if self.commander_colors else 'Colorless'}")

    def is_color_compatible(self, card_identity: List[str]) -> bool:
        return set(card_identity).issubset(self.commander_colors)

    async def generate_deck(self) -> Deck:
        commander = self.settings.commander_name

        # Step 0: Setup
        await self.get_commander_identity()
        verified_cards: List[Card] = []
        verified_card_names: Set[str] = set()

        # Phase 1: Discovery (Synergy Search)
        await self.log_callback("System", "Phase 1: Discovery - Searching for synergies...")

        # Ask LLM for search terms based on commander text
        synergy_prompt = (
            f"Analyze the commander '{commander}'. Extract 3-5 distinct Scryfall search queries to find synergistic cards. "
            f"Example: 'o:+1/+1 counters', 't:elf', 'o:proliferate'. "
            f"Return ONLY the queries separated by commas."
        )
        search_terms_text = await client.generate(synergy_prompt)
        search_terms = [t.strip() for t in search_terms_text.split(',')]

        candidate_pool: List[Dict] = []
        seen_candidates = set()

        # Execute searches
        for term in search_terms:
            # Construct strict query: term + commander colors + strict exclusion of illegal colors
            # Scryfall 'id' (color identity) syntax: id:g (mono green), id:gw (selesnya)
            # If commander colors is empty, id:c
            color_str = "".join(self.commander_colors).lower()
            if not color_str: color_str = "c"

            query = f"({term}) id:<={color_str} (game:paper) -t:basic"
            await self.log_callback("System", f"Searching Scryfall: {query}")

            results = await asyncio.to_thread(search_scryfall, query, limit=15)
            for card in results:
                if card['name'] not in seen_candidates and card['name'] not in self.commander_names:
                    # Double check color identity locally just in case
                    if self.is_color_compatible(card.get('color_identity', [])):
                         candidate_pool.append(card)
                         seen_candidates.add(card['name'])

        await self.log_callback("System", f"Found {len(candidate_pool)} candidates for analysis.")

        # Inventory Check (Optional Injection)
        if self.settings.use_owned_cards:
             # Basic implementation: Fetch owned cards that match identity and add to pool
             inventory = get_inventory()
             for item in inventory:
                  # Need to check color identity. Inventory items might not have it stored,
                  # but we can fetch or assume user knows what they are doing.
                  # For safety, let's just re-fetch data or skip if unknown.
                  # Ideally inventory should have strict color check too.
                  if item.name not in seen_candidates and item.name not in self.commander_names:
                       # This is a bit expensive if inventory is huge.
                       # Let's just add top 20 owned cards to the front of the pool
                       candidate_pool.insert(0, item.model_dump())
                       seen_candidates.add(item.name)

        # Phase 2: Analysis & Voting
        await self.log_callback("System", "Phase 2: Analysis & Voting...")

        target_non_land = 63 # Aiming for ~36-37 lands
        batch_size = 5

        # Shuffle pool to vary results
        random.shuffle(candidate_pool)

        for i in range(0, len(candidate_pool), batch_size):
            if len(verified_cards) >= target_non_land:
                break

            batch = candidate_pool[i : i+batch_size]

            # Simple voting: If at least one agent likes it, we add it.
            # (Strict majority can be too slow for small agent counts, but let's try strict > 0)

            # We can ask one agent to pick from the batch to save tokens, or all.
            # Let's have agents rotate.
            agent = self.agents[i % len(self.agents)]

            approved_names = await agent.analyze_candidates(batch, f"Build for {commander}", self.log_callback)

            for card in batch:
                # Fuzzy matching approved name
                if any(approved in card['name'] for approved in approved_names):
                    if card['name'] not in verified_card_names:
                        verified_cards.append(Card(**card))
                        verified_card_names.add(card['name'])
                        await self.log_callback("System", f"Added {card['name']} to deck.")

        # Phase 3: Land Base
        needed = 100 - len(verified_cards) - len(self.commander_names)
        if needed > 0:
            await self.log_callback("System", f"Phase 3: Adding {needed} lands...")
            colors = list(self.commander_colors)
            if not colors: colors = ['C']

            basics_map = {'W': "Plains", 'U': "Island", 'B': "Swamp", 'R': "Mountain", 'G': "Forest", 'C': "Wastes"}

            for i in range(needed):
                c = colors[i % len(colors)]
                land_name = basics_map.get(c, "Wastes")
                verified_cards.append(Card(name=land_name, type_line="Basic Land", quantity=1))

        # Phase 4: Final Validation
        # Check for commander in deck list (should be handled by exclusion logic, but sanity check)
        final_cards = [c for c in verified_cards if c.name not in self.commander_names]

        # Fill if pruned
        if len(final_cards) + len(self.commander_names) < 100:
             # Just add more basic lands
             diff = 100 - (len(final_cards) + len(self.commander_names))
             land_name = basics_map.get(list(self.commander_colors)[0] if self.commander_colors else 'C', "Wastes")
             for _ in range(diff):
                 final_cards.append(Card(name=land_name, type_line="Basic Land", quantity=1))

        deck = Deck(
            commander=commander,
            cards=final_cards,
            combos=[], # Combos could be re-added if needed
            status="completed"
        )

        await self.log_callback("System", "Deck generation complete.")
        return deck
