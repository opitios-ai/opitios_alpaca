# System Architecture - Opitios Alpaca Trading Service

## Executive Summary
This document outlines the comprehensive technical architecture for fixing and enhancing the opitios_alpaca system, a FastAPI-based multi-user trading service that provides real-time stock and options trading capabilities through the Alpaca API. The architecture addresses critical issues including JWT package conflicts, Pydantic V2 compatibility, testing framework gaps, and production readiness requirements.

## Architecture Overview

### System Context
```mermaid
C4Context
    Person(trader, "Trader", "Individual trader using the platform")
    Person(admin, "Admin", "System administrator")
    System(opitios_alpaca, "Opitios Alpaca Service", "Multi-user trading API service")
    System_Ext(alpaca_api, "Alpaca Markets API", "Stock/Options trading platform")
    System_Ext(redis, "Redis", "Caching and rate limiting")
    System_Ext(mysql, "MySQL", "User credentials and trading data")
    
    Rel(trader, opitios_alpaca, "Places trades via REST API")
    Rel(admin, opitios_alpaca, "Manages users and system")
    Rel(opitios_alpaca, alpaca_api, "Executes trades and fetches market data")
    Rel(opitios_alpaca, redis, "Rate limiting and caching")
    Rel(opitios_alpaca, mysql, "User management and audit logs")
```

### Container Diagram
```mermaid
C4Container
    Container(web_api, "FastAPI Application", "Python 3.9+", "REST API with JWT authentication")
    Container(auth_middleware, "Authentication Layer", "JWT + User Context", "Multi-user auth and authorization")
    Container(rate_limiter, "Rate Limiting", "Redis/Memory", "Per-user API rate limiting")
    Container(connection_pool, "Alpaca Connection Pool", "Connection Manager", "Efficient API connection reuse")
    Container(user_manager, "User Context Manager", "SQLAlchemy", "Encrypted credential management")
    Container(logging, "Logging System", "Loguru", "Structured logging and monitoring")
    ContainerDb(redis_cache, "Redis Cache", "Redis 7+", "Session and rate limit storage")
    ContainerDb(mysql_db, "MySQL Database", "MySQL 8+", "User accounts and trading history")
    
    Rel(web_api, auth_middleware, "Validates JWT tokens")
    Rel(auth_middleware, user_manager, "Retrieves user context")
    Rel(web_api, rate_limiter, "Enforces API limits")
    Rel(rate_limiter, redis_cache, "Stores rate limit counters")
    Rel(web_api, connection_pool, "Alpaca API calls")
    Rel(user_manager, mysql_db, "User credential storage")
    Rel(web_api, logging, "Request/response logging")
```

## Technology Stack

### Current Stack (Fixed)
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Framework** | FastAPI | 0.104.1 | High-performance async web framework |
| **Runtime** | Python | 3.9+ | Primary language runtime |
| **Authentication** | PyJWT | 2.8.0 | JWT token handling (FIXED import) |
| **Data Validation** | Pydantic | 2.5.0 | Request/response validation (V2 compatible) |
| **Database ORM** | SQLAlchemy | 2.0.23 | Modern async ORM for user management |
| **Caching** | Redis | 5.0.1 | Rate limiting and session storage |
| **Trading API** | alpaca-py | 0.21.0 | Official Alpaca Markets SDK |
| **Logging** | Loguru | 0.7.2 | Structured logging with rotation |
| **Testing** | pytest | 7.4.3 | Comprehensive test framework |
| **HTTP Client** | httpx | 0.25.2 | Async HTTP client for external APIs |

### Architecture Principles
- **Security First**: JWT-based authentication with role-based permissions
- **Multi-tenancy**: Complete user isolation with encrypted credentials
- **Performance**: Connection pooling and Redis-based caching
- **Reliability**: Comprehensive error handling and circuit breakers
- **Observability**: Structured logging with request tracing
- **Scalability**: Stateless design with horizontal scaling capability

## Component Design

### Authentication & Authorization Layer
**Purpose**: Secure multi-user access with JWT-based authentication
**Technology**: PyJWT + SQLAlchemy + Redis
**Key Features**:
- JWT token validation with configurable expiration
- Role-based permissions (admin, trader, viewer)
- User context management with encrypted credentials
- Session management with Redis backend
- Rate limiting per user and endpoint

