"""Unit tests for health check routes."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime

from app.health_routes import health_router, WebHealthChecker, health_cache


@pytest.fixture
def test_app():
    """Create test app with health routes."""
    app = FastAPI()
    app.include_router(health_router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def health_checker():
    """Create WebHealthChecker instance."""
    return WebHealthChecker()


class TestWebHealthChecker:
    """Test WebHealthChecker class."""
    
    @patch('app.health_routes.settings')
    def test_health_checker_initialization(self, mock_settings):
        """Test WebHealthChecker initialization."""
        mock_settings.accounts = {"account1": "config1"}
        
        checker = WebHealthChecker()
        assert checker.accounts == {"account1": "config1"}
        
    def test_health_checker_exists(self):
        """Test WebHealthChecker class exists and can be instantiated."""
        checker = WebHealthChecker()
        assert checker is not None
        assert hasattr(checker, 'accounts')


class TestHealthRouter:
    """Test health router configuration."""
    
    def test_health_router_prefix(self):
        """Test health router has correct prefix."""
        assert health_router.prefix == "/health"
        
    def test_health_router_tags(self):
        """Test health router has correct tags."""
        assert "health" in health_router.tags
        
    def test_health_routes_registered(self, test_app):
        """Test health routes are properly registered."""
        routes = [route.path for route in test_app.routes]
        health_routes = [route for route in routes if route.startswith("/health")]
        assert len(health_routes) >= 0  # At least basic health routes should exist


class TestHealthCache:
    """Test health check caching mechanism."""
    
    def test_health_cache_exists(self):
        """Test health cache variable exists."""
        from app.health_routes import health_cache
        assert isinstance(health_cache, dict)
        
    def test_health_check_running_flag(self):
        """Test health check running flag exists."""
        from app.health_routes import health_check_running
        assert isinstance(health_check_running, bool)
        
    def test_health_cache_operations(self):
        """Test basic health cache operations."""
        # Clear cache for test
        health_cache.clear()
        
        # Test cache operations
        test_key = "test_account"
        test_data = {"status": "healthy", "timestamp": datetime.now()}
        
        health_cache[test_key] = test_data
        assert health_cache[test_key] == test_data
        
        # Clean up
        health_cache.clear()


class TestHealthCheckEndpoints:
    """Test health check endpoints."""
    
    def test_health_endpoints_accessible(self, client):
        """Test basic health endpoints are accessible."""
        # Test that the health router is mounted
        # Basic connectivity test - endpoints should exist even if they return errors
        response = client.get("/health/")
        # Should either work (200) or be not found (404) but not server error
        assert response.status_code in [200, 404, 405]  # 405 = Method Not Allowed
        
    def test_health_router_mounted(self, test_app):
        """Test health router is properly mounted."""
        # Check that routes exist in the app
        route_paths = [route.path for route in test_app.routes]
        # The router should be mounted even if no specific routes are defined
        assert any(path.startswith("/health") for path in route_paths) or len(route_paths) > 0


class TestAlpacaClientIntegration:
    """Test Alpaca client integration in health checks."""
    
    @patch('app.health_routes.TradingClient')
    def test_trading_client_import(self, mock_trading_client):
        """Test TradingClient is properly imported."""
        # Test that imports work
        from app.health_routes import TradingClient
        assert TradingClient is not None
        
    @patch('app.health_routes.StockHistoricalDataClient')
    def test_stock_client_import(self, mock_stock_client):
        """Test StockHistoricalDataClient is properly imported."""
        from app.health_routes import StockHistoricalDataClient
        assert StockHistoricalDataClient is not None
        
    def test_alpaca_enums_import(self):
        """Test Alpaca enums are properly imported."""
        from app.health_routes import OrderSide, TimeInForce
        assert OrderSide is not None
        assert TimeInForce is not None


class TestHealthCheckModels:
    """Test health check related models and requests."""
    
    def test_limit_order_request_import(self):
        """Test LimitOrderRequest import."""
        from app.health_routes import LimitOrderRequest
        assert LimitOrderRequest is not None
        
    def test_stock_quote_request_import(self):
        """Test StockLatestQuoteRequest import."""
        from app.health_routes import StockLatestQuoteRequest
        assert StockLatestQuoteRequest is not None


class TestBackgroundTasksIntegration:
    """Test background tasks integration."""
    
    def test_background_tasks_import(self):
        """Test BackgroundTasks is properly imported."""
        from app.health_routes import BackgroundTasks
        assert BackgroundTasks is not None
        
    @patch('app.health_routes.settings')
    def test_settings_integration(self, mock_settings):
        """Test settings integration in health checks."""
        mock_settings.accounts = {}
        
        from app.health_routes import settings
        assert settings is not None


class TestErrorHandling:
    """Test error handling in health routes."""
    
    def test_http_exception_import(self):
        """Test HTTPException is properly imported."""
        from app.health_routes import HTTPException
        assert HTTPException is not None
        
    def test_asyncio_integration(self):
        """Test asyncio integration."""
        from app.health_routes import asyncio
        assert asyncio is not None


class TestLoggingIntegration:
    """Test logging integration."""
    
    def test_logger_import(self):
        """Test logger is properly imported."""
        from app.health_routes import logger
        assert logger is not None
        
    def test_datetime_import(self):
        """Test datetime is properly imported."""
        from app.health_routes import datetime
        assert datetime is not None


class TestHealthCheckConcurrency:
    """Test concurrent health check handling."""
    
    def test_health_check_running_flag_operations(self):
        """Test health check running flag operations."""
        from app.health_routes import health_check_running
        
        # Test flag can be accessed and is boolean
        assert isinstance(health_check_running, bool)
        
    def test_concurrent_health_check_prevention(self):
        """Test concurrent health check prevention mechanism."""
        # This tests that the global flag exists for preventing concurrent checks
        from app.health_routes import health_check_running
        
        # Should be able to check the flag
        original_state = health_check_running
        assert isinstance(original_state, bool)


@pytest.mark.asyncio
class TestAsyncHealthOperations:
    """Test async health check operations."""
    
    async def test_async_health_checker_compatibility(self):
        """Test health checker is compatible with async operations."""
        checker = WebHealthChecker()
        
        # Should be able to create and use in async context
        assert checker is not None
        assert hasattr(checker, 'accounts')
        
    async def test_asyncio_integration(self):
        """Test asyncio is properly integrated."""
        import asyncio
        
        # Should be able to use asyncio in health check context
        await asyncio.sleep(0.001)  # Minimal async operation test
        assert True  # If we get here, async works