"""Integration tests for StorageService with real Supabase storage.

These tests use actual test images and real Supabase storage operations.
Test image: tests/test_image/image_test.png
"""

import pytest
from pathlib import Path
from backend.services.supabase_service import StorageService
from backend.config import Settings


# Load settings at module level for test verification
settings = Settings()

# Test image paths - Using real test image from tests/test_image/
TEST_IMAGE_DIR = Path(__file__).parent.parent / "test_image"
TEST_IMAGE_PNG = TEST_IMAGE_DIR / "image_test.png"


@pytest.fixture
def storage_service():
    """Create StorageService with REAL test storage connection.

    Uses test bucket from Settings to keep test data isolated.
    """
    test_settings = Settings()  # Load from .env
    return StorageService(
        url=test_settings.supabase_url,
        key=test_settings.supabase_service_key,
        bucket_name=test_settings.supabase_bucket_test  # ← Use TEST bucket!
    )


@pytest.fixture
def test_image_data():
    """Load test image data from tests/test_image/image_test.png."""
    if not TEST_IMAGE_PNG.exists():
        raise FileNotFoundError(f"Test image not found: {TEST_IMAGE_PNG}")

    with open(TEST_IMAGE_PNG, "rb") as f:
        return f.read()


@pytest.mark.integration
def test_test_image_exists():
    """Verify test image file exists before running storage tests."""
    assert TEST_IMAGE_PNG.exists(), f"Test image not found at {TEST_IMAGE_PNG}"
    assert TEST_IMAGE_PNG.stat().st_size > 0, "Test image is empty"


@pytest.mark.integration
async def test_ensure_bucket_exists(storage_service):
    """Test that bucket exists or can be created."""
    # Act
    result = await storage_service.ensure_bucket_exists()

    # Assert
    assert result is True
    # Verify we're using the test bucket from Settings
    assert storage_service.bucket_name == settings.supabase_bucket_test


@pytest.mark.integration
async def test_upload_image_success(storage_service, test_image_data):
    """Test successful image upload with real test image."""
    # Act
    result = await storage_service.upload_image(
        image_data=test_image_data,
        filename="image_test.png",
        content_type="image/png"
    )

    # Assert
    assert "url" in result
    assert "path" in result
    assert "bucket" in result
    assert result["path"].endswith(".png")
    assert settings.supabase_bucket_test in result["url"] or result["bucket"] == settings.supabase_bucket_test

    # Cleanup
    await storage_service.delete_image(result["path"])


@pytest.mark.integration
async def test_upload_and_delete_workflow(storage_service, test_image_data):
    """Test complete upload and delete workflow."""
    # Act - Upload
    upload_result = await storage_service.upload_image(
        image_data=test_image_data,
        filename="workflow_test.png",
        content_type="image/png"
    )

    assert "path" in upload_result
    stored_path = upload_result["path"]

    # Act - Delete
    delete_result = await storage_service.delete_image(stored_path)

    # Assert
    assert delete_result is True


@pytest.mark.integration
async def test_delete_nonexistent_image(storage_service):
    """Test deleting an image that doesn't exist."""
    # Act
    result = await storage_service.delete_image("nonexistent_12345.png")

    # Assert - Should return False or handle gracefully
    assert result is False


@pytest.mark.integration
async def test_upload_different_image_formats(storage_service, test_image_data):
    """Test uploading images with different content types."""
    test_cases = [
        ("image/png", ".png"),
        ("image/jpeg", ".jpg"),
        ("image/jpg", ".jpg"),
        ("image/webp", ".webp"),
        ("image/gif", ".gif"),
    ]

    uploaded_paths = []

    for content_type, expected_ext in test_cases:
        # Act
        result = await storage_service.upload_image(
            image_data=test_image_data,
            filename=f"test{expected_ext}",
            content_type=content_type
        )

        # Assert
        assert result["path"].endswith(expected_ext)
        uploaded_paths.append(result["path"])

    # Cleanup
    for path in uploaded_paths:
        await storage_service.delete_image(path)


@pytest.mark.integration
async def test_upload_without_filename(storage_service, test_image_data):
    """Test uploading image without providing filename (should auto-generate)."""
    # Act
    result = await storage_service.upload_image(
        image_data=test_image_data,
        content_type="image/jpeg"
    )

    # Assert
    assert "path" in result
    assert result["path"].endswith(".jpg")  # Default for jpeg
    assert len(result["path"]) > 10  # Should have timestamp and UUID

    # Cleanup
    await storage_service.delete_image(result["path"])


