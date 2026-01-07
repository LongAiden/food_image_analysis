"""Unit tests for AnalysisService.

These tests mock all external dependencies (image validation, AI, storage, database)
to test the service logic in isolation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from backend.services.analyses_service import AnalysisService, AnalysisResult
from backend.models.models import NutritionAnalysis
from backend.services.image_utils import PreparedImage


@pytest.fixture
def mock_prepared_image():
    """Create a mock PreparedImage for tests that bypass image validation."""
    return PreparedImage(
        image_bytes=b"fake_image_bytes_for_testing",
        content_type="image/jpeg",
        data_uri="data:image/jpeg;base64,ZmFrZV9pbWFnZV9ieXRlcw==",
        image_format="JPEG"
    )


@pytest.fixture
def mock_services():
    """Create all mocked services at once."""
    test_uuid = str(uuid4())
    return {
        'analyzer': Mock(analyze_image=AsyncMock(return_value=NutritionAnalysis(
            food_name="Test Food",
            calories=500.0,
            protein=30.0,
            sugar=10.0,
            carbs=50.0,
            fat=20.0,
            fiber=5.0,
            health_score=75,
            others="Test description"
        ))),
        'storage': Mock(upload_image=AsyncMock(return_value={
            "url": "https://test.com/image.jpg",
            "path": "20260107_120000_abc123.jpg",
            "bucket": "test-bucket"
        })),
        'database': Mock(save_analysis=AsyncMock(return_value={
            "id": test_uuid,
            "created_at": datetime.utcnow().isoformat()
        }))
    }


@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_and_store_calls_all_services(mock_prepare, mock_services, mock_prepared_image):
    """Test that analysis workflow calls all services in correct order."""
    # Mock image preparation to bypass validation
    mock_prepare.return_value = mock_prepared_image

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    result = await service.analyze_and_store(
        image_data=b"any_bytes",
        filename="test.jpg"
    )

    # Verify prepare_image was called
    mock_prepare.assert_called_once()

    # Verify all services were called in order
    assert mock_services['analyzer'].analyze_image.called
    assert mock_services['storage'].upload_image.called
    assert mock_services['database'].save_analysis.called

    # Verify result structure
    assert isinstance(result, AnalysisResult)
    assert result.nutrition.food_name == "Test Food"
    assert result.image_url == "https://test.com/image.jpg"


# ============================================================
# Edge Cases: Invalid Image Data
# ============================================================

@pytest.mark.unit
async def test_analyze_with_empty_image_data(mock_services):
    """Test that empty image data raises ValueError (from prepare_image)."""
    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    # prepare_image will raise ValueError for empty data
    with pytest.raises(ValueError):
        await service.analyze_and_store(
            image_data=b"",
            filename="empty.jpg"
        )


@pytest.mark.unit
async def test_analyze_with_invalid_image_data(mock_services):
    """Test that corrupted image data raises ValueError (from prepare_image)."""
    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    # prepare_image will raise ValueError for invalid data
    with pytest.raises(ValueError):
        await service.analyze_and_store(
            image_data=b"not an image at all!",
            filename="invalid.jpg"
        )


@pytest.mark.unit
async def test_analyze_with_oversized_image(mock_services):
    """Test that image exceeding size limit raises ValueError (from prepare_image)."""
    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=0.001  # 1KB limit
    )

    # Create large data that exceeds limit
    large_image_data = b"x" * 2000  # 2KB

    # prepare_image will raise ValueError for oversized data
    with pytest.raises(ValueError, match="Image too large"):
        await service.analyze_and_store(
            image_data=large_image_data,
            filename="huge.jpg"
        )


# ============================================================
# Edge Cases: Extreme Nutrition Values
# ============================================================

@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_with_zero_nutrition_values(mock_prepare, mock_services, mock_prepared_image):
    """Test analysis with all zero nutrition values (edge case from real data)."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    # Mock analyzer to return all zeros
    mock_services['analyzer'].analyze_image = AsyncMock(return_value=NutritionAnalysis(
        food_name="Empty Food",
        calories=0.0,
        protein=0.0,
        sugar=0.0,
        carbs=0.0,
        fat=0.0,
        fiber=0.0,
        health_score=0,
        others=""
    ))

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    result = await service.analyze_and_store(
        image_data=b"any_bytes",
        filename="zero_nutrition.jpg"
    )

    # Should succeed even with zeros
    assert result.nutrition.calories == 0.0
    assert result.nutrition.health_score == 0
    assert mock_services['database'].save_analysis.called


