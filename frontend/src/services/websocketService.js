/**
 * WebSocket Service - Handles real-time communication with backend
 */

const EventEmitter = require('events');

class WebSocketService extends EventEmitter {
  constructor(io) {
    super();
    this.io = io;
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1 second
    this.heartbeatInterval = null;
    this.lastHeartbeat = null;
  }

  /**
   * Initialize WebSocket connection
   */
  async initialize() {
    try {
      this.socket = this.io();

      this.setupEventHandlers();
      this.startHeartbeat();

      console.log('🔗 WebSocketService initialized');

    } catch (error) {
      console.error('❌ WebSocketService initialization failed:', error);
      throw error;
    }
  }

  /**
   * Setup WebSocket event handlers
   */
  setupEventHandlers() {
    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected:', this.socket.id);
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      this.emit('connected');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('❌ WebSocket disconnected:', reason);
      this.isConnected = false;
      this.emit('disconnected', reason);
      this.handleReconnect();
    });

    this.socket.on('connect_error', (error) => {
      console.error('❌ WebSocket connection error:', error);
      this.emit('connectionError', error);
      this.handleReconnect();
    });

    // Application-specific events
    this.socket.on('radio-status', (data) => {
      this.emit('radioStatusUpdate', data);
    });

    this.socket.on('audio-received', (data) => {
      this.emit('audioReceived', data);
    });

    this.socket.on('spectrum-data', (data) => {
      this.emit('spectrumData', data);
    });

    this.socket.on('error', (error) => {
      console.error('❌ WebSocket error:', error);
      this.emit('error', error);
    });
  }

  /**
   * Start heartbeat mechanism
   */
  startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected) {
        this.socket.emit('heartbeat', { timestamp: Date.now() });
        this.lastHeartbeat = Date.now();
      }
    }, 30000); // 30 seconds
  }

  /**
   * Handle reconnection logic
   */
  handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Max reconnection attempts reached');
      this.emit('maxReconnectAttemptsReached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`🔄 Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      if (!this.isConnected) {
        this.socket.connect();
      }
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
  }

  /**
   * Send message to server
   */
  send(event, data) {
    if (!this.isConnected) {
      console.warn('⚠️ Attempting to send message while disconnected:', event);
      return false;
    }

    try {
      this.socket.emit(event, data);
      return true;
    } catch (error) {
      console.error('❌ Error sending message:', error);
      return false;
    }
  }

  /**
   * Join radio session
   */
  joinRadio(radioId) {
    this.send('join-radio', { radioId });
    console.log('📡 Joined radio session:', radioId);
  }

  /**
   * Send audio data
   */
  sendAudioData(data) {
    this.send('audio-data', data);
  }

  /**
   * Send radio command
   */
  sendRadioCommand(command, value) {
    this.send('radio-command', { command, value });
  }

  /**
   * Get connection status
   */
  getStatus() {
    return {
      isConnected: this.isConnected,
      socketId: this.socket?.id || null,
      reconnectAttempts: this.reconnectAttempts,
      lastHeartbeat: this.lastHeartbeat
    };
  }

  /**
   * Disconnect from server
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }

    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    this.isConnected = false;
    console.log('🔌 WebSocketService disconnected');
  }

  /**
   * Cleanup resources
   */
  cleanup() {
    this.disconnect();
    this.removeAllListeners();
    console.log('🧹 WebSocketService cleanup complete');
  }
}

module.exports = WebSocketService;
