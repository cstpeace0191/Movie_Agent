import sys
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    VIDEO_PROVIDER: Literal["ltx-2.3", "gemini-omni-1.2-flash", "mock"] = "ltx-2.3"
    SESSION_SECRET: str = "change-this-to-a-secure-random-secret-key-in-production"
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    LTX_COMFYUI_URL: str = "http://127.0.0.1:8188"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = "sqlite:///./movie_agent.db"
    STORAGE_DIR: str = "./storage"
    ENV: str = "test" if "pytest" in sys.modules else "development"

    # SMTP email configuration
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "noreply@moviemaker.local"
    SMTP_TLS: bool = True

    # Built-in Python aiosmtpd Mail Server configuration
    MAIL_SERVER_ENABLED: bool = True
    MAIL_SERVER_HOST: str = "0.0.0.0"
    MAIL_SERVER_PORT: int = 1025

    # Limit constants
    MAX_IMAGES_PER_JOB: int = 100
    MAX_IMAGE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MiB
    MAX_PLANNED_SECONDS: int = 180
    RETENTION_DAYS: int = 2
    SESSION_LIFETIME_DAYS: int = 7
    TASK_TIME_LIMIT_SECONDS: int = 1800  # 30 minutes


settings = Settings()
