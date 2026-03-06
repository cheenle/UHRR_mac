// Script to extract WebAssembly binary data from controls.js and create opus.wasm

const fs = require('fs');
const path = require('path');

// Read the controls.js file
const controlsJsPath = path.join(__dirname, 'controls.js');
const controlsJsContent = fs.readFileSync(controlsJsPath, 'utf8');

// Find the allocate array containing the WebAssembly binary data
const allocateRegex = /allocate\(\[([\s\S]*?)\]\)/;
const match = controlsJsContent.match(allocateRegex);

if (!match) {
    console.error('Could not find WebAssembly binary data in controls.js');
    process.exit(1);
}

// Extract the array content
const arrayContent = match[1];

// Parse the array string into actual numbers
const binaryArray = arrayContent.split(',').map(num => parseInt(num.trim(), 10));

// Convert to Uint8Array
const wasmBinary = new Uint8Array(binaryArray);

// Write to .wasm file
const wasmPath = path.join(__dirname, 'opus.wasm');
fs.writeFileSync(wasmPath, wasmBinary);

console.log(`✅ WebAssembly binary extracted successfully!`);
console.log(`📁 File created: ${wasmPath}`);
console.log(`📊 Size: ${wasmBinary.length} bytes`);

// Verify the WASM file
const wasmFileStats = fs.statSync(wasmPath);
console.log(`✅ WASM file verified: ${wasmFileStats.size} bytes`);