@pytest.mark.integration
async def test_upload_filename_with_special_characters(storage_service, test_image_data):
    """Test uploading with special characters in filename."""
    # Note: The service generates its own filename, so special chars are handled
    # Act
    result = await storage_service.upload_image(
        image_data=test_image_data,
        filename="test file with spaces & special!@#.png",
        content_type="image/png"
    )

    # Assert - Service should generate safe filename
    assert "path" in result
    assert result["path"].endswith(".png")

    # Cleanup
    await storage_service.delete_image(result["path"])


@pytest.mark.integration
async def test_upload_very_long_filename(storage_service, test_image_data):
    """Test uploading with very long filename."""
    long_filename = "a" * 200 + ".png"

    # Act
    result = await storage_service.upload_image(
        image_data=test_image_data,
        filename=long_filename,
        content_type="image/png"
    )

    # Assert
    assert "path" in result
    # Service generates its own filename, so it should be reasonable length
    assert len(result["path"]) < 100

    # Cleanup
    await storage_service.delete_image(result["path"])


@pytest.mark.integration
async def test_upload_empty_image_data(storage_service):
    """Test uploading empty image data (edge case)."""
    # Act & Assert - Should raise an exception or handle gracefully
    with pytest.raises(Exception):
        await storage_service.upload_image(
            image_data=b"",
            filename="empty.png",
            content_type="image/png"
        )


@pytest.mark.integration
async def test_multiple_uploads_same_filename(storage_service, test_image_data):
    """Test uploading multiple files with same filename creates unique paths."""
    filename = "duplicate_test.png"

    # Act - Upload twice with same filename
    result1 = await storage_service.upload_image(
        image_data=test_image_data,
        filename=filename,
        content_type="image/png"
    )

    result2 = await storage_service.upload_image(
        image_data=test_image_data,
        filename=filename,
        content_type="image/png"
    )

    # Assert - Paths should be different (timestamp + UUID makes them unique)
    assert result1["path"] != result2["path"]

    # Cleanup
    await storage_service.delete_image(result1["path"])
    await storage_service.delete_image(result2["path"])


@pytest.mark.integration
async def test_get_extension_method(storage_service):
    """Test the _get_extension static method with various inputs."""
    # Test with filename
    assert storage_service._get_extension("image/png", "test.png") == ".png"
    assert storage_service._get_extension("image/jpeg", "test.jpg") == ".jpg"
    assert storage_service._get_extension("image/jpeg", "test.JPEG") == ".jpeg"

    # Test without filename (use content_type)
    assert storage_service._get_extension("image/png", None) == ".png"
    assert storage_service._get_extension("image/jpeg", None) == ".jpg"
    assert storage_service._get_extension("image/webp", None) == ".webp"

    # Test with unknown content_type
    assert storage_service._get_extension("image/unknown", None) == ".jpg"  # Default


@pytest.mark.integration
async def test_upload_create_unique_timestamped_paths(storage_service, test_image_data):
    """Test that uploads create paths with timestamp and unique ID."""
    import re

    # Act
    result = await storage_service.upload_image(
        image_data=test_image_data,
        filename="timestamp_test.png",
        content_type="image/png"
    )

    # Assert - Path should match pattern: YYYYMMDD_HHMMSS_<uuid>.png
    path = result["path"]
    pattern = r'^\d{8}_\d{6}_[a-f0-9]{8}\.png$'
    assert re.match(pattern, path), f"Path '{path}' doesn't match expected pattern"

    # Cleanup
    await storage_service.delete_image(path)


@pytest.mark.integration
async def test_delete_already_deleted_image(storage_service, test_image_data):
    """Test deleting the same image twice."""
    # Arrange - Upload and delete once
    result = await storage_service.upload_image(
        image_data=test_image_data,
        filename="delete_twice.png",
        content_type="image/png"
    )
    path = result["path"]

    first_delete = await storage_service.delete_image(path)
    assert first_delete is True

    # Act - Try deleting again
    second_delete = await storage_service.delete_image(path)

    # Assert - Should return False (already deleted)
    assert second_delete is False
