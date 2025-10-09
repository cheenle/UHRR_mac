// Test script to verify audio sample rate settings
console.log("Testing audio sample rate settings...");

// Check mobile.js settings
console.log("mobile.js audioRXSampleRate:", 
  typeof audioRXSampleRate !== 'undefined' ? audioRXSampleRate : 'Not found');

// Check mobile_audio_direct_copy.js settings
console.log("mobile_audio_direct_copy.js AudioRX_sampleRate:", 
  typeof AudioRX_sampleRate !== 'undefined' ? AudioRX_sampleRate : 'Not found');

console.log("All sample rates should be 8000 for old browser compatibility");