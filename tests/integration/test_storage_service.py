import pytest
from unittest.mock import Mock, AsyncMock, patch
from backend.services.supabase_service import StorageService


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client."""
    client = Mock()
    client.storage = Mock()
    return client


@pytest.fixture
def storage_service(mock_supabase_client):
    """Create storage service with mocked client."""
    with patch('backend.services.supabase_service.create_client', return_value=mock_supabase_client):
        service = StorageService(
            url="https://test.supabase.co",
            key="test_key",
            bucket_name="test-bucket"
        )
    return service


@pytest.mark.asyncio
async def test_upload_image_success(storage_service, mock_supabase_client):
    """Test successful image upload with mocked client."""
    # Arrange
    mock_bucket = Mock()
    mock_bucket.upload = Mock(return_value={"path": "test.png"})
    mock_supabase_client.storage.from_.return_value = mock_bucket
    
    # Act
    result = await storage_service.upload_image(
        image_data=b"fake_image",
        filename="test.png",
        content_type="image/png"
    )
    
    # Assert
    assert "url" in result
    assert "path" in result
    mock_bucket.upload.assert_called_once()


@pytest.mark.asyncio
async def test_delete_image_success(storage_service, mock_supabase_client):
    """Test successful image deletion."""
    # Arrange
    mock_bucket = Mock()
    mock_bucket.remove = Mock(return_value=None)
    mock_supabase_client.storage.from_.return_value = mock_bucket
    
    # Act
    result = await storage_service.delete_image("test.png")
    
    # Assert
    assert result == True
    mock_bucket.remove.assert_called_once()