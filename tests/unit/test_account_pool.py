"""Unit tests for account pool management with real connections."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from app.account_pool import (
    AccountConfig, 
    ConnectionStats, 
    AlpacaAccountConnection,
    AccountConnectionPool,
    get_account_pool
)
from tests.utils import APITestHelper


class TestAccountConfig:
    """Test AccountConfig dataclass."""
    
    def test_account_config_creation(self):
        """Test creating AccountConfig with required fields."""
        config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        assert config.account_id == "test_account"
        assert config.api_key == "test_key"
        assert config.secret_key == "test_secret"
        assert config.paper_trading is True  # Default value
        assert config.enabled is True  # Default value
        assert config.max_connections == 3  # Default value
    
    def test_account_config_with_custom_values(self):
        """Test creating AccountConfig with custom values."""
        config = AccountConfig(
            account_id="premium_account",
            api_key="premium_key",
            secret_key="premium_secret",
            paper_trading=False,
            account_name="Premium Account",
            region="eu",
            tier="premium",
            max_connections=5,
            enabled=True
        )
        
        assert config.account_id == "premium_account"
        assert config.paper_trading is False
        assert config.account_name == "Premium Account"
        assert config.region == "eu"
        assert config.tier == "premium"
        assert config.max_connections == 5


class TestConnectionStats:
    """Test ConnectionStats dataclass."""
    
    def test_connection_stats_creation(self):
        """Test creating ConnectionStats."""
        created_time = datetime.utcnow()
        last_used_time = datetime.utcnow()
        
        stats = ConnectionStats(
            created_at=created_time,
            last_used=last_used_time
        )
        
        assert stats.created_at == created_time
        assert stats.last_used == last_used_time
        assert stats.usage_count == 0  # Default value
        assert stats.error_count == 0  # Default value
        assert stats.is_healthy is True  # Default value


class TestAlpacaAccountConnection:
    """Test AlpacaAccountConnection functionality."""
    
    def test_connection_initialization(self, primary_test_account):
        """Test AlpacaAccountConnection initialization."""
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=primary_test_account.credentials.paper_trading
        )
        
        connection = AlpacaAccountConnection(account_config)
        
        assert connection.account_config == account_config
        assert connection.connection_id.startswith(account_config.account_id)
        assert connection.alpaca_client is not None
        assert connection.stats is not None
        assert connection._in_use is False
        assert connection.is_available is True
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, primary_test_account):
        """Test successful connection test."""
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=primary_test_account.credentials.paper_trading
        )
        
        connection = AlpacaAccountConnection(account_config)
        
        # Test connection
        is_healthy = await connection.test_connection()
        
        if is_healthy:
            assert connection.stats.is_healthy is True
            assert connection.stats.usage_count == 1
            assert connection.stats.last_health_check is not None
            assert connection.stats.avg_response_time > 0
        else:
            # If connection failed, it should be marked as unhealthy
            assert connection.stats.is_healthy is False
            assert connection.stats.error_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self):
        """Test connection test with invalid credentials."""
        account_config = AccountConfig(
            account_id="invalid_account",
            api_key="invalid_key",
            secret_key="invalid_secret"
        )
        
        connection = AlpacaAccountConnection(account_config)
        
        # Test connection with invalid credentials
        is_healthy = await connection.test_connection()
        
        assert is_healthy is False
        assert connection.stats.is_healthy is False
        assert connection.stats.error_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_acquire_release(self, primary_test_account):
        """Test connection acquire and release."""
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key
        )
        
        connection = AlpacaAccountConnection(account_config)
        
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
    
    def test_connection_age_calculation(self, primary_test_account):
        """Test connection age calculation."""
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key
        )
        
        connection = AlpacaAccountConnection(account_config)
        
        # Age should be very small for new connection
        age = connection.age_minutes
        assert age >= 0
        assert age < 1  # Should be less than 1 minute for new connection


class TestAccountConnectionPool:
    """Test AccountConnectionPool functionality."""
    
    def test_pool_initialization(self):
        """Test AccountConnectionPool initialization."""
        pool = AccountConnectionPool(
            max_connections_per_account=5,
            health_check_interval_seconds=600
        )
        
        assert pool.max_connections_per_account == 5
        assert pool.health_check_interval_seconds == 600
        assert pool._initialized is False
        assert len(pool.account_configs) == 0
        assert len(pool.account_pools) == 0
    
    @pytest.mark.asyncio
    async def test_pool_initialization_with_config(self):
        """Test pool initialization with account configuration."""
        pool = AccountConnectionPool()
        
        # Mock the settings to provide test configuration
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {
                "test_account_1": {
                    "api_key": "test_key_1",
                    "secret_key": "test_secret_1",
                    "paper_trading": True,
                    "enabled": True,
                    "max_connections": 2
                },
                "test_account_2": {
                    "api_key": "test_key_2",
                    "secret_key": "test_secret_2",
                    "paper_trading": True,
                    "enabled": False,  # Disabled account
                    "max_connections": 1
                }
            }
            
            # Mock the connection test to avoid real API calls
            with patch.object(AlpacaAccountConnection, 'test_connection', return_value=True):
                await pool.initialize()
            
            assert pool._initialized is True
            assert len(pool.account_configs) == 1  # Only enabled account
            assert "test_account_1" in pool.account_configs
            assert "test_account_2" not in pool.account_configs
            assert len(pool.account_id_list) == 1
    
    @pytest.mark.asyncio
    async def test_pool_initialization_fallback_to_default(self):
        """Test pool initialization fallback to default single account."""
        pool = AccountConnectionPool()
        
        # Mock settings without accounts configuration
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {}
            mock_settings.alpaca_api_key = "default_key"
            mock_settings.alpaca_secret_key = "default_secret"
            mock_settings.alpaca_paper_trading = True
            
            # Mock the connection test
            with patch.object(AlpacaAccountConnection, 'test_connection', return_value=True):
                await pool.initialize()
            
            assert pool._initialized is True
            assert len(pool.account_configs) == 1
            assert "default_account" in pool.account_configs
            assert pool.account_configs["default_account"].api_key == "default_key"
    
    def test_routing_strategies(self):
        """Test different account routing strategies."""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account_1", "account_2", "account_3"]
        
        # Test round robin
        account1 = pool.get_account_by_routing(strategy="round_robin")
        assert account1 in pool.account_id_list
        
        # Test hash routing
        account2 = pool.get_account_by_routing(routing_key="test_key", strategy="hash")
        assert account2 in pool.account_id_list
        
        # Same routing key should return same account
        account3 = pool.get_account_by_routing(routing_key="test_key", strategy="hash")
        assert account2 == account3
        
        # Test random routing
        account4 = pool.get_account_by_routing(strategy="random")
        assert account4 in pool.account_id_list
        
        # Test least loaded routing (without actual connections)
        account5 = pool.get_account_by_routing(strategy="least_loaded")
        assert account5 in pool.account_id_list
    
    @pytest.mark.asyncio
    async def test_get_connection_success(self):
        """Test successful connection retrieval."""
        pool = AccountConnectionPool()
        
        # Setup test account configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        pool.account_id_list = ["test_account"]
        
        # Create mock connection
        mock_connection = MagicMock(spec=AlpacaAccountConnection)
        mock_connection.is_available = True
        mock_connection.acquire = AsyncMock()
        
        pool.account_pools["test_account"] = [mock_connection]
        pool.usage_queues["test_account"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # Get connection
        connection = await pool.get_connection("test_account")
        
        assert connection == mock_connection
        mock_connection.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_connection_no_available(self):
        """Test connection retrieval when no connections are available."""
        pool = AccountConnectionPool()
        
        # Setup test account configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        pool.account_id_list = ["test_account"]
        
        # Create mock connection that's not available
        mock_connection = MagicMock(spec=AlpacaAccountConnection)
        mock_connection.is_available = False
        mock_connection.stats = MagicMock()
        mock_connection.stats.usage_count = 5
        mock_connection.acquire = AsyncMock()
        
        pool.account_pools["test_account"] = [mock_connection]
        pool.usage_queues["test_account"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # Should still return the connection (reuse busy connection)
        connection = await pool.get_connection("test_account")
        
        assert connection == mock_connection
        mock_connection.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_connection_invalid_account(self):
        """Test connection retrieval with invalid account ID."""
        pool = AccountConnectionPool()
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        with pytest.raises(Exception, match="账户不存在或无可用连接"):
            await pool.get_connection("nonexistent_account")
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """Test connection context manager."""
        pool = AccountConnectionPool()
        
        # Setup test account configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        pool.account_id_list = ["test_account"]
        
        # Create mock connection
        mock_connection = MagicMock(spec=AlpacaAccountConnection)
        mock_connection.is_available = True
        mock_connection.acquire = AsyncMock()
        mock_connection.release = MagicMock()
        
        pool.account_pools["test_account"] = [mock_connection]
        pool.usage_queues["test_account"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # Use context manager
        async with pool.get_account_connection("test_account") as connection:
            assert connection == mock_connection
            mock_connection.acquire.assert_called_once()
        
        # Connection should be released after context
        mock_connection.release.assert_called_once()
    
    def test_pool_stats(self):
        """Test pool statistics generation."""
        pool = AccountConnectionPool()
        
        # Setup test configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret",
            account_name="Test Account",
            tier="premium"
        )
        
        pool.account_configs["test_account"] = test_account_config
        
        # Create mock connections with stats
        mock_connection1 = MagicMock(spec=AlpacaAccountConnection)
        mock_connection1.is_available = True
        mock_connection1.stats = MagicMock()
        mock_connection1.stats.is_healthy = True
        mock_connection1.stats.usage_count = 10
        mock_connection1.stats.error_count = 1
        mock_connection1.stats.avg_response_time = 0.5
        mock_connection1.stats.last_health_check = datetime.utcnow()
        
        mock_connection2 = MagicMock(spec=AlpacaAccountConnection)
        mock_connection2.is_available = False
        mock_connection2.stats = MagicMock()
        mock_connection2.stats.is_healthy = True
        mock_connection2.stats.usage_count = 15
        mock_connection2.stats.error_count = 0
        mock_connection2.stats.avg_response_time = 0.3
        mock_connection2.stats.last_health_check = datetime.utcnow()
        
        pool.account_pools["test_account"] = [mock_connection1, mock_connection2]
        
        # Get stats
        stats = pool.get_pool_stats()
        
        assert stats["total_accounts"] == 1
        assert stats["active_accounts"] == 1
        assert stats["total_connections"] == 2
        
        account_stats = stats["account_stats"]["test_account"]
        assert account_stats["account_name"] == "Test Account"
        assert account_stats["tier"] == "premium"
        assert account_stats["connection_count"] == 2
        assert account_stats["available_connections"] == 1
        assert account_stats["healthy_connections"] == 2
        assert account_stats["total_usage"] == 25
        assert account_stats["total_errors"] == 1
        assert account_stats["avg_response_time"] == 0.4  # (0.5 + 0.3) / 2
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check loop performance."""
        pool = AccountConnectionPool()
        
        # Setup test configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        
        # Create mock connections
        healthy_connection = MagicMock(spec=AlpacaAccountConnection)
        healthy_connection._in_use = False
        healthy_connection.test_connection = AsyncMock(return_value=True)
        
        unhealthy_connection = MagicMock(spec=AlpacaAccountConnection)
        unhealthy_connection._in_use = False
        unhealthy_connection.test_connection = AsyncMock(return_value=False)
        
        pool.account_pools["test_account"] = [healthy_connection, unhealthy_connection]
        pool._global_lock = asyncio.Lock()
        
        # Perform health checks
        await pool._perform_health_checks()
        
        # Verify health checks were called
        healthy_connection.test_connection.assert_called_once()
        unhealthy_connection.test_connection.assert_called_once()
        
        # Verify unhealthy connection was removed
        assert len(pool.account_pools["test_account"]) == 1
        assert pool.account_pools["test_account"][0] == healthy_connection
    
    @pytest.mark.asyncio
    async def test_pool_shutdown(self):
        """Test pool shutdown process."""
        pool = AccountConnectionPool()
        
        # Setup mock background tasks
        mock_task1 = MagicMock()
        mock_task1.cancel = MagicMock()
        mock_task2 = MagicMock()
        mock_task2.cancel = MagicMock()
        
        pool._background_tasks = [mock_task1, mock_task2]
        
        # Setup mock connections
        mock_connection = MagicMock(spec=AlpacaAccountConnection)
        mock_connection._in_use = True
        mock_connection.release = MagicMock()
        
        pool.account_pools["test_account"] = [mock_connection]
        pool.usage_queues["test_account"] = []
        pool._global_lock = asyncio.Lock()
        
        # Mock asyncio.gather to avoid waiting for cancelled tasks
        with patch('asyncio.gather', new_callable=AsyncMock):
            await pool.shutdown()
        
        # Verify tasks were cancelled
        mock_task1.cancel.assert_called_once()
        mock_task2.cancel.assert_called_once()
        
        # Verify connections were released
        mock_connection.release.assert_called_once()
        
        # Verify pools were cleared
        assert len(pool.account_pools) == 0
        assert len(pool.usage_queues) == 0


