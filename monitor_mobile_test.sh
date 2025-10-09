#!/bin/bash
# Monitor UHRR server for mobile testing

echo "=== UHRR Mobile Interface Testing Monitor ==="
echo "Date: $(date)"
echo "Server PID: $(ps aux | grep UHRR | grep -v grep | awk '{print $2}')"
echo "Server Port: 8443"
echo ""
echo "Monitoring for mobile connection attempts and WebSocket activity..."
echo "Press Ctrl+C to stop monitoring"
echo ""

# Monitor system logs for UHRR activity
echo "--- System Log Activity ---"
log stream --predicate 'process == "Python"' --info --debug | grep -i "UHRR\|WebSocket\|mobile\|HTTP" &

# Store the background process ID
LOG_PID=$!

# Set up cleanup function
cleanup() {
    echo ""
    echo "Stopping monitor..."
    kill $LOG_PID 2>/dev/null
    exit 0
}

# Trap Ctrl+C
trap cleanup INT

# Wait indefinitely
wait