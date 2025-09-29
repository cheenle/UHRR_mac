/**
 * Radio Service - Handles radio control commands and status
 */

const EventEmitter = require('events');

class RadioService extends EventEmitter {
  constructor(io) {
    super();
    this.io = io;
    this.radioState = {
      frequency: 7050000,
      mode: 'USB',
      power: 100,
      ptt: false,
      signalStrength: 0,
      connected: false
    };
    this.commandQueue = [];
    this.isProcessing = false;
  }

  /**
   * Initialize radio service
   */
  initialize() {
    console.log('📡 RadioService initialized');

    // Setup periodic status updates
    this.setupStatusPolling();
  }

  /**
   * Setup periodic status polling
   */
  setupStatusPolling() {
    setInterval(() => {
      if (this.radioState.connected) {
        this.requestStatus();
      }
    }, 1000); // Poll every second
  }

  /**
   * Handle radio command from client
   */
  handleRadioCommand(socket, data) {
    const { command, value } = data;

    switch (command) {
      case 'setFrequency':
        this.setFrequency(value);
        break;
      case 'setMode':
        this.setMode(value);
        break;
      case 'setPower':
        this.setPower(value);
        break;
      case 'setPTT':
        this.setPTT(value);
        break;
      case 'getStatus':
        this.sendStatus(socket);
        break;
      default:
        console.warn('⚠️ Unknown radio command:', command);
    }
  }

  /**
   * Set radio frequency
   */
  setFrequency(frequency) {
    console.log('📡 Setting frequency to:', frequency);
    this.radioState.frequency = frequency;

    // Send to server
    this.io.emit('radio-command', {
      type: 'setFreq',
      frequency: frequency
    });

    this.emit('frequencyChanged', frequency);
  }

  /**
   * Set radio mode
   */
  setMode(mode) {
    console.log('📡 Setting mode to:', mode);
    this.radioState.mode = mode;

    this.io.emit('radio-command', {
      type: 'setMode',
      mode: mode
    });

    this.emit('modeChanged', mode);
  }

  /**
   * Set transmitter power
   */
  setPower(power) {
    console.log('📡 Setting power to:', power);
    this.radioState.power = power;

    this.io.emit('radio-command', {
      type: 'setPower',
      power: power
    });

    this.emit('powerChanged', power);
  }

  /**
   * Set PTT state
   */
  setPTT(state) {
    console.log('📡 Setting PTT to:', state);
    this.radioState.ptt = state;

    this.io.emit('radio-command', {
      type: 'setPTT',
      state: state
    });

    this.emit('pttChanged', state);
  }

  /**
   * Request current status from server
   */
  requestStatus() {
    this.io.emit('radio-command', {
      type: 'getStatus'
    });
  }

  /**
   * Send current status to specific socket
   */
  sendStatus(socket) {
    socket.emit('radio-status', this.radioState);
  }

  /**
   * Handle status update from server
   */
  handleStatusUpdate(status) {
    const oldState = { ...this.radioState };

    // Update local state
    if (status.frequency !== undefined) {
      this.radioState.frequency = status.frequency;
    }
    if (status.mode !== undefined) {
      this.radioState.mode = status.mode;
    }
    if (status.power !== undefined) {
      this.radioState.power = status.power;
    }
    if (status.ptt !== undefined) {
      this.radioState.ptt = status.ptt;
    }
    if (status.signalStrength !== undefined) {
      this.radioState.signalStrength = status.signalStrength;
    }
    if (status.connected !== undefined) {
      this.radioState.connected = status.connected;
    }

    // Emit events for state changes
    if (oldState.frequency !== this.radioState.frequency) {
      this.emit('frequencyChanged', this.radioState.frequency);
    }
    if (oldState.mode !== this.radioState.mode) {
      this.emit('modeChanged', this.radioState.mode);
    }
    if (oldState.ptt !== this.radioState.ptt) {
      this.emit('pttChanged', this.radioState.ptt);
    }
  }

  /**
   * Handle radio connection
   */
  handleRadioConnect() {
    this.radioState.connected = true;
    this.emit('radioConnected');
    console.log('📡 Radio connected');
  }

  /**
   * Handle radio disconnection
   */
  handleRadioDisconnect() {
    this.radioState.connected = false;
    this.emit('radioDisconnected');
    console.log('📡 Radio disconnected');
  }

  /**
   * Get current radio state
   */
  getState() {
    return { ...this.radioState };
  }

  /**
   * Reset radio state
   */
  resetState() {
    this.radioState = {
      frequency: 7050000,
      mode: 'USB',
      power: 100,
      ptt: false,
      signalStrength: 0,
      connected: false
    };
    console.log('📡 Radio state reset');
  }

  /**
   * Validate frequency
   */
  validateFrequency(frequency) {
    const freq = parseInt(frequency);
    return freq >= 100000 && freq <= 30000000000; // 100kHz to 30GHz
  }

  /**
   * Validate mode
   */
  validateMode(mode) {
    const validModes = ['USB', 'LSB', 'CW', 'AM', 'FM', 'DIGI'];
    return validModes.includes(mode.toUpperCase());
  }

  /**
   * Validate power
   */
  validatePower(power) {
    const pwr = parseInt(power);
    return pwr >= 0 && pwr <= 100;
  }
}

module.exports = RadioService;
