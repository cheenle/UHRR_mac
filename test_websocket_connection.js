// Test WebSocket connections to UHRR server
console.log('Testing UHRR WebSocket connections...');

// Use the same protocol as the current page
const protocol = 'wss:';
const baseUrl = `${protocol}//localhost:8443`;

console.log('Base URL:', baseUrl);

// Test Control WebSocket
console.log('Testing Control WebSocket connection...');
const wsControlTRX = new WebSocket(`${baseUrl}/WSCTRX`);

wsControlTRX.onopen = function() {
    console.log('Control WebSocket connected successfully');
    
    // Request initial status from radio
    console.log('Requesting initial frequency and mode...');
    wsControlTRX.send('getFreq:');
    wsControlTRX.send('getMode:');
};

wsControlTRX.onmessage = function(msg) {
    console.log('Control WebSocket message received:', msg.data);
};

wsControlTRX.onclose = function() {
    console.log('Control WebSocket disconnected');
};

wsControlTRX.onerror = function(error) {
    console.error('Control WebSocket error:', error);
};

// Test Audio RX WebSocket
console.log('Testing Audio RX WebSocket connection...');
const wsAudioRX = new WebSocket(`${baseUrl}/WSaudioRX`);

wsAudioRX.onopen = function() {
    console.log('Audio RX WebSocket connected');
};

wsAudioRX.onclose = function() {
    console.log('Audio RX WebSocket disconnected');
};

wsAudioRX.onerror = function(error) {
    console.error('Audio RX WebSocket error:', error);
};

// Test Audio TX WebSocket
console.log('Testing Audio TX WebSocket connection...');
const wsAudioTX = new WebSocket(`${baseUrl}/WSaudioTX`);

wsAudioTX.onopen = function() {
    console.log('Audio TX WebSocket connected');
};

wsAudioTX.onclose = function() {
    console.log('Audio TX WebSocket disconnected');
};

wsAudioTX.onerror = function(error) {
    console.error('Audio TX WebSocket error:', error);
};