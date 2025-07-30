# 🚀 Quick Start Guide

## Step 1: Get Your Alpaca API Keys

1. Go to [Alpaca Markets Dashboard](https://app.alpaca.markets/)
2. Create an account or log in
3. Navigate to "API Keys" in the dashboard
4. Generate a new API key pair (key + secret)
5. Copy both the API Key and Secret Key

## Step 2: Configure Your API Keys

Update the `.env` file with your actual API keys:

```env
ALPACA_API_KEY=PKEIKZWFXA4BD1JMJAY3
ALPACA_SECRET_KEY=your_actual_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true
```

⚠️ **Important**: Replace `your_actual_secret_key_here` with your real Alpaca secret key.

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Test the Installation

```bash
python3 test_app.py
```

You should see:
- ✅ FastAPI endpoints working (200 status codes)
- ✅ Application structure functioning
- With valid API keys, you'll also see successful API calls

## Step 5: Start the Server

```bash
python3 main.py
```

Server will start at: http://localhost:8081

## Step 6: Explore the API

Visit http://localhost:8081/docs for interactive API documentation.

### Try These Endpoints:

1. **Health Check**: GET `/api/v1/health`
2. **Account Info**: GET `/api/v1/account`
3. **Stock Quote**: GET `/api/v1/stocks/AAPL/quote`
4. **Buy Stock**: POST `/api/v1/stocks/AAPL/buy?qty=1`

### Example Commands:

```bash
# Get account information
curl http://localhost:8081/api/v1/account

# Get AAPL stock quote
curl http://localhost:8081/api/v1/stocks/AAPL/quote

# Buy 1 share of AAPL at market price
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/buy?qty=1"

# Place a limit order
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{"symbol":"AAPL","qty":1,"side":"buy","type":"limit","limit_price":150.00}'
```

## ✅ You're Ready!

The Alpaca trading service is now fully functional with:
- ✅ Stock price retrieval
- ✅ Stock trading (buy/sell with market/limit orders)
- ✅ Portfolio management
- ✅ Real-time API endpoints
- ✅ Complete documentation
- ✅ Testing suite

For more details, see the full [README.md](README.md)