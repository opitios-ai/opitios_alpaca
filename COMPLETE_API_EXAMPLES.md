# 📈 Alpaca Trading API - Complete Usage Examples

This document provides comprehensive examples for all API endpoints with real-world usage scenarios.

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

---

## Health & Connection

### Health Check
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

---

## Account Management

### Get Account Information
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

### Get Positions
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

---

## Single Stock Quotes

### Get Quote by Symbol (GET)
```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/quote"
```

### Get Quote by Request Body (POST)
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

---

## Batch Stock Quotes

### Get Multiple Stock Quotes
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
    },
    {
      "symbol": "GOOGL",
      "bid_price": 142.8,
      "ask_price": 143.2,
      "bid_size": 100,
      "ask_size": 100,
      "timestamp": "2024-01-15T15:30:00Z"
    }
  ],
  "count": 3,
  "requested_symbols": ["AAPL", "TSLA", "GOOGL"]
}
```

---

## Stock Historical Data

### Get Historical Bars
```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=5"
```

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

---

## Options Chain

### Get Options Chain for Underlying Stock
```bash
curl -X POST "http://localhost:8081/api/v1/options/chain" \
     -H "Content-Type: application/json" \
     -d '{
       "underlying_symbol": "AAPL",
       "expiration_date": "2024-02-16"
     }'
```

### Get Options Chain by URL
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
    },
    {
      "symbol": "AAPL240216P00230000",
      "underlying_symbol": "AAPL", 
      "strike_price": 230.0,
      "expiration_date": "2024-02-16",
      "option_type": "put",
      "bid_price": 19.10,
      "ask_price": 19.60,
      "last_price": 19.35,
      "implied_volatility": 0.25,
      "delta": -0.75,
      "in_the_money": true
    }
  ],
  "note": "Sample options data - in production, this would use real market data"
}
```

---

## Single Option Quote

### Understanding Option Symbol Format
**Format:** `AAPL240216C00190000`
- `AAPL`: Underlying stock symbol
- `240216`: Expiration date (YYMMDD) - Feb 16, 2024
- `C`: Option type (C=Call, P=Put)
- `00190000`: Strike price ($190.00)

### Get Option Quote
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

---

## Batch Option Quotes

### Get Multiple Option Quotes
```bash
curl -X POST "http://localhost:8081/api/v1/options/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "option_symbols": [
         "AAPL240216C00190000",
         "AAPL240216P00180000",
         "TSLA240216C00200000"
       ]
     }'
```

**Response:**
```json
{
  "quotes": [
    {
      "symbol": "AAPL240216C00190000",
      "underlying_symbol": "AAPL",
      "strike_price": 190.0,
      "option_type": "call",
      "bid_price": 24.25,
      "ask_price": 24.75,
      "delta": 0.85,
      "in_the_money": true
    },
    {
      "symbol": "AAPL240216P00180000",
      "underlying_symbol": "AAPL",
      "strike_price": 180.0,
      "option_type": "put", 
      "bid_price": 2.10,
      "ask_price": 2.35,
      "delta": -0.15,
      "in_the_money": false
    },
    {
      "symbol": "TSLA240216C00200000",
      "underlying_symbol": "TSLA",
      "strike_price": 200.0,
      "option_type": "call",
      "bid_price": 3.50,
      "ask_price": 3.75,
      "delta": 0.25,
      "in_the_money": false
    }
  ],
  "count": 3,
  "requested_symbols": ["AAPL240216C00190000", "AAPL240216P00180000", "TSLA240216C00200000"]
}
```

---

## Stock Trading

### Market Order - Buy
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

#### Quick Buy
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/buy?qty=10"
```

#### Quick Sell
```bash 
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/sell?qty=5&order_type=limit&limit_price=215.50"
```

---

## Order Management

### Get All Orders
```bash
curl -X GET "http://localhost:8081/api/v1/orders?limit=10"
```

### Get Orders by Status
```bash
curl -X GET "http://localhost:8081/api/v1/orders?status=filled&limit=5"
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

---

## Portfolio Management

### Get All Positions
```bash
curl -X GET "http://localhost:8081/api/v1/positions"
```

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "qty": 15.0,
    "side": "long",
    "market_value": 3187.5,
    "cost_basis": 3150.0,
    "unrealized_pl": 37.5,
    "unrealized_plpc": 0.0119,
    "avg_entry_price": 210.0
  },
  {
    "symbol": "TSLA", 
    "qty": 5.0,
    "side": "long",
    "market_value": 932.5,
    "cost_basis": 950.0,
    "unrealized_pl": -17.5,
    "unrealized_plpc": -0.0184,
    "avg_entry_price": 190.0
  }
]
```

---

## Error Handling Examples

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

### Too Many Symbols
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

---

## Option Symbol Examples

### Popular Option Symbols

**AAPL Options:**
- `AAPL240216C00190000` - AAPL Feb 16, 2024 $190 Call
- `AAPL240216P00230000` - AAPL Feb 16, 2024 $230 Put
- `AAPL240315C00200000` - AAPL Mar 15, 2024 $200 Call

**TSLA Options:**
- `TSLA240216C00200000` - TSLA Feb 16, 2024 $200 Call
- `TSLA240216P00180000` - TSLA Feb 16, 2024 $180 Put

**GOOGL Options:**
- `GOOGL240216C00140000` - GOOGL Feb 16, 2024 $140 Call
- `GOOGL240216P00135000` - GOOGL Feb 16, 2024 $135 Put

---

## Complete Trading Workflow Example

### 1. Check Account Status
```bash
curl -X GET "http://localhost:8081/api/v1/account"
```

### 2. Get Stock Quotes
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{"symbols": ["AAPL", "TSLA", "GOOGL"]}'
```

### 3. Analyze Options
```bash
curl -X POST "http://localhost:8081/api/v1/options/chain" \
     -H "Content-Type: application/json" \
     -d '{"underlying_symbol": "AAPL"}'
```

### 4. Place Orders
```bash
# Buy stock
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
```

### 5. Monitor Positions
```bash
curl -X GET "http://localhost:8081/api/v1/positions"
```

### 6. Check Orders
```bash
curl -X GET "http://localhost:8081/api/v1/orders?limit=5"
```

---

## 🎯 Ready to Trade!

This API provides complete access to:
- ✅ Real-time stock quotes (single and batch)
- ✅ Complete options chains with Greeks
- ✅ Individual option quotes with detailed pricing
- ✅ Full trading capabilities (market, limit, stop orders)
- ✅ Portfolio and position management
- ✅ Order history and management

All endpoints are documented in the interactive API documentation at:
**http://localhost:8081/docs**