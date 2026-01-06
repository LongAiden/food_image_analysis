"""Unit tests for DatabaseService.

CURRENT IMPLEMENTATION: Tests the actual DatabaseService in backend/services/supabase_service.py
Method name: get_statistic() (singular, not plural)

NOTE: This will be refactored to SupabaseFoodAnalysisRepository in Phase 2.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

from backend.services.supabase_service import DatabaseService


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
async def test_get_statistic_empty_database(database_service):
    """Test statistics with no data returns zeros."""
    # Arrange - Mock the database to return empty list
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        
        # Act
        result = await database_service.get_statistic(days=7)  # Note: singular in current code
    
    # Assert
    assert result["total_meals"] == 0
    assert result["avg_calories"] == 0
    assert result["avg_protein"] == 0
    assert "start_date" in result


@pytest.mark.unit
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
        result = await database_service.get_statistic(days=7)  # Note: singular in current code
    
    # Assert
    assert result["total_meals"] == 2
    # Average per day (2 meals over 7 days)
    assert result["avg_calories"] == round((500 + 300) / 7, 1)  # ~114.3
    assert result["avg_protein"] == round((30 + 20) / 7, 1)      # ~7.1
    assert result["avg_health_score"] == round((80 + 90) / 2, 1)  # 85.0


@pytest.mark.unit
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
        result = await database_service.get_statistic(days=7)  # Note: singular in current code
    
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


@pytest.mark.unit
async def test_get_analysis_by_id(database_service):
    """Test getting a specific analysis by ID."""
    # Arrange
    test_id = str(uuid4())
    sample_record = {
        "id": test_id,
        "image_path": "https://example.com/image.jpg",
        "raw_result": {"calories": 500, "protein": 30},
        "created_at": datetime.utcnow().isoformat()
    }

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([sample_record])
        result = await database_service.get_analysis(test_id)

    # Assert
    assert result is not None
    assert result["id"] == test_id
    assert "image_path" in result


@pytest.mark.unit
async def test_get_analysis_not_found(database_service):
    """Test getting analysis that doesn't exist."""
    # Arrange
    test_id = str(uuid4())

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_analysis(test_id)

    # Assert
    assert result is None


@pytest.mark.unit
async def test_get_recent_analyses(database_service):
    """Test getting recent analyses with limit."""
    # Arrange
    sample_records = [
        {
            "id": str(uuid4()),
            "image_path": "https://example.com/image1.jpg",
            "raw_result": {"calories": 500},
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "id": str(uuid4()),
            "image_path": "https://example.com/image2.jpg",
            "raw_result": {"calories": 300},
            "created_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
        }
    ]

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse(sample_records)
        result = await database_service.get_recent_analyses(limit=10)

    # Assert
    assert len(result) == 2
    assert all("image_path" in record for record in result)
    assert all("raw_result" in record for record in result)


@pytest.mark.unit
async def test_delete_analysis_success(database_service):
    """Test successful analysis deletion."""
    # Arrange
    test_id = uuid4()

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.delete_analysis(test_id)

    # Assert
    assert result is True
