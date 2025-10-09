// Comprehensive Audio Diagnostic Script
console.log('=== UHRR Audio Diagnostic Tool ===');

function checkAudioConfiguration() {
    console.log('\n1. Audio Sample Rate Configuration:');
    
    // Check sample rates
    const sampleRates = {
        'Server-side (PyAudio)': 24000,
        'Desktop interface': window.AudioRX_sampleRate || 'Not initialized',
        'Mobile interface': window.audioRXSampleRate || 'Not initialized',
        'Modern mobile interface': window.audioRXSampleRate || 'Not initialized'
    };
    
    Object.entries(sampleRates).forEach(([name, rate]) => {
        const status = rate === 24000 ? '✅' : '❌';
        console.log(`  ${status} ${name}: ${rate}Hz`);
    });
    
    // Check AudioContext availability
    console.log('\n2. AudioContext Support:');
    const audioContextSupported = !!(window.AudioContext || window.webkitAudioContext);
    console.log(`  ${audioContextSupported ? '✅' : '❌'} AudioContext API available`);
    
    if (audioContextSupported) {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            console.log(`  ✅ AudioContext created successfully`);
            console.log(`  📊 Default sample rate: ${ctx.sampleRate}Hz`);
            ctx.close();
        } catch (e) {
            console.log(`  ❌ Failed to create AudioContext: ${e.message}`);
        }
    }
    
    // Check WebSocket connections
    console.log('\n3. WebSocket Connections:');
    const websockets = {
        'Control (wsControlTRX)': window.wsControlTRX,
        'Audio RX (wsAudioRX)': window.wsAudioRX,
        'Audio TX (wsAudioTX)': window.wsAudioTX
    };
    
    Object.entries(websockets).forEach(([name, ws]) => {
        if (ws) {
            const status = ws.readyState === WebSocket.OPEN ? '✅' : '⚠️';
            const state = ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'][ws.readyState];
            console.log(`  ${status} ${name}: ${state}`);
        } else {
            console.log(`  ❌ ${name}: Not initialized`);
        }
    });
    
    // Check audio buffer status
    console.log('\n4. Audio Buffer Status:');
    const audioBuffers = {
        'Desktop (AudioRX_audiobuffer)': window.AudioRX_audiobuffer,
        'Mobile (audioRXAudioBuffer)': window.audioRXAudioBuffer,
        'Modern mobile (audioRXAudioBuffer)': window.audioRXAudioBuffer
    };
    
    Object.entries(audioBuffers).forEach(([name, buffer]) => {
        if (buffer) {
            console.log(`  📦 ${name}: ${buffer.length} chunks`);
        } else {
            console.log(`  📦 ${name}: Not initialized`);
        }
    });
    
    // Check audio nodes
    console.log('\n5. Audio Processing Nodes:');
    const audioNodes = {
        'Desktop gain node': window.AudioRX_gain_node,
        'Desktop filter node': window.AudioRX_biquadFilter_node,
        'Mobile gain node': window.audioRXGainNode,
        'Mobile filter node': window.audioRXBiquadFilterNode,
        'Modern mobile gain node': window.audioRXGainNode,
        'Modern mobile filter node': window.audioRXBiquadFilterNode
    };
    
    Object.entries(audioNodes).forEach(([name, node]) => {
        const status = node ? '✅' : '❌';
        console.log(`  ${status} ${name}: ${node ? 'Available' : 'Not initialized'}`);
    });
    
    // Check browser compatibility
    console.log('\n6. Browser Compatibility:');
    const features = {
        'Web Audio API': !!(window.AudioContext || window.webkitAudioContext),
        'WebSocket API': !!window.WebSocket,
        'MediaDevices API': !!navigator.mediaDevices,
        'getUserMedia': !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
        'AudioWorklet': !!window.AudioWorklet
    };
    
    Object.entries(features).forEach(([feature, supported]) => {
        console.log(`  ${supported ? '✅' : '❌'} ${feature}`);
    });
    
    // Summary
    console.log('\n=== DIAGNOSTIC SUMMARY ===');
    const issues = [];
    
    // Check sample rate consistency
    const desktopRate = window.AudioRX_sampleRate;
    const mobileRate = window.audioRXSampleRate;
    if (desktopRate !== 24000 || mobileRate !== 24000) {
        issues.push('Sample rate mismatch - should be 24000Hz');
    }
    
    // Check WebSocket connections
    if (!window.wsAudioRX || window.wsAudioRX.readyState !== WebSocket.OPEN) {
        issues.push('Audio RX WebSocket not connected');
    }
    
    if (!window.wsControlTRX || window.wsControlTRX.readyState !== WebSocket.OPEN) {
        issues.push('Control WebSocket not connected');
    }
    
    if (issues.length === 0) {
        console.log('🎉 All audio systems are properly configured!');
        console.log('🔊 Audio should be working correctly.');
    } else {
        console.log('⚠️ Issues detected:');
        issues.forEach(issue => console.log(`  - ${issue}`));
    }
    
    return {
        sampleRates,
        websockets,
        issues
    };
}

// Run diagnostic
setTimeout(() => {
    const results = checkAudioConfiguration();
}, 1000);

// Make function globally available
window.runAudioDiagnostic = checkAudioConfiguration;