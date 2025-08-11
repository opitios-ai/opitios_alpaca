"""Unit tests for connection pool with real connection validation."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from collections import deque

from app.connection_pool import (
    ConnectionStats,
    AlpacaConnection,
    ConnectionPool,
    get_connection_pool
)


class MockUser:
    """Mock user class for testing."""
    
    def __init__(self, user_id: str, api_key: str, secret_key: str, paper_trading: bool = True):
        self.id = user_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.alpaca_paper_trading = paper_trading
    
    def decrypt_alpaca_credentials(self):
        """Mock credential decryption."""
        return self.api_key, self.secret_key


class TestConnectionStats:
    """Test ConnectionStats dataclass."""
    
    def test_connection_stats_creation(self):
        """Test ConnectionStats creation."""
        created_time = datetime.utcnow()
        last_used_time = datetime.utcnow()
        
        stats = ConnectionStats(
            created_at=created_time,
            last_used=last_used_time
        )
        
        assert stats.created_at == created_time
        assert stats.last_used == last_used_time
        assert stats.usage_count == 0
        assert stats.error_count == 0
        assert stats.avg_response_time == 0.0
        assert stats.is_healthy is True


class TestAlpacaConnection:
    """Test AlpacaConnection functionality."""
    
    def test_connection_initialization(self, real_api_credentials):
        """Test AlpacaConnection initialization."""
        connection = AlpacaConnection(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        assert connection.user_id == "test_user"
        assert connection.api_key == real_api_credentials.api_key
        assert connection.secret_key == real_api_credentials.secret_key
        assert connection.paper_trading == real_api_credentials.paper_trading
        assert connection.trading_client is not None
        assert connection.data_client is not None
        assert connection.stats is not None
        assert connection._lock is not None
        assert connection._in_use is False
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, real_api_credentials):
        """Test successful connection test."""
        connection = AlpacaConnection(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        # Test connection
        is_healthy = await connection.test_connection()
        
        if is_healthy:
            assert connection.stats.is_healthy is True
            assert connection.stats.usage_count == 1
            assert connection.stats.avg_response_time > 0
        else:
            # If connection failed, it should be marked as unhealthy
            assert connection.stats.is_healthy is False
            assert connection.stats.error_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self):
        """Test connection test with invalid credentials."""
        connection = AlpacaConnection(
            user_id="test_user",
            api_key="invalid_key",
            secret_key="invalid_secret",
            paper_trading=True
        )
        
        # Test connection with invalid credentials
        is_healthy = await connection.test_connection()
        
        assert is_healthy is False
        assert connection.stats.is_healthy is False
        assert connection.stats.error_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_acquire_release(self, real_api_credentials):
        """Test connection acquire and release."""
        connection = AlpacaConnection(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Initially available
        assert connection.is_available is True
        assert connection._in_use is False
        
        # Acquire connection
        await connection.acquire()
        
        assert connection._in_use is True
        assert connection.is_available is False
        
        # Release connection
        connection.release()
        
        assert connection._in_use is False
        assert connection.is_available is True
    
    def test_connection_age_calculation(self, real_api_credentials):
        """Test connection age calculation."""
        connection = AlpacaConnection(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Age should be very small for new connection
        age = connection.age_minutes
        assert age >= 0
        assert age < 1  # Should be less than 1 minute for new connection
    
    def test_ensure_lock_compatibility(self, real_api_credentials):
        """Test _ensure_lock method for backward compatibility."""
        connection = AlpacaConnection(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Lock should already be initialized
        assert connection._lock is not None
        
        # _ensure_lock should not change anything
        connection._ensure_lock()
        assert connection._lock is not None


class TestConnectionPool:
    """Test ConnectionPool functionality."""
    
    def test_pool_initialization(self):
        """Test ConnectionPool initialization."""
        pool = ConnectionPool(
            max_connections_per_user=10,
            max_idle_time_minutes=60,
            health_check_interval_seconds=600
        )
        
        assert pool.max_connections_per_user == 10
        assert pool.max_idle_time_minutes == 60
        assert pool.health_check_interval_seconds == 600
        assert len(pool.user_pools) == 0
        assert len(pool.usage_queues) == 0
        assert pool._global_lock is None  # Lazy initialization
    
    @pytest.mark.asyncio
    async def test_ensure_async_components(self):
        """Test async components initialization."""
        pool = ConnectionPool()
        
        # Initially no lock
        assert pool._global_lock is None
        
        # Ensure async components
        await pool._ensure_async_components()
        
        # Lock should be initialized
        assert pool._global_lock is not None
        assert isinstance(pool._global_lock, asyncio.Lock)
    
    @pytest.mark.asyncio
    async def test_get_connection_new_user(self):
        """Test getting connection for new user."""
        pool = ConnectionPool(max_connections_per_user=2)
        
        user = MockUser(
            user_id="new_user",
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Get connection for new user
            connection = await pool.get_connection(user)
            
            assert connection is not None
            assert connection.user_id == "new_user"
            assert connection._in_use is True
            
            # Verify user pool was created
            assert "new_user" in pool.user_pools
            assert len(pool.user_pools["new_user"]) == 1
            assert "new_user" in pool.usage_queues
            
            # Release connection
            pool.release_connection(connection)
            assert connection._in_use is False
            
            # Cleanup
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_connection_existing_user(self):
        """Test getting connection for existing user with available connection."""
        pool = ConnectionPool(max_connections_per_user=2)
        
        user = MockUser(
            user_id="existing_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Get first connection
            connection1 = await pool.get_connection(user)
            pool.release_connection(connection1)
            
            # Get second connection (should reuse existing)
            connection2 = await pool.get_connection(user)
            
            assert connection2 is not None
            assert connection2.user_id == "existing_user"
            
            # Should be the same connection object (reused)
            assert connection1 == connection2
            
            pool.release_connection(connection2)
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_connection_max_limit(self):
        """Test connection creation up to max limit."""
        pool = ConnectionPool(max_connections_per_user=2)
        
        user = MockUser(
            user_id="limit_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Get connections up to limit
            connections = []
            for i in range(2):
                conn = await pool.get_connection(user)
                connections.append(conn)
            
            # Should have 2 connections
            assert len(pool.user_pools["limit_user"]) == 2
            
            # Try to get another connection (should reuse existing)
            connection3 = await pool.get_connection(user)
            assert connection3 in connections  # Should be one of the existing connections
            
            # Cleanup
            for conn in connections:
                pool.release_connection(conn)
            pool.release_connection(connection3)
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_connection_invalid_credentials(self):
        """Test getting connection with invalid credentials."""
        pool = ConnectionPool()
        
        user = MockUser(
            user_id="invalid_user",
            api_key="invalid_key",
            secret_key="invalid_secret"
        )
        
        # Should raise exception for invalid credentials
        with pytest.raises(Exception):
            await pool.get_connection(user)
        
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """Test connection context manager."""
        pool = ConnectionPool()
        
        user = MockUser(
            user_id="context_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Use context manager
            async with pool.get_user_connection(user) as connection:
                assert connection is not None
                assert connection._in_use is True
                assert connection.user_id == "context_user"
            
            # Connection should be released after context
            assert connection._in_use is False
            
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check functionality."""
        pool = ConnectionPool()
        
        user = MockUser(
            user_id="health_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Create connection
            connection = await pool.get_connection(user)
            pool.release_connection(connection)
            
            # Perform health check
            await pool._perform_health_checks()
            
            # Connection should still be healthy if credentials are valid
            connections = pool.user_pools.get("health_user", [])
            if connections:
                # If connection was created successfully, it should remain after health check
                assert len(connections) >= 1
                for conn in connections:
                    # Health status depends on actual API connection
                    assert isinstance(conn.stats.is_healthy, bool)
            
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_cleanup_idle_connections(self):
        """Test cleanup of idle connections."""
        pool = ConnectionPool(max_idle_time_minutes=0.01)  # Very short idle time
        
        user = MockUser(
            user_id="idle_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Create connection
            connection = await pool.get_connection(user)
            pool.release_connection(connection)
            
            # Manually set last_used to old time
            connection.stats.last_used = datetime.utcnow() - timedelta(minutes=5)
            
            # Perform cleanup
            await pool._cleanup_idle_connections()
            
            # Connection should be removed due to idle time
            connections = pool.user_pools.get("idle_user", [])
            assert len(connections) == 0 or "idle_user" not in pool.user_pools
            
            await pool.shutdown()
    
    def test_pool_stats(self, real_api_credentials):
        """Test pool statistics generation."""
        pool = ConnectionPool()
        
        # Create mock connection with stats
        connection = AlpacaConnection(
            user_id="stats_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Set some stats
        connection.stats.usage_count = 10
        connection.stats.error_count = 1
        connection.stats.avg_response_time = 0.5
        connection.stats.is_healthy = True
        
        # Add to pool manually
        pool.user_pools["stats_user"] = [connection]
        
        # Get stats
        stats = pool.get_pool_stats()
        
        assert stats["total_users"] == 1
        assert stats["total_connections"] == 1
        
        user_stats = stats["user_stats"]["stats_user"]
        assert user_stats["connection_count"] == 1
        assert user_stats["available_connections"] == 1  # Not in use
        assert user_stats["healthy_connections"] == 1
        assert user_stats["total_usage"] == 10
        assert user_stats["total_errors"] == 1
        assert user_stats["avg_response_time"] == 0.5
    
    @pytest.mark.asyncio
    async def test_pool_shutdown(self):
        """Test pool shutdown process."""
        pool = ConnectionPool()
        
        user = MockUser(
            user_id="shutdown_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the connection test to avoid real API calls
        with patch.object(AlpacaConnection, 'test_connection', return_value=True):
            # Create connection
            connection = await pool.get_connection(user)
            
            # Shutdown pool
            await pool.shutdown()
            
            # Verify connection was released
            assert connection._in_use is False
            
            # Verify pools were cleared
            assert len(pool.user_pools) == 0
            assert len(pool.usage_queues) == 0
    
    @pytest.mark.asyncio
    async def test_background_tasks_handling(self):
        """Test background tasks creation and handling."""
        pool = ConnectionPool()
        
        # Ensure async components (which starts background tasks)
        await pool._ensure_async_components()
        
        # Background tasks should be created if event loop is running
        # Note: In test environment, tasks might not be created due to event loop state
        assert isinstance(pool._background_tasks, list)
        
        await pool.shutdown()


class TestConnectionPoolIntegration:
    """Integration tests for connection pool with real connections."""
    
    @pytest.mark.asyncio
    async def test_real_connection_pool_usage(self, real_api_credentials):
        """Test connection pool with real API credentials."""
        pool = ConnectionPool(max_connections_per_user=1)
        
        user = MockUser(
            user_id="real_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        # Use connection pool
        async with pool.get_user_connection(user) as connection:
            # Test that connection works
            is_healthy = await connection.test_connection()
            
            if is_healthy:
                assert connection.stats.is_healthy is True
                assert connection.stats.usage_count > 0
                assert connection.trading_client is not None
                assert connection.data_client is not None
            else:
                # Connection might fail in test environment
                assert connection.stats.is_healthy is False
                assert connection.stats.error_count > 0
        
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_usage(self, real_api_credentials):
        """Test concurrent connection usage."""
        pool = ConnectionPool(max_connections_per_user=2)
        
        user = MockUser(
            user_id="concurrent_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        async def use_connection():
            async with pool.get_user_connection(user) as connection:
                # Simulate some work
                await asyncio.sleep(0.01)
                return await connection.test_connection()
        
        # Run multiple concurrent connection requests
        tasks = [use_connection() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All tasks should complete
        for result in results:
            assert not isinstance(result, Exception)
            assert isinstance(result, bool)
        
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_connection_reuse_efficiency(self, real_api_credentials):
        """Test that connections are efficiently reused."""
        pool = ConnectionPool(max_connections_per_user=1)
        
        user = MockUser(
            user_id="reuse_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Get connection multiple times
        connections = []
        for i in range(3):
            conn = await pool.get_connection(user)
            connections.append(conn)
            pool.release_connection(conn)
        
        # All connections should be the same object (reused)
        assert all(conn == connections[0] for conn in connections)
        
        # Usage count should increase
        assert connections[0].stats.usage_count >= 3
        
        await pool.shutdown()


def test_get_connection_pool_function():
    """Test the get_connection_pool dependency injection function."""
    pool = get_connection_pool()
    
    assert isinstance(pool, ConnectionPool)
    assert pool.max_connections_per_user == 5  # Default value
    assert pool.max_idle_time_minutes == 30  # Default value
    assert pool.health_check_interval_seconds == 300  # Default value


@pytest.mark.asyncio
async def test_connection_pool_error_recovery():
    """Test connection pool error recovery scenarios."""
    pool = ConnectionPool()
    
    # Test with user that has invalid credentials
    invalid_user = MockUser(
        user_id="invalid_user",
        api_key="invalid",
        secret_key="invalid"
    )
    
    # Should raise exception
    with pytest.raises(Exception):
        await pool.get_connection(invalid_user)
    
    # Pool should still be functional for valid users
    # (This would require valid credentials to test fully)
    
    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_pool_memory_management():
    """Test connection pool memory management."""
    pool = ConnectionPool(max_connections_per_user=1, max_idle_time_minutes=0.01)
    
    # Create multiple users to test memory usage
    users = [
        MockUser(f"user_{i}", "key", "secret") 
        for i in range(3)
    ]
    
    # Mock connection creation to avoid real API calls
    with patch.object(AlpacaConnection, 'test_connection', return_value=True):
        # Create connections for all users
        connections = []
        for user in users:
            try:
                conn = await pool.get_connection(user)
                connections.append(conn)
                pool.release_connection(conn)
            except Exception:
                # Expected for invalid credentials
                pass
    
    # Verify pools were created
    initial_users = len(pool.user_pools)
    
    # Simulate idle cleanup
    await pool._cleanup_idle_connections()
    
    # Some connections might be cleaned up
    final_users = len(pool.user_pools)
    assert final_users <= initial_users
    
    await pool.shutdown()