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

    async def analyze_candidates(self, candidates: List[Dict], strategy: str, log_callback: Callable, previous_feedback: str = "") -> Dict[str, str]:
        """
        Analyze a batch of cards and vote on them.
        Returns a dict: {"reasoning": str, "approved": List[str]}
        """
        # Simplify candidate data for the LLM to save context
        simplified_candidates = []
        for c in candidates:
            simplified_candidates.append(f"{c['name']} ({c['type_line']}): {c['oracle_text'][:150]}")

        context_msg = ""
        if previous_feedback:
            context_msg = f"\nA previous agent said this about these cards: '{previous_feedback}'. Do you agree or disagree? Explain why, and make your own selections."

        prompt = (
            f"You are a Magic: The Gathering deck builder with a {self.personality} personality.\n"
            f"Strategy: {strategy}\n"
            f"Analyze these cards and pick the ones that fit the deck:\n"
            f"{' | '.join(simplified_candidates)}\n"
            f"{context_msg}\n"
            f"Return your response in JSON format: {{ \"reasoning\": \"...\", \"approved\": [\"Card Name 1\", \"Card Name 2\"] }}."
        )

        response = await client.generate(prompt)

        # Parse JSON from response
        import json
        import re
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                reasoning = data.get("reasoning", "No reasoning provided.")
                approved = data.get("approved", [])
            else:
                # Fallback
                reasoning = response
                approved = []
        except:
            reasoning = response
            approved = []

        await log_callback(self.name, f"{reasoning} (Approved: {len(approved)})")

        return {"reasoning": reasoning, "approved": approved}

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
            f"Analyze the commander '{commander}'. Extract 5-8 distinct Scryfall search queries to find synergistic cards. "
            f"Include a mix of specific mechanics (e.g. 'o:proliferate'), tribal tags (e.g. 't:elf'), and generic staples for these colors. "
            f"Return ONLY the queries separated by commas."
        )
        search_terms_text = await client.generate(synergy_prompt)
        search_terms = [t.strip() for t in search_terms_text.split(',')]

        candidate_pool: List[Dict] = []
        seen_candidates = set()

        # Color Identity String
        color_str = "".join(self.commander_colors).lower()
        if not color_str: color_str = "c"

        # Execute searches
        for term in search_terms:
            # Construct strict query: term + commander colors + strict exclusion of illegal colors
            # Scryfall 'id' (color identity) syntax: id:g (mono green), id:gw (selesnya)
            query = f"({term}) id:<={color_str} (game:paper) -t:basic"
            await self.log_callback("System", f"Searching Scryfall: {query}")

            results = await asyncio.to_thread(search_scryfall, query, limit=50)
            for card in results:
                if card['name'] not in seen_candidates and card['name'] not in self.commander_names:
                    # Double check color identity locally just in case
                    if self.is_color_compatible(card.get('color_identity', [])):
                         candidate_pool.append(card)
                         seen_candidates.add(card['name'])

        # Fallback: Broad Search if pool is too small
        if len(candidate_pool) < 100:
            await self.log_callback("System", "Candidate pool low, performing broad search...")
            broad_query = f"id:<={color_str} (game:paper) -t:basic"
            # Maybe add "cheapest" or "edhrec rank" implicitly by Scryfall default sort or explicitly
            broad_results = await asyncio.to_thread(search_scryfall, broad_query, limit=100)
            for card in broad_results:
                 if card['name'] not in seen_candidates and card['name'] not in self.commander_names:
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
        batch_size = 6 # Increase batch size slightly

        # Shuffle pool to vary results
        random.shuffle(candidate_pool)

        # Collaborative Loop
        for i in range(0, len(candidate_pool), batch_size):
            if len(verified_cards) >= target_non_land:
                break

            batch = candidate_pool[i : i+batch_size]

            # Select Primary Agent and Reviewer Agent
            primary_idx = i % len(self.agents)
            reviewer_idx = (i + 1) % len(self.agents)

            agent_primary = self.agents[primary_idx]
            agent_reviewer = self.agents[reviewer_idx]

            # Step 1: Primary Agent Proposes
            result_primary = await agent_primary.analyze_candidates(
                batch,
                f"Build for {commander}",
                self.log_callback
            )

            # Step 2: Reviewer Agent Critiques/Finalizes
            # We pass the primary agent's reasoning as context
            prev_feedback = f"{agent_primary.name} ({agent_primary.personality}): {result_primary['reasoning']} (Approved: {', '.join(result_primary['approved'])})"

            result_final = await agent_reviewer.analyze_candidates(
                batch,
                f"Build for {commander}",
                self.log_callback,
                previous_feedback=prev_feedback
            )

            approved_names = result_final['approved']

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
