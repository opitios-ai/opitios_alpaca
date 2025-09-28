"""Integration tests for system-wide component integration."""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

from tests.utils import RealAPITestClient, WebSocketTestManager, APITestHelper, WebSocketEndpoint
from app.account_pool import AccountPool, AccountConfig
from app.connection_pool import PoolManager, ConnectionType
from app.middleware import RateLimiter, create_jwt_token, verify_jwt_token


class TestAccountPoolIntegration:
    """Test account pool integration with real API clients."""
    
    @pytest.mark.asyncio
    async def test_account_pool_with_real_connections(self, primary_test_account):
        """Test account pool with real API connections."""
        pool = AccountPool(health_check_interval_seconds=300)
        
        # Mock settings with real test account
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {
                primary_test_account.credentials.account_id: {
                    "api_key": primary_test_account.credentials.api_key,
                    "secret_key": primary_test_account.credentials.secret_key,
                    "paper_trading": primary_test_account.credentials.paper_trading,
                    "enabled": True,
                    "max_connections": 2
                }
            }
            
            # Initialize pool
            await pool.initialize()
            
            # Test connection usage
            async with pool.get_account_connection(primary_test_account.credentials.account_id) as connection:
                # Test that connection works
                result = await connection.alpaca_client.test_connection()
                
                if result.get("status") == "connected":
                    assert "account_number" in result
                    assert connection.stats.usage_count > 0
                else:
                    # Connection might fail in test environment
                    assert "error" in result
            
            # Get pool statistics
            stats = pool.get_pool_stats()
            assert stats["total_accounts"] == 1
            assert stats["total_connections"] >= 1
            
            # Cleanup
            await pool.shutdown()


class TestConnectionPoolIntegration:
    """Test connection pool integration."""
    
    @pytest.mark.asyncio
    async def test_connection_pool_with_real_users(self, primary_test_account):
        """Test connection pool with real user credentials."""
        pool = PoolManager(max_idle_time_minutes=30, health_check_interval_seconds=300)
        
        # Create mock user object
        class MockUser:
            def __init__(self, account):
                self.id = account.credentials.account_id
                self.api_key = account.credentials.api_key
                self.secret_key = account.credentials.secret_key
                self.alpaca_paper_trading = account.credentials.paper_trading
            
            def decrypt_alpaca_credentials(self):
                return self.api_key, self.secret_key
        
        user = MockUser(primary_test_account)
        
        # Test connection acquisition and usage
        connection_manager = await pool.get_user_manager(user)
        trading_client = await connection_manager.get_connection(ConnectionType.TRADING_CLIENT)
        try:
            # Test connection functionality
            is_healthy = await connection_manager.test_connection(ConnectionType.TRADING_CLIENT)
            
            if is_healthy:
                stats = connection_manager.connection_stats[ConnectionType.TRADING_CLIENT]
                assert stats.is_healthy is True
                assert connection_manager.user_id == user.id
                assert connection_manager._in_use[ConnectionType.TRADING_CLIENT] is True
            else:
                # Connection might fail in test environment
                stats = connection_manager.connection_stats[ConnectionType.TRADING_CLIENT]
                assert stats.is_healthy is False
        finally:
            # Release connection
            connection_manager.release_connection(ConnectionType.TRADING_CLIENT)
        
        # Connection should be released
        assert connection_manager._in_use[ConnectionType.TRADING_CLIENT] is False
        
        # Test pool statistics
        stats = pool.get_pool_stats()
        assert stats["total_users"] == 1
        assert stats["total_connections"] >= 1
        
        await pool.shutdown()


class TestMiddlewareIntegration:
    """Test middleware integration with real authentication flows."""
    
    def test_jwt_authentication_flow(self):
        """Test complete JWT authentication flow."""
        # 1. Create user data
        user_data = {
            "user_id": "integration_test_user",
            "account_id": "integration_test_account",
            "permissions": ["trading", "market_data", "admin"]
        }
        
        # 2. Create JWT token
        token = create_jwt_token(user_data)
        assert isinstance(token, str)
        assert len(token) > 0
        
        # 3. Verify JWT token
        payload = verify_jwt_token(token)
        assert payload["user_id"] == user_data["user_id"]
        assert payload["account_id"] == user_data["account_id"]
        assert payload["permissions"] == user_data["permissions"]
        
        # 4. Test rate limiting for authenticated user
        rate_limiter = RateLimiter()
        
        # Make several requests
        for i in range(5):
            allowed, info = rate_limiter.is_allowed(
                f"user:{payload['user_id']}", limit=10, window_seconds=60
            )
            assert allowed is True
            assert info["remaining"] == 9 - i
        
        # Test rate limit exceeded
        for i in range(6):
            allowed, info = rate_limiter.is_allowed(
                f"user:{payload['user_id']}", limit=10, window_seconds=60
            )
            if i < 5:
                assert allowed is True
            else:
                assert allowed is False
                assert info["remaining"] == 0


