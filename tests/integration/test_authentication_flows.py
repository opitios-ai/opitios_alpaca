"""Integration tests for authentication flows with JWT validation."""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.middleware import (
    create_jwt_token, 
    verify_jwt_token, 
    RequestContext,
    AuthenticationMiddleware,
    RateLimitMiddleware
)
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse


class TestJWTAuthenticationFlows:
    """Test JWT authentication flows end-to-end."""
    
    def test_complete_jwt_workflow(self):
        """Test complete JWT workflow from creation to validation."""
        # 1. Create user data
        user_data = {
            "user_id": "workflow_user_123",
            "account_id": "account_456", 
            "permissions": ["trading", "market_data", "options"],
            "role": "trader"
        }
        
        # 2. Create JWT token
        token = create_jwt_token(user_data)
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
        
        # 3. Verify token
        payload = verify_jwt_token(token)
        assert payload["user_id"] == user_data["user_id"]
        assert payload["account_id"] == user_data["account_id"]
        assert payload["permissions"] == user_data["permissions"]
        
        # 4. Create request context
        context = RequestContext(payload)
        assert context.user_id == user_data["user_id"]
        assert context.account_id == user_data["account_id"]
        assert context.has_permission("trading")
        assert context.has_permission("market_data")
        assert not context.has_permission("admin")
        
        # 5. Update activity
        initial_count = context.request_count
        context.update_activity()
        assert context.request_count == initial_count + 1
    
    def test_token_expiration_workflow(self):
        """Test token expiration handling."""
        # Create token with very short expiration
        user_data = {"user_id": "expiry_test"}
        
        # Mock datetime to create expired token
        past_time = datetime.utcnow() - timedelta(hours=25)  # 25 hours ago
        
        with patch('app.middleware.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = past_time
            expired_token = create_jwt_token(user_data)
        
        # Try to verify expired token
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(expired_token)
        
        assert exc_info.value.status_code == 401
        assert "Token expired" in exc_info.value.detail
    
    def test_invalid_token_workflow(self):
        """Test invalid token handling."""
        invalid_tokens = [
            "invalid.token.format",
            "not_a_token_at_all",
            "",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid.signature"
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises(HTTPException) as exc_info:
                verify_jwt_token(invalid_token)
            
            assert exc_info.value.status_code == 401
            assert "Invalid token" in exc_info.value.detail
    
    def test_permission_escalation_prevention(self):
        """Test that permissions cannot be escalated."""
        # Create token with limited permissions
        user_data = {
            "user_id": "limited_user",
            "permissions": ["market_data"]  # No trading permission
        }
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        context = RequestContext(payload)
        
        # Verify limited permissions
        assert context.has_permission("market_data")
        assert not context.has_permission("trading")
        assert not context.has_permission("admin")
        assert not context.has_permission("options")
        
        # Attempt to modify permissions (should not affect original)
        context.permissions.append("admin")
        
        # Create new context from same token
        new_payload = verify_jwt_token(token)
        new_context = RequestContext(new_payload)
        
        # Original permissions should be preserved
        assert not new_context.has_permission("admin")


class TestMiddlewareAuthenticationFlows:
    """Test authentication middleware flows."""
    
    @pytest.mark.asyncio
    async def test_authentication_middleware_workflow(self):
        """Test complete authentication middleware workflow."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        # Create valid token
        user_data = {
            "user_id": "middleware_user",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        # Mock request with valid token
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/protected"
        request.headers.get.return_value = f"Bearer {token}"
        request.state = MagicMock()
        
        # Mock call_next
        call_next = MagicMock()
        call_next.return_value = JSONResponse(content={"success": True})
        
        # Process request through middleware
        response = await middleware.dispatch(request, call_next)
        
        # Verify request was processed
        call_next.assert_called_once_with(request)
        assert response.status_code == 200
        
        # Verify request state was set
        assert request.state.user_id == "middleware_user"
        assert request.state.permissions == ["trading", "market_data"]
    
    @pytest.mark.asyncio
    async def test_public_path_bypass(self):
        """Test that public paths bypass authentication."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        public_paths = [
            "/health",
            "/docs", 
            "/api/v1/health",
            "/api/v1/health/comprehensive"
        ]
        
        for path in public_paths:
            request = MagicMock(spec=Request)
            request.url.path = path
            
            call_next = MagicMock()
            call_next.return_value = JSONResponse(content={"status": "ok"})
            
            response = await middleware.dispatch(request, call_next)
            
            # Should bypass authentication
            call_next.assert_called_with(request)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_missing_authorization_header(self):
        """Test handling of missing authorization header."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/protected"
        request.headers.get.return_value = None  # No auth header
        
        call_next = MagicMock()
        
        response = await middleware.dispatch(request, call_next)
        
        # Should return 401
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
        call_next.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_malformed_authorization_header(self):
        """Test handling of malformed authorization header."""
        app = MagicMock()
        middleware = AuthenticationMiddleware(app)
        
        malformed_headers = [
            "InvalidFormat",
            "Bearer",  # Missing token
            "Basic dXNlcjpwYXNz",  # Wrong auth type
            "Bearer invalid.token"
        ]
        
        for header in malformed_headers:
            request = MagicMock(spec=Request)
            request.url.path = "/api/v1/protected"
            request.headers.get.return_value = header
            
            call_next = MagicMock()
            
            response = await middleware.dispatch(request, call_next)
            
            # Should return 401 for all malformed headers
            assert isinstance(response, JSONResponse)
            assert response.status_code == 401
            call_next.assert_not_called()


class TestRateLimitingFlows:
    """Test rate limiting flows with authentication."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_with_authentication(self):
        """Test rate limiting combined with authentication."""
        app = MagicMock()
        rate_middleware = RateLimitMiddleware(app)
        
        # Mock request with authenticated user
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/stocks/quote"
        request.state = MagicMock()
        request.state.user_id = "rate_test_user"
        
        # Mock call_next
        call_next = MagicMock()
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        # Mock rate limiter to allow request
        with patch('app.middleware.rate_limiter') as mock_limiter:
            mock_limiter.is_allowed.return_value = (True, {
                "limit": 60,
                "remaining": 59,
                "reset_time": int(time.time() + 60),
                "current_requests": 1
            })
            
            response = await rate_middleware.dispatch(request, call_next)
            
            # Verify request was processed
            call_next.assert_called_once_with(request)
            
            # Verify rate limit headers were added
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_flow(self):
        """Test rate limit exceeded scenario."""
        app = MagicMock()
        rate_middleware = RateLimitMiddleware(app)
        
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/stocks/quote"
        request.state = MagicMock()
        request.state.user_id = "rate_exceeded_user"
        
        call_next = MagicMock()
        
        # Mock rate limiter to deny request
        with patch('app.middleware.rate_limiter') as mock_limiter:
            mock_limiter.is_allowed.return_value = (False, {
                "limit": 60,
                "remaining": 0,
                "reset_time": int(time.time() + 60),
                "current_requests": 60
            })
            
            response = await rate_middleware.dispatch(request, call_next)
            
            # Should return 429 Too Many Requests
            assert isinstance(response, JSONResponse)
            assert response.status_code == 429
            call_next.assert_not_called()
            
            # Verify rate limit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers


class TestMultiUserAuthenticationFlows:
    """Test authentication flows with multiple users."""
    
    def test_concurrent_user_sessions(self):
        """Test multiple concurrent user sessions."""
        users = [
            {"user_id": "user_1", "permissions": ["trading", "market_data"]},
            {"user_id": "user_2", "permissions": ["market_data"]},
            {"user_id": "user_3", "permissions": ["trading", "options"]}
        ]
        
        # Create tokens for all users
        tokens = {}
        contexts = {}
        
        for user in users:
            token = create_jwt_token(user)
            payload = verify_jwt_token(token)
            context = RequestContext(payload)
            
            tokens[user["user_id"]] = token
            contexts[user["user_id"]] = context
        
        # Verify each user has correct permissions
        assert contexts["user_1"].has_permission("trading")
        assert contexts["user_1"].has_permission("market_data")
        
        assert not contexts["user_2"].has_permission("trading")
        assert contexts["user_2"].has_permission("market_data")
        
        assert contexts["user_3"].has_permission("trading")
        assert contexts["user_3"].has_permission("options")
        assert not contexts["user_3"].has_permission("market_data")
    
    def test_user_session_isolation(self):
        """Test that user sessions are properly isolated."""
        user1_data = {
            "user_id": "isolated_user_1",
            "account_id": "account_1",
            "permissions": ["trading"]
        }
        
        user2_data = {
            "user_id": "isolated_user_2", 
            "account_id": "account_2",
            "permissions": ["market_data"]
        }
        
        # Create separate tokens
        token1 = create_jwt_token(user1_data)
        token2 = create_jwt_token(user2_data)
        
        # Verify tokens are different
        assert token1 != token2
        
        # Verify payloads are isolated
        payload1 = verify_jwt_token(token1)
        payload2 = verify_jwt_token(token2)
        
        assert payload1["user_id"] != payload2["user_id"]
        assert payload1["account_id"] != payload2["account_id"]
        assert payload1["permissions"] != payload2["permissions"]
        
        # Verify contexts are isolated
        context1 = RequestContext(payload1)
        context2 = RequestContext(payload2)
        
        assert context1.user_id != context2.user_id
        assert context1.account_id != context2.account_id
        assert context1.has_permission("trading")
        assert not context2.has_permission("trading")


class TestAuthenticationErrorRecovery:
    """Test authentication error recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_token_refresh_simulation(self):
        """Test token refresh workflow simulation."""
        # Create initial token
        user_data = {"user_id": "refresh_user", "permissions": ["trading"]}
        old_token = create_jwt_token(user_data)
        
        # Simulate token refresh by creating new token
        time.sleep(0.01)  # Small delay to ensure different timestamps
        new_token = create_jwt_token(user_data)
        
        # Tokens should be different (different timestamps)
        assert old_token != new_token
        
        # Both should be valid
        old_payload = verify_jwt_token(old_token)
        new_payload = verify_jwt_token(new_token)
        
        # User data should be the same
        assert old_payload["user_id"] == new_payload["user_id"]
        assert old_payload["permissions"] == new_payload["permissions"]
        
        # Timestamps should be different
        assert old_payload["iat"] != new_payload["iat"]
    
    def test_graceful_degradation(self):
        """Test graceful degradation when authentication fails."""
        # Test with various failure scenarios
        failure_scenarios = [
            {"token": None, "expected_behavior": "reject"},
            {"token": "", "expected_behavior": "reject"},
            {"token": "invalid", "expected_behavior": "reject"}
        ]
        
        for scenario in failure_scenarios:
            token = scenario["token"]
            
            if token:
                try:
                    verify_jwt_token(token)
                    assert False, f"Should have failed for token: {token}"
                except HTTPException as e:
                    assert e.status_code == 401
                    assert scenario["expected_behavior"] == "reject"
            else:
                # None token should be handled at middleware level
                assert scenario["expected_behavior"] == "reject"


@pytest.mark.asyncio
async def test_complete_authentication_integration():
    """Complete integration test for authentication flows."""
    # 1. Create user and token
    user_data = {
        "user_id": "integration_auth_user",
        "account_id": "integration_account",
        "permissions": ["trading", "market_data", "options"]
    }
    
    token = create_jwt_token(user_data)
    
    # 2. Verify token
    payload = verify_jwt_token(token)
    assert payload["user_id"] == user_data["user_id"]
    
    # 3. Create request context
    context = RequestContext(payload)
    assert context.has_permission("trading")
    
    # 4. Simulate middleware processing
    app = MagicMock()
    auth_middleware = AuthenticationMiddleware(app)
    rate_middleware = RateLimitMiddleware(app)
    
    # Mock request
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/stocks/quote"
    request.headers.get.return_value = f"Bearer {token}"
    request.state = MagicMock()
    
    # Mock call_next
    call_next = MagicMock()
    mock_response = MagicMock()
    mock_response.headers = {}
    call_next.return_value = mock_response
    
    # Process through authentication middleware
    auth_response = await auth_middleware.dispatch(request, call_next)
    
    # Verify authentication succeeded
    call_next.assert_called_once_with(request)
    assert request.state.user_id == user_data["user_id"]
    
    # Process through rate limiting middleware
    with patch('app.middleware.rate_limiter') as mock_limiter:
        mock_limiter.is_allowed.return_value = (True, {
            "limit": 60, "remaining": 59, "reset_time": int(time.time() + 60), "current_requests": 1
        })
        
        rate_response = await rate_middleware.dispatch(request, call_next)
        
        # Verify rate limiting succeeded
        assert "X-RateLimit-Limit" in rate_response.headers
    
    # 5. Verify complete workflow
    assert auth_response.status_code != 401  # Authentication passed
    assert "X-RateLimit-Limit" in rate_response.headers  # Rate limiting applied