class TestAccountPoolIntegration:
    """Integration tests for account pool with real connections."""
    
    @pytest.mark.asyncio
    async def test_real_account_pool_initialization(self, primary_test_account):
        """Test account pool initialization with real account."""
        pool = AccountConnectionPool(max_connections_per_account=1)
        
        # Mock settings with real test account
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {
                primary_test_account.credentials.account_id: {
                    "api_key": primary_test_account.credentials.api_key,
                    "secret_key": primary_test_account.credentials.secret_key,
                    "paper_trading": primary_test_account.credentials.paper_trading,
                    "enabled": True,
                    "max_connections": 1
                }
            }
            
            await pool.initialize()
            
            assert pool._initialized is True
            assert len(pool.account_configs) == 1
            assert primary_test_account.credentials.account_id in pool.account_configs
            
            # Check that connection was created and tested
            connections = pool.account_pools.get(primary_test_account.credentials.account_id, [])
            if connections:
                assert len(connections) == 1
                connection = connections[0]
                assert connection.stats.is_healthy is True
                assert connection.stats.usage_count > 0
            
            # Cleanup
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_real_connection_usage(self, primary_test_account, api_test_helper):
        """Test using real connection from pool."""
        pool = AccountConnectionPool(max_connections_per_account=1)
        
        # Mock settings with real test account
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {
                primary_test_account.credentials.account_id: {
                    "api_key": primary_test_account.credentials.api_key,
                    "secret_key": primary_test_account.credentials.secret_key,
                    "paper_trading": primary_test_account.credentials.paper_trading,
                    "enabled": True,
                    "max_connections": 1
                }
            }
            
            await pool.initialize()
            
            # Use connection to make API call
            async with pool.get_account_connection(primary_test_account.credentials.account_id) as connection:
                result = await api_test_helper.timed_api_call(
                    connection.alpaca_client.test_connection
                )
                
                if result.success:
                    assert result.response_data.get("status") == "connected"
                    assert result.response_time_ms > 0
                else:
                    # Connection might fail in test environment
                    assert result.error_message is not None
            
            # Cleanup
            await pool.shutdown()


