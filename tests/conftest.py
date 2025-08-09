"""Pytest configuration and fixtures for Opitios Alpaca tests."""

import pytest
import asyncio
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def project_root_path():
    """Provide the project root path."""
    return project_root


@pytest.fixture
def secrets_file_path():
    """Provide the secrets file path."""
    return project_root / "secrets.yml"


@pytest.fixture
def mock_alpaca_credentials():
    """Provide mock Alpaca credentials for testing."""
    return {
        "api_key": "test_api_key",
        "secret_key": "test_secret_key",
        "paper_trading": True
    }