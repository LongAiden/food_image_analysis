from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    supabase_url: str = Field(validation_alias="SUPABASE_PROJECT_URL")
    supabase_service_key: str = Field(validation_alias="SUPABASE_SERVICE_KEY")
    supabase_bucket: str = Field(validation_alias="SUPABASE_BUCKETS")
    supabase_table: str = Field(validation_alias="SUPABASE_TABLE")

    supabase_bucket_test: str = Field(validation_alias="SUPABASE_BUCKETS_TEST")
    supabase_table_test: str = Field(validation_alias="SUPABASE_TABLE_TEST")

    # Support both legacy GEMINI_API_KEY and current GOOGLE_API_KEY
    google_api_key: str = Field(
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY")
    )

    telegram_bot_token: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_bot_password: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_BOT_PASSWORD"
    )
    telegram_webhook_secret: Optional[str] = None
    telegram_webhook_url: Optional[str] = Field(
        default=None, validation_alias="TELEGRAM_WEBHOOK_URL"
    )

    logfire_write_token: Optional[str] = Field(
        default=None, validation_alias="LOGFIRE_WRITE_TOKEN"
    )

    # Local tunneling (optional)
    enable_ngrok: bool = Field(default=False, validation_alias="ENABLE_NGROK")
    ngrok_port: int = Field(default=8000, validation_alias="NGROK_PORT")

    # App behaviour
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    max_image_size_mb: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )
