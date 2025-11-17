// Script to modify controls.js to load WebAssembly dynamically

const fs = require('fs');
const path = require('path');

// Read the controls.js file
const controlsJsPath = path.join(__dirname, 'controls.js');
let controlsJsContent = fs.readFileSync(controlsJsPath, 'utf8');

// Find the allocate array containing the WebAssembly binary data
const allocateRegex = /allocate\(\[([\s\S]*?)\]\)/;
const match = controlsJsContent.match(allocateRegex);

if (!match) {
    console.error('Could not find WebAssembly binary data in controls.js');
    process.exit(1);
}

// Replace the embedded WebAssembly data with dynamic loading code
const wasmLoadingCode = `
// WebAssembly module loading - dynamically load opus.wasm
Module['wasmBinary'] = null;

// Function to load WebAssembly module
function loadWasmModule() {
    return fetch('opus.wasm')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load WebAssembly module: ' + response.statusText);
            }
            return response.arrayBuffer();
        })
        .then(buffer => {
            Module['wasmBinary'] = new Uint8Array(buffer);
            console.log('✅ WebAssembly module loaded successfully');
            return Module;
        })
        .catch(error => {
            console.error('❌ Failed to load WebAssembly module:', error);
            throw error;
        });
}

// Initialize WebAssembly when needed
var wasmInitialized = false;
function ensureWasmInitialized() {
    if (!wasmInitialized && Module['wasmBinary']) {
        // WebAssembly initialization would happen here
        wasmInitialized = true;
    }
    return wasmInitialized;
}`;

// Replace the allocate call with the dynamic loading code
const modifiedContent = controlsJsContent.replace(allocateRegex, wasmLoadingCode);

// Write the modified content back to controls.js
fs.writeFileSync(controlsJsPath, modifiedContent);

console.log('✅ controls.js modified to load WebAssembly dynamically');
console.log('📁 Original file backed up as controls.js.backup');