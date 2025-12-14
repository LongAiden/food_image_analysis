import asyncio
from datetime import datetime
from typing import Callable, List, Optional, TypeVar
from uuid import UUID, uuid4

import logfire
from anyio import to_thread
from supabase import Client, create_client

from backend.models.models import NutritionAnalysis

T = TypeVar("T")


class _BaseSupabaseService:
    """Helper mixin to run blocking Supabase calls safely."""

    async def _run_with_retry(self, func: Callable[[], T], retries: int = 2) -> T:
        delay = 0.2
        last_exc: Optional[Exception] = None
        for _ in range(retries + 1):
            try:
                return await to_thread.run_sync(func)
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(delay)
                delay *= 2
        assert last_exc is not None
        raise last_exc


class DatabaseService(_BaseSupabaseService):
    """Service for managing analysis records in Supabase database."""

    def __init__(
        self, url: Optional[str] = None, key: Optional[str] = None, table_name: Optional[str] = None
    ):
        if not url or not key:
            raise ValueError("SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY must be set")

        self.client: Client = create_client(url, key)
        self.table_name = table_name

        logfire.info("Database Service initialized", table=self.table_name)

    async def save_analysis(
        self, image_path: str, nutrition: NutritionAnalysis, analysis_id: Optional[UUID] = None
    ) -> dict:
        record = {
            "image_path": image_path,
            "food_name": nutrition.food_name,
            "calories": nutrition.calories,
            "sugar": nutrition.sugar,
            "protein": nutrition.protein,
            "carbs": nutrition.carbs,
            "fat": nutrition.fat,
            "fiber": nutrition.fiber,
            "others": nutrition.others,
            "health_score": nutrition.health_score,
            "raw_result": nutrition.model_dump(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        if analysis_id:
            record["id"] = str(analysis_id)

        logfire.debug("Saving analysis record")

        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name).insert(record).execute()
        )
        if not response.data:
            raise RuntimeError("Failed to save analysis")
        return response.data[0]

    async def get_analysis(self, analysis_id: UUID) -> Optional[dict]:
        try:
            response = await self._run_with_retry(
                lambda: self.client.table(self.table_name)
                .select("*")
                .eq("id", str(analysis_id))
                .execute()
            )
        except Exception as exc:
            logfire.error(f"Error fetching analysis {analysis_id}: {exc}")
            return None

        return response.data[0] if response.data else None

    async def delete_analysis(self, analysis_id: UUID) -> bool:
        try:
            await self._run_with_retry(
                lambda: self.client.table(self.table_name).delete().eq("id", str(analysis_id)).execute()
            )
            logfire.info("Deleted analysis", id=str(analysis_id))
            return True
        except Exception as exc:
            logfire.error(f"Error deleting analysis {analysis_id}: {exc}")
            return False


class StorageService(_BaseSupabaseService):
    """Service for managing file uploads to Supabase Storage."""

    def __init__(
        self, url: Optional[str] = None, key: Optional[str] = None, bucket_name: Optional[str] = None
    ):
        if not url or not key:
            raise ValueError("SUPABASE_PROJECT_URL and SUPABASE_SERVICE_KEY must be set")

        self.bucket_name = bucket_name
        self.client: Client = create_client(url, key)

        logfire.info("Storage Service initialized", bucket=self.bucket_name)

    async def ensure_bucket_exists(self) -> bool:
        try:
            await self._run_with_retry(lambda: self.client.storage.get_bucket(self.bucket_name))
            logfire.debug(f"Bucket '{self.bucket_name}' exists")
            return True
        except Exception:
            try:
                await self._run_with_retry(
                    lambda: self.client.storage.create_bucket(
                        self.bucket_name,
                        options={
                            "public": True,
                            "file_size_limit": 10485760,  # 10MB
                            "allowed_mime_types": [
                                "image/jpeg",
                                "image/png",
                                "image/jpg",
                                "image/webp",
                                "image/gif",
                            ],
                        },
                    )
                )
                logfire.info("Created bucket", bucket=self.bucket_name)
                return True
            except Exception as exc:
                logfire.error(f"Error creating bucket: {exc}")
                return False

    async def upload_image(
        self, image_data: bytes, filename: Optional[str] = None, content_type: str = "image/jpeg"
    ) -> dict:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid4())[:8]
        extension = self._get_extension(content_type, filename)
        storage_path = f"{timestamp}_{unique_id}{extension}"

        logfire.debug("Uploading image", path=storage_path)

        await self._run_with_retry(
            lambda: self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=image_data,
                file_options={"content-type": content_type},
            )
        )

        public_url = self.client.storage.from_(self.bucket_name).get_public_url(storage_path)

        logfire.info("Image uploaded", path=storage_path)

        return {"path": storage_path, "url": public_url, "bucket": self.bucket_name}

    async def delete_image(self, path: str) -> bool:
        try:
            await self._run_with_retry(lambda: self.client.storage.from_(self.bucket_name).remove([path]))
            logfire.info("Deleted image", path=path)
            return True
        except Exception as exc:
            logfire.error(f"Error deleting image {path}: {exc}")
            return False

    @staticmethod
    def _get_extension(content_type: str, filename: Optional[str] = None) -> str:
        if filename and "." in filename:
            return "." + filename.rsplit(".", 1)[1].lower()

        extension_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return extension_map.get(content_type, ".jpg")
