import ollama
import asyncio
import random
import time
import os

class OllamaClient:
    def __init__(self, model="llama3"):
        self.model = model
        self.mock_mode = False
        self.async_client = None

        # Check for OLLAMA_HOST env var
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        try:
            # Check connection (sync check on init is fine)
            # Create a client with the specific host if needed
            self.client = ollama.Client(host=host)
            self.client.list()
            self.async_client = ollama.AsyncClient(host=host)
        except Exception as e:
            print(f"Ollama not reachable at {host}: {e}, switching to MOCK mode.")
            self.mock_mode = True

    async def generate(self, prompt: str, system: str = "") -> str:
        if self.mock_mode:
            return await self._mock_response(prompt)

        try:
            response = await self.async_client.generate(model=self.model, prompt=prompt, system=system)
            return response['response']
        except Exception as e:
            print(f"Ollama error: {e}")
            return await self._mock_response(prompt)

    async def chat(self, messages: list) -> str:
        if self.mock_mode:
            return await self._mock_response(messages[-1]['content'])

        try:
            response = await self.async_client.chat(model=self.model, messages=messages)
            return response['message']['content']
        except Exception as e:
            print(f"Ollama error: {e}")
            return await self._mock_response(messages[-1]['content'])

    async def _mock_response(self, input_text: str) -> str:
        await asyncio.sleep(0.5) # Simulate delay

        # Mock Scryfall Query generation
        if "Scryfall search query" in input_text:
             if "Green" in input_text:
                 # Simulate the bad query the user is complaining about or a mock one
                 return "Query: t:legendary (t:creature or o:\"can be your commander\") id:g"
             return "Query: t:legendary (t:creature or o:\"can be your commander\")"

        # Mock Selection
        if "Select the single best fit" in input_text:
             return "Commander: Omnath, Locus of Mana\nReasoning: Classic Mono-Green big mana commander."

        if "combo" in input_text.lower():
             return "Combo: Basalt Monolith + Rings of Brighthearth | Result: Infinite colorless mana. | Instructions: Tap Basalt Monolith for 3 mana. Pay 3 to untap using Monolith's ability. Copy the untap ability with Rings of Brighthearth (pay 2). Let copy resolve, untap Monolith. Tap for 3 mana. Let original untap resolve. Repeat."

        if "list" in input_text.lower() or "extract" in input_text.lower():
            return "Sol Ring, Arcane Signet, Command Tower, Cultivate, Kodama's Reach, Swords to Plowshares, Path to Exile, Beast Within, Generous Gift, Cyclonic Rift, Rhystic Study, Smothering Tithe, Teferi's Protection, Heroic Intervention, Counterspell, Negate, Fierce Guardianship, Mana Drain, Lightning Greaves, Swiftfoot Boots"

        return f"This is a mock response from the AI for input: {input_text[:50]}..."

client = OllamaClient()
