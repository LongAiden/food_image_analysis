import os
import logfire
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import List, Optional

import google.generativeai as genai
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

load_dotenv()

# Initialize client
SUPABASE_URL = os.getenv('SUPABASE_PROJECT_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKETS')
LOGFIRE_TOKEN = os.getenv('LOGFIRE_WRITE_TOKEN')

# Create app config class


class AppConfig:
    def __init__(self):
        # Initialize logfire with token from environment
        if LOGFIRE_TOKEN:
            logfire.configure(token=LOGFIRE_TOKEN)
            logfire.info("✓ Logfire configured successfully")
        else:
            logfire.info("⚠️ LOGFIRE_WRITE_TOKEN not found, using default configuration")
            logfire.configure()

        if SUPABASE_KEY:
            self.client = SupabaseBucketManager(SUPABASE_URL, SUPABASE_KEY)


class SupabaseBucketManager:
    """Manage Supabase storage buckets"""

    def __init__(self, url: str, key: str):
        """Initialize with service role key for admin operations"""
        self.supabase: Client = create_client(url, key)
        logfire.info(f"Connect to Supabase Successfully")

    def create_bucket(self, name: str, config: dict) -> dict:
        """Create a new storage bucket
           config example:
            {
            "public": config.get("public", False),
            "file_size_limit": config.get("file_size_limit", None),
            "allowed_mime_types": config.get("allowed_mime_types", None)
            }
        """
        try:
            self.supabase.storage.create_bucket(name, options=config)
            logfire.info(f"✅ Bucket '{name}' created with config: {config}")
        except Exception as e:
            logfire.info(f"❌ Error: {e}")
            return None

    def list_buckets(self) -> List[dict]:
        """List all storage buckets"""
        try:
            buckets = self.supabase.storage.list_buckets()
            return buckets
        except Exception as e:
            logfire.info(f"Error listing buckets: {e}")
            return []

    def get_bucket(self, name: str) -> Optional[dict]:
        """Get information about a specific bucket"""
        try:
            bucket = self.supabase.storage.get_bucket(name)
            return bucket
        except Exception as e:
            logfire.info(f"Error getting bucket: {e}")
            return None

    def update_bucket(self, name: str, public: bool = None,
                      file_size_limit: int = None,
                      allowed_mime_types: List[str] = None) -> dict:
        """Update bucket settings"""
        try:
            options = {}
            if public is not None:
                options["public"] = public
            if file_size_limit is not None:
                options["file_size_limit"] = file_size_limit
            if allowed_mime_types is not None:
                options["allowed_mime_types"] = allowed_mime_types

            result = self.supabase.storage.update_bucket(name, options=options)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_bucket(self, name: str) -> dict:
        """Delete a storage bucket (must be empty)"""
        try:
            result = self.supabase.storage.delete_bucket(name)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def empty_bucket(self, name: str) -> dict:
        """Empty all files from a bucket"""
        try:
            result = self.supabase.storage.empty_bucket(name)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
