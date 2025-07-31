# API Architecture - Real Data Only Design

## Overview

This document defines the API architecture for the opitios_alpaca service, ensuring 100% real market data usage with comprehensive error handling for scenarios where real data is unavailable.

## API Design Principles

### 1. Real Data Only Policy
- **Zero Calculated Data**: No Black-Scholes, theoretical pricing, or mock values
- **Source Attribution**: Every response includes data source information
- **Fail Fast**: Return structured errors when real data unavailable
- **Transparency**: Clear indication of data availability and freshness

### 2. Consistent Error Handling
- **Structured Errors**: Standardized error format across all endpoints
- **HTTP Status Alignment**: Proper HTTP status codes for different error types
- **Actionable Messages**: Error messages with suggested user actions
- **Request Tracing**: Unique request IDs for debugging

### 3. Data Integrity
- **Validation Layers**: Multi-level data validation
- **Freshness Tracking**: Data age and market status information
- **Type Safety**: Strong typing with Pydantic models
- **Immutable Responses**: Consistent response structure

## API Request/Response Patterns

### Success Response Pattern
All successful responses follow this structure:

```json
{
    "data": {
        // Actual market data
    },
    "metadata": {
        "data_source": "alpaca_real_time",
        "timestamp": "2024-01-15T15:30:00Z",
        "data_freshness_seconds": 1.2,
        "market_status": "open",
        "request_id": "req_1234567890"
    }
}
```

### Error Response Pattern
All error responses follow this structure:

```json
{
    "error": {
        "code": "REAL_DATA_UNAVAILABLE",
        "message": "Real market data not available for the requested symbol",
        "type": "data_unavailable",
        "details": {
            "symbol": "AAPL240216C00190000",
            "reason": "Option contract not found in Alpaca database"
        }
    },
    "metadata": {
        "request_id": "req_1234567890",
        "timestamp": "2024-01-15T15:30:00Z",
        "suggested_action": "Verify the option symbol format and expiration date"
    }
}
```

## Endpoint Specifications

### 1. Stock Quote Endpoints

#### GET /api/v1/stocks/{symbol}/quote
**Purpose**: Get real-time stock quote data

**Success Response (200)**:
```json
{
    "data": {
        "symbol": "AAPL",
        "bid_price": 210.25,
        "ask_price": 210.30,
        "last_price": 210.28,
        "bid_size": 100,
        "ask_size": 200,
        "volume": 1250000
    },
    "metadata": {
        "data_source": "alpaca_real_time",
        "timestamp": "2024-01-15T15:30:00Z",
        "data_freshness_seconds": 0.8,
        "market_status": "open",
        "request_id": "req_1234567890"
    }
}
```

**Error Responses**:
- **404**: Symbol not found or no real data available
- **429**: Rate limit exceeded  
- **503**: Alpaca API unavailable

#### POST /api/v1/stocks/quotes/batch
**Purpose**: Get multiple stock quotes in single request

**Request Body**:
```json
{
    "symbols": ["AAPL", "TSLA", "GOOGL"],
    "max_age_seconds": 30
}
```

**Success Response (200)**:
```json
{
    "data": {
        "quotes": [
            {
                "symbol": "AAPL",
                "bid_price": 210.25,
                "ask_price": 210.30,
                "status": "success"
            },
            {
                "symbol": "INVALID",
                "status": "error",
                "error": {
                    "code": "SYMBOL_NOT_FOUND",
                    "message": "Real data not available for symbol INVALID"
                }
            }
        ],
        "summary": {
            "total_requested": 3,
            "successful": 2,
            "failed": 1
        }
    },
    "metadata": {
        "data_source": "alpaca_real_time",
        "timestamp": "2024-01-15T15:30:00Z",
        "request_id": "req_1234567891"
    }
}
```

### 2. Options Endpoints

#### GET /api/v1/options/{symbol}/quote
**Purpose**: Get real options contract quote

**Success Response (200)**:
```json
{
    "data": {
        "symbol": "AAPL240216C00190000",
        "underlying_symbol": "AAPL",
        "underlying_price": 210.28,
        "strike_price": 190.0,
        "expiration_date": "2024-02-16",
        "option_type": "call",
        "bid_price": 22.10,
        "ask_price": 22.35,
        "last_price": 22.20,
        "volume": 150,
        "open_interest": 1200,
        "in_the_money": true
    },
    "metadata": {
        "data_source": "alpaca_options_real_time",
        "timestamp": "2024-01-15T15:30:00Z",
        "data_freshness_seconds": 2.1,
        "market_status": "open",
        "request_id": "req_1234567892"
    }
}
```

**Error Response (404)**:
```json
{
    "error": {
        "code": "OPTION_DATA_UNAVAILABLE",
        "message": "Real options data not available for AAPL240216C00190000",
        "type": "data_unavailable",
        "details": {
            "symbol": "AAPL240216C00190000",
            "reason": "Contract not found in Alpaca options database",
            "parsed_components": {
                "underlying": "AAPL",
                "expiration": "2024-02-16", 
                "type": "call",
                "strike": 190.0
            }
        }
    },
    "metadata": {
        "request_id": "req_1234567892",
        "timestamp": "2024-01-15T15:30:00Z",
        "suggested_action": "Verify option contract exists and is actively traded"
    }
}
```

#### GET /api/v1/options/{underlying}/chain
**Purpose**: Get real options chain data

**Query Parameters**:
- `expiration_date` (optional): Filter by expiration date
- `option_type` (optional): "call" or "put"
- `min_strike` (optional): Minimum strike price
- `max_strike` (optional): Maximum strike price

