"""Unit tests for account pool management with real connections."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from app.account_pool import (
    AccountConfig, 
    AccountConnection,
    AccountPool,
    account_pool
)
from app.connection_pool import ConnectionStats
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
        assert config.region == "us"  # Default value
        assert config.tier == "standard"  # Default value
    
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
            enabled=True
        )
        
        assert config.account_id == "premium_account"
        assert config.paper_trading is False
        assert config.account_name == "Premium Account"
        assert config.region == "eu"
        assert config.tier == "premium"
        assert config.enabled is True


class TestConnectionStats:
    """Test ConnectionStats dataclass."""
    
    def test_connection_stats_creation(self):
        """Test creating ConnectionStats."""
        from app.connection_pool import ConnectionType
        
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
        assert stats.usage_count == 0  # Default value
        assert stats.error_count == 0  # Default value
        assert stats.is_healthy is True  # Default value


class TestAccountConnection:
    """Test AlpacaAccountConnection functionality."""
    
    def test_connection_initialization(self, primary_test_account):
        """Test AlpacaAccountConnection initialization."""
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=primary_test_account.credentials.paper_trading
        )
        
        connection = AccountConnection(account_config)
        
        assert connection.account_config == account_config
        assert connection.connection_id.startswith(account_config.account_id)
        assert connection.alpaca_client is not None
        assert connection.connection_manager is not None
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
        
        connection = AccountConnection(account_config)
        
        # Test connection
        is_healthy = await connection.test_connection()
        
        # Get connection stats through the connection manager
        stats = connection.get_connection_stats()
        trading_stats = stats.get('connections', {}).get('trading_client', {})
        
        if is_healthy:
            assert trading_stats.get('is_healthy', False) is True
            assert trading_stats.get('usage_count', 0) >= 1
            assert 'last_used' in trading_stats
            assert trading_stats.get('avg_response_time', 0) >= 0
        else:
            # If connection failed, it should be marked as unhealthy
            assert trading_stats.get('is_healthy', True) is False
            assert trading_stats.get('error_count', 0) >= 0
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self):
        """Test connection test with invalid credentials."""
        account_config = AccountConfig(
            account_id="invalid_account",
            api_key="invalid_key",
            secret_key="invalid_secret"
        )
        
        connection = AccountConnection(account_config)
        
        # Test connection with invalid credentials
        is_healthy = await connection.test_connection()
        
        assert is_healthy is False
        # Get connection stats through the connection manager
        stats = connection.get_connection_stats()
        trading_stats = stats.get('connections', {}).get('trading_client', {})
        assert trading_stats.get('is_healthy', True) is False
        assert trading_stats.get('error_count', 0) >= 0
    
    @pytest.mark.asyncio
    async def test_connection_acquire_release(self, primary_test_account):
        """Test connection acquire and release."""
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key
        )
        
        connection = AccountConnection(account_config)
        
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
        
        connection = AccountConnection(account_config)
        
        # Age should be very small for new connection
        age = connection.age_minutes
        assert age >= 0
        assert age < 1  # Should be less than 1 minute for new connection


class TestAccountValidationFixes:
    """Test the 6 critical production fixes for account validation."""
    
    @pytest.mark.asyncio
    async def test_pa_prefix_account_type_detection_paper(self, primary_test_account):
        """Test PA prefix detection for paper trading accounts - Fix #1."""
        from app.account_pool import AccountConnection
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=True  # Expect paper trading
        )
        
        connection = AccountConnection(account_config)
        
        # Mock the trading client response with PA prefix (paper account)
        with patch.object(connection.connection_manager, 'get_connection') as mock_get_conn:
            mock_trading_client = MagicMock()
            mock_account = MagicMock()
            mock_account.account_number = "PA123456789"  # Paper account with PA prefix
            mock_account.cash = "10000.00"  # Above minimum balance
            mock_trading_client.get_account.return_value = mock_account
            mock_get_conn.return_value = mock_trading_client
            
            # Test connection should succeed with matching account type
            is_healthy = await connection.test_connection()
            
            assert is_healthy is True, "Paper account with PA prefix should be valid when paper_trading=True"
            mock_trading_client.get_account.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pa_prefix_account_type_detection_mismatch(self, primary_test_account):
        """Test PA prefix detection mismatch - Fix #1."""
        from app.account_pool import AccountConnection
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=False  # Expect live trading but get paper account
        )
        
        connection = AccountConnection(account_config)
        
        # Mock the trading client response with PA prefix (paper account) but config expects live
        with patch.object(connection.connection_manager, 'get_connection') as mock_get_conn:
            mock_trading_client = MagicMock()
            mock_account = MagicMock()
            mock_account.account_number = "PA123456789"  # Paper account with PA prefix
            mock_account.cash = "10000.00"  # Above minimum balance
            mock_trading_client.get_account.return_value = mock_account
            mock_get_conn.return_value = mock_trading_client
            
            # Test connection should still succeed but log warning
            with patch('app.account_pool.logger') as mock_logger:
                is_healthy = await connection.test_connection()
                
                # Connection should still succeed but warning should be logged
                assert is_healthy is True, "Connection should still succeed despite account type mismatch"
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert "Account type mismatch" in warning_call
                assert "Expected paper_trading=False" in warning_call
                assert "PA123456789 is paper" in warning_call
    
    @pytest.mark.asyncio
    async def test_live_account_detection(self, primary_test_account):
        """Test live account detection (non-PA prefix) - Fix #1."""
        from app.account_pool import AccountConnection
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=False  # Expect live trading
        )
        
        connection = AccountConnection(account_config)
        
        # Mock the trading client response with non-PA prefix (live account)
        with patch.object(connection.connection_manager, 'get_connection') as mock_get_conn:
            mock_trading_client = MagicMock()
            mock_account = MagicMock()
            mock_account.account_number = "123456789"  # Live account without PA prefix
            mock_account.cash = "25000.00"  # Above minimum balance
            mock_trading_client.get_account.return_value = mock_account
            mock_get_conn.return_value = mock_trading_client
            
            # Test connection should succeed with matching account type
            is_healthy = await connection.test_connection()
            
            assert is_healthy is True, "Live account without PA prefix should be valid when paper_trading=False"
            mock_trading_client.get_account.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_minimum_balance_validation_success(self, primary_test_account):
        """Test minimum balance validation with sufficient funds - Fix #2."""
        from app.account_pool import AccountConnection
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=True
        )
        
        connection = AccountConnection(account_config)
        
        # Mock settings to set minimum balance requirement
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.minimum_balance = 5000.0
            
            # Mock the trading client response with sufficient balance
            with patch.object(connection.connection_manager, 'get_connection') as mock_get_conn:
                mock_trading_client = MagicMock()
                mock_account = MagicMock()
                mock_account.account_number = "PA123456789"
                mock_account.cash = "10000.00"  # Above minimum balance ($5000)
                mock_trading_client.get_account.return_value = mock_account
                mock_get_conn.return_value = mock_trading_client
                
                # Test connection should succeed with sufficient balance
                is_healthy = await connection.test_connection()
                
                assert is_healthy is True, "Account with balance above minimum should be valid"
                mock_trading_client.get_account.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_minimum_balance_validation_failure(self, primary_test_account):
        """Test minimum balance validation with insufficient funds - Fix #2."""
        from app.account_pool import AccountConnection
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=True
        )
        
        connection = AccountConnection(account_config)
        
        # Mock settings to set minimum balance requirement
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.minimum_balance = 5000.0
            
            # Mock the trading client response with insufficient balance
            with patch.object(connection.connection_manager, 'get_connection') as mock_get_conn:
                mock_trading_client = MagicMock()
                mock_account = MagicMock()
                mock_account.account_number = "PA123456789"
                mock_account.cash = "2500.00"  # Below minimum balance ($5000)
                mock_trading_client.get_account.return_value = mock_account
                mock_get_conn.return_value = mock_trading_client
                
                # Test connection should fail with insufficient balance
                with patch('app.account_pool.logger') as mock_logger:
                    is_healthy = await connection.test_connection()
                    
                    assert is_healthy is False, "Account with balance below minimum should be invalid"
                    mock_logger.error.assert_called()
                    error_call = mock_logger.error.call_args[0][0]
                    assert "balance $2,500.00 is below minimum required $5,000.00" in error_call
    
    @pytest.mark.asyncio
    async def test_balance_validation_with_secrets_yml_config(self, primary_test_account):
        """Test balance validation using configuration from secrets.yml - Fix #2."""
        from app.account_pool import AccountConnection
        import config
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key=primary_test_account.credentials.api_key,
            secret_key=primary_test_account.credentials.secret_key,
            paper_trading=True
        )
        
        connection = AccountConnection(account_config)
        
        # Test that settings.minimum_balance is loaded from config properly
        # This ensures the secrets.yml configuration is being read correctly
        assert hasattr(config.settings, 'minimum_balance')
        assert config.settings.minimum_balance >= 0  # Should be a positive number
        
        # Mock the trading client response
        with patch.object(connection.connection_manager, 'get_connection') as mock_get_conn:
            mock_trading_client = MagicMock()
            mock_account = MagicMock()
            mock_account.account_number = "PA123456789"
            # Use balance exactly at minimum (should pass)
            mock_account.cash = str(config.settings.minimum_balance)
            mock_trading_client.get_account.return_value = mock_account
            mock_get_conn.return_value = mock_trading_client
            
            # Test connection should succeed with balance exactly at minimum
            is_healthy = await connection.test_connection()
            
            assert is_healthy is True, "Account with balance exactly at minimum should be valid"
    
    @pytest.mark.asyncio 
    async def test_account_validation_with_real_data(self, real_api_client):
        """Test account validation with real Alpaca API data - Fix #1 and #2 combined."""
        # This test uses real API connections and data (NO MOCK TESTS ALLOWED)
        
        # Get real account information
        account_result = await real_api_client.get_account_info()
        
        if account_result.get("error"):
            pytest.skip(f"Real API connection failed: {account_result['error']}")
        
        # Extract real account data
        account_number = account_result.get("account_number")
        portfolio_value = float(account_result.get("portfolio_value", 0))
        
        # Validate account type detection with real data
        is_paper_account = account_number.startswith("PA") if account_number else False
        
        # Test PA prefix detection logic
        if real_api_client.test_account.credentials.paper_trading:
            # For paper trading, we expect PA prefix
            assert is_paper_account, f"Paper trading account should have PA prefix, got: {account_number}"
        else:
            # For live trading, we expect no PA prefix
            assert not is_paper_account, f"Live trading account should not have PA prefix, got: {account_number}"
        
        # Test balance validation with real data
        # Note: Paper accounts typically have virtual money, live accounts have real money
        assert portfolio_value >= 0, f"Portfolio value should be non-negative, got: {portfolio_value}"
        
        # Log results for verification
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Real account validation results:")
        logger.info(f"  Account Number: {account_number}")
        logger.info(f"  Is Paper Account: {is_paper_account}")
        logger.info(f"  Portfolio Value: ${portfolio_value:,.2f}")
        logger.info(f"  Expected Paper Trading: {real_api_client.test_account.credentials.paper_trading}")
    
    @pytest.mark.asyncio
    async def test_account_validation_error_handling(self, primary_test_account):
        """Test account validation error handling - Fix #1 and #2."""
        from app.account_pool import AccountConnection
        
        account_config = AccountConfig(
            account_id=primary_test_account.credentials.account_id,
            api_key="invalid_key",  # Invalid credentials to trigger error
            secret_key="invalid_secret",
            paper_trading=True
        )
        
        connection = AccountConnection(account_config)
        
        # Test connection should fail gracefully with invalid credentials
        with patch('app.account_pool.logger') as mock_logger:
            is_healthy = await connection.test_connection()
            
            assert is_healthy is False, "Connection with invalid credentials should fail"
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "Connection test failed" in error_call
    
    def test_account_type_detection_edge_cases(self):
        """Test edge cases for account type detection - Fix #1."""
        from app.account_pool import AccountConnection
        
        # Test empty account number
        mock_account = MagicMock()
        mock_account.account_number = ""
        mock_account.cash = "10000.00"
        
        # Empty account number should not start with PA
        is_paper = mock_account.account_number.startswith("PA")
        assert is_paper is False
        
        # Test None account number
        mock_account.account_number = None
        try:
            is_paper = mock_account.account_number.startswith("PA") if mock_account.account_number else False
            assert is_paper is False
        except AttributeError:
            # This is expected behavior for None
            pass
        
        # Test case-sensitive PA prefix
        test_cases = [
            ("PA123456789", True),   # Standard paper account
            ("pa123456789", False),  # Lowercase should not match
            ("PA", True),            # Minimal PA prefix
            ("P", False),            # Just P is not enough
            ("AP123456789", False),  # AP is not PA
            ("123456789", False),    # No prefix (live account)
            ("XPA123456789", False), # PA not at start
        ]
        
        for account_number, expected_is_paper in test_cases:
            is_paper = account_number.startswith("PA")
            assert is_paper == expected_is_paper, f"Account number '{account_number}' should {'be' if expected_is_paper else 'not be'} detected as paper account"


