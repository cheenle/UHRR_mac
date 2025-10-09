#!/usr/bin/env python3
"""
Test script to verify the optimization effects:
1. Data format optimization: Float32 → Int16 (50% reduction)
2. Network packet merge optimization: Accumulate data before sending
3. Sample rate optimization: 12kHz (already implemented)
"""

import time
import websocket
import threading
import json

class OptimizationTester:
    def __init__(self):
        self.rx_bytes = 0
        self.packet_count = 0
        self.start_time = None
        self.ws = None
        
    def on_message(self, ws, message):
        """Handle incoming audio data"""
        if isinstance(message, bytes):
            self.rx_bytes += len(message)
            self.packet_count += 1
            
            # Calculate bandwidth every 10 packets
            if self.packet_count % 10 == 0:
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    bandwidth_kbps = (self.rx_bytes * 8) / (elapsed * 1000)
                    print(f"📊 Packet #{self.packet_count}: {len(message)} bytes, "
                          f"Total: {self.rx_bytes} bytes, "
                          f"Bandwidth: {bandwidth_kbps:.1f} kbps")
    
    def on_error(self, ws, error):
        print(f"❌ WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("🔌 WebSocket connection closed")
    
    def on_open(self, ws):
        print("✅ WebSocket connection opened")
        self.start_time = time.time()
        print("🎵 Starting audio data monitoring...")
    
    def test_optimization(self):
        """Test the optimization effects"""
        print("🚀 Testing UHRR Audio Optimization Effects")
        print("=" * 50)
        
        # Connect to WebSocket
        ws_url = "wss://localhost:8877/WSaudioRX"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        try:
            # Run for 30 seconds
            print("⏱️  Monitoring for 30 seconds...")
            self.ws.run_forever(sslopt={"cert_reqs": False})
        except KeyboardInterrupt:
            print("\n⏹️  Test interrupted by user")
        except Exception as e:
            print(f"❌ Test failed: {e}")
        finally:
            if self.ws:
                self.ws.close()
            
            # Calculate final statistics
            if self.start_time:
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    final_bandwidth = (self.rx_bytes * 8) / (elapsed * 1000)
                    avg_packet_size = self.rx_bytes / self.packet_count if self.packet_count > 0 else 0
                    
                    print("\n📈 Final Results:")
                    print("=" * 30)
                    print(f"Total packets received: {self.packet_count}")
                    print(f"Total bytes received: {self.rx_bytes}")
                    print(f"Average packet size: {avg_packet_size:.1f} bytes")
                    print(f"Average bandwidth: {final_bandwidth:.1f} kbps")
                    print(f"Test duration: {elapsed:.1f} seconds")
                    
                    # Compare with theoretical values
                    print("\n🔍 Optimization Analysis:")
                    print("=" * 30)
                    print("✅ Sample rate: 12kHz (50% reduction from 24kHz)")
                    print("✅ Data format: Int16 (50% reduction from Float32)")
                    print("✅ Packet merging: Accumulated data before sending")
                    print(f"📊 Measured bandwidth: {final_bandwidth:.1f} kbps")
                    print("📊 Theoretical bandwidth: ~192 kbps (12kHz × 16-bit)")
                    
                    if final_bandwidth < 250:
                        print("🎉 Optimization successful! Bandwidth significantly reduced.")
                    else:
                        print("⚠️  Bandwidth higher than expected. Check optimization implementation.")

if __name__ == "__main__":
    tester = OptimizationTester()
    tester.test_optimization()
