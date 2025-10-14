import logfire
from typing import Optional
from datetime import datetime
from uuid import uuid4, UUID
from supabase import Client, create_client
from backend.models.models import NutritionAnalysis
from typing import List, Optional

class DatabaseService:
    """Service for managing analysis records in Supabase database"""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None, table_name:Optional[str] = None):
        """Initialize Database Service

        Args:
            url: Supabase project URL. If None, reads from SUPABASE_PROJECT_URL env var
            key: Supabase service key. If None, reads from SUPABASE_SERVICE_KEY env var
        """
        self.url = url
        self.key = key

        if not self.url or not self.key:
            raise ValueError("SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY must be set")

        self.client: Client = create_client(self.url, self.key)
        self.table_name = table_name

        logfire.info(f"✓ Database Service initialized with table: {self.table_name}")

    async def create_table(self) -> bool:
        """Create the food_analyses table if it doesn't exist

        Note: This is best done via Supabase SQL Editor or migrations.
        This method provides the SQL schema for reference.

        SQL to run in Supabase SQL Editor:

        CREATE TABLE IF NOT EXISTS food_analyses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            image_path TEXT NOT NULL,
            calories FLOAT NOT NULL,
            sugar FLOAT NOT NULL,
            protein FLOAT NOT NULL,
            others TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Add index for faster queries
        CREATE INDEX IF NOT EXISTS idx_created_at ON food_analyses(created_at DESC);

        -- Enable Row Level Security (optional)
        ALTER TABLE food_analyses ENABLE ROW LEVEL SECURITY;

        -- Create policy to allow all operations (adjust for your security needs)
        CREATE POLICY "Allow all operations" ON food_analyses
        FOR ALL USING (true) WITH CHECK (true);
        """
        logfire.info("Table creation should be done via Supabase SQL Editor")
        return True

    async def save_analysis(self, image_path: str, nutrition: NutritionAnalysis,
                           analysis_id: Optional[UUID] = None) -> dict:
        """Save analysis record to database

        Args:
            image_path: Path/URL to stored image
            nutrition: Nutrition analysis data
            analysis_id: Optional custom UUID

        Returns:
            Saved record dict
        """
        try:
            record = {
                "image_path": image_path,
                "calories": nutrition.calories,
                "sugar": nutrition.sugar,
                "protein": nutrition.protein,
                "others": nutrition.others,
            }

            if analysis_id:
                record["id"] = str(analysis_id)

            logfire.info(f"Saving analysis to database: {record.get('id', 'new')}")

            response = self.client.table(self.table_name).insert(record).execute()

            logfire.info(f"✓ Analysis saved successfully")

            return response.data[0] if response.data else {}

        except Exception as e:
            logfire.error(f"Error saving analysis: {str(e)}")
            raise

    async def get_analysis(self, analysis_id: UUID) -> Optional[dict]:
        """Get analysis record by ID

        Args:
            analysis_id: UUID of the analysis

        Returns:
            Analysis record or None
        """
        try:
            response = self.client.table(self.table_name).select("*").eq("id", str(analysis_id)).execute()

            if response.data:
                return response.data[0]
            return None

        except Exception as e:
            logfire.error(f"Error fetching analysis {analysis_id}: {str(e)}")
            return None

    async def get_recent_analyses(self, limit: int = 10, offset: int = 0) -> List[dict]:
        """Get recent analysis records

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of analysis records
        """
        try:
            response = (
                self.client.table(self.table_name)
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            logfire.info(f"Retrieved {len(response.data)} analyses")

            return response.data

        except Exception as e:
            logfire.error(f"Error fetching recent analyses: {str(e)}")
            return []

    async def delete_analysis(self, analysis_id: UUID) -> bool:
        """Delete analysis record

        Args:
            analysis_id: UUID of the analysis to delete

        Returns:
            True if deleted successfully
        """
        try:
            self.client.table(self.table_name).delete().eq("id", str(analysis_id)).execute()
            logfire.info(f"✓ Deleted analysis: {analysis_id}")
            return True

        except Exception as e:
            logfire.error(f"Error deleting analysis {analysis_id}: {str(e)}")
            return False

    async def get_statistics(self) -> dict:
        """Get basic statistics about stored analyses

        Returns:
            Dict with statistics
        """
        try:
            # Get total count
            count_response = self.client.table(self.table_name).select("id", count="exact").execute()
            total_count = count_response.count if hasattr(count_response, 'count') else 0

            # Get average calories (example aggregation)
            # Note: For complex aggregations, you may want to use PostgreSQL functions or RPC
            recent_data = await self.get_recent_analyses(limit=100)

            avg_calories = sum(record['calories'] for record in recent_data) / len(recent_data) if recent_data else 0
            avg_protein = sum(record['protein'] for record in recent_data) / len(recent_data) if recent_data else 0
            avg_sugar = sum(record['sugar'] for record in recent_data) / len(recent_data) if recent_data else 0

            return {
                "total_analyses": total_count,
                "avg_calories": round(avg_calories, 2),
                "avg_protein": round(avg_protein, 2),
                "avg_sugar": round(avg_sugar, 2),
            }

        except Exception as e:
            logfire.error(f"Error calculating statistics: {str(e)}")
            return {
                "total_analyses": 0,
                "avg_calories": 0,
                "avg_protein": 0,
                "avg_sugar": 0,
            }


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

    def list_images(self, limit: int = 100, offset: int = 0) -> List:
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
