"""RealAPITestClient wrapper for Alpaca API testing with test data isolation."""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from app.alpaca_client import AlpacaClient
from tests.config import TestCredentials, TestAccount

logger = logging.getLogger(__name__)


@dataclass
class TestOrderInfo:
    """Information about test orders for cleanup tracking."""
    order_id: str
    symbol: str
    qty: float
    side: str
    order_type: str
    account_id: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestPositionInfo:
    """Information about test positions for cleanup tracking."""
    symbol: str
    qty: float
    side: str
    account_id: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CleanupMetrics:
    """Metrics for cleanup operations."""
    total_orders: int = 0
    cancelled_orders: int = 0
    failed_cancellations: int = 0
    total_positions: int = 0
    closed_positions: int = 0
    failed_closures: int = 0
    api_calls_made: int = 0
    rate_limit_delays: int = 0
    total_cleanup_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class RealAPITestClient:
    """
    Wrapper for AlpacaClient that provides test-specific functionality including:
    - Test data isolation and cleanup
    - Order and position tracking
    - Enhanced error handling for tests
    - Connection validation
    """
    
    def __init__(self, test_account: TestAccount, test_prefix: str = "TEST"):
        """
        Initialize RealAPITestClient.
        
        Args:
            test_account: TestAccount configuration
            test_prefix: Prefix for test identification
        """
        self.test_account = test_account
        self.test_prefix = test_prefix
        self.account_id = test_account.credentials.account_id
        
        # Initialize the underlying Alpaca client
        self.client = AlpacaClient(
            api_key=test_account.credentials.api_key,
            secret_key=test_account.credentials.secret_key,
            paper_trading=test_account.credentials.paper_trading
        )
        
        # Track test resources for cleanup
        self.test_orders: List[TestOrderInfo] = []
        self.test_positions: List[TestPositionInfo] = []
        self.test_symbols: Set[str] = set()
        self.cleanup_handlers: List[callable] = []
        
        # Connection state
        self._connection_verified = False
        self._last_connection_check = None
        
        # Rate limiting and metrics
        self._rate_limiter = self._create_rate_limiter()
        self.cleanup_metrics = CleanupMetrics()
        self._api_call_history = defaultdict(list)
        
        # Enhanced error tracking
        self._error_history: List[Dict[str, Any]] = []
        self._cleanup_attempts: int = 0
        
        logger.info(f"Initialized RealAPITestClient for account {self.account_id}")
    
    def _create_rate_limiter(self) -> Dict[str, Any]:
        """Create rate limiter configuration."""
        return {
            'last_request_time': 0.0,
            'requests_per_minute': 100,  # Alpaca API rate limit
            'min_interval': 0.6,  # Minimum interval between requests (seconds)
            'burst_limit': 10,  # Allow burst of requests
            'burst_window': 60.0  # Reset burst count every minute
        }
    
    async def _apply_rate_limiting(self) -> None:
        """Apply rate limiting to prevent API overload."""
        current_time = time.time()
        time_since_last = current_time - self._rate_limiter['last_request_time']
        
        if time_since_last < self._rate_limiter['min_interval']:
            delay = self._rate_limiter['min_interval'] - time_since_last
            await asyncio.sleep(delay)
            self.cleanup_metrics.rate_limit_delays += 1
        
        self._rate_limiter['last_request_time'] = time.time()
        self.cleanup_metrics.api_calls_made += 1
    
    def _record_api_call(self, method: str, result: Dict[str, Any]) -> None:
        """Record API call for analysis."""
        self._api_call_history[method].append({
            'timestamp': datetime.now(),
            'success': 'error' not in result,
            'result': result
        })
    
    def _record_error(self, operation: str, error: Exception, context: Dict[str, Any] = None) -> None:
        """Record error for analysis and reporting."""
        error_record = {
            'timestamp': datetime.now(),
            'operation': operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'account_id': self.account_id
        }
        self._error_history.append(error_record)
        self.cleanup_metrics.errors.append(f"{operation}: {str(error)}")
        
        logger.error(f"Error in {operation} for account {self.account_id}: {error}")

    async def verify_connection(self) -> Dict[str, Any]:
        """
        Verify connection to Alpaca API and cache result.
        
        Returns:
            Dict containing connection status and account info
        """
        try:
            result = await self.client.test_connection()
            
            if result.get("status") == "connected":
                self._connection_verified = True
                self._last_connection_check = datetime.now()
                logger.info(f"Connection verified for account {self.account_id}")
            else:
                self._connection_verified = False
                logger.error(f"Connection failed for account {self.account_id}: {result}")
            
            return result
            
        except Exception as e:
            self._connection_verified = False
            logger.error(f"Connection verification failed for account {self.account_id}: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "account_id": self.account_id
            }
    
    def _ensure_connection(self) -> None:
        """Ensure connection is verified before API calls."""
        if not self._connection_verified:
            raise RuntimeError(
                f"Connection not verified for account {self.account_id}. "
                "Call verify_connection() first."
            )
        
        # Re-verify if connection check is old
        if (self._last_connection_check and 
            datetime.now() - self._last_connection_check > timedelta(minutes=30)):
            logger.warning(f"Connection check is stale for account {self.account_id}")
    
    def register_test_symbol(self, symbol: str) -> None:
        """Register a symbol as being used in tests for cleanup tracking."""
        self.test_symbols.add(symbol)
        logger.debug(f"Registered test symbol: {symbol}")
    
    def register_cleanup_handler(self, handler: callable) -> None:
        """Register a custom cleanup handler."""
        self.cleanup_handlers.append(handler)
        logger.debug(f"Registered cleanup handler: {handler.__name__}")
    
    # Stock API Methods with test tracking
    async def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """Get stock quote with test symbol tracking."""
        self._ensure_connection()
        self.register_test_symbol(symbol)
        
        try:
            result = await self.client.get_stock_quote(symbol)
            logger.debug(f"Retrieved stock quote for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to get stock quote for {symbol}: {e}")
            raise
    
    async def get_multiple_stock_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get multiple stock quotes with test symbol tracking."""
        self._ensure_connection()
        
        for symbol in symbols:
            self.register_test_symbol(symbol)
        
        try:
            result = await self.client.get_multiple_stock_quotes(symbols)
            logger.debug(f"Retrieved quotes for {len(symbols)} symbols")
            return result
        except Exception as e:
            logger.error(f"Failed to get multiple stock quotes: {e}")
            raise
    
    async def get_stock_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100) -> Dict[str, Any]:
        """Get stock bars with test symbol tracking."""
        self._ensure_connection()
        self.register_test_symbol(symbol)
        
        try:
            result = await self.client.get_stock_bars(symbol, timeframe, limit)
            logger.debug(f"Retrieved stock bars for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to get stock bars for {symbol}: {e}")
            raise
    
    # Options API Methods with test tracking
    async def get_options_chain(self, underlying_symbol: str, expiration_date: Optional[str] = None) -> Dict[str, Any]:
        """Get options chain with test symbol tracking."""
        self._ensure_connection()
        self.register_test_symbol(underlying_symbol)
        
        try:
            result = await self.client.get_options_chain(underlying_symbol, expiration_date)
            logger.debug(f"Retrieved options chain for {underlying_symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to get options chain for {underlying_symbol}: {e}")
            raise
    
    async def get_option_quote(self, option_symbol: str) -> Dict[str, Any]:
        """Get option quote with test symbol tracking."""
        self._ensure_connection()
        self.register_test_symbol(option_symbol)
        
        try:
            result = await self.client.get_option_quote(option_symbol)
            logger.debug(f"Retrieved option quote for {option_symbol}")
            return result
        except Exception as e:
            logger.error(f"Failed to get option quote for {option_symbol}: {e}")
            raise
    
    async def get_multiple_option_quotes(self, option_symbols: List[str]) -> Dict[str, Any]:
        """Get multiple option quotes with test symbol tracking."""
        self._ensure_connection()
        
        for symbol in option_symbols:
            self.register_test_symbol(symbol)
        
        try:
            result = await self.client.get_multiple_option_quotes(option_symbols)
            logger.debug(f"Retrieved quotes for {len(option_symbols)} option symbols")
            return result
        except Exception as e:
            logger.error(f"Failed to get multiple option quotes: {e}")
            raise
    
    # Trading Methods with test order tracking
    async def place_test_order(self, symbol: str, qty: float, side: str, order_type: str = "market",
                              limit_price: Optional[float] = None, stop_price: Optional[float] = None,
                              time_in_force: str = "day") -> Dict[str, Any]:
        """
        Place a test order with automatic tracking for cleanup.
        
        Args:
            symbol: Stock symbol
            qty: Quantity
            side: "buy" or "sell"
            order_type: "market", "limit", or "stop"
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: "day" or "gtc"
        
        Returns:
            Dict containing order information
        """
        self._ensure_connection()
        self.register_test_symbol(symbol)
        
        try:
            result = await self.client.place_stock_order(
                symbol, qty, side, order_type, limit_price, stop_price, time_in_force
            )
            
            if "error" not in result and "id" in result:
                # Track the test order for cleanup
                test_order = TestOrderInfo(
                    order_id=result["id"],
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type,
                    account_id=self.account_id
                )
                self.test_orders.append(test_order)
                
                logger.info(f"Placed test order {result['id']} for {symbol}")
            else:
                logger.error(f"Failed to place test order for {symbol}: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to place test order for {symbol}: {e}")
            raise
    
    async def place_test_option_order(self, option_symbol: str, qty: int, side: str, order_type: str = "market",
                                     limit_price: Optional[float] = None, time_in_force: str = "day") -> Dict[str, Any]:
        """Place a test option order with automatic tracking for cleanup."""
        self._ensure_connection()
        self.register_test_symbol(option_symbol)
        
        try:
            result = await self.client.place_option_order(
                option_symbol, qty, side, order_type, limit_price, time_in_force
            )
            
            if "error" not in result and "id" in result:
                # Track the test order for cleanup
                test_order = TestOrderInfo(
                    order_id=result["id"],
                    symbol=option_symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type,
                    account_id=self.account_id
                )
                self.test_orders.append(test_order)
                
                logger.info(f"Placed test option order {result['id']} for {option_symbol}")
            else:
                logger.error(f"Failed to place test option order for {option_symbol}: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to place test option order for {option_symbol}: {e}")
            raise
    
    # Account and Position Methods
    async def get_account(self) -> Dict[str, Any]:
        """Get account information."""
        self._ensure_connection()
        
        try:
            result = await self.client.get_account()
            logger.debug(f"Retrieved account info for {self.account_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions and track them for cleanup."""
        self._ensure_connection()
        
        try:
            positions = await self.client.get_positions()
            
            # Track positions for cleanup
            for position in positions:
                if "error" not in position:
                    test_position = TestPositionInfo(
                        symbol=position["symbol"],
                        qty=position["qty"],
                        side=position["side"],
                        account_id=self.account_id
                    )
                    
                    # Only add if not already tracked
                    if not any(p.symbol == position["symbol"] for p in self.test_positions):
                        self.test_positions.append(test_position)
            
            logger.debug(f"Retrieved {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise
    
    async def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders."""
        self._ensure_connection()
        
        try:
            result = await self.client.get_orders(status, limit)
            logger.debug(f"Retrieved {len(result)} orders")
            return result
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        self._ensure_connection()
        
        try:
            result = await self.client.cancel_order(order_id)
            logger.info(f"Cancelled order {order_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    # Enhanced Cleanup Methods
    async def cleanup_test_orders(self, max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, Any]:
        """Clean up all test orders with enhanced error handling and rate limiting."""
        start_time = time.time()
        self._cleanup_attempts += 1
        
        cleanup_results = {
            "cancelled_orders": [],
            "failed_cancellations": [],
            "total_orders": len(self.test_orders),
            "cleanup_attempt": self._cleanup_attempts,
            "rate_limit_delays": 0,
            "api_calls": 0
        }
        
        self.cleanup_metrics.total_orders = len(self.test_orders)
        
        logger.info(f"Starting cleanup of {len(self.test_orders)} test orders (attempt {self._cleanup_attempts})")
        
        for order_info in self.test_orders.copy():
            retry_count = 0
            order_cancelled = False
            
            while retry_count <= max_retries and not order_cancelled:
                try:
                    # Apply rate limiting
                    await self._apply_rate_limiting()
                    cleanup_results["api_calls"] += 1
                    
                    result = await self.cancel_order(order_info.order_id)
                    self._record_api_call("cancel_order", result)
                    
                    if "error" not in result:
                        cleanup_results["cancelled_orders"].append(order_info.order_id)
                        self.test_orders.remove(order_info)
                        self.cleanup_metrics.cancelled_orders += 1
                        order_cancelled = True
                        logger.debug(f"Cancelled test order {order_info.order_id}")
                    else:
                        # Check if this is a retryable error
                        error_msg = result.get("error", "Unknown error")
                        if retry_count < max_retries and self._is_retryable_error(error_msg):
                            retry_count += 1
                            logger.warning(f"Retryable error cancelling order {order_info.order_id}, "
                                         f"retry {retry_count}/{max_retries}: {error_msg}")
                            await asyncio.sleep(retry_delay * retry_count)
                        else:
                            cleanup_results["failed_cancellations"].append({
                                "order_id": order_info.order_id,
                                "error": error_msg,
                                "retry_count": retry_count
                            })
                            self.cleanup_metrics.failed_cancellations += 1
                            break
                    
                except Exception as e:
                    self._record_error("cleanup_test_orders", e, {"order_id": order_info.order_id})
                    
                    if retry_count < max_retries and self._is_retryable_exception(e):
                        retry_count += 1
                        logger.warning(f"Exception cancelling order {order_info.order_id}, "
                                     f"retry {retry_count}/{max_retries}: {e}")
                        await asyncio.sleep(retry_delay * retry_count)
                    else:
                        cleanup_results["failed_cancellations"].append({
                            "order_id": order_info.order_id,
                            "error": str(e),
                            "retry_count": retry_count
                        })
                        self.cleanup_metrics.failed_cancellations += 1
                        break
        
        cleanup_results["rate_limit_delays"] = self.cleanup_metrics.rate_limit_delays
        self.cleanup_metrics.total_cleanup_time += time.time() - start_time
        
        logger.info(f"Order cleanup completed: {len(cleanup_results['cancelled_orders'])} cancelled, "
                   f"{len(cleanup_results['failed_cancellations'])} failed, "
                   f"{cleanup_results['api_calls']} API calls made")
        
        return cleanup_results
    
    def _is_retryable_error(self, error_msg: str) -> bool:
        """Check if an error message indicates a retryable condition."""
        retryable_errors = [
            "rate limit",
            "timeout",
            "temporary",
            "unavailable",
            "connection",
            "network",
            "gateway"
        ]
        error_lower = error_msg.lower()
        return any(retryable in error_lower for retryable in retryable_errors)
    
    def _is_retryable_exception(self, exception: Exception) -> bool:
        """Check if an exception indicates a retryable condition."""
        retryable_types = [
            asyncio.TimeoutError,
            ConnectionError,
            OSError
        ]
        return any(isinstance(exception, exc_type) for exc_type in retryable_types)

    async def cleanup_test_positions(self, max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, Any]:
        """Clean up test positions by closing them."""
        cleanup_results = {
            "closed_positions": [],
            "failed_closures": [],
            "total_positions": len(self.test_positions)
        }
        
        logger.info(f"Starting cleanup of {len(self.test_positions)} test positions")
        
        for position_info in self.test_positions.copy():
            try:
                # Close position by placing opposite order
                opposite_side = "sell" if position_info.side == "long" else "buy"
                
                result = await self.place_test_order(
                    symbol=position_info.symbol,
                    qty=abs(position_info.qty),
                    side=opposite_side,
                    order_type="market"
                )
                
                if "error" not in result:
                    cleanup_results["closed_positions"].append(position_info.symbol)
                    self.test_positions.remove(position_info)
                    logger.debug(f"Closed test position for {position_info.symbol}")
                else:
                    cleanup_results["failed_closures"].append({
                        "symbol": position_info.symbol,
                        "error": result.get("error", "Unknown error")
                    })
                    logger.warning(f"Failed to close test position for {position_info.symbol}: {result}")
                
            except Exception as e:
                cleanup_results["failed_closures"].append({
                    "symbol": position_info.symbol,
                    "error": str(e)
                })
                logger.error(f"Exception closing test position for {position_info.symbol}: {e}")
        
        logger.info(f"Position cleanup completed: {len(cleanup_results['closed_positions'])} closed, "
                   f"{len(cleanup_results['failed_closures'])} failed")
        
        return cleanup_results
    
    async def cleanup_all_test_data(self) -> Dict[str, Any]:
        """Clean up all test data including orders, positions, and custom handlers."""
        logger.info(f"Starting comprehensive test data cleanup for account {self.account_id}")
        
        cleanup_results = {
            "account_id": self.account_id,
            "orders": {},
            "positions": {},
            "custom_handlers": {"executed": 0, "failed": 0},
            "test_symbols": list(self.test_symbols)
        }
        
        # Execute custom cleanup handlers first
        for handler in self.cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                cleanup_results["custom_handlers"]["executed"] += 1
                logger.debug(f"Executed cleanup handler: {handler.__name__}")
            except Exception as e:
                cleanup_results["custom_handlers"]["failed"] += 1
                logger.error(f"Failed to execute cleanup handler {handler.__name__}: {e}")
        
        # Clean up orders
        try:
            cleanup_results["orders"] = await self.cleanup_test_orders()
        except Exception as e:
            logger.error(f"Failed to cleanup test orders: {e}")
            cleanup_results["orders"] = {"error": str(e)}
        
        # Clean up positions
        try:
            cleanup_results["positions"] = await self.cleanup_test_positions()
        except Exception as e:
            logger.error(f"Failed to cleanup test positions: {e}")
            cleanup_results["positions"] = {"error": str(e)}
        
        # Clear tracking data
        self.test_symbols.clear()
        self.cleanup_handlers.clear()
        
        logger.info(f"Comprehensive test data cleanup completed for account {self.account_id}")
        return cleanup_results
    
    def get_cleanup_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive cleanup metrics.
        
        Returns:
            Dictionary containing cleanup metrics
        """
        return {
            "total_orders": self.cleanup_metrics.total_orders,
            "cancelled_orders": self.cleanup_metrics.cancelled_orders,
            "failed_cancellations": self.cleanup_metrics.failed_cancellations,
            "order_cleanup_success_rate": (
                self.cleanup_metrics.cancelled_orders / self.cleanup_metrics.total_orders * 100
                if self.cleanup_metrics.total_orders > 0 else 0.0
            ),
            "total_positions": self.cleanup_metrics.total_positions,
            "closed_positions": self.cleanup_metrics.closed_positions,
            "failed_closures": self.cleanup_metrics.failed_closures,
            "position_cleanup_success_rate": (
                self.cleanup_metrics.closed_positions / self.cleanup_metrics.total_positions * 100
                if self.cleanup_metrics.total_positions > 0 else 0.0
            ),
            "api_calls_made": self.cleanup_metrics.api_calls_made,
            "rate_limit_delays": self.cleanup_metrics.rate_limit_delays,
            "total_cleanup_time": self.cleanup_metrics.total_cleanup_time,
            "cleanup_attempts": self._cleanup_attempts,
            "errors": self.cleanup_metrics.errors,
            "error_count": len(self.cleanup_metrics.errors)
        }
    
    def get_error_analysis(self) -> Dict[str, Any]:
        """
        Get analysis of errors encountered during testing.
        
        Returns:
            Dictionary containing error analysis
        """
        if not self._error_history:
            return {"total_errors": 0, "error_types": {}, "operations_affected": {}}
        
        error_types = defaultdict(int)
        operations_affected = defaultdict(int)
        recent_errors = []
        
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        for error in self._error_history:
            error_types[error['error_type']] += 1
            operations_affected[error['operation']] += 1
            
            if error['timestamp'] >= cutoff_time:
                recent_errors.append(error)
        
        return {
            "total_errors": len(self._error_history),
            "error_types": dict(error_types),
            "operations_affected": dict(operations_affected),
            "recent_errors_count": len(recent_errors),
            "recent_errors": recent_errors[-5:],  # Last 5 recent errors
            "most_common_error": max(error_types.items(), key=lambda x: x[1])[0] if error_types else None,
            "most_affected_operation": max(operations_affected.items(), key=lambda x: x[1])[0] if operations_affected else None
        }
    
    def get_api_performance_stats(self) -> Dict[str, Any]:
        """
        Get API performance statistics.
        
        Returns:
            Dictionary containing API performance stats
        """
        stats = {
            "total_api_calls": sum(len(calls) for calls in self._api_call_history.values()),
            "calls_by_method": {method: len(calls) for method, calls in self._api_call_history.items()},
            "success_rates": {},
            "average_response_times": {}
        }
        
        for method, calls in self._api_call_history.items():
            if calls:
                successful_calls = sum(1 for call in calls if call['success'])
                stats["success_rates"][method] = successful_calls / len(calls) * 100
        
        return stats

    def get_test_summary(self) -> Dict[str, Any]:
        """Get summary of test activity."""
        return {
            "account_id": self.account_id,
            "test_prefix": self.test_prefix,
            "connection_verified": self._connection_verified,
            "last_connection_check": self._last_connection_check,
            "tracked_orders": len(self.test_orders),
            "tracked_positions": len(self.test_positions),
            "test_symbols": list(self.test_symbols),
            "cleanup_handlers": len(self.cleanup_handlers)
        }