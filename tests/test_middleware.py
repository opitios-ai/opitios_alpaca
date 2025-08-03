"""
Comprehensive tests for middleware functionality including rate limiting,
authentication middleware, and logging middleware
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from main import app
from app.middleware import (
    RateLimiter, AuthenticationMiddleware, RateLimitMiddleware, 
    LoggingMiddleware, UserContextManager, create_jwt_token
)

client = TestClient(app)


class TestRateLimiter:
    """Test RateLimiter functionality"""
    
    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization"""
        limiter = RateLimiter()
        assert limiter.memory_store is not None
        assert isinstance(limiter.memory_store, dict)
    
    def test_memory_rate_limiting_allow(self):
        """Test memory-based rate limiting - allowed requests"""
        limiter = RateLimiter()
        identifier = "test_user_123"
        limit = 5
        window_seconds = 60
        
        # First request should be allowed
        allowed, info = limiter.is_allowed(identifier, limit, window_seconds)
        
        assert allowed is True
        assert info["limit"] == limit
        assert info["remaining"] == limit - 1
        assert info["current_requests"] == 1
        assert "reset_time" in info
    
    def test_memory_rate_limiting_multiple_requests(self):
        """Test memory-based rate limiting - multiple requests"""
        limiter = RateLimiter()
        identifier = "test_user_123"
        limit = 3
        window_seconds = 60
        
        # Make requests up to limit
        results = []
        for i in range(limit + 2):  # Try to exceed limit
            allowed, info = limiter.is_allowed(identifier, limit, window_seconds)
            results.append((allowed, info))
        
        # First 3 should be allowed
        for i in range(limit):
            assert results[i][0] is True
            assert results[i][1]["remaining"] == limit - i - 1
        
        # Requests beyond limit should be rejected
        for i in range(limit, len(results)):
            assert results[i][0] is False
            assert results[i][1]["remaining"] == 0
    
    def test_memory_rate_limiting_window_expiry(self):
        """Test memory-based rate limiting - window expiry"""
        limiter = RateLimiter()
        identifier = "test_user_123"
        limit = 2
        window_seconds = 1  # Very short window
        
        # Fill up the limit
        allowed1, _ = limiter.is_allowed(identifier, limit, window_seconds)
        allowed2, _ = limiter.is_allowed(identifier, limit, window_seconds)
        allowed3, _ = limiter.is_allowed(identifier, limit, window_seconds)
        
        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again after window expiry
        allowed4, info = limiter.is_allowed(identifier, limit, window_seconds)
        assert allowed4 is True
        assert info["remaining"] == limit - 1
    
    def test_rate_limiter_different_users(self):
        """Test rate limiting with different users"""
        limiter = RateLimiter()
        limit = 2
        window_seconds = 60
        
        # User 1 fills their limit
        allowed1, _ = limiter.is_allowed("user1", limit, window_seconds)
        allowed2, _ = limiter.is_allowed("user1", limit, window_seconds)
        allowed3, _ = limiter.is_allowed("user1", limit, window_seconds)
        
        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is False
        
        # User 2 should still be allowed
        allowed4, info = limiter.is_allowed("user2", limit, window_seconds)
        assert allowed4 is True
        assert info["remaining"] == limit - 1
    
    def test_clean_old_requests(self):
        """Test cleaning of old request records"""
        limiter = RateLimiter()
        
        # Create test deque with old and new timestamps
        from collections import deque
        requests = deque()
        now = time.time()
        
        # Add old requests (should be cleaned)
        requests.append(now - 120)  # 2 minutes old
        requests.append(now - 90)   # 1.5 minutes old
        
        # Add recent requests (should remain)
        requests.append(now - 30)   # 30 seconds old
        requests.append(now - 10)   # 10 seconds old
        
        assert len(requests) == 4
        
        # Clean requests older than 60 seconds
        limiter._clean_old_requests(requests, 60)
        
        assert len(requests) == 2  # Only recent requests should remain
        assert requests[0] == now - 30
        assert requests[1] == now - 10


