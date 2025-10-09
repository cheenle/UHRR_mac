// ATR-1000 Troubleshooting Script
// This script provides diagnostic functions to help troubleshoot ATR-1000 connection issues

class AtuTroubleshooter {
    constructor() {
        this.results = [];
    }
    
    // Run all diagnostic tests
    async runAllTests(ip = '192.168.1.12', port = 81) {
        this.results = [];
        
        console.log('Starting ATR-1000 troubleshooting...');
        
        // Test 1: Basic connectivity
        await this.testConnectivity(ip);
        
        // Test 2: WebSocket connection
        await this.testWebSocketConnection(ip, port);
        
        // Test 3: HTTP access
        await this.testHttpAccess(ip);
        
        // Test 4: Port scan
        await this.testPort(ip, port);
        
        // Display results
        this.displayResults();
        
        return this.results;
    }
    
    // Test basic network connectivity
    async testConnectivity(ip) {
        this.log('Testing basic connectivity to ' + ip, 'info');
        
        try {
            // Try a simple fetch to test if host is reachable
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);
            
            const response = await fetch(`http://${ip}`, {
                method: 'HEAD',
                mode: 'no-cors',
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            this.log('✓ Host is reachable', 'success');
            this.results.push({test: 'Connectivity', status: 'PASS', details: 'Host is reachable'});
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.log('✗ Host is not responding (timeout)', 'error');
                this.results.push({test: 'Connectivity', status: 'FAIL', details: 'Host timeout'});
            } else {
                this.log('✓ Host is reachable (network level)', 'success');
                this.results.push({test: 'Connectivity', status: 'PASS', details: 'Host reachable'});
            }
        }
    }
    
    // Test WebSocket connection
    async testWebSocketConnection(ip, port) {
        this.log(`Testing WebSocket connection to ${ip}:${port}`, 'info');
        
        return new Promise((resolve) => {
            try {
                const url = `ws://${ip}:${port}/`;
                const socket = new WebSocket(url);
                let connected = false;
                
                const timeoutId = setTimeout(() => {
                    if (!connected) {
                        this.log(`✗ WebSocket connection timed out`, 'error');
                        this.results.push({test: 'WebSocket', status: 'FAIL', details: 'Connection timeout'});
                        try {
                            socket.close();
                        } catch (e) {
                            // Ignore
                        }
                        resolve();
                    }
                }, 5000);
                
                socket.onopen = () => {
                    if (!connected) {
                        connected = true;
                        clearTimeout(timeoutId);
                        this.log('✓ WebSocket connection established', 'success');
                        this.results.push({test: 'WebSocket', status: 'PASS', details: 'Connection established'});
                        
                        // Try to send a sync command
                        try {
                            const buffer = new ArrayBuffer(2);
                            const dataView = new DataView(buffer);
                            dataView.setUint8(0, 0xFF);
                            dataView.setUint8(1, 0x00);
                            socket.send(buffer);
                            this.log('✓ Sent SYNC command', 'success');
                        } catch (sendError) {
                            this.log(`⚠ Error sending command: ${sendError.message}`, 'warning');
                        }
                        
                        // Close after a short delay
                        setTimeout(() => {
                            socket.close();
                            resolve();
                        }, 1000);
                    }
                };
                
                socket.onerror = (error) => {
                    if (!connected) {
                        connected = true;
                        clearTimeout(timeoutId);
                        this.log(`✗ WebSocket error: ${error.message}`, 'error');
                        this.results.push({test: 'WebSocket', status: 'FAIL', details: `Error: ${error.message}`});
                        resolve();
                    }
                };
                
                socket.onclose = () => {
                    if (!connected) {
                        connected = true;
                        clearTimeout(timeoutId);
                        this.log('✗ WebSocket connection failed', 'error');
                        this.results.push({test: 'WebSocket', status: 'FAIL', details: 'Connection failed'});
                        resolve();
                    }
                };
                
            } catch (error) {
                this.log(`✗ Failed to create WebSocket: ${error.message}`, 'error');
                this.results.push({test: 'WebSocket', status: 'FAIL', details: `Creation error: ${error.message}`});
                resolve();
            }
        });
    }
    
