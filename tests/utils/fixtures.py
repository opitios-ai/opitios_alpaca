"""Shared fixtures for consistent test setup across all test categories."""

import pytest
import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from pathlib import Path
from datetime import datetime, time

from tests.config import RealAPITestConfig, TestEnvironmentType, TestCredentials, TestAccount
from tests.utils.real_api_client import RealAPITestClient
from tests.utils.websocket_helpers import WebSocketTestManager, WebSocketEndpoint

logger = logging.getLogger(__name__)


# Real API Client Fixtures
@pytest.fixture
async def real_api_client(primary_test_account: TestAccount) -> AsyncGenerator[RealAPITestClient, None]:
    """Provide a RealAPITestClient with automatic cleanup."""
    client = RealAPITestClient(primary_test_account, test_prefix="PYTEST")
    
    # Verify connection before yielding
    connection_result = await client.verify_connection()
    if connection_result.get("status") != "connected":
        pytest.skip(f"Cannot connect to Alpaca API: {connection_result}")
    
    yield client
    
    # Cleanup after test
    try:
        await client.cleanup_all_test_data()
    except Exception as e:
        logger.error(f"Error during client cleanup: {e}")


@pytest.fixture
async def multi_account_clients(all_test_accounts: List[TestAccount]) -> AsyncGenerator[List[RealAPITestClient], None]:
    """Provide multiple RealAPITestClients for multi-account testing."""
    clients = []
    
    for account in all_test_accounts:
        client = RealAPITestClient(account, test_prefix="PYTEST_MULTI")
        
        # Verify connection
        connection_result = await client.verify_connection()
        if connection_result.get("status") == "connected":
            clients.append(client)
        else:
            logger.warning(f"Skipping account {account.name}: {connection_result}")
    
    if not clients:
        pytest.skip("No valid API connections available for multi-account testing")
    
    yield clients
    
    # Cleanup all clients
    for client in clients:
        try:
            await client.cleanup_all_test_data()
        except Exception as e:
            logger.error(f"Error during multi-client cleanup: {e}")


@pytest.fixture
async def verified_api_client(real_api_client: RealAPITestClient) -> RealAPITestClient:
    """Provide a verified API client (connection already tested)."""
    return real_api_client


# WebSocket Testing Fixtures
@pytest.fixture
async def websocket_manager(real_api_credentials: TestCredentials) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket test manager with automatic cleanup."""
    manager = WebSocketTestManager(real_api_credentials)
    
    yield manager
    
    # Cleanup connections
    try:
        await manager.close_all_connections()
    except Exception as e:
        logger.error(f"Error during WebSocket cleanup: {e}")


@pytest.fixture
async def stock_websocket_connection(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with established stock data connection."""
    success = await websocket_manager.establish_connection(WebSocketEndpoint.STOCK_DATA)
    
    if not success:
        pytest.skip("Cannot establish stock data WebSocket connection")
    
    yield websocket_manager


