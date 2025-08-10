"""Test environment management system for automated setup and teardown of test environments."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import random

from .test_data_manager import TestDataManager, TestDataType
from .cleanup_verification import CleanupVerificationSystem, VerificationReport
from .real_api_client import RealAPITestClient
from tests.config import (
    RealAPITestConfig, 
    TestAccount, 
    TestEnvironment, 
    TestEnvironmentType,
    TestCredentials
)


logger = logging.getLogger(__name__)


class EnvironmentState(Enum):
    """States of test environment."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    CLEANING_UP = "cleaning_up"
    COMPLETED = "completed"
    FAILED = "failed"


class SymbolValidationType(Enum):
    """Types of symbol validation."""
    BASIC = "basic"           # Basic format validation
    MARKET_DATA = "market_data"   # Check if market data is available
    TRADEABLE = "tradeable"   # Check if symbol is tradeable
    OPTIONS_CHAIN = "options_chain"  # Validate options chain availability


@dataclass
class TestEnvironmentSession:
    """Information about a test environment session."""
    session_id: str
    environment_type: TestEnvironmentType
    start_time: datetime
    accounts: List[TestAccount]
    test_symbols: List[str]
    validated_symbols: Set[str] = field(default_factory=set)
    state: EnvironmentState = EnvironmentState.INITIALIZING
    data_manager: Optional[TestDataManager] = None
    verification_system: Optional[CleanupVerificationSystem] = None
    end_time: Optional[datetime] = None
    cleanup_report: Optional[Dict[str, Any]] = None
    verification_report: Optional[VerificationReport] = None
    error: Optional[str] = None


