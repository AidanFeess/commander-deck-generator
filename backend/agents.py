import asyncio
import random
from typing import List, Callable, Dict, Set
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
        await log_callback(self.name, f"Thinking...")
        prompt = (
            f"You are a Magic: The Gathering deck builder with a {self.personality} personality.\n"
            f"Context: {context}\n"
            f"Based on your personality and the current state of the deck, propose 3-5 specific cards to add. "
            f"Also, suggest a combo if you know one. "
            f"Format your response as a list of card names, followed by a brief reasoning."
        )
        response = await client.generate(prompt)
        await log_callback(self.name, f"Suggestions: {response}")
        return response

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
        # Fetch commander data to determine color identity
        names = [n.strip() for n in self.settings.commander_name.split('+')]
        self.commander_names = names

        for name in names:
            data = await asyncio.to_thread(get_card_data, name)
            if data:
                # Scryfall returns color_identity as list of chars ['W', 'U', 'B', 'R', 'G']
                self.commander_colors.update(data.get('color_identity', []))

        await self.log_callback("System", f"Commander Identity established: {', '.join(self.commander_colors) if self.commander_colors else 'Colorless'}")

    def is_color_compatible(self, card_identity: List[str]) -> bool:
        # Card identity must be a subset of commander identity
        return set(card_identity).issubset(self.commander_colors)

    async def generate_deck(self) -> Deck:
        commander = self.settings.commander_name
        mode = self.settings.mode

        await self.log_callback("System", f"Starting iterative deck generation for {commander}...")

        # Step 0: Commander Identity
        await self.get_commander_identity()

        verified_cards: List[Card] = []
        verified_card_names: Set[str] = set()

        # Step 1: Strategy Formulation
        strategy_context = f"We are building a Commander deck for {commander}. The color identity is {list(self.commander_colors)}."

        # Inventory Integration
        owned_cards_context = ""
        if self.settings.use_owned_cards:
            await self.log_callback("System", "Checking inventory for owned cards...")
            inventory = get_inventory()
            owned_card_names = [item.name for item in inventory]
            if owned_card_names:
                # Provide a sample of owned cards to guide the LLM
                # We can't dump everything, but we can give a substantial list or ask it to query us (too complex for now)
                # We'll provide a random sample or top 50 to influence direction.
                sample_owned = ', '.join(owned_card_names[:100])
                owned_cards_context = f" PREFER cards from this list if they fit the strategy: {sample_owned}..."
                strategy_context += f" {owned_cards_context}"
            else:
                await self.log_callback("System", "Inventory is empty. Ignoring 'Use Owned Cards'.")

        await self.log_callback("System", "Formulating strategy...")
        strategy_prompt = f"What is the best strategy for a commander deck built around {commander}? Summarize it in one sentence."
        strategy_response = await client.generate(strategy_prompt)
        strategy_context += f" Strategy: {strategy_response}"
        await self.log_callback("System", f"Strategy: {strategy_response}")

        # Step 2: Iterative Card Selection (Loop until ~65 non-lands)
        target_non_land = 65

        # Initial context
        discussion_history = ""

        loops = 0
        max_loops = 5 # Safety break

        while len(verified_cards) < target_non_land and loops < max_loops:
            loops += 1
            await self.log_callback("System", f"Round {loops}: Researching cards (Current count: {len(verified_cards)})...")

            for agent in self.agents:
                if len(verified_cards) >= target_non_land:
                    break

                # Update context with current deck state summary
                current_state = f"We have {len(verified_cards)} cards so far. We need more."

                response = await agent.think(f"{strategy_context}\n{discussion_history}\n{current_state}", self.log_callback)
                discussion_history += f"\n{agent.name} suggested: {response}"

                # Parse suggested cards from response (Naively extract capitalized words or look for CSV)
                # Better approach: Ask LLM to extract the cards from the agent's response.

                extraction_prompt = (
                    f"Extract the specific Magic: The Gathering card names from this text: '{response}'. "
                    f"Return ONLY a comma-separated list of card names. "
                    f"Do not include explanation."
                )
                card_names_text = await client.generate(extraction_prompt)
                suggested_names = [n.strip() for n in card_names_text.split(',') if n.strip()]

                for name in suggested_names:
                    if len(verified_cards) >= target_non_land:
                        break

                    # Basic cleanup
                    clean_name = name.replace("Card Name:", "").strip()
                    if not clean_name: continue

                    # Skip if already in deck (Singleton Rule)
                    # Note: We need to allow duplicates for basic lands or specific cards like Shadowborn Apostle,
                    # but for this phase we are focusing on non-lands.
                    if clean_name in verified_card_names:
                        continue

                    data = await asyncio.to_thread(get_card_data, clean_name)
                    if data:
                        # Color Identity Check
                        card_id = data.get('color_identity', [])
                        if not self.is_color_compatible(card_id):
                            await self.log_callback("System", f"Rejected {clean_name} (Color mismatch: {card_id})")
                            continue

                        # Add to deck
                        card = Card(**data)
                        verified_cards.append(card)
                        verified_card_names.add(clean_name)
                        await self.log_callback("System", f"Added {clean_name}")
                    else:
                        # Silent fail or log
                        pass

            # Brief pause
            await asyncio.sleep(0.5)

        # Step 3: Fill with Lands
        # Determine how many lands needed
        current_count = len(verified_cards) + len(self.commander_names) # Commanders count towards 100
        needed = 100 - current_count

        if needed > 0:
            await self.log_callback("System", f"Adding {needed} lands to reach 100 cards...")
            # Simple land base generation
            basics = {
                'W': "Plains",
                'U': "Island",
                'B': "Swamp",
                'R': "Mountain",
                'G': "Forest"
            }

            colors = list(self.commander_colors)
            if not colors:
                # Colorless commander -> Wastes? or just generic
                colors = ['C']

            # Distribute evenly
            for i in range(needed):
                # Pick a color (round robin)
                c = colors[i % len(colors)]
                land_name = basics.get(c, "Wastes") # Default to Wastes if colorless or unknown

                # Fetch data for land (so we have image)
                land_data = await asyncio.to_thread(get_card_data, land_name)
                if land_data:
                    # Allow duplicates for basic lands
                    verified_cards.append(Card(**land_data))
                else:
                    # Fallback
                    verified_cards.append(Card(name=land_name, type_line="Basic Land", quantity=1))

        # Step 4: Final Validation (Pruning if over 100)
        total_cards = len(verified_cards) + len(self.commander_names)
        if total_cards > 100:
            await self.log_callback("System", f"Deck has {total_cards} cards. Pruning to 100...")
            to_remove = total_cards - 100
            # Remove from end (likely basic lands we just added, or last added cards)
            verified_cards = verified_cards[:-to_remove]

        # Step 5: Combo Identification
        await self.log_callback("System", "Identifying combos in final list...")
        # Ask LLM if any combos exist in the generated list
        deck_list_str = ", ".join([c.name for c in verified_cards])
        combo_prompt = (
            f"Analyze this deck list for {commander}: {deck_list_str}. "
            f"Identify 1-2 combos present in this list. "
            f"Output in format: Card A + Card B | Result | Instructions"
        )
        combo_text = await client.generate(combo_prompt)
        combos = []
        try:
             lines = combo_text.strip().split('\n')
             for line in lines:
                if "|" in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        card_names_str = parts[0].strip()
                        result = parts[1].strip()
                        instructions = parts[2].strip()

                        # Find these cards in our list
                        combo_card_names = [n.strip() for n in card_names_str.split('+')]
                        found_combo_cards = []
                        for c_name in combo_card_names:
                             # Fuzzy match in verified_cards
                             match = next((c for c in verified_cards if c.name == c_name), None)
                             if match:
                                 found_combo_cards.append(match)

                        # If we found at least 2 parts of the combo
                        if len(found_combo_cards) >= 2:
                             combos.append(Combo(cards=found_combo_cards, result=result, instructions=instructions))
                             await self.log_callback("System", f"Identified combo: {card_names_str}")
        except Exception as e:
            pass

        deck = Deck(
            commander=commander,
            cards=verified_cards,
            combos=combos,
            status="completed"
        )

        await self.log_callback("System", "Deck generation complete.")
        return deck