**Interfaces**:
- Input: HTTP requests with Bearer tokens
- Output: User context with decrypted Alpaca credentials
- Dependencies: MySQL for user storage, Redis for session cache

### Rate Limiting System
**Purpose**: Prevent API abuse and ensure fair resource allocation
**Technology**: Redis (primary) with memory fallback
**Implementation**: Sliding window algorithm with per-user limits

**Configuration**:
```python
RATE_LIMITS = {
    "/api/v1/stocks/quote": (60, 60),        # 60 requests per minute
    "/api/v1/options/quotes/batch": (20, 60), # 20 requests per minute
    "/api/v1/stocks/order": (10, 60),        # 10 orders per minute
    "default": (120, 60)                     # Default: 120 requests per minute
}
```

### Connection Pool Manager
**Purpose**: Efficient management of Alpaca API connections
**Technology**: Custom connection pool with health monitoring
**Features**:
- Per-user connection isolation
- Connection health checks and auto-recovery
- Circuit breaker pattern for API failures
- Metrics collection for monitoring

### User Context Manager
**Purpose**: Secure storage and management of user credentials
**Technology**: SQLAlchemy 2.0 + Cryptography (Fernet)
**Security Features**:
- AES encryption for API keys at rest
- In-memory credential caching with TTL
- Automatic cleanup of inactive sessions
- Audit logging for credential access

## Data Architecture

### Database Schema
```sql
-- Users table with encrypted credentials
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'trader', 'viewer') DEFAULT 'trader',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
);

-- Encrypted Alpaca credentials
CREATE TABLE user_credentials (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    alpaca_api_key_encrypted TEXT NOT NULL,
    alpaca_secret_key_encrypted TEXT NOT NULL,
    paper_trading BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
);

-- Trading activity audit log
CREATE TABLE trading_audit (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    action VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    quantity DECIMAL(10,4),
    price DECIMAL(12,4),
    order_id VARCHAR(100),
    status VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id_created (user_id, created_at),
    INDEX idx_symbol_created (symbol, created_at)
);
```

### Redis Data Structure
```redis
# Rate limiting (sliding window)
rate_limit:user:{user_id}:{endpoint}:{window} -> Sorted Set of timestamps

# User sessions
session:{user_id} -> Hash {
    "last_active": timestamp,
    "permissions": json_array,
    "alpaca_credentials": encrypted_json
}

# Connection pool health
connection_pool:{user_id} -> Hash {
    "status": "healthy|degraded|failed",
    "last_check": timestamp,
    "error_count": integer
}
```

## Security Architecture

### Authentication Flow
1. **Login**: Username/password → JWT token with user_id and permissions
2. **Request Validation**: Extract JWT → Verify signature → Load user context
3. **Credential Access**: Decrypt stored Alpaca credentials for API calls
4. **Authorization**: Check user permissions for requested endpoint
5. **Audit**: Log all trading actions with user attribution

### Security Measures
- [ ] JWT tokens with configurable expiration (24h default)
- [ ] PBKDF2 password hashing with salt
- [ ] AES-256 encryption for API credentials at rest
- [ ] TLS 1.3 for all external communications
- [ ] Input validation and sanitization via Pydantic V2
- [ ] SQL injection prevention via SQLAlchemy parameterized queries
- [ ] Rate limiting to prevent DoS attacks
- [ ] CORS restrictions to approved domains only
- [ ] Secrets management via environment variables
- [ ] Audit logging for all trading operations

### Permission Matrix
| Role | Market Data | Trading | User Management | System Admin |
|------|-------------|---------|----------------|--------------|
| viewer | ✓ | ✗ | ✗ | ✗ |
| trader | ✓ | ✓ | ✗ | ✗ |
| admin | ✓ | ✓ | ✓ | ✓ |

## Dependency Resolution Strategy

### JWT Package Conflict Resolution
**Issue**: Conflicting JWT packages causing import errors
**Solution**:
```python
# Current problematic import:
import jwt  # Ambiguous - could be jwt or PyJWT

# Fixed import strategy:
try:
    import jwt  # PyJWT package provides 'jwt' module
except ImportError:
    raise ImportError("PyJWT package is required: pip install PyJWT==2.8.0")

# Verify correct package is installed
def verify_jwt_package():
    """Ensure we're using PyJWT, not python-jwt"""
    try:
        # PyJWT has these methods, python-jwt does not
        jwt.encode({}, "key", algorithm="HS256")
        jwt.decode("token", "key", algorithms=["HS256"], options={"verify_signature": False})
        return True
    except AttributeError:
        raise ImportError("Wrong JWT package detected. Install PyJWT: pip uninstall jwt && pip install PyJWT==2.8.0")
```

