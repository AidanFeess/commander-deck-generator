import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

const API_URL = 'http://localhost:8000/api';

export default function Decks() {
  const [decks, setDecks] = useState([]);

  useEffect(() => {
    // Simplified fetch - in real app, need an endpoint to list decks.
    // Assuming /api/decks endpoint exists.
    fetchDecks();
  }, []);

  const fetchDecks = async () => {
    try {
      const res = await axios.get(`${API_URL}/decks`);
      setDecks(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Your Decks</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {decks.map(deck => (
          <Link key={deck.id} to={`/results/${deck.id}`} className="block">
            <div className="bg-gray-800 p-6 rounded-lg shadow hover:bg-gray-700 transition">
              <h2 className="text-xl font-bold text-purple-400">{deck.commander}</h2>
              <p className="text-gray-400">Status: {deck.status}</p>
              <p className="text-sm text-gray-500">{new Date(deck.created_at).toLocaleString()}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
