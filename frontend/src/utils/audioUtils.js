/**
 * Audio utility functions
 */

/**
 * Convert frequency to human readable format
 * @param {number} frequency - Frequency in Hz
 * @returns {string} Formatted frequency string
 */
export const formatFrequency = (frequency) => {
  if (frequency >= 1000000) {
    return `${(frequency / 1000000).toFixed(3)} MHz`;
  } else if (frequency >= 1000) {
    return `${(frequency / 1000).toFixed(1)} kHz`;
  }
  return `${frequency} Hz`;
};

/**
 * Convert signal strength to S-meter reading
 * @param {number} strength - Signal strength value (0-9)
 * @returns {string} S-meter reading
 */
export const formatSignalStrength = (strength) => {
  if (strength < 0) return 'S0';
  if (strength <= 9) return `S${strength}`;
  if (strength <= 19) return `S9+${strength - 9}`;
  if (strength <= 29) return `S9+${(strength - 9) * 2}`;
  if (strength <= 39) return `S9+${(strength - 9) * 3}`;
  return 'S9+40';
};

/**
 * Validate frequency value
 * @param {number} frequency - Frequency to validate
 * @returns {boolean} True if valid
 */
export const validateFrequency = (frequency) => {
  const freq = parseInt(frequency);
  return freq >= 100000 && freq <= 30000000000; // 100kHz to 30GHz
};

/**
 * Validate mode value
 * @param {string} mode - Mode to validate
 * @returns {boolean} True if valid
 */
export const validateMode = (mode) => {
  const validModes = ['USB', 'LSB', 'CW', 'AM', 'FM'];
  return validModes.includes(mode?.toUpperCase());
};

/**
 * Validate power value
 * @param {number} power - Power to validate
 * @returns {boolean} True if valid
 */
export const validatePower = (power) => {
  const pwr = parseInt(power);
  return pwr >= 0 && pwr <= 100;
};

/**
 * Convert bytes to human readable format
 * @param {number} bytes - Bytes to convert
 * @returns {string} Formatted size string
 */
export const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

/**
 * Calculate audio bitrate
 * @param {number} sampleRate - Sample rate
 * @param {number} bitDepth - Bit depth
 * @param {number} channels - Number of channels
 * @returns {number} Bitrate in kbps
 */
export const calculateBitrate = (sampleRate, bitDepth = 16, channels = 1) => {
  return (sampleRate * bitDepth * channels) / 1000;
};

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

/**
 * Throttle function
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in ms
 * @returns {Function} Throttled function
 */
export const throttle = (func, limit) => {
  let inThrottle;
  return function() {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  }
};