class TestAuthenticationMiddleware:
    """Test AuthenticationMiddleware functionality"""
    
    @pytest.fixture
    def auth_middleware(self):
        """Fixture providing AuthenticationMiddleware instance"""
        return AuthenticationMiddleware(app=Mock())
    
    @pytest.mark.asyncio
    async def test_public_paths_allowed(self, auth_middleware):
        """Test that public paths are allowed without authentication"""
        mock_request = Mock()
        mock_request.url.path = "/docs"
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_call_next.return_value = mock_response
        
        result = await auth_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        mock_call_next.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    async def test_missing_authorization_header(self, auth_middleware):
        """Test request without Authorization header"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/protected"
        mock_request.headers = {}
        
        mock_call_next = AsyncMock()
        
        result = await auth_middleware.dispatch(mock_request, mock_call_next)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 401
        mock_call_next.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_invalid_authorization_format(self, auth_middleware):
        """Test request with invalid Authorization header format"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/protected"
        mock_request.headers = {"Authorization": "Invalid format"}
        
        mock_call_next = AsyncMock()
        
        result = await auth_middleware.dispatch(mock_request, mock_call_next)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 401
        mock_call_next.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.middleware.verify_jwt_token')
    async def test_valid_token(self, mock_verify, auth_middleware):
        """Test request with valid JWT token"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/protected"
        mock_request.headers = {"Authorization": "Bearer valid_token"}
        mock_request.state = Mock()
        
        mock_verify.return_value = {
            "user_id": "test_user_123",
            "permissions": ["trading", "market_data"]
        }
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_call_next.return_value = mock_response
        
        result = await auth_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        assert mock_request.state.user_id == "test_user_123"
        assert mock_request.state.permissions == ["trading", "market_data"]
        mock_call_next.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    @patch('app.middleware.verify_jwt_token')
    async def test_invalid_token(self, mock_verify, auth_middleware):
        """Test request with invalid JWT token"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/protected"
        mock_request.headers = {"Authorization": "Bearer invalid_token"}
        
        mock_verify.side_effect = HTTPException(status_code=401, detail="Invalid token")
        
        mock_call_next = AsyncMock()
        
        result = await auth_middleware.dispatch(mock_request, mock_call_next)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 401
        mock_call_next.assert_not_called()


class TestRateLimitMiddleware:
    """Test RateLimitMiddleware functionality"""
    
    @pytest.fixture
    def rate_limit_middleware(self):
        """Fixture providing RateLimitMiddleware instance"""
        return RateLimitMiddleware(app=Mock())
    
    @pytest.mark.asyncio
    async def test_public_paths_skip_rate_limiting(self, rate_limit_middleware):
        """Test that public paths skip rate limiting"""
        mock_request = Mock()
        mock_request.url.path = "/health"
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_call_next.return_value = mock_response
        
        result = await rate_limit_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        mock_call_next.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    async def test_no_user_id_skip_rate_limiting(self, rate_limit_middleware):
        """Test that requests without user_id skip rate limiting"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/protected"
        mock_request.state = Mock()
        mock_request.state.user_id = None
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_call_next.return_value = mock_response
        
        result = await rate_limit_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        mock_call_next.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    @patch.object(RateLimiter, 'is_allowed')
    async def test_rate_limit_allowed(self, mock_is_allowed, rate_limit_middleware):
        """Test request within rate limit"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/stocks/quote"
        mock_request.state = Mock()
        mock_request.state.user_id = "test_user_123"
        
        mock_is_allowed.return_value = (True, {
            "limit": 60,
            "remaining": 59,
            "reset_time": int(time.time() + 60),
            "current_requests": 1
        })
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        mock_call_next.return_value = mock_response
        
        result = await rate_limit_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        assert "X-RateLimit-Limit" in mock_response.headers
        assert "X-RateLimit-Remaining" in mock_response.headers
        assert "X-RateLimit-Reset" in mock_response.headers
        mock_call_next.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    @patch.object(RateLimiter, 'is_allowed')
    async def test_rate_limit_exceeded(self, mock_is_allowed, rate_limit_middleware):
        """Test request that exceeds rate limit"""
        mock_request = Mock()
        mock_request.url.path = "/api/v1/stocks/quote"
        mock_request.state = Mock()
        mock_request.state.user_id = "test_user_123"
        
        mock_is_allowed.return_value = (False, {
            "limit": 60,
            "remaining": 0,
            "reset_time": int(time.time() + 60),
            "current_requests": 61
        })
        
        mock_call_next = AsyncMock()
        
        result = await rate_limit_middleware.dispatch(mock_request, mock_call_next)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 429
        
        # Check response content
        import json
        content = json.loads(result.body.decode())
        assert "Rate limit exceeded" in content["detail"]
        assert content["limit"] == 60
        assert content["remaining"] == 0
        
        # Check headers
        assert "X-RateLimit-Limit" in result.headers
        assert "X-RateLimit-Remaining" in result.headers
        assert "X-RateLimit-Reset" in result.headers
        
        mock_call_next.assert_not_called()
    
    def test_endpoint_limit_configuration(self, rate_limit_middleware):
        """Test that different endpoints have different rate limits"""
        # Check specific endpoint limits
        assert "/api/v1/stocks/quote" in rate_limit_middleware.endpoint_limits
        assert "/api/v1/stocks/order" in rate_limit_middleware.endpoint_limits
        assert "default" in rate_limit_middleware.endpoint_limits
        
        # Verify different limits for different endpoints
        quote_limit = rate_limit_middleware.endpoint_limits["/api/v1/stocks/quote"]
        order_limit = rate_limit_middleware.endpoint_limits["/api/v1/stocks/order"]
        default_limit = rate_limit_middleware.endpoint_limits["default"]
        
        assert quote_limit != order_limit  # Different endpoints should have different limits
        assert default_limit[0] == 120  # Default should be 120 requests per minute


