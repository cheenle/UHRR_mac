/**
 * Audio Service - Handles audio streaming, encoding, and WebRTC
 */

const Peer = require('simple-peer');

class AudioService {
  constructor(io) {
    this.io = io;
    this.audioContext = null;
    this.microphoneStream = null;
    this.audioProcessor = null;
    this.peerConnections = new Map(); // Store WebRTC peer connections
    this.isRecording = false;
    this.audioBuffer = [];
    this.bufferSize = 4096;
    this.sampleRate = 24000;

    // Audio quality settings
    this.audioConfig = {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: true,
      sampleRate: this.sampleRate,
      channelCount: 1
    };
  }

  /**
   * Initialize audio service
   */
  async initialize() {
    try {
      // Initialize Web Audio API
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        latencyHint: 'interactive',
        sampleRate: this.sampleRate
      });

      console.log('🎵 AudioService initialized with sample rate:', this.audioContext.sampleRate);

      // Setup audio processing
      await this.setupAudioProcessing();

    } catch (error) {
      console.error('❌ AudioService initialization failed:', error);
      throw error;
    }
  }

  /**
   * Setup audio processing pipeline
   */
  async setupAudioProcessing() {
    try {
      // Get microphone access
      this.microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: this.audioConfig
      });

      // Create audio processing nodes
      const source = this.audioContext.createMediaStreamSource(this.microphoneStream);
      this.audioProcessor = this.audioContext.createScriptProcessor(this.bufferSize, 1, 1);

      // Audio processing callback
      this.audioProcessor.onaudioprocess = (event) => {
        if (this.isRecording) {
          const inputData = event.inputBuffer.getChannelData(0);
          this.processAudioData(inputData);
        }
      };

      // Connect nodes
      source.connect(this.audioProcessor);
      this.audioProcessor.connect(this.audioContext.destination);

      console.log('🎤 Audio processing pipeline setup complete');

    } catch (error) {
      console.error('❌ Audio processing setup failed:', error);
      throw error;
    }
  }

  /**
   * Process audio data for transmission
   */
  processAudioData(inputData) {
    // Convert Float32 to Int16 for transmission
    const int16Data = new Int16Array(inputData.length);
    for (let i = 0; i < inputData.length; i++) {
      int16Data[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
    }

    // Emit audio data via WebSocket
    this.io.emit('audio-data', {
      type: 'tx',
      data: int16Data.buffer,
      timestamp: Date.now(),
      sequence: this.getSequenceNumber()
    });
  }

  /**
   * Start audio transmission
   */
  startTransmission() {
    if (!this.microphoneStream || !this.audioContext) {
      throw new Error('Audio system not initialized');
    }

    this.isRecording = true;
    console.log('🎙️ Started audio transmission');

    // Send TX initialization
    this.io.emit('audio-command', {
      type: 'tx-init',
      config: {
        sampleRate: this.sampleRate,
        channels: 1,
        format: 'int16'
      }
    });
  }

  /**
   * Stop audio transmission
   */
  stopTransmission() {
    this.isRecording = false;
    console.log('⏹️ Stopped audio transmission');

    // Send TX stop command
    this.io.emit('audio-command', {
      type: 'tx-stop'
    });
  }

  /**
   * Handle incoming audio data for playback
   */
  handleIncomingAudio(audioData) {
    try {
      // Convert Int16 back to Float32 for playback
      const int16Array = new Int16Array(audioData);
      const float32Array = new Float32Array(int16Array.length);

      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }

      // Queue for playback
      this.audioBuffer.push(float32Array);

      // Limit buffer size to prevent memory issues
      if (this.audioBuffer.length > 50) {
        this.audioBuffer.shift();
      }

    } catch (error) {
      console.error('❌ Error handling incoming audio:', error);
    }
  }

  /**
   * Play received audio data
   */
  playAudio() {
    if (this.audioBuffer.length === 0 || !this.audioContext) {
      return;
    }

    try {
      const audioData = this.audioBuffer.shift();

      // Create audio buffer for playback
      const buffer = this.audioContext.createBuffer(1, audioData.length, this.sampleRate);
      buffer.getChannelData(0).set(audioData);

      // Create and start source
      const source = this.audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(this.audioContext.destination);
      source.start();

    } catch (error) {
      console.error('❌ Error playing audio:', error);
    }
  }

  /**
   * Get sequence number for audio packets
   */
  getSequenceNumber() {
    if (!this.sequenceNumber) {
      this.sequenceNumber = 0;
    }
    return this.sequenceNumber++;
  }

  /**
   * Setup WebRTC peer connection for audio
   */
  async setupWebRTCAudio() {
    try {
      // This will be implemented for direct audio streaming
      console.log('🔗 WebRTC audio setup initiated');
      return true;
    } catch (error) {
      console.error('❌ WebRTC audio setup failed:', error);
      return false;
    }
  }

  /**
   * Get audio statistics
   */
  getAudioStats() {
    return {
      isRecording: this.isRecording,
      bufferLength: this.audioBuffer.length,
      sampleRate: this.audioContext?.sampleRate || this.sampleRate,
      sequenceNumber: this.sequenceNumber || 0
    };
  }

  /**
   * Cleanup audio resources
   */
  cleanup() {
    try {
      if (this.audioProcessor) {
        this.audioProcessor.disconnect();
        this.audioProcessor = null;
      }

      if (this.microphoneStream) {
        this.microphoneStream.getTracks().forEach(track => track.stop());
        this.microphoneStream = null;
      }

      if (this.audioContext && this.audioContext.state !== 'closed') {
        this.audioContext.close();
        this.audioContext = null;
      }

      this.isRecording = false;
      this.audioBuffer = [];

      console.log('🧹 AudioService cleanup complete');

    } catch (error) {
      console.error('❌ AudioService cleanup error:', error);
    }
  }
}

module.exports = AudioService;
