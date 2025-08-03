"""
Pytest configuration and shared fixtures for Alpaca service tests
"""

import pytest
import os
import sys
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from typing import Generator, Dict, Any
from fastapi.testclient import TestClient

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app
from app.middleware import create_jwt_token


@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture"""
    return {
        "real_data_only": True,
        "mock_data_enabled": False,
        "strict_error_handling": True,
        "max_option_symbols_per_request": 50
    }


@pytest.fixture
def mock_settings():
    """Mock settings for tests"""
    with patch('config.settings') as mock_settings:
        mock_settings.alpaca_api_key = "test_api_key"
        mock_settings.alpaca_secret_key = "test_secret_key"
        mock_settings.alpaca_base_url = "https://paper-api.alpaca.markets"
        mock_settings.alpaca_paper_trading = True
        mock_settings.real_data_only = True
        mock_settings.enable_mock_data = False
        mock_settings.strict_error_handling = True
        mock_settings.max_option_symbols_per_request = 50
        yield mock_settings


@pytest.fixture
def sample_stock_quote():
    """Sample stock quote data"""
    return {
        "symbol": "AAPL",
        "bid_price": 185.25,
        "ask_price": 185.50,
        "bid_size": 100,
        "ask_size": 200,
        "timestamp": datetime.now().isoformat() + "Z"
    }


@pytest.fixture
def sample_option_quote():
    """Sample option quote data"""
    return {
        "symbol": "AAPL240315C00180000",
        "underlying_symbol": "AAPL",
        "strike_price": 180.0,
        "expiration_date": "2024-03-15",
        "option_type": "call",
        "bid_price": 8.25,
        "ask_price": 8.75,
        "bid_size": 25,
        "ask_size": 35,
        "timestamp": datetime.now().isoformat() + "Z"
    }


@pytest.fixture
def sample_account_data():
    """Sample account data"""
    return {
        "account_number": "123456789",
        "buying_power": 50000.00,
        "cash": 25000.00,
        "portfolio_value": 75000.00,
        "equity": 75000.00,
        "last_equity": 74500.00,
        "multiplier": "4",
        "pattern_day_trader": False
    }


@pytest.fixture
def real_data_validation():
    """Fixture to validate that responses contain only real data"""
    def validate_no_mock_data(data):
        """Validate that response contains no mock or synthetic data"""
        data_str = str(data).lower()
        
        # Check for mock data indicators
        mock_indicators = [
            "mock", "synthetic", "calculated", "estimated", "simulated",
            "fake", "test_mode", "paper_mode", "virtual", "fallback"
        ]
        
        for indicator in mock_indicators:
            assert indicator not in data_str, f"Found mock data indicator: {indicator}"
        
        return True
    
    return validate_no_mock_data


@pytest.fixture
def alpaca_error_scenarios():
    """Common Alpaca API error scenarios"""
    return {
        "network_timeout": Exception("Network timeout"),
        "rate_limit": Exception("Rate limit exceeded"),
        "invalid_credentials": Exception("Invalid API credentials"),
        "market_closed": {"error": "Market is closed"},
        "symbol_not_found": {"error": "Symbol not found"},
        "no_options_data": {"error": "No options data available"}
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
        # Add markers based on test file names
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        elif "e2e" in item.nodeid:
            item.add_marker(pytest.mark.e2e)


# Skip performance tests in CI if needed
def pytest_runtest_setup(item):
    """Setup for individual tests"""
    if "performance" in item.keywords:
        if os.getenv("SKIP_PERFORMANCE_TESTS"):
            pytest.skip("Performance tests skipped in CI")


# Additional fixtures for comprehensive testing
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application"""
    return TestClient(app)


@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Provide test user data"""
    return {
        "user_id": "test_user_123",
        "username": "testuser",
        "email": "test@example.com",
        "permissions": ["trading", "market_data"],
        "rate_limits": {
            "requests_per_minute": 120,
            "orders_per_minute": 10
        },
        "alpaca_credentials": {
            "api_key": "test_api_key",
            "secret_key": "test_secret_key",
            "paper_trading": True
        }
    }


@pytest.fixture
def jwt_token(test_user_data) -> str:
    """Create a JWT token for testing"""
    return create_jwt_token({
        "user_id": test_user_data["user_id"],
        "permissions": test_user_data["permissions"]
    })


@pytest.fixture
def auth_headers(jwt_token) -> Dict[str, str]:
    """Create authorization headers with JWT token"""
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.fixture
def test_context():
    """Create a test context for multi-account system"""
    return {
        "account_id": "account_001",
        "routing_key": "test_routing"
    }


@pytest.fixture(autouse=True)
def cleanup_connections():
    """Automatically cleanup connections after each test"""
    yield
    # Any cleanup needed for connection pool
    pass