### Pydantic V2 Migration Strategy
**Issue**: Mixed V1/V2 syntax causing validation errors
**Solution**: Complete V2 compatibility layer

```python
# Updated models with V2 syntax
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore unknown fields
    )
    
    # Updated field definitions
    alpaca_api_key: str = Field(..., description="Alpaca API key")
    alpaca_secret_key: Optional[str] = Field(None, description="Alpaca secret key")

# Migration checklist:
# 1. Replace Config class with model_config
# 2. Update Field validators to v2 syntax
# 3. Replace schema_extra with model_config examples
# 4. Update custom validators to @field_validator decorator
```

### Clean Environment Setup
```bash
# Complete environment refresh script
#!/bin/bash
set -e

echo "Setting up clean opitios_alpaca environment..."

# Remove existing virtual environment
rm -rf venv/

# Create new Python 3.9+ virtual environment
python3.9 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Upgrade pip and setup tools
pip install --upgrade pip setuptools wheel

# Install fixed requirements
pip install -r requirements-fixed.txt

# Verify critical packages
python -c "import jwt; print(f'PyJWT version: {jwt.__version__}')"
python -c "import pydantic; print(f'Pydantic version: {pydantic.__version__}')"
python -c "from pydantic_settings import BaseSettings; print('Pydantic settings OK')"

echo "Environment setup complete!"
```

## Testing Framework Architecture

### Multi-Layer Testing Strategy
```mermaid
graph TD
    A[Unit Tests] --> B[Integration Tests]
    B --> C[Authentication Tests]
    C --> D[Multi-User Tests]
    D --> E[Load Tests]
    E --> F[End-to-End Tests]
    
    A --> A1[Model Validation]
    A --> A2[Utility Functions]
    A --> A3[Business Logic]
    
    B --> B1[Database Operations]
    B --> B2[Alpaca API Integration]
    B --> B3[Redis Operations]
    
    C --> C1[JWT Token Flow]
    C --> C2[Permission Checks]
    C --> C3[User Context]
    
    D --> D1[User Isolation]
    D --> D2[Concurrent Access]
    D --> D3[Rate Limiting]
    
    E --> E1[Stress Testing]
    E --> E2[Performance Benchmarks]
    
    F --> F1[Full User Journey]
    F --> F2[Error Scenarios]
```

### Test Framework Implementation
```python
# conftest.py - Pytest configuration
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import redis

from main import app
from app.user_manager import get_db, get_redis
from app.models import Base

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Test Redis setup
@pytest.fixture
def test_redis():
    return redis.Redis(host='localhost', port=6379, db=15, decode_responses=True)

# Database fixtures
@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

# Authentication fixtures
@pytest.fixture
def test_user():
    return {
        "user_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "alpaca_credentials": {
            "api_key": "test_api_key",
            "secret_key": "test_secret_key",
            "paper_trading": True
        },
        "permissions": ["trading", "market_data"]
    }

@pytest.fixture
def auth_token(test_user):
    from app.middleware import create_jwt_token
    return create_jwt_token(test_user)

@pytest.fixture
def authenticated_client(auth_token):
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client

# Mock Alpaca API
@pytest.fixture
def mock_alpaca_client():
    class MockAlpacaClient:
        def get_account(self):
            return {"buying_power": 10000, "cash": 5000}
        
        def submit_order(self, **kwargs):
            return {"id": "order-123", "status": "filled"}
    
    return MockAlpacaClient()
```

### Authentication Testing Patterns
```python
# test_auth.py - Authentication and authorization tests
import pytest
from fastapi import HTTPException

class TestAuthentication:
    
    def test_jwt_token_creation(self, test_user):
        """Test JWT token creation with user data"""
        from app.middleware import create_jwt_token, verify_jwt_token
        
        token = create_jwt_token(test_user)
        assert token is not None
        
        payload = verify_jwt_token(token)
        assert payload["user_id"] == test_user["user_id"]
        assert payload["permissions"] == test_user["permissions"]
    
    def test_expired_token_rejection(self):
        """Test that expired tokens are rejected"""
        from app.middleware import verify_jwt_token
        import jwt
        from datetime import datetime, timedelta
        
        # Create expired token
        expired_payload = {
            "user_id": "test-user",
            "exp": datetime.utcnow() - timedelta(hours=1)
        }
        expired_token = jwt.encode(expired_payload, "secret", algorithm="HS256")
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(expired_token)
        assert exc_info.value.status_code == 401
    
    def test_user_context_creation(self, test_user, db_session):
        """Test user context creation and credential encryption"""
        from app.middleware import user_manager
        
        context = user_manager.create_user_context(test_user)
        assert context.user_id == test_user["user_id"]
        assert context.has_permission("trading")
        
        # Test credential decryption
        credentials = context.get_alpaca_credentials()
        assert credentials["api_key"] == test_user["alpaca_credentials"]["api_key"]

class TestMultiUserIsolation:
    
    def test_user_data_isolation(self, db_session):
        """Test that users can only access their own data"""
        # Create two users with different credentials
        user1 = create_test_user("user1", "api_key_1")
        user2 = create_test_user("user2", "api_key_2")
        
        # Verify each user can only access their own data
        context1 = user_manager.get_user_context("user1")
        context2 = user_manager.get_user_context("user2")
        
        creds1 = context1.get_alpaca_credentials()
        creds2 = context2.get_alpaca_credentials()
        
        assert creds1["api_key"] != creds2["api_key"]
        assert creds1["api_key"] == "api_key_1"
        assert creds2["api_key"] == "api_key_2"
    
    def test_concurrent_user_access(self):
        """Test concurrent access by multiple users"""
        import threading
        import time
        
        results = []
        
        def user_request(user_id, iterations=10):
            for i in range(iterations):
                # Simulate API request
                context = user_manager.get_user_context(user_id)
                results.append(f"{user_id}_{i}")
                time.sleep(0.01)
        
        # Start multiple threads
        threads = []
        for user_id in ["user1", "user2", "user3"]:
            thread = threading.Thread(target=user_request, args=(user_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all requests completed
        assert len(results) == 30  # 3 users * 10 iterations
```

### API Integration Testing
```python
# test_trading.py - Trading functionality tests
class TestTradingAPI:
    
    def test_stock_quote_with_auth(self, authenticated_client, mock_alpaca_client):
        """Test authenticated stock quote request"""
        response = authenticated_client.get("/api/v1/stocks/AAPL/quote")
        assert response.status_code == 200
        
        data = response.json()
        assert "symbol" in data
        assert "last_price" in data
    
    def test_rate_limiting_enforcement(self, authenticated_client):
        """Test that rate limiting is enforced per user"""
        # Make rapid requests to trigger rate limit
        responses = []
        for i in range(65):  # Exceed 60 requests per minute limit
            response = authenticated_client.get("/api/v1/stocks/AAPL/quote")
            responses.append(response.status_code)
        
        # Should have some 429 responses
        assert 429 in responses
        
        # Verify rate limit headers
        last_response = authenticated_client.get("/api/v1/stocks/AAPL/quote")
        assert "X-RateLimit-Limit" in last_response.headers
        assert "X-RateLimit-Remaining" in last_response.headers
    
    def test_permission_based_access(self, db_session):
        """Test that different user roles have appropriate access"""
        # Create users with different permissions
        viewer_user = create_user_with_role("viewer", ["market_data"])
        trader_user = create_user_with_role("trader", ["market_data", "trading"])
        
        viewer_client = create_authenticated_client(viewer_user)
        trader_client = create_authenticated_client(trader_user)
        
        # Viewer can access market data
        response = viewer_client.get("/api/v1/stocks/AAPL/quote")
        assert response.status_code == 200
        
        # Viewer cannot place orders
        response = viewer_client.post("/api/v1/stocks/order", json={
            "symbol": "AAPL", "qty": 1, "side": "buy"
        })
        assert response.status_code == 403
        
        # Trader can place orders
        response = trader_client.post("/api/v1/stocks/order", json={
            "symbol": "AAPL", "qty": 1, "side": "buy"
        })
        assert response.status_code == 200
```

## Production Deployment Architecture

### Environment Configuration Management
```python
# Enhanced settings with production-ready configuration
class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=[".env.local", ".env.prod", ".env"],
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: str = Field(default="development", description="Deployment environment")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Security
    jwt_secret: str = Field(..., description="JWT signing secret")
    encryption_key: str = Field(..., description="Database encryption key")
    
    # Database
    database_url: str = Field(...., description="Database connection URL")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_max_overflow: int = Field(default=20, description="Database max overflow")
    
    # Redis
    redis_url: str = Field(..., description="Redis connection URL")
    redis_max_connections: int = Field(default=50, description="Redis connection pool size")
    
    # Alpaca API
    alpaca_api_timeout: int = Field(default=30, description="Alpaca API timeout seconds")
    alpaca_retry_attempts: int = Field(default=3, description="API retry attempts")
    
    # Rate Limiting
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    global_rate_limit: int = Field(default=1000, description="Global requests per minute")
    
    # Monitoring
    log_level: str = Field(default="INFO", description="Logging level")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    health_check_interval: int = Field(default=30, description="Health check interval")
    
    # Feature Flags
    enable_options_trading: bool = Field(default=True, description="Enable options trading")
    enable_paper_trading_only: bool = Field(default=False, description="Force paper trading")
    maintenance_mode: bool = Field(default=False, description="Maintenance mode")
```

### Health Check System
```python
# app/health.py - Comprehensive health checks
from typing import Dict, Any
import asyncio
import time
from datetime import datetime

class HealthChecker:
    def __init__(self):
        self.checks = {}
        self.last_check_time = None
        self.check_cache_ttl = 30  # Cache health results for 30 seconds
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        now = time.time()
        
        # Use cache if recent
        if (self.last_check_time and 
            now - self.last_check_time < self.check_cache_ttl):
            return self.checks
        
        # Run all health checks concurrently
        checks = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_alpaca_api(),
            self.check_memory_usage(),
            self.check_disk_space(),
            return_exceptions=True
        )
        
        # Compile results
        self.checks = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "checks": {
                "database": checks[0],
                "redis": checks[1],
                "alpaca_api": checks[2],
                "memory": checks[3],
                "disk": checks[4]
            }
        }
        
        # Determine overall status
        failed_checks = [
            name for name, result in self.checks["checks"].items()
            if isinstance(result, Exception) or 
               (isinstance(result, dict) and result.get("status") != "healthy")
        ]
        
        if failed_checks:
            self.checks["status"] = "degraded" if len(failed_checks) < 3 else "unhealthy"
            self.checks["failed_checks"] = failed_checks
        
        self.last_check_time = now
        return self.checks
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            async with get_db() as db:
                result = await db.execute("SELECT 1")
                await result.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "connection_pool": {
                    "active_connections": engine.pool.checkedout(),
                    "pool_size": engine.pool.size(),
                    "max_overflow": engine.pool._max_overflow
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_error_time": datetime.utcnow().isoformat()
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            start_time = time.time()
            
            # Test Redis operations
            await redis_client.ping()
            await redis_client.set("health_check", "ok", ex=60)
            value = await redis_client.get("health_check")
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "memory_usage": await redis_client.info("memory"),
                "connected_clients": await redis_client.info("clients")
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_alpaca_api(self) -> Dict[str, Any]:
        """Check Alpaca API connectivity"""
        try:
            start_time = time.time()
            
            # Test with a lightweight API call
            from app.connection_pool import connection_pool
            client = await connection_pool.get_client("health_check")
            account = await client.get_account()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "api_status": "connected",
                "paper_trading": getattr(account, 'pattern_day_trader', None) is not None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "api_status": "disconnected"
            }

# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with all system components"""
    health_checker = HealthChecker()
    return await health_checker.get_system_health()

@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe"""
    health_checker = HealthChecker()
    health = await health_checker.get_system_health()
    
    if health["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {"status": "ready"}

@app.get("/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
```

### Deployment Configuration
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  opitios-alpaca:
    build: .
    ports:
      - "8081:8081"
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
      - DATABASE_URL=mysql+aiomysql://user:pass@mysql:3306/trading
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
    depends_on:
      - mysql
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: trading
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    
volumes:
  mysql_data:
  redis_data:
```

### Kubernetes Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opitios-alpaca
  labels:
    app: opitios-alpaca
spec:
  replicas: 3
  selector:
    matchLabels:
      app: opitios-alpaca
  template:
    metadata:
      labels:
        app: opitios-alpaca
    spec:
      containers:
      - name: opitios-alpaca
        image: opitios-alpaca:latest
        ports:
        - containerPort: 8081
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: opitios-secrets
              key: database-url
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: opitios-secrets
              key: jwt-secret
        livenessProbe:
          httpGet:
            path: /live
            port: 8081
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8081
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: opitios-alpaca-service
spec:
  selector:
    app: opitios-alpaca
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8081
  type: LoadBalancer
```