class TestEnvironmentManager:
    """
    Automated test environment management system.
    
    This system provides:
    - Automated test environment setup and teardown
    - Account switching for different test scenarios
    - Symbol list management and validation
    - Integration with test data management and cleanup verification
    """
    
    def __init__(self, config: RealAPITestConfig):
        """
        Initialize TestEnvironmentManager.
        
        Args:
            config: RealAPITestConfig instance
        """
        self.config = config
        self.current_session: Optional[TestEnvironmentSession] = None
        self.symbol_validators: Dict[SymbolValidationType, callable] = {}
        self.environment_hooks: Dict[str, List[callable]] = {
            "pre_setup": [],
            "post_setup": [],
            "pre_teardown": [],
            "post_teardown": []
        }
        
        # Initialize built-in symbol validators
        self._setup_builtin_validators()
        
        logger.info("Initialized TestEnvironmentManager")
    
    def _setup_builtin_validators(self):
        """Setup built-in symbol validators."""
        self.symbol_validators[SymbolValidationType.BASIC] = self._validate_symbol_basic
        self.symbol_validators[SymbolValidationType.MARKET_DATA] = self._validate_symbol_market_data
        self.symbol_validators[SymbolValidationType.TRADEABLE] = self._validate_symbol_tradeable
        self.symbol_validators[SymbolValidationType.OPTIONS_CHAIN] = self._validate_symbol_options_chain
    
    def register_environment_hook(self, hook_type: str, hook_function: callable) -> None:
        """
        Register an environment hook.
        
        Args:
            hook_type: Type of hook (pre_setup, post_setup, pre_teardown, post_teardown)
            hook_function: Function to call
        """
        if hook_type in self.environment_hooks:
            self.environment_hooks[hook_type].append(hook_function)
            logger.debug(f"Registered {hook_type} hook: {hook_function.__name__}")
        else:
            logger.warning(f"Unknown hook type: {hook_type}")
    
    def register_symbol_validator(self, validation_type: SymbolValidationType, 
                                validator_function: callable) -> None:
        """
        Register a custom symbol validator.
        
        Args:
            validation_type: Type of validation
            validator_function: Validator function
        """
        self.symbol_validators[validation_type] = validator_function
        logger.debug(f"Registered symbol validator: {validation_type.value}")
    
    async def setup_test_environment(self, environment_type: TestEnvironmentType,
                                   custom_accounts: Optional[List[TestAccount]] = None,
                                   custom_symbols: Optional[List[str]] = None,
                                   symbol_validation: SymbolValidationType = SymbolValidationType.BASIC) -> TestEnvironmentSession:
        """
        Setup a test environment with automatic configuration.
        
        Args:
            environment_type: Type of test environment to setup
            custom_accounts: Optional custom accounts to use
            custom_symbols: Optional custom symbols to use
            symbol_validation: Type of symbol validation to perform
            
        Returns:
            TestEnvironmentSession
        """
        session_id = f"env_{environment_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Setting up test environment: {session_id}")
        
        # Get environment configuration
        environment = self.config.get_test_environment(environment_type)
        
        # Use custom accounts if provided, otherwise use environment defaults
        accounts = custom_accounts or environment.accounts
        test_symbols = custom_symbols or environment.test_symbols
        
        # Create session
        self.current_session = TestEnvironmentSession(
            session_id=session_id,
            environment_type=environment_type,
            start_time=datetime.now(),
            accounts=accounts,
            test_symbols=test_symbols,
            state=EnvironmentState.INITIALIZING
        )
        
        try:
            # Execute pre-setup hooks
            await self._execute_hooks("pre_setup")
            
            # Initialize test data manager
            self.current_session.data_manager = TestDataManager(
                test_prefix=f"ENV_{environment_type.value}_{session_id[-8:]}"
            )
            
            # Start test session in data manager
            self.current_session.data_manager.start_test_session(environment_type)
            
            # Initialize cleanup verification system
            self.current_session.verification_system = CleanupVerificationSystem()
            
            # Setup accounts and validate connections
            await self._setup_accounts()
            
            # Validate test symbols
            await self._validate_test_symbols(symbol_validation)
            
            # Execute post-setup hooks
            await self._execute_hooks("post_setup")
            
            self.current_session.state = EnvironmentState.READY
            logger.info(f"Test environment ready: {session_id}")
            
        except Exception as e:
            self.current_session.state = EnvironmentState.FAILED
            self.current_session.error = str(e)
            logger.error(f"Failed to setup test environment {session_id}: {e}")
            raise
        
        return self.current_session
    
    async def _setup_accounts(self) -> None:
        """Setup and validate account connections."""
        if not self.current_session or not self.current_session.data_manager:
            raise RuntimeError("No active session or data manager")
        
        logger.info(f"Setting up {len(self.current_session.accounts)} accounts")
        
        for account in self.current_session.accounts:
            try:
                # Register client with data manager
                client = await self.current_session.data_manager.register_test_client(account)
                
                # Verify account state
                account_info = await client.get_account()
                if "error" in account_info:
                    raise RuntimeError(f"Account {account.credentials.account_id} error: {account_info['error']}")
                
                logger.debug(f"Account setup successful: {account.credentials.account_id}")
                
            except Exception as e:
                logger.error(f"Failed to setup account {account.credentials.account_id}: {e}")
                raise
    
    async def _validate_test_symbols(self, validation_type: SymbolValidationType) -> None:
        """
        Validate test symbols using the specified validation type.
        
        Args:
            validation_type: Type of validation to perform
        """
        if not self.current_session:
            raise RuntimeError("No active session")
        
        logger.info(f"Validating {len(self.current_session.test_symbols)} symbols with {validation_type.value} validation")
        
        validator = self.symbol_validators.get(validation_type)
        if not validator:
            raise ValueError(f"No validator found for type: {validation_type}")
        
        # Get a client for validation
        if not self.current_session.data_manager or not self.current_session.data_manager.active_clients:
            raise RuntimeError("No active clients available for symbol validation")
        
        client = next(iter(self.current_session.data_manager.active_clients.values()))
        
        # Validate each symbol
        validated_symbols = set()
        for symbol in self.current_session.test_symbols:
            try:
                is_valid = await validator(symbol, client)
                if is_valid:
                    validated_symbols.add(symbol)
                    logger.debug(f"Symbol validated: {symbol}")
                else:
                    logger.warning(f"Symbol failed validation: {symbol}")
            except Exception as e:
                logger.warning(f"Error validating symbol {symbol}: {e}")
        
        self.current_session.validated_symbols = validated_symbols
        
        if not validated_symbols:
            raise RuntimeError("No symbols passed validation")
        
        logger.info(f"Symbol validation completed: {len(validated_symbols)}/{len(self.current_session.test_symbols)} symbols validated")
    
    async def _validate_symbol_basic(self, symbol: str, client: RealAPITestClient) -> bool:
        """Basic symbol format validation."""
        # Basic checks for symbol format
        if not symbol or len(symbol) < 1 or len(symbol) > 12:
            return False
        
        # Check for valid characters (alphanumeric)
        if not symbol.replace('/', '').replace('.', '').isalnum():
            return False
        
        return True
    
    async def _validate_symbol_market_data(self, symbol: str, client: RealAPITestClient) -> bool:
        """Validate that market data is available for symbol."""
        try:
            # Try to get a quote for the symbol
            quote = await client.get_stock_quote(symbol)
            return "error" not in quote and quote.get("symbol") == symbol
        except Exception:
            return False
    
    async def _validate_symbol_tradeable(self, symbol: str, client: RealAPITestClient) -> bool:
        """Validate that symbol is tradeable."""
        try:
            # Get quote and check if tradeable
            quote = await client.get_stock_quote(symbol)
            if "error" in quote:
                return False
            
            # Check for basic trading indicators
            ask_price = quote.get("ask")
            bid_price = quote.get("bid")
            
            return ask_price and bid_price and float(ask_price) > 0 and float(bid_price) > 0
        except Exception:
            return False
    
    async def _validate_symbol_options_chain(self, symbol: str, client: RealAPITestClient) -> bool:
        """Validate that options chain is available for symbol."""
        try:
            # Try to get options chain
            options_chain = await client.get_options_chain(symbol)
            return "error" not in options_chain and len(options_chain.get("option_chains", [])) > 0
        except Exception:
            return False
    
    async def _execute_hooks(self, hook_type: str) -> None:
        """Execute environment hooks of the specified type."""
        hooks = self.environment_hooks.get(hook_type, [])
        
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(self.current_session)
                else:
                    hook(self.current_session)
                logger.debug(f"Executed {hook_type} hook: {hook.__name__}")
            except Exception as e:
                logger.error(f"Error executing {hook_type} hook {hook.__name__}: {e}")
    
    async def switch_account(self, account: TestAccount) -> RealAPITestClient:
        """
        Switch to a different account within the current test session.
        
        Args:
            account: Account to switch to
            
        Returns:
            RealAPITestClient for the account
        """
        if not self.current_session or not self.current_session.data_manager:
            raise RuntimeError("No active test session")
        
        if self.current_session.state != EnvironmentState.READY:
            raise RuntimeError(f"Cannot switch accounts in state: {self.current_session.state}")
        
        logger.info(f"Switching to account: {account.credentials.account_id}")
        
        # Register client with data manager if not already registered
        client = await self.current_session.data_manager.register_test_client(account)
        
        # Add account to session if not already included
        if account not in self.current_session.accounts:
            self.current_session.accounts.append(account)
        
        return client
    
    def get_validated_symbols(self, count: Optional[int] = None, 
                            random_selection: bool = False) -> List[str]:
        """
        Get validated symbols for testing.
        
        Args:
            count: Number of symbols to return (None for all)
            random_selection: Whether to randomly select symbols
            
        Returns:
            List of validated symbols
        """
        if not self.current_session:
            raise RuntimeError("No active test session")
        
        symbols = list(self.current_session.validated_symbols)
        
        if random_selection:
            random.shuffle(symbols)
        
        if count is not None:
            symbols = symbols[:count]
        
        return symbols
    
    async def teardown_test_environment(self, verify_cleanup: bool = True) -> Dict[str, Any]:
        """
        Teardown the test environment with comprehensive cleanup.
        
        Args:
            verify_cleanup: Whether to verify cleanup completion
            
        Returns:
            Teardown results including cleanup and verification reports
        """
        if not self.current_session:
            logger.warning("No active test session to teardown")
            return {"error": "No active test session"}
        
        session_id = self.current_session.session_id
        logger.info(f"Tearing down test environment: {session_id}")
        
        self.current_session.state = EnvironmentState.CLEANING_UP
        teardown_results = {
            "session_id": session_id,
            "teardown_start": datetime.now().isoformat()
        }
        
        try:
            # Execute pre-teardown hooks
            await self._execute_hooks("pre_teardown")
            
            # Perform comprehensive cleanup
            if self.current_session.data_manager:
                logger.info("Starting comprehensive test data cleanup")
                cleanup_report = await self.current_session.data_manager.cleanup_all_test_data()
                self.current_session.cleanup_report = cleanup_report
                teardown_results["cleanup_report"] = cleanup_report
            
            # Perform cleanup verification if requested
            if verify_cleanup and self.current_session.verification_system and self.current_session.data_manager:
                logger.info("Starting cleanup verification")
                verification_report = await self.current_session.verification_system.verify_cleanup(
                    self.current_session.data_manager
                )
                self.current_session.verification_report = verification_report
                
                # Convert verification report to dict for JSON serialization
                teardown_results["verification_report"] = {
                    "session_id": verification_report.session_id,
                    "total_checks": verification_report.total_checks,
                    "verified_checks": verification_report.verified_checks,
                    "failed_checks": verification_report.failed_checks,
                    "warning_checks": verification_report.warning_checks,
                    "success_rate": verification_report.success_rate,
                    "summary": verification_report.summary
                }
            
            # Execute post-teardown hooks
            await self._execute_hooks("post_teardown")
            
            self.current_session.state = EnvironmentState.COMPLETED
            self.current_session.end_time = datetime.now()
            
            teardown_results.update({
                "status": "completed",
                "teardown_end": self.current_session.end_time.isoformat(),
                "duration_seconds": (self.current_session.end_time - self.current_session.start_time).total_seconds(),
                "accounts_cleaned": len(self.current_session.accounts),
                "symbols_used": len(self.current_session.test_symbols),
                "symbols_validated": len(self.current_session.validated_symbols)
            })
            
            logger.info(f"Test environment teardown completed: {session_id}")
            
        except Exception as e:
            self.current_session.state = EnvironmentState.FAILED
            self.current_session.error = str(e)
            teardown_results.update({
                "status": "failed",
                "error": str(e),
                "teardown_end": datetime.now().isoformat()
            })
            logger.error(f"Test environment teardown failed: {e}")
        
        return teardown_results
    
    def get_environment_summary(self) -> Dict[str, Any]:
        """
        Get summary of the current test environment.
        
        Returns:
            Environment summary
        """
        if not self.current_session:
            return {"error": "No active test session"}
        
        return {
            "session_id": self.current_session.session_id,
            "environment_type": self.current_session.environment_type.value,
            "state": self.current_session.state.value,
            "start_time": self.current_session.start_time.isoformat(),
            "end_time": self.current_session.end_time.isoformat() if self.current_session.end_time else None,
            "duration_seconds": (
                (self.current_session.end_time or datetime.now()) - self.current_session.start_time
            ).total_seconds(),
            "accounts": [
                {
                    "account_id": acc.credentials.account_id,
                    "name": acc.name,
                    "tier": acc.tier,
                    "enabled": acc.enabled
                } for acc in self.current_session.accounts
            ],
            "test_symbols": self.current_session.test_symbols,
            "validated_symbols": list(self.current_session.validated_symbols),
            "validation_success_rate": (
                len(self.current_session.validated_symbols) / len(self.current_session.test_symbols) * 100
                if self.current_session.test_symbols else 0
            ),
            "data_manager_active": self.current_session.data_manager is not None,
            "verification_system_active": self.current_session.verification_system is not None,
            "error": self.current_session.error
        }
    
    def export_environment_report(self, file_path: Optional[str] = None) -> str:
        """
        Export comprehensive environment report.
        
        Args:
            file_path: Optional file path
            
        Returns:
            File path where report was saved
        """
        if not self.current_session:
            raise RuntimeError("No active test session to export")
        
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"test_environment_{self.current_session.session_id}_{timestamp}.json"
        
        report_data = {
            "environment_summary": self.get_environment_summary(),
            "cleanup_report": self.current_session.cleanup_report,
            "verification_report": (
                {
                    "session_id": self.current_session.verification_report.session_id,
                    "total_checks": self.current_session.verification_report.total_checks,
                    "verified_checks": self.current_session.verification_report.verified_checks,
                    "failed_checks": self.current_session.verification_report.failed_checks,
                    "warning_checks": self.current_session.verification_report.warning_checks,
                    "success_rate": self.current_session.verification_report.success_rate,
                    "summary": self.current_session.verification_report.summary
                } if self.current_session.verification_report else None
            ),
            "data_manager_summary": (
                self.current_session.data_manager.get_test_session_summary()
                if self.current_session.data_manager else None
            )
        }
        
        import json
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"Exported environment report to: {file_path}")
        return file_path


