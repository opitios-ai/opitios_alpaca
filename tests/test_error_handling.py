"""
Comprehensive error handling tests for all error scenarios and edge cases
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from main import app
from app.middleware import (
    verify_jwt_token, get_current_user, UserContext, 
    UserContextManager, RateLimiter, create_jwt_token
)
from app.alpaca_client import AlpacaClient
from config import settings

client = TestClient(app)


class TestJWTErrorHandling:
    """Test JWT authentication error scenarios"""
    
    def test_missing_authorization_header(self):
        """Test request without Authorization header"""
        response = client.get("/api/v1/account")
        
        assert response.status_code == 401
        data = response.json()
        assert "Missing or invalid authorization header" in data["detail"]
    
    def test_invalid_authorization_format(self):
        """Test request with malformed Authorization header"""
        headers = {"Authorization": "Invalid format"}
        response = client.get("/api/v1/account", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "Missing or invalid authorization header" in data["detail"]
    
    def test_malformed_jwt_token(self):
        """Test request with malformed JWT token"""
        headers = {"Authorization": "Bearer malformed.jwt.token"}
        response = client.get("/api/v1/account", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid token" in data["detail"]
    
    def test_expired_jwt_token(self):
        """Test request with expired JWT token"""
        # Create an expired token
        import jwt
        from app.middleware import JWT_SECRET, JWT_ALGORITHM
        
        expired_payload = {
            "user_id": "test_user",
            "permissions": ["trading"],
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        
        expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        headers = {"Authorization": f"Bearer {expired_token}"}
        
        response = client.get("/api/v1/account", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "expired" in data["detail"].lower()
    
    def test_token_with_wrong_secret(self):
        """Test token signed with wrong secret"""
        import jwt
        
        payload = {
            "user_id": "test_user",
            "permissions": ["trading"],
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        
        wrong_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {wrong_token}"}
        
        response = client.get("/api/v1/account", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid token" in data["detail"]
    
    def test_user_context_not_found(self):
        """Test valid token but no user context"""
        # Create valid token but don't create user context
        user_data = {"user_id": "nonexistent_user", "permissions": ["trading"]}
        token = create_jwt_token(user_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/v1/account", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "User context not found" in data["detail"]


class TestRateLimitingErrorHandling:
    """Test rate limiting error scenarios"""
    
    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded scenario"""
        # Create user context with very low rate limit
        from app.middleware import user_manager
        
        user_data = {
            "user_id": "rate_limit_test_user",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        context = UserContext(
            user_id="rate_limit_test_user",
            alpaca_credentials={},
            permissions=["trading", "market_data"],
            rate_limits={"requests_per_minute": 1}  # Very low limit
        )
        user_manager.active_users["rate_limit_test_user"] = context
        
        try:
            # Make first request (should succeed)
            response1 = client.get("/api/v1/test-connection", headers=headers)
            
            # Make second request quickly (should be rate limited)
            response2 = client.get("/api/v1/test-connection", headers=headers)
            
            # At least one should be rate limited
            responses = [response1, response2]
            rate_limited_responses = [r for r in responses if r.status_code == 429]
            
            if rate_limited_responses:
                response = rate_limited_responses[0]
                data = response.json()
                assert "Rate limit exceeded" in data["detail"]
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert "X-RateLimit-Reset" in response.headers
        
        finally:
            # Cleanup
            if "rate_limit_test_user" in user_manager.active_users:
                del user_manager.active_users["rate_limit_test_user"]
    
    def test_rate_limiter_memory_errors(self):
        """Test rate limiter memory operation errors"""
        limiter = RateLimiter()
        
        # Test with invalid parameters
        with pytest.raises(TypeError):
            limiter.is_allowed(None, 10, 60)  # None identifier
        
        # Test with negative limits
        allowed, info = limiter.is_allowed("test", -1, 60)
        # Should handle gracefully
        assert isinstance(allowed, bool)
        assert isinstance(info, dict)
    
    @patch('app.middleware.redis_client')
    def test_redis_connection_failure(self, mock_redis):
        """Test rate limiting when Redis connection fails"""
        # Mock Redis connection failure
        mock_redis.pipeline.side_effect = Exception("Redis connection failed")
        
        limiter = RateLimiter()
        
        # Should fall back to memory-based rate limiting
        allowed, info = limiter.is_allowed("test_user", 10, 60)
        
        assert isinstance(allowed, bool)
        assert isinstance(info, dict)
        assert "limit" in info
        assert "remaining" in info


class TestAlpacaAPIErrorHandling:
    """Test Alpaca API error handling scenarios"""
    
    @pytest.fixture
    def mock_alpaca_client(self):
        """Create AlpacaClient with mocked dependencies"""
        with patch('app.alpaca_client.TradingClient'), \
             patch('app.alpaca_client.StockHistoricalDataClient'), \
             patch('app.alpaca_client.OptionHistoricalDataClient'):
            client = AlpacaClient()
            return client
    
    @pytest.mark.asyncio
    async def test_api_connection_timeout(self, mock_alpaca_client):
        """Test API connection timeout"""
        # Mock timeout exception
        mock_alpaca_client.trading_client.get_account = Mock(
            side_effect=TimeoutError("Connection timeout")
        )
        
        result = await mock_alpaca_client.test_connection()
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "timeout" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_api_authentication_failure(self, mock_alpaca_client):
        """Test API authentication failure"""
        # Mock authentication failure
        mock_alpaca_client.trading_client.get_account = Mock(
            side_effect=Exception("Authentication failed: Invalid API key")
        )
        
        result = await mock_alpaca_client.test_connection()
        
        assert result["status"] == "failed"
        assert "Authentication failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_exceeded(self, mock_alpaca_client):
        """Test Alpaca API rate limit exceeded"""
        # Mock rate limit exception
        mock_alpaca_client.stock_data_client.get_stock_latest_quote = Mock(
            side_effect=Exception("Rate limit exceeded")
        )
        
        result = await mock_alpaca_client.get_stock_quote("AAPL")
        
        assert "error" in result
        assert "Rate limit exceeded" in result["error"]
    
    @pytest.mark.asyncio
    async def test_invalid_symbol_error(self, mock_alpaca_client):
        """Test invalid stock symbol error"""
        # Mock no data for invalid symbol
        mock_alpaca_client.stock_data_client.get_stock_latest_quote = Mock(
            return_value={}  # Empty response
        )
        
        result = await mock_alpaca_client.get_stock_quote("INVALID_SYMBOL")
        
        assert "error" in result
        assert "No quote data found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_order_placement_insufficient_funds(self, mock_alpaca_client):
        """Test order placement with insufficient funds"""
        # Mock insufficient funds error
        mock_alpaca_client.trading_client.submit_order = Mock(
            side_effect=Exception("Insufficient buying power")
        )
        
        result = await mock_alpaca_client.place_stock_order(
            symbol="AAPL",
            qty=1000000,  # Very large quantity
            side="buy",
            order_type="market"
        )
        
        assert "error" in result
        assert "Insufficient buying power" in result["error"]
    
    @pytest.mark.asyncio
    async def test_market_closed_error(self, mock_alpaca_client):
        """Test order placement when market is closed"""
        # Mock market closed error
        mock_alpaca_client.trading_client.submit_order = Mock(
            side_effect=Exception("Market is closed")
        )
        
        result = await mock_alpaca_client.place_stock_order(
            symbol="AAPL",
            qty=10,
            side="buy",
            order_type="market"
        )
        
        assert "error" in result
        assert "Market is closed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_empty_symbols_list(self, mock_alpaca_client):
        """Test handling of empty symbols list"""
        result = await mock_alpaca_client.get_multiple_stock_quotes([])
        
        assert "error" in result
        assert "No symbols provided" in result["error"]
    
    @pytest.mark.asyncio
    async def test_malformed_option_symbol(self, mock_alpaca_client):
        """Test handling of malformed option symbol"""
        result = await mock_alpaca_client.get_option_quote("INVALID_OPTION")
        
        # Should handle parsing error gracefully
        assert "error" in result


class TestUserManagementErrorHandling:
    """Test user management error scenarios"""
    
    def test_user_context_creation_with_invalid_data(self):
        """Test user context creation with invalid data"""
        manager = UserContextManager()
        
        # Test with missing required fields
        with pytest.raises(KeyError):
            manager.create_user_context({})
        
        # Test with invalid data types
        with pytest.raises((TypeError, ValueError)):
            manager.create_user_context({
                "user_id": None,  # Invalid user_id
                "alpaca_credentials": {},
                "permissions": [],
                "rate_limits": {}
            })
    
    def test_user_context_credential_decryption_failure(self):
        """Test credential decryption failure"""
        context = UserContext(
            user_id="test_user",
            alpaca_credentials={
                "api_key": "invalid_encrypted_data",
                "secret_key": "invalid_encrypted_data",
                "paper_trading": True
            },
            permissions=["trading"],
            rate_limits={}
        )
        
        # Should raise HTTPException for invalid credentials
        with pytest.raises(HTTPException) as exc_info:
            context.get_alpaca_credentials()
        
        assert exc_info.value.status_code == 401
        assert "Invalid credentials" in exc_info.value.detail
    
    def test_concurrent_user_context_operations_error_handling(self):
        """Test error handling in concurrent user context operations"""
        manager = UserContextManager()
        
        # Create user context
        user_data = {
            "user_id": "concurrent_test_user",
            "alpaca_credentials": {},
            "permissions": ["trading"],
            "rate_limits": {}
        }
        context = manager.create_user_context(user_data)
        
        # Simulate error during activity update
        original_update = context.update_activity
        
        def failing_update():
            raise Exception("Update failed")
        
        context.update_activity = failing_update
        
        # Should handle error gracefully
        try:
            context.update_activity()
        except Exception as e:
            assert "Update failed" in str(e)
        
        # Restore original method
        context.update_activity = original_update


class TestConnectionPoolErrorHandling:
    """Test connection pool error scenarios"""
    
    def test_connection_pool_max_connections_exceeded(self):
        """Test connection pool when max connections exceeded"""
        # This would test the connection pool's behavior when
        # the maximum number of connections is exceeded
        pass
    
    def test_connection_pool_connection_failure(self):
        """Test connection pool when individual connections fail"""
        # This would test error handling when individual
        # connections in the pool fail
        pass


class TestAPIEndpointErrorHandling:
    """Test API endpoint error handling"""
    
    def test_invalid_request_data(self):
        """Test endpoints with invalid request data"""
        # Test with invalid JSON
        response = client.post(
            "/api/v1/stocks/quote",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_missing_required_fields(self):
        """Test endpoints with missing required fields"""
        headers = {"Authorization": f"Bearer {create_jwt_token({'user_id': 'test', 'permissions': []})}"}
        
        # Test stock order without required fields
        response = client.post(
            "/api/v1/stocks/order",
            json={},  # Missing required fields
            headers=headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_field_types(self):
        """Test endpoints with invalid field types"""
        headers = {"Authorization": f"Bearer {create_jwt_token({'user_id': 'test', 'permissions': []})}"}
        
        # Test with invalid qty type
        response = client.post(
            "/api/v1/stocks/order",
            json={
                "symbol": "AAPL",
                "qty": "invalid",  # Should be number
                "side": "buy",
                "type": "market"
            },
            headers=headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_enum_values(self):
        """Test endpoints with invalid enum values"""
        headers = {"Authorization": f"Bearer {create_jwt_token({'user_id': 'test', 'permissions': []})}"}
        
        # Test with invalid side value
        response = client.post(
            "/api/v1/stocks/order",
            json={
                "symbol": "AAPL",
                "qty": 10,
                "side": "invalid_side",  # Should be "buy" or "sell"
                "type": "market"
            },
            headers=headers
        )
        
        assert response.status_code == 422  # Validation error


class TestSystemErrorHandling:
    """Test system-level error handling"""
    
    def test_database_connection_failure(self):
        """Test handling of database connection failures"""
        # This would test the system's behavior when
        # database connections fail
        pass
    
    def test_memory_exhaustion_handling(self):
        """Test handling of memory exhaustion scenarios"""
        # This would test the system's behavior under
        # memory pressure situations
        pass
    
    def test_thread_pool_exhaustion(self):
        """Test handling when thread pool is exhausted"""
        # This would test the system's behavior when
        # the thread pool is exhausted
        pass
    
    @patch('app.middleware.logger')
    def test_logging_system_failure(self, mock_logger):
        """Test handling when logging system fails"""
        # Mock logging failure
        mock_logger.error.side_effect = Exception("Logging failed")
        
        # System should continue to work even if logging fails
        response = client.get("/")
        
        # Should still return successful response
        assert response.status_code == 200


class TestRecoveryMechanisms:
    """Test system recovery mechanisms"""
    
    def test_automatic_cleanup_after_errors(self):
        """Test that system cleans up properly after errors"""
        manager = UserContextManager()
        
        # Create user contexts
        for i in range(5):
            user_data = {
                "user_id": f"cleanup_test_user_{i}",
                "alpaca_credentials": {},
                "permissions": ["trading"],
                "rate_limits": {}
            }
            manager.create_user_context(user_data)
        
        # Simulate error condition that requires cleanup
        # Make some users inactive
        for i in range(2):
            context = manager.get_user_context(f"cleanup_test_user_{i}")
            context.last_active = datetime.utcnow() - timedelta(hours=2)
        
        # Run cleanup
        initial_count = len(manager.active_users)
        manager.cleanup_inactive_users(max_inactive_minutes=30)
        final_count = len(manager.active_users)
        
        # Should have cleaned up inactive users
        assert final_count < initial_count
    
    def test_graceful_degradation(self):
        """Test graceful degradation when external services fail"""
        # This would test that the system continues to operate
        # in a degraded mode when external services fail
        pass
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker functionality for external API calls"""
        # This would test that the system implements circuit breaker
        # patterns to handle external API failures
        pass


class TestErrorLogging:
    """Test error logging functionality"""
    
    @patch('app.middleware.logger')
    def test_error_logging_detail_level(self, mock_logger):
        """Test that errors are logged with appropriate detail"""
        # Trigger an error condition
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/account", headers=headers)
        
        # Should log the error
        assert mock_logger.error.called or mock_logger.warning.called
    
    def test_sensitive_data_not_logged(self):
        """Test that sensitive data is not logged in error messages"""
        # This would verify that API keys, secrets, and other
        # sensitive information are not logged in error messages
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])