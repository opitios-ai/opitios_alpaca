# 📈 Complete API Examples

This document provides comprehensive examples for all API endpoints with real-world usage scenarios and detailed explanations.

## 🔗 Base URL
```
http://localhost:8081
```

## 📋 Table of Contents
1. [Health & Connection](#health--connection)
2. [Account Management](#account-management)
3. [Single Stock Quotes](#single-stock-quotes)
4. [Batch Stock Quotes](#batch-stock-quotes)
5. [Stock Historical Data](#stock-historical-data)
6. [Options Chain](#options-chain)
7. [Single Option Quote](#single-option-quote)
8. [Batch Option Quotes](#batch-option-quotes)
9. [Stock Trading](#stock-trading)
10. [Order Management](#order-management)
11. [Portfolio Management](#portfolio-management)
12. [Error Handling](#error-handling)
13. [Complete Workflow](#complete-workflow)

---

## Health & Connection

### Health Check
Monitor service status and ensure the API is responsive.

```bash
curl -X GET "http://localhost:8081/api/v1/health"
```

**Response:**
```json
{
  "status": "healthy",
  "service": "Opitios Alpaca Trading Service"
}
```

### Test API Connection
Verify Alpaca API connectivity and account access.

```bash
curl -X GET "http://localhost:8081/api/v1/test-connection"
```

**Response:**
```json
{
  "status": "connected",
  "account_number": "PA33OLW2BBG7",
  "buying_power": 200000.0,
  "cash": 100000.0,
  "portfolio_value": 100000.0
}
```

**Use Case**: Check this endpoint before starting trading operations to ensure API connectivity.

---

## Account Management

### Get Account Information
Retrieve comprehensive account details including buying power, cash, and portfolio value.

```bash
curl -X GET "http://localhost:8081/api/v1/account"
```

**Response:**
```json
{
  "account_number": "PA33OLW2BBG7",
  "buying_power": 200000.0,
  "cash": 100000.0,
  "portfolio_value": 100000.0,
  "equity": 100000.0,
  "last_equity": 100000.0,
  "multiplier": 2,
  "pattern_day_trader": false
}
```

**Key Fields Explained:**
- `buying_power`: Maximum amount available for purchases (includes margin)
- `cash`: Actual cash available
- `portfolio_value`: Total value of account (cash + positions)
- `equity`: Current equity value
- `multiplier`: Margin multiplier (2 = 2:1 margin)
- `pattern_day_trader`: Day trading status

### Get Positions
View all current stock positions with profit/loss information.

```bash
curl -X GET "http://localhost:8081/api/v1/positions"
```

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "qty": 10.0,
    "side": "long",
    "market_value": 2125.0,
    "cost_basis": 2100.0,
    "unrealized_pl": 25.0,
    "unrealized_plpc": 0.0119,
    "avg_entry_price": 210.0
  }
]
```

**Use Case**: Monitor portfolio performance and position sizing before making new trades.

---

## Single Stock Quotes

### Get Quote by Symbol (GET)
Retrieve real-time quote for a specific stock symbol.

```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/quote"
```

### Get Quote by Request Body (POST)
Alternative method using POST request with symbol in body.

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quote" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "AAPL"}'
```

**Response:**
```json
{
  "symbol": "AAPL",
  "bid_price": 210.1,
  "ask_price": 214.3,
  "bid_size": 100,
  "ask_size": 200,
  "timestamp": "2024-01-15T15:30:00.961420+00:00"
}
```

**Quote Fields Explained:**
- `bid_price`: Highest price buyers are willing to pay
- `ask_price`: Lowest price sellers are willing to accept
- `bid_size`: Number of shares at bid price
- `ask_size`: Number of shares at ask price
- `timestamp`: Quote timestamp in UTC

**Use Case**: Get current market price before placing orders or analyzing market conditions.

---

## Batch Stock Quotes

### Get Multiple Stock Quotes
Efficiently retrieve quotes for multiple symbols in a single request.

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
     }'
```

**Response:**
```json
{
  "quotes": [
    {
      "symbol": "AAPL",
      "bid_price": 210.1,
      "ask_price": 214.3,
      "bid_size": 100,
      "ask_size": 200,
      "timestamp": "2024-01-15T15:30:00Z"
    },
    {
      "symbol": "TSLA",
      "bid_price": 185.5,
      "ask_price": 187.2,
      "bid_size": 150,
      "ask_size": 300,
      "timestamp": "2024-01-15T15:30:00Z"
    }
  ],
  "count": 2,
  "requested_symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
}
```

**Limitations**: Maximum 20 symbols per request to maintain performance.

**Use Case**: Portfolio monitoring, watchlist updates, or market scanning.

---

## Stock Historical Data

### Get Historical Bars
Retrieve historical price data for technical analysis.

```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=5"
```

**Parameters:**
- `timeframe`: 1Min, 5Min, 15Min, 1Hour, 1Day
- `limit`: Number of bars to retrieve (max 1000)
- `start`: Start date (optional, format: YYYY-MM-DD)
- `end`: End date (optional, format: YYYY-MM-DD)

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1Day",
  "bars": [
    {
      "timestamp": "2024-01-12T00:00:00Z",
      "open": 208.5,
      "high": 212.3,
      "low": 207.8,
      "close": 211.2,
      "volume": 45678900
    },
    {
      "timestamp": "2024-01-11T00:00:00Z", 
      "open": 205.1,
      "high": 209.4,
      "low": 204.6,
      "close": 208.7,
      "volume": 52341200
    }
  ]
}
```

**Use Case**: Technical analysis, backtesting strategies, chart generation.

---

## Options Chain

### Get Options Chain for Underlying Stock
Retrieve all available options contracts for a specific stock and expiration date.

```bash
curl -X POST "http://localhost:8081/api/v1/options/chain" \
     -H "Content-Type: application/json" \
     -d '{
       "underlying_symbol": "AAPL",
       "expiration_date": "2024-02-16"
     }'
```

### Alternative GET Method
```bash
curl -X GET "http://localhost:8081/api/v1/options/AAPL/chain?expiration_date=2024-02-16"
```

**Response:**
```json
{
  "underlying_symbol": "AAPL",
  "underlying_price": 212.5,
  "expiration_dates": ["2024-02-16"],
  "options_count": 42,
  "options": [
    {
      "symbol": "AAPL240216C00190000",
      "underlying_symbol": "AAPL",
      "strike_price": 190.0,
      "expiration_date": "2024-02-16",
      "option_type": "call",
      "bid_price": 24.25,
      "ask_price": 24.75,
      "last_price": 24.50,
      "implied_volatility": 0.25,
      "delta": 0.85,
      "in_the_money": true
    }
  ],
  "note": "Sample options data - in production, this would use real market data"
}
```

**Option Symbol Format**: `AAPL240216C00190000`
- `AAPL`: Underlying symbol
- `240216`: Expiration date (YYMMDD)
- `C`: Option type (C=Call, P=Put)
- `00190000`: Strike price ($190.00)

**Use Case**: Options strategy analysis, finding optimal strike prices and expiration dates.

---

## Single Option Quote

### Get Option Quote
Retrieve detailed pricing and Greeks for a specific option contract.

```bash
curl -X POST "http://localhost:8081/api/v1/options/quote" \
     -H "Content-Type: application/json" \
     -d '{"option_symbol": "AAPL240216C00190000"}'
```

**Response:**
```json
{
  "symbol": "AAPL240216C00190000",
  "underlying_symbol": "AAPL",
  "underlying_price": 212.5,
  "strike_price": 190.0,
  "expiration_date": "2024-02-16",
  "option_type": "call",
  "bid_price": 24.25,
  "ask_price": 24.75,
  "last_price": 24.50,
  "implied_volatility": 0.25,
  "delta": 0.85,
  "gamma": 0.05,
  "theta": -0.02,
  "vega": 0.1,
  "in_the_money": true,
  "intrinsic_value": 22.5,
  "time_value": 2.0,
  "timestamp": "2024-01-15T15:30:00Z"
}
```

**Greeks Explained:**
- `delta`: Price sensitivity to underlying stock movement
- `gamma`: Delta sensitivity to underlying stock movement
- `theta`: Time decay (daily premium loss)
- `vega`: Volatility sensitivity

**Use Case**: Options pricing analysis, risk assessment, strategy evaluation.

---

## Stock Trading

### Market Order - Buy
Execute immediate purchase at current market price.

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "buy",
       "type": "market",
       "time_in_force": "day"
     }'
```

### Limit Order - Sell  
Sell shares only at specified price or better.

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 5,
       "side": "sell",
       "type": "limit",
       "limit_price": 215.50,
       "time_in_force": "gtc"
     }'
```

### Stop Loss Order
Trigger market sell when price drops to stop level.

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "sell",
       "type": "stop",
       "stop_price": 200.00,
       "time_in_force": "day"
     }'
```

**Order Response:**
```json
{
  "id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa",
  "symbol": "AAPL", 
  "qty": 10.0,
  "side": "buy",
  "order_type": "market",
  "status": "pending_new",
  "filled_qty": 0.0,
  "filled_avg_price": null,
  "submitted_at": "2024-01-15T15:30:13.903790+00:00",
  "filled_at": null
}
```

### Quick Trading Endpoints

#### Quick Buy (Simplified)
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/buy?qty=10"
```

#### Quick Sell (Simplified)
```bash 
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/sell?qty=5&order_type=limit&limit_price=215.50"
```

**Order Types Explained:**
- `market`: Execute immediately at current price
- `limit`: Execute only at specified price or better
- `stop`: Trigger market order when stop price reached
- `stop_limit`: Trigger limit order when stop price reached

**Time in Force Options:**
- `day`: Valid for current trading day only
- `gtc`: Good Till Cancelled (remains active until filled or cancelled)
- `ioc`: Immediate or Cancel (fill immediately or cancel)
- `fok`: Fill or Kill (fill completely or cancel)

---

## Order Management

### Get All Orders
Retrieve order history with optional filtering.

```bash
# Get recent orders
curl -X GET "http://localhost:8081/api/v1/orders?limit=10"

# Get orders by status
curl -X GET "http://localhost:8081/api/v1/orders?status=filled&limit=5"

# Get orders for specific symbol
curl -X GET "http://localhost:8081/api/v1/orders?symbol=AAPL&limit=5"
```

**Response:**
```json
[
  {
    "id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa",
    "symbol": "AAPL",
    "qty": 10.0,
    "side": "buy",
    "order_type": "market",
    "status": "filled",
    "filled_qty": 10.0,
    "filled_avg_price": 212.15,
    "submitted_at": "2024-01-15T15:30:13.903790+00:00",
    "filled_at": "2024-01-15T15:30:14.125000+00:00",
    "limit_price": null,
    "stop_price": null
  }
]
```

### Cancel Order
Cancel a pending order by order ID.

```bash
curl -X DELETE "http://localhost:8081/api/v1/orders/1b7d6894-7040-4284-b7a4-2f900e30b6aa"
```

**Response:**
```json
{
  "status": "cancelled",
  "order_id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa"
}
```

**Order Statuses:**
- `pending_new`: Order submitted, awaiting acceptance
- `accepted`: Order accepted by exchange
- `filled`: Order completely filled
- `partially_filled`: Order partially filled
- `cancelled`: Order cancelled
- `rejected`: Order rejected by exchange

---

## Error Handling

### Invalid Symbol
```bash
curl -X GET "http://localhost:8081/api/v1/stocks/INVALID/quote"
```

**Response:**
```json
{
  "detail": "No quote data found for INVALID"
}
```

### Too Many Symbols in Batch Request
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "META", "NFLX", "NVDA", "AMD", "INTC", "ORCL", "CRM", "ADBE", "PYPL", "UBER", "LYFT", "SPOT", "SQ", "ROKU", "ZM", "TWTR"]
     }'
```

**Response:**
```json
{
  "detail": "Maximum 20 symbols allowed per request"
}
```

### Insufficient Buying Power
```bash
# Try to buy $1M worth of stock with insufficient funds
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 5000,
       "side": "buy",
       "type": "market"
     }'
```

**Response:**
```json
{
  "detail": "Insufficient buying power for this order"
}
```

---

## Complete Workflow

### 1. Pre-Trading Setup
```bash
# Check service health
curl -X GET "http://localhost:8081/api/v1/health"

# Verify API connection
curl -X GET "http://localhost:8081/api/v1/test-connection"

# Check account status
curl -X GET "http://localhost:8081/api/v1/account"
```

### 2. Market Research
```bash
# Get current quotes for watchlist
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{"symbols": ["AAPL", "TSLA", "GOOGL"]}'

# Get historical data for technical analysis
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=10"
```

### 3. Options Analysis (if applicable)
```bash
# Get options chain
curl -X POST "http://localhost:8081/api/v1/options/chain" \
     -H "Content-Type: application/json" \
     -d '{"underlying_symbol": "AAPL"}'

# Get specific option quote
curl -X POST "http://localhost:8081/api/v1/options/quote" \
     -H "Content-Type: application/json" \
     -d '{"option_symbol": "AAPL240216C00190000"}'
```

### 4. Place Orders
```bash
# Place strategic buy order
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "buy",
       "type": "limit",
       "limit_price": 210.00,
       "time_in_force": "day"
     }'

# Set stop loss
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "sell",
       "type": "stop",
       "stop_price": 200.00,
       "time_in_force": "gtc"
     }'
```

### 5. Monitor and Manage
```bash
# Check order status
curl -X GET "http://localhost:8081/api/v1/orders?limit=5"

# Monitor positions
curl -X GET "http://localhost:8081/api/v1/positions"

# Cancel order if needed
curl -X DELETE "http://localhost:8081/api/v1/orders/{order_id}"
```

---

## 🎯 Ready to Trade!

This comprehensive API provides:

- ✅ **Real-time Market Data**: Single and batch stock quotes
- ✅ **Historical Data**: Price bars for technical analysis
- ✅ **Options Trading**: Complete options chain and pricing
- ✅ **Order Management**: All major order types with full lifecycle management
- ✅ **Portfolio Tracking**: Real-time positions and P&L
- ✅ **Account Management**: Complete account information and monitoring

**Next Steps:**
1. **Production Setup**: Configure for live trading (update base URL and disable paper trading)
2. **Risk Management**: Implement position sizing and stop-loss strategies
3. **Automation**: Build automated trading strategies using these endpoints
4. **Monitoring**: Set up alerts and monitoring for your trading operations

**Interactive Documentation**: Visit http://localhost:8081/docs for the complete interactive API reference with request/response testing capabilities.

---

**API Version**: 1.0.0  
**Last Updated**: January 2025  
**Next**: [Troubleshooting Guide](troubleshooting.md)