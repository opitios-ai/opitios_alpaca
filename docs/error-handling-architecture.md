# Error Handling Architecture - Real Data Scenarios

## Overview

This document defines the comprehensive error handling architecture for the opitios_alpaca service, specifically designed to handle scenarios where real market data is unavailable. The architecture ensures transparent communication about data availability while maintaining system reliability.

## Error Handling Principles

### 1. Fail-Fast Philosophy
- **Immediate Detection**: Identify data unavailability as early as possible
- **No Silent Failures**: Every error condition produces a structured response
- **Clear Attribution**: Distinguish between different types of failures
- **Actionable Information**: Provide users with next steps when possible

### 2. Structured Error Responses
- **Consistent Format**: Standardized error structure across all endpoints
- **Error Classification**: Categorize errors by type and severity
- **Context Preservation**: Include relevant request context in errors
- **Debugging Support**: Provide information for troubleshooting

### 3. Graceful Degradation
- **Service Continuity**: Keep service operational when possible
- **Partial Results**: Return successful data even if some requests fail
- **Circuit Breaker**: Prevent cascade failures from upstream services
- **Health Monitoring**: Track system health and error patterns

## Error Classification System

### Primary Error Categories

#### 1. Data Availability Errors (4xx)
Errors where real market data is not available from Alpaca APIs.

```python
class DataAvailabilityError(BaseException):
    """Real market data not available from upstream source"""
    
    ERROR_CODES = {
        "SYMBOL_NOT_FOUND": "Stock symbol not found in Alpaca database",
        "OPTION_CONTRACT_NOT_FOUND": "Option contract not found or not actively traded",
        "OPTIONS_CHAIN_UNAVAILABLE": "No options chain data available for underlying",
        "HISTORICAL_DATA_UNAVAILABLE": "Historical data not available for requested timeframe",
        "REAL_TIME_DATA_UNAVAILABLE": "Real-time data feed temporarily unavailable",
        "MARKET_CLOSED_NO_DATA": "Market closed and no recent data available"
    }
```

#### 2. External Service Errors (5xx)
Errors related to upstream Alpaca API services.

```python
class ExternalServiceError(BaseException):
    """Upstream service (Alpaca API) errors"""
    
    ERROR_CODES = {
        "UPSTREAM_API_UNAVAILABLE": "Alpaca API service temporarily unavailable",
        "UPSTREAM_TIMEOUT": "Alpaca API request timed out",
        "UPSTREAM_RATE_LIMITED": "Alpaca API rate limit exceeded",
        "UPSTREAM_AUTHENTICATION_FAILED": "Alpaca API authentication failed",
        "UPSTREAM_INVALID_RESPONSE": "Received invalid response from Alpaca API"
    }
```

#### 3. Data Validation Errors (422)
Errors where data is available but fails validation.

```python
class DataValidationError(BaseException):
    """Data validation failures"""
    
    ERROR_CODES = {
        "STALE_DATA_REJECTED": "Data too old to be considered current",
        "INVALID_PRICE_DATA": "Price data failed validation checks",
        "INCOMPLETE_DATA_STRUCTURE": "Required data fields missing",
        "DATA_INTEGRITY_VIOLATION": "Data integrity checks failed",
        "SCHEMA_VALIDATION_FAILED": "Data doesn't match expected schema"
    }
```

#### 4. Business Rule Errors (400)
Errors where business rules are violated.

```python
class BusinessRuleError(BaseException):
    """Business rule violations"""
    
    ERROR_CODES = {
        "SYMBOL_FORMAT_INVALID": "Symbol format doesn't match requirements",
        "DATE_RANGE_INVALID": "Date range exceeds allowed limits",
        "REQUEST_SIZE_EXCEEDED": "Request exceeds maximum allowed size",
        "MARKET_HOURS_RESTRICTION": "Operation not allowed outside market hours",
        "INSUFFICIENT_PERMISSIONS": "Operation requires higher permission level"
    }
```

## Error Response Structure

### Standard Error Response Format
```json
{
    "error": {
        "code": "REAL_DATA_UNAVAILABLE",
        "message": "Real market data not available for the requested symbol",
        "type": "data_unavailable",
        "severity": "warning",
        "details": {
            "symbol": "AAPL240216C00190000",
            "reason": "Option contract not found in Alpaca database",
            "upstream_error": "Contract not listed",
            "data_attempted": ["alpaca_options_api", "alpaca_data_api"]
        }
    },
    "metadata": {
        "request_id": "req_1234567890",
        "timestamp": "2024-01-15T15:30:00Z",
        "endpoint": "/api/v1/options/AAPL240216C00190000/quote",
        "suggested_actions": [
            "Verify the option symbol format is correct",
            "Check if the option contract is actively traded",
            "Try a different expiration date"
        ],
        "documentation_url": "https://docs.opitios.com/errors/REAL_DATA_UNAVAILABLE",
        "retry_after": null
    }
}
```

