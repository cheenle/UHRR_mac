// Fix for wsRX not turning green in mobile interface
console.log('Applying wsRX status fix...');

// Function to update WebSocket status indicators
function updateWebSocketStatus(type, status) {
    const indicator = document.getElementById(`status-${type}`);
    if (indicator) {
        console.log(`Updating ${type} status to:`, status);
        if (status === 'connected') {
            indicator.classList.add('connected');
            indicator.textContent = type.toUpperCase();
        } else if (status === 'disconnected') {
            indicator.classList.remove('connected');
            indicator.textContent = type.toUpperCase();
        } else if (status === 'transmitting') {
            indicator.classList.add('connected');
            indicator.textContent = 'TX';
        }
    } else {
        console.log(`Indicator for ${type} not found`);
    }
}

// Override WebSocket event handlers to ensure proper status updates
function fixWebSocketHandlers() {
    // Fix for wsAudioRX
    if (window.wsAudioRX) {
        const originalOnOpen = window.wsAudioRX.onopen;
        window.wsAudioRX.onopen = function(event) {
            console.log('wsAudioRX connected');
            updateWebSocketStatus('rx', 'connected');
            if (originalOnOpen) originalOnOpen.call(this, event);
        };
        
        const originalOnClose = window.wsAudioRX.onclose;
        window.wsAudioRX.onclose = function(event) {
            console.log('wsAudioRX disconnected');
            updateWebSocketStatus('rx', 'disconnected');
            if (originalOnClose) originalOnClose.call(this, event);
        };
        
        const originalOnError = window.wsAudioRX.onerror;
        window.wsAudioRX.onerror = function(event) {
            console.log('wsAudioRX error');
            updateWebSocketStatus('rx', 'disconnected');
            if (originalOnError) originalOnError.call(this, event);
        };
    }
    
    // Fix for wsAudioTX
    if (window.wsAudioTX) {
        const originalOnOpen = window.wsAudioTX.onopen;
        window.wsAudioTX.onopen = function(event) {
            console.log('wsAudioTX connected');
            updateWebSocketStatus('tx', 'connected');
            if (originalOnOpen) originalOnOpen.call(this, event);
        };
        
        const originalOnClose = window.wsAudioTX.onclose;
        window.wsAudioTX.onclose = function(event) {
            console.log('wsAudioTX disconnected');
            updateWebSocketStatus('tx', 'disconnected');
            if (originalOnClose) originalOnClose.call(this, event);
        };
        
        const originalOnError = window.wsAudioTX.onerror;
        window.wsAudioTX.onerror = function(event) {
            console.log('wsAudioTX error');
            updateWebSocketStatus('tx', 'disconnected');
            if (originalOnError) originalOnError.call(this, event);
        };
    }
    
    // Fix for wsControlTRX
    if (window.wsControlTRX) {
        const originalOnOpen = window.wsControlTRX.onopen;
        window.wsControlTRX.onopen = function(event) {
            console.log('wsControlTRX connected');
            updateWebSocketStatus('ctrl', 'connected');
            if (originalOnOpen) originalOnOpen.call(this, event);
        };
        
        const originalOnClose = window.wsControlTRX.onclose;
        window.wsControlTRX.onclose = function(event) {
            console.log('wsControlTRX disconnected');
            updateWebSocketStatus('ctrl', 'disconnected');
            if (originalOnClose) originalOnClose.call(this, event);
        };
        
        const originalOnError = window.wsControlTRX.onerror;
        window.wsControlTRX.onerror = function(event) {
            console.log('wsControlTRX error');
            updateWebSocketStatus('ctrl', 'disconnected');
            if (originalOnError) originalOnError.call(this, event);
        };
    }
}

// Enhanced power toggle function
const originalPowerToggle = window.powerToggle;
window.powerToggle = function() {
    console.log('Power toggle clicked');
    
    // Call original function
    if (originalPowerToggle) {
        originalPowerToggle();
    }
    
    // Apply fixes after a short delay
    setTimeout(() => {
        fixWebSocketHandlers();
        
        // Force status update
        if (window.poweron) {
            console.log('Power ON - checking connections');
            // Update status indicators
            if (window.wsControlTRX && window.wsControlTRX.readyState === WebSocket.OPEN) {
                updateWebSocketStatus('ctrl', 'connected');
            }
            if (window.wsAudioRX && window.wsAudioRX.readyState === WebSocket.OPEN) {
                updateWebSocketStatus('rx', 'connected');
            }
            if (window.wsAudioTX && window.wsAudioTX.readyState === WebSocket.OPEN) {
                updateWebSocketStatus('tx', 'connected');
            }
        } else {
            console.log('Power OFF - disconnecting');
            updateWebSocketStatus('ctrl', 'disconnected');
            updateWebSocketStatus('rx', 'disconnected');
            updateWebSocketStatus('tx', 'disconnected');
        }
    }, 100);
};

// Apply fixes when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixWebSocketHandlers);
} else {
    fixWebSocketHandlers();
}

console.log('wsRX status fix applied');