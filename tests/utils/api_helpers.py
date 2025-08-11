"""API testing helper utilities for enhanced test functionality."""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class APICallResult:
    """Result of an API call with timing and metadata."""
    success: bool
    response_data: Any
    response_time_ms: float
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class PerformanceMetrics:
    """Performance metrics for API testing."""
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    error_rate: float
    calls_per_second: float
    start_time: datetime
    end_time: datetime


class APITestHelper:
    """Helper utilities for API testing with timing and error handling."""
    
    def __init__(self):
        self.call_history: List[APICallResult] = []
        self.performance_metrics: Optional[PerformanceMetrics] = None
    
    async def timed_api_call(self, api_func: Callable, *args, **kwargs) -> APICallResult:
        """
        Execute an API call with timing measurement.
        
        Args:
            api_func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            APICallResult with timing and response data
        """
        start_time = time.perf_counter()
        
        try:
            response_data = await api_func(*args, **kwargs)
            end_time = time.perf_counter()
            
            response_time_ms = (end_time - start_time) * 1000
            
            # Check if response indicates an error
            success = True
            error_message = None
            
            if isinstance(response_data, dict) and "error" in response_data:
                success = False
                error_message = response_data["error"]
            
            result = APICallResult(
                success=success,
                response_data=response_data,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
            
            self.call_history.append(result)
            logger.debug(f"API call completed in {response_time_ms:.2f}ms, success: {success}")
            
            return result
            
        except Exception as e:
            end_time = time.perf_counter()
            response_time_ms = (end_time - start_time) * 1000
            
            result = APICallResult(
                success=False,
                response_data=None,
                response_time_ms=response_time_ms,
                error_message=str(e)
            )
            
            self.call_history.append(result)
            logger.error(f"API call failed after {response_time_ms:.2f}ms: {e}")
            
            return result
    
    async def batch_api_calls(self, api_calls: List[Tuple[Callable, tuple, dict]], 
                             max_concurrent: int = 5) -> List[APICallResult]:
        """
        Execute multiple API calls concurrently with rate limiting.
        
        Args:
            api_calls: List of (function, args, kwargs) tuples
            max_concurrent: Maximum concurrent calls
        
        Returns:
            List of APICallResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def limited_call(api_func, args, kwargs):
            async with semaphore:
                return await self.timed_api_call(api_func, *args, **kwargs)
        
        tasks = [
            limited_call(api_func, args, kwargs)
            for api_func, args, kwargs in api_calls
        ]
        
        logger.info(f"Executing {len(tasks)} API calls with max {max_concurrent} concurrent")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(APICallResult(
                    success=False,
                    response_data=None,
                    response_time_ms=0,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def stress_test_endpoint(self, api_func: Callable, args: tuple, kwargs: dict,
                                  num_calls: int, duration_seconds: Optional[int] = None,
                                  max_concurrent: int = 10) -> PerformanceMetrics:
        """
        Stress test an API endpoint with multiple concurrent calls.
        
        Args:
            api_func: API function to test
            args: Arguments for the function
            kwargs: Keyword arguments for the function
            num_calls: Number of calls to make (if duration_seconds not specified)
            duration_seconds: Duration to run test (overrides num_calls)
            max_concurrent: Maximum concurrent calls
        
        Returns:
            PerformanceMetrics object
        """
        start_time = datetime.now()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def make_call():
            async with semaphore:
                return await self.timed_api_call(api_func, *args, **kwargs)
        
        results = []
        
        if duration_seconds:
            # Time-based stress test
            logger.info(f"Starting {duration_seconds}s stress test with max {max_concurrent} concurrent calls")
            end_time = start_time + timedelta(seconds=duration_seconds)
            
            while datetime.now() < end_time:
                batch_size = min(max_concurrent, 50)  # Limit batch size
                tasks = [make_call() for _ in range(batch_size)]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        results.append(APICallResult(
                            success=False,
                            response_data=None,
                            response_time_ms=0,
                            error_message=str(result)
                        ))
                    else:
                        results.append(result)
                
                # Small delay to prevent overwhelming the API
                await asyncio.sleep(0.1)
        
        else:
            # Count-based stress test
            logger.info(f"Starting stress test with {num_calls} calls, max {max_concurrent} concurrent")
            
            # Execute calls in batches
            for i in range(0, num_calls, max_concurrent):
                batch_size = min(max_concurrent, num_calls - i)
                tasks = [make_call() for _ in range(batch_size)]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        results.append(APICallResult(
                            success=False,
                            response_data=None,
                            response_time_ms=0,
                            error_message=str(result)
                        ))
                    else:
                        results.append(result)
                
                # Progress logging
                if (i + batch_size) % 100 == 0:
                    logger.info(f"Completed {i + batch_size}/{num_calls} calls")
        
        end_time = datetime.now()
        
        # Calculate metrics
        successful_calls = sum(1 for r in results if r.success)
        failed_calls = len(results) - successful_calls
        response_times = [r.response_time_ms for r in results if r.response_time_ms > 0]
        
        total_duration = (end_time - start_time).total_seconds()
        
        metrics = PerformanceMetrics(
            total_calls=len(results),
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            average_response_time_ms=sum(response_times) / len(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            error_rate=failed_calls / len(results) if results else 0,
            calls_per_second=len(results) / total_duration if total_duration > 0 else 0,
            start_time=start_time,
            end_time=end_time
        )
        
        self.performance_metrics = metrics
        
        logger.info(f"Stress test completed: {metrics.total_calls} calls, "
                   f"{metrics.successful_calls} successful, "
                   f"{metrics.average_response_time_ms:.2f}ms avg response time, "
                   f"{metrics.calls_per_second:.2f} calls/sec")
        
        return metrics
    
    def get_call_history(self, success_only: bool = False) -> List[APICallResult]:
        """Get history of API calls."""
        if success_only:
            return [call for call in self.call_history if call.success]
        return self.call_history.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of all calls."""
        if not self.call_history:
            return {"message": "No API calls recorded"}
        
        successful_calls = [call for call in self.call_history if call.success]
        failed_calls = [call for call in self.call_history if not call.success]
        response_times = [call.response_time_ms for call in successful_calls]
        
        return {
            "total_calls": len(self.call_history),
            "successful_calls": len(successful_calls),
            "failed_calls": len(failed_calls),
            "success_rate": len(successful_calls) / len(self.call_history),
            "average_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
            "min_response_time_ms": min(response_times) if response_times else 0,
            "max_response_time_ms": max(response_times) if response_times else 0,
            "error_messages": [call.error_message for call in failed_calls if call.error_message]
        }
    
    def clear_history(self) -> None:
        """Clear call history."""
        self.call_history.clear()
        self.performance_metrics = None
        logger.debug("Cleared API call history")


class RateLimitHelper:
    """Helper for managing API rate limits during testing."""
    
    def __init__(self, calls_per_minute: int = 200):
        """
        Initialize rate limit helper.
        
        Args:
            calls_per_minute: Maximum calls per minute allowed
        """
        self.calls_per_minute = calls_per_minute
        self.call_timestamps: List[datetime] = []
        self.min_interval = 60.0 / calls_per_minute  # Minimum seconds between calls
    
    async def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limits."""
        now = datetime.now()
        
        # Remove timestamps older than 1 minute
        cutoff_time = now - timedelta(minutes=1)
        self.call_timestamps = [ts for ts in self.call_timestamps if ts > cutoff_time]
        
        # Check if we need to wait
        if len(self.call_timestamps) >= self.calls_per_minute:
            # Find the oldest timestamp and calculate wait time
            oldest_timestamp = min(self.call_timestamps)
            wait_until = oldest_timestamp + timedelta(minutes=1)
            
            if now < wait_until:
                wait_seconds = (wait_until - now).total_seconds()
                logger.info(f"Rate limit reached, waiting {wait_seconds:.2f} seconds")
                await asyncio.sleep(wait_seconds)
        
        # Record this call
        self.call_timestamps.append(datetime.now())
    
    @asynccontextmanager
    async def rate_limited_call(self):
        """Context manager for rate-limited API calls."""
        await self.wait_if_needed()
        yield
    
    def get_remaining_calls(self) -> int:
        """Get number of calls remaining in current minute."""
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=1)
        recent_calls = len([ts for ts in self.call_timestamps if ts > cutoff_time])
        return max(0, self.calls_per_minute - recent_calls)


class APIResponseValidator:
    """Validates API response data structure and content."""
    
    @staticmethod
    def validate_stock_quote_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate stock quote response structure."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if "error" in response:
            validation_result["valid"] = False
            validation_result["errors"].append(f"API error: {response['error']}")
            return validation_result
        
        required_fields = ["symbol", "bid_price", "ask_price", "timestamp"]
        for field in required_fields:
            if field not in response:
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["valid"] = False
        
        # Validate data types and ranges
        if "bid_price" in response:
            if response["bid_price"] is not None and not isinstance(response["bid_price"], (int, float)):
                validation_result["errors"].append("bid_price must be numeric")
                validation_result["valid"] = False
            elif response["bid_price"] is not None and response["bid_price"] <= 0:
                validation_result["warnings"].append("bid_price is zero or negative")
        
        if "ask_price" in response:
            if response["ask_price"] is not None and not isinstance(response["ask_price"], (int, float)):
                validation_result["errors"].append("ask_price must be numeric")
                validation_result["valid"] = False
            elif response["ask_price"] is not None and response["ask_price"] <= 0:
                validation_result["warnings"].append("ask_price is zero or negative")
        
        # Check bid-ask spread
        if (response.get("bid_price") and response.get("ask_price") and
            response["bid_price"] > response["ask_price"]):
            validation_result["warnings"].append("bid_price is higher than ask_price")
        
        return validation_result
    
    @staticmethod
    def validate_order_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate order response structure."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if "error" in response:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Order error: {response['error']}")
            return validation_result
        
        required_fields = ["id", "symbol", "qty", "side", "status"]
        for field in required_fields:
            if field not in response:
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["valid"] = False
        
        # Validate enums
        if "side" in response and response["side"] not in ["buy", "sell"]:
            validation_result["errors"].append(f"Invalid side: {response['side']}")
            validation_result["valid"] = False
        
        valid_statuses = ["new", "partially_filled", "filled", "done_for_day", 
                         "canceled", "expired", "replaced", "pending_cancel", 
                         "pending_replace", "accepted", "pending_new", "accepted_for_bidding", 
                         "stopped", "rejected", "suspended", "calculated"]
        
        if "status" in response and response["status"] not in valid_statuses:
            validation_result["warnings"].append(f"Unusual order status: {response['status']}")
        
        return validation_result
    
    @staticmethod
    def validate_account_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate account response structure."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if "error" in response:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Account error: {response['error']}")
            return validation_result
        
        required_fields = ["account_number", "buying_power", "cash", "portfolio_value"]
        for field in required_fields:
            if field not in response:
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["valid"] = False
        
        # Validate numeric fields
        numeric_fields = ["buying_power", "cash", "portfolio_value", "equity"]
        for field in numeric_fields:
            if field in response and not isinstance(response[field], (int, float)):
                validation_result["errors"].append(f"{field} must be numeric")
                validation_result["valid"] = False
        
        return validation_result


class TestDataGenerator:
    """Generates test data for API testing."""
    
    @staticmethod
    def generate_test_order_params(symbol: str = "AAPL", 
                                  order_type: str = "limit") -> Dict[str, Any]:
        """Generate safe test order parameters."""
        base_params = {
            "symbol": symbol,
            "qty": 1,  # Minimal quantity
            "side": "buy",
            "time_in_force": "day"
        }
        
        if order_type == "limit":
            base_params.update({
                "order_type": "limit",
                "limit_price": 100.00  # Safe limit price
            })
        elif order_type == "market":
            base_params.update({
                "order_type": "market"
            })
        elif order_type == "stop":
            base_params.update({
                "order_type": "stop",
                "stop_price": 95.00  # Safe stop price
            })
        
        return base_params
    
    @staticmethod
    def generate_test_symbols(count: int = 5) -> List[str]:
        """Generate list of test symbols."""
        common_symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
            "META", "NVDA", "NFLX", "SPY", "QQQ"
        ]
        return common_symbols[:count]
    
    @staticmethod
    def generate_option_symbols(underlying: str = "AAPL", count: int = 3) -> List[str]:
        """Generate test option symbols."""
        # Generate some realistic option symbols
        # Format: UNDERLYING + YYMMDD + C/P + STRIKE (8 digits)
        base_date = "240315"  # March 15, 2024
        
        symbols = []
        strikes = [140, 150, 160]  # Different strike prices
        
        for i, strike in enumerate(strikes[:count]):
            option_type = "C" if i % 2 == 0 else "P"
            strike_str = f"{strike:08d}"  # 8-digit strike (multiply by 1000)
            symbols.append(f"{underlying}{base_date}{option_type}{strike_str}")
        
        return symbols