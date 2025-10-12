import os
import logfire
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from supabase import Client, create_client

from backend.models.models import NutritionAnalysis


class DatabaseService:
    """Service for managing analysis records in Supabase database"""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
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
        self.table_name = "food_analyses"

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
