import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

const CardSection = ({ title, cards }) => {
  if (!cards || cards.length === 0) return null;
  return (
    <div className="mb-8">
      <h3 className="text-xl font-bold mb-4 border-b border-gray-700 pb-2">{title} ({cards.length})</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {cards.map((card, i) => (
          <div key={i} className="relative group">
            <img
              src={card.image_uri || 'https://via.placeholder.com/250x350?text=No+Image'}
              alt={card.name}
              className="rounded-lg shadow-lg w-full transition transform group-hover:scale-105"
            />
            <div className="mt-2 text-center text-sm font-semibold truncate">{card.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default function Results() {
  const { id } = useParams();
  const [deck, setDeck] = useState(null);
  const [showCombos, setShowCombos] = useState(false);

  useEffect(() => {
    const fetchDeck = async () => {
      try {
        const res = await axios.get(`${API_URL}/deck/${id}`);
        setDeck(res.data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchDeck();
  }, [id]);

  if (!deck) return <div>Loading...</div>;

  // Categorize cards
  const categories = {
    "Creature": [], "Planeswalker": [], "Instant": [], "Sorcery": [],
    "Artifact": [], "Enchantment": [], "Land": []
  };

  deck.cards.forEach(card => {
    const type = card.type_line;
    let added = false;
    for (const key of Object.keys(categories)) {
      if (type.includes(key)) {
        categories[key].push(card);
        added = true;
        break;
      }
    }
    if (!added) {
       if (!categories["Other"]) categories["Other"] = [];
       categories["Other"].push(card);
    }
  });

  const downloadDeck = () => {
    const content = deck.cards.map(c => `1 ${c.name}`).join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${deck.commander.replace(/\s+/g, '_')}_Deck.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const copyDeck = () => {
    const content = deck.cards.map(c => `1 ${c.name}`).join('\n');
    navigator.clipboard.writeText(content);
    alert("Deck list copied to clipboard!");
  };

  return (
    <div className="space-y-8 relative">
      <div className="flex justify-between items-center bg-gray-800 p-6 rounded-lg shadow-lg">
        <div>
          <h1 className="text-3xl font-bold">{deck.commander}</h1>
          <p className="text-gray-400">Generated on {new Date(deck.created_at).toLocaleDateString()}</p>
        </div>
        <div className="space-x-4">
          <button onClick={() => setShowCombos(true)} className="bg-yellow-600 hover:bg-yellow-700 px-4 py-2 rounded font-bold shadow">
            Combo List ({deck.combos.length})
          </button>
          <button onClick={copyDeck} className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded font-bold shadow">
            Copy Deck
          </button>
          <button onClick={downloadDeck} className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded font-bold shadow">
            Download Deck
          </button>
        </div>
      </div>

      <div className="space-y-8">
        {Object.entries(categories).map(([key, cards]) => (
          <CardSection key={key} title={key + (key === "Creature" ? "s" : "s")} cards={cards} />
        ))}
      </div>

      {showCombos && (
        <div className="fixed inset-0 bg-black/80 flex justify-center items-center z-50 p-4">
          <div className="bg-gray-800 p-8 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Combos</h2>
              <button onClick={() => setShowCombos(false)} className="text-gray-400 hover:text-white text-2xl">&times;</button>
            </div>
            <div className="space-y-8">
              {deck.combos.map((combo, i) => (
                <div key={i} className="bg-gray-700 p-6 rounded-lg">
                  <div className="flex gap-4 overflow-x-auto pb-4 mb-4">
                    {combo.cards.map((card, j) => (
                      <img key={j} src={card.image_uri} alt={card.name} className="w-32 rounded shadow" />
                    ))}
                  </div>
                  <div className="space-y-2">
                    <p><span className="font-bold text-yellow-400">Result:</span> {combo.result}</p>
                    <p><span className="font-bold text-blue-400">Instructions:</span> {combo.instructions}</p>
                  </div>
                </div>
              ))}
              {deck.combos.length === 0 && <p>No specific combos identified.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
