"""Comprehensive test data management and cleanup system for Alpaca API testing."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

from .real_api_client import RealAPITestClient, TestOrderInfo, TestPositionInfo
from tests.config import TestAccount, TestCredentials, TestEnvironmentType


logger = logging.getLogger(__name__)


class TestDataType(Enum):
    """Types of test data that can be managed."""
    ORDER = "order"
    POSITION = "position"
    SYMBOL = "symbol"
    ACCOUNT = "account"
    CONNECTION = "connection"
    CUSTOM = "custom"


class CleanupStatus(Enum):
    """Status of cleanup operations."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    IN_PROGRESS = "in_progress"


@dataclass
class TestSession:
    """Information about a test session."""
    session_id: str
    start_time: datetime
    test_prefix: str
    environment_type: TestEnvironmentType
    accounts_used: Set[str] = field(default_factory=set)
    test_data: Dict[str, List[Any]] = field(default_factory=lambda: defaultdict(list))
    cleanup_results: Dict[str, Any] = field(default_factory=dict)
    end_time: Optional[datetime] = None
    success: bool = False


@dataclass
class CleanupTask:
    """Represents a cleanup task to be executed."""
    task_id: str
    data_type: TestDataType
    account_id: str
    target: Any  # Order ID, symbol, etc.
    cleanup_function: callable
    priority: int = 0  # Higher number = higher priority
    max_retries: int = 3
    retry_delay: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    task_id: str
    status: CleanupStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    retry_count: int = 0
    error: Optional[Exception] = None


