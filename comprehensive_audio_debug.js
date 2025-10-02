// Comprehensive Audio Debug Script for Mobile Interface
console.log('=== Comprehensive Mobile Audio Debug ===');

// Detailed audio system status checker
function checkAudioSystem() {
    console.log('\n=== AUDIO SYSTEM STATUS ===');
    
    // Check WebSocket connections
    console.log('🔌 WebSocket Connections:');
    const connections = {
        wsControlTRX: window.wsControlTRX,
        wsAudioRX: window.wsAudioRX,
        wsAudioTX: window.wsAudioTX
    };
    
    Object.keys(connections).forEach(key => {
        const ws = connections[key];
        if (ws) {
            console.log(`  ${key}: ${ws.readyState === WebSocket.OPEN ? '✅ OPEN' : ws.readyState === WebSocket.CONNECTING ? '⏳ CONNECTING' : ws.readyState === WebSocket.CLOSING ? '🟡 CLOSING' : '❌ CLOSED'}`);
        } else {
            console.log(`  ${key}: ❌ NOT INITIALIZED`);
        }
    });
    
    // Check Audio Context
    console.log('\n🎵 Audio Context:');
    if (window.audioContext) {
        console.log(`  State: ${window.audioContext.state}`);
        console.log(`  Sample Rate: ${window.audioContext.sampleRate}Hz`);
        console.log(`  Base Latency: ${window.audioContext.baseLatency || 'N/A'}`);
        console.log(`  Output Latency: ${window.audioContext.outputLatency || 'N/A'}`);
    } else {
        console.log('  ❌ NOT INITIALIZED');
    }
    
    // Check Audio Nodes
    console.log('\n🎚️ Audio Nodes:');
    const nodes = {
        audioRXSourceNode: window.audioRXSourceNode,
        audioRXGainNode: window.audioRXGainNode,
        audioRXBiquadFilterNode: window.audioRXBiquadFilterNode
    };
    
    Object.keys(nodes).forEach(key => {
        console.log(`  ${key}: ${nodes[key] ? '✅ INITIALIZED' : '❌ NOT INITIALIZED'}`);
    });
    
    // Check Audio Buffer
    console.log('\n📦 Audio Buffer:');
    if (window.audioRXAudioBuffer) {
        console.log(`  Buffer Length: ${window.audioRXAudioBuffer.length}`);
        if (window.audioRXAudioBuffer.length > 0) {
            console.log(`  First Buffer Size: ${window.audioRXAudioBuffer[0].length} samples`);
        }
    } else {
        console.log('  ❌ NOT INITIALIZED');
    }
    
    // Check Connection Status
    console.log('\n🔗 Connection Status:');
    console.log(`  isConnected: ${window.isConnected}`);
    console.log(`  poweron: ${window.poweron}`);
    
    return {
        websockets: connections,
        audioContext: window.audioContext,
        audioNodes: nodes,
        audioBuffer: window.audioRXAudioBuffer,
        connectionStatus: {
            isConnected: window.isConnected,
            poweron: window.poweron
        }
    };
}

// Test audio context functionality
function testAudioContext() {
    console.log('\n=== AUDIO CONTEXT TEST ===');
    
    if (!window.audioContext) {
        console.log('❌ No audio context found');
        return false;
    }
    
    console.log(`Audio Context State: ${window.audioContext.state}`);
    
    // Try to resume if suspended
    if (window.audioContext.state === 'suspended') {
        console.log('🔄 Resuming audio context...');
        window.audioContext.resume().then(() => {
            console.log('✅ Audio context resumed');
            playTestTone();
        }).catch(err => {
            console.error('❌ Failed to resume audio context:', err);
            return false;
        });
    } else {
        playTestTone();
    }
    
    return true;
}

