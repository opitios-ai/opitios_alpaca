"""Unit tests for middleware components with real authentication flows."""

import pytest
import time
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.responses import JSONResponse

from app.middleware import (
    RequestContext,
    RateLimiter,
    create_jwt_token,
    verify_jwt_token,
    get_current_context,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    LoggingMiddleware,
    JWT_SECRET,
    JWT_ALGORITHM
)


class TestRequestContext:
    """Test RequestContext functionality."""
    
    def test_context_creation(self):
        """Test RequestContext creation with token payload."""
        token_payload = {
            "user_id": "test_user_123",
            "account_id": "test_account_456",
            "permissions": ["trading", "market_data", "admin"]
        }
        
        context = RequestContext(token_payload)
        
        assert context.user_id == "test_user_123"
        assert context.account_id == "test_account_456"
        assert context.permissions == ["trading", "market_data", "admin"]
        assert context.request_count == 0
        assert isinstance(context.created_at, datetime)
        assert isinstance(context.last_active, datetime)
    
    def test_context_creation_with_defaults(self):
        """Test RequestContext creation with minimal payload."""
        token_payload = {}
        
        context = RequestContext(token_payload)
        
        assert context.user_id == "external_user"
        assert context.account_id is None
        assert context.permissions == []
    
    def test_update_activity(self):
        """Test activity update functionality."""
        context = RequestContext({"user_id": "test_user"})
        
        initial_count = context.request_count
        initial_time = context.last_active
        
        # Small delay to ensure time difference
        time.sleep(0.01)
        
        context.update_activity()
        
        assert context.request_count == initial_count + 1
        assert context.last_active > initial_time
    
    def test_has_permission(self):
        """Test permission checking."""
        context = RequestContext({
            "user_id": "test_user",
            "permissions": ["trading", "market_data"]
        })
        
        assert context.has_permission("trading") is True
        assert context.has_permission("market_data") is True
        assert context.has_permission("admin") is False
        assert context.has_permission("nonexistent") is False


class TestRateLimiter:
    """Test RateLimiter functionality."""
    
    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter()
        
        assert hasattr(limiter, 'memory_store')
        assert callable(limiter.is_allowed)
    
    def test_memory_rate_limiting_allowed(self):
        """Test memory-based rate limiting when requests are allowed."""
        limiter = RateLimiter()
        
        # First request should be allowed
        allowed, info = limiter.is_allowed("test_user", limit=5, window_seconds=60)
        
        assert allowed is True
        assert info["limit"] == 5
        assert info["remaining"] == 4
        assert info["current_requests"] == 1
        assert "reset_time" in info
    
    def test_memory_rate_limiting_exceeded(self):
        """Test memory-based rate limiting when limit is exceeded."""
        limiter = RateLimiter()
        identifier = "test_user_limit"
        
        # Make requests up to the limit
        for i in range(3):
            allowed, info = limiter.is_allowed(identifier, limit=3, window_seconds=60)
            assert allowed is True
            assert info["remaining"] == 2 - i
        
        # Next request should be denied
        allowed, info = limiter.is_allowed(identifier, limit=3, window_seconds=60)
        
        assert allowed is False
        assert info["limit"] == 3
        assert info["remaining"] == 0
        assert info["current_requests"] == 3
    
    def test_memory_rate_limiting_window_expiry(self):
        """Test that rate limiting resets after window expires."""
        limiter = RateLimiter()
        identifier = "test_user_expiry"
        
        # Use very short window for testing
        window_seconds = 1
        
        # Fill up the limit
        for i in range(2):
            allowed, info = limiter.is_allowed(identifier, limit=2, window_seconds=window_seconds)
            assert allowed is True
        
        # Should be at limit
        allowed, info = limiter.is_allowed(identifier, limit=2, window_seconds=window_seconds)
        assert allowed is False
        
        # Wait for window to expire
        time.sleep(window_seconds + 0.1)
        
        # Should be allowed again
        allowed, info = limiter.is_allowed(identifier, limit=2, window_seconds=window_seconds)
        assert allowed is True
        assert info["remaining"] == 1
    
    def test_rate_limiter_key_generation(self):
        """Test rate limiter key generation."""
        limiter = RateLimiter()
        
        key = limiter._get_key("test_user", "60")
        
        assert key == "rate_limit:test_user:60"
        assert isinstance(key, str)
    
    def test_clean_old_requests(self):
        """Test cleaning old requests from memory store."""
        limiter = RateLimiter()
        
        # Create a deque with old and new timestamps
        from collections import deque
        requests = deque()
        
        now = time.time()
        old_time = now - 120  # 2 minutes ago
        recent_time = now - 30  # 30 seconds ago
        
        requests.extend([old_time, recent_time, now])
        
        # Clean requests older than 60 seconds
        limiter._clean_old_requests(requests, 60)
        
        # Should only have recent requests
        assert len(requests) == 2
        assert old_time not in requests
        assert recent_time in requests
        assert now in requests


