/**
 * Type definitions for Universal HamRadio Remote
 */

/**
 * @typedef {Object} RadioState
 * @property {number} frequency - Current frequency in Hz
 * @property {string} mode - Current mode (USB/LSB/CW/AM/FM)
 * @property {number} power - Transmitter power (0-100)
 * @property {boolean} ptt - PTT state
 * @property {number} signalStrength - Signal strength (0-9)
 * @property {boolean} connected - Connection status
 * @property {string} lastUpdate - Last update timestamp
 */

/**
 * @typedef {Object} AudioStats
 * @property {boolean} isRecording - Recording state
 * @property {number} bufferLength - Buffer length
 * @property {number} sampleRate - Sample rate
 * @property {number} sequenceNumber - Sequence number
 */

/**
 * @typedef {Object} WebSocketStatus
 * @property {boolean} isConnected - Connection status
 * @property {string} socketId - Socket ID
 * @property {number} reconnectAttempts - Reconnect attempts
 * @property {string} lastHeartbeat - Last heartbeat timestamp
 */

/**
 * @typedef {Object} SpectrumData
 * @property {Float32Array} fftData - FFT data
 * @property {number} sampleRate - Sample rate
 * @property {number} centerFreq - Center frequency
 * @property {number} fftSize - FFT size
 */

/**
 * @typedef {Object} AudioData
 * @property {ArrayBuffer} data - Audio data buffer
 * @property {string} timestamp - Timestamp
 * @property {number} sequence - Sequence number
 * @property {number} sampleRate - Sample rate
 * @property {number} channels - Number of channels
 */

/**
 * @typedef {Object} RadioCommand
 * @property {string} command - Command type
 * @property {*} value - Command value
 * @property {string} timestamp - Timestamp
 */

/**
 * @typedef {Object} ConnectionConfig
 * @property {string} host - Server host
 * @property {number} port - Server port
 * @property {boolean} secure - Use HTTPS/WSS
 * @property {string} radioId - Radio session ID
 */

/**
 * @typedef {Object} AudioConfig
 * @property {number} sampleRate - Sample rate
 * @property {number} channels - Number of channels
 * @property {number} chunkSize - Chunk size
 * @property {string} format - Audio format
 */

/**
 * @typedef {Object} ServerHealth
 * @property {string} status - Health status
 * @property {string} timestamp - Timestamp
 * @property {string} version - Server version
 * @property {Object} services - Service status
 */
