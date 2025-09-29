"""
Universal HamRadio Remote - Modern Python Backend
FastAPI + AsyncIO + Socket.IO implementation
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
import socketio
import asyncio
import logging
import struct
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

# Import custom modules
from app.config import settings
from app.services.audio_service import AudioService
from app.services.radio_service import RadioService
from app.services.websocket_service import WebSocketService
from app.models.radio_state import RadioState
from app.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ORIGINS,
    logger=True,
    engineio_logger=True
)

# Create FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("🚀 Starting Universal HamRadio Remote Backend")

    # Initialize services
    await audio_service.initialize()
    await radio_service.initialize()
    await websocket_service.initialize()

    logger.info("✅ All services initialized")

    yield

    # Cleanup
    logger.info("🔄 Shutting down services...")
    await audio_service.cleanup()
    await radio_service.cleanup()
    await websocket_service.cleanup()
    logger.info("✅ Shutdown complete")

app = FastAPI(
    title="Universal HamRadio Remote API",
    description="Modern backend for ham radio remote control",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS
    )

# Initialize services
audio_service = AudioService()
radio_service = RadioService()
websocket_service = WebSocketService(sio)

# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"🔌 Client connected: {sid}")
    await websocket_service.handle_connect(sid, auth)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"🔌 Client disconnected: {sid}")
    await websocket_service.handle_disconnect(sid)

@sio.event
async def join_radio(sid, data):
    """Handle joining radio session"""
    await websocket_service.handle_join_radio(sid, data)

@sio.event
async def audio_data(sid, data):
    """Handle incoming audio data"""
    await audio_service.handle_audio_data(sid, data)

@sio.event
async def radio_command(sid, data):
    """Handle radio control commands"""
    await radio_service.handle_radio_command(sid, data)

@sio.event
async def heartbeat(sid, data):
    """Handle heartbeat from client"""
    await websocket_service.handle_heartbeat(sid, data)

# FastAPI routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - redirect to frontend"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Universal HamRadio Remote</title>
        <meta http-equiv="refresh" content="0; url=/app">
    </head>
    <body>
        <p>Redirecting to application...</p>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "services": {
            "audio": audio_service.is_initialized,
            "radio": radio_service.is_initialized,
            "websocket": websocket_service.is_initialized
        }
    }

@app.get("/api/radio/status")
async def get_radio_status():
    """Get current radio status"""
    try:
        status = await radio_service.get_status()
        return {"status": "success", "data": status}
    except Exception as e:
        logger.error(f"Failed to get radio status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get radio status")

@app.post("/api/radio/command")
async def execute_radio_command(command: dict):
    """Execute radio command"""
    try:
        result = await radio_service.execute_command(command)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Failed to execute radio command: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute radio command")

@app.get("/api/audio/stats")
async def get_audio_stats():
    """Get audio service statistics"""
    try:
        stats = audio_service.get_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Failed to get audio stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get audio stats")

# WebSocket endpoint for Socket.IO
app.mount('/socket.io', socketio.ASGIApp(sio))

# Static files for frontend
if settings.SERVE_FRONTEND:
    from fastapi.staticfiles import StaticFiles
    app.mount("/app", StaticFiles(directory="../frontend/dist", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting UHRR Backend Server...")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
