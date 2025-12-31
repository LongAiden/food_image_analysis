from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
import logfire

from backend.models.models import NutritionAnalysis
from backend.services.gemini_analyzer import GeminiAnalyzer
from backend.services.image_utils import prepare_image
from backend.services.supabase_service import StorageService, DatabaseService


class AnalysisResult(BaseModel):
    """
    Data Transfer Object (DTO) for analysis results.

    This is a simple data class that carries data between layers.
    Unlike domain entities, it has no business logic.
    """
    analysis_id: UUID = Field(description="Unique analysis ID")
    food_name: str = Field(description="Food Name")
    nutrition: NutritionAnalysis = Field(description="Nutrition analysis results")
    image_url: str = Field(description="URL to stored image")
    timestamp: datetime = Field(description="Analysis timestamp")


class AnalysisService:
    """
    Service for analyzing food images.
    
    Design Patterns Applied:
    - Service Layer: Encapsulates business logic
    - Dependency Injection: Dependencies passed via constructor
    - Single Responsibility: Only handles analysis workflow
    
    This is a step toward Use Case pattern - it orchestrates
    the workflow but still depends on infrastructure (Supabase).
    In Phase 2, we'll refactor to use Repository pattern.
    """

    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        storage: StorageService,
        database: DatabaseService,
        max_image_size_mb: float
    ):
        """
        Initialize with dependencies (Dependency Injection pattern).
        
        Args:
            analyzer: AI service for food analysis
            storage: File storage service
            database: Database service
            max_image_size_mb: Maximum allowed image size
        """
        self.analyzer = analyzer
        self.storage = storage
        self.database = database
        self.max_image_size_mb = max_image_size_mb

    async def analyze_and_store(
        self,
        image_data: bytes,
        filename: str
    ) -> AnalysisResult:
        """
        Execute the complete food image analysis workflow.
        
        This method demonstrates the Template Method pattern:
        1. Validate input (prepare_image)
        2. Analyze (AI service)
        3. Store file (storage service)
        4. Store metadata (database service)
        5. Return result (DTO)
        
        This is reusable across:
        - REST API endpoints (/analyze, /analyze-base64)
        - Telegram bot
        - Future: CLI tool, batch processing, etc.
        
        Args:
            image_data: Raw image bytes
            filename: Original filename
            
        Returns:
            AnalysisResult with all data
            
        Raises:
            ValueError: If image is invalid or too large
            RuntimeError: If analysis or storage fails
        """
        logfire.info("Starting food image analysis", filename=filename)

        # Step 1: Validate and prepare image
        logfire.debug("Preparing image")
        prepared = prepare_image(
            image_data,
            max_size_mb=self.max_image_size_mb
        )

        # Step 2: Analyze with AI
        logfire.debug("Analyzing with Gemini AI")
        nutrition_analysis = await self.analyzer.analyze_image(
            prepared=prepared,
            filename=filename
        )

        # Step 3: Upload to storage
        logfire.debug("Uploading to storage")
        storage_result = await self.storage.upload_image(
            image_data=prepared.image_bytes,
            filename=filename,
            content_type=prepared.content_type,
        )

        # Step 4: Save to database
        logfire.debug("Saving to database")
        db_record = await self.database.save_analysis(
            image_path=storage_result["url"],
            nutrition=nutrition_analysis
        )

        logfire.info(
            "Analysis completed successfully",
            analysis_id=db_record["id"],
            food_name=nutrition_analysis.food_name
        )

        # Step 5: Return structured result
        return AnalysisResult(
            analysis_id=UUID(db_record["id"]),
            food_name=nutrition_analysis.food_name,
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"]
        )