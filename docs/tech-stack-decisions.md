# Technology Stack Decisions - Real Market Data System

## Overview

This document outlines the technology stack decisions for the opitios_alpaca service redesign, focusing on eliminating mock data and ensuring 100% real market data usage. Each technology choice is evaluated based on reliability, performance, and alignment with the real-data-only architecture.

## Core Technology Decisions

### Runtime and Framework Stack

#### Python 3.11+ Runtime
**Choice**: Python 3.11 or later
**Rationale**: 
- **Async Performance**: Improved asyncio performance for concurrent API calls
- **Type Hints**: Enhanced type checking for data validation
- **Error Handling**: Better exception handling for complex error scenarios
- **Ecosystem**: Rich ecosystem for financial data processing
- **Team Expertise**: Existing team knowledge and codebase compatibility

**Alternatives Considered**:
- Python 3.9/3.10: Older versions with less performance optimization
- Node.js: Good async performance but less mature financial libraries
- Go: Excellent performance but requires team retraining

#### FastAPI 0.104+ Web Framework
**Choice**: FastAPI with latest stable version
**Rationale**:
- **Async Native**: Built-in async/await support for non-blocking I/O
- **Type Safety**: Pydantic integration for request/response validation
- **API Documentation**: Auto-generated OpenAPI docs for transparency
- **Performance**: High-performance async web framework
- **Error Handling**: Excellent exception handling and validation

**Alternatives Considered**:
- Flask: Simpler but less async-native and type-safe
- Django: Feature-rich but heavier for API-only service
- Starlette: Lower-level but requires more boilerplate

#### Pydantic v2 Data Validation
**Choice**: Pydantic v2 for data models and validation
**Rationale**:
- **Type Safety**: Strong typing for market data structures
- **Validation**: Comprehensive validation for incoming data
- **Serialization**: Fast JSON serialization for API responses
- **Error Messages**: Clear validation error messages
- **Performance**: V2 performance improvements

**Configuration**:
```python
# Enhanced data models for real market data
class RealStockQuote(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, regex=r'^[A-Z]+$')
    bid_price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    ask_price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    timestamp: datetime = Field(..., description="Data timestamp from Alpaca")
    data_source: Literal["alpaca_real_time"] = "alpaca_real_time"
    
    class Config:
        use_enum_values = True
        validate_assignment = True
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }
```

### External Data Integration

#### Alpaca APIs Primary Integration
**Choice**: Alpaca Trading API, Data API, and Options API
**Rationale**:
- **Single Source**: Unified data source for consistency
- **Real-time Data**: Actual market data without calculations
- **Comprehensive Coverage**: Stocks, options, historical data
- **Reliability**: Production-grade financial data provider
- **API Quality**: Well-documented REST APIs with good error handling

**Integration Architecture**:
```python
class AlpacaAPIClient:
    """Pure Alpaca API client - no fallback calculations"""
    
    def __init__(self):
        self.trading_client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.paper_trading
        )
        self.data_client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key
        )
        self.options_client = OptionHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key
        )
```

#### aiohttp HTTP Client
**Choice**: aiohttp for async HTTP requests
**Rationale**:
- **Async Performance**: Non-blocking HTTP requests
- **Connection Pooling**: Efficient connection reuse
- **Timeout Handling**: Configurable timeouts for reliability
- **Error Handling**: Comprehensive HTTP error handling
- **SSL Support**: Secure connections to Alpaca APIs

**Configuration**:
```python
# Optimized HTTP client configuration
async def create_http_client() -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    connector = aiohttp.TCPConnector(
        limit=100,              # Total connection limit
        limit_per_host=30,      # Per-host connection limit
        ttl_dns_cache=300,      # DNS cache TTL
        use_dns_cache=True,
    )
    
    return aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={
            "User-Agent": "Opitios-Alpaca-Service/1.0",
            "Accept": "application/json"
        }
    )
```

### Caching and Performance

#### Redis Caching Layer
**Choice**: Redis 7.0+ for caching real market data
**Rationale**:
- **Performance**: In-memory performance for fast data access
- **TTL Support**: Time-based expiration for market data freshness
- **Atomic Operations**: Consistent cache operations
- **Persistence**: Optional persistence for critical cached data
- **Clustering**: Horizontal scaling capability

