import os
import logfire
from typing import Optional
from datetime import datetime
from uuid import uuid4
from supabase import Client, create_client


class StorageService:
    """Service for managing file uploads to Supabase Storage"""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None, bucket_name: Optional[str] = None):
        """Initialize Storage Service

        Args:
            url: Supabase project URL. If None, reads from SUPABASE_PROJECT_URL env var
            key: Supabase service key. If None, reads from SUPABASE_SERVICE_KEY env var
            bucket_name: Bucket name for storing images. If None, reads from SUPABASE_BUCKETS env var
        """
        self.url = url
        self.key = key
        self.bucket_name = bucket_name

        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY must be set")

        self.client: Client = create_client(self.url, self.key)

        logfire.info(
            f"✓ Storage Service initialized with bucket: {self.bucket_name}")

    def ensure_bucket_exists(self) -> bool:
        """Ensure the bucket exists, create if it doesn't

        Returns:
            True if bucket exists or was created successfully
        """
        try:
            # Try to get bucket
            bucket = self.client.storage.get_bucket(self.bucket_name)
            logfire.info(f"Bucket '{self.bucket_name}' exists")
            return True
        except Exception:
            # Bucket doesn't exist, create it
            try:
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={
                        "public": True,
                        "file_size_limit": 10485760,  # 10MB
                        "allowed_mime_types": ["image/jpeg", "image/png", "image/jpg", "image/webp", "image/gif"]
                    }
                )
                logfire.info(f"✓ Created bucket '{self.bucket_name}'")
                return True
            except Exception as e:
                logfire.error(f"Error creating bucket: {str(e)}")
                return False

    def upload_image(self, image_data: bytes, filename: Optional[str] = None,
                     content_type: str = "image/jpeg") -> dict:
        """Upload image to Supabase Storage

        Args:
            image_data: Raw image bytes
            filename: Original filename (optional)
            content_type: MIME type of the image

        Returns:
            Dict with 'path' and 'url' keys
        """
        try:
            # Ensure bucket exists
            self.ensure_bucket_exists()

            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid4())[:8]
            extension = self._get_extension(content_type, filename)
            storage_path = f"{timestamp}_{unique_id}{extension}"

            logfire.info(f"Uploading image to: {storage_path}")

            # Upload to Supabase
            self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=image_data,
                file_options={"content-type": content_type}
            )

            # Get public URL
            public_url = self.client.storage.from_(
                self.bucket_name).get_public_url(storage_path)

            logfire.info(f"✓ Image uploaded successfully: {storage_path}")

            return {
                "path": storage_path,
                "url": public_url,
                "bucket": self.bucket_name
            }

        except Exception as e:
            logfire.error(f"Error uploading image: {str(e)}")
            raise

    def delete_image(self, path: str) -> bool:
        """Delete image from storage
        Args:
            path: Storage path of the image

        Returns:
            True if deleted successfully
        """
        try:
            self.client.storage.from_(self.bucket_name).remove([path])
            logfire.info(f"✓ Deleted image: {path}")
            return True
        except Exception as e:
            logfire.error(f"Error deleting image {path}: {str(e)}")
            return False

    def get_image_url(self, path: str) -> str:
        """Get public URL for an image

        Args:
            path: Storage path of the image

        Returns:
            Public URL
        """
        return self.client.storage.from_(self.bucket_name).get_public_url(path)

    def list_images(self, limit: int = 100, offset: int = 0) -> list:
        """List images in the bucket

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of file objects
        """
        try:
            files = self.client.storage.from_(self.bucket_name).list()
            return files[offset:offset + limit]
        except Exception as e:
            logfire.error(f"Error listing images: {str(e)}")
            return []

    @staticmethod
    def _get_extension(content_type: str, filename: Optional[str] = None) -> str:
        """Get file extension from content type or filename

        Args:
            content_type: MIME type
            filename: Original filename

        Returns:
            File extension with dot (e.g., '.jpg')
        """
        if filename and '.' in filename:
            return '.' + filename.rsplit('.', 1)[1].lower()

        # Map content types to extensions
        extension_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif"
        }

        return extension_map.get(content_type, ".jpg")