### Error Response Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error.code` | string | Yes | Unique error identifier |
| `error.message` | string | Yes | Human-readable error description |
| `error.type` | string | Yes | Error category classification |
| `error.severity` | string | Yes | Error severity level |
| `error.details` | object | No | Additional error-specific information |
| `metadata.request_id` | string | Yes | Unique request identifier |
| `metadata.timestamp` | string | Yes | When error occurred (ISO 8601) |
| `metadata.endpoint` | string | Yes | API endpoint that generated error |
| `metadata.suggested_actions` | array | No | Actionable suggestions for user |
| `metadata.retry_after` | integer | No | Seconds to wait before retry |

## Error Handling Implementation

### 1. Error Detection and Classification

```python
class ErrorHandler:
    """Centralized error handling and classification"""
    
    async def handle_alpaca_api_error(self, error: Exception, context: RequestContext) -> ErrorResponse:
        """Convert Alpaca API errors to standardized error responses"""
        
        if isinstance(error, AlpacaAPINotFoundError):
            return self._create_data_unavailable_error(error, context)
        elif isinstance(error, AlpacaAPIRateLimitError):
            return self._create_rate_limit_error(error, context)
        elif isinstance(error, AlpacaAPITimeoutError):
            return self._create_timeout_error(error, context)
        elif isinstance(error, AlpacaAPIAuthError):
            return self._create_auth_error(error, context)
        else:
            return self._create_generic_upstream_error(error, context)
    
    def _create_data_unavailable_error(self, error: AlpacaAPINotFoundError, context: RequestContext) -> ErrorResponse:
        """Create structured error for data unavailability"""
        
        # Determine specific error code based on context
        if context.endpoint_type == "stock_quote":
            error_code = "SYMBOL_NOT_FOUND"
        elif context.endpoint_type == "option_quote":
            error_code = "OPTION_CONTRACT_NOT_FOUND"
        elif context.endpoint_type == "options_chain":
            error_code = "OPTIONS_CHAIN_UNAVAILABLE"
        else:
            error_code = "REAL_DATA_UNAVAILABLE"
        
        return ErrorResponse(
            error=ErrorDetails(
                code=error_code,
                message=self._get_error_message(error_code),
                type="data_unavailable",
                severity="warning",
                details={
                    "symbol": context.symbol,
                    "reason": str(error),
                    "upstream_error": error.alpaca_error_code,
                    "data_attempted": ["alpaca_api"]
                }
            ),
            metadata=ErrorMetadata(
                request_id=context.request_id,
                timestamp=datetime.utcnow(),
                endpoint=context.endpoint,
                suggested_actions=self._get_suggested_actions(error_code, context)
            )
        )
```

### 2. Error Response Generation

```python
class ErrorResponseGenerator:
    """Generate consistent error responses"""
    
    def __init__(self):
        self.error_messages = {
            "SYMBOL_NOT_FOUND": "Stock symbol '{}' not found in real market data",
            "OPTION_CONTRACT_NOT_FOUND": "Option contract '{}' not found or not actively traded",
            "REAL_DATA_UNAVAILABLE": "Real market data temporarily unavailable for '{}'",
            "UPSTREAM_API_UNAVAILABLE": "Market data service temporarily unavailable"
        }
        
        self.suggested_actions = {
            "SYMBOL_NOT_FOUND": [
                "Verify the stock symbol spelling",
                "Check if the stock is listed on supported exchanges",
                "Try searching for the company name instead"
            ],
            "OPTION_CONTRACT_NOT_FOUND": [
                "Verify the option symbol format (e.g., AAPL240216C00190000)",
                "Check if the option contract is actively traded",
                "Try different strike prices or expiration dates"
            ],
            "UPSTREAM_API_UNAVAILABLE": [
                "Wait a few minutes and try again",
                "Check system status page for known issues",
                "Contact support if problem persists"
            ]
        }
    
    def generate_error_response(self, error_code: str, context: RequestContext, 
                              additional_details: Dict = None) -> ErrorResponse:
        """Generate standardized error response"""
        
        message = self.error_messages.get(error_code, "An error occurred")
        if context.symbol:
            message = message.format(context.symbol)
        
        error_details = {
            "symbol": context.symbol,
            "endpoint": context.endpoint,
            "timestamp": context.timestamp
        }
        
        if additional_details:
            error_details.update(additional_details)
        
        return ErrorResponse(
            error=ErrorDetails(
                code=error_code,
                message=message,
                type=self._get_error_type(error_code),
                severity=self._get_error_severity(error_code),
                details=error_details
            ),
            metadata=ErrorMetadata(
                request_id=context.request_id,
                timestamp=datetime.utcnow(),
                endpoint=context.endpoint,
                suggested_actions=self.suggested_actions.get(error_code, [])
            )
        )
```

### 3. Circuit Breaker Implementation

```python
class CircuitBreaker:
    """Prevent cascade failures from upstream services"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Service temporarily unavailable")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
```

### 4. Batch Operation Error Handling