## Monitoring & Observability

### Structured Logging Configuration
```python
# app/logging_config.py - Enhanced logging setup
import sys
import json
from pathlib import Path
from loguru import logger
from datetime import datetime

class LoggingConfig:
    def __init__(self):
        self.log_format = self._get_log_format()
        
    def _get_log_format(self):
        """Get structured log format for production"""
        if settings.environment == "production":
            return json.dumps({
                "timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}",
                "level": "{level}",
                "service": "opitios_alpaca",
                "module": "{module}",
                "function": "{function}",
                "line": "{line}",
                "message": "{message}",
                "extra": "{extra}"
            })
        else:
            return ("<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>")
    
    def setup_logging(self):
        """Configure comprehensive logging"""
        # Remove default handler
        logger.remove()
        
        # Console logging
        logger.add(
            sys.stdout,
            format=self._get_log_format(),
            level=settings.log_level,
            colorize=settings.environment != "production",
            serialize=settings.environment == "production"
        )
        
        # File logging with rotation
        log_path = Path("logs")
        log_path.mkdir(exist_ok=True)
        
        logger.add(
            log_path / "opitios_alpaca_{time:YYYY-MM-DD}.log",
            format=self._get_log_format(),
            level="INFO",
            rotation="1 day",
            retention="30 days",
            compression="gz",
            serialize=True
        )
        
        # Error file logging
        logger.add(
            log_path / "errors_{time:YYYY-MM-DD}.log",
            format=self._get_log_format(),
            level="ERROR",
            rotation="1 day",
            retention="90 days",
            compression="gz",
            serialize=True
        )
        
        # Trading activity logging
        logger.add(
            log_path / "trading_{time:YYYY-MM-DD}.log",
            format=self._get_log_format(),
            level="INFO",
            rotation="1 day",
            retention="365 days",  # Keep trading logs for 1 year
            compression="gz",
            serialize=True,
            filter=lambda record: "trading" in record["extra"]
        )

# Trading activity logging helper
def log_trading_activity(user_id: str, action: str, **kwargs):
    """Log trading activities with structured data"""
    logger.info(
        f"Trading activity: {action}",
        extra={
            "category": "trading",
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
    )

# Performance monitoring decorator
import functools
import time

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                f"Performance: {func.__name__} completed",
                extra={
                    "category": "performance",
                    "function": func.__name__,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "success"
                }
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Performance: {func.__name__} failed",
                extra={
                    "category": "performance",
                    "function": func.__name__,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "error",
                    "error": str(e)
                }
            )
            raise
    return wrapper
```

### Metrics Collection
```python
# app/metrics.py - Application metrics
from typing import Dict, Any
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

class MetricsCollector:
    def __init__(self):
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(lambda: deque(maxlen=1000))
        self.timeseries = defaultdict(lambda: deque(maxlen=100))
        
    def increment_counter(self, metric_name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        key = self._build_key(metric_name, tags)
        self.counters[key] += value
        
    def set_gauge(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric"""
        key = self._build_key(metric_name, tags)
        self.gauges[key] = value
        
    def record_histogram(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram value"""
        key = self._build_key(metric_name, tags)
        self.histograms[key].append(value)
        
    def record_timeseries(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a time series data point"""
        key = self._build_key(metric_name, tags)
        timestamp = datetime.utcnow()
        self.timeseries[key].append((timestamp, value))
        
    def _build_key(self, metric_name: str, tags: Dict[str, str] = None) -> str:
        """Build metric key with tags"""
        if not tags:
            return metric_name
        tag_string = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{metric_name}[{tag_string}]"
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                key: {
                    "count": len(values),
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "avg": sum(values) / len(values) if values else 0,
                    "p95": self._percentile(values, 0.95) if values else 0,
                    "p99": self._percentile(values, 0.99) if values else 0
                }
                for key, values in self.histograms.items()
            }
        }
        
    def _percentile(self, values: deque, percentile: float) -> float:
        """Calculate percentile from deque"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

# Global metrics instance
metrics = MetricsCollector()

# Metrics middleware
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()
        
        # Increment request counter
        metrics.increment_counter("http_requests_total", tags={
            "method": request.method,
            "endpoint": request.url.path
        })
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record response time
            duration = time.time() - start_time
            metrics.record_histogram("http_request_duration_seconds", duration, tags={
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": str(response.status_code)
            })
            
            # Increment response counter
            metrics.increment_counter("http_responses_total", tags={
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": str(response.status_code)
            })
            
            return response
            
        except Exception as e:
            # Record error
            duration = time.time() - start_time
            metrics.record_histogram("http_request_duration_seconds", duration, tags={
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": "500"
            })
            
            metrics.increment_counter("http_errors_total", tags={
                "method": request.method,
                "endpoint": request.url.path,
                "error_type": type(e).__name__
            })
            
            raise

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus-style metrics endpoint"""
    return metrics.get_metrics_summary()
```

