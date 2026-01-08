import asyncio
from datetime import datetime
from typing import Callable, List, Optional, TypeVar
from uuid import UUID, uuid4

import logfire
from anyio import to_thread
from supabase import Client, create_client
from datetime import datetime, timedelta

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
                .select('id','image_path','raw_result','created_at','food_name')
                .eq("id", str(analysis_id))
                .execute()
            )
        except Exception as exc:
            logfire.error(f"Error fetching analysis {analysis_id}: {exc}")
            return None

        return response.data[0] if response.data else None
    
    async def get_recent_analyses(self, limit: int=10) -> List[dict]:
        '''Get recent analysis'''
        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name)
                        .select('id','image_path','raw_result','created_at')
                        .order('created_at',desc=True)
                        .limit(limit)
                        .execute()
        )
        return response.data
    

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

    def _extract_nutrition_from_raw(self, raw_result: dict) -> dict:
        """
        Extract nutrition data from raw_result. Exclude the case when there are no records
        """
        return {
            'calories': raw_result.get('calories', 0),
            'protein': raw_result.get('protein', 0),
            'sugar': raw_result.get('sugar', 0),
            'carbs': raw_result.get('carbs', 0),
            'fat': raw_result.get('fat', 0),
            'fiber': raw_result.get('fiber', 0),
            'health_score': raw_result.get('health_score', 0)
        }
    
    async def get_statistic(self, days: int=7):
        '''Get nutrition statistic'''
        start_date = datetime.utcnow() - timedelta(days=days)
        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name)
                        .select('id','created_at','raw_result')
                        .gte('created_at',start_date)
                        .execute()
        )

        analyses = response.data
        if not analyses:
            return {
                'start_date':start_date.isoformat(),
                "total_meals": 0,
                "avg_calories": 0,
                "avg_protein": 0,
                "avg_sugar": 0,
                "avg_carbs": 0,
                "avg_fat": 0,
                "avg_fiber": 0,
                "avg_health_score": 0
            }
        
        # Filter valid analyses
        valid_analyses = [
            a for a in analyses 
            if a.get('raw_result') and all(
                key in a['raw_result'] 
                for key in ['calories', 'protein', 'sugar', 'carbs', 'fat', 'fiber']
            )
        ]

        # Extract nutrition data
        nutrition_data = [
            self._extract_nutrition_from_raw(a['raw_result']) 
            for a in valid_analyses
        ]

        total_meals = len(valid_analyses)
        
        # Calculate totals (handle None values by treating them as 0)
        total_calories = sum(a.get('calories') or 0 for a in nutrition_data)
        total_protein = sum(a.get('protein') or 0 for a in nutrition_data)
        total_sugar = sum(a.get('sugar') or 0 for a in nutrition_data)
        total_carbs = sum(a.get('carbs') or 0 for a in nutrition_data)
        total_fat = sum(a.get('fat') or 0 for a in nutrition_data)
        total_fiber = sum(a.get('fiber') or 0 for a in nutrition_data)

        # Handle health_score separately (it's optional and can be None or 0)
        # Only include valid health scores (> 0) in the average
        valid_health_scores = [
            a['health_score'] for a in nutrition_data
            if a.get('health_score') is not None and a['health_score'] > 0
        ]
        avg_health_score = round(sum(valid_health_scores) / len(valid_health_scores), 1) if valid_health_scores else 0

        return {
            'start_date': start_date.isoformat(),
            "total_meals": total_meals,
            "avg_calories": round(total_calories / days, 1),
            "avg_protein": round(total_protein / days, 1),
            "avg_sugar": round(total_sugar / days, 1),
            "avg_carbs": round(total_carbs / days, 1),
            "avg_fat": round(total_fat / days, 1),
            "avg_fiber": round(total_fiber / days, 1),
            "avg_health_score": avg_health_score
        }

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
        # Validate image data is not empty
        if not image_data or len(image_data) == 0:
            raise ValueError("Image data cannot be empty")

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
            # First check if file exists by attempting to get its public URL info
            # If file doesn't exist, list operation will show it's not there
            result = await self._run_with_retry(
                lambda: self.client.storage.from_(self.bucket_name).list(path=path.rsplit('/', 1)[0] if '/' in path else '')
            )

            # Check if the file exists in the list
            file_exists = any(
                file.get('name') == (path.rsplit('/', 1)[-1] if '/' in path else path)
                for file in result
            )

            if not file_exists:
                logfire.warning(f"Image does not exist: {path}")
                return False

            # File exists, proceed with deletion
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