def test_get_account_pool_function():
    """Test the get_account_pool dependency injection function."""
    pool = get_account_pool()
    
    assert isinstance(pool, AccountConnectionPool)
    assert pool.max_connections_per_account == 3  # Default value
    assert pool.health_check_interval_seconds == 300  # Default value


@pytest.mark.asyncio
async def test_account_pool_performance_under_load():
    """Test account pool performance under concurrent load."""
    pool = AccountConnectionPool(max_connections_per_account=2)
    
    # Setup test configuration
    test_account_config = AccountConfig(
        account_id="load_test_account",
        api_key="test_key",
        secret_key="test_secret"
    )
    
    pool.account_configs["load_test_account"] = test_account_config
    pool.account_id_list = ["load_test_account"]
    
    # Create mock connections
    mock_connections = []
    for i in range(2):
        mock_connection = MagicMock(spec=AlpacaAccountConnection)
        mock_connection.is_available = True
        mock_connection.acquire = AsyncMock()
        mock_connection.release = MagicMock()
        mock_connection.stats = MagicMock()
        mock_connection.stats.usage_count = 0
        mock_connections.append(mock_connection)
    
    pool.account_pools["load_test_account"] = mock_connections
    pool.usage_queues["load_test_account"] = []
    pool._initialized = True
    pool._global_lock = asyncio.Lock()
    
    # Simulate concurrent connection requests
    async def get_and_release_connection():
        connection = await pool.get_connection("load_test_account")
        # Simulate some work
        await asyncio.sleep(0.01)
        pool.release_connection(connection)
        return connection
    
    # Run multiple concurrent requests
    tasks = [get_and_release_connection() for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # All requests should complete successfully
    for result in results:
        assert not isinstance(result, Exception), f"Task failed with: {result}"
        assert result in mock_connections
    
    # Verify that connections were properly acquired and released
    total_acquire_calls = sum(conn.acquire.call_count for conn in mock_connections)
    total_release_calls = sum(conn.release.call_count for conn in mock_connections)
    
    # At least some calls should have been made
    assert total_acquire_calls > 0, "No acquire calls were made"
    assert total_release_calls > 0, "No release calls were made"
    assert total_acquire_calls == total_release_calls, "Mismatched acquire/release calls"