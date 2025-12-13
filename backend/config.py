from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    supabase_url: str = Field(validation_alias="SUPABASE_PROJECT_URL")
    supabase_service_key: str = Field(validation_alias="SUPABASE_SERVICE_KEY")
    supabase_bucket: str = Field(validation_alias="SUPABASE_BUCKETS")
    supabase_table: str = Field(validation_alias="SUPABASE_TABLE")

    google_api_key: str = Field(validation_alias="GOOGLE_API_KEY")
    logfire_write_token: Optional[str] = Field(
        default=None, validation_alias="LOGFIRE_WRITE_TOKEN"
    )

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
