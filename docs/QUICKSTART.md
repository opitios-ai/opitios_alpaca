# 🚀 Quick Start Guide - Multi-Account Trading System

Welcome to the Opitios Alpaca Multi-Account Trading System! This guide will help you get started quickly with the redesigned zero-delay, multi-account architecture.

## 📋 Prerequisites

- Python 3.9+
- Virtual environment (venv) - **CRITICAL REQUIREMENT**
- 1-3 Alpaca Paper Trading accounts (free)
- Redis Server (optional, for distributed rate limiting)

## Step 1: Get Your Alpaca API Keys

1. Go to [Alpaca Markets Dashboard](https://app.alpaca.markets/)
2. Create account(s) or log in
3. Navigate to "API Keys" in the dashboard
4. Generate API key pairs for each account you want to use
5. Copy both the API Key and Secret Key for each account

**Recommended**: Set up 1-3 separate Alpaca accounts for better load distribution.

## Step 2: Configure Your Accounts

**IMPORTANT**: This system uses `secrets.yml` (NOT `.env` files) for configuration.

Create/update your `secrets.yml` file based on `secrets.example.yml`:

```yaml
# Multi-Account Configuration
accounts:
  account_001:
    name: "Primary Trading Account"
    api_key: "YOUR_FIRST_API_KEY"
    secret_key: "YOUR_FIRST_SECRET_KEY"
    paper_trading: true
    tier: "premium"
    max_connections: 5
    enabled: true
  
  account_002:
    name: "Secondary Trading Account"  
    api_key: "YOUR_SECOND_API_KEY"
    secret_key: "YOUR_SECOND_SECRET_KEY"
    paper_trading: true
    tier: "standard"
    max_connections: 3
    enabled: true
    
  account_003:
    name: "Backup Trading Account"
    api_key: "YOUR_THIRD_API_KEY" 
    secret_key: "YOUR_THIRD_SECRET_KEY"
    paper_trading: true
    tier: "vip"
    max_connections: 4
    enabled: true

# JWT Configuration (for trading operations)
jwt:
  secret: "your-jwt-secret-key-here"
  algorithm: "HS256"
  expiration_hours: 24

# Trading Configuration
trading:
  real_data_only: true
  enable_mock_data: false
  strict_error_handling: true
  max_option_symbols_per_request: 20
```

⚠️ **Security**: Replace ALL placeholder API keys with your real Alpaca credentials.

## Step 3: Setup Virtual Environment

**CRITICAL**: Always use virtual environment - this is mandatory!

```bash
# Navigate to project directory
cd opitios_alpaca

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Verify venv is active (you should see (venv) in prompt)
```

## Step 4: Install Dependencies

```bash
# Make sure venv is activated first!
pip install -r requirements.txt
```

## Step 5: Test Account Configuration

Test your account configuration with our validation script:

```bash
# Make sure venv is activated!
python test_accounts.py
```

You should see:
```
=== Testing Individual Account Functionality ===
--- Testing account_001 ---
  Connection test: connected
  Account Number: PA33OLW2BBG7
  Buying Power: $199,562.26
  Portfolio Value: $99,983.51
  [SUCCESS] account_001 test completed successfully
```

## Step 6: Start the Multi-Account Server

```bash
# Development mode with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Or use the startup script
python start_server.py
```

Server will start at: http://localhost:8080

You should see:
```
Account pool initialized: 3 accounts, 12 connections
- account_001: 5/5 connections established
- account_002: 3/3 connections established  
- account_003: 4/4 connections established
```

## Step 7: Explore the Multi-Account API

Visit http://localhost:8080/docs for interactive API documentation.

### Core Features Test:

#### 1. Health Check
```bash
curl http://localhost:8080/api/v1/health
```

#### 2. Account Routing (No Authentication)
```bash
# Test specific account routing
curl "http://localhost:8080/api/v1/account?account_id=account_001"
curl "http://localhost:8080/api/v1/account?account_id=account_002"
curl "http://localhost:8080/api/v1/account?account_id=account_003"
```

#### 3. Load Balanced Market Data
```bash
# Stock quotes with load balancing
curl "http://localhost:8080/api/v1/stocks/AAPL/quote"
curl "http://localhost:8080/api/v1/stocks/AAPL/quote?routing_key=portfolio_1"

# Batch quotes
curl -X POST "http://localhost:8080/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{"symbols": ["AAPL", "GOOGL", "TSLA"]}'
```

#### 4. Trading Operations (JWT Authentication Required)

First, generate a test JWT token:
```bash
python -c "
from app.middleware import create_jwt_token
token = create_jwt_token({'user_id': 'trader', 'permissions': ['trading']})
print(token)
"
```

Then use the token for trading:
```bash
# Place order with account routing
curl -X POST "http://localhost:8080/api/v1/stocks/order?account_id=account_001" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 1,
       "side": "buy",
       "type": "market",
       "time_in_force": "day"
     }'

# Quick trading endpoints
curl -X POST "http://localhost:8080/api/v1/stocks/AAPL/buy?qty=1&account_id=account_002" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Step 8: Run Comprehensive Tests

Test the entire system:

```bash
# Make sure venv is activated!
python test_trading_simple.py
```

## ✅ You're Ready!

The Multi-Account Alpaca Trading System is now fully operational with:

### 🎯 Zero-Delay Architecture
- ✅ Pre-established connections to all accounts
- ✅ No connection overhead for trading operations
- ✅ Consistent <200ms response times

### 🔄 Intelligent Load Balancing  
- ✅ Account routing via `account_id` parameter
- ✅ Load balancing via `routing_key` parameter
- ✅ Multiple routing strategies (round-robin, hash-based, random)

### 🚀 High Performance Features
- ✅ 50+ requests/second throughput
- ✅ Concurrent multi-account operations
- ✅ Real-time market data streaming
- ✅ Scalable to 100-1000 accounts

### 🔐 External Authentication Ready
- ✅ JWT token validation (no user management)
- ✅ Permission-based access control
- ✅ Ready for external identity providers

## 📊 Performance Monitoring

Monitor your system performance:

```bash
# Check connection pool status
curl http://localhost:8080/api/v1/health

# Monitor logs
tail -f logs/app/alpaca_service.log

# Check account routing distribution
grep "routing" logs/app/alpaca_service.log
```

## 🔧 Troubleshooting

### Common Issues:

1. **Import Errors**: Make sure virtual environment is activated
2. **Connection Failures**: Verify API keys in secrets.yml
3. **Authentication Errors**: Check JWT token format and permissions
4. **Routing Issues**: Verify account_id exists in configuration

### Getting Help:

1. Check [docs/multi-account-system.md](multi-account-system.md) for detailed architecture
2. Review [docs/test-results.md](test-results.md) for validation examples
3. See [docs/api/api-spec.md](api/api-spec.md) for complete API reference

## 🚀 Next Steps

1. **Scale Up**: Add more accounts to your secrets.yml configuration
2. **Integrate**: Connect your external JWT authentication system
3. **Monitor**: Set up production monitoring and alerting
4. **Optimize**: Tune connection pool sizes based on your load

For complete documentation, see the [docs/](../docs/) folder with detailed guides on architecture, deployment, and advanced features.

---

**Remember**: Always use virtual environments (`venv`) and never commit `secrets.yml` to version control!