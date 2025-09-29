"""
WebSocket Service - Handles real-time communication and client management
"""

import asyncio
import logging
import json
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
import socketio

logger = logging.getLogger(__name__)


class WebSocketService:
    """Modern async WebSocket service using Socket.IO"""

    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        self.connected_clients: Set[str] = set()
        self.client_sessions: Dict[str, Dict] = {}
        self.heartbeat_timers: Dict[str, asyncio.Task] = {}
        self.max_connections = 100
        self.heartbeat_interval = 30  # seconds

    async def initialize(self):
        """Initialize WebSocket service"""
        logger.info("🔗 Initializing WebSocketService...")

        # Setup Socket.IO event handlers
        self.sio.on('connect')(self.handle_connect)
        self.sio.on('disconnect')(self.handle_disconnect)
        self.sio.on('join-radio')(self.handle_join_radio)
        self.sio.on('heartbeat')(self.handle_heartbeat)

        logger.info("✅ WebSocketService initialized")

    async def handle_connect(self, sid: str, environ: dict, auth: dict):
        """Handle client connection"""
        try:
            if len(self.connected_clients) >= self.max_connections:
                logger.warning(f"❌ Connection rejected: max connections ({self.max_connections}) reached")
                await self.sio.disconnect(sid)
                return

            self.connected_clients.add(sid)
            self.client_sessions[sid] = {
                'connected_at': datetime.utcnow(),
                'last_heartbeat': datetime.utcnow(),
                'radio_id': None,
                'user_agent': environ.get('HTTP_USER_AGENT', 'Unknown'),
                'ip_address': self._get_client_ip(environ)
            }

            # Start heartbeat timer
            self.heartbeat_timers[sid] = asyncio.create_task(
                self._heartbeat_monitor(sid)
            )

            logger.info(f"🔌 Client connected: {sid} from {self._get_client_ip(environ)}")

        except Exception as e:
            logger.error(f"❌ Error handling connection for {sid}: {e}")

    async def handle_disconnect(self, sid: str):
        """Handle client disconnection"""
        try:
            if sid in self.connected_clients:
                self.connected_clients.discard(sid)

            if sid in self.client_sessions:
                del self.client_sessions[sid]

            if sid in self.heartbeat_timers:
                self.heartbeat_timers[sid].cancel()
                del self.heartbeat_timers[sid]

            logger.info(f"🔌 Client disconnected: {sid}")

        except Exception as e:
            logger.error(f"❌ Error handling disconnection for {sid}: {e}")

    async def handle_join_radio(self, sid: str, data: dict):
        """Handle client joining radio session"""
        try:
            radio_id = data.get('radioId', 'default')
            self.client_sessions[sid]['radio_id'] = radio_id

            # Join Socket.IO room for this radio
            self.sio.enter_room(sid, radio_id)

            logger.info(f"📡 Client {sid} joined radio session: {radio_id}")

            # Send current radio status
            from app.services.radio_service import radio_service
            status = await radio_service.get_status()
            await self.sio.emit('radio-status', status, room=sid)

        except Exception as e:
            logger.error(f"❌ Error handling join-radio for {sid}: {e}")

    async def handle_heartbeat(self, sid: str, data: dict):
        """Handle heartbeat from client"""
        try:
            if sid in self.client_sessions:
                self.client_sessions[sid]['last_heartbeat'] = datetime.utcnow()

            # Respond with server timestamp
            await self.sio.emit('heartbeat-response', {
                'timestamp': datetime.utcnow().isoformat(),
                'server_time': datetime.utcnow().timestamp()
            }, room=sid)

        except Exception as e:
            logger.error(f"❌ Error handling heartbeat for {sid}: {e}")

    async def _heartbeat_monitor(self, sid: str):
        """Monitor client heartbeat"""
        try:
            while sid in self.connected_clients:
                await asyncio.sleep(self.heartbeat_interval)

                if sid in self.client_sessions:
                    last_heartbeat = self.client_sessions[sid]['last_heartbeat']
                    time_since_heartbeat = datetime.utcnow() - last_heartbeat

                    # Disconnect if no heartbeat for 2x interval
                    if time_since_heartbeat > timedelta(seconds=self.heartbeat_interval * 2):
                        logger.warning(f"⚠️ Client {sid} heartbeat timeout, disconnecting")
                        await self.sio.disconnect(sid)
                        break

        except asyncio.CancelledError:
            pass  # Normal cancellation
        except Exception as e:
            logger.error(f"❌ Heartbeat monitor error for {sid}: {e}")

    def _get_client_ip(self, environ: dict) -> str:
        """Extract client IP address from environment"""
        # Try various headers for client IP
        for header in ['HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR']:
            if header in environ:
                ip = environ[header]
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                return ip
        return 'unknown'

    async def broadcast_to_radio(self, radio_id: str, event: str, data: dict):
        """Broadcast message to all clients in a radio session"""
        try:
            await self.sio.emit(event, data, room=radio_id)
        except Exception as e:
            logger.error(f"❌ Error broadcasting to radio {radio_id}: {e}")

    async def send_to_client(self, sid: str, event: str, data: dict):
        """Send message to specific client"""
        try:
            await self.sio.emit(event, data, room=sid)
        except Exception as e:
            logger.error(f"❌ Error sending to client {sid}: {e}")

    def get_connection_stats(self) -> dict:
        """Get WebSocket connection statistics"""
        return {
            'connected_clients': len(self.connected_clients),
            'active_sessions': len(self.client_sessions),
            'max_connections': self.max_connections,
            'uptime': self._get_uptime()
        }

    def _get_uptime(self) -> str:
        """Get service uptime"""
        # This would be calculated from service start time
        return "Unknown"

    async def cleanup(self):
        """Cleanup WebSocket service"""
        try:
            logger.info("🧹 Cleaning up WebSocketService...")

            # Cancel all heartbeat timers
            for timer in self.heartbeat_timers.values():
                timer.cancel()

            self.heartbeat_timers.clear()
            self.connected_clients.clear()
            self.client_sessions.clear()

            logger.info("✅ WebSocketService cleanup complete")

        except Exception as e:
            logger.error(f"❌ WebSocketService cleanup error: {e}")