**Success Response (200)**:
```json
{
    "data": {
        "underlying_symbol": "AAPL",
        "underlying_price": 210.28,
        "expiration_dates": ["2024-01-19", "2024-02-16", "2024-03-15"],
        "contracts": [
            {
                "symbol": "AAPL240119C00200000",
                "strike_price": 200.0,
                "expiration_date": "2024-01-19",
                "option_type": "call",
                "bid_price": 10.50,
                "ask_price": 10.75,
                "volume": 500,
                "open_interest": 2500
            }
        ],
        "total_contracts": 150,
        "filtered_contracts": 25,
        "filters_applied": {
            "expiration_date": "2024-01-19",
            "option_type": "call"
        }
    },
    "metadata": {
        "data_source": "alpaca_options_chain",
        "timestamp": "2024-01-15T15:30:00Z",
        "data_freshness_seconds": 15.2,
        "market_status": "open",
        "request_id": "req_1234567893"
    }
}
```

**Error Response (404)**:
```json
{
    "error": {
        "code": "OPTIONS_CHAIN_UNAVAILABLE",
        "message": "No real options chain data available for AAPL",
        "type": "data_unavailable",
        "details": {
            "underlying_symbol": "AAPL",
            "reason": "No active options contracts found in Alpaca database"
        }
    },
    "metadata": {
        "request_id": "req_1234567893",
        "timestamp": "2024-01-15T15:30:00Z",
        "suggested_action": "Check if the underlying symbol has listed options"
    }
}
```

### 3. Historical Data Endpoints

#### GET /api/v1/stocks/{symbol}/bars
**Purpose**: Get real historical price bars

**Query Parameters**:
- `timeframe`: "1Min", "5Min", "15Min", "1Hour", "1Day"
- `start_date`: ISO 8601 date string
- `end_date`: ISO 8601 date string
- `limit`: Maximum number of bars (default: 100, max: 1000)

**Success Response (200)**:
```json
{
    "data": {
        "symbol": "AAPL",
        "timeframe": "1Day",
        "bars": [
            {
                "timestamp": "2024-01-12T00:00:00Z",
                "open": 208.50,
                "high": 212.75,
                "low": 207.80,
                "close": 210.28,
                "volume": 45000000,
                "vwap": 209.85
            }
        ],
        "count": 1,
        "page_info": {
            "has_more": false,
            "next_page_token": null
        }
    },
    "metadata": {
        "data_source": "alpaca_historical",
        "timestamp": "2024-01-15T15:30:00Z",
        "request_id": "req_1234567894"
    }
}
```

## Error Code Reference

### Data Availability Errors (4xx)
| Code | HTTP Status | Description | Suggested Action |
|------|-------------|-------------|------------------|
| `SYMBOL_NOT_FOUND` | 404 | Stock symbol not found | Verify symbol spelling |
| `OPTION_DATA_UNAVAILABLE` | 404 | Option contract data not available | Check contract existence |
| `OPTIONS_CHAIN_UNAVAILABLE` | 404 | No options chain data | Verify underlying has options |
| `HISTORICAL_DATA_UNAVAILABLE` | 404 | No historical data for timeframe | Try different date range |
| `INVALID_SYMBOL_FORMAT` | 400 | Symbol format incorrect | Check symbol format rules |
| `INVALID_DATE_RANGE` | 400 | Date range invalid | Use valid date range |

### Service Errors (5xx)
| Code | HTTP Status | Description | Suggested Action |
|------|-------------|-------------|------------------|
| `UPSTREAM_SERVICE_ERROR` | 503 | Alpaca API unavailable | Retry in few minutes |
| `RATE_LIMIT_EXCEEDED` | 429 | API rate limit hit | Wait and retry |
| `INTERNAL_SERVICE_ERROR` | 500 | Internal processing error | Contact support |
| `DATA_VALIDATION_ERROR` | 500 | Received invalid data from source | Contact support |

## Request/Response Validation

### Request Validation
- **Symbol Format**: Alpaca-compliant symbol validation
- **Parameter Ranges**: Enforce min/max values for numeric parameters
- **Date Validation**: ISO 8601 date format validation
- **Rate Limiting**: Per-client request limits

### Response Validation
- **Data Completeness**: Validate required fields present
- **Data Freshness**: Check timestamp validity
- **Source Attribution**: Ensure data_source field present
- **Type Consistency**: Validate data types match schema

## Caching Strategy

### Cache Keys
```
cache:stocks:quote:{symbol}
cache:options:quote:{option_symbol}
cache:options:chain:{underlying}:{expiration}:{type}
```

### Cache TTL (Time To Live)
- **Real-time Quotes**: 5-30 seconds (market hours), 5 minutes (after hours)
- **Options Data**: 30-60 seconds (market hours), 10 minutes (after hours)
- **Historical Data**: 1 hour (intraday), 24 hours (daily/weekly)

### Cache Headers
```http
Cache-Control: max-age=30, must-revalidate
X-Data-Source: alpaca_real_time
X-Cache-Status: HIT/MISS
X-Data-Freshness: 1.2
```

## Rate Limiting

### Default Limits
- **Anonymous**: 100 requests/hour
- **Authenticated**: 1000 requests/hour  
- **Premium**: 5000 requests/hour

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642258800
Retry-After: 3600
```

## Security Considerations

### Input Validation
- SQL injection prevention
- XSS protection in error messages
- Parameter sanitization
- Request size limits

### Authentication
- API key validation
- Request signing (optional)
- IP allowlisting (optional)
- User agent validation

### Data Protection
- No sensitive data in logs
- Encrypted data transmission
- Secure credential storage
- Data retention policies

This API architecture ensures 100% real market data usage while providing comprehensive error handling and clear communication when real data is unavailable. The design prioritizes transparency, reliability, and user experience.