# Opitios Alpaca Trading Service

A FastAPI-based trading service that integrates with the Alpaca API for stock and options trading. This service provides RESTful endpoints for market data retrieval, order placement, and portfolio management.

## Features

- ✅ **Stock Trading**: Buy/sell stocks with market, limit, and stop orders
- ✅ **Market Data**: Real-time quotes and historical price bars
- ⚠️ **Options Trading**: Basic framework (requires additional Alpaca options API implementation)
- ✅ **Portfolio Management**: Account info, positions, and order management
- ✅ **Paper Trading**: Supports Alpaca's paper trading environment
- ✅ **RESTful API**: Comprehensive FastAPI endpoints with automatic documentation
- ✅ **Testing**: Unit tests with pytest
- ✅ **Logging**: Structured logging with loguru

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Update the `.env` file with your Alpaca API credentials:

```env
ALPACA_API_KEY=PKEIKZWFXA4BD1JMJAY3
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true
```

### 3. Run the Service

```bash
# Development mode
python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

### 4. Access the API

- **API Documentation**: http://localhost:8081/docs
- **Alternative Docs**: http://localhost:8081/redoc
- **Health Check**: http://localhost:8081/api/v1/health

## API Endpoints

### Health & Connection
- `GET /` - Service information
- `GET /api/v1/health` - Health check
- `GET /api/v1/test-connection` - Test Alpaca API connection

### Account Management
- `GET /api/v1/account` - Get account information
- `GET /api/v1/positions` - Get all positions
- `GET /api/v1/orders` - Get orders (with optional status filter)
- `DELETE /api/v1/orders/{order_id}` - Cancel an order

### Stock Market Data
- `GET /api/v1/stocks/{symbol}/quote` - Get latest stock quote
- `POST /api/v1/stocks/quote` - Get quote by request body
- `GET /api/v1/stocks/{symbol}/bars` - Get historical price bars

### Stock Trading
- `POST /api/v1/stocks/order` - Place a stock order
- `POST /api/v1/stocks/{symbol}/buy` - Quick buy endpoint
- `POST /api/v1/stocks/{symbol}/sell` - Quick sell endpoint

### Options (Basic Framework)
- `GET /api/v1/options/{symbol}/chain` - Get options chain
- `POST /api/v1/options/order` - Place options order

## Usage Examples

### Get Account Information
```bash
curl -X GET "http://localhost:8081/api/v1/account"
```

### Get Stock Quote
```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/quote"
```

### Place Market Buy Order
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

### Place Limit Sell Order
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 5,
       "side": "sell",
       "type": "limit",
       "limit_price": 150.50,
       "time_in_force": "gtc"
     }'
```

### Quick Buy/Sell
```bash
# Quick buy 100 shares of TSLA at market price
curl -X POST "http://localhost:8081/api/v1/stocks/TSLA/buy?qty=100"

# Quick sell 50 shares of TSLA with limit price
curl -X POST "http://localhost:8081/api/v1/stocks/TSLA/sell?qty=50&order_type=limit&limit_price=200.00"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ALPACA_API_KEY` | Your Alpaca API key | Required |
| `ALPACA_SECRET_KEY` | Your Alpaca secret key | Required |
| `ALPACA_BASE_URL` | Alpaca API base URL | https://paper-api.alpaca.markets |
| `ALPACA_PAPER_TRADING` | Enable paper trading | true |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8081 |
| `DEBUG` | Debug mode | true |

### Order Types Supported

- **Market Orders**: Execute immediately at current market price
- **Limit Orders**: Execute only at specified price or better
- **Stop Orders**: Trigger market order when stop price is reached
- **Stop Limit Orders**: Trigger limit order when stop price is reached

### Time in Force Options

- **DAY**: Order valid for current trading day
- **GTC**: Good Till Cancelled
- **IOC**: Immediate or Cancel
- **FOK**: Fill or Kill

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_main.py

# Run with coverage
pytest --cov=app tests/
```

## Project Structure

```
opitios_alpaca/
├── app/
│   ├── __init__.py
│   ├── alpaca_client.py    # Alpaca API client wrapper
│   ├── models.py           # Pydantic models
│   └── routes.py           # FastAPI routes
├── tests/
│   ├── __init__.py
│   ├── test_main.py        # API endpoint tests
│   └── test_alpaca_client.py # Client tests
├── logs/                   # Log files directory
├── .env                    # Environment configuration
├── config.py               # Settings management
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── pytest.ini             # Pytest configuration
└── README.md              # This file
```

## Development

### Adding New Features

1. **New API endpoints**: Add routes in `app/routes.py`
2. **New data models**: Define Pydantic models in `app/models.py`  
3. **New Alpaca functionality**: Extend `app/alpaca_client.py`
4. **Tests**: Add corresponding tests under `tests/`

### Common Development Tasks

```bash
# Install development dependencies
pip install -r requirements.txt

# Run in development mode with auto-reload
python main.py

# Format code (if using black)
black .

# Run linter (if using flake8)
flake8 app/ tests/

# Run tests with coverage
pytest --cov=app --cov-report=html
```

## Production Deployment

### Environment Setup

1. Set `DEBUG=false` in production
2. Configure proper CORS origins in `main.py`
3. Use a production WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8081
```

### Security Considerations

- Store API keys securely (use environment variables or secret management)
- Enable HTTPS in production
- Configure proper CORS policies
- Implement authentication/authorization if needed
- Monitor API usage and rate limits

## Limitations & Notes

### Options Trading
The options trading functionality is currently a basic framework. Full implementation depends on:
- Alpaca's options data API availability
- Options contract symbol formatting
- Specific options trading permissions

### Market Data
- Real-time data may require subscription
- Market data availability depends on trading hours
- Some endpoints may have rate limits

### Paper Trading
- This service is configured for paper trading by default
- Switch to live trading by updating `ALPACA_BASE_URL` and `ALPACA_PAPER_TRADING` settings
- Ensure proper risk management when using live trading

## Support

For issues and questions:
1. Check the [Alpaca API documentation](https://alpaca.markets/docs/)
2. Review the FastAPI docs at `/docs` endpoint
3. Check application logs in the `logs/` directory

## License

This project is part of the Opitios trading system. Refer to the main repository license.