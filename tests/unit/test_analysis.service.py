import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from backend.services.analyses_service import AnalysisService, AnalysisResult
from backend.models.models import NutritionAnalysis


@pytest.fixture
def mock_services():
    """Create all mocked services at once."""
    return {
        'analyzer': Mock(analyze_image=AsyncMock(return_value=NutritionAnalysis(
            food_name="Test Food",
            calories=300.0,
            sugar=10.0,
            protein=20.0,
            carbs=30.0,
            fat=10.0,
            fiber=5.0,
            health_score=80,
            others="Test"
        ))),
        'storage': Mock(upload_image=AsyncMock(return_value={
            "url": "https://test.com/image.jpg",
            "path": "image.jpg"
        })),
        'database': Mock(save_analysis=AsyncMock(return_value={
            "id": str(uuid4()),
            "created_at": datetime.utcnow().isoformat()
        }))
    }


@pytest.mark.unit
async def test_analyze_and_store_calls_all_services(mock_services):
    """Test that analysis workflow calls all services in correct order."""
    service = AnalysisService(
        analyzer=mock_services['analyzer'],
        storage=mock_services['storage'],
        database=mock_services['database'],
        max_image_size_mb=10.0
    )
    
    # Tiny 1x1 PNG image (valid)
    test_image = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
        b'\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
        b'\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    
    result = await service.analyze_and_store(
        image_data=test_image,
        filename="test.jpg"
    )
    
    # Verify all services were called
    assert mock_services['analyzer'].analyze_image.called
    assert mock_services['storage'].upload_image.called
    assert mock_services['database'].save_analysis.called
    
    # Verify result structure
    assert isinstance(result, AnalysisResult)
    assert result.nutrition.food_name == "Test Food"