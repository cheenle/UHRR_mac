"""
Audio Service - Handles audio streaming and processing
"""

import asyncio
import logging
import numpy as np
from typing import Dict, List, Optional, Any
import pyaudio
import struct
from datetime import datetime

logger = logging.getLogger(__name__)


class AudioService:
    """Modern async audio service using PyAudio"""

    def __init__(self):
        self.is_initialized = False
        self.audio = None
        self.stream = None
        self.input_device_index = None
        self.output_device_index = None
        self.sample_rate = 24000
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16

        # Audio buffers and statistics
        self.audio_buffer = []
        self.buffer_lock = asyncio.Lock()
        self.stats = {
            'packets_received': 0,
            'packets_sent': 0,
            'bytes_received': 0,
            'bytes_sent': 0,
            'last_activity': None
        }

        # Connected clients
        self.clients = set()

    async def initialize(self):
        """Initialize audio service"""
        try:
            logger.info("🎵 Initializing AudioService...")

            self.audio = pyaudio.PyAudio()

            # Find audio devices
            self.input_device_index = self._find_input_device()
            self.output_device_index = self._find_output_device()

            if self.input_device_index is None:
                raise RuntimeError("No suitable input device found")

            # Initialize input stream
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )

            self.is_initialized = True
            logger.info("✅ AudioService initialized successfully")

        except Exception as e:
            logger.error(f"❌ AudioService initialization failed: {e}")
            raise

    def _find_input_device(self) -> Optional[int]:
        """Find suitable input device"""
        try:
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    logger.info(f"Found input device: {device_info['name']}")
                    return i
            return None
        except Exception as e:
            logger.error(f"Error finding input device: {e}")
            return None

    def _find_output_device(self) -> Optional[int]:
        """Find suitable output device"""
        try:
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxOutputChannels'] > 0:
                    logger.info(f"Found output device: {device_info['name']}")
                    return i
            return None
        except Exception as e:
            logger.error(f"Error finding output device: {e}")
            return None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for input audio"""
        try:
            # Convert bytes to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.int16)

            # Process audio data
            asyncio.create_task(self._process_audio_data(audio_data))

            return (in_data, pyaudio.paContinue)

        except Exception as e:
            logger.error(f"Audio callback error: {e}")
            return (in_data, pyaudio.paContinue)

    async def _process_audio_data(self, audio_data: np.ndarray):
        """Process incoming audio data"""
        try:
            # Update statistics
            self.stats['packets_received'] += 1
            self.stats['bytes_received'] += audio_data.nbytes
            self.stats['last_activity'] = datetime.utcnow()

            # Broadcast to all connected clients
            audio_bytes = audio_data.tobytes()

            # Send to clients via WebSocket
            for client_sid in list(self.clients):
                try:
                    # Convert to float32 for frontend
                    float32_data = (audio_data.astype(np.float32) / 32768.0).tobytes()
                    await sio.emit('audio-received', {
                        'data': float32_data,
                        'timestamp': datetime.utcnow().isoformat(),
                        'sample_rate': self.sample_rate,
                        'channels': self.channels
                    }, room=client_sid)

                except Exception as e:
                    logger.error(f"Error sending audio to client {client_sid}: {e}")
                    self.clients.discard(client_sid)

        except Exception as e:
            logger.error(f"Error processing audio data: {e}")

    async def handle_audio_data(self, sid: str, data: dict):
        """Handle audio data from client"""
        try:
            # Update statistics
            self.stats['packets_sent'] += 1
            self.stats['bytes_sent'] += len(data.get('data', b''))
            self.stats['last_activity'] = datetime.utcnow()

            # Process TX audio data
            audio_bytes = data.get('data', b'')
            if audio_bytes:
                # Convert back to int16 for playback
                audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
                int16_data = (audio_data * 32768).astype(np.int16)

                # Play audio (this would be sent to radio)
                await self._play_audio_to_radio(int16_data)

        except Exception as e:
            logger.error(f"Error handling audio data from {sid}: {e}")

    async def _play_audio_to_radio(self, audio_data: np.ndarray):
        """Play audio data to radio (placeholder)"""
        try:
            # This would interface with the radio's audio input
            # For now, just log the audio data
            logger.debug(f"Playing {len(audio_data)} samples to radio")

            # TODO: Implement actual radio audio output
            # This could use PyAudio output stream or direct radio interface

        except Exception as e:
            logger.error(f"Error playing audio to radio: {e}")

    def get_stats(self) -> dict:
        """Get audio service statistics"""
        return {
            'is_initialized': self.is_initialized,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'chunk_size': self.chunk_size,
            'input_device': self.input_device_index,
            'output_device': self.output_device_index,
            'buffer_length': len(self.audio_buffer),
            'clients_connected': len(self.clients),
            'stats': self.stats.copy()
        }

    async def cleanup(self):
        """Cleanup audio resources"""
        try:
            logger.info("🧹 Cleaning up AudioService...")

            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            if self.audio:
                self.audio.terminate()
                self.audio = None

            self.is_initialized = False
            self.clients.clear()

            logger.info("✅ AudioService cleanup complete")

        except Exception as e:
            logger.error(f"❌ AudioService cleanup error: {e}")
