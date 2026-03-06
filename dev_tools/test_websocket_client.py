#!/usr/bin/env python3
import asyncio
import websockets
import ssl
import time

async def test_audio_rx_connection():
    uri = "wss://localhost:8888/WSaudioRX"
    
    # Create SSL context that ignores certificate verification for testing
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        print("Connecting to WebSocket...")
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("Connected to audio RX WebSocket!")
            print("Waiting for audio data...")
            
            # Send ready message to start receiving data
            await websocket.send("ready")
            
            # Listen for audio data
            count = 0
            while count < 10:  # Listen for 10 messages
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    count += 1
                    print(f"Received audio data packet {count}: {len(message)} bytes")
                except asyncio.TimeoutError:
                    print("Timeout waiting for audio data")
                    break
                    
    except Exception as e:
        print(f"WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_audio_rx_connection())