# Context manager for easy test environment management
class ManagedTestEnvironment:
    """Context manager for automated test environment setup and teardown."""
    
    def __init__(self, config: RealAPITestConfig, environment_type: TestEnvironmentType,
                 custom_accounts: Optional[List[TestAccount]] = None,
                 custom_symbols: Optional[List[str]] = None,
                 symbol_validation: SymbolValidationType = SymbolValidationType.BASIC,
                 verify_cleanup: bool = True):
        """
        Initialize managed test environment.
        
        Args:
            config: RealAPITestConfig instance
            environment_type: Type of test environment
            custom_accounts: Optional custom accounts
            custom_symbols: Optional custom symbols
            symbol_validation: Type of symbol validation
            verify_cleanup: Whether to verify cleanup on exit
        """
        self.manager = TestEnvironmentManager(config)
        self.environment_type = environment_type
        self.custom_accounts = custom_accounts
        self.custom_symbols = custom_symbols
        self.symbol_validation = symbol_validation
        self.verify_cleanup = verify_cleanup
        self.session: Optional[TestEnvironmentSession] = None
    
    async def __aenter__(self) -> TestEnvironmentSession:
        """Setup test environment on enter."""
        self.session = await self.manager.setup_test_environment(
            self.environment_type,
            self.custom_accounts,
            self.custom_symbols,
            self.symbol_validation
        )
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Teardown test environment on exit."""
        if self.session:
            await self.manager.teardown_test_environment(self.verify_cleanup)
    
    def get_manager(self) -> TestEnvironmentManager:
        """Get the environment manager instance."""
        return self.manager