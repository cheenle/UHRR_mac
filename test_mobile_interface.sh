#!/bin/bash

# Test script for the new mobile interface

echo "Testing Mobile Interface Implementation"
echo "======================================"

# Check if all required files exist
echo "Checking required files..."
REQUIRED_FILES=(
    "www/mobile_modern.html"
    "www/mobile_modern.css"
    "www/mobile_modern.js"
    "www/manifest.json"
    "www/sw.js"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file exists"
    else
        echo "  ❌ $file is missing"
    fi
done

# Check if the original mobile files still exist
echo ""
echo "Checking original mobile files (should still exist)..."
ORIGINAL_FILES=(
    "www/mobile.html"
    "www/mobile.css"
    "www/mobile.js"
)

for file in "${ORIGINAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file exists"
    else
        echo "  ❌ $file is missing"
    fi
done

# Check for proper HTML structure in new mobile interface
echo ""
echo "Checking HTML structure..."
if grep -q "mobile-modern-container" www/mobile_modern.html; then
    echo "  ✅ Modern mobile container found"
else
    echo "  ❌ Modern mobile container not found"
fi

if grep -q "ptt-button" www/mobile_modern.html; then
    echo "  ✅ PTT button found"
else
    echo "  ❌ PTT button not found"
fi

# Check for CSS features
echo ""
echo "Checking CSS features..."
if grep -q "safe-area-inset" www/mobile_modern.css; then
    echo "  ✅ Safe area insets support found"
else
    echo "  ❌ Safe area insets support not found"
fi

if grep -q "touch-action" www/mobile_modern.css; then
    echo "  ✅ Touch optimization found"
else
    echo "  ❌ Touch optimization not found"
fi

# Check for JavaScript functionality
echo ""
echo "Checking JavaScript features..."
if grep -q "handlePTTStart" www/mobile_modern.js; then
    echo "  ✅ PTT touch handling found"
else
    echo "  ❌ PTT touch handling not found"
fi

if grep -q "connectWebSocket" www/mobile_modern.js; then
    echo "  ✅ WebSocket support found"
else
    echo "  ❌ WebSocket support not found"
fi

echo ""
echo "Test completed!"