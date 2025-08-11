"""Enhanced test configuration system with real API credentials management."""

import os
import yaml
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TestEnvironmentType(Enum):
    """Test environment types."""
    UNIT = "unit"
    INTEGRATION = "integration"
    WEBSOCKET = "websocket"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class TestCredentials:
    """Test credentials for Alpaca API."""
    api_key: str
    secret_key: str
    account_id: str
    paper_trading: bool = True
    base_url: str = "https://paper-api.alpaca.markets"
    websocket_url: str = "wss://stream.data.alpaca.markets/v2"


@dataclass
class TestAccount:
    """Test account configuration."""
    name: str
    credentials: TestCredentials
    tier: str = "standard"
    max_connections: int = 3
    enabled: bool = True
    region: str = "us"


@dataclass
class TestEnvironment:
    """Test environment configuration."""
    name: str
    type: TestEnvironmentType
    accounts: List[TestAccount]
    test_symbols: List[str] = field(default_factory=lambda: ["AAPL", "MSFT", "GOOGL"])
    cleanup_enabled: bool = True
    parallel_execution: bool = True
    max_workers: int = 4
    timeout_seconds: int = 300


class RealAPITestConfig:
    """Enhanced test configuration system with real API credentials management."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize test configuration.
        
        Args:
            config_path: Path to configuration file. Defaults to secrets.yml in project root.
        """
        self.project_root = Path(__file__).parent.parent
        self.config_path = config_path or self.project_root / "secrets.yml"
        self.test_data_dir = self.project_root / "tests" / "data"
        self.coverage_dir = self.project_root / "htmlcov"
        self.reports_dir = self.project_root / "test-reports"
        
        # Ensure directories exist
        self.test_data_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self._config_data = self._load_config()
        self._test_accounts = self._load_test_accounts()
        self._test_environments = self._setup_test_environments()
        
        # Track test resources for cleanup
        self.test_orders: List[str] = []
        self.test_positions: List[str] = []
        self.active_connections: List[Any] = []
        self.cleanup_handlers: List[callable] = []
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise
    
    def _load_test_accounts(self) -> List[TestAccount]:
        """Load test accounts from configuration."""
        accounts = []
        
        # Load multi-account configuration
        if "accounts" in self._config_data:
            for account_id, account_config in self._config_data["accounts"].items():
                if account_config.get("enabled", True):
                    credentials = TestCredentials(
                        api_key=account_config["api_key"],
                        secret_key=account_config["secret_key"],
                        account_id=account_id,
                        paper_trading=account_config.get("paper_trading", True),
                        base_url=account_config.get("base_url", "https://paper-api.alpaca.markets")
                    )
                    
                    account = TestAccount(
                        name=account_config.get("name", f"Test Account {account_id}"),
                        credentials=credentials,
                        tier=account_config.get("tier", "standard"),
                        max_connections=account_config.get("max_connections", 3),
                        enabled=account_config.get("enabled", True),
                        region=account_config.get("region", "us")
                    )
                    accounts.append(account)
        
        # Fallback to legacy single account configuration
        elif "alpaca" in self._config_data:
            alpaca_config = self._config_data["alpaca"]
            credentials = TestCredentials(
                api_key=alpaca_config["api_key"],
                secret_key=alpaca_config["secret_key"],
                account_id="legacy_account",
                paper_trading=alpaca_config.get("paper_trading", True),
                base_url=alpaca_config.get("base_url", "https://paper-api.alpaca.markets")
            )
            
            account = TestAccount(
                name="Legacy Test Account",
                credentials=credentials,
                tier="standard",
                max_connections=3,
                enabled=True,
                region="us"
            )
            accounts.append(account)
        
        if not accounts:
            raise ValueError("No enabled test accounts found in configuration")
        
        return accounts
    
    def _setup_test_environments(self) -> Dict[TestEnvironmentType, TestEnvironment]:
        """Setup different test environments."""
        environments = {}
        
        # Unit test environment - single account, minimal setup
        environments[TestEnvironmentType.UNIT] = TestEnvironment(
            name="Unit Tests",
            type=TestEnvironmentType.UNIT,
            accounts=self._test_accounts[:1],  # Use first account only
            test_symbols=["AAPL", "MSFT"],
            cleanup_enabled=True,
            parallel_execution=True,
            max_workers=2,
            timeout_seconds=60
        )
        
        # Integration test environment - multiple accounts
        environments[TestEnvironmentType.INTEGRATION] = TestEnvironment(
            name="Integration Tests",
            type=TestEnvironmentType.INTEGRATION,
            accounts=self._test_accounts,
            test_symbols=["AAPL", "MSFT", "GOOGL", "TSLA"],
            cleanup_enabled=True,
            parallel_execution=True,
            max_workers=4,
            timeout_seconds=300
        )
        
        # WebSocket test environment - optimized for real-time testing
        environments[TestEnvironmentType.WEBSOCKET] = TestEnvironment(
            name="WebSocket Tests",
            type=TestEnvironmentType.WEBSOCKET,
            accounts=self._test_accounts[:2],  # Limit connections
            test_symbols=["AAPL", "MSFT", "GOOGL"],
            cleanup_enabled=True,
            parallel_execution=False,  # Sequential for WebSocket stability
            max_workers=1,
            timeout_seconds=120
        )
        
        # Performance test environment - load testing setup
        environments[TestEnvironmentType.PERFORMANCE] = TestEnvironment(
            name="Performance Tests",
            type=TestEnvironmentType.PERFORMANCE,
            accounts=self._test_accounts,
            test_symbols=["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
            cleanup_enabled=True,
            parallel_execution=True,
            max_workers=8,
            timeout_seconds=600
        )
        
        # Security test environment - security-focused testing
        environments[TestEnvironmentType.SECURITY] = TestEnvironment(
            name="Security Tests",
            type=TestEnvironmentType.SECURITY,
            accounts=self._test_accounts[:1],
            test_symbols=["AAPL"],
            cleanup_enabled=True,
            parallel_execution=False,  # Sequential for security testing
            max_workers=1,
            timeout_seconds=180
        )
        
        return environments
    
    def get_test_environment(self, env_type: TestEnvironmentType) -> TestEnvironment:
        """Get test environment by type."""
        return self._test_environments[env_type]
    
    def get_test_credentials(self, account_name: Optional[str] = None) -> TestCredentials:
        """Get test credentials for specified account or first available."""
        if account_name:
            for account in self._test_accounts:
                if account.name == account_name:
                    return account.credentials
            raise ValueError(f"Account '{account_name}' not found")
        
        return self._test_accounts[0].credentials
    
    def get_test_accounts(self, tier: Optional[str] = None) -> List[TestAccount]:
        """Get test accounts, optionally filtered by tier."""
        if tier:
            return [acc for acc in self._test_accounts if acc.tier == tier]
        return self._test_accounts.copy()
    
    def register_test_order(self, order_id: str) -> None:
        """Register test order for cleanup."""
        self.test_orders.append(order_id)
    
    def register_test_position(self, symbol: str) -> None:
        """Register test position for cleanup."""
        self.test_positions.append(symbol)
    
    def register_connection(self, connection: Any) -> None:
        """Register active connection for cleanup."""
        self.active_connections.append(connection)
    
    def register_cleanup_handler(self, handler: callable) -> None:
        """Register cleanup handler."""
        self.cleanup_handlers.append(handler)
    
    async def cleanup_test_data(self) -> None:
        """Clean up all test data and resources."""
        logger.info("Starting test data cleanup...")
        
        # Run custom cleanup handlers
        for handler in self.cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"Error in cleanup handler: {e}")
        
        # Close active connections
        for connection in self.active_connections:
            try:
                if hasattr(connection, 'close'):
                    if asyncio.iscoroutinefunction(connection.close):
                        await connection.close()
                    else:
                        connection.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        
        # Clear tracking lists
        self.test_orders.clear()
        self.test_positions.clear()
        self.active_connections.clear()
        self.cleanup_handlers.clear()
        
        logger.info("Test data cleanup completed")
    
    def get_coverage_config(self) -> Dict[str, Any]:
        """Get coverage configuration."""
        return {
            "source": ["app"],
            "omit": [
                "*/tests/*",
                "*/venv/*",
                "*/__pycache__/*",
                "*/migrations/*"
            ],
            "exclude_lines": [
                "pragma: no cover",
                "def __repr__",
                "raise AssertionError",
                "raise NotImplementedError",
                "if __name__ == .__main__.:"
            ],
            "html_dir": str(self.coverage_dir),
            "xml_output": str(self.reports_dir / "coverage.xml"),
            "json_output": str(self.reports_dir / "coverage.json")
        }
    
    def get_pytest_config(self) -> Dict[str, Any]:
        """Get pytest configuration."""
        return {
            "testpaths": ["tests"],
            "python_files": ["test_*.py"],
            "python_functions": ["test_*"],
            "python_classes": ["Test*"],
            "addopts": [
                "-v",
                "--tb=short",
                "--strict-markers",
                "--disable-warnings",
                f"--cov=app",
                f"--cov-report=html:{self.coverage_dir}",
                f"--cov-report=xml:{self.reports_dir}/coverage.xml",
                f"--cov-report=json:{self.reports_dir}/coverage.json",
                f"--html={self.reports_dir}/report.html",
                f"--json-report={self.reports_dir}/report.json",
                "--self-contained-html"
            ],
            "asyncio_mode": "auto",
            "markers": {
                "slow": "marks tests as slow (deselect with '-m \"not slow\"')",
                "integration": "marks tests as integration tests",
                "unit": "marks tests as unit tests",
                "websocket": "marks tests as WebSocket tests",
                "performance": "marks tests as performance tests",
                "security": "marks tests as security tests",
                "auth": "marks tests related to authentication",
                "middleware": "marks tests related to middleware",
                "alpaca": "marks tests related to Alpaca API",
                "error_handling": "marks tests related to error handling",
                "real_api": "marks tests that use real API calls"
            }
        }
    
    @property
    def project_root_path(self) -> Path:
        """Get project root path."""
        return self.project_root
    
    @property
    def test_data_path(self) -> Path:
        """Get test data directory path."""
        return self.test_data_dir
    
    @property
    def reports_path(self) -> Path:
        """Get test reports directory path."""
        return self.reports_dir