"""
Audio API routes
"""

from fastapi import APIRouter, HTTPException
import logging

from app.services.audio_service import audio_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.get("/stats")
async def get_audio_stats():
    """Get audio service statistics"""
    try:
        stats = audio_service.get_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Failed to get audio stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get audio stats")


@router.get("/devices")
async def get_audio_devices():
    """Get available audio devices"""
    try:
        devices = audio_service.get_devices()
        return {"status": "success", "devices": devices}
    except Exception as e:
        logger.error(f"Failed to get audio devices: {e}")
        raise HTTPException(status_code=500, detail="Failed to get audio devices")


@router.post("/config")
async def update_audio_config(config: dict):
    """Update audio configuration"""
    try:
        result = await audio_service.update_config(config)
        return {"status": "success", "config": result}
    except Exception as e:
        logger.error(f"Failed to update audio config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update audio config")
