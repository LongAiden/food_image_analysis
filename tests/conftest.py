"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """
    Load environment variables from .env file for all tests.

    This fixture runs automatically for every test session.
    """
    # Load main .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment from {env_path}")
    else:
        print("⚠ No .env file found - using system environment")

    print(f"✓ Test bucket: {os.environ.get('SUPABASE_BUCKETS_TEST')}")
    print(f"✓ Test table: {os.environ.get('SUPABASE_TABLE_TEST')}")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
