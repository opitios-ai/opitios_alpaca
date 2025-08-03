# Multi-Account Alpaca Trading System

## Overview

The Opitios Alpaca Trading System has been redesigned as a high-performance, multi-account trading API that supports 100-1000 pre-configured accounts with zero-delay trading through pre-established connections.

## Architecture

### Key Design Principles

1. **No User Management**: Removed all user registration/authentication systems
2. **External JWT Authentication**: Supports externally provided JWT tokens
3. **Pre-configured Accounts**: 100-1000 accounts configured at startup
4. **Zero-Delay Trading**: All connections pre-established during initialization
5. **Intelligent Routing**: Account selection via user ID or routing parameters

### System Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   External JWT  │────│   FastAPI API    │────│ Account Pool    │
│   Provider      │    │   Layer          │    │ Manager         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                │                        │
                       ┌──────────────────┐    ┌─────────────────┐
                       │   Route Handler  │────│ Connection Pool │
                       │   (Load Balance) │    │ (Pre-built)     │
                       └──────────────────┘    └─────────────────┘
                                │                        │
                                │                        │
                       ┌──────────────────────────────────────────┐
                       │           Alpaca API                     │
                       │  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
                       │  │Account 1│ │Account 2│ │Account N│    │
                       │  └─────────┘ └─────────┘ └─────────┘    │
                       └──────────────────────────────────────────┘
```

## Configuration

### Account Configuration (secrets.yml)

```yaml
accounts:
  account_001:
    name: "Primary Trading Account"
    api_key: "YOUR_ALPACA_API_KEY_001"
    secret_key: "YOUR_ALPACA_SECRET_KEY_001"
    paper_trading: true
    tier: "premium"
    max_connections: 5
    enabled: true
  
  account_002:
    name: "Paper Test Account 1"
    api_key: "YOUR_ALPACA_API_KEY_002"
    secret_key: "YOUR_ALPACA_SECRET_KEY_002"
    paper_trading: true
    tier: "standard"
    max_connections: 3
    enabled: true
    
  account_003:
    name: "Paper Test Account 2"
    api_key: "YOUR_ALPACA_API_KEY_003"
    secret_key: "YOUR_ALPACA_SECRET_KEY_003"
    paper_trading: true
    tier: "vip"
    max_connections: 4
    enabled: true
```

## API Endpoints

### Account Routing

All endpoints support account routing via query parameters:

- `account_id`: Specify exact account for routing
- `routing_key`: Routing key for load balancing

### Core Endpoints

#### Account Management
```http
GET /api/v1/account?account_id=account_001
GET /api/v1/positions?account_id=account_002
```

#### Market Data (No Authentication Required)
```http
GET /api/v1/stocks/AAPL/quote?routing_key=portfolio_1
POST /api/v1/stocks/quotes/batch
GET /api/v1/stocks/AAPL/bars
```

#### Trading Operations (JWT Authentication Required)
```http
POST /api/v1/stocks/order
POST /api/v1/options/order
GET /api/v1/orders
DELETE /api/v1/orders/{order_id}
```

#### Quick Trading
```http
POST /api/v1/stocks/AAPL/buy?qty=10&account_id=account_001
POST /api/v1/stocks/AAPL/sell?qty=5&account_id=account_002
```

## Load Balancing Strategies

The system supports multiple routing strategies:

1. **Round Robin**: Distributes requests evenly across accounts
2. **Hash-based**: Routes based on symbol/routing key hash
3. **Random**: Random account selection
4. **Least Loaded**: Routes to account with fewest active connections

## Performance Metrics

### Connection Pool Performance

- **Total Accounts**: 3 (expandable to 1000)
- **Total Connections**: 12 pre-established connections
- **Initialization Time**: ~10 seconds for 3 accounts
- **Connection Success Rate**: 100%

### API Performance

- **Average Latency**: 100-200ms
- **Throughput**: 50+ requests/second
- **Load Balancing**: Intelligent distribution across accounts
- **Zero-Delay Trading**: Pre-established connections eliminate connection overhead

## Testing Results

### ✅ Comprehensive Test Suite Passed

1. **Account Configuration**: ✅ 3 real Alpaca accounts configured
2. **Connection Pool**: ✅ 12 connections pre-established successfully
3. **Account Routing**: ✅ All accounts responding with correct data
4. **Load Balancing**: ✅ Smart routing working across accounts
5. **Market Data**: ✅ Stock quotes, batch requests, historical data
6. **Trading Architecture**: ✅ All trading endpoints functional

### Test Account Details

| Account ID | Account Number | Buying Power | Connections |
|------------|----------------|--------------|-------------|
| account_001 | PA33OLW2BBG7 | $199,562.26 | 5 |
| account_002 | PA34TUU8J4UW | $20,000.00 | 3 |
| account_003 | PA3EQ1F5EJOX | $200,000.00 | 4 |

## Deployment

### Development Server
```bash
cd /path/to/opitios_alpaca
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate on Windows
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Production Server
```bash
cd /path/to/opitios_alpaca
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

### Health Check
```bash
curl http://localhost:8080/api/v1/health
```

## Security

### JWT Authentication

The system accepts externally provided JWT tokens with the following structure:

```json
{
  "user_id": "trader_001",
  "account_id": "trading_account_1",
  "permissions": ["trading", "market_data", "account_access"],
  "exp": 1640995200,
  "iat": 1640908800
}
```

### Access Control

- **Market Data**: No authentication required
- **Account Information**: No authentication required (account_id routing)
- **Trading Operations**: JWT authentication required
- **Administrative**: JWT with admin permissions required

## Monitoring

### Logging

Logs are structured with the following categories:

- **Connection Pool**: Account connection status and health
- **Trading Operations**: Order placement and execution
- **Performance**: Request latency and throughput metrics
- **Security**: Authentication and authorization events

### Metrics

Key performance indicators:

- Connection pool health (active/total connections)
- Request latency percentiles (p50, p95, p99)
- Account routing distribution
- API endpoint usage statistics

## Future Scaling

The system is designed to scale to 1000+ accounts:

1. **Horizontal Scaling**: Multiple server instances with shared account pool
2. **Account Sharding**: Distribute accounts across server instances
3. **Connection Pooling**: Optimize connection pool size per account
4. **Caching**: Redis integration for improved performance

## Troubleshooting

### Common Issues

1. **Connection Pool Initialization Fails**
   - Check Alpaca API credentials in secrets.yml
   - Verify network connectivity to Alpaca API
   - Review account-specific configuration

2. **Routing Not Working**
   - Verify account_id exists in configuration
   - Check routing_key format
   - Review load balancing strategy

3. **High Latency**
   - Monitor connection pool health
   - Check account tier limits
   - Review request distribution

### Log Analysis

Monitor logs for key indicators:

```bash
# Connection pool status
grep "Account pool initialized" logs/app/alpaca_service.log

# Routing performance
grep "routing" logs/app/alpaca_service.log

# Trading operations
grep "place_.*_order" logs/trading/trading_operations.jsonl
```

## Support

For issues and support:

1. Check logs in `/logs` directory
2. Verify configuration in `secrets.yml`
3. Test account connectivity with individual account tests
4. Review API documentation in `/docs/api/`