class TestJWTFunctions:
    """Test JWT token creation and verification."""
    
    def test_create_jwt_token(self):
        """Test JWT token creation."""
        user_data = {
            "user_id": "test_user_123",
            "account_id": "test_account_456",
            "permissions": ["trading", "market_data"]
        }
        
        token = create_jwt_token(user_data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == "test_user_123"
        assert payload["account_id"] == "test_account_456"
        assert payload["permissions"] == ["trading", "market_data"]
        assert "exp" in payload
        assert "iat" in payload
    
    def test_create_jwt_token_with_defaults(self):
        """Test JWT token creation with minimal data."""
        user_data = {}
        
        token = create_jwt_token(user_data)
        
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == "demo_user"
        assert payload["account_id"] is None
        assert payload["permissions"] == ["trading", "market_data"]
    
    def test_verify_jwt_token_valid(self):
        """Test JWT token verification with valid token."""
        user_data = {"user_id": "test_user", "permissions": ["trading"]}
        token = create_jwt_token(user_data)
        
        payload = verify_jwt_token(token)
        
        assert payload["user_id"] == "test_user"
        assert payload["permissions"] == ["trading"]
    
    def test_verify_jwt_token_invalid(self):
        """Test JWT token verification with invalid token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(invalid_token)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail
    
    def test_verify_jwt_token_expired(self):
        """Test JWT token verification with expired token."""
        # Create token with past expiration
        payload = {
            "user_id": "test_user",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(expired_token)
        
        assert exc_info.value.status_code == 401
        assert "Token expired" in exc_info.value.detail


class TestGetCurrentContext:
    """Test get_current_context dependency function."""
    
    @pytest.mark.asyncio
    async def test_get_current_context_valid_token(self):
        """Test getting current context with valid token."""
        user_data = {
            "user_id": "test_user_123",
            "account_id": "test_account_456",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        context = await get_current_context(credentials)
        
        assert isinstance(context, RequestContext)
        assert context.user_id == "test_user_123"
        assert context.account_id == "test_account_456"
        assert context.permissions == ["trading", "market_data"]
        assert context.request_count == 1  # Should be updated
    
    @pytest.mark.asyncio
    async def test_get_current_context_invalid_token(self):
        """Test getting current context with invalid token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid.token.here"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_context(credentials)
        
        assert exc_info.value.status_code == 401


class TestAuthenticationMiddleware:
    """Test AuthenticationMiddleware functionality."""
    
    def test_middleware_initialization(self):
        """Test AuthenticationMiddleware initialization."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        assert middleware.public_paths is not None
        assert len(middleware.public_paths) > 0
        assert "/health" in middleware.public_paths
        assert "/docs" in middleware.public_paths
    
    @pytest.mark.asyncio
    async def test_middleware_public_path(self):
        """Test middleware allows public paths without authentication."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        # Mock request for public path
        request = MagicMock(spec=Request)
        request.url.path = "/health"
        
        call_next = AsyncMock()
        call_next.return_value = JSONResponse(content={"status": "ok"})
        
        response = await middleware.dispatch(request, call_next)
        
        call_next.assert_called_once_with(request)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_missing_auth_header(self):
        """Test middleware rejects requests without auth header."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        # Mock request without auth header
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/protected"
        request.headers.get.return_value = None
        
        call_next = AsyncMock()
        
        response = await middleware.dispatch(request, call_next)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
        call_next.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_middleware_invalid_auth_header(self):
        """Test middleware rejects requests with invalid auth header."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        # Mock request with invalid auth header
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/protected"
        request.headers.get.return_value = "Invalid header format"
        
        call_next = AsyncMock()
        
        response = await middleware.dispatch(request, call_next)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
        call_next.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_middleware_valid_token(self):
        """Test middleware allows requests with valid token."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        # Create valid token
        user_data = {"user_id": "test_user", "permissions": ["trading"]}
        token = create_jwt_token(user_data)
        
        # Mock request with valid auth header
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/protected"
        request.headers.get.return_value = f"Bearer {token}"
        request.state = MagicMock()
        
        call_next = AsyncMock()
        call_next.return_value = JSONResponse(content={"data": "success"})
        
        response = await middleware.dispatch(request, call_next)
        
        call_next.assert_called_once_with(request)
        assert response.status_code == 200
        
        # Verify request state was set
        assert request.state.user_id == "test_user"
        assert request.state.permissions == ["trading"]


class TestRateLimitMiddleware:
    """Test RateLimitMiddleware functionality."""
    
    def test_rate_limit_middleware_initialization(self):
        """Test RateLimitMiddleware initialization."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        assert middleware.endpoint_limits is not None
        assert "default" in middleware.endpoint_limits
        assert "/api/v1/stocks/quote" in middleware.endpoint_limits
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_public_path(self):
        """Test rate limit middleware allows public paths."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/health"
        
        call_next = AsyncMock()
        call_next.return_value = JSONResponse(content={"status": "ok"})
        
        response = await middleware.dispatch(request, call_next)
        
        call_next.assert_called_once_with(request)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_anonymous_user(self):
        """Test rate limit middleware allows anonymous users."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/stocks/quote"
        request.state = MagicMock()
        request.state.user_id = None
        
        call_next = AsyncMock()
        call_next.return_value = JSONResponse(content={"data": "success"})
        
        response = await middleware.dispatch(request, call_next)
        
        call_next.assert_called_once_with(request)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_within_limit(self):
        """Test rate limit middleware allows requests within limit."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/stocks/quote"
        request.state = MagicMock()
        request.state.user_id = "test_user"
        
        call_next = AsyncMock()
        call_next.return_value = MagicMock()
        call_next.return_value.headers = {}
        
        # Mock rate limiter to allow request
        with patch('app.middleware.rate_limiter') as mock_limiter:
            mock_limiter.is_allowed.return_value = (True, {
                "limit": 60,
                "remaining": 59,
                "reset_time": int(time.time() + 60),
                "current_requests": 1
            })
            
            response = await middleware.dispatch(request, call_next)
            
            call_next.assert_called_once_with(request)
            
            # Check rate limit headers were added
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_exceeded(self):
        """Test rate limit middleware blocks requests when limit exceeded."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/stocks/quote"
        request.state = MagicMock()
        request.state.user_id = "test_user"
        
        call_next = AsyncMock()
        
        # Mock rate limiter to deny request
        with patch('app.middleware.rate_limiter') as mock_limiter:
            mock_limiter.is_allowed.return_value = (False, {
                "limit": 60,
                "remaining": 0,
                "reset_time": int(time.time() + 60),
                "current_requests": 60
            })
            
            response = await middleware.dispatch(request, call_next)
            
            assert isinstance(response, JSONResponse)
            assert response.status_code == 429
            call_next.assert_not_called()
            
            # Check rate limit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers


class TestLoggingMiddleware:
    """Test LoggingMiddleware functionality."""
    
    def test_logging_middleware_initialization(self):
        """Test LoggingMiddleware initialization."""
        app = MagicMock()
        middleware = LoggingMiddleware(app)
        
        assert middleware is not None
    
    @pytest.mark.asyncio
    async def test_logging_middleware_request_logging(self):
        """Test logging middleware logs requests and responses."""
        app = MagicMock()
        middleware = LoggingMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.__str__ = MagicMock(return_value="http://test.com/api/v1/test")
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = "test-user-agent"
        request.state = MagicMock()
        request.state.user_id = "test_user"
        
        call_next = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        with patch('app.middleware.logger') as mock_logger:
            response = await middleware.dispatch(request, call_next)
            
            # Verify request was logged
            assert mock_logger.info.call_count == 2  # Start and completion
            
            # Verify response headers were added
            assert "X-Process-Time" in response.headers
            
            call_next.assert_called_once_with(request)


class TestMiddlewareIntegration:
    """Integration tests for middleware components."""
    
    @pytest.mark.asyncio
    async def test_middleware_chain_integration(self):
        """Test integration of multiple middleware components."""
        # This would typically test the full middleware chain
        # For now, we test that they can work together
        
        user_data = {"user_id": "integration_user", "permissions": ["trading"]}
        token = create_jwt_token(user_data)
        
        # Verify token works with context function
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        context = await get_current_context(credentials)
        
        assert context.user_id == "integration_user"
        assert context.has_permission("trading")
        
        # Test rate limiting for the user
        limiter = RateLimiter()
        allowed, info = limiter.is_allowed("integration_user", limit=10, window_seconds=60)
        
        assert allowed is True
        assert info["remaining"] == 9
    
    def test_jwt_token_roundtrip(self):
        """Test complete JWT token creation and verification cycle."""
        original_data = {
            "user_id": "roundtrip_user",
            "account_id": "roundtrip_account",
            "permissions": ["trading", "market_data", "admin"]
        }
        
        # Create token
        token = create_jwt_token(original_data)
        
        # Verify token
        payload = verify_jwt_token(token)
        
        # Check all data is preserved
        assert payload["user_id"] == original_data["user_id"]
        assert payload["account_id"] == original_data["account_id"]
        assert payload["permissions"] == original_data["permissions"]
        
        # Create context from payload
        context = RequestContext(payload)
        
        assert context.user_id == original_data["user_id"]
        assert context.account_id == original_data["account_id"]
        assert context.permissions == original_data["permissions"]
    
    @pytest.mark.asyncio
    async def test_rate_limiting_across_endpoints(self):
        """Test rate limiting behavior across different endpoints."""
        limiter = RateLimiter()
        user_id = "multi_endpoint_user"
        
        # Test different endpoints have separate limits
        endpoint1 = "/api/v1/stocks/quote"
        endpoint2 = "/api/v1/options/quote"
        
        # Make requests to endpoint1
        for i in range(3):
            allowed, info = limiter.is_allowed(
                f"user:{user_id}:{endpoint1}", limit=5, window_seconds=60
            )
            assert allowed is True
            assert info["remaining"] == 4 - i
        
        # Make requests to endpoint2 (should have separate limit)
        for i in range(2):
            allowed, info = limiter.is_allowed(
                f"user:{user_id}:{endpoint2}", limit=5, window_seconds=60
            )
            assert allowed is True
            assert info["remaining"] == 4 - i
        
        # Verify endpoint1 still has its separate count
        allowed, info = limiter.is_allowed(
            f"user:{user_id}:{endpoint1}", limit=5, window_seconds=60
        )
        assert allowed is True
        assert info["remaining"] == 1  # Should be 4th request for endpoint1


@pytest.mark.asyncio
async def test_middleware_error_handling():
    """Test middleware error handling scenarios."""
    # Test authentication middleware with malformed token
    app = MagicMock()
    auth_middleware = AuthenticationMiddleware(app)
    
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/protected"
    request.headers.get.return_value = "Bearer malformed.token"
    
    call_next = AsyncMock()
    
    response = await auth_middleware.dispatch(request, call_next)
    
    assert isinstance(response, JSONResponse)
    assert response.status_code == 401
    call_next.assert_not_called()


def test_redis_fallback_behavior():
    """Test rate limiter fallback to memory when Redis is unavailable."""
    # This test verifies the fallback mechanism
    limiter = RateLimiter()
    
    # Mock Redis to be unavailable
    with patch('app.middleware.get_redis_client', return_value=None):
        allowed, info = limiter.is_allowed("test_user", limit=5, window_seconds=60)
        
        assert allowed is True
        assert info["limit"] == 5
        assert info["remaining"] == 4
        
        # Verify it's using memory store
        assert "test_user" in limiter.memory_store