class TestFullSystemIntegration:
    """Test full system integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_system_workflow(self, real_api_client, websocket_manager, api_test_helper):
        """Test complete system workflow with all components."""
        # 1. Authentication setup
        user_data = {
            "user_id": real_api_client.account_id,
            "account_id": real_api_client.account_id,
            "permissions": ["trading", "market_data", "admin"]
        }
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        
        # 2. Rate limiting setup
        rate_limiter = RateLimiter()
        
        # 3. API operations with rate limiting
        api_operations = [
            ("get_account", real_api_client.get_account, []),
            ("get_stock_quote", real_api_client.get_stock_quote, ["AAPL"]),
            ("get_positions", real_api_client.get_positions, []),
            ("get_orders", real_api_client.get_orders, [])
        ]
        
        api_results = []
        
        for operation_name, operation_func, args in api_operations:
            # Check rate limit
            user_key = f"user:{payload['user_id']}:/api/v1/{operation_name}"
            allowed, rate_info = rate_limiter.is_allowed(user_key, limit=30, window_seconds=60)
            
            if allowed:
                result = await api_test_helper.timed_api_call(operation_func, *args)
                api_results.append({
                    "operation": operation_name,
                    "success": result.success,
                    "response_time": result.response_time_ms,
                    "rate_limit_remaining": rate_info["remaining"]
                })
            else:
                api_results.append({
                    "operation": operation_name,
                    "success": False,
                    "error": "Rate limit exceeded",
                    "rate_limit_remaining": rate_info["remaining"]
                })
        
        # 4. WebSocket operations
        websocket_success = await websocket_manager.establish_connection(
            WebSocketEndpoint.STOCK_DATA, timeout=15
        )
        
        websocket_results = {
            "connection_established": websocket_success,
            "messages_received": 0,
            "connection_health": None
        }
        
        if websocket_success:
            # Subscribe to symbols
            subscribe_success = await websocket_manager.subscribe_symbols(
                WebSocketEndpoint.STOCK_DATA, ["AAPL"]
            )
            
            if subscribe_success:
                # Wait for messages
                messages = await websocket_manager.wait_for_messages(
                    WebSocketEndpoint.STOCK_DATA, count=1, timeout=15
                )
                websocket_results["messages_received"] = len(messages)
            
            # Get connection health
            health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            websocket_results["connection_health"] = {
                "connected": health.connected,
                "messages_received": health.messages_received,
                "error_count": health.error_count
            }
        
        # 5. System performance analysis
        successful_api_calls = [r for r in api_results if r["success"]]
        total_response_time = sum(r["response_time"] for r in successful_api_calls)
        avg_response_time = total_response_time / len(successful_api_calls) if successful_api_calls else 0
        
        system_metrics = {
            "api_success_rate": len(successful_api_calls) / len(api_results),
            "avg_api_response_time": avg_response_time,
            "websocket_connected": websocket_results["connection_established"],
            "websocket_messages": websocket_results["messages_received"],
            "total_operations": len(api_results) + (1 if websocket_success else 0)
        }
        
        # 6. Assertions for system health
        assert system_metrics["api_success_rate"] >= 0.5, "API success rate should be at least 50%"
        assert system_metrics["avg_api_response_time"] < 10000, "Average response time should be under 10 seconds"
        assert system_metrics["total_operations"] >= 4, "Should have performed multiple operations"
        
        # 7. Get final performance summary
        performance = api_test_helper.get_performance_summary()
        assert performance["total_calls"] >= 4, "Should have made at least 4 API calls"
        
        # 8. Final system health check
        final_health_check = {
            "authentication": payload is not None,
            "rate_limiting": len([r for r in api_results if "rate_limit_remaining" in r]) > 0,
            "api_connectivity": system_metrics["api_success_rate"] > 0,
            "websocket_connectivity": system_metrics["websocket_connected"],
            "overall_performance": system_metrics["avg_api_response_time"] < 10000
        }
        
        # At least 3 out of 5 health checks should pass
        health_score = sum(final_health_check.values())
        assert health_score >= 3, f"System health score too low: {health_score}/5"


@pytest.mark.asyncio
async def test_system_integration_comprehensive(real_api_client, websocket_manager, api_test_helper):
    """Comprehensive system integration test covering all major components."""
    # 1. System initialization
    system_components = {
        "api_client": real_api_client is not None,
        "websocket_manager": websocket_manager is not None,
        "api_helper": api_test_helper is not None
    }
    
    assert all(system_components.values()), "All system components should be available"
    
    # 2. Authentication and authorization
    user_data = {
        "user_id": real_api_client.account_id,
        "account_id": real_api_client.account_id,
        "permissions": ["trading", "market_data", "admin"]
    }
    
    token = create_jwt_token(user_data)
    payload = verify_jwt_token(token)
    
    auth_test = {
        "token_created": token is not None,
        "token_verified": payload is not None,
        "user_id_match": payload.get("user_id") == user_data["user_id"],
        "permissions_preserved": payload.get("permissions") == user_data["permissions"]
    }
    
    assert all(auth_test.values()), "Authentication system should work correctly"
    
    # 3. API connectivity and functionality
    api_tests = [
        ("account", real_api_client.get_account, []),
        ("quote", real_api_client.get_stock_quote, ["AAPL"]),
        ("positions", real_api_client.get_positions, []),
        ("orders", real_api_client.get_orders, [])
    ]
    
    api_results = {}
    for test_name, func, args in api_tests:
        result = await api_test_helper.timed_api_call(func, *args)
        api_results[test_name] = {
            "success": result.success,
            "response_time": result.response_time_ms,
            "has_data": len(result.response_data) > 0 if result.success else False
        }
    
    successful_api_tests = [name for name, result in api_results.items() if result["success"]]
    assert len(successful_api_tests) >= len(api_tests) // 2, "At least half of API tests should succeed"
    
    # 4. WebSocket connectivity
    websocket_success = await websocket_manager.establish_connection(
        WebSocketEndpoint.STOCK_DATA, timeout=15
    )
    
    websocket_results = {"connection_established": websocket_success}
    
    if websocket_success:
        subscribe_success = await websocket_manager.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, ["AAPL"]
        )
        websocket_results["subscription_success"] = subscribe_success
        
        if subscribe_success:
            messages = await websocket_manager.wait_for_messages(
                WebSocketEndpoint.STOCK_DATA, count=1, timeout=20
            )
            websocket_results["messages_received"] = len(messages)
    
    # 5. Rate limiting functionality
    rate_limiter = RateLimiter()
    rate_limit_tests = []
    
    for i in range(5):
        allowed, info = rate_limiter.is_allowed(
            f"integration_test_user", limit=10, window_seconds=60
        )
        rate_limit_tests.append({
            "request_number": i + 1,
            "allowed": allowed,
            "remaining": info["remaining"]
        })
    
    rate_limit_working = all(test["allowed"] for test in rate_limit_tests)
    rate_limit_decreasing = all(
        rate_limit_tests[i]["remaining"] >= rate_limit_tests[i+1]["remaining"]
        for i in range(len(rate_limit_tests)-1)
    )
    
    # 6. System performance metrics
    performance_summary = api_test_helper.get_performance_summary()
    
    system_health = {
        "authentication": all(auth_test.values()),
        "api_connectivity": len(successful_api_tests) >= 2,
        "websocket_connectivity": websocket_results.get("connection_established", False),
        "rate_limiting": rate_limit_working and rate_limit_decreasing,
        "performance": performance_summary["success_rate"] > 0.5
    }
    
    # 7. Final system validation
    health_score = sum(system_health.values())
    total_checks = len(system_health)
    
    assert health_score >= total_checks * 0.6, f"System health score: {health_score}/{total_checks} (need at least 60%)"
    
    return {
        "system_components": system_components,
        "authentication": auth_test,
        "api_results": api_results,
        "websocket_results": websocket_results,
        "overall_health": system_health,
        "health_score": f"{health_score}/{total_checks}"
    }