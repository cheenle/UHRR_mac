// Comprehensive debug script for mobile interface audio issues
console.log('=== Mobile Audio Debug Started ===');

// Debug function to check all audio-related variables and states
function debugAudioStatus() {
    console.log('\n=== Audio Debug Information ===');
    
    // Check WebSocket connections
    console.log('WebSocket Status:');
    console.log('- wsControlTRX:', window.wsControlTRX ? `ReadyState: ${window.wsControlTRX.readyState}` : 'Not initialized');
    console.log('- wsAudioRX:', window.wsAudioRX ? `ReadyState: ${window.wsAudioRX.readyState}` : 'Not initialized');
    console.log('- wsAudioTX:', window.wsAudioTX ? `ReadyState: ${window.wsAudioTX.readyState}` : 'Not initialized');
    
    // Check Audio Context
    console.log('\nAudio Context Status:');
    console.log('- audioContext:', window.audioContext ? `State: ${window.audioContext.state}, SampleRate: ${window.audioContext.sampleRate}` : 'Not initialized');
    console.log('- audioRXGainNode:', window.audioRXGainNode ? 'Initialized' : 'Not initialized');
    
    // Check connection status
    console.log('\nConnection Status:');
    console.log('- isConnected:', window.isConnected);
    console.log('- poweron:', window.poweron);
    
    // Check if we're actually receiving audio data
    console.log('\nAudio Data Monitoring:');
    if (window.wsAudioRX) {
        const originalOnMessage = window.wsAudioRX.onmessage;
        window.wsAudioRX.onmessage = function(event) {
            console.log('📥 Audio data received:', {
                dataType: event.data.constructor.name,
                dataSize: event.data.byteLength || event.data.length,
                timestamp: new Date().toISOString()
            });
            
            // Call original handler
            if (originalOnMessage) {
                originalOnMessage.call(this, event);
            }
        };
    }
    
    return {
        websockets: {
            control: window.wsControlTRX ? window.wsControlTRX.readyState : null,
            audioRX: window.wsAudioRX ? window.wsAudioRX.readyState : null,
            audioTX: window.wsAudioTX ? window.wsAudioTX.readyState : null
        },
        audioContext: window.audioContext ? {
            state: window.audioContext.state,
            sampleRate: window.audioContext.sampleRate
        } : null,
        isConnected: window.isConnected
    };
}

// Enhanced audio test with more detailed logging
function enhancedAudioTest() {
    console.log('\n=== Enhanced Audio Test ===');
    
    // Test 1: Audio Context State
    if (!window.audioContext) {
        console.log('❌ No audio context found');
        return;
    }
    
    console.log('Audio Context State:', window.audioContext.state);
    
    // Test 2: Resume if suspended
    if (window.audioContext.state === 'suspended') {
        console.log('Resuming audio context...');
        window.audioContext.resume().then(() => {
            console.log('✅ Audio context resumed');
        }).catch(err => {
            console.error('❌ Failed to resume audio context:', err);
        });
    }
    
    // Test 3: Create test tone
    try {
        console.log('Creating test tone...');
        const oscillator = window.audioContext.createOscillator();
        const gainNode = window.audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(window.audioContext.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.value = 880; // A5 note
        gainNode.gain.value = 0.1;
        
        oscillator.start();
        setTimeout(() => {
            oscillator.stop();
            console.log('✅ Test tone completed');
        }, 1000);
        
    } catch (error) {
        console.error('❌ Test tone failed:', error);
    }
}

// Check if mobile interface is properly initialized
function checkMobileInterface() {
    console.log('\n=== Mobile Interface Check ===');
    
    // Check for mobile-specific elements
    const elements = {
        powerButton: document.getElementById('power-btn'),
        pttButton: document.getElementById('ptt-btn'),
        statusCtrl: document.getElementById('status-ctrl'),
        statusRX: document.getElementById('status-rx'),
        statusTX: document.getElementById('status-tx')
    };
    
    Object.keys(elements).forEach(key => {
        console.log(`${key}:`, elements[key] ? 'Found' : 'Missing');
    });
    
    // Check event listeners
    if (elements.powerButton) {
        console.log('Power button event listeners:', elements.powerButton.listeners ? 'Yes' : 'Unknown');
    }
}

// Run all debug functions
setTimeout(() => {
    const debugInfo = debugAudioStatus();
    checkMobileInterface();
    
    console.log('\n=== Debug Summary ===');
    console.log('If you see this message, the debug script is working.');
    console.log('Check the console for detailed information about the audio status.');
    
    // Auto-run enhanced test if connected
    if (window.isConnected && window.audioContext) {
        setTimeout(enhancedAudioTest, 2000);
    }
    
}, 1000);

// Export for manual calling
window.debugAudioStatus = debugAudioStatus;
window.enhancedAudioTest = enhancedAudioTest;

console.log('🔧 Debug functions available:');
console.log('- debugAudioStatus()  // Check current audio status');
console.log('- enhancedAudioTest() // Run enhanced audio test');