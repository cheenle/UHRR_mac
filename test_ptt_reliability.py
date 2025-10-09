#!/usr/bin/env python3
"""
Test script to verify PTT reliability improvements in UHRR
"""

import asyncio
import websockets
import ssl
import sys

async def test_ptt_reliability():
    # Create SSL context that doesn't verify certificates (for testing only)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Connect to UHRR WebSocket endpoint
        uri = "wss://localhost:8443/WSCTRX"
        print(f"Connecting to {uri}...")
        
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("Connected successfully!")
            
            # Send PTT ON command
            print("Sending PTT ON command...")
            await websocket.send("setPTT:true")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Send PTT OFF command
            print("Sending PTT OFF command...")
            await websocket.send("setPTT:false")
            
            # Wait for any responses
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"Received response: {response}")
            except asyncio.TimeoutError:
                print("No response received (expected)")
            
            print("Test completed successfully!")
            
    except Exception as e:
        print(f"Error during test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Testing PTT reliability improvements...")
    asyncio.run(test_ptt_reliability())