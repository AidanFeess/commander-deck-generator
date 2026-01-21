import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/ws/process';

export default function Process() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState("pending");
  const logsEndRef = useRef(null);

  useEffect(() => {
    // Initial fetch to check status
    const checkStatus = async () => {
      try {
        const res = await axios.get(`${API_URL}/deck/${id}`);
        setStatus(res.data.status);
        if (res.data.status === "completed") {
          navigate(`/results/${id}`);
        }
      } catch (err) {
        console.error(err);
      }
    };
    checkStatus();

    // WebSocket connection
    const ws = new WebSocket(`${WS_URL}/${id}`);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      setLogs(prev => [...prev, msg]);

      if (msg.message === "Deck generation complete.") {
        setStatus("completed");
        setTimeout(() => navigate(`/results/${id}`), 2000);
      }
    };

    return () => ws.close();
  }, [id, navigate]);

  // Auto-scroll removed as per user request
  // useEffect(() => {
  //   logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  // }, [logs]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold text-center">Deck Generation in Progress</h1>
      <div className="bg-black p-4 rounded-lg font-mono h-96 overflow-y-auto border border-gray-700 shadow-inner">
        {logs.map((log, i) => (
          <div key={i} className="mb-2">
            <span className="text-gray-500">[{new Date(log.timestamp * 1000).toLocaleTimeString()}]</span>
            <span className={`font-bold ml-2 ${log.agent_name === "System" ? "text-yellow-400" : "text-blue-400"}`}>
              {log.agent_name}:
            </span>
            <span className="ml-2 text-gray-300">{log.message}</span>
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>
      <div className="text-center">
        {status === "completed" ? (
          <button
            onClick={() => navigate(`/results/${id}`)}
            className="bg-green-600 px-6 py-2 rounded text-white font-bold"
          >
            View Results
          </button>
        ) : (
          <p className="text-purple-400 animate-pulse">AI Agents are collaborating...</p>
        )}
      </div>
    </div>
  );
}
