# 🚀 Quick Start Guide

Get your Opitios Alpaca Trading Service up and running in minutes with this comprehensive guide.

## Prerequisites

- Python 3.8 or higher
- Git (for cloning the repository)
- An Alpaca Markets account (free registration)

## Step 1: Get Your Alpaca API Keys

1. Go to [Alpaca Markets Dashboard](https://app.alpaca.markets/)
2. Create an account or log in
3. Navigate to "API Keys" in the dashboard
4. Generate a new API key pair (key + secret)
5. Copy both the API Key and Secret Key

> **💡 Tip**: Keep your API keys secure and never commit them to version control.

## Step 2: Clone and Setup the Project

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd opitios_alpaca

# Activate virtual environment (CRITICAL REQUIREMENT)
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

> **⚠️ CRITICAL**: Always use virtual environments for Python projects. This is mandatory per CLAUDE.md requirements.

## Step 3: Configure Your API Keys

Create or update the `.env` file with your actual API keys:

```env
ALPACA_API_KEY=PKEIKZWFXA4BD1JMJAY3
ALPACA_SECRET_KEY=your_actual_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true
HOST=0.0.0.0
PORT=8081
DEBUG=true
```

> **⚠️ Important**: Replace `your_actual_secret_key_here` with your real Alpaca secret key.

## Step 4: Validate Your Setup

Run the interactive setup validation script:

```bash
python docs/scripts/setup_validator.py
```

Or run the basic test suite:

```bash
python test_app.py
```

**Expected Output:**
- ✅ FastAPI endpoints working (200 status codes)
- ✅ Application structure functioning
- ✅ With valid API keys, successful API calls

## Step 5: Start the Server

```bash
# Start the development server
python main.py

# Alternative: Direct uvicorn command
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

**Server will start at**: http://localhost:8081

**Success Indicators:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Starting Opitios Alpaca Trading Service
INFO:     Paper trading mode: True
INFO:     Alpaca base URL: https://paper-api.alpaca.markets
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8081 (Press CTRL+C to quit)
```

## Step 6: Verify Installation

### Access the API Documentation
- **Interactive API Docs**: http://localhost:8081/docs
- **Alternative Docs**: http://localhost:8081/redoc
- **Service Info**: http://localhost:8081/

### Test Core Endpoints

1. **Health Check**:
   ```bash
   curl http://localhost:8081/api/v1/health
   ```
   
   Expected: `{"status": "healthy", "service": "Opitios Alpaca Trading Service"}`

2. **Account Information**:
   ```bash
   curl http://localhost:8081/api/v1/account
   ```
   
   Expected: Account details with buying power, cash, etc.

3. **Stock Quote**:
   ```bash
   curl http://localhost:8081/api/v1/stocks/AAPL/quote
   ```
   
   Expected: Real-time AAPL stock quote data

## Step 7: Test Trading (Paper Trading)

Try a simple paper trading transaction:

```bash
# Buy 1 share of AAPL at market price
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/buy?qty=1"

# Place a limit order
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 1,
       "side": "buy",
       "type": "limit",
       "limit_price": 150.00,
       "time_in_force": "day"
     }'
```

## ✅ Verification Checklist

After completing the setup, verify these items:

- [ ] **Environment**: Virtual environment activated
- [ ] **Dependencies**: All packages installed successfully
- [ ] **Configuration**: API keys configured in `.env`
- [ ] **Server**: Service starts without errors
- [ ] **API Docs**: Interactive documentation accessible
- [ ] **Health Check**: `/api/v1/health` returns success
- [ ] **Account Access**: `/api/v1/account` returns account data
- [ ] **Market Data**: Stock quotes working
- [ ] **Trading**: Paper trading orders execute successfully

## 🎯 Success! You're Ready to Trade

Your Opitios Alpaca trading service is now fully functional with:

- ✅ **Stock Trading**: Buy/sell stocks with market, limit, and stop orders
- ✅ **Market Data**: Real-time quotes and historical price bars
- ✅ **Portfolio Management**: Account info, positions, and order management
- ✅ **Paper Trading**: Safe testing environment
- ✅ **API Documentation**: Complete endpoint documentation
- ✅ **Testing Suite**: Comprehensive test coverage

## Next Steps

1. **Explore API**: Visit http://localhost:8081/docs for full API reference
2. **Review Examples**: Check [API Examples](api-examples.md) for detailed usage
3. **Production Setup**: See [Architecture](architecture.md) for production deployment
4. **Troubleshooting**: If issues arise, see [Troubleshooting Guide](troubleshooting.md)

## Need Help?

- **Setup Issues**: Run `python docs/scripts/setup_validator.py`
- **API Problems**: Check [API Examples](api-examples.md)
- **Error Resolution**: See [Troubleshooting Guide](troubleshooting.md)
- **Configuration**: Use `python docs/scripts/config_helper.py`

---

**Setup Time**: ~5-10 minutes  
**Difficulty**: Beginner-friendly  
**Next**: [API Examples](api-examples.md)