"""Integration tests for DatabaseService.

Uses real Supabase database with test table from Settings.
"""

import pytest
import random
from backend.services.supabase_service import DatabaseService
from backend.config import Settings


# Load settings at module level for test verification
settings = Settings()


@pytest.fixture
def database_service():
    """Create DatabaseService with REAL test database connection.

    Uses test table from Settings to keep test data isolated.
    """
    test_settings = Settings()  # Load from .env
    return DatabaseService(
        url=test_settings.supabase_url,
        key=test_settings.supabase_service_key,
        table_name=test_settings.supabase_table_test  # ← Use TEST table!
    )


@pytest.mark.integration
def test_database_service_uses_test_table(database_service):
    """Verify database service is using test table from Settings."""
    assert database_service.table_name == settings.supabase_table_test
    assert "test" in database_service.table_name.lower(), \
        "Database service should use test table for integration tests"


@pytest.mark.integration
async def test_save_and_retrieve_real_analysis(database_service):
    """Test real database save and retrieve."""
    from backend.models.models import NutritionAnalysis
    from uuid import uuid4
    
    # Arrange
    test_id = uuid4()
    nutrition = NutritionAnalysis(
        food_name="Test Apple",
        calories=random.uniform(0, 1000.0),
        protein=random.uniform(0, 1000.0),
        sugar=random.uniform(0, 1000.0),
        carbs=random.uniform(0, 1000.0),
        fat=random.uniform(0, 1000.0),
        fiber=random.uniform(0, 1000.0),
        health_score=random.randint(0, 1000),
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


@pytest.mark.integration
async def test_get_nonexistent_analysis(database_service):
    """Test retrieving an analysis that doesn't exist."""
    from uuid import uuid4

    # Arrange - Use a UUID that doesn't exist in database
    nonexistent_id = uuid4()

    # Act
    result = await database_service.get_analysis(nonexistent_id)

    # Assert - Should return None or handle gracefully
    assert result is None


@pytest.mark.integration
async def test_get_statistics_with_edge_case_days(database_service):
    """Test statistics with edge case day parameters."""

    # Test with 0 days
    stats_zero = await database_service.get_statistic(days=0)
    assert "total_meals" in stats_zero
    assert "avg_calories" in stats_zero
    assert stats_zero["total_meals"] >= 0

    # Test with 1 day (boundary)
    stats_one = await database_service.get_statistic(days=1)
    assert "total_meals" in stats_one
    assert stats_one["total_meals"] >= 0

    # Test with very large number of days
    stats_large = await database_service.get_statistic(days=36500)  # 100 years
    assert "total_meals" in stats_large
    assert stats_large["total_meals"] >= 0


@pytest.mark.integration
async def test_save_analysis_with_extreme_values(database_service):
    """Test saving and retrieving analysis with extreme/boundary nutritional values."""
    from backend.models.models import NutritionAnalysis
    from uuid import uuid4

    # Arrange - Test with zero values and very long strings
    test_id = uuid4()
    nutrition = NutritionAnalysis(
        food_name="Test Food With Very Long Name " * 10,  # Long name
        calories=0.0,  # Zero calories
        protein=0.0,
        sugar=0.0,
        carbs=0.0,
        fat=0.0,
        fiber=0.0,
        health_score=0,  # Minimum score
        others="A" * 5000  # Very long text
    )

    # Act - Save to database
    await database_service.save_analysis(
        image_path="https://example.com/extreme.jpg",
        nutrition=nutrition,
        analysis_id=test_id
    )

    # Assert - Retrieve and verify data integrity
    retrieved = await database_service.get_analysis(test_id)
    assert retrieved is not None
    assert retrieved['raw_result']["calories"] == 0.0
    assert retrieved['raw_result']["health_score"] == 0
    assert len(retrieved['raw_result']["others"]) > 0  # Verify long text was saved

    # Cleanup
    await database_service.delete_analysis(test_id)