@pytest.fixture
async def option_websocket_connection(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with established option data connection."""
    success = await websocket_manager.establish_connection(WebSocketEndpoint.OPTION_DATA)
    
    if not success:
        pytest.skip("Cannot establish option data WebSocket connection")
    
    yield websocket_manager


@pytest.fixture
async def trade_websocket_connection(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with established trade updates connection."""
    success = await websocket_manager.establish_connection(WebSocketEndpoint.TRADE_UPDATES)
    
    if not success:
        pytest.skip("Cannot establish trade updates WebSocket connection")
    
    yield websocket_manager


@pytest.fixture
async def all_websocket_connections(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with all connections established."""
    connections_established = []
    
    for endpoint in WebSocketEndpoint:
        success = await websocket_manager.establish_connection(endpoint)
        if success:
            connections_established.append(endpoint)
        else:
            logger.warning(f"Failed to establish connection to {endpoint.value}")
    
    if not connections_established:
        pytest.skip("Cannot establish any WebSocket connections")
    
    logger.info(f"Established {len(connections_established)} WebSocket connections")
    yield websocket_manager


# Test Data Fixtures
@pytest.fixture
def test_stock_symbols() -> List[str]:
    """Provide standard test stock symbols."""
    return ["AAPL", "MSFT", "GOOGL", "TSLA"]


@pytest.fixture
def test_option_symbols() -> List[str]:
    """Provide test option symbols."""
    return [
        "AAPL240315C00150000",  # AAPL call option
        "MSFT240315P00300000",  # MSFT put option
        "GOOGL240315C02500000", # GOOGL call option
    ]


@pytest.fixture
def test_trading_symbols() -> List[str]:
    """Provide symbols suitable for test trading (high liquidity, low price)."""
    return ["SQQQ", "TQQQ", "SPY", "QQQ"]  # ETFs for safer test trading


@pytest.fixture
def small_test_order_params() -> Dict[str, Any]:
    """Provide parameters for small test orders."""
    return {
        "qty": 1,  # Minimal quantity
        "side": "buy",
        "order_type": "limit",
        "time_in_force": "day"
    }


# Environment-Specific Fixtures
@pytest.fixture
async def unit_test_client(test_config: RealAPITestConfig) -> AsyncGenerator[RealAPITestClient, None]:
    """Provide API client configured for unit testing."""
    env = test_config.get_test_environment(TestEnvironmentType.UNIT)
    client = RealAPITestClient(env.accounts[0], test_prefix="UNIT")
    
    connection_result = await client.verify_connection()
    if connection_result.get("status") != "connected":
        pytest.skip(f"Unit test API connection failed: {connection_result}")
    
    yield client
    
    await client.cleanup_all_test_data()


@pytest.fixture
async def integration_test_clients(test_config: RealAPITestConfig) -> AsyncGenerator[List[RealAPITestClient], None]:
    """Provide API clients configured for integration testing."""
    env = test_config.get_test_environment(TestEnvironmentType.INTEGRATION)
    clients = []
    
    for account in env.accounts:
        client = RealAPITestClient(account, test_prefix="INTEGRATION")
        connection_result = await client.verify_connection()
        
        if connection_result.get("status") == "connected":
            clients.append(client)
    
    if not clients:
        pytest.skip("No valid connections for integration testing")
    
    yield clients
    
    for client in clients:
        await client.cleanup_all_test_data()


@pytest.fixture
async def performance_test_client(test_config: RealAPITestConfig) -> AsyncGenerator[RealAPITestClient, None]:
    """Provide API client configured for performance testing."""
    env = test_config.get_test_environment(TestEnvironmentType.PERFORMANCE)
    client = RealAPITestClient(env.accounts[0], test_prefix="PERFORMANCE")
    
    connection_result = await client.verify_connection()
    if connection_result.get("status") != "connected":
        pytest.skip(f"Performance test API connection failed: {connection_result}")
    
    yield client
    
    await client.cleanup_all_test_data()


@pytest.fixture
async def security_test_client(test_config: RealAPITestConfig) -> AsyncGenerator[RealAPITestClient, None]:
    """Provide API client configured for security testing."""
    env = test_config.get_test_environment(TestEnvironmentType.SECURITY)
    client = RealAPITestClient(env.accounts[0], test_prefix="SECURITY")
    
    connection_result = await client.verify_connection()
    if connection_result.get("status") != "connected":
        pytest.skip(f"Security test API connection failed: {connection_result}")
    
    yield client
    
    await client.cleanup_all_test_data()


# Test Isolation and Cleanup Fixtures
@pytest.fixture
async def isolated_test_environment():
    """Provide isolated test environment with automatic cleanup."""
    test_resources = {
        "orders": [],
        "positions": [],
        "connections": [],
        "cleanup_tasks": []
    }
    
    def register_order(order_id: str):
        test_resources["orders"].append(order_id)
    
    def register_position(symbol: str):
        test_resources["positions"].append(symbol)
    
    def register_connection(connection):
        test_resources["connections"].append(connection)
    
    def register_cleanup_task(task):
        test_resources["cleanup_tasks"].append(task)
    
    # Provide registration functions
    test_resources.update({
        "register_order": register_order,
        "register_position": register_position,
        "register_connection": register_connection,
        "register_cleanup_task": register_cleanup_task
    })
    
    yield test_resources
    
    # Cleanup registered resources
    logger.info("Starting isolated test environment cleanup")
    
    # Execute cleanup tasks
    for task in test_resources["cleanup_tasks"]:
        try:
            if asyncio.iscoroutinefunction(task):
                await task()
            else:
                task()
        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")
    
    # Close connections
    for connection in test_resources["connections"]:
        try:
            if hasattr(connection, 'close'):
                if asyncio.iscoroutinefunction(connection.close):
                    await connection.close()
                else:
                    connection.close()
        except Exception as e:
            logger.error(f"Connection cleanup failed: {e}")
    
    logger.info("Isolated test environment cleanup completed")


# Utility Fixtures
@pytest.fixture
def test_timeout() -> int:
    """Provide standard test timeout in seconds."""
    return 30


@pytest.fixture
def websocket_timeout() -> int:
    """Provide WebSocket-specific timeout in seconds."""
    return 60


@pytest.fixture
def performance_timeout() -> int:
    """Provide performance test timeout in seconds."""
    return 300


@pytest.fixture
async def test_data_validator():
    """Provide test data validation utilities."""
    class TestDataValidator:
        @staticmethod
        def validate_stock_quote(quote_data: Dict[str, Any]) -> bool:
            """Validate stock quote data structure."""
            required_fields = ["symbol", "bid_price", "ask_price"]
            return all(field in quote_data for field in required_fields)
        
        @staticmethod
        def validate_option_quote(quote_data: Dict[str, Any]) -> bool:
            """Validate option quote data structure."""
            required_fields = ["symbol", "underlying_symbol", "strike_price", "expiration_date"]
            return all(field in quote_data for field in required_fields)
        
        @staticmethod
        def validate_order_response(order_data: Dict[str, Any]) -> bool:
            """Validate order response data structure."""
            required_fields = ["id", "symbol", "qty", "side", "status"]
            return all(field in order_data for field in required_fields)
        
        @staticmethod
        def validate_account_data(account_data: Dict[str, Any]) -> bool:
            """Validate account data structure."""
            required_fields = ["account_number", "buying_power", "cash", "portfolio_value"]
            return all(field in account_data for field in required_fields)
        
        @staticmethod
        def validate_websocket_message(message_data: Dict[str, Any]) -> bool:
            """Validate WebSocket message structure."""
            return "T" in message_data  # All messages should have type field
    
    return TestDataValidator()


@pytest.fixture
def test_metrics_collector():
    """Provide test metrics collection utilities."""
    class TestMetricsCollector:
        def __init__(self):
            self.metrics = {
                "api_calls": 0,
                "websocket_messages": 0,
                "orders_placed": 0,
                "errors": 0,
                "response_times": []
            }
        
        def record_api_call(self, response_time_ms: float = None):
            self.metrics["api_calls"] += 1
            if response_time_ms:
                self.metrics["response_times"].append(response_time_ms)
        
        def record_websocket_message(self):
            self.metrics["websocket_messages"] += 1
        
        def record_order(self):
            self.metrics["orders_placed"] += 1
        
        def record_error(self):
            self.metrics["errors"] += 1
        
        def get_summary(self) -> Dict[str, Any]:
            avg_response_time = (
                sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
                if self.metrics["response_times"] else 0
            )
            
            return {
                **self.metrics,
                "average_response_time_ms": avg_response_time,
                "error_rate": self.metrics["errors"] / max(self.metrics["api_calls"], 1)
            }
    
    return TestMetricsCollector()


# Parameterized Test Fixtures
@pytest.fixture(params=["AAPL", "MSFT", "GOOGL"])
def parameterized_stock_symbol(request) -> str:
    """Provide parameterized stock symbols for testing multiple symbols."""
    return request.param


@pytest.fixture(params=["1Day", "1Hour", "1Min"])
def parameterized_timeframe(request) -> str:
    """Provide parameterized timeframes for testing different intervals."""
    return request.param


@pytest.fixture(params=["market", "limit"])
def parameterized_order_type(request) -> str:
    """Provide parameterized order types for testing different order types."""
    return request.param


# Conditional Fixtures
@pytest.fixture
def skip_if_market_closed():
    """Skip test if market is closed (for real trading tests)."""
    import pytz
    
    # Check if it's during market hours (9:30 AM - 4:00 PM ET)
    et_tz = pytz.timezone('US/Eastern')
    now_et = datetime.now(et_tz)
    
    market_open = time(9, 30)
    market_close = time(16, 0)
    
    # Skip if outside market hours or weekend
    if (now_et.weekday() >= 5 or  # Weekend
        now_et.time() < market_open or 
        now_et.time() > market_close):
        pytest.skip("Market is closed - skipping real trading test")


@pytest.fixture
def require_paper_trading(real_api_credentials: TestCredentials):
    """Ensure we're using paper trading for safety."""
    if not real_api_credentials.paper_trading:
        pytest.skip("Test requires paper trading to be enabled for safety")


# Async Utilities
@pytest.fixture
def async_timeout():
    """Provide async timeout context manager."""
    return asyncio.timeout


@pytest.fixture
async def event_loop_policy():
    """Provide event loop policy for async tests."""
    return asyncio.get_event_loop_policy()