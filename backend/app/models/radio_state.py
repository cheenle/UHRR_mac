"""
Radio State Models
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class RadioMode(str, Enum):
    """Radio operation modes"""
    USB = "USB"
    LSB = "LSB"
    CW = "CW"
    AM = "AM"
    FM = "FM"
    DIGI = "DIGI"


class RadioState(BaseModel):
    """Radio state model"""

    frequency: int = Field(default=7050000, ge=100000, le=30000000000)
    mode: RadioMode = Field(default=RadioMode.USB)
    power: int = Field(default=100, ge=0, le=100)
    ptt: bool = Field(default=False)
    signal_strength: int = Field(default=0, ge=0, le=9)
    connected: bool = Field(default=False)
    last_update: Optional[datetime] = Field(default=None)

    class Config:
        from_attributes = True


class AudioConfig(BaseModel):
    """Audio configuration model"""

    sample_rate: int = Field(default=24000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    chunk_size: int = Field(default=1024, ge=256, le=4096)
    format: str = Field(default="int16")

    class Config:
        from_attributes = True


class RadioCommand(BaseModel):
    """Radio command model"""

    command: str = Field(..., min_length=1)
    value: Optional[str] = Field(default=None)
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class AudioData(BaseModel):
    """Audio data model"""

    data: bytes = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence: Optional[int] = Field(default=None)
    sample_rate: Optional[int] = Field(default=24000)
    channels: Optional[int] = Field(default=1)

    class Config:
        from_attributes = True
