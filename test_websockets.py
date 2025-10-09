#!/usr/bin/env python3

import websocket
import ssl
import time

def on_message(ws, message):
    print(f"Received message: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")

def on_open(ws):
    print("Connection opened")

if __name__ == "__main__":
    # Test Control WebSocket
    print("Testing Control WebSocket...")
    try:
        ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        ws.connect("wss://localhost:8443/WSCTRX")
        print("Control WebSocket connected successfully")
        ws.close()
    except Exception as e:
        print(f"Control WebSocket error: {e}")
    
    # Test Audio RX WebSocket
    print("\nTesting Audio RX WebSocket...")
    try:
        ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        ws.connect("wss://localhost:8443/WSaudioRX")
        print("Audio RX WebSocket connected successfully")
        ws.close()
    except Exception as e:
        print(f"Audio RX WebSocket error: {e}")
    
    # Test Audio TX WebSocket
    print("\nTesting Audio TX WebSocket...")
    try:
        ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        ws.connect("wss://localhost:8443/WSaudioTX")
        print("Audio TX WebSocket connected successfully")
        ws.close()
    except Exception as e:
        print(f"Audio TX WebSocket error: {e}")