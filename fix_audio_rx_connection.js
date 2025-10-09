// Fix for Audio RX WebSocket connection issue in mobile interface
// This script addresses the issue where wsRX doesn't turn green after power button is pressed

console.log('Applying Audio RX connection fix...');

// Check if we're on the mobile interface
if (window.location.pathname.includes('mobile')) {
    console.log('Mobile interface detected, applying fix...');
    
    // Override the wsAudioRXopen function to ensure proper status update
    const originalWsAudioRXopen = window.wsAudioRXopen;
    window.wsAudioRXopen = function() {
        console.log('Fixed: WebSocket audio RX connection opened');
        const statusElement = document.getElementById("indwsAudioRX");
        if (statusElement) {
            statusElement.innerHTML = '<img src="img/critsgreen.png">wsRX';
        }
        // Call original function if it exists
        if (originalWsAudioRXopen) {
            originalWsAudioRXopen();
        }
    };
    
    // Override the wsAudioRXclose function to ensure proper status update
    const originalWsAudioRXclose = window.wsAudioRXclose;
    window.wsAudioRXclose = function() {
        console.log('Fixed: WebSocket audio RX connection closed');
        const statusElement = document.getElementById("indwsAudioRX");
        if (statusElement) {
            statusElement.innerHTML = '<img src="img/critsred.png">wsRX';
        }
        // Call original function if it exists
        if (originalWsAudioRXclose) {
            originalWsAudioRXclose();
        }
        // Call AudioRX_stop if it exists
        if (typeof AudioRX_stop === 'function') {
            AudioRX_stop();
        }
    };
    
    // Override the wsAudioRXerror function to ensure proper status update
    const originalWsAudioRXerror = window.wsAudioRXerror;
    window.wsAudioRXerror = function(err) {
        console.log('Fixed: WebSocket audio RX error', err);
        const statusElement = document.getElementById("indwsAudioRX");
        if (statusElement) {
            statusElement.innerHTML = '<img src="img/critsred.png">wsRX';
        }
        // Call original function if it exists
        if (originalWsAudioRXerror) {
            originalWsAudioRXerror(err);
        }
        // Call AudioRX_stop if it exists
        if (typeof AudioRX_stop === 'function') {
            AudioRX_stop();
        }
    };
    
    // Ensure AudioRX_start function properly initializes the connection
    const originalAudioRX_start = window.AudioRX_start;
    window.AudioRX_start = function() {
        console.log('Fixed: Starting Audio RX connection');
        
        // Update status indicator immediately
        const statusElement = document.getElementById("indwsAudioRX");
        if (statusElement) {
            statusElement.innerHTML = '<img src="img/critsgrey.png">wsRX';
        }
        
        // Initialize audio buffer
        if (typeof AudioRX_audiobuffer === 'undefined') {
            window.AudioRX_audiobuffer = [];
        }
        
        // Create WebSocket connection
        try {
            const wsUrl = 'wss://' + window.location.href.split('/')[2] + '/WSaudioRX';
            console.log('Connecting to Audio RX WebSocket:', wsUrl);
            
            if (window.wsAudioRX) {
                window.wsAudioRX.close();
            }
            
            window.wsAudioRX = new WebSocket(wsUrl);
            window.wsAudioRX.binaryType = 'arraybuffer';
            window.wsAudioRX.onmessage = window.appendwsAudioRX || function(msg) {
                // Fallback message handler
                if (msg && msg.data && msg.data instanceof ArrayBuffer) {
                    if (typeof AudioRX_audiobuffer !== 'undefined') {
                        AudioRX_audiobuffer.push(new Float32Array(msg.data));
                    }
                }
            };
            window.wsAudioRX.onopen = window.wsAudioRXopen;
            window.wsAudioRX.onclose = window.wsAudioRXclose;
            window.wsAudioRX.onerror = window.wsAudioRXerror;
            
        } catch (error) {
            console.error('Failed to create Audio RX WebSocket connection:', error);
            if (statusElement) {
                statusElement.innerHTML = '<img src="img/critsred.png">wsRX';
            }
        }
        
        // Call original function if it exists
        if (originalAudioRX_start) {
            originalAudioRX_start();
        }
    };
    
    console.log('Audio RX connection fix applied successfully');
}

// Fix for mobile interface power button not connecting wsRX
const originalPowerToggle = window.powerToggle;
window.powerToggle = function() {
    console.log('Fixed: Power toggle clicked');
    
    // Call original power toggle function
    if (originalPowerToggle) {
        originalPowerToggle();
    }
    
    // Ensure all WebSocket connections are properly initialized
    setTimeout(() => {
        // Check if power is on
        if (window.poweron) {
            console.log('Power is ON, ensuring all connections are active');
            
            // Check and restart Audio RX if needed
            if (typeof AudioRX_start === 'function') {
                console.log('Starting Audio RX connection');
                AudioRX_start();
            }
            
            // Check and restart Audio TX if needed
            if (typeof AudioTX_start === 'function') {
                console.log('Starting Audio TX connection');
                AudioTX_start();
            }
            
            // Check and restart Control TRX if needed
            if (typeof ControlTRX_start === 'function') {
                console.log('Starting Control TRX connection');
                ControlTRX_start();
            }
        }
    }, 100);
};

console.log('All fixes applied');