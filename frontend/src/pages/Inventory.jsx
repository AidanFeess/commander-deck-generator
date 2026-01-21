import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

export default function Inventory() {
  const [cards, setCards] = useState([]);
  const [importText, setImportText] = useState("");
  const [newCardName, setNewCardName] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    try {
      const res = await axios.get(`${API_URL}/inventory`);
      setCards(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const addCard = async () => {
    try {
      await axios.post(`${API_URL}/inventory/add`, null, { params: { card_name: newCardName } });
      setNewCardName("");
      fetchInventory();
    } catch (err) {
      setError(`Failed to add card: ${err.response?.data?.detail || err.message}`);
    }
  };

  const deleteCard = async (id) => {
    try {
      await axios.delete(`${API_URL}/inventory/${id}`);
      fetchInventory();
    } catch (err) {
      console.error(err);
    }
  };

  const importCards = async () => {
    try {
      const res = await axios.post(`${API_URL}/inventory/import`, null, { params: { text: importText } });
      if (res.status === 207) {
        alert(`Imported with failures:\n${res.data.failed.join(', ')}`);
      }
      setImportText("");
      fetchInventory();
    } catch (err) {
      setError("Import failed.");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Card Inventory</h1>

      {error && (
        <div className="bg-red-500 text-white p-3 rounded flex justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}>X</button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Add Card</h2>
          <div className="flex space-x-2">
            <input
              type="text"
              className="flex-1 p-2 bg-gray-700 rounded text-white"
              placeholder="Card Name"
              value={newCardName}
              onChange={(e) => setNewCardName(e.target.value)}
            />
            <button
              onClick={addCard}
              className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded text-white"
            >
              Add
            </button>
          </div>
        </div>

        <div className="bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Import Cards</h2>
          <textarea
            className="w-full p-2 bg-gray-700 rounded text-white h-32"
            placeholder="Paste MTG list here..."
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
          />
          <div className="flex justify-between mt-2">
            <button
              onClick={importCards}
              className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white"
            >
              Import Text
            </button>
            <label className="cursor-pointer bg-green-600 hover:bg-green-700 px-4 py-2 rounded text-white">
               Upload File
               <input type="file" className="hidden" accept=".txt" onChange={(e) => {
                 const file = e.target.files[0];
                 if (file) {
                   const reader = new FileReader();
                   reader.onload = (e) => setImportText(e.target.result);
                   reader.readAsText(file);
                 }
               }} />
            </label>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {cards.map(card => (
          <div key={card.id} className="relative group">
            <img src={card.image_uri} alt={card.name} className="rounded-lg shadow-lg w-full" />
            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex flex-col justify-center items-center transition-opacity rounded-lg">
              <span className="font-bold text-center p-1">{card.name}</span>
              <span className="text-sm">Qty: {card.quantity}</span>
              <button
                onClick={() => deleteCard(card.id)}
                className="mt-2 bg-red-600 px-3 py-1 rounded text-sm hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