class TestDataManager:
    """
    Centralized test data management system with comprehensive cleanup and verification.
    
    This class provides:
    - Test data isolation between different test runs
    - Account-specific resource tracking
    - Automated cleanup with retry logic
    - Comprehensive reporting and verification
    - Rate limiting during cleanup operations
    """
    
    def __init__(self, test_prefix: str = None):
        """
        Initialize TestDataManager.
        
        Args:
            test_prefix: Prefix for test identification
        """
        self.test_prefix = test_prefix or f"TEST_{uuid.uuid4().hex[:8]}"
        self.current_session: Optional[TestSession] = None
        self.active_clients: Dict[str, RealAPITestClient] = {}
        self.cleanup_queue: List[CleanupTask] = []
        self.cleanup_results: List[CleanupResult] = []
        self.rate_limiter = self._create_rate_limiter()
        
        logger.info(f"Initialized TestDataManager with prefix: {self.test_prefix}")
    
    def _create_rate_limiter(self):
        """Create rate limiter for cleanup operations."""
        return {
            'last_request': datetime.now(),
            'requests_per_minute': 100,  # Alpaca API rate limit
            'min_interval': 0.6  # Minimum interval between requests
        }
    
    async def _rate_limit(self):
        """Apply rate limiting to prevent API overload."""
        current_time = datetime.now()
        time_diff = (current_time - self.rate_limiter['last_request']).total_seconds()
        
        if time_diff < self.rate_limiter['min_interval']:
            sleep_time = self.rate_limiter['min_interval'] - time_diff
            await asyncio.sleep(sleep_time)
        
        self.rate_limiter['last_request'] = datetime.now()
    
    def start_test_session(self, environment_type: TestEnvironmentType = TestEnvironmentType.UNIT) -> str:
        """
        Start a new test session.
        
        Args:
            environment_type: Type of test environment
            
        Returns:
            Session ID
        """
        session_id = f"{self.test_prefix}_{uuid.uuid4().hex[:8]}"
        
        self.current_session = TestSession(
            session_id=session_id,
            start_time=datetime.now(),
            test_prefix=self.test_prefix,
            environment_type=environment_type
        )
        
        logger.info(f"Started test session: {session_id}")
        return session_id
    
    async def register_test_client(self, account: TestAccount) -> RealAPITestClient:
        """
        Register a test client for tracking and cleanup.
        
        Args:
            account: Test account configuration
            
        Returns:
            RealAPITestClient instance
        """
        if not self.current_session:
            raise RuntimeError("No active test session. Call start_test_session() first.")
        
        account_id = account.credentials.account_id
        
        if account_id not in self.active_clients:
            client = RealAPITestClient(account, self.test_prefix)
            
            # Verify connection
            connection_result = await client.verify_connection()
            if connection_result.get("status") != "connected":
                raise RuntimeError(f"Failed to connect to Alpaca API for account {account_id}")
            
            self.active_clients[account_id] = client
            self.current_session.accounts_used.add(account_id)
            
            logger.info(f"Registered test client for account: {account_id}")
        
        return self.active_clients[account_id]
    
    def register_test_data(self, data_type: TestDataType, account_id: str, data: Any) -> None:
        """
        Register test data for tracking and cleanup.
        
        Args:
            data_type: Type of test data
            account_id: Account ID the data belongs to
            data: The test data to track
        """
        if not self.current_session:
            raise RuntimeError("No active test session. Call start_test_session() first.")
        
        self.current_session.test_data[f"{account_id}_{data_type.value}"].append({
            "data": data,
            "timestamp": datetime.now(),
            "type": data_type
        })
        
        logger.debug(f"Registered test data: {data_type.value} for account {account_id}")
    
    def create_cleanup_task(self, data_type: TestDataType, account_id: str, target: Any,
                          cleanup_function: callable, priority: int = 0) -> str:
        """
        Create a cleanup task.
        
        Args:
            data_type: Type of data to clean up
            account_id: Account ID
            target: Target to clean up (order ID, symbol, etc.)
            cleanup_function: Function to call for cleanup
            priority: Task priority (higher = more important)
            
        Returns:
            Task ID
        """
        task_id = f"{self.test_prefix}_cleanup_{uuid.uuid4().hex[:8]}"
        
        task = CleanupTask(
            task_id=task_id,
            data_type=data_type,
            account_id=account_id,
            target=target,
            cleanup_function=cleanup_function,
            priority=priority
        )
        
        self.cleanup_queue.append(task)
        logger.debug(f"Created cleanup task: {task_id}")
        
        return task_id
    
    async def _execute_cleanup_task(self, task: CleanupTask) -> CleanupResult:
        """
        Execute a single cleanup task with retry logic.
        
        Args:
            task: Cleanup task to execute
            
        Returns:
            CleanupResult
        """
        start_time = datetime.now()
        result = CleanupResult(
            task_id=task.task_id,
            status=CleanupStatus.IN_PROGRESS,
            message=f"Executing cleanup for {task.data_type.value}",
        )
        
        for attempt in range(task.max_retries + 1):
            try:
                # Apply rate limiting
                await self._rate_limit()
                
                # Execute cleanup function
                if asyncio.iscoroutinefunction(task.cleanup_function):
                    cleanup_result = await task.cleanup_function(task.target)
                else:
                    cleanup_result = task.cleanup_function(task.target)
                
                result.status = CleanupStatus.SUCCESS
                result.message = f"Successfully cleaned up {task.data_type.value}"
                result.details = cleanup_result if isinstance(cleanup_result, dict) else {}
                break
                
            except Exception as e:
                result.error = e
                result.retry_count = attempt
                
                if attempt < task.max_retries:
                    logger.warning(f"Cleanup task {task.task_id} failed, retrying ({attempt + 1}/{task.max_retries}): {e}")
                    await asyncio.sleep(task.retry_delay * (attempt + 1))
                else:
                    result.status = CleanupStatus.FAILED
                    result.message = f"Failed to clean up {task.data_type.value} after {task.max_retries} retries"
                    logger.error(f"Cleanup task {task.task_id} failed permanently: {e}")
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result
    
    async def cleanup_account_data(self, account_id: str) -> Dict[str, Any]:
        """
        Clean up all data for a specific account.
        
        Args:
            account_id: Account ID to clean up
            
        Returns:
            Cleanup results
        """
        if account_id not in self.active_clients:
            logger.warning(f"No client found for account {account_id}")
            return {"error": f"No client found for account {account_id}"}
        
        client = self.active_clients[account_id]
        
        logger.info(f"Starting cleanup for account: {account_id}")
        
        # Create cleanup tasks for this account
        account_tasks = [
            task for task in self.cleanup_queue
            if task.account_id == account_id
        ]
        
        # Add automatic cleanup tasks for client data
        if client.test_orders:
            for order_info in client.test_orders:
                self.create_cleanup_task(
                    TestDataType.ORDER,
                    account_id,
                    order_info.order_id,
                    client.cancel_order,
                    priority=10  # High priority for orders
                )
        
        if client.test_positions:
            for position_info in client.test_positions:
                self.create_cleanup_task(
                    TestDataType.POSITION,
                    account_id,
                    position_info,
                    lambda pos: self._cleanup_position(client, pos),
                    priority=5  # Medium priority for positions
                )
        
        # Execute cleanup tasks for this account
        cleanup_results = []
        account_tasks = [task for task in self.cleanup_queue if task.account_id == account_id]
        
        # Sort tasks by priority
        account_tasks.sort(key=lambda x: x.priority, reverse=True)
        
        for task in account_tasks:
            result = await self._execute_cleanup_task(task)
            cleanup_results.append(result)
            self.cleanup_results.append(result)
        
        # Remove completed tasks from queue
        self.cleanup_queue = [
            task for task in self.cleanup_queue
            if task.account_id != account_id
        ]
        
        # Execute client's comprehensive cleanup
        try:
            client_cleanup = await client.cleanup_all_test_data()
        except Exception as e:
            logger.error(f"Error in client cleanup for {account_id}: {e}")
            client_cleanup = {"error": str(e)}
        
        return {
            "account_id": account_id,
            "task_results": [
                {
                    "task_id": r.task_id,
                    "status": r.status.value,
                    "message": r.message,
                    "execution_time": r.execution_time,
                    "retry_count": r.retry_count
                }
                for r in cleanup_results
            ],
            "client_cleanup": client_cleanup,
            "total_tasks": len(cleanup_results),
            "successful_tasks": len([r for r in cleanup_results if r.status == CleanupStatus.SUCCESS]),
            "failed_tasks": len([r for r in cleanup_results if r.status == CleanupStatus.FAILED])
        }
    
    async def _cleanup_position(self, client: RealAPITestClient, position_info: TestPositionInfo) -> Dict[str, Any]:
        """Clean up a position by placing an opposite order."""
        try:
            opposite_side = "sell" if position_info.side == "long" else "buy"
            
            result = await client.place_test_order(
                symbol=position_info.symbol,
                qty=abs(position_info.qty),
                side=opposite_side,
                order_type="market"
            )
            
            return {"position_closed": position_info.symbol, "order_result": result}
            
        except Exception as e:
            return {"error": f"Failed to close position {position_info.symbol}: {e}"}
    
    async def cleanup_all_test_data(self) -> Dict[str, Any]:
        """
        Clean up all test data from all accounts.
        
        Returns:
            Comprehensive cleanup results
        """
        if not self.current_session:
            logger.warning("No active test session for cleanup")
            return {"error": "No active test session"}
        
        logger.info(f"Starting comprehensive cleanup for session: {self.current_session.session_id}")
        
        cleanup_results = {
            "session_id": self.current_session.session_id,
            "start_time": self.current_session.start_time.isoformat(),
            "cleanup_start": datetime.now().isoformat(),
            "accounts": {},
            "summary": {}
        }
        
        # Clean up each account
        for account_id in self.active_clients:
            try:
                account_cleanup = await self.cleanup_account_data(account_id)
                cleanup_results["accounts"][account_id] = account_cleanup
                
            except Exception as e:
                logger.error(f"Error cleaning up account {account_id}: {e}")
                cleanup_results["accounts"][account_id] = {
                    "error": str(e),
                    "account_id": account_id
                }
        
        # Update session
        self.current_session.end_time = datetime.now()
        self.current_session.cleanup_results = cleanup_results
        self.current_session.success = all(
            "error" not in result for result in cleanup_results["accounts"].values()
        )
        
        # Generate summary
        total_tasks = sum(
            result.get("total_tasks", 0) for result in cleanup_results["accounts"].values()
            if isinstance(result, dict) and "total_tasks" in result
        )
        
        successful_tasks = sum(
            result.get("successful_tasks", 0) for result in cleanup_results["accounts"].values()
            if isinstance(result, dict) and "successful_tasks" in result
        )
        
        failed_tasks = sum(
            result.get("failed_tasks", 0) for result in cleanup_results["accounts"].values()
            if isinstance(result, dict) and "failed_tasks" in result
        )
        
        cleanup_results["summary"] = {
            "total_accounts": len(self.active_clients),
            "successful_accounts": len([
                r for r in cleanup_results["accounts"].values()
                if isinstance(r, dict) and "error" not in r
            ]),
            "failed_accounts": len([
                r for r in cleanup_results["accounts"].values()
                if isinstance(r, dict) and "error" in r
            ]),
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": (successful_tasks / total_tasks * 100) if total_tasks > 0 else 100.0,
            "duration_seconds": (self.current_session.end_time - self.current_session.start_time).total_seconds(),
            "cleanup_duration_seconds": (datetime.now() - datetime.fromisoformat(cleanup_results["cleanup_start"])).total_seconds()
        }
        
        # Clear active clients
        self.active_clients.clear()
        self.cleanup_queue.clear()
        
        logger.info(f"Comprehensive cleanup completed for session: {self.current_session.session_id}")
        return cleanup_results
    
    def get_test_session_summary(self) -> Dict[str, Any]:
        """
        Get summary of the current test session.
        
        Returns:
            Session summary
        """
        if not self.current_session:
            return {"error": "No active test session"}
        
        return {
            "session_id": self.current_session.session_id,
            "start_time": self.current_session.start_time.isoformat(),
            "end_time": self.current_session.end_time.isoformat() if self.current_session.end_time else None,
            "test_prefix": self.current_session.test_prefix,
            "environment_type": self.current_session.environment_type.value,
            "accounts_used": list(self.current_session.accounts_used),
            "active_clients": len(self.active_clients),
            "pending_cleanup_tasks": len(self.cleanup_queue),
            "completed_cleanup_tasks": len(self.cleanup_results),
            "test_data_count": {
                key: len(data) for key, data in self.current_session.test_data.items()
            },
            "success": self.current_session.success
        }
    
    def export_session_data(self, file_path: Optional[str] = None) -> str:
        """
        Export session data to JSON file.
        
        Args:
            file_path: Optional file path. If not provided, uses session ID.
            
        Returns:
            File path where data was saved
        """
        if not self.current_session:
            raise RuntimeError("No active test session to export")
        
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"test_session_{self.current_session.session_id}_{timestamp}.json"
        
        session_data = {
            "session": self.get_test_session_summary(),
            "cleanup_results": self.current_session.cleanup_results,
            "test_data": {
                key: [
                    {
                        "data": item["data"],
                        "timestamp": item["timestamp"].isoformat(),
                        "type": item["type"].value
                    } for item in data
                ]
                for key, data in self.current_session.test_data.items()
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(session_data, f, indent=2, default=str)
        
        logger.info(f"Exported session data to: {file_path}")
        return file_path