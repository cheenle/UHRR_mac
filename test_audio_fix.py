#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify audio streaming functionality
"""

import websocket
import ssl
import threading
import time
import json

def on_message(ws, message):
    """Handle incoming WebSocket messages"""
    print(f"Received message: {type(message)} - {len(message) if hasattr(message, '__len__') else 'N/A'} bytes")
    if isinstance(message, bytes):
        print(f"Binary message received: {len(message)} bytes")
    else:
        print(f"Text message received: {message}")

def on_error(ws, error):
    """Handle WebSocket errors"""
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket closure"""
    print("WebSocket connection closed")

def on_open(ws):
    """Handle WebSocket opening"""
    print("WebSocket connection opened")
    # Send a test message
    # ws.send("Test message from client")

def test_audio_rx_connection():
    """Test the audio RX WebSocket connection"""
    print("Testing Audio RX WebSocket connection...")
    
    # Use the same URL pattern as the mobile interface
    # ws_url = "wss://localhost:8766/WSaudioRX"  # Adjust host/port as needed
    # For testing without SSL:
    ws_url = "ws://localhost:8766/WSaudioRX"  # Adjust host/port as needed
    
    print(f"Connecting to: {ws_url}")
    
    try:
        # Create WebSocket connection
        ws = websocket.WebSocketApp(ws_url,
                                    on_open=on_open,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        
        # Run the WebSocket in a separate thread
        wst = threading.Thread(target=ws.run_forever, 
                              kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
        wst.daemon = True
        wst.start()
        
        # Keep the connection alive for 10 seconds to test
        time.sleep(10)
        
        # Close the connection
        ws.close()
        print("Test completed")
        
    except Exception as e:
        print(f"Error during test: {e}")

def test_audio_tx_connection():
    """Test the audio TX WebSocket connection"""
    print("Testing Audio TX WebSocket connection...")
    
    # Use the same URL pattern as the mobile interface
    # ws_url = "wss://localhost:8766/WSaudioTX"  # Adjust host/port as needed
    # For testing without SSL:
    ws_url = "ws://localhost:8766/WSaudioTX"  # Adjust host/port as needed
    
    print(f"Connecting to: {ws_url}")
    
    try:
        # Create WebSocket connection
        ws = websocket.WebSocketApp(ws_url,
                                    on_open=on_open,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        
        # Run the WebSocket in a separate thread
        wst = threading.Thread(target=ws.run_forever,
                              kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
        wst.daemon = True
        wst.start()
        
        # Keep the connection alive for 10 seconds to test
        time.sleep(10)
        
        # Close the connection
        ws.close()
        print("Test completed")
        
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    print("=== UHRR Audio Streaming Test ===")
    
    # Test RX connection
    test_audio_rx_connection()
    
    # Wait a bit between tests
    time.sleep(2)
    
    # Test TX connection
    test_audio_tx_connection()
    
    print("=== Test Complete ===")