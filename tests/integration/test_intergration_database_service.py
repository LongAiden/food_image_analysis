"""Integration tests for DatabaseService.
"""

import pytest
from backend.services.supabase_service import DatabaseService
from backend.config import Settings


@pytest.fixture
def database_service():
    """Create DatabaseService with REAL test database connection."""
    settings = Settings()  # Load from .env
    return DatabaseService(
        url=settings.supabase_url,
        key=settings.supabase_service_key,
        table_name=settings.supabase_table_test  # ← Use TEST table!
    )


@pytest.mark.integration  # ← Mark as integration
async def test_save_and_retrieve_real_analysis(database_service):
    """Test real database save and retrieve."""
    from backend.models.models import NutritionAnalysis
    from uuid import uuid4
    
    # Arrange
    test_id = uuid4()
    nutrition = NutritionAnalysis(
        food_name="Test Apple",
        calories=95.0,
        protein=0.5,
        sugar=19.0,
        carbs=25.0,
        fat=0.3,
        fiber=4.0,
        health_score=85,
        others=""
    )
    
    # Act - Save to REAL database
    await database_service.save_analysis(
        image_path="https://example.com/test.jpg",
        nutrition=nutrition,
        analysis_id=test_id
    )
    
    # Assert - Retrieve from REAL database
    retrieved = await database_service.get_analysis(test_id)
    assert retrieved is not None
    assert retrieved["food_name"] == "Test Apple"
    
    # Cleanup - Delete test record
    await database_service.delete_analysis(test_id)


@pytest.mark.integration
async def test_get_statistics_real_data(database_service):
    """Test statistics with real database data."""
    # This queries the REAL test database
    stats = await database_service.get_statistic(days=30)
    
    # Assert structure is correct
    assert "total_meals" in stats
    assert "avg_calories" in stats
    assert stats["total_meals"] >= 0  # Could be 0 or more
