#!/usr/bin/env python3
import asyncio
import websockets
import ssl
import time

async def test_websocket_connection(uri, name):
    """Test a WebSocket connection to the UHRR server"""
    print(f"Testing {name} connection to: {uri}")
    
    # Create SSL context that ignores certificate verification for testing
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        async with websockets.connect(uri, ssl=ssl_context, timeout=5) as websocket:
            print(f"✓ {name} connected successfully!")
            
            # For control WebSocket, try sending a command
            if "WSCTRX" in uri:
                print(f"  Sending getFreq command...")
                await websocket.send("getFreq:")
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"  Received response: {response}")
                except asyncio.TimeoutError:
                    print(f"  No response received within timeout")
            
            return True
            
    except Exception as e:
        print(f"✗ {name} connection failed: {e}")
        return False

async def test_all_websockets():
    """Test all UHRR WebSocket endpoints"""
    print("=== UHRR WebSocket Connection Test ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # WebSocket endpoints to test
    endpoints = [
        ("wss://localhost:8443/WSCTRX", "Control WebSocket"),
        ("wss://localhost:8443/WSaudioRX", "Audio RX WebSocket"),
        ("wss://localhost:8443/WSaudioTX", "Audio TX WebSocket")
    ]
    
    results = []
    
    for uri, name in endpoints:
        try:
            result = await test_websocket_connection(uri, name)
            results.append((name, result))
            print()
        except Exception as e:
            print(f"✗ {name} test failed with exception: {e}")
            results.append((name, False))
            print()
    
    # Summary
    print("=== Test Summary ===")
    all_passed = True
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ All WebSocket connections successful!")
    else:
        print("✗ Some WebSocket connections failed!")
    
    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(test_all_websockets())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"Test failed with exception: {e}")
        exit(1)