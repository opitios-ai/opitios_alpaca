"""Pytest configuration and fixtures for Opitios Alpaca tests."""

import pytest
import pytest_asyncio
import asyncio
import logging
import uuid
from pathlib import Path
import sys
from typing import AsyncGenerator, Generator
from datetime import datetime, timedelta

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.config import RealAPITestConfig, TestEnvironmentType, TestCredentials, TestAccount
from tests.utils import (
    RealAPITestClient, 
    WebSocketTestManager, 
    APITestHelper,
    RateLimitHelper,
    TestDataManager,
    TestEnvironmentManager,
    ManagedTestEnvironment,
    CleanupVerificationSystem,
    CleanupReportingSystem,
    SymbolValidationType
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    # Get current event loop or create new one
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    yield loop
    
    # Clean up
    if not loop.is_closed():
        loop.close()


@pytest.fixture(scope="session")
def test_config() -> RealAPITestConfig:
    """Provide the main test configuration instance."""
    return RealAPITestConfig()


@pytest_asyncio.fixture(scope="session")
async def test_config_with_cleanup(test_config: RealAPITestConfig) -> AsyncGenerator[RealAPITestConfig, None]:
    """Provide test configuration with automatic cleanup after session."""
    yield test_config
    await test_config.cleanup_test_data()


@pytest.fixture
def project_root_path(test_config: RealAPITestConfig) -> Path:
    """Provide the project root path."""
    return test_config.project_root_path


@pytest.fixture
def test_data_path(test_config: RealAPITestConfig) -> Path:
    """Provide the test data directory path."""
    return test_config.test_data_path


@pytest.fixture
def reports_path(test_config: RealAPITestConfig) -> Path:
    """Provide the test reports directory path."""
    return test_config.reports_path


@pytest.fixture
def secrets_file_path(test_config: RealAPITestConfig) -> Path:
    """Provide the secrets file path."""
    return test_config.config_path


@pytest.fixture
def real_api_credentials(test_config: RealAPITestConfig) -> TestCredentials:
    """Provide real Alpaca API credentials for testing."""
    credentials = test_config.get_test_credentials()
    
    # Validate credentials before returning
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(
            api_key=credentials.api_key,
            secret_key=credentials.secret_key,
            paper=credentials.paper_trading
        )
        # Quick test to validate credentials
        account = client.get_account()
        logger.info(f"Credentials validated for account: {account.account_number}")
        return credentials
    except Exception as e:
        logger.warning(f"Invalid API credentials detected: {e}")
        pytest.skip(f"Skipping test due to invalid API credentials: {e}")


@pytest.fixture
def primary_test_account(test_config: RealAPITestConfig) -> TestAccount:
    """Provide the primary test account."""
    accounts = test_config.get_test_accounts()
    primary_account = accounts[0]
    
    # Validate primary account credentials
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(
            api_key=primary_account.credentials.api_key,
            secret_key=primary_account.credentials.secret_key,
            paper=primary_account.credentials.paper_trading
        )
        # Quick test to validate credentials
        account = client.get_account()
        logger.info(f"Primary account validated: {account.account_number}")
        return primary_account
    except Exception as e:
        logger.warning(f"Invalid primary account credentials: {e}")
        pytest.skip(f"Skipping test due to invalid primary account credentials: {e}")


@pytest.fixture
def all_test_accounts(test_config: RealAPITestConfig) -> list[TestAccount]:
    """Provide all available test accounts (only those with valid credentials)."""
    accounts = test_config.get_test_accounts()
    valid_accounts = []
    
    from alpaca.trading.client import TradingClient
    
    for account in accounts:
        try:
            client = TradingClient(
                api_key=account.credentials.api_key,
                secret_key=account.credentials.secret_key,
                paper=account.credentials.paper_trading
            )
            # Quick test to validate credentials
            client.get_account()
            valid_accounts.append(account)
            logger.info(f"Account {account.name} credentials are valid")
        except Exception as e:
            logger.warning(f"Account {account.name} has invalid credentials: {e}")
            continue
    
    if not valid_accounts:
        pytest.skip("No valid test accounts available - all API credentials are invalid")
    
    return valid_accounts


@pytest.fixture
def unit_test_environment(test_config: RealAPITestConfig):
    """Provide unit test environment configuration."""
    return test_config.get_test_environment(TestEnvironmentType.UNIT)


@pytest.fixture
def integration_test_environment(test_config: RealAPITestConfig):
    """Provide integration test environment configuration."""
    return test_config.get_test_environment(TestEnvironmentType.INTEGRATION)


@pytest.fixture
def websocket_test_environment(test_config: RealAPITestConfig):
    """Provide WebSocket test environment configuration."""
    return test_config.get_test_environment(TestEnvironmentType.WEBSOCKET)


@pytest.fixture
def performance_test_environment(test_config: RealAPITestConfig):
    """Provide performance test environment configuration."""
    return test_config.get_test_environment(TestEnvironmentType.PERFORMANCE)


@pytest.fixture
def security_test_environment(test_config: RealAPITestConfig):
    """Provide security test environment configuration."""
    return test_config.get_test_environment(TestEnvironmentType.SECURITY)


@pytest_asyncio.fixture(scope="function")
async def test_cleanup_handler(test_config: RealAPITestConfig):
    """Provide a cleanup handler for individual tests."""
    cleanup_tasks = []
    
    def register_cleanup(task):
        """Register a cleanup task."""
        cleanup_tasks.append(task)
    
    yield register_cleanup
    
    # Execute cleanup tasks
    for task in cleanup_tasks:
        try:
            if asyncio.iscoroutinefunction(task):
                await task()
            else:
                task()
        except Exception as e:
            logger.error(f"Error in test cleanup: {e}")


@pytest.fixture
def test_symbols() -> list[str]:
    """Provide standard test symbols."""
    return ["AAPL", "MSFT", "GOOGL", "TSLA"]


@pytest.fixture
def test_option_symbols() -> list[str]:
    """Provide test option symbols."""
    return [
        "AAPL240315C00150000",  # AAPL call option
        "MSFT240315P00300000",  # MSFT put option
    ]


# Credential validation fixture
@pytest.fixture(scope="session")
def api_credentials_available(test_config: RealAPITestConfig) -> bool:
    """Check if any valid API credentials are available."""
    from alpaca.trading.client import TradingClient
    accounts = test_config.get_test_accounts()
    
    for account in accounts:
        try:
            client = TradingClient(
                api_key=account.credentials.api_key,
                secret_key=account.credentials.secret_key,
                paper=account.credentials.paper_trading
            )
            client.get_account()
            logger.info("Valid API credentials found")
            return True
        except Exception:
            continue
    
    logger.warning("No valid API credentials found")
    return False

# Legacy fixtures for backward compatibility
@pytest.fixture
def mock_alpaca_credentials():
    """Provide mock Alpaca credentials for testing (legacy compatibility)."""
    return {
        "api_key": "test_api_key",
        "secret_key": "test_secret_key",
        "paper_trading": True
    }


# Pytest hooks for enhanced test management


# New utility fixtures from utils package
@pytest_asyncio.fixture(scope="function")
async def real_api_client(primary_test_account: TestAccount) -> AsyncGenerator[RealAPITestClient, None]:
    """Provide a RealAPITestClient with automatic cleanup."""
    client = None
    try:
        client = RealAPITestClient(primary_test_account, test_prefix="PYTEST")
        
        # Verify connection before yielding
        connection_result = await client.verify_connection()
        if connection_result.get("status") != "connected":
            pytest.skip(f"Cannot connect to Alpaca API: {connection_result}")
        
        yield client
        
    except Exception as e:
        logger.error(f"Error in real_api_client fixture: {e}")
        raise
    finally:
        # Cleanup after test
        if client:
            try:
                await client.cleanup_all_test_data()
            except Exception as e:
                logger.error(f"Error during client cleanup: {e}")


@pytest_asyncio.fixture(scope="function")
async def websocket_manager(real_api_credentials: TestCredentials) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket test manager with automatic cleanup."""
    manager = None
    try:
        manager = WebSocketTestManager(real_api_credentials)
        yield manager
    finally:
        # Cleanup connections
        if manager:
            try:
                await manager.close_all_connections()
            except Exception as e:
                logger.error(f"Error during WebSocket cleanup: {e}")


@pytest_asyncio.fixture(scope="function")
async def stock_websocket_connection(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with established stock data connection."""
    from tests.utils.websocket_helpers import WebSocketEndpoint
    
    try:
        # Establish stock data connection with extended timeout
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.STOCK_DATA, timeout=30
        )
        
        if not success:
            pytest.skip("Cannot establish stock data WebSocket connection")
        
        yield websocket_manager
        
    except Exception as e:
        logger.error(f"Error establishing stock WebSocket connection: {e}")
        pytest.skip(f"Stock WebSocket connection failed: {e}")


