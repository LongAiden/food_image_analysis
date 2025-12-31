"""Unit tests for DatabaseService."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from backend.services.supabase_service import DatabaseService
from tests.fixtures.sample_data import SAMPLE_NUTRITION, SAMPLE_DB_RECORD


class MockSupabaseResponse:
    """Mock Supabase response object."""
    def __init__(self, data):
        self.data = data


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with all necessary methods."""
    client = MagicMock()
    # Mock the table() chain
    table_mock = MagicMock()
    client.table.return_value = table_mock
    return client


@pytest.fixture
def database_service(mock_supabase_client):
    """
    Create DatabaseService with mocked Supabase client.
    
    IMPORTANT: We patch create_client BEFORE creating the service
    so it never tries to connect to real Supabase.
    """
    # Patch create_client to return our mock
    with patch('backend.services.supabase_service.create_client', return_value=mock_supabase_client):
        service = DatabaseService(
            url="https://test.supabase.co",
            key="test_key",
            table_name="food_analyses"
        )
    return service


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_statistic_empty_database(database_service):
    """Test statistics with no data returns zeros."""
    # Arrange - Mock the database to return empty list
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        
        # Act
        result = await database_service.get_statistic(days=7)
    
    # Assert
    assert result["total_meals"] == 0
    assert result["avg_calories"] == 0
    assert result["avg_protein"] == 0
    assert "start_date" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_statistic_with_valid_data(database_service):
    """Test statistics calculation with valid data."""
    # Arrange
    sample_records = [
        {
            "id": "1",
            "created_at": datetime.utcnow().isoformat(),
            "raw_result": {
                "calories": 500,
                "protein": 30,
                "sugar": 10,
                "carbs": 50,
                "fat": 20,
                "fiber": 5,
                "health_score": 80
            }
        },
        {
            "id": "2",
            "created_at": datetime.utcnow().isoformat(),
            "raw_result": {
                "calories": 300,
                "protein": 20,
                "sugar": 5,
                "carbs": 30,
                "fat": 10,
                "fiber": 3,
                "health_score": 90
            }
        }
    ]
    
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse(sample_records)
        result = await database_service.get_statistic(days=7)
    
    # Assert
    assert result["total_meals"] == 2
    # Average per day (2 meals over 7 days)
    assert result["avg_calories"] == round((500 + 300) / 7, 1)  # ~114.3
    assert result["avg_protein"] == round((30 + 20) / 7, 1)      # ~7.1
    assert result["avg_health_score"] == round((80 + 90) / 2, 1)  # 85.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_statistic_filters_invalid_records(database_service):
    """Test that invalid records are filtered out."""
    # Arrange
    sample_records = [
        {
            "id": "1",
            "created_at": datetime.utcnow().isoformat(),
            "raw_result": {
                "calories": 500,
                "protein": 30,
                "sugar": 10,
                "carbs": 50,
                "fat": 20,
                "fiber": 5,
                "health_score": 80
            }
        },
        {
            "id": "2",
            "created_at": datetime.utcnow().isoformat(),
            "raw_result": None  # Invalid - should be filtered out
        },
        {
            "id": "3",
            "created_at": datetime.utcnow().isoformat(),
            "raw_result": {
                "calories": 300,
                # Missing required fields - should be filtered out
            }
        }
    ]
    
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse(sample_records)
        result = await database_service.get_statistic(days=7)
    
    # Assert - Only 1 valid record should be counted
    assert result["total_meals"] == 1
    assert result["avg_calories"] == round(500 / 7, 1)


@pytest.mark.unit
def test_extract_nutrition_from_raw(database_service):
    """Test nutrition data extraction helper."""
    # Arrange
    raw_result = {
        "calories": 400,
        "protein": 25,
        "sugar": 12,
        "carbs": 45,
        "fat": 15,
        "fiber": 6,
        "health_score": 75
    }
    
    # Act
    result = database_service._extract_nutrition_from_raw(raw_result)
    
    # Assert
    assert result["calories"] == 400
    assert result["protein"] == 25
    assert result["health_score"] == 75


@pytest.mark.unit
def test_extract_nutrition_handles_missing_fields(database_service):
    """Test extraction with missing fields uses defaults."""
    # Arrange
    raw_result = {
        "calories": 400,
        # Other fields missing
    }
    
    # Act
    result = database_service._extract_nutrition_from_raw(raw_result)
    
    # Assert
    assert result["calories"] == 400
    assert result["protein"] == 0  # Default
    assert result["sugar"] == 0     # Default
