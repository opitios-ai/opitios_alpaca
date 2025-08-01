# Opitios Alpaca Trading API

A multi-user, production-ready trading API service built on FastAPI with real-time stock and options data from Alpaca Markets. Features JWT authentication, paper trading, WebSocket support, and comprehensive REST API for stock/options trading.

## 🔥 Key Features

- **Multi-User Authentication**: JWT-based user management with secure credentials
- **WebSocket Support**: Real-time market data streaming (Alpaca Paper Trading compatible)
- **Paper Trading**: Full Alpaca Paper Trading integration with live market data
- **Real-Time Data**: Stock quotes, options pricing, account data, and order management
- **Comprehensive API**: 20+ endpoints with complete OpenAPI documentation
- **Production Ready**: Rate limiting, logging, error handling, and security middleware

## 🌐 Alpaca WebSocket Support

✅ **Alpaca Paper Trading (Free) fully supports WebSocket**
- **Real-time Streaming**: Stock and options market data
- **Limitations**: IEX exchange data only, 30 symbol limit for stocks, 200 quotes for options
- **Endpoints**: 
  - Account updates: `wss://paper-api.alpaca.markets/stream`
  - Market data: `wss://stream.data.alpaca.markets/v2/iex`
- **Authentication**: API key-based, single connection per user

## 📋 System Requirements

- Python 3.9+
- Redis Server (optional, for distributed rate limiting)
- SQLite/MySQL (user data storage)
- Alpaca Paper Trading Account (free)

## 🛠 Quick Setup

### 1. Installation
```bash
git clone <repository-url>
cd opitios_alpaca
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Set environment variables
export ALPACA_API_KEY="your_paper_trading_api_key"
export ALPACA_SECRET_KEY="your_paper_trading_secret_key"
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"
export ALPACA_PAPER_TRADING="true"
```

### 3. Start Server
```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

## 🚀 API Endpoints

### Public Endpoints (No Authentication)
- `GET /` - Service info
- `GET /api/v1/health` - Health check
- `GET /api/v1/test-connection` - Test Alpaca connection
- `POST /api/v1/stocks/quote` - Get stock quote
- `GET /api/v1/stocks/{symbol}/quote` - Get stock quote by symbol
- `POST /api/v1/stocks/quotes/batch` - Batch stock quotes
- `GET /api/v1/account` - Account info (demo)
- `GET /api/v1/positions` - Positions (demo)

### Authentication Endpoints
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login (get JWT token)

### Protected Endpoints (JWT Required)
- `POST /api/v1/stocks/order` - Place stock order
- `POST /api/v1/options/order` - Place options order
- `GET /api/v1/orders` - Get orders
- `DELETE /api/v1/orders/{id}` - Cancel order
- `POST /api/v1/stocks/{symbol}/buy` - Quick buy
- `POST /api/v1/stocks/{symbol}/sell` - Quick sell

## 📚 API Documentation

- **Swagger UI**: http://localhost:8081/docs
- **ReDoc**: http://localhost:8081/redoc
- **OpenAPI Spec**: http://localhost:8081/openapi.json

### JWT Authentication in Swagger
1. Register/Login to get JWT token
2. Click "Authorize" button in Swagger UI
3. Enter: `Bearer YOUR_JWT_TOKEN`
4. Test protected endpoints

## 🧪 Testing

### Run Tests
```bash
# Basic unit tests
pytest tests/test_main.py -v

# All tests
pytest -v

# With coverage
pytest --cov=app --cov-report=html
```

### Manual API Testing
See [API_TEST_COMMANDS.md](API_TEST_COMMANDS.md) for complete curl command examples.

### Quick Test
```bash
# Health check
curl http://localhost:8081/api/v1/health

# Stock quote
curl http://localhost:8081/api/v1/stocks/AAPL/quote

# Register user
curl -X POST http://localhost:8081/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com", 
    "password": "TestPassword123!",
    "alpaca_api_key": "YOUR_KEY",
    "alpaca_secret_key": "YOUR_SECRET",
    "alpaca_paper_trading": true
  }'
```

## 🏗 Architecture

### Multi-User System
- **User Management**: SQLite database with encrypted Alpaca credentials
- **Authentication**: JWT tokens with role-based permissions
- **User Isolation**: Each user has isolated trading sessions and data
- **Connection Pooling**: Efficient Alpaca API connection management

### Middleware Stack
1. **Authentication Middleware**: JWT validation and user context
2. **Rate Limiting Middleware**: User-level request throttling
3. **Logging Middleware**: Structured request/response logging
4. **CORS Middleware**: Cross-origin resource sharing

### Security Features
- Encrypted Alpaca API credentials storage
- JWT token expiration and refresh
- Request rate limiting per user
- Input validation and sanitization
- Comprehensive audit logging

## 🔧 Configuration

### Environment Variables
```bash
# Required
ALPACA_API_KEY=your_paper_api_key
ALPACA_SECRET_KEY=your_paper_secret_key

# Optional
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true
JWT_SECRET=your-jwt-secret-key
REDIS_HOST=localhost
REDIS_PORT=6379
LOG_LEVEL=INFO
```

### Database Configuration
The system uses SQLite by default for user data storage. For production, configure MySQL:

```python
# config.py
database_url = "mysql://user:password@localhost/opitios_alpaca"
```

## 📊 Monitoring

### Logs
- **Application logs**: `logs/app/alpaca_service.log`
- **User operations**: `logs/users/user_operations.jsonl`
- **Trading operations**: `logs/trading/trading_operations.jsonl`
- **Security audit**: `logs/security/security_audit.jsonl`
- **Performance metrics**: `logs/performance/performance.jsonl`

### Metrics
- Request rate per user
- API response times
- Error rates by endpoint
- User session activity

## 🚢 Production Deployment

### Docker Deployment
```bash
# Build image
docker build -t opitios-alpaca .

# Run container
docker run -d \
  -p 8081:8081 \
  -e ALPACA_API_KEY=your_key \
  -e ALPACA_SECRET_KEY=your_secret \
  opitios-alpaca
```

### Production Considerations
- Use MySQL for production database
- Configure Redis for distributed rate limiting
- Set up proper JWT secret key rotation
- Enable HTTPS with reverse proxy
- Monitor logs and metrics
- Regular security updates

## 🔍 Troubleshooting

### Common Issues

**1. JWT Authentication Fails in Swagger**
- Ensure you're using `Bearer TOKEN_HERE` format
- Check token hasn't expired (24 hour default)
- Verify user exists and credentials are correct

**2. Alpaca API Connection Errors**
- Verify Paper Trading API keys are correct
- Check Alpaca service status
- Ensure network connectivity to Alpaca endpoints

**3. WebSocket Connection Issues**
- Free accounts limited to single WebSocket connection
- Check API key permissions for market data
- Verify IEX data feed access

### Debug Mode
```bash
# Start in debug mode
uvicorn main:app --reload --log-level debug

# Check system health
curl http://localhost:8081/api/v1/health
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue in the GitHub repository
- Check the API documentation at `/docs`
- Review the test commands in `API_TEST_COMMANDS.md`