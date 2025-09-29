"""
Radio Service - Handles radio control and communication with rigctld
"""

import asyncio
import logging
import socket
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class RadioService:
    """Modern async radio service using rigctld"""

    def __init__(self):
        self.is_initialized = False
        self.radio_state = {
            'frequency': 7050000,
            'mode': 'USB',
            'power': 100,
            'ptt': False,
            'signal_strength': 0,
            'connected': False,
            'last_update': None
        }
        self.host = 'localhost'
        self.port = 4532
        self.socket = None
        self.connected_clients = set()

        # Command queue for async processing
        self.command_queue = asyncio.Queue()
        self.is_processing = False

    async def initialize(self):
        """Initialize radio service"""
        try:
            logger.info("📡 Initializing RadioService...")

            # Start command processor
            self.is_processing = True
            asyncio.create_task(self._process_commands())

            # Connect to rigctld
            await self._connect_to_rigctld()

            # Start periodic status updates
            asyncio.create_task(self._periodic_status_update())

            self.is_initialized = True
            logger.info("✅ RadioService initialized successfully")

        except Exception as e:
            logger.error(f"❌ RadioService initialization failed: {e}")
            raise

    async def _connect_to_rigctld(self):
        """Connect to rigctld daemon"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))

            self.radio_state['connected'] = True
            logger.info(f"✅ Connected to rigctld at {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"❌ Failed to connect to rigctld: {e}")
            self.radio_state['connected'] = False
            raise

    async def _send_command(self, command: str) -> str:
        """Send command to rigctld and get response"""
        try:
            if not self.socket:
                await self._connect_to_rigctld()

            # Send command
            full_command = command + '\n'
            self.socket.send(full_command.encode())

            # Read response
            response = self.socket.recv(1024).decode().strip()

            logger.debug(f"📡 Sent: {command}, Received: {response}")
            return response

        except Exception as e:
            logger.error(f"❌ Error sending command '{command}': {e}")
            self.radio_state['connected'] = False
            raise

    async def _process_commands(self):
        """Process queued radio commands"""
        while self.is_processing:
            try:
                command_data = await self.command_queue.get()

                if command_data['type'] == 'set_frequency':
                    await self._set_frequency(command_data['frequency'])
                elif command_data['type'] == 'set_mode':
                    await self._set_mode(command_data['mode'])
                elif command_data['type'] == 'set_ptt':
                    await self._set_ptt(command_data['state'])
                elif command_data['type'] == 'get_status':
                    await self._update_status()

                self.command_queue.task_done()

            except Exception as e:
                logger.error(f"❌ Error processing command: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop

    async def handle_radio_command(self, sid: str, data: dict):
        """Handle radio command from client"""
        try:
            command_type = data.get('type')
            command_value = data.get('value')

            # Queue command for processing
            await self.command_queue.put({
                'type': command_type,
                'value': command_value,
                'sid': sid,
                'timestamp': datetime.utcnow()
            })

            logger.debug(f"📡 Queued command: {command_type} from {sid}")

        except Exception as e:
            logger.error(f"❌ Error handling radio command from {sid}: {e}")

    async def _set_frequency(self, frequency: int):
        """Set radio frequency"""
        try:
            response = await self._send_command(f'F {frequency}')
            if response.startswith('RPRT 0'):
                self.radio_state['frequency'] = frequency
                self.radio_state['last_update'] = datetime.utcnow()
                logger.info(f"📡 Frequency set to {frequency} Hz")
                await self._broadcast_state()
            else:
                logger.error(f"❌ Failed to set frequency: {response}")

        except Exception as e:
            logger.error(f"❌ Error setting frequency: {e}")

    async def _set_mode(self, mode: str):
        """Set radio mode"""
        try:
            # Map mode to rigctld format
            mode_map = {
                'USB': 'USB',
                'LSB': 'LSB',
                'CW': 'CW',
                'AM': 'AM',
                'FM': 'FM'
            }

            rig_mode = mode_map.get(mode.upper(), 'USB')

            response = await self._send_command(f'M {rig_mode} 2400')
            if response.startswith('RPRT 0'):
                self.radio_state['mode'] = mode.upper()
                self.radio_state['last_update'] = datetime.utcnow()
                logger.info(f"📡 Mode set to {mode}")
                await self._broadcast_state()
            else:
                logger.error(f"❌ Failed to set mode: {response}")

        except Exception as e:
            logger.error(f"❌ Error setting mode: {e}")

    async def _set_ptt(self, state: bool):
        """Set PTT state"""
        try:
            ptt_value = '1' if state else '0'
            response = await self._send_command(f'T {ptt_value}')

            if response.startswith('RPRT 0'):
                self.radio_state['ptt'] = state
                self.radio_state['last_update'] = datetime.utcnow()
                logger.info(f"📡 PTT set to {state}")
                await self._broadcast_state()
            else:
                logger.error(f"❌ Failed to set PTT: {response}")

        except Exception as e:
            logger.error(f"❌ Error setting PTT: {e}")

    async def _update_status(self):
        """Update radio status from rigctld"""
        try:
            # Get frequency
            freq_response = await self._send_command('f')
            if freq_response and not freq_response.startswith('RPRT'):
                try:
                    self.radio_state['frequency'] = int(freq_response)
                except ValueError:
                    pass

            # Get mode
            mode_response = await self._send_command('m')
            if mode_response and not mode_response.startswith('RPRT'):
                try:
                    mode_data = mode_response.split()
                    if len(mode_data) >= 1:
                        self.radio_state['mode'] = mode_data[0]
                except (ValueError, IndexError):
                    pass

            # Get signal strength
            signal_response = await self._send_command('l')
            if signal_response and not signal_response.startswith('RPRT'):
                try:
                    self.radio_state['signal_strength'] = int(signal_response)
                except ValueError:
                    pass

            self.radio_state['last_update'] = datetime.utcnow()
            self.radio_state['connected'] = True

            # Broadcast updated state
            await self._broadcast_state()

        except Exception as e:
            logger.error(f"❌ Error updating status: {e}")
            self.radio_state['connected'] = False

    async def _periodic_status_update(self):
        """Periodic status updates"""
        while True:
            try:
                await asyncio.sleep(1.0)  # Update every second
                await self._update_status()
            except Exception as e:
                logger.error(f"❌ Periodic status update error: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error

    async def _broadcast_state(self):
        """Broadcast current radio state to all clients"""
        try:
            # Send to all connected clients via Socket.IO
            await sio.emit('radio-status', {
                'frequency': self.radio_state['frequency'],
                'mode': self.radio_state['mode'],
                'power': self.radio_state['power'],
                'ptt': self.radio_state['ptt'],
                'signal_strength': self.radio_state['signal_strength'],
                'connected': self.radio_state['connected'],
                'timestamp': self.radio_state['last_update'].isoformat() if self.radio_state['last_update'] else None
            })

        except Exception as e:
            logger.error(f"❌ Error broadcasting radio state: {e}")

    async def get_status(self) -> dict:
        """Get current radio status"""
        return self.radio_state.copy()

    async def execute_command(self, command: dict) -> dict:
        """Execute a radio command"""
        command_type = command.get('command')
        value = command.get('value')

        if command_type == 'setFrequency':
            await self._set_frequency(int(value))
        elif command_type == 'setMode':
            await self._set_mode(value)
        elif command_type == 'setPTT':
            await self._set_ptt(bool(value))
        elif command_type == 'getStatus':
            return await self.get_status()
        else:
            raise ValueError(f"Unknown command: {command_type}")

        return await self.get_status()

    def validate_frequency(self, frequency: int) -> bool:
        """Validate frequency value"""
        return 100000 <= frequency <= 30000000000  # 100kHz to 30GHz

    def validate_mode(self, mode: str) -> bool:
        """Validate mode value"""
        valid_modes = ['USB', 'LSB', 'CW', 'AM', 'FM']
        return mode.upper() in valid_modes

    async def cleanup(self):
        """Cleanup radio service"""
        try:
            logger.info("🧹 Cleaning up RadioService...")

            self.is_processing = False

            if self.socket:
                self.socket.close()
                self.socket = None

            self.radio_state['connected'] = False
            self.connected_clients.clear()

            logger.info("✅ RadioService cleanup complete")

        except Exception as e:
            logger.error(f"❌ RadioService cleanup error: {e}")
