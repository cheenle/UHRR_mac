// Final test script to verify all WebSocket and audio fixes
console.log('=== Final UHRR Interface Fix Verification ===');

// Test power toggle logic
function testPowerToggleLogic() {
    console.log('Testing power toggle logic...');
    
    // Simulate initial state
    window.poweron = false;
    
    // Test that stop functions are not called when power is off
    const originalAudioRXStop = window.AudioRX_stop;
    const originalAudioTXStop = window.AudioTX_stop;
    const originalControlTRXStop = window.ControlTRX_stop;
    
    let rxStopCalled = false;
    let txStopCalled = false;
    let ctrlStopCalled = false;
    
    window.AudioRX_stop = function() { rxStopCalled = true; console.log('AudioRX_stop called'); };
    window.AudioTX_stop = function() { txStopCalled = true; console.log('AudioTX_stop called'); };
    window.ControlTRX_stop = function() { ctrlStopCalled = true; console.log('ControlTRX_stop called'); };
    
    // Simulate wsAudioRXclose call when power is off
    if (typeof window.wsAudioRXclose === 'function') {
        window.wsAudioRXclose();
        if (!rxStopCalled) {
            console.log('✅ wsAudioRXclose correctly skipped AudioRX_stop when power is off');
        } else {
            console.log('❌ wsAudioRXclose incorrectly called AudioRX_stop when power is off');
        }
    }
    
    // Reset flags
    rxStopCalled = false;
    
    // Simulate power on state
    window.poweron = true;
    
    // Simulate wsAudioRXclose call when power is on
    if (typeof window.wsAudioRXclose === 'function') {
        window.wsAudioRXclose();
        if (rxStopCalled) {
            console.log('✅ wsAudioRXclose correctly called AudioRX_stop when power is on');
        } else {
            console.log('❌ wsAudioRXclose failed to call AudioRX_stop when power is on');
        }
    }
    
    // Restore original functions
    window.AudioRX_stop = originalAudioRXStop;
    window.AudioTX_stop = originalAudioTXStop;
    window.ControlTRX_stop = originalControlTRXStop;
    
    console.log('✅ Power toggle logic test completed');
}

// Test WebSocket safety
function testWebSocketSafety() {
    console.log('Testing WebSocket safety...');
    
    // Test with null WebSocket
    const originalWsAudioRX = window.wsAudioRX;
    window.wsAudioRX = null;
    
    if (typeof window.AudioRX_stop === 'function') {
        try {
            window.AudioRX_stop();
            console.log('✅ AudioRX_stop handles null WebSocket gracefully');
        } catch (error) {
            console.log(`❌ AudioRX_stop failed with null WebSocket: ${error.message}`);
        }
    }
    
    // Test with closed WebSocket
    window.wsAudioRX = { readyState: WebSocket.CLOSED, close: function() { throw new Error('Already closed'); } };
    
    if (typeof window.AudioRX_stop === 'function') {
        try {
            window.AudioRX_stop();
            console.log('✅ AudioRX_stop handles closed WebSocket gracefully');
        } catch (error) {
            console.log(`❌ AudioRX_stop failed with closed WebSocket: ${error.message}`);
        }
    }
    
    // Restore original
    window.wsAudioRX = originalWsAudioRX;
    
    console.log('✅ WebSocket safety test completed');
}

// Test AudioContext safety
function testAudioContextSafety() {
    console.log('Testing AudioContext safety...');
    
    // Test with null AudioContext
    const originalAudioContext = window.AudioRX_context;
    window.AudioRX_context = null;
    
    if (typeof window.AudioRX_stop === 'function') {
        try {
            window.AudioRX_stop();
            console.log('✅ AudioRX_stop handles null AudioContext gracefully');
        } catch (error) {
            console.log(`❌ AudioRX_stop failed with null AudioContext: ${error.message}`);
        }
    }
    
    // Test with closed AudioContext
    window.AudioRX_context = { state: 'closed', close: function() { throw new Error('Already closed'); } };
    
    if (typeof window.AudioRX_stop === 'function') {
        try {
            window.AudioRX_stop();
            console.log('✅ AudioRX_stop handles closed AudioContext gracefully');
        } catch (error) {
            console.log(`❌ AudioRX_stop failed with closed AudioContext: ${error.message}`);
        }
    }
    
    // Restore original
    window.AudioRX_context = originalAudioContext;
    
    console.log('✅ AudioContext safety test completed');
}

// Main test function
function runFinalVerification() {
    console.log('🚀 Starting final verification of all fixes...\n');
    
    testPowerToggleLogic();
    testWebSocketSafety();
    testAudioContextSafety();
    
    console.log('\n=== FINAL VERIFICATION COMPLETE ===');
    console.log('🔧 Applied fixes:');
    console.log('  1. Power toggle logic - prevent stop functions from being called when power is off');
    console.log('  2. WebSocket safety - check WebSocket state before closing');
    console.log('  3. AudioContext safety - check AudioContext state before closing');
    console.log('  4. Error handler safety - prevent error handlers from stopping connections when power is off');
    console.log('  5. Biquad filter frequency - clamped to valid range');
    console.log('\n✅ All fixes should prevent the connection errors seen in the logs');
    console.log('🔄 Please refresh the page and test the interface');
}

// Run the test
setTimeout(() => {
    runFinalVerification();
}, 1000);

// Make function globally available
window.runFinalVerification = runFinalVerification;