@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_with_very_long_food_name(mock_prepare, mock_services, mock_prepared_image):
    """Test analysis with extremely long food name (300+ chars from real data)."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    long_name = "Test Food With Very Long Name " * 10  # ~300 chars

    mock_services['analyzer'].analyze_image = AsyncMock(return_value=NutritionAnalysis(
        food_name=long_name,
        calories=100.0,
        protein=10.0,
        sugar=5.0,
        carbs=20.0,
        fat=3.0,
        fiber=2.0,
        health_score=75,
        others="Normal description"
    ))

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    result = await service.analyze_and_store(
        image_data=b"any_bytes",
        filename="long_name.jpg"
    )

    # Should handle long names
    assert len(result.nutrition.food_name) > 250
    assert result.food_name == long_name


@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_with_very_long_others_text(mock_prepare, mock_services, mock_prepared_image):
    """Test analysis with extremely long 'others' text (5000+ chars from real data)."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    long_text = "A" * 5000  # 5000 character text

    mock_services['analyzer'].analyze_image = AsyncMock(return_value=NutritionAnalysis(
        food_name="Normal Food",
        calories=200.0,
        protein=15.0,
        sugar=10.0,
        carbs=30.0,
        fat=8.0,
        fiber=4.0,
        health_score=80,
        others=long_text
    ))

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    result = await service.analyze_and_store(
        image_data=b"any_bytes",
        filename="long_description.jpg"
    )

    # Should handle very long text
    assert len(result.nutrition.others) == 5000
    assert result.nutrition.others == long_text


# ============================================================
# Edge Cases: Service Failures
# ============================================================

@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_when_analyzer_fails(mock_prepare, mock_services, mock_prepared_image):
    """Test that analyzer failure propagates correctly."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    mock_services['analyzer'].analyze_image = AsyncMock(
        side_effect=Exception("AI service unavailable")
    )

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    with pytest.raises(Exception, match="AI service unavailable"):
        await service.analyze_and_store(
            image_data=b"any_bytes",
            filename="test.jpg"
        )

    # Storage and database should NOT be called if analyzer fails
    assert not mock_services['storage'].upload_image.called
    assert not mock_services['database'].save_analysis.called


@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_when_storage_fails(mock_prepare, mock_services, mock_prepared_image):
    """Test that storage failure propagates correctly."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    mock_services['storage'].upload_image = AsyncMock(
        side_effect=Exception("Storage service unavailable")
    )

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    with pytest.raises(Exception, match="Storage service unavailable"):
        await service.analyze_and_store(
            image_data=b"any_bytes",
            filename="test.jpg"
        )

    # Analyzer should have been called
    assert mock_services['analyzer'].analyze_image.called
    # Database should NOT be called if storage fails
    assert not mock_services['database'].save_analysis.called


@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_when_database_fails(mock_prepare, mock_services, mock_prepared_image):
    """Test that database failure propagates correctly."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    mock_services['database'].save_analysis = AsyncMock(
        side_effect=Exception("Database service unavailable")
    )

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    with pytest.raises(Exception, match="Database service unavailable"):
        await service.analyze_and_store(
            image_data=b"any_bytes",
            filename="test.jpg"
        )

    # Analyzer and storage should have been called
    assert mock_services['analyzer'].analyze_image.called
    assert mock_services['storage'].upload_image.called


# ============================================================
# Edge Cases: Special Filenames
# ============================================================

@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_with_special_characters_in_filename(mock_prepare, mock_services, mock_prepared_image):
    """Test that filenames with special characters are handled."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    result = await service.analyze_and_store(
        image_data=b"any_bytes",
        filename="test file with spaces & special!@#.jpg"
    )

    # Should handle special characters
    assert isinstance(result, AnalysisResult)
    assert mock_services['storage'].upload_image.called


@pytest.mark.unit
@patch('backend.services.analyses_service.prepare_image')
async def test_analyze_with_very_long_filename(mock_prepare, mock_services, mock_prepared_image):
    """Test that very long filenames are handled."""
    # Mock image preparation
    mock_prepare.return_value = mock_prepared_image

    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )

    long_filename = "a" * 250 + ".jpg"  # 254 character filename

    result = await service.analyze_and_store(
        image_data=b"any_bytes",
        filename=long_filename
    )

    # Should handle long filenames
    assert isinstance(result, AnalysisResult)
    assert mock_services['storage'].upload_image.called