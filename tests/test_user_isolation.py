"""
Multi-user scenario tests to ensure proper user isolation and context management
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from main import app
from app.middleware import (
    UserContext, UserContextManager, create_jwt_token, 
    RateLimiter, user_manager
)
from app.connection_pool import ConnectionPool

client = TestClient(app)


class TestUserContextIsolation:
    """Test user context isolation between different users"""
    
    def test_multiple_user_contexts_creation(self):
        """Test creating multiple user contexts simultaneously"""
        manager = UserContextManager()
        
        # Create multiple users
        users_data = []
        for i in range(5):
            user_data = {
                "user_id": f"test_user_{i}",
                "alpaca_credentials": {
                    "api_key": f"test_api_key_{i}",
                    "secret_key": f"test_secret_key_{i}",
                    "paper_trading": True
                },
                "permissions": ["trading", "market_data"],
                "rate_limits": {"requests_per_minute": 120 + i * 10}
            }
            users_data.append(user_data)
            context = manager.create_user_context(user_data)
            assert context.user_id == f"test_user_{i}"
        
        # Verify all contexts exist and are isolated
        for i, user_data in enumerate(users_data):
            context = manager.get_user_context(f"test_user_{i}")
            assert context is not None
            assert context.user_id == f"test_user_{i}"
            assert context.rate_limits["requests_per_minute"] == 120 + i * 10
            
            # Verify credentials are isolated
            creds = context.alpaca_credentials
            assert creds["api_key"] == f"test_api_key_{i}"
            assert creds["secret_key"] == f"test_secret_key_{i}"
    
    def test_user_context_activity_isolation(self):
        """Test that user activity updates don't affect other users"""
        manager = UserContextManager()
        
        # Create two users
        user1_data = {
            "user_id": "user1",
            "alpaca_credentials": {},
            "permissions": ["trading"],
            "rate_limits": {}
        }
        user2_data = {
            "user_id": "user2",
            "alpaca_credentials": {},
            "permissions": ["market_data"],
            "rate_limits": {}
        }
        
        context1 = manager.create_user_context(user1_data)
        context2 = manager.create_user_context(user2_data)
        
        # Record initial states
        initial_count1 = context1.request_count
        initial_count2 = context2.request_count
        initial_time1 = context1.last_active
        initial_time2 = context2.last_active
        
        # Update activity for user1 only
        time.sleep(0.01)  # Small delay to ensure time difference
        context1.update_activity()
        
        # Verify user1 updated but user2 unchanged
        assert context1.request_count == initial_count1 + 1
        assert context1.last_active > initial_time1
        assert context2.request_count == initial_count2
        assert context2.last_active == initial_time2
    
    def test_user_permissions_isolation(self):
        """Test that user permissions are properly isolated"""
        manager = UserContextManager()
        
        # Create users with different permissions
        admin_data = {
            "user_id": "admin_user",
            "alpaca_credentials": {},
            "permissions": ["trading", "market_data", "admin"],
            "rate_limits": {}
        }
        user_data = {
            "user_id": "regular_user",
            "alpaca_credentials": {},
            "permissions": ["trading"],
            "rate_limits": {}
        }
        
        admin_context = manager.create_user_context(admin_data)
        user_context = manager.create_user_context(user_data)
        
        # Test permission isolation
        assert admin_context.has_permission("admin") is True
        assert admin_context.has_permission("trading") is True
        assert admin_context.has_permission("market_data") is True
        
        assert user_context.has_permission("admin") is False
        assert user_context.has_permission("trading") is True
        assert user_context.has_permission("market_data") is False
    
    def test_concurrent_user_context_operations(self):
        """Test concurrent operations on user contexts"""
        manager = UserContextManager()
        
        def create_and_update_user(user_id):
            """Helper function to create and update user context"""
            user_data = {
                "user_id": user_id,
                "alpaca_credentials": {},
                "permissions": ["trading"],
                "rate_limits": {}
            }
            
            context = manager.create_user_context(user_data)
            
            # Perform multiple updates
            for _ in range(10):
                context.update_activity()
                time.sleep(0.001)  # Small delay
            
            return context.request_count
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(5):
                future = executor.submit(create_and_update_user, f"concurrent_user_{i}")
                futures.append(future)
            
            results = [future.result() for future in futures]
        
        # Verify all operations completed successfully
        assert all(count == 10 for count in results)
        
        # Verify all contexts exist and are isolated
        for i in range(5):
            context = manager.get_user_context(f"concurrent_user_{i}")
            assert context is not None
            assert context.request_count == 10


