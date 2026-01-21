import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Inventory from './pages/Inventory';
import Generator from './pages/Generator';
import Process from './pages/Process';
import Results from './pages/Results';
import Decks from './pages/Decks';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-900 text-white font-sans">
        <nav className="bg-gray-800 p-4 shadow-lg">
          <div className="container mx-auto flex justify-between items-center">
            <Link to="/" className="text-2xl font-bold text-purple-400">AI Commander</Link>
            <div className="space-x-4">
              <Link to="/" className="hover:text-purple-300">Generator</Link>
              <Link to="/inventory" className="hover:text-purple-300">Inventory</Link>
              <Link to="/decks" className="hover:text-purple-300">My Decks</Link>
            </div>
          </div>
        </nav>
        <div className="container mx-auto p-4">
          <Routes>
            <Route path="/" element={<Generator />} />
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/decks" element={<Decks />} />
            <Route path="/process/:id" element={<Process />} />
            <Route path="/results/:id" element={<Results />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
