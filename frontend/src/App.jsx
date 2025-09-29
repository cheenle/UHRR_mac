import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import RadioControl from './components/RadioControl';
import SpectrumDisplay from './components/SpectrumDisplay';
import AudioControl from './components/AudioControl';
import RadioService from './services/radioService';
import AudioService from './services/audioService';
import WebSocketService from './services/websocketService';
import './App.css';

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [services, setServices] = useState(null);

  useEffect(() => {
    initializeServices();
  }, []);

  const initializeServices = async () => {
    try {
      // Initialize WebSocket connection
      const socket = io(process.env.REACT_APP_BACKEND_URL || 'http://localhost:3000');

      const websocketService = new WebSocketService(socket);
      const radioService = new RadioService(socket);
      const audioService = new AudioService(socket);

      // Initialize services
      await websocketService.initialize();
      radioService.initialize();
      await audioService.initialize();

      setServices({
        websocket: websocketService,
        radio: radioService,
        audio: audioService
      });

      // Setup event listeners
      websocketService.on('connected', () => {
        setIsConnected(true);
        console.log('✅ Connected to server');
      });

      websocketService.on('disconnected', () => {
        setIsConnected(false);
        console.log('❌ Disconnected from server');
      });

      websocketService.on('radioStatusUpdate', (status) => {
        radioService.handleStatusUpdate(status);
      });

      websocketService.on('audioReceived', (data) => {
        audioService.handleIncomingAudio(data);
      });

    } catch (error) {
      console.error('❌ Failed to initialize services:', error);
    }
  };

  const handleConnect = () => {
    if (services?.websocket) {
      services.websocket.initialize();
    }
  };

  if (!services) {
    return (
      <div className="app loading">
        <div className="loading-spinner">Loading...</div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Universal HamRadio Remote</h1>
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
          {!isConnected && (
            <button onClick={handleConnect} className="connect-button">
              Connect
            </button>
          )}
        </div>
      </header>

      <main className="app-main">
        <div className="controls-section">
          <RadioControl
            radioService={services.radio}
            websocketService={services.websocket}
          />
          <AudioControl
            audioService={services.audio}
            websocketService={services.websocket}
          />
        </div>

        <div className="display-section">
          <SpectrumDisplay
            websocketService={services.websocket}
          />
        </div>
      </main>

      <footer className="app-footer">
        <p>Universal HamRadio Remote v2.0.0 - Modern Node.js Frontend</p>
        <p>Built with React, Socket.io, and Web Audio API</p>
      </footer>
    </div>
  );
}

export default App;
