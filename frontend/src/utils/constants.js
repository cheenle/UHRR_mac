/**
 * Application constants
 */

export const AUDIO_CONFIG = {
  SAMPLE_RATE: 24000,
  CHANNELS: 1,
  CHUNK_SIZE: 1024,
  FORMAT: 'int16'
};

export const WEBSOCKET_EVENTS = {
  // Client to Server
  JOIN_RADIO: 'join-radio',
  AUDIO_DATA: 'audio-data',
  RADIO_COMMAND: 'radio-command',
  HEARTBEAT: 'heartbeat',

  // Server to Client
  RADIO_STATUS: 'radio-status',
  AUDIO_RECEIVED: 'audio-received',
  SPECTRUM_DATA: 'spectrum-data',
  HEARTBEAT_RESPONSE: 'heartbeat-response'
};

export const RADIO_MODES = [
  'USB', 'LSB', 'CW', 'AM', 'FM'
];

export const FREQUENCY_RANGES = {
  HF: { min: 3000000, max: 30000000, name: 'HF' },
  VHF: { min: 30000000, max: 300000000, name: 'VHF' },
  UHF: { min: 300000000, max: 3000000000, name: 'UHF' }
};

export const SIGNAL_STRENGTH_LEVELS = [
  'S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S9+10', 'S9+20', 'S9+30', 'S9+40'
];