class TestRateLimitingIsolation:
    """Test rate limiting isolation between users"""
    
    def test_rate_limit_per_user_isolation(self):
        """Test that rate limits are enforced per user independently"""
        limiter = RateLimiter()
        limit = 3
        window_seconds = 60
        
        # User 1 hits their limit
        for i in range(limit):
            allowed, _ = limiter.is_allowed("user1", limit, window_seconds)
            assert allowed is True
        
        # User 1 should now be blocked
        allowed, _ = limiter.is_allowed("user1", limit, window_seconds)
        assert allowed is False
        
        # User 2 should still be allowed (independent limit)
        allowed, info = limiter.is_allowed("user2", limit, window_seconds)
        assert allowed is True
        assert info["remaining"] == limit - 1
        
        # User 3 should also be allowed
        allowed, info = limiter.is_allowed("user3", limit, window_seconds)
        assert allowed is True
        assert info["remaining"] == limit - 1
    
    def test_concurrent_rate_limiting(self):
        """Test rate limiting under concurrent access"""
        limiter = RateLimiter()
        limit = 10
        window_seconds = 60
        
        def make_requests(user_id, num_requests):
            """Helper function to make multiple requests for a user"""
            allowed_count = 0
            denied_count = 0
            
            for _ in range(num_requests):
                allowed, _ = limiter.is_allowed(user_id, limit, window_seconds)
                if allowed:
                    allowed_count += 1
                else:
                    denied_count += 1
                time.sleep(0.001)  # Small delay
            
            return allowed_count, denied_count
        
        # Run concurrent requests for multiple users
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(3):
                future = executor.submit(make_requests, f"user_{i}", 15)
                futures.append(future)
            
            results = [future.result() for future in futures]
        
        # Each user should be allowed exactly 'limit' requests
        for allowed_count, denied_count in results:
            assert allowed_count == limit
            assert denied_count == 5  # 15 - 10 = 5 denied
    
    def test_rate_limit_window_isolation(self):
        """Test that rate limit windows are isolated per user"""
        limiter = RateLimiter()
        limit = 2
        window_seconds = 1
        
        # User 1 fills their limit
        allowed1, _ = limiter.is_allowed("user1", limit, window_seconds)
        allowed2, _ = limiter.is_allowed("user1", limit, window_seconds)
        allowed3, _ = limiter.is_allowed("user1", limit, window_seconds)
        
        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is False
        
        # User 2 should still be allowed despite user 1's limit
        allowed4, _ = limiter.is_allowed("user2", limit, window_seconds)
        allowed5, _ = limiter.is_allowed("user2", limit, window_seconds)
        assert allowed4 is True
        assert allowed5 is True
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Both users should be allowed again
        allowed6, _ = limiter.is_allowed("user1", limit, window_seconds)
        allowed7, _ = limiter.is_allowed("user2", limit, window_seconds)
        assert allowed6 is True
        assert allowed7 is True


class TestConnectionPoolIsolation:
    """Test connection pool isolation between users"""
    
    @pytest.fixture
    def connection_pool(self):
        """Create a connection pool for testing"""
        return ConnectionPool(max_connections_per_user=3)
    
    def test_connection_allocation_per_user(self, connection_pool):
        """Test that connections are allocated per user"""
        # This test would verify that each user gets their own 
        # connection allocation in the pool
        pass
    
    def test_connection_limits_per_user(self, connection_pool):
        """Test that connection limits are enforced per user"""
        # This test would verify that one user hitting their
        # connection limit doesn't affect other users
        pass


