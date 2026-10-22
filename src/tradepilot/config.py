"""Application configuration management for TradePilot AI."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TradePilot environment and configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Environment
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging verbosity")
    APP_HOST: str = Field(default="0.0.0.0", description="API server host")
    APP_PORT: int = Field(default=8000, description="API server port")
    
    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    PRIMARY_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
    FALLBACK_MODEL: str = Field(default="gpt-4o-2024-08-06")
    
    # External APIs
    COMTRADE_API_KEY: Optional[str] = Field(default=None)
    WTO_API_KEY: Optional[str] = Field(default=None)
    OPENCORPORATES_API_TOKEN: Optional[str] = Field(default=None)
    EXA_SEARCH_API_KEY: Optional[str] = Field(default=None)
    CUSTOMS_DATA_VENDOR_API_KEY: Optional[str] = Field(default=None)
    CUSTOMS_DATA_VENDOR_URL: Optional[str] = Field(default=None)
    
    # Endpoints & Gateways
    USITC_BASE_URL: str = Field(default="https://hts.usitc.gov/reststop")
    EU_TARIC_BASE_URL: str = Field(default="https://ec.europa.eu/taxation_customs/dds2/taric")
    DGFT_PORTAL_URL: str = Field(default="https://www.dgft.gov.in")
    
    # State Persistence
    DATABASE_URL: Optional[str] = Field(default=None)
    REDIS_URL: Optional[str] = Field(default=None)
    
    # LangGraph & Execution Controls
    MAX_WORKFLOW_STEPS: int = Field(default=30)
    WORKFLOW_TIMEOUT_SECONDS: int = Field(default=300)
    ENABLE_HUMAN_APPROVAL_INTERRUPTS: bool = Field(default=True)
    EVIDENCE_VERIFICATION_STRICT_MODE: bool = Field(default=True)
    
    # Project paths
    PROJECT_ROOT: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    SKILLS_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "skills")


settings = Settings()