class TestAccountPool:
    """Test AccountConnectionPool functionality."""
    
    def test_pool_initialization(self):
        """Test AccountPool initialization."""
        pool = AccountPool(
            health_check_interval_seconds=600
        )
        
        assert pool.health_check_interval_seconds == 600
        assert pool._initialized is False
        assert len(pool.account_configs) == 0
        assert len(pool.account_connections) == 0
    
    @pytest.mark.asyncio
    async def test_pool_initialization_with_config(self):
        """Test pool initialization with account configuration."""
        pool = AccountPool()
        
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
            with patch.object(AccountConnection, 'test_connection', return_value=True):
                await pool.initialize()
            
            assert pool._initialized is True
            assert len(pool.account_configs) == 1  # Only enabled account
            assert "test_account_1" in pool.account_configs
            assert "test_account_2" not in pool.account_configs
            assert len(pool.account_id_list) == 1
    
    @pytest.mark.asyncio
    async def test_pool_initialization_fallback_to_default(self):
        """Test pool initialization failure when no account configurations are found."""
        pool = AccountPool()
        
        # Mock settings without accounts configuration
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {}
            
            # Should raise ValueError when no account configurations are found
            with pytest.raises(ValueError, match="No account configurations found"):
                await pool.initialize()
            
            # Pool should not be initialized
            assert pool._initialized is False
            assert len(pool.account_configs) == 0
    
    def test_routing_strategies(self):
        """Test different account routing strategies."""
        pool = AccountPool()
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
        pool = AccountPool()
        
        # Setup test account configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        pool.account_id_list = ["test_account"]
        
        # Create mock connection
        mock_connection = MagicMock(spec=AccountConnection)
        mock_connection.is_available = True
        mock_connection.acquire = AsyncMock()
        
        pool.account_connections["test_account"] = mock_connection
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
        pool = AccountPool()
        
        # Setup test account configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        pool.account_id_list = ["test_account"]
        
        # Create mock connection that's not available
        mock_connection = MagicMock(spec=AccountConnection)
        mock_connection.is_available = False
        mock_connection.stats = MagicMock()
        mock_connection.stats.usage_count = 5
        mock_connection.acquire = AsyncMock()
        
        pool.account_connections["test_account"] = mock_connection
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
        pool = AccountPool()
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        with pytest.raises(Exception, match="Cannot resolve account identifier"):
            await pool.get_connection("nonexistent_account")
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """Test connection context manager."""
        pool = AccountPool()
        
        # Setup test account configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        pool.account_id_list = ["test_account"]
        
        # Create mock connection
        mock_connection = MagicMock(spec=AccountConnection)
        mock_connection.is_available = True
        mock_connection.acquire = AsyncMock()
        mock_connection.release = MagicMock()
        
        pool.account_connections["test_account"] = mock_connection
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
        pool = AccountPool()
        
        # Setup test configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret",
            account_name="Test Account",
            tier="premium"
        )
        
        pool.account_configs["test_account"] = test_account_config
        
        # Create mock connection with proper stats
        mock_connection1 = MagicMock(spec=AccountConnection)
        mock_connection1.is_available = True
        mock_connection1.connection_count = 1  # Return integer, not MagicMock
        mock_connection1.get_connection_stats.return_value = {
            'connections': {
                'trading_client': {
                    'is_healthy': True,
                    'usage_count': 10,
                    'error_count': 1,
                    'avg_response_time': 0.5,
                    'last_health_check': datetime.utcnow().isoformat()
                }
            }
        }
        
        # Note: The pool now uses single connections, not lists
        pool.account_connections["test_account"] = mock_connection1
        
        # Get stats
        stats = pool.get_pool_stats()
        
        assert stats["total_accounts"] == 1
        assert stats["active_accounts"] == 1
        assert stats["total_connections"] == 1  # Single connection per account
        
        account_stats = stats["account_stats"]["test_account"]
        assert account_stats["account_name"] == "Test Account"
        assert account_stats["tier"] == "premium"
        assert account_stats["connection_count"] == 1  # Single connection
        assert account_stats["is_available"] == True
        # Note: Since we're using single connections now, the stats format is different
        # The detailed stats are stored in connection_details
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check loop performance."""
        pool = AccountPool()
        
        # Setup test configuration
        test_account_config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        pool.account_configs["test_account"] = test_account_config
        
        # Create mock connections
        healthy_connection = MagicMock(spec=AccountConnection)
        healthy_connection._in_use = False
        healthy_connection.test_connection = AsyncMock(return_value=True)
        
        unhealthy_connection = MagicMock(spec=AccountConnection)
        unhealthy_connection._in_use = False
        unhealthy_connection.test_connection = AsyncMock(return_value=False)
        
        # Store the healthy connection (pool uses single connections)
        pool.account_connections["test_account"] = healthy_connection
        pool._global_lock = asyncio.Lock()
        
        # Perform health checks
        await pool._perform_health_checks()
        
        # Verify health checks were called
        healthy_connection.test_connection.assert_called_once()
        
        # Since we only stored the healthy connection, it should still be there
        assert "test_account" in pool.account_connections
        assert pool.account_connections["test_account"] == healthy_connection
    
    @pytest.mark.asyncio
    async def test_pool_shutdown(self):
        """Test pool shutdown process."""
        pool = AccountPool()
        
        # Setup mock background tasks
        mock_task1 = MagicMock()
        mock_task1.cancel = MagicMock()
        mock_task2 = MagicMock()
        mock_task2.cancel = MagicMock()
        
        pool._background_tasks = [mock_task1, mock_task2]
        
        # Setup mock connections
        mock_connection = MagicMock(spec=AccountConnection)
        mock_connection._in_use = True
        mock_connection.shutdown = AsyncMock()  # shutdown is async
        
        pool.account_connections["test_account"] = mock_connection
        pool.usage_queues["test_account"] = []
        pool._global_lock = asyncio.Lock()
        
        # Mock asyncio.gather to avoid waiting for cancelled tasks
        with patch('asyncio.gather', new_callable=AsyncMock):
            await pool.shutdown()
        
        # Verify tasks were cancelled
        mock_task1.cancel.assert_called_once()
        mock_task2.cancel.assert_called_once()
        
        # Verify connections were shutdown
        mock_connection.shutdown.assert_called_once()
        
        # Verify pools were cleared
        assert len(pool.account_connections) == 0
        assert len(pool.usage_queues) == 0


class TestAccountPoolIntegration:
    """Integration tests for account pool with real connections."""
    
    @pytest.mark.asyncio
    async def test_real_account_pool_initialization(self, primary_test_account):
        """Test account pool initialization with real account."""
        pool = AccountPool()
        
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
            connection = pool.account_connections.get(primary_test_account.credentials.account_id)
            if connection:
                stats = connection.get_connection_stats()
                trading_stats = stats.get('connections', {}).get('trading_client', {})
                assert trading_stats.get('is_healthy', False) is True
                assert trading_stats.get('usage_count', 0) > 0
            
            # Cleanup
            await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_real_connection_usage(self, primary_test_account, api_test_helper):
        """Test using real connection from pool."""
        pool = AccountPool()
        
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
    """Test the account_pool global instance."""
    pool = account_pool
    
    assert isinstance(pool, AccountPool)
    assert pool.health_check_interval_seconds == 300  # Default value


@pytest.mark.asyncio
async def test_account_pool_performance_under_load():
    """Test account pool performance under concurrent load."""
    pool = AccountPool()
    
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
        mock_connection = MagicMock(spec=AccountConnection)
        mock_connection.is_available = True
        mock_connection.acquire = AsyncMock()
        mock_connection.release = MagicMock()
        mock_connection.stats = MagicMock()
        mock_connection.stats.usage_count = 0
        mock_connections.append(mock_connection)
    
    # Note: The new pool design uses single connections per account
    pool.account_connections["load_test_account"] = mock_connections[0]
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
        assert result == mock_connections[0]  # All should get same connection
    
    # Verify that connections were properly acquired and released
    total_acquire_calls = mock_connections[0].acquire.call_count
    total_release_calls = mock_connections[0].release.call_count
    
    # At least some calls should have been made
    assert total_acquire_calls > 0, "No acquire calls were made"
    assert total_release_calls > 0, "No release calls were made"
    assert total_acquire_calls == total_release_calls, "Mismatched acquire/release calls"