**Cache Strategy**:
```python
class MarketDataCache:
    """Redis-based caching for real market data only"""
    
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,
            decode_responses=True,
            health_check_interval=30
        )
    
    async def cache_stock_quote(self, symbol: str, data: RealStockQuote, ttl: int = 30):
        """Cache real market data with appropriate TTL"""
        cache_key = f"stock:quote:{symbol}"
        cache_data = {
            "data": data.json(),
            "cached_at": datetime.utcnow().isoformat(),
            "data_source": data.data_source,
            "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
        }
        
        await self.redis.setex(cache_key, ttl, json.dumps(cache_data))
```

### Database and Storage

#### PostgreSQL for Configuration and Metadata
**Choice**: PostgreSQL 15+ for non-market data storage
**Rationale**:
- **ACID Compliance**: Reliable transactions for configuration data
- **JSON Support**: Store complex configuration objects
- **Performance**: Excellent query performance
- **Extensibility**: Rich extension ecosystem
- **Reliability**: Production-proven reliability

**Schema Design**:
```sql
-- Configuration and metadata only - no market data storage
CREATE TABLE api_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(255) NOT NULL,
    error_code VARCHAR(100) NOT NULL,
    error_message TEXT,
    context JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance
CREATE INDEX idx_error_logs_timestamp ON error_logs(timestamp);
CREATE INDEX idx_error_logs_error_code ON error_logs(error_code);
```

### Monitoring and Observability

#### Prometheus + Grafana Monitoring
**Choice**: Prometheus for metrics collection, Grafana for visualization
**Rationale**:
- **Real-time Metrics**: Track data source success rates
- **Custom Metrics**: Monitor real vs unavailable data ratios
- **Alerting**: Alert on data availability issues
- **Scalability**: Handle high-frequency metrics
- **Integration**: Good FastAPI integration

**Metrics Configuration**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Key metrics for real data monitoring
REAL_DATA_REQUESTS = Counter(
    'real_data_requests_total',
    'Total requests for real market data',
    ['endpoint', 'symbol', 'data_source']
)

REAL_DATA_SUCCESS = Counter(
    'real_data_success_total', 
    'Successful real data responses',
    ['endpoint', 'data_source']
)

REAL_DATA_FAILURES = Counter(
    'real_data_failures_total',
    'Failed real data requests',
    ['endpoint', 'error_code', 'data_source']
)

API_RESPONSE_TIME = Histogram(
    'api_response_time_seconds',
    'API response time',
    ['endpoint', 'status']
)

DATA_FRESHNESS = Gauge(
    'market_data_freshness_seconds',
    'Age of market data in seconds',
    ['symbol', 'data_type']
)
```

#### Structured Logging with loguru
**Choice**: loguru for structured logging
**Rationale**:
- **Structured Output**: JSON logging for better parsing
- **Performance**: Efficient async logging
- **Flexibility**: Easy configuration and formatting
- **Error Context**: Rich error context preservation
- **Integration**: Good FastAPI integration

**Logging Configuration**:
```python
import loguru
from loguru import logger

# Configure structured logging
logger.configure(
    handlers=[
        {
            "sink": "logs/opitios_alpaca_{time:YYYY-MM-DD}.log",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {extra} | {message}",
            "rotation": "100 MB",
            "retention": "30 days",
            "compression": "gz",
            "serialize": True,  # JSON output
            "enqueue": True,    # Async logging
        },
        {
            "sink": sys.stdout,
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
            "level": "INFO",
        }
    ]
)

# Usage with context
logger.bind(
    request_id="req_123456",
    symbol="AAPL",
    data_source="alpaca_real_time",
    endpoint="/stocks/AAPL/quote"
).info("Successfully retrieved real market data")
```

### Testing and Quality Assurance

#### pytest + pytest-asyncio Testing Framework
**Choice**: pytest with async testing support
**Rationale**:
- **Async Support**: Test async functions properly
- **Fixtures**: Reusable test components
- **Mocking**: Mock external API calls for testing
- **Coverage**: Comprehensive test coverage reporting
- **Parametrization**: Test multiple scenarios efficiently

**Test Configuration**:
```python
# conftest.py
import pytest
from unittest.mock import AsyncMock
from app.alpaca_client import AlpacaClient