## Architectural Decision Records (ADRs)

### ADR-001: JWT Package Selection
**Status**: Accepted
**Context**: Multiple JWT packages in Python ecosystem causing import conflicts
**Decision**: Use PyJWT 2.8.0 as the standard JWT library
**Consequences**:
- Positive: Well-maintained, secure, standard-compliant implementation
- Positive: Active community and regular security updates
- Negative: Must ensure no conflicting jwt packages are installed
**Alternatives Considered**: python-jose, authlib
**Implementation**: Clean virtual environment setup with explicit PyJWT dependency

### ADR-002: Pydantic V2 Migration
**Status**: Accepted
**Context**: Pydantic V2 provides better performance and type safety
**Decision**: Migrate to Pydantic V2 with full compatibility
**Consequences**:
- Positive: 20-50% performance improvement in validation
- Positive: Better TypeScript-like type annotations
- Negative: Breaking changes require code updates
**Migration Strategy**: Gradual migration with compatibility layer

### ADR-003: Multi-User Architecture
**Status**: Accepted
**Context**: Need to support multiple users with isolated trading accounts
**Decision**: Implement user context management with encrypted credential storage
**Consequences**:
- Positive: Complete user isolation and security
- Positive: Scalable to many concurrent users
- Negative: Increased complexity in connection management
**Security**: AES-256 encryption for credentials at rest

### ADR-004: Redis for Rate Limiting
**Status**: Accepted
**Context**: Need distributed rate limiting across multiple instances
**Decision**: Use Redis with sliding window algorithm, memory fallback
**Consequences**:
- Positive: Accurate rate limiting across instances
- Positive: High performance with Redis
- Negative: Additional infrastructure dependency
**Fallback**: Memory-based rate limiting when Redis unavailable

### ADR-005: Comprehensive Testing Strategy
**Status**: Accepted
**Context**: Current testing is insufficient for production deployment
**Decision**: Implement multi-layer testing with authentication focus
**Consequences**:
- Positive: High confidence in production deployments
- Positive: Better regression detection
- Negative: Increased development time for test creation
**Coverage Target**: 90% code coverage with focus on critical paths

## Migration Roadmap

## Phase 1: Foundation Fixes (Week 1)
- [ ] Fix JWT import conflicts
- [ ] Complete Pydantic V2 migration
- [ ] Update requirements.txt with fixed versions
- [ ] Implement clean environment setup scripts

## Phase 2: Testing Framework (Week 2)
- [ ] Implement comprehensive test framework
- [ ] Add authentication and multi-user tests
- [ ] Create mock Alpaca API for testing
- [ ] Achieve 80% test coverage

## Phase 3: Production Readiness (Week 3)
- [ ] Implement health check system
- [ ] Add comprehensive error handling
- [ ] Create monitoring and metrics collection
- [ ] Setup structured logging

## Phase 4: Deployment & Monitoring (Week 4)
- [ ] Create Docker and Kubernetes configurations
- [ ] Implement CI/CD pipeline
- [ ] Setup monitoring dashboards
- [ ] Load testing and performance optimization

## Success Metrics

### Technical Metrics
- 99.9% uptime target
- < 100ms average API response time
- 90%+ test coverage
- Zero critical security vulnerabilities
- < 1% error rate

### Business Metrics
- Support 100+ concurrent users
- Process 1000+ trades per day
- 24/7 operational availability
- Sub-second quote delivery
- Complete audit trail for compliance

This architecture provides a robust, scalable, and secure foundation for the opitios_alpaca trading system while addressing all identified issues and preparing for production deployment.