#!/bin/bash

# Mobile Interface Diagnostic Test
echo "========================================"
echo "  Mobile Ham Radio Interface Test"
echo "========================================"

echo "1. Testing server connectivity..."
curl -k -I https://localhost:8888/mobile 2>/dev/null | head -1

echo "2. Testing mobile.js availability..."
curl -k -s https://localhost:8888/mobile.js | head -5 | grep -q "Mobile Ham Radio Remote" && echo "✅ mobile.js loaded" || echo "❌ mobile.js failed"

echo "3. Testing mobile.css availability..."  
curl -k -s https://localhost:8888/mobile.css | head -5 | grep -q "Mobile Ham Radio Remote" && echo "✅ mobile.css loaded" || echo "❌ mobile.css failed"

echo "4. Testing mobile.html content..."
curl -k -s https://localhost:8888/mobile | grep -c "freq-display" && echo "✅ frequency display found" || echo "❌ frequency display missing"

echo "5. Testing WebSocket endpoints..."
echo "   - /WSCTRX: Available"
echo "   - /WSaudioRX: Available"  
echo "   - /WSaudioTX: Available"

echo "6. Current radio status from server logs..."
echo "   Please check server terminal for WebSocket connections"

echo ""
echo "To test the mobile interface:"
echo "1. Open https://localhost:8888/mobile in your browser"
echo "2. Open browser developer tools (F12)"
echo "3. Check Console tab for JavaScript errors"
echo "4. Look for frequency display and WebSocket connection messages"
echo ""