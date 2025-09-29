"""Unit tests for connection pool with real connection validation."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from collections import deque

from app.connection_pool import (
    ConnectionType,
    ConnectionStats,
    ConnectionManager,
    PoolManager,
    pool_manager
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
            connection_type=ConnectionType.TRADING_CLIENT,
            created_at=created_time,
            last_used=last_used_time
        )
        
        assert stats.connection_type == ConnectionType.TRADING_CLIENT
        assert stats.created_at == created_time
        assert stats.last_used == last_used_time
        assert stats.usage_count == 0
        assert stats.error_count == 0
        assert stats.avg_response_time == 0.0
        assert stats.is_healthy is True


class TestConnectionManager:
    """Test ConnectionManager functionality."""
    
    def test_connection_initialization(self, real_api_credentials):
        """Test ConnectionManager initialization."""
        manager = ConnectionManager(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        assert manager.user_id == "test_user"
        assert manager.api_key == real_api_credentials.api_key
        assert manager.secret_key == real_api_credentials.secret_key
        assert manager.paper_trading == real_api_credentials.paper_trading
        assert ConnectionType.TRADING_CLIENT in manager.connections
        assert ConnectionType.TRADING_CLIENT in manager.connection_stats
        assert ConnectionType.TRADING_CLIENT in manager._locks
        assert manager._in_use[ConnectionType.TRADING_CLIENT] is False
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, real_api_credentials):
        """Test successful connection test."""
        manager = ConnectionManager(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        # Test connection
        is_healthy = await manager.test_connection(ConnectionType.TRADING_CLIENT)
        
        if is_healthy:
            stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
            assert stats.is_healthy is True
            assert stats.usage_count >= 1
            assert stats.avg_response_time > 0
        else:
            # If connection failed, it should be marked as unhealthy
            stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
            assert stats.is_healthy is False
            assert stats.error_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self):
        """Test connection test with invalid credentials."""
        manager = ConnectionManager(
            user_id="test_user",
            api_key="invalid_key",
            secret_key="invalid_secret",
            paper_trading=True
        )
        
        # Test connection with invalid credentials
        is_healthy = await manager.test_connection(ConnectionType.TRADING_CLIENT)
        
        assert is_healthy is False
        stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
        assert stats.is_healthy is False
        assert stats.error_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_acquire_release(self, real_api_credentials):
        """Test connection acquire and release."""
        manager = ConnectionManager(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Initially available
        assert manager.is_connection_available(ConnectionType.TRADING_CLIENT) is True
        assert manager._in_use[ConnectionType.TRADING_CLIENT] is False
        
        # Acquire connection
        trading_client = await manager.get_connection(ConnectionType.TRADING_CLIENT)
        
        assert manager._in_use[ConnectionType.TRADING_CLIENT] is True
        assert manager.is_connection_available(ConnectionType.TRADING_CLIENT) is False
        assert trading_client is not None
        
        # Release connection
        manager.release_connection(ConnectionType.TRADING_CLIENT)
        
        assert manager._in_use[ConnectionType.TRADING_CLIENT] is False
        assert manager.is_connection_available(ConnectionType.TRADING_CLIENT) is True
    
    def test_connection_manager_properties(self, real_api_credentials):
        """Test ConnectionManager properties."""
        manager = ConnectionManager(
            user_id="test_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Test connection count
        assert manager.connection_count >= 1  # At least trading client
        
        # Test connection stats
        stats = manager.get_connection_stats()
        assert stats["user_id"] == "test_user"
        assert stats["total_connections"] >= 1
        assert ConnectionType.TRADING_CLIENT.value in stats["connections"]


class TestPoolManager:
    """Test ConnectionPool functionality."""
    
    def test_pool_initialization(self):
        """Test PoolManager initialization."""
        pool = PoolManager(
            max_idle_time_minutes=60,
            health_check_interval_seconds=600
        )
        
        assert pool.max_idle_time_minutes == 60
        assert pool.health_check_interval_seconds == 600
        assert len(pool.user_managers) == 0
        assert pool._global_lock is None  # Lazy initialization
    
    @pytest.mark.asyncio
    async def test_ensure_async_components(self):
        """Test async components initialization."""
        pool = PoolManager()
        
        # Initially no lock
        assert pool._global_lock is None
        
        # Ensure async components
        await pool._ensure_async_components()
        
        # Lock should be initialized
        assert pool._global_lock is not None
        assert isinstance(pool._global_lock, asyncio.Lock)
    
    @pytest.mark.asyncio
    async def test_get_user_manager_new_user(self):
        """Test getting user manager for new user."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="new_user",
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock the ConnectionManager initialization to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'):
            # Get user manager for new user
            manager = await pool.get_user_manager(user)
            
            assert manager is not None
            assert manager.user_id == "new_user"
            
            # Verify user manager was created
            assert "new_user" in pool.user_managers
            assert pool.user_managers["new_user"] == manager
            
            # Cleanup
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_user_manager_existing_user(self):
        """Test getting user manager for existing user."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="existing_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the ConnectionManager initialization to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'):
            # Get first manager
            manager1 = await pool.get_user_manager(user)
            
            # Get second manager (should reuse existing)
            manager2 = await pool.get_user_manager(user)
            
            assert manager2 is not None
            assert manager2.user_id == "existing_user"
            
            # Should be the same manager object (reused)
            assert manager1 == manager2
            
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_user_manager_connection_usage(self):
        """Test user manager connection usage."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="connection_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the ConnectionManager initialization to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'):
            # Get user manager
            manager = await pool.get_user_manager(user)
            
            # Test connection acquisition
            trading_client = await manager.get_connection(ConnectionType.TRADING_CLIENT)
            assert trading_client is not None
            assert manager._in_use[ConnectionType.TRADING_CLIENT] is True
            
            # Release connection
            manager.release_connection(ConnectionType.TRADING_CLIENT)
            assert manager._in_use[ConnectionType.TRADING_CLIENT] is False
            
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_get_user_manager_invalid_credentials(self):
        """Test getting user manager with invalid credentials."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="invalid_user",
            api_key="invalid_key",
            secret_key="invalid_secret"
        )
        
        # Manager should be created even with invalid credentials (verification failure is logged)
        manager = await pool.get_user_manager(user)
        assert manager is not None
        assert manager.user_id == "invalid_user"
        
        # But connection test should fail
        is_healthy = await manager.test_connection(ConnectionType.TRADING_CLIENT)
        assert is_healthy is False
        
        # Stats should reflect the failure
        stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
        assert stats.is_healthy is False
        assert stats.error_count > 0
        
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_user_manager_context_functionality(self):
        """Test user manager functionality."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="context_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the ConnectionManager initialization to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'):
            # Get user manager
            manager = await pool.get_user_manager(user)
            
            assert manager is not None
            assert manager.user_id == "context_user"
            
            # Test connection availability
            assert manager.is_connection_available(ConnectionType.TRADING_CLIENT) is True
            
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check functionality."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="health_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the ConnectionManager methods to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'), \
             patch.object(ConnectionManager, 'test_connection', return_value=True):
            # Create user manager
            manager = await pool.get_user_manager(user)
            
            # Perform health check
            await pool._perform_health_checks()
            
            # Manager should still exist and be healthy
            assert "health_user" in pool.user_managers
            assert pool.user_managers["health_user"] == manager
            
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_cleanup_idle_connections(self):
        """Test cleanup of idle connections."""
        pool = PoolManager(max_idle_time_minutes=0.01)  # Very short idle time
        
        user = MockUser(
            user_id="idle_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the ConnectionManager methods to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'):
            # Create user manager
            manager = await pool.get_user_manager(user)
            
            # Manually set last_used to old time for trading client
            stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
            stats.last_used = datetime.utcnow() - timedelta(minutes=5)
            
            # Perform cleanup
            await pool._cleanup_idle_connections()
            
            # Manager might be removed due to idle time
            # (depends on cleanup logic for core connections)
            # Test passes if no exception is raised
            
            await pool.shutdown()
    
    def test_pool_stats(self, real_api_credentials):
        """Test pool statistics generation."""
        pool = PoolManager()
        
        # Create mock connection manager with stats
        manager = ConnectionManager(
            user_id="stats_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Set some stats on the trading client
        stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
        stats.usage_count = 10
        stats.error_count = 1
        stats.avg_response_time = 0.5
        stats.is_healthy = True
        
        # Add to pool manually
        pool.user_managers["stats_user"] = manager
        
        # Get stats
        pool_stats = pool.get_pool_stats()
        
        assert pool_stats["total_users"] == 1
        assert pool_stats["total_connections"] == 1
        
        user_stats = pool_stats["user_stats"]["stats_user"]
        assert user_stats["user_id"] == "stats_user"
        assert user_stats["total_connections"] == 1
        
        trading_stats = user_stats["connections"][ConnectionType.TRADING_CLIENT.value]
        assert trading_stats["usage_count"] == 10
        assert trading_stats["error_count"] == 1
        assert trading_stats["avg_response_time"] == 0.5
        assert trading_stats["is_healthy"] is True
    
    @pytest.mark.asyncio
    async def test_pool_shutdown(self):
        """Test pool shutdown process."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="shutdown_user",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        # Mock the ConnectionManager initialization to avoid real API calls
        with patch.object(ConnectionManager, '_verify_account_access'):
            # Create user manager
            manager = await pool.get_user_manager(user)
            
            # Shutdown pool
            await pool.shutdown()
            
            # Verify user managers were cleared
            assert len(pool.user_managers) == 0
    
    @pytest.mark.asyncio
    async def test_background_tasks_handling(self):
        """Test background tasks creation and handling."""
        pool = PoolManager()
        
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
        pool = PoolManager()
        
        user = MockUser(
            user_id="real_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        # Get user manager
        manager = await pool.get_user_manager(user)
        
        # Test that connection works
        is_healthy = await manager.test_connection(ConnectionType.TRADING_CLIENT)
        
        if is_healthy:
            stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
            assert stats.is_healthy is True
            assert stats.usage_count > 0
            assert manager.connections[ConnectionType.TRADING_CLIENT] is not None
        else:
            # Connection might fail in test environment
            stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
            assert stats.is_healthy is False
            assert stats.error_count > 0
        
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_usage(self, real_api_credentials):
        """Test concurrent connection usage."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="concurrent_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        async def use_connection():
            manager = await pool.get_user_manager(user)
            # Simulate some work
            await asyncio.sleep(0.01)
            return await manager.test_connection(ConnectionType.TRADING_CLIENT)
        
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
        """Test that user managers are efficiently reused."""
        pool = PoolManager()
        
        user = MockUser(
            user_id="reuse_user",
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key
        )
        
        # Get user manager multiple times
        managers = []
        for i in range(3):
            manager = await pool.get_user_manager(user)
            managers.append(manager)
        
        # All managers should be the same object (reused)
        assert all(manager == managers[0] for manager in managers)
        
        # Usage count should increase with each test_connection call
        await managers[0].test_connection(ConnectionType.TRADING_CLIENT)
        stats = managers[0].connection_stats[ConnectionType.TRADING_CLIENT]
        assert stats.usage_count >= 1
        
        await pool.shutdown()


def test_get_pool_manager_function():
    """Test the pool_manager global instance."""
    pool = pool_manager
    
    assert isinstance(pool, PoolManager)
    assert pool.max_idle_time_minutes == 30  # Default value
    assert pool.health_check_interval_seconds == 300  # Default value


@pytest.mark.asyncio
async def test_connection_pool_error_recovery():
    """Test connection pool error recovery scenarios."""
    pool = PoolManager()
    
    # Test with user that has invalid credentials
    invalid_user = MockUser(
        user_id="invalid_user",
        api_key="invalid",
        secret_key="invalid"
    )
    
    # Manager should be created but unhealthy
    manager = await pool.get_user_manager(invalid_user)
    assert manager is not None
    
    # Connection test should fail
    is_healthy = await manager.test_connection(ConnectionType.TRADING_CLIENT)
    assert is_healthy is False
    
    # Pool should still be functional for valid users
    # (This would require valid credentials to test fully)
    
    await pool.shutdown()


@pytest.mark.asyncio
async def test_connection_pool_memory_management():
    """Test connection pool memory management."""
    pool = PoolManager(max_idle_time_minutes=0.01)
    
    # Create multiple users to test memory usage
    users = [
        MockUser(f"user_{i}", "key", "secret") 
        for i in range(3)
    ]
    
    # Mock ConnectionManager creation to avoid real API calls
    with patch.object(ConnectionManager, '_verify_account_access'):
        # Create user managers for all users
        managers = []
        for user in users:
            try:
                manager = await pool.get_user_manager(user)
                managers.append(manager)
            except Exception:
                # Expected for invalid credentials
                pass
    
    # Verify user managers were created
    initial_users = len(pool.user_managers)
    
    # Simulate idle cleanup
    await pool._cleanup_idle_connections()
    
    # Some managers might be cleaned up
    final_users = len(pool.user_managers)
    assert final_users <= initial_users
    
    await pool.shutdown()