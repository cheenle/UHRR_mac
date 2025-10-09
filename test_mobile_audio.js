// Test script to verify mobile interface audio functionality
console.log('=== Mobile Interface Audio Test ===');

// Test audio context creation with correct sample rate
function testAudioContext() {
    console.log('Testing Web Audio API with 24kHz sample rate...');
    
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: 24000});
        console.log('✅ AudioContext created successfully with 24kHz sample rate');
        console.log('📊 Actual sample rate:', audioContext.sampleRate);
        
        // Test gain node creation
        const gainNode = audioContext.createGain();
        console.log('✅ Gain node created successfully');
        
        // Clean up
        audioContext.close();
        console.log('✅ AudioContext closed successfully');
        
    } catch (error) {
        console.error('❌ Failed to create AudioContext:', error);
    }
}

// Test WebSocket connection
function testWebSocketConnection() {
    console.log('Testing WebSocket connection to audio endpoint...');
    
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const baseUrl = `${protocol}//${window.location.host}`;
        const wsAudioRX = new WebSocket(`${baseUrl}/WSaudioRX`);
        
        wsAudioRX.onopen = function() {
            console.log('✅ Audio RX WebSocket connected successfully');
            wsAudioRX.close();
        };
        
        wsAudioRX.onerror = function(error) {
            console.error('❌ Audio RX WebSocket error:', error);
        };
        
        wsAudioRX.onclose = function() {
            console.log('✅ Audio RX WebSocket closed');
        };
        
    } catch (error) {
        console.error('❌ Failed to create WebSocket connection:', error);
    }
}

// Run tests
setTimeout(() => {
    testAudioContext();
    testWebSocketConnection();
}, 1000);

console.log('🔄 Tests started. Check console for results...');