```python
class BatchErrorHandler:
    """Handle errors in batch operations"""
    
    async def handle_batch_quotes(self, symbols: List[str]) -> BatchQuoteResponse:
        """Handle batch quote requests with partial failures"""
        
        results = []
        errors = []
        
        for symbol in symbols:
            try:
                quote_data = await self.get_stock_quote(symbol)
                results.append({
                    "symbol": symbol,
                    "status": "success",
                    "data": quote_data
                })
            except DataAvailabilityError as e:
                errors.append({
                    "symbol": symbol,
                    "status": "error",
                    "error": self._format_batch_error(e)
                })
            except Exception as e:
                errors.append({
                    "symbol": symbol,
                    "status": "error", 
                    "error": self._format_unexpected_error(e)
                })
        
        return BatchQuoteResponse(
            results=results,
            errors=errors,
            summary={
                "total_requested": len(symbols),
                "successful": len(results),
                "failed": len(errors),
                "success_rate": len(results) / len(symbols) * 100
            }
        )
```

## HTTP Status Code Mapping

### Error Type to HTTP Status Mapping

| Error Type | HTTP Status | Description |
|------------|-------------|-------------|
| `data_unavailable` | 404 | Requested data not found in real sources |
| `validation_failed` | 422 | Data validation failed |
| `business_rule_violation` | 400 | Request violates business rules |
| `authentication_failed` | 401 | Authentication credentials invalid |
| `rate_limit_exceeded` | 429 | Request rate limit exceeded |
| `upstream_service_error` | 503 | External service unavailable |
| `timeout` | 504 | Request timeout |
| `internal_error` | 500 | Internal processing error |

### Response Headers for Errors

```python
def get_error_headers(error_type: str, error_code: str) -> Dict[str, str]:
    """Generate appropriate HTTP headers for error responses"""
    
    headers = {
        "Content-Type": "application/json",
        "X-Error-Code": error_code,
        "X-Error-Type": error_type,
        "X-RateLimit-Remaining": str(get_remaining_rate_limit()),
    }
    
    if error_code == "UPSTREAM_RATE_LIMITED":
        headers["Retry-After"] = "300"  # 5 minutes
    elif error_code == "UPSTREAM_API_UNAVAILABLE":
        headers["Retry-After"] = "60"   # 1 minute
    
    return headers
```

## Error Monitoring and Alerting

### Error Metrics Collection

```python
class ErrorMetricsCollector:
    """Collect and report error metrics"""
    
    async def record_error(self, error_code: str, error_type: str, 
                          endpoint: str, symbol: str = None):
        """Record error occurrence for monitoring"""
        
        metrics = {
            "error_code": error_code,
            "error_type": error_type,
            "endpoint": endpoint,
            "symbol": symbol,
            "timestamp": datetime.utcnow()
        }
        
        # Send to metrics system
        await self.metrics_client.increment(f"errors.{error_type}.{error_code}")
        await self.metrics_client.increment(f"errors.by_endpoint.{endpoint}")
        
        if symbol:
            await self.metrics_client.increment(f"errors.by_symbol.{symbol}")
```

### Alert Conditions

```yaml
# Error rate alerting configuration
alerts:
  - name: "High Data Unavailability Rate"
    condition: "rate(errors{error_type='data_unavailable'}[5m]) > 0.1"
    severity: "warning"
    message: "High rate of data unavailability errors detected"
    
  - name: "Upstream Service Down"
    condition: "rate(errors{error_code='UPSTREAM_API_UNAVAILABLE'}[1m]) > 0.05"
    severity: "critical"
    message: "Alpaca API appears to be unavailable"
    
  - name: "Data Validation Failures"
    condition: "rate(errors{error_type='validation_failed'}[10m]) > 0.02"
    severity: "warning"
    message: "Unusual rate of data validation failures"
```

## Error Recovery Strategies

### 1. Retry Logic with Exponential Backoff

```python
class RetryHandler:
    """Handle retries with exponential backoff"""
    
    async def retry_with_backoff(self, func: Callable, max_retries: int = 3, 
                                base_delay: float = 1.0) -> Any:
        """Retry function with exponential backoff"""
        
        for attempt in range(max_retries + 1):
            try:
                return await func()
            except (ConnectionError, TimeoutError) as e:
                if attempt == max_retries:
                    raise e
                
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            except DataAvailabilityError:
                # Don't retry data unavailability errors
                raise
```

### 2. Fallback Data Sources (Limited)

```python
class FallbackHandler:
    """Handle fallbacks to alternative data sources (real data only)"""
    
    async def get_stock_quote_with_fallback(self, symbol: str) -> StockQuoteResponse:
        """Try multiple real data sources"""
        
        # Primary: Real-time API
        try:
            return await self.alpaca_client.get_real_time_quote(symbol)
        except DataAvailabilityError:
            pass
        
        # Fallback: Last known good data (if recent)
        try:
            cached_data = await self.cache.get_recent_quote(symbol, max_age=300)
            if cached_data:
                return self._format_cached_response(cached_data)
        except CacheError:
            pass
        
        # No fallback to calculated data - return error
        raise DataAvailabilityError(
            error_code="REAL_DATA_UNAVAILABLE",
            message=f"No real market data available for {symbol}"
        )
```

This comprehensive error handling architecture ensures that users receive clear, actionable information when real market data is unavailable, while maintaining system reliability and preventing the introduction of any calculated or mock data.