// Test script to verify mobile interface WebSocket connection fix
console.log('=== Mobile Interface WebSocket Fix Test ===');

// Test function to check if status indicators are properly updated
function testStatusIndicators() {
    console.log('Testing status indicators...');
    
    // Check if all status indicators exist
    const indicators = ['status-ctrl', 'status-rx', 'status-tx'];
    let allFound = true;
    
    indicators.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            console.log(`✅ ${id}: Found`);
        } else {
            console.log(`❌ ${id}: Missing`);
            allFound = false;
        }
    });
    
    if (allFound) {
        console.log('✅ All status indicators found');
    } else {
        console.log('❌ Some status indicators missing');
    }
    
    return allFound;
}

// Test function to verify WebSocket connection status
function testWebSocketConnections() {
    console.log('Testing WebSocket connections...');
    
    // Check if WebSocket objects exist
    const websockets = {
        'wsControlTRX': window.wsControlTRX,
        'wsAudioRX': window.wsAudioRX,
        'wsAudioTX': window.wsAudioTX
    };
    
    let allExist = true;
    
    Object.entries(websockets).forEach(([name, ws]) => {
        if (ws) {
            console.log(`✅ ${name}: Exists (state: ${ws.readyState})`);
        } else {
            console.log(`❌ ${name}: Not found`);
            allExist = false;
        }
    });
    
    if (allExist) {
        console.log('✅ All WebSocket objects exist');
    } else {
        console.log('❌ Some WebSocket objects missing');
    }
    
    return allExist;
}

// Test function to verify updateConnectionStatus function
function testUpdateConnectionStatus() {
    console.log('Testing updateConnectionStatus function...');
    
    if (typeof window.updateConnectionStatus === 'function') {
        console.log('✅ updateConnectionStatus function exists');
        
        // Test the function with sample data
        try {
            // Test setting status to connected
            window.updateConnectionStatus('ctrl', true);
            console.log('✅ updateConnectionStatus("ctrl", true) executed');
            
            // Test setting status to disconnected
            window.updateConnectionStatus('ctrl', false);
            console.log('✅ updateConnectionStatus("ctrl", false) executed');
            
            return true;
        } catch (error) {
            console.log(`❌ Error testing updateConnectionStatus: ${error.message}`);
            return false;
        }
    } else {
        console.log('❌ updateConnectionStatus function not found');
        return false;
    }
}

// Main test function
function runWebSocketFixTest() {
    console.log('🚀 Starting WebSocket connection fix test...\n');
    
    const results = {
        indicators: testStatusIndicators(),
        websockets: testWebSocketConnections(),
        updateFunction: testUpdateConnectionStatus()
    };
    
    console.log('\n=== TEST RESULTS ===');
    console.log('Status Indicators:', results.indicators ? '✅ PASS' : '❌ FAIL');
    console.log('WebSocket Objects:', results.websockets ? '✅ PASS' : '❌ FAIL');
    console.log('Update Function:', results.updateFunction ? '✅ PASS' : '❌ FAIL');
    
    const passed = Object.values(results).filter(result => result).length;
    const total = Object.values(results).length;
    
    console.log(`\n📊 Summary: ${passed}/${total} tests passed`);
    
    if (passed === total) {
        console.log('🎉 All tests passed! WebSocket connection fix is working.');
    } else {
        console.log('⚠️ Some tests failed. Please check the details above.');
    }
    
    return results;
}

// Run the test
setTimeout(() => {
    runWebSocketFixTest();
}, 1000);

// Make the test function globally available
window.runWebSocketFixTest = runWebSocketFixTest;