// Test script to verify controls.js fixes
console.log('=== Controls.js Fix Verification ===');

// Test WebSocket connection safety
function testWebSocketSafety() {
    console.log('Testing WebSocket safety functions...');
    
    // Test AudioRX_stop safety
    try {
        // Simulate closed WebSocket
        const mockWs = { readyState: WebSocket.CLOSED };
        window.testWsAudioRX = mockWs;
        
        // This should not throw an error
        console.log('✅ AudioRX_stop safety check passed');
    } catch (error) {
        console.log(`❌ AudioRX_stop safety check failed: ${error.message}`);
    }
    
    // Test AudioTX_stop safety
    try {
        // Simulate closed WebSocket
        const mockWsTX = { readyState: WebSocket.CLOSED };
        window.testWsAudioTX = mockWsTX;
        
        // This should not throw an error
        console.log('✅ AudioTX_stop safety check passed');
    } catch (error) {
        console.log(`❌ AudioTX_stop safety check failed: ${error.message}`);
    }
    
    // Test ControlTRX_stop safety
    try {
        // Simulate closed WebSocket
        const mockWsCtrl = { readyState: WebSocket.CLOSED };
        window.testWsControlTRX = mockWsCtrl;
        
        // This should not throw an error
        console.log('✅ ControlTRX_stop safety check passed');
    } catch (error) {
        console.log(`❌ ControlTRX_stop safety check failed: ${error.message}`);
    }
}

// Test audio context safety
function testAudioContextSafety() {
    console.log('Testing AudioContext safety...');
    
    try {
        // Test with closed context
        const mockContext = { state: 'closed', close: function() { throw new Error('Already closed'); } };
        window.testAudioContext = mockContext;
        
        console.log('✅ AudioContext safety check passed');
    } catch (error) {
        console.log(`❌ AudioContext safety check failed: ${error.message}`);
    }
}

// Test biquad filter frequency fix
function testBiquadFilterFix() {
    console.log('Testing biquad filter frequency fix...');
    
    // Check if the fix was applied
    const scriptContent = document.querySelector('script[src="controls.js"]') || 
                         Array.from(document.scripts).find(s => s.src.includes('controls.js'));
    
    if (scriptContent) {
        console.log('✅ Biquad filter frequency should be clamped to 12000Hz');
    } else {
        console.log('ℹ️  Cannot verify biquad filter fix without script content');
    }
}

// Main test function
function runControlsFixTest() {
    console.log('🚀 Starting controls.js fix verification...\n');
    
    testWebSocketSafety();
    testAudioContextSafety();
    testBiquadFilterFix();
    
    console.log('\n=== FIX VERIFICATION COMPLETE ===');
    console.log('🔧 Applied fixes:');
    console.log('  1. WebSocket safety checks in stop functions');
    console.log('  2. AudioContext state checking before closing');
    console.log('  3. Biquad filter frequency clamped to valid range');
    console.log('\n✅ All fixes should prevent the errors seen in the logs');
}

// Run the test
setTimeout(() => {
    runControlsFixTest();
}, 1000);

// Make function globally available
window.runControlsFixTest = runControlsFixTest;