@pytest_asyncio.fixture(scope="function")
async def option_websocket_connection(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with established option data connection."""
    from tests.utils.websocket_helpers import WebSocketEndpoint
    
    try:
        # Establish option data connection with extended timeout
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.OPTION_DATA, timeout=30
        )
        
        if not success:
            pytest.skip("Cannot establish option data WebSocket connection")
        
        yield websocket_manager
        
    except Exception as e:
        logger.error(f"Error establishing option WebSocket connection: {e}")
        pytest.skip(f"Option WebSocket connection failed: {e}")


@pytest_asyncio.fixture(scope="function")  
async def trading_websocket_connection(websocket_manager: WebSocketTestManager) -> AsyncGenerator[WebSocketTestManager, None]:
    """Provide a WebSocket manager with established trading updates connection."""
    from tests.utils.websocket_helpers import WebSocketEndpoint
    
    try:
        # Establish trading updates connection with extended timeout
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.TRADE_UPDATES, timeout=30
        )
        
        if not success:
            pytest.skip("Cannot establish trading updates WebSocket connection")
        
        yield websocket_manager
        
    except Exception as e:
        logger.error(f"Error establishing trading WebSocket connection: {e}")
        pytest.skip(f"Trading WebSocket connection failed: {e}")


@pytest.fixture
def api_test_helper() -> APITestHelper:
    """Provide API test helper for performance monitoring."""
    return APITestHelper()


@pytest.fixture
def rate_limit_helper() -> RateLimitHelper:
    """Provide rate limit helper for API testing."""
    return RateLimitHelper(calls_per_minute=200)


@pytest.fixture(scope="function")
def websocket_timeout_config() -> dict:
    """Provide WebSocket timeout configuration for tests."""
    return {
        "connection_timeout": 30,      # Connection establishment timeout
        "message_timeout": 60,         # Wait for messages timeout
        "auth_timeout": 15,           # Authentication timeout
        "subscription_timeout": 20,    # Subscription confirmation timeout
        "health_check_timeout": 10,   # Health check ping timeout
        "cleanup_timeout": 15,        # Connection cleanup timeout
        "reconnection_timeout": 45,   # Reconnection attempt timeout
        "test_timeout": 300,          # Overall test timeout
    }


@pytest.fixture(scope="function")
def websocket_test_symbols() -> dict:
    """Provide test symbols optimized for WebSocket testing."""
    return {
        "stock_symbols": ["AAPL", "MSFT", "GOOGL"],  # Active, liquid stocks
        "option_symbols": [
            "AAPL240315C00150000",  # AAPL call option
            "MSFT240315P00300000",  # MSFT put option
            "GOOGL240315C02500000", # GOOGL call option
        ],
        "test_symbols": ["FAKEPACA"],  # Alpaca test symbol
        "minimal_symbols": ["AAPL"],   # For quick connection tests
    }


# New comprehensive test data management fixtures

@pytest_asyncio.fixture(scope="session")
async def comprehensive_test_manager(test_config: RealAPITestConfig) -> TestDataManager:
    """Provide a comprehensive test data manager for the session."""
    manager = TestDataManager(test_prefix="COMPREHENSIVE_TESTS")
    manager.start_test_session(TestEnvironmentType.INTEGRATION)
    
    yield manager
    
    # Clean up at session end
    try:
        await manager.cleanup_all_test_data()
    except Exception as e:
        logger.error(f"Error during comprehensive test manager cleanup: {e}")


@pytest_asyncio.fixture(scope="function")
async def managed_test_environment(test_config: RealAPITestConfig) -> ManagedTestEnvironment:
    """Provide a managed test environment with automatic setup and teardown."""
    env_manager = TestEnvironmentManager(test_config)
    
    # Setup environment
    session = await env_manager.setup_test_environment(
        TestEnvironmentType.UNIT,
        symbol_validation=SymbolValidationType.BASIC
    )
    
    yield session
    
    # Teardown environment
    try:
        await env_manager.teardown_test_environment(verify_cleanup=True)
    except Exception as e:
        logger.error(f"Error during managed test environment teardown: {e}")


@pytest.fixture(scope="session")
def cleanup_verification_system() -> CleanupVerificationSystem:
    """Provide cleanup verification system."""
    return CleanupVerificationSystem()


@pytest.fixture(scope="session") 
def cleanup_reporting_system() -> CleanupReportingSystem:
    """Provide cleanup reporting system."""
    return CleanupReportingSystem()


@pytest_asyncio.fixture(scope="function")
async def isolated_test_client(test_config: RealAPITestConfig) -> RealAPITestClient:
    """Provide an isolated test client with automatic cleanup tracking."""
    accounts = test_config.get_test_accounts()
    if not accounts:
        pytest.skip("No test accounts available")
    
    client = RealAPITestClient(accounts[0], test_prefix=f"ISOLATED_{uuid.uuid4().hex[:8]}")
    
    # Verify connection
    connection_result = await client.verify_connection()
    if connection_result.get("status") != "connected":
        pytest.skip(f"Cannot connect to Alpaca API: {connection_result}")
    
    yield client
    
    # Enhanced cleanup with verification
    try:
        cleanup_results = await client.cleanup_all_test_data()
        logger.info(f"Isolated client cleanup completed: {cleanup_results}")
        
        # Additional verification
        remaining_orders = len(client.test_orders)
        remaining_positions = len(client.test_positions)
        
        if remaining_orders > 0 or remaining_positions > 0:
            logger.warning(f"Incomplete cleanup detected: {remaining_orders} orders, {remaining_positions} positions remaining")
            
    except Exception as e:
        logger.error(f"Error during isolated client cleanup: {e}")


@pytest_asyncio.fixture(scope="function")
async def multi_account_test_environment(test_config: RealAPITestConfig):
    """Provide a multi-account test environment for complex scenarios."""
    accounts = test_config.get_test_accounts()
    if len(accounts) < 2:
        pytest.skip("Multi-account testing requires at least 2 test accounts")
    
    env_manager = TestEnvironmentManager(test_config)
    
    # Setup environment with multiple accounts
    session = await env_manager.setup_test_environment(
        TestEnvironmentType.INTEGRATION,
        custom_accounts=accounts[:2],  # Use first 2 accounts
        symbol_validation=SymbolValidationType.MARKET_DATA
    )
    
    yield session
    
    # Comprehensive cleanup
    try:
        teardown_results = await env_manager.teardown_test_environment(verify_cleanup=True)
        logger.info(f"Multi-account environment teardown: {teardown_results}")
    except Exception as e:
        logger.error(f"Error during multi-account environment teardown: {e}")


@pytest.fixture(scope="function")
def test_session_tracker():
    """Track test session data for cleanup verification."""
    import uuid
    session_data = {
        "session_id": f"test_{uuid.uuid4().hex[:8]}",
        "start_time": datetime.now(),
        "test_orders": [],
        "test_positions": [],
        "test_symbols": set(),
        "cleanup_verified": False
    }
    
    def track_order(order_id: str, symbol: str):
        """Track a test order."""
        session_data["test_orders"].append({"order_id": order_id, "symbol": symbol})
        session_data["test_symbols"].add(symbol)
    
    def track_position(symbol: str, qty: float):
        """Track a test position."""
        session_data["test_positions"].append({"symbol": symbol, "qty": qty})
        session_data["test_symbols"].add(symbol)
    
    def get_summary():
        """Get session summary."""
        return {
            **session_data,
            "test_symbols": list(session_data["test_symbols"]),
            "duration": (datetime.now() - session_data["start_time"]).total_seconds()
        }
    
    session_data["track_order"] = track_order
    session_data["track_position"] = track_position
    session_data["get_summary"] = get_summary
    
    yield session_data
    
    # Log session summary
    summary = get_summary()
    logger.info(f"Test session summary: {summary}")


@pytest_asyncio.fixture(scope="function")
async def verified_cleanup_client(primary_test_account: TestAccount, cleanup_verification_system: CleanupVerificationSystem):
    """Provide a test client with verified cleanup."""
    import uuid
    client = RealAPITestClient(primary_test_account, test_prefix=f"VERIFIED_{uuid.uuid4().hex[:8]}")
    
    # Verify connection
    connection_result = await client.verify_connection()
    if connection_result.get("status") != "connected":
        pytest.skip(f"Cannot connect to Alpaca API: {connection_result}")
    
    yield client
    
    # Perform cleanup with verification
    try:
        # Cleanup test data
        cleanup_results = await client.cleanup_all_test_data()
        
        # Create mock test data manager for verification
        from tests.utils.test_data_manager import TestSession
        mock_session = TestSession(
            session_id=client.test_prefix,
            start_time=datetime.now(),
            test_prefix=client.test_prefix,
            environment_type=TestEnvironmentType.UNIT
        )
        
        # Mock test data manager
        class MockTestDataManager:
            def __init__(self):
                self.current_session = mock_session
                self.active_clients = {primary_test_account.credentials.account_id: client}
        
        mock_manager = MockTestDataManager()
        
        # Verify cleanup
        verification_report = await cleanup_verification_system.verify_cleanup(mock_manager)
        
        logger.info(f"Cleanup verification completed: {verification_report.success_rate:.1f}% success rate")
        
        if verification_report.failed_checks > 0:
            logger.warning(f"Verification found {verification_report.failed_checks} failed checks")
            
    except Exception as e:
        logger.error(f"Error during verified cleanup: {e}")


@pytest.fixture(autouse=True)
def test_isolation():
    """Ensure test isolation by cleaning up between tests."""
    # Setup phase - record test start
    test_start_time = datetime.now()
    logger.debug(f"Starting test at {test_start_time}")
    
    yield
    
    # Teardown phase - log test completion
    test_end_time = datetime.now()
    test_duration = (test_end_time - test_start_time).total_seconds()
    logger.debug(f"Test completed in {test_duration:.2f} seconds")


# Enhanced pytest hooks for comprehensive test management
def pytest_configure(config):
    """Configure pytest with enhanced settings for comprehensive testing."""
    # Ensure test directories exist
    test_reports_dir = Path("test-reports")
    test_reports_dir.mkdir(exist_ok=True)
    
    htmlcov_dir = Path("htmlcov")
    htmlcov_dir.mkdir(exist_ok=True)
    
    # Create comprehensive test logs directory
    test_logs_dir = Path("test-logs")
    test_logs_dir.mkdir(exist_ok=True)
    
    # Configure additional markers
    markers = [
        "real_api: mark test as using real API calls",
        "comprehensive: mark test as using comprehensive test data management",
        "cleanup_verification: mark test as requiring cleanup verification",
        "multi_account: mark test as requiring multiple accounts",
        "isolated: mark test as requiring isolated test environment",
        "data_management: mark test as testing data management features"
    ]
    
    for marker in markers:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add enhanced markers."""
    for item in items:
        test_file = str(item.fspath)
        
        # Add existing markers based on test file location
        if "/unit/" in test_file:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in test_file:
            item.add_marker(pytest.mark.integration)
        elif "/websocket/" in test_file:
            item.add_marker(pytest.mark.websocket)
        elif "/performance/" in test_file:
            item.add_marker(pytest.mark.performance)
        elif "/security/" in test_file:
            item.add_marker(pytest.mark.security)
        
        # Add comprehensive testing markers
        if "comprehensive" in test_file or "data_management" in test_file:
            item.add_marker(pytest.mark.comprehensive)
        
        if "cleanup" in test_file:
            item.add_marker(pytest.mark.cleanup_verification)
        
        # Add real_api marker for tests using real API
        if "real_api" in test_file or "alpaca" in test_file.lower():
            item.add_marker(pytest.mark.real_api)