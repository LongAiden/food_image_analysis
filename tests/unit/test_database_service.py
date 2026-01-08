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


@pytest.mark.unit
async def test_delete_analysis_failure(database_service):
    """Test deletion failure returns False."""
    # Arrange
    test_id = uuid4()

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = Exception("Database error")
        result = await database_service.delete_analysis(test_id)

    # Assert
    assert result is False


# ============================================================
# Edge Cases: get_statistic with invalid parameters
# ============================================================

@pytest.mark.unit
async def test_get_statistic_with_zero_days(database_service):
    """Test statistics with zero days."""
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_statistic(days=0)

    # Assert - Should handle zero days gracefully
    assert result["total_meals"] == 0
    assert "start_date" in result


@pytest.mark.unit
async def test_get_statistic_with_negative_days(database_service):
    """Test statistics with negative days (invalid input)."""
    # Note: The service doesn't validate negative days, but timedelta handles it
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_statistic(days=-7)

    # Assert - Should complete but with unusual date range
    assert result["total_meals"] == 0
    assert "start_date" in result


@pytest.mark.unit
async def test_get_statistic_with_very_large_days(database_service):
    """Test statistics with very large day count."""
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_statistic(days=36500)  # 100 years

    # Assert
    assert result["total_meals"] == 0
    assert "start_date" in result


@pytest.mark.unit
async def test_get_statistic_with_string_days(database_service):
    """Test statistics with invalid string input for days parameter."""
    # Act & Assert - Should raise TypeError when timedelta receives string
    with pytest.raises(TypeError):
        with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = MockSupabaseResponse([])
            await database_service.get_statistic(days="abc")


@pytest.mark.unit
async def test_get_statistic_with_float_days(database_service):
    """Test statistics with float input for days parameter."""
    # Act - Float should work (timedelta accepts float)
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_statistic(days=7.5)

    # Assert
    assert result["total_meals"] == 0
    assert "start_date" in result


@pytest.mark.unit
async def test_get_statistic_with_none_days(database_service):
    """Test statistics with None input for days parameter."""
    # Act & Assert - Should raise TypeError
    with pytest.raises(TypeError):
        with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = MockSupabaseResponse([])
            await database_service.get_statistic(days=None)


@pytest.mark.unit
async def test_get_statistic_with_partial_valid_records(database_service):
    """Test statistics with mix of valid and partial records."""
    # Arrange - Some records missing health_score
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
                "health_score": 0  # Zero health score
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
                "health_score": None  # None health score
            }
        }
    ]

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse(sample_records)
        result = await database_service.get_statistic(days=7)

    # Assert - Should handle zero/None health scores
    assert result["total_meals"] == 2
    assert result["avg_health_score"] == 0  # No valid health scores


# ============================================================
# Edge Cases: get_analysis with invalid parameters
# ============================================================

@pytest.mark.unit
async def test_get_analysis_with_exception(database_service):
    """Test get_analysis when database raises exception."""
    # Arrange
    test_id = uuid4()

    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = Exception("Database connection error")
        result = await database_service.get_analysis(test_id)

    # Assert - Should return None on exception
    assert result is None


# ============================================================
# Edge Cases: get_recent_analyses with invalid parameters
# ============================================================

@pytest.mark.unit
async def test_get_recent_analyses_with_zero_limit(database_service):
    """Test get_recent_analyses with zero limit."""
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_recent_analyses(limit=0)

    # Assert
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.unit
async def test_get_recent_analyses_with_negative_limit(database_service):
    """Test get_recent_analyses with negative limit."""
    # Note: Supabase will handle negative limits, but service doesn't validate
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_recent_analyses(limit=-10)

    # Assert - Should complete (Supabase handles it)
    assert isinstance(result, list)


@pytest.mark.unit
async def test_get_recent_analyses_with_very_large_limit(database_service):
    """Test get_recent_analyses with very large limit."""
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_recent_analyses(limit=10000)

    # Assert
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.unit
async def test_get_recent_analyses_empty_database(database_service):
    """Test get_recent_analyses with empty database."""
    # Act
    with patch.object(database_service, '_run_with_retry', new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = MockSupabaseResponse([])
        result = await database_service.get_recent_analyses(limit=10)

    # Assert
    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================
# Edge Cases: _extract_nutrition_from_raw with invalid inputs
# ============================================================

@pytest.mark.unit
def test_extract_nutrition_from_empty_dict(database_service):
    """Test extraction from empty dict uses all defaults."""
    # Arrange
    raw_result = {}

    # Act
    result = database_service._extract_nutrition_from_raw(raw_result)

    # Assert - All should be 0 (defaults)
    assert result["calories"] == 0
    assert result["protein"] == 0
    assert result["sugar"] == 0
    assert result["carbs"] == 0
    assert result["fat"] == 0
    assert result["fiber"] == 0
    assert result["health_score"] == 0


@pytest.mark.unit
def test_extract_nutrition_with_none_values(database_service):
    """Test extraction with None values."""
    # Arrange
    raw_result = {
        "calories": None,
        "protein": None,
        "sugar": 10,  # Some valid
        "carbs": None,
        "fat": None,
        "fiber": None,
        "health_score": None
    }

    # Act
    result = database_service._extract_nutrition_from_raw(raw_result)

    # Assert - None values should be returned as-is (get() returns None)
    assert result["calories"] is None
    assert result["sugar"] == 10
    assert result["health_score"] is None


@pytest.mark.unit
def test_extract_nutrition_with_string_values(database_service):
    """Test extraction with unexpected string values."""
    # Arrange
    raw_result = {
        "calories": "500",  # String instead of number
        "protein": "30",
        "sugar": 10,  # Correct
        "carbs": "fifty",  # Invalid string
        "fat": 20,  # Correct
        "fiber": "",  # Empty string
        "health_score": "high"  # Invalid string
    }

    # Act
    result = database_service._extract_nutrition_from_raw(raw_result)

    # Assert - Service doesn't validate, just extracts
    assert result["calories"] == "500"  # Returns as-is
    assert result["protein"] == "30"
    assert result["sugar"] == 10
    assert result["carbs"] == "fifty"
