"""
Configuration settings for UHRR Backend
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with validation"""

    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=3000, env="PORT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # Security settings
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:8080"], env="CORS_ORIGINS")
    TRUSTED_HOSTS: List[str] = Field(default=[], env="TRUSTED_HOSTS")

    # TLS settings
    TLS_ENABLED: bool = Field(default=False, env="TLS_ENABLED")
    CERT_FILE: Optional[str] = Field(default=None, env="CERT_FILE")
    KEY_FILE: Optional[str] = Field(default=None, env="KEY_FILE")

    # Audio settings
    AUDIO_SAMPLE_RATE: int = Field(default=24000, env="AUDIO_SAMPLE_RATE")
    AUDIO_CHANNELS: int = Field(default=1, env="AUDIO_CHANNELS")
    AUDIO_CHUNK_SIZE: int = Field(default=1024, env="AUDIO_CHUNK_SIZE")
    AUDIO_DEVICE_INDEX: Optional[int] = Field(default=None, env="AUDIO_DEVICE_INDEX")

    # Radio settings
    RADIO_MODEL: str = Field(default="IC-7100", env="RADIO_MODEL")
    RADIO_PORT: str = Field(default="/dev/ttyUSB0", env="RADIO_PORT")
    RADIO_BAUDRATE: int = Field(default=19200, env="RADIO_BAUDRATE")
    RIGCTLD_HOST: str = Field(default="localhost", env="RIGCTLD_HOST")
    RIGCTLD_PORT: int = Field(default=4532, env="RIGCTLD_PORT")

    # WebSocket settings
    HEARTBEAT_INTERVAL: int = Field(default=30, env="HEARTBEAT_INTERVAL")
    MAX_CONNECTIONS: int = Field(default=100, env="MAX_CONNECTIONS")
    CONNECTION_TIMEOUT: int = Field(default=60, env="CONNECTION_TIMEOUT")

    # Database settings (for future use)
    DATABASE_URL: str = Field(default="sqlite:///./uhrr.db", env="DATABASE_URL")

    # Redis settings (for clustering)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    REDIS_ENABLED: bool = Field(default=False, env="REDIS_ENABLED")

    # Monitoring
    PROMETHEUS_ENABLED: bool = Field(default=False, env="PROMETHEUS_ENABLED")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")

    # Frontend settings
    SERVE_FRONTEND: bool = Field(default=True, env="SERVE_FRONTEND")
    FRONTEND_URL: str = Field(default="http://localhost:3000", env="FRONTEND_URL")

    # Version
    VERSION: str = "2.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Validate critical settings
def validate_settings():
    """Validate critical configuration settings"""
    errors = []

    if settings.TLS_ENABLED:
        if not settings.CERT_FILE or not settings.KEY_FILE:
            errors.append("TLS enabled but CERT_FILE or KEY_FILE not provided")
        if settings.CERT_FILE and not os.path.exists(settings.CERT_FILE):
            errors.append(f"CERT_FILE not found: {settings.CERT_FILE}")
        if settings.KEY_FILE and not os.path.exists(settings.KEY_FILE):
            errors.append(f"KEY_FILE not found: {settings.KEY_FILE}")

    if settings.REDIS_ENABLED and not settings.REDIS_URL:
        errors.append("REDIS enabled but REDIS_URL not provided")

    if errors:
        raise ValueError("Configuration validation failed: " + "; ".join(errors))

# Validate on import
validate_settings()
