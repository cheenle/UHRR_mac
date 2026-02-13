#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TCI (Transceiver Control Interface) client implementation
This module provides a client to connect to TCI-compatible radio equipment
"""

import asyncio
import websockets
import json
import threading
import time
import logging
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)

class TCIController:
    """
    TCI (Transceiver Control Interface) Controller
    Provides interface to control TCI-compatible radio equipment over network
    """
    
    def __init__(self, host: str = "localhost", port: int = 50001):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.websocket = None
        self.connected = False
        self.callbacks = {}
        self._stop_event = threading.Event()
        
        # Radio state
        self.frequency = 0.0
        self.mode = ""
        self.ptt_state = False
        self.power = 0
        self.squelch = 0
        self.volume = 0
        
    async def connect(self):
        """Connect to TCI server"""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            logger.info(f"✅ Connected to TCI server at {self.uri}")
            
            # Start listening for incoming messages
            asyncio.create_task(self._listen_for_messages())
            
            # Request initial state
            await self.request_initial_state()
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to TCI server: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from TCI server"""
        self.connected = False
        self._stop_event.set()
        if self.websocket:
            await self.websocket.close()
        logger.info("Disconnected from TCI server")
    
    async def _listen_for_messages(self):
        """Listen for incoming messages from TCI server"""
        try:
            async for message in self.websocket:
                if self._stop_event.is_set():
                    break
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("TCI WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in TCI message listener: {e}")
            self.connected = False
    
    async def _handle_message(self, message: str):
        """Handle incoming TCI message"""
        try:
            # TCI messages are in format: command:arg1,arg2,arg3;
            if message.endswith(';'):
                # Parse TCI command format
                parts = message.rstrip(';').split(':', 1)
                if len(parts) == 2:
                    cmd = parts[0].lower()
                    args = parts[1].split(',') if parts[1] else []
                    
                    # Update internal state based on received commands
                    if cmd == 'freq' and len(args) >= 2:
                        try:
                            vfo = args[0]  # VFO identifier
                            freq = float(args[1])  # Frequency in Hz
                            self.frequency = freq
                            logger.debug(f"Updated frequency: {freq} Hz")
                            
                            # Call frequency change callback if registered
                            if 'freq_change' in self.callbacks:
                                self.callbacks['freq_change'](freq)
                                
                        except ValueError:
                            pass
                    elif cmd == 'mode' and len(args) >= 2:
                        try:
                            vfo = args[0]  # VFO identifier
                            mode = args[1]  # Mode string
                            self.mode = mode
                            logger.debug(f"Updated mode: {mode}")
                            
                            # Call mode change callback if registered
                            if 'mode_change' in self.callbacks:
                                self.callbacks['mode_change'](mode)
                                
                        except:
                            pass
                    elif cmd == 'ptt' and len(args) >= 2:
                        try:
                            vfo = args[0]  # VFO identifier
                            ptt = args[1] == '1'  # PTT state
                            self.ptt_state = ptt
                            logger.debug(f"Updated PTT: {'ON' if ptt else 'OFF'}")
                            
                            # Call PTT change callback if registered
                            if 'ptt_change' in self.callbacks:
                                self.callbacks['ptt_change'](ptt)
                                
                        except:
                            pass
                    elif cmd.startswith('vfo_'):
                        # Handle VFO-related commands
                        logger.debug(f"VFO command: {cmd} with args: {args}")
            else:
                # This might be a JSON message or other format
                logger.debug(f"Received non-TCI format message: {message}")
                
        except Exception as e:
            logger.error(f"Error handling TCI message: {e}")
    
    async def request_initial_state(self):
        """Request initial radio state from server"""
        # Request current frequency
        await self.send_command("get_freq", ["A"])  # VFO A
        # Request current mode
        await self.send_command("get_mode", ["A"])  # VFO A
        # Request current PTT status
        await self.send_command("get_ptt", ["A"])  # VFO A
    
    async def send_command(self, cmd: str, args: list = None) -> Optional[str]:
        """Send TCI command to server"""
        if not self.connected or not self.websocket:
            logger.error("Not connected to TCI server")
            return None
        
        if args is None:
            args = []
        
        try:
            # Format: command:arg1,arg2,arg3;
            message = f"{cmd}:{','.join(map(str, args))};"
            await self.websocket.send(message)
            logger.debug(f"Sent TCI command: {message}")
            return message
        except Exception as e:
            logger.error(f"Error sending TCI command: {e}")
            self.connected = False
            return None
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register a callback for specific events"""
        self.callbacks[event_type] = callback
    
    # Radio control methods
    async def set_frequency(self, frequency_hz: float, vfo: str = "A"):
        """Set radio frequency"""
        return await self.send_command("freq", [vfo, str(int(frequency_hz))])
    
    async def set_mode(self, mode: str, vfo: str = "A"):
        """Set radio mode (e.g., USB, LSB, CW, etc.)"""
        return await self.send_command("mode", [vfo, mode])
    
    async def set_ptt(self, ptt_state: bool, vfo: str = "A"):
        """Set PTT state"""
        state_str = "1" if ptt_state else "0"
        return await self.send_command("ptt", [vfo, state_str])
    
    async def get_frequency(self, vfo: str = "A"):
        """Get current frequency"""
        await self.send_command("get_freq", [vfo])
        return self.frequency
    
    async def get_mode(self, vfo: str = "A"):
        """Get current mode"""
        await self.send_command("get_mode", [vfo])
        return self.mode
    
    async def get_ptt_state(self, vfo: str = "A"):
        """Get current PTT state"""
        await self.send_command("get_ptt", [vfo])
        return self.ptt_state
    
    # Convenience methods
    async def set_split(self, enabled: bool):
        """Enable/disable split operation"""
        state_str = "1" if enabled else "0"
        return await self.send_command("split", [state_str])
    
    async def set_power(self, power_level: int):
        """Set power level"""
        return await self.send_command("power", [str(power_level)])
    
    async def set_squelch(self, squelch_level: int):
        """Set squelch level"""
        return await self.send_command("squelch", [str(squelch_level)])
    
    async def set_volume(self, volume_level: int):
        """Set audio volume"""
        return await self.send_command("volume", [str(volume_level)])
    
    def is_connected(self):
        """Check if connected to TCI server"""
        if not self.connected or not self.websocket:
            return False
        # For newer websockets library versions, check the connection state differently
        try:
            # Check if websocket is closed (newer websockets versions)
            if hasattr(self.websocket, 'closed'):
                return not self.websocket.closed
            else:
                # For newer websockets.asyncio, check the protocol state
                return self.websocket.protocol and not self.websocket.protocol.closed
        except:
            return False


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Create TCI controller instance
        tci = TCIController("localhost", 50001)
        
        # Register callbacks for changes
        def on_frequency_change(freq):
            print(f"Frequency changed to: {freq} Hz")
        
        def on_mode_change(mode):
            print(f"Mode changed to: {mode}")
        
        def on_ptt_change(ptt):
            print(f"PTT changed to: {'ON' if ptt else 'OFF'}")
        
        tci.register_callback('freq_change', on_frequency_change)
        tci.register_callback('mode_change', on_mode_change)
        tci.register_callback('ptt_change', on_ptt_change)
        
        # Connect to TCI server
        if await tci.connect():
            print("Connected to TCI server, testing commands...")
            
            # Test setting frequency
            await tci.set_frequency(14074000.0)  # 20m band
            await asyncio.sleep(1)
            
            # Test setting mode
            await tci.set_mode("USB")
            await asyncio.sleep(1)
            
            # Test PTT
            await tci.set_ptt(True)
            await asyncio.sleep(1)
            await tci.set_ptt(False)
            
            # Keep running to receive updates
            await asyncio.sleep(10)
            
            await tci.disconnect()
        else:
            print("Failed to connect to TCI server")
    
    # Run the example
    asyncio.run(main())