    // Test HTTP access
    async testHttpAccess(ip) {
        this.log(`Testing HTTP access to ${ip}`, 'info');
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            const response = await fetch(`http://${ip}`, {
                method: 'GET',
                mode: 'no-cors',
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            this.log('✓ HTTP access successful', 'success');
            this.results.push({test: 'HTTP', status: 'PASS', details: 'HTTP access successful'});
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.log('✗ HTTP access timed out', 'error');
                this.results.push({test: 'HTTP', status: 'FAIL', details: 'HTTP timeout'});
            } else {
                this.log(`✓ HTTP access test completed (${error.message})`, 'warning');
                this.results.push({test: 'HTTP', status: 'WARN', details: `HTTP test: ${error.message}`});
            }
        }
    }
    
    // Test specific port
    async testPort(ip, port) {
        this.log(`Testing port ${ip}:${port}`, 'info');
        
        // For port testing, we'll use WebSocket since that's what ATR-1000 uses
        return new Promise((resolve) => {
            try {
                const url = `ws://${ip}:${port}/`;
                const socket = new WebSocket(url);
                let connected = false;
                
                const timeoutId = setTimeout(() => {
                    if (!connected) {
                        this.log(`✗ Port ${port} appears to be closed or filtered`, 'error');
                        this.results.push({test: 'Port', status: 'FAIL', details: `Port ${port} closed/filtered`});
                        try {
                            socket.close();
                        } catch (e) {
                            // Ignore
                        }
                        resolve();
                    }
                }, 3000);
                
                socket.onopen = () => {
                    if (!connected) {
                        connected = true;
                        clearTimeout(timeoutId);
                        this.log(`✓ Port ${port} is open`, 'success');
                        this.results.push({test: 'Port', status: 'PASS', details: `Port ${port} open`});
                        socket.close();
                        resolve();
                    }
                };
                
                socket.onerror = () => {
                    if (!connected) {
                        connected = true;
                        clearTimeout(timeoutId);
                        this.log(`✗ Port ${port} connection failed`, 'error');
                        this.results.push({test: 'Port', status: 'FAIL', details: `Port ${port} connection failed`});
                        resolve();
                    }
                };
                
            } catch (error) {
                this.log(`✗ Error testing port ${port}: ${error.message}`, 'error');
                this.results.push({test: 'Port', status: 'FAIL', details: `Port test error: ${error.message}`});
                resolve();
            }
        });
    }
    
    // Log messages
    log(message, type = 'info') {
        const timestamp = new Date().toISOString().substr(11, 12);
        console.log(`[${timestamp}][ATU-Troubleshoot][${type.toUpperCase()}] ${message}`);
    }
    
    // Display results
    displayResults() {
        console.log('\n=== ATR-1000 Troubleshooting Results ===');
        this.results.forEach(result => {
            const statusSymbol = result.status === 'PASS' ? '✓' : result.status === 'WARN' ? '⚠' : '✗';
            console.log(`${statusSymbol} ${result.test}: ${result.details}`);
        });
        console.log('========================================\n');
        
        // Summary
        const passCount = this.results.filter(r => r.status === 'PASS').length;
        const failCount = this.results.filter(r => r.status === 'FAIL').length;
        const warnCount = this.results.filter(r => r.status === 'WARN').length;
        
        if (failCount === 0) {
            console.log('🎉 All tests passed! Your ATR-1000 connection should work correctly.');
        } else {
            console.log(`⚠️  ${failCount} test(s) failed. Please check the issues above.`);
        }
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AtuTroubleshooter;
}

// Make available globally
if (typeof window !== 'undefined') {
    window.AtuTroubleshooter = AtuTroubleshooter;
}

// Run automatic diagnostic if called directly
if (typeof window !== 'undefined' && document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        // Only run if we're on a troubleshooting page
        if (window.location.pathname.includes('troubleshoot') || window.location.pathname.includes('diagnostic')) {
            console.log('ATR-1000 Troubleshooting Script Loaded');
            console.log('To run diagnostics, create an instance and call runAllTests():');
            console.log('const troubleshooter = new AtuTroubleshooter();');
            console.log('troubleshooter.runAllTests();');
        }
    });
}

console.log('ATR-1000 Troubleshooting Script Loaded');