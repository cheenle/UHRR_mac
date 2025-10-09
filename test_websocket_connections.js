// Test WebSocket connections for UHRR mobile interface
console.log('=== UHRR WebSocket Connection Test ===');

// Test if we're on mobile interface
if (window.location.pathname.includes('mobile')) {
    console.log('Running on mobile interface');
    
    // Check current WebSocket status
    console.log('Current WebSocket status:');
    console.log('- wsControlTRX:', window.wsControlTRX ? 'Exists' : 'Not found');
    console.log('- wsAudioRX:', window.wsAudioRX ? 'Exists' : 'Not found');
    console.log('- wsAudioTX:', window.wsAudioTX ? 'Exists' : 'Not found');
    
    // Check connection states
    if (window.wsControlTRX) {
        console.log('- wsControlTRX state:', window.wsControlTRX.readyState);
    }
    if (window.wsAudioRX) {
        console.log('- wsAudioRX state:', window.wsAudioRX.readyState);
    }
    if (window.wsAudioTX) {
        console.log('- wsAudioTX state:', window.wsAudioTX.readyState);
    }
    
    // Check status indicators
    const ctrlIndicator = document.getElementById('status-ctrl');
    const rxIndicator = document.getElementById('status-rx');
    const txIndicator = document.getElementById('status-tx');
    
    console.log('Status indicators:');
    console.log('- CTRL:', ctrlIndicator ? (ctrlIndicator.classList.contains('connected') ? 'Connected' : 'Disconnected') : 'Not found');
    console.log('- RX:', rxIndicator ? (rxIndicator.classList.contains('connected') ? 'Connected' : 'Disconnected') : 'Not found');
    console.log('- TX:', txIndicator ? (txIndicator.classList.contains('connected') ? 'Connected' : 'Disconnected') : 'Not found');
    
    // Test connection functions
    console.log('Testing connection functions...');
    
    // Test power toggle
    if (typeof window.powerToggle === 'function') {
        console.log('powerToggle function exists');
    } else {
        console.log('powerToggle function NOT found');
    }
    
    // Test individual connection functions
    if (typeof window.ControlTRX_start === 'function') {
        console.log('ControlTRX_start function exists');
    } else {
        console.log('ControlTRX_start function NOT found');
    }
    
    if (typeof window.AudioRX_start === 'function') {
        console.log('AudioRX_start function exists');
    } else {
        console.log('AudioRX_start function NOT found');
    }
    
    if (typeof window.AudioTX_start === 'function') {
        console.log('AudioTX_start function exists');
    } else {
        console.log('AudioTX_start function NOT found');
    }
} else {
    console.log('Not on mobile interface, skipping mobile-specific tests');
}

console.log('=== Test Complete ===');