@pytest.fixture
async def mock_alpaca_client():
    """Mock Alpaca client for testing"""
    client = AsyncMock(spec=AlpacaClient)
    
    # Mock real data responses
    client.get_stock_quote.return_value = {
        "symbol": "AAPL",
        "bid_price": 210.25,
        "ask_price": 210.30,
        "timestamp": datetime.utcnow(),
        "data_source": "alpaca_real_time"
    }
    
    # Mock data unavailable scenario
    client.get_option_quote.side_effect = DataAvailabilityError(
        error_code="OPTION_CONTRACT_NOT_FOUND",
        message="Option contract not found"
    )
    
    return client

@pytest.mark.asyncio
async def test_real_data_only_response(mock_alpaca_client):
    """Test that only real data is returned"""
    service = MarketDataService(alpaca_client=mock_alpaca_client)
    
    response = await service.get_stock_quote("AAPL")
    
    assert response.data_source == "alpaca_real_time"
    assert "calculated" not in response.dict()
    assert "mock" not in response.dict()
```

### Development and Deployment Tools

#### Docker Containerization
**Choice**: Docker for containerization
**Rationale**:
- **Consistency**: Same environment across dev/staging/prod
- **Isolation**: Isolated dependencies and configuration
- **Scalability**: Easy horizontal scaling
- **Deployment**: Simplified deployment process
- **Resource Management**: Better resource control

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/api/v1/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
```

#### GitHub Actions CI/CD
**Choice**: GitHub Actions for continuous integration and deployment
**Rationale**:
- **Integration**: Native GitHub integration
- **Flexibility**: Comprehensive workflow capabilities
- **Cost**: Free for public repositories
- **Ecosystem**: Rich marketplace of actions
- **Security**: Secure secrets management

**CI/CD Pipeline**:
```yaml
name: Real Data Service CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=app --cov-report=xml
      env:
        REDIS_URL: redis://localhost:6379
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
```

## Technology Stack Summary

### Production Stack
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Runtime | Python | 3.11+ | Application runtime |
| Web Framework | FastAPI | 0.104+ | API framework |
| HTTP Client | aiohttp | 3.8+ | External API calls |
| Data Validation | Pydantic | 2.0+ | Request/response validation |
| Caching | Redis | 7.0+ | Performance optimization |
| Database | PostgreSQL | 15+ | Configuration storage |
| Monitoring | Prometheus | 2.40+ | Metrics collection |
| Visualization | Grafana | 9.0+ | Metrics dashboards |
| Logging | loguru | 0.7+ | Structured logging |

### Development Stack
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Testing | pytest | 7.0+ | Test framework |
| Async Testing | pytest-asyncio | 0.21+ | Async test support |
| Code Quality | black, flake8, mypy | latest | Code quality tools |
| Containerization | Docker | 20.0+ | Application packaging |
| CI/CD | GitHub Actions | - | Automation pipeline |

### External Dependencies
| Service | Purpose | Fallback Strategy |
|---------|---------|-------------------|
| Alpaca Trading API | Real-time market data | Circuit breaker + error response |
| Alpaca Data API | Historical data | Cache recent data + error response |
| Alpaca Options API | Options data | Error response only (no fallback) |

## Performance Targets

### Response Time Targets
- **Cached Data**: < 50ms
- **Real-time Data**: < 500ms
- **Batch Operations**: < 2s for 20 symbols
- **Error Responses**: < 100ms

### Throughput Targets
- **Single Instance**: 1000+ requests/second
- **Concurrent Connections**: 100+ simultaneous
- **Cache Hit Rate**: > 80% during market hours
- **Real Data Success Rate**: > 95%

### Reliability Targets
- **Uptime**: 99.9% (excluding upstream issues)
- **Error Rate**: < 1% for application errors
- **Data Freshness**: < 30 seconds for real-time data
- **Recovery Time**: < 60 seconds after upstream recovery

This technology stack is specifically designed to support the real-data-only architecture while maintaining high performance, reliability, and observability for monitoring data source success rates.