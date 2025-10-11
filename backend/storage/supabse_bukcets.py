import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize client
SUPABASE_URL = os.getenv('SUPABASE_PROJECT_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_advanced_bucket(bucket_name: str, config: dict):
    """
    Create a bucket with advanced configuration

    Args:
        bucket_name: Name of the bucket
        config: Configuration dictionary with options
    """
    try:
        bucket = supabase.storage.create_bucket(
            bucket_name,
            options={
                "public": config.get("public", False),
                "file_size_limit": config.get("file_size_limit", None),
                "allowed_mime_types": config.get("allowed_mime_types", None)
            }
        )
        print(f"✅ Bucket '{bucket_name}' created with config: {config}")
        return bucket
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


# Example configurations
image_bucket_config = {
    "public": True,
    "file_size_limit": 10485760,  # 10MB
    "allowed_mime_types": ["image/jpeg", "image/png", "image/gif", "image/webp"]
}

document_bucket_config = {
    "public": False,
    "file_size_limit": 52428800,  # 50MB
    "allowed_mime_types": ["application/pdf", "application/msword"]
}

video_bucket_config = {
    "public": True,
    "file_size_limit": 104857600,  # 100MB
    "allowed_mime_types": ["video/mp4", "video/webm"]
}

# Create buckets
create_advanced_bucket("images", image_bucket_config)
create_advanced_bucket("documents", document_bucket_config)
create_advanced_bucket("videos", video_bucket_config)
