import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const API_URL = 'http://localhost:8000/api';

export default function Generator() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [commander, setCommander] = useState(null);
  const [loadingCmd, setLoadingCmd] = useState(false);

  // Settings
  const [mode, setMode] = useState("Thinking");
  const [numAgents, setNumAgents] = useState(1);
  const [numDecks, setNumDecks] = useState(1);
  const [useOwned, setUseOwned] = useState(false);

  const generateCommander = async () => {
    setLoadingCmd(true);
    try {
      const res = await axios.post(`${API_URL}/generate/commander`, { prompt });
      setCommander(res.data);
    } catch (err) {
      alert("Failed to generate commander");
    }
    setLoadingCmd(false);
  };

  const generateDeck = async () => {
    if (!commander) return;
    try {
      const res = await axios.post(`${API_URL}/generate/deck`, {
        commander_name: commander.name,
        mode,
        num_agents: numAgents,
        num_decks: numDecks,
        use_owned_cards: useOwned
      });
      // If multiple decks, redirect to the first one but show message
      if (numDecks > 1) {
          alert(`Started generating ${numDecks} decks. Redirecting to the first one.`);
      }
      navigate(`/process/${res.data.deck_id}`);
    } catch (err) {
      alert("Failed to start generation");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
          AI Deck Architect
        </h1>
        <p className="text-gray-400">Craft your next Commander masterpiece using local LLMs.</p>
      </div>

      <div className="bg-gray-800 p-8 rounded-xl shadow-2xl border border-gray-700">
        <div className="space-y-4">
          <label className="block text-lg font-medium">Describe your desired commander</label>
          <div className="flex gap-4">
            <input
              type="text"
              className="flex-1 p-4 bg-gray-900 rounded-lg border border-gray-700 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none transition"
              placeholder="e.g. A dragon that cares about treasure..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button
              onClick={generateCommander}
              disabled={loadingCmd || !prompt}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 px-8 py-4 rounded-lg font-bold transition shadow-lg"
            >
              {loadingCmd ? "Scrying..." : "Generate Commander"}
            </button>
          </div>
        </div>

        {commander && (
          <div className="mt-8 animate-fade-in flex flex-col md:flex-row gap-8 items-center bg-gray-750 p-6 rounded-lg border border-gray-700">
            <img src={commander.image_uri} alt={commander.name} className="w-64 rounded-lg shadow-2xl" />
            <div className="flex-1 space-y-4">
              <h2 className="text-2xl font-bold text-white">{commander.name}</h2>
              <p className="text-gray-300 italic">"{commander.reasoning}"</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 pt-6 border-t border-gray-700">
                <div>
                  <label className="block text-sm font-medium mb-2">Thinking Mode</label>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                    className="w-full bg-gray-900 p-2 rounded border border-gray-700"
                  >
                    <option value="Thinking">Thinking (Deep Analysis)</option>
                    <option value="Fast">Fast (Impulsive)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Agents (1-3)</label>
                  <input
                    type="number"
                    min="1"
                    max="3"
                    value={numAgents}
                    onChange={(e) => setNumAgents(parseInt(e.target.value))}
                    className="w-full bg-gray-900 p-2 rounded border border-gray-700"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Deck Count (1-4)</label>
                  <input
                    type="number"
                    min="1"
                    max="4"
                    value={numDecks}
                    onChange={(e) => setNumDecks(parseInt(e.target.value))}
                    className="w-full bg-gray-900 p-2 rounded border border-gray-700"
                  />
                </div>
                <div className="flex items-center">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={useOwned}
                      onChange={(e) => setUseOwned(e.target.checked)}
                      className="w-5 h-5 rounded border-gray-700 text-purple-600 focus:ring-purple-500"
                    />
                    <span>Use Owned Cards Only</span>
                  </label>
                </div>
              </div>

              <button
                onClick={generateDeck}
                className="w-full mt-4 bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold text-lg shadow-lg transition transform hover:scale-105"
              >
                Generate Deck
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
