"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

@pytest.fixture(scope="session", autouse=True)
def load_env():
    """
    Load environment variables from .env file.
    
    Uses the main .env file but allows overrides for testing.
    """
    # Load main .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment from {env_path}")
    else:
        print("⚠ No .env file found - using system environment")
    
    # Override specific settings for tests
    # Use test bucket to keep test data separate
    os.environ['SUPABASE_BUCKETS'] = 'food-image-test'
    os.environ['SUPABASE_TABLE'] = 'food_analyses'  # Keep same table or use food_analyses_test
    
    print(f"✓ Test bucket: {os.environ.get('SUPABASE_BUCKETS')}")

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_settings():
    """
    Get settings for integration tests.
    
    This will use real .env credentials with test bucket override.
    """
    from backend.config import Settings
    settings = Settings()
    
    # Verify it's using test bucket
    assert settings.supabase_bucket == 'food-image-test', \
        "Test settings should use food-image-test bucket"
    
    return settings

@pytest.fixture
async def test_database_service(test_settings):
    """
    Create real DatabaseService for integration tests.
    
    Uses actual Supabase but with test bucket.
    """
    from backend.services.supabase_service import DatabaseService
    
    service = DatabaseService(
        url=test_settings.supabase_url,
        key=test_settings.supabase_service_key,
        table_name=test_settings.supabase_table
    )
    return service

@pytest.fixture
async def test_storage_service(test_settings):
    """
    Create real StorageService for integration tests.
    
    Uses test bucket to keep test images separate.
    """
    from backend.services.supabase_service import StorageService
    
    service = StorageService(
        url=test_settings.supabase_url,
        key=test_settings.supabase_service_key,
        bucket_name='food-image-test'  # Hardcode test bucket
    )
    
    # Ensure test bucket exists
    await service.ensure_bucket_exists()
    
    return service
