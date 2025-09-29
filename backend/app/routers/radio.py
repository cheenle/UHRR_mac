"""
Radio control API routes
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import logging

from app.services.radio_service import radio_service
from app.models.radio_state import RadioCommand

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/radio", tags=["radio"])


@router.get("/status")
async def get_radio_status():
    """Get current radio status"""
    try:
        status = await radio_service.get_status()
        return {"status": "success", "data": status}
    except Exception as e:
        logger.error(f"Failed to get radio status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get radio status")


@router.post("/command")
async def execute_radio_command(command: RadioCommand):
    """Execute radio command"""
    try:
        result = await radio_service.execute_command(command.dict())
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Failed to execute radio command: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute radio command")


@router.post("/frequency/{frequency}")
async def set_frequency(frequency: int):
    """Set radio frequency"""
    try:
        if not radio_service.validate_frequency(frequency):
            raise HTTPException(status_code=400, detail="Invalid frequency")

        await radio_service.set_frequency(frequency)
        return {"status": "success", "frequency": frequency}
    except Exception as e:
        logger.error(f"Failed to set frequency: {e}")
        raise HTTPException(status_code=500, detail="Failed to set frequency")


@router.post("/mode/{mode}")
async def set_mode(mode: str):
    """Set radio mode"""
    try:
        if not radio_service.validate_mode(mode):
            raise HTTPException(status_code=400, detail="Invalid mode")

        await radio_service.set_mode(mode)
        return {"status": "success", "mode": mode}
    except Exception as e:
        logger.error(f"Failed to set mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to set mode")


@router.post("/ptt/{state}")
async def set_ptt(state: bool):
    """Set PTT state"""
    try:
        await radio_service.set_ptt(state)
        return {"status": "success", "ptt": state}
    except Exception as e:
        logger.error(f"Failed to set PTT: {e}")
        raise HTTPException(status_code=500, detail="Failed to set PTT")


@router.get("/modes")
async def get_available_modes():
    """Get available radio modes"""
    return {
        "status": "success",
        "modes": ["USB", "LSB", "CW", "AM", "FM"]
    }