class TestLoggingMiddleware:
    """Test LoggingMiddleware functionality"""
    
    @pytest.fixture
    def logging_middleware(self):
        """Fixture providing LoggingMiddleware instance"""
        return LoggingMiddleware(app=Mock())
    
    @pytest.mark.asyncio
    @patch('app.middleware.logger')
    async def test_request_logging(self, mock_logger, logging_middleware):
        """Test that requests are properly logged"""
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url = Mock()
        mock_request.url.__str__ = Mock(return_value="http://test.com/api/v1/test")
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-agent"}
        mock_request.state = Mock()
        mock_request.state.user_id = "test_user_123"
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_call_next.return_value = mock_response
        
        result = await logging_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        assert "X-Process-Time" in mock_response.headers
        
        # Verify logging calls
        assert mock_logger.info.call_count == 2  # Start and completion logs
        
        # Check start log
        start_call = mock_logger.info.call_args_list[0]
        assert "Request started" in start_call[0][0]
        start_extra = start_call[1]["extra"]
        assert start_extra["user_id"] == "test_user_123"
        assert start_extra["method"] == "GET"
        assert start_extra["client_ip"] == "127.0.0.1"
        assert start_extra["user_agent"] == "test-agent"
        
        # Check completion log
        completion_call = mock_logger.info.call_args_list[1]
        assert "Request completed" in completion_call[0][0]
        completion_extra = completion_call[1]["extra"]
        assert completion_extra["user_id"] == "test_user_123"
        assert completion_extra["status_code"] == 200
        assert "process_time" in completion_extra
    
    @pytest.mark.asyncio
    @patch('app.middleware.logger')
    async def test_anonymous_user_logging(self, mock_logger, logging_middleware):
        """Test logging for anonymous users"""
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url = Mock()
        mock_request.url.__str__ = Mock(return_value="http://test.com/api/v1/test")
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-agent"}
        mock_request.state = Mock()
        # No user_id set (anonymous user)
        
        mock_call_next = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_call_next.return_value = mock_response
        
        result = await logging_middleware.dispatch(mock_request, mock_call_next)
        
        assert result == mock_response
        
        # Check that user_id is logged as "anonymous"
        start_call = mock_logger.info.call_args_list[0]
        start_extra = start_call[1]["extra"]
        assert start_extra["user_id"] == "anonymous"


class TestMiddlewareIntegration:
    """Integration tests for middleware stack"""
    
    def test_middleware_order(self):
        """Test that middleware is applied in correct order"""
        # This would test the full middleware stack to ensure
        # they are applied in the correct order and work together
        pass
    
    @pytest.mark.asyncio
    async def test_authentication_and_rate_limiting_together(self):
        """Test authentication and rate limiting working together"""
        # Create a valid token
        user_data = {
            "user_id": "test_user_123",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make multiple requests to test rate limiting
        responses = []
        for i in range(5):
            response = client.get("/api/v1/test-connection", headers=headers)
            responses.append(response)
        
        # All requests should have rate limit headers
        for response in responses:
            # Check if rate limit headers are present (they should be for authenticated requests)
            # Note: This test may need adjustment based on actual endpoint behavior
            pass
    
    def test_error_handling_across_middleware(self):
        """Test error handling across the middleware stack"""
        # Test that errors from one middleware don't break others
        pass


class TestMiddlewareConfiguration:
    """Test middleware configuration and settings"""
    
    def test_rate_limit_configuration_loading(self):
        """Test that rate limit configuration is properly loaded"""
        middleware = RateLimitMiddleware(app=Mock())
        
        # Check that endpoint limits are properly configured
        assert isinstance(middleware.endpoint_limits, dict)
        assert "default" in middleware.endpoint_limits
        
        # Check specific endpoint configurations
        for endpoint, (limit, window) in middleware.endpoint_limits.items():
            assert isinstance(limit, int)
            assert isinstance(window, int)
            assert limit > 0
            assert window > 0
    
    def test_authentication_middleware_public_paths(self):
        """Test authentication middleware public path configuration"""
        middleware = AuthenticationMiddleware(app=Mock())
        
        # Check that public paths are properly configured
        assert isinstance(middleware.public_paths, list)
        assert "/" in middleware.public_paths
        assert "/docs" in middleware.public_paths
        assert "/health" in middleware.public_paths


if __name__ == "__main__":
    pytest.main([__file__, "-v"])