// Play a test tone to verify audio output
function playTestTone() {
    console.log('\n=== PLAYING TEST TONE ===');
    
    try {
        if (!window.audioContext) {
            console.log('❌ No audio context available');
            return;
        }
        
        // Create oscillator for test tone
        const oscillator = window.audioContext.createOscillator();
        const gainNode = window.audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(window.audioContext.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.value = 880; // A5 note
        gainNode.gain.value = 0.1; // Low volume
        
        oscillator.start();
        setTimeout(() => {
            oscillator.stop();
            console.log('✅ Test tone played (if you heard it)');
        }, 1000);
        
    } catch (error) {
        console.error('❌ Test tone failed:', error);
    }
}

// Monitor audio data flow
function monitorAudioData() {
    console.log('\n=== MONITORING AUDIO DATA FLOW ===');
    
    if (window.wsAudioRX) {
        const originalOnMessage = window.wsAudioRX.onmessage;
        
        window.wsAudioRX.onmessage = function(event) {
            console.log('📥 Audio Data Received:', {
                timestamp: new Date().toISOString(),
                dataType: event.data.constructor.name,
                dataSize: event.data.byteLength || 'unknown',
                isArrayBuffer: event.data instanceof ArrayBuffer
            });
            
            // Check if we're processing the data
            if (window.audioRXAudioBuffer) {
                console.log(`  Buffer Queue Length: ${window.audioRXAudioBuffer.length}`);
            }
            
            // Call original handler
            if (originalOnMessage) {
                originalOnMessage.call(this, event);
            }
        };
        
        console.log('✅ Audio data monitoring enabled');
    } else {
        console.log('❌ No audio WebSocket connection to monitor');
    }
}

// Simulate audio data processing
function simulateAudioProcessing() {
    console.log('\n=== SIMULATING AUDIO PROCESSING ===');
    
    if (!window.audioContext || !window.audioRXAudioBuffer) {
        console.log('❌ Required components not available');
        return;
    }
    
    // Create simulated audio data
    const simulatedData = new Float32Array(256);
    for (let i = 0; i < simulatedData.length; i++) {
        simulatedData[i] = Math.sin(i * 0.1) * 0.5; // Simple sine wave
    }
    
    // Add to buffer
    window.audioRXAudioBuffer.push(simulatedData);
    console.log(`✅ Simulated audio data added to buffer (length: ${simulatedData.length})`);
    
    // Check if ScriptProcessor is working
    console.log('🔄 ScriptProcessor should be processing this data automatically');
}

// Check for common audio issues
function checkCommonIssues() {
    console.log('\n=== CHECKING COMMON AUDIO ISSUES ===');
    
    const issues = [];
    
    // Check 1: Audio context state
    if (window.audioContext && window.audioContext.state === 'suspended') {
        issues.push('Audio context is suspended - user interaction may be needed');
    }
    
    // Check 2: WebSocket connections
    if (window.wsAudioRX && window.wsAudioRX.readyState !== WebSocket.OPEN) {
        issues.push('Audio RX WebSocket is not open');
    }
    
    // Check 3: Audio buffer
    if (window.audioRXAudioBuffer && window.audioRXAudioBuffer.length > 20) {
        issues.push('Audio buffer is very large - possible processing issue');
    }
    
    // Check 4: Connection status
    if (!window.isConnected) {
        issues.push('Not connected to server');
    }
    
    if (issues.length === 0) {
        console.log('✅ No obvious issues detected');
    } else {
        console.log('⚠️ Potential issues found:');
        issues.forEach(issue => console.log(`  - ${issue}`));
    }
    
    return issues;
}

// Run comprehensive diagnostics
function runDiagnostics() {
    console.log('\n=== RUNNING COMPREHENSIVE DIAGNOSTICS ===');
    
    const status = checkAudioSystem();
    const issues = checkCommonIssues();
    
    console.log('\n=== DIAGNOSTICS SUMMARY ===');
    console.log('🔧 Debug functions available:');
    console.log('   - checkAudioSystem()     // Check all audio components');
    console.log('   - testAudioContext()     // Test audio context functionality');
    console.log('   - monitorAudioData()     // Monitor incoming audio data');
    console.log('   - simulateAudioProcessing() // Simulate audio processing');
    console.log('   - checkCommonIssues()    // Check for common issues');
    
    if (issues.length > 0) {
        console.log('\n🚨 ACTION NEEDED:');
        console.log('Please address the issues above and run diagnostics again.');
    } else {
        console.log('\n✅ System appears to be properly configured.');
        console.log('If you still don\'t hear audio, try clicking the power button to establish connections.');
    }
}

// Auto-run diagnostics after a short delay
setTimeout(() => {
    console.log('=== MOBILE AUDIO DEBUG READY ===');
    console.log('Type "runDiagnostics()" in console to start diagnostics');
}, 2000);

// Export functions for manual use
window.checkAudioSystem = checkAudioSystem;
window.testAudioContext = testAudioContext;
window.monitorAudioData = monitorAudioData;
window.simulateAudioProcessing = simulateAudioProcessing;
window.checkCommonIssues = checkCommonIssues;
window.runDiagnostics = runDiagnostics;

console.log('🔄 Debug script loaded. Functions available in 2 seconds...');