class TestMultiUserScenarios:
    """Test realistic multi-user scenarios"""
    
    @patch('app.user_manager.get_user_manager')
    def test_multiple_users_login_simultaneously(self, mock_get_manager):
        """Test multiple users logging in at the same time"""
        # Mock user manager
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Create mock users
        users = []
        for i in range(3):
            mock_user = Mock()
            mock_user.id = f"user_{i}"
            mock_user.username = f"testuser_{i}"
            mock_user.email = f"test{i}@example.com"
            mock_user.role = "user"
            mock_user.status = "active"
            mock_user.permissions = {"trading": True}
            mock_user.rate_limits = {"requests_per_minute": 120}
            mock_user.alpaca_paper_trading = True
            mock_user.total_requests = 0
            mock_user.total_orders = 0
            mock_user.last_login = None
            mock_user.created_at = datetime.utcnow()
            users.append(mock_user)
        
        mock_manager.authenticate_user.side_effect = users
        
        # Simulate concurrent logins
        def login_user(user_index):
            login_data = {
                "username": f"testuser_{user_index}",
                "password": "testpass123"
            }
            response = client.post("/api/v1/auth/login", json=login_data)
            return response.status_code, response.json()
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(3):
                future = executor.submit(login_user, i)
                futures.append(future)
            
            results = [future.result() for future in futures]
        
        # All logins should succeed
        for status_code, response_data in results:
            assert status_code == 200
            assert "access_token" in response_data
            assert "user" in response_data
    
    def test_user_session_cleanup_isolation(self):
        """Test that cleaning up one user's session doesn't affect others"""
        manager = UserContextManager()
        
        # Create multiple users
        active_users = []
        inactive_users = []
        
        for i in range(3):
            user_data = {
                "user_id": f"active_user_{i}",
                "alpaca_credentials": {},
                "permissions": ["trading"],
                "rate_limits": {}
            }
            context = manager.create_user_context(user_data)
            active_users.append(context)
        
        for i in range(2):
            user_data = {
                "user_id": f"inactive_user_{i}",
                "alpaca_credentials": {},
                "permissions": ["trading"],
                "rate_limits": {}
            }
            context = manager.create_user_context(user_data)
            # Make user inactive
            context.last_active = datetime.utcnow() - timedelta(hours=1)
            inactive_users.append(context)
        
        # Run cleanup
        manager.cleanup_inactive_users(max_inactive_minutes=30)
        
        # Verify active users remain
        for user in active_users:
            assert manager.get_user_context(user.user_id) is not None
        
        # Verify inactive users are removed
        for user in inactive_users:
            assert manager.get_user_context(user.user_id) is None
    
    def test_cross_user_data_leakage_prevention(self):
        """Test that user data doesn't leak between users"""
        manager = UserContextManager()
        
        # Create users with sensitive data
        user1_data = {
            "user_id": "user1",
            "alpaca_credentials": {
                "api_key": "secret_key_user1",
                "secret_key": "very_secret_user1",
                "paper_trading": True
            },
            "permissions": ["trading", "admin"],
            "rate_limits": {"requests_per_minute": 200}
        }
        
        user2_data = {
            "user_id": "user2",
            "alpaca_credentials": {
                "api_key": "secret_key_user2",
                "secret_key": "very_secret_user2",
                "paper_trading": False
            },
            "permissions": ["trading"],
            "rate_limits": {"requests_per_minute": 100}
        }
        
        context1 = manager.create_user_context(user1_data)
        context2 = manager.create_user_context(user2_data)
        
        # Verify data isolation
        assert context1.alpaca_credentials["api_key"] != context2.alpaca_credentials["api_key"]
        assert context1.alpaca_credentials["secret_key"] != context2.alpaca_credentials["secret_key"]
        assert context1.permissions != context2.permissions
        assert context1.rate_limits != context2.rate_limits
        
        # Verify no cross-contamination after operations
        context1.update_activity()
        context2.update_activity()
        
        # Data should still be isolated
        assert context1.alpaca_credentials["api_key"] == "secret_key_user1"
        assert context2.alpaca_credentials["api_key"] == "secret_key_user2"


class TestUserIsolationIntegration:
    """Integration tests for user isolation across the entire system"""
    
    def test_end_to_end_user_isolation(self):
        """Test user isolation from authentication to API calls"""
        # This would test the complete flow:
        # 1. Multiple users authenticate
        # 2. Make concurrent API calls
        # 3. Verify rate limiting is per-user
        # 4. Verify data isolation
        # 5. Verify cleanup works correctly
        pass
    
    def test_memory_isolation_under_load(self):
        """Test memory isolation under high load"""
        # This would test that under high concurrent load,
        # user data doesn't get mixed up in memory
        pass
    
    def test_error_isolation(self):
        """Test that errors for one user don't affect others"""
        # This would test that if one user encounters an error,
        # it doesn't impact other users' sessions or data
        pass


class TestScalabilityAndPerformance:
    """Test scalability with multiple users"""
    
    def test_many_concurrent_users(self):
        """Test system behavior with many concurrent users"""
        manager = UserContextManager()
        
        # Create many users
        num_users = 100
        users = []
        
        start_time = time.time()
        
        for i in range(num_users):
            user_data = {
                "user_id": f"scale_test_user_{i}",
                "alpaca_credentials": {},
                "permissions": ["trading"],
                "rate_limits": {}
            }
            context = manager.create_user_context(user_data)
            users.append(context)
        
        creation_time = time.time() - start_time
        
        # Verify all users were created successfully
        assert len(manager.active_users) == num_users
        
        # Test concurrent operations
        def update_user_activity(context):
            for _ in range(10):
                context.update_activity()
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_user_activity, user) for user in users]
            for future in futures:
                future.result()
        
        update_time = time.time() - start_time
        
        # Verify all users are still properly isolated
        for i, context in enumerate(users):
            assert context.user_id == f"scale_test_user_{i}"
            assert context.request_count == 10
        
        # Performance should be reasonable
        assert creation_time < 5.0  # Should create 100 users in less than 5 seconds
        assert update_time < 10.0   # Should update all users in less than 10 seconds
    
    def test_memory_usage_with_many_users(self):
        """Test memory usage doesn't grow excessively with many users"""
        # This would monitor memory usage as users are created
        # and perform operations to ensure no memory leaks
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])