# Opitios Alpaca Trading API

A multi-user, production-ready trading API service built on FastAPI with real-time stock and options data from Alpaca Markets. Features JWT authentication, paper trading, WebSocket support, and comprehensive REST API for stock/options trading.

## 🔥 Key Features

- **Multi-User Authentication**: JWT-based user management with secure credentials
- **WebSocket Support**: Real-time market data streaming (Alpaca Paper Trading compatible)
- **Paper Trading**: Full Alpaca Paper Trading integration with live market data
- **Real-Time Data**: Stock quotes, options pricing, account data, and order management
- **Comprehensive API**: 20+ endpoints with complete OpenAPI documentation
- **Production Ready**: Rate limiting, logging, error handling, and security middleware

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

Copy the secrets template and configure your API keys:
```bash
cp secrets.example.yml secrets.yml
# Edit secrets.yml and add your Alpaca API keys
```

**🔑 Get Your API Keys:**
1. Visit [Alpaca Markets](https://alpaca.markets/)
2. Create a free account
3. Enable Paper Trading mode  
4. Generate API keys in your dashboard

### 3. Start Server
```bash
python main.py
# Service runs on port 8090
```

## 📚 API Documentation

- **Swagger UI**: http://localhost:8090/docs
- **ReDoc**: http://localhost:8090/redoc
- **OpenAPI Spec**: http://localhost:8090/openapi.json

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

### Quick Health Check
```bash
curl http://localhost:8090/api/v1/health
```

## 📖 Documentation

Complete documentation is available in the `/docs` folder:

- **[Quick Start Guide](docs/QUICKSTART.md)** - Get up and running quickly
- **[Setup Instructions](docs/SETUP.md)** - Detailed installation guide
- **[API Test Commands](docs/API_TEST_COMMANDS.md)** - Complete curl examples
- **[Testing Guide](docs/TESTING.md)** - Testing framework and procedures
- **[Real Data Requirements](docs/requirements-real-data-only.md)** - Production data setup

## 🏗 Architecture

### Multi-User System
- **User Management**: SQLite database with encrypted Alpaca credentials
- **Authentication**: JWT tokens with role-based permissions
- **User Isolation**: Each user has isolated trading sessions and data
- **Connection Pooling**: Efficient Alpaca API connection management

### Security Features
- Encrypted Alpaca API credentials storage
- JWT token expiration and refresh
- Request rate limiting per user
- Input validation and sanitization
- Comprehensive audit logging

## 🔧 Configuration

The system uses `secrets.yml` for all sensitive configuration. See `secrets.example.yml` for the template.

### Required Configuration
- Alpaca API credentials
- JWT secret key
- Application settings

### Optional Configuration
- Redis settings (for distributed caching)
- Rate limiting parameters
- CORS allowed origins

## 📊 Monitoring

### Logs
- **Application logs**: `logs/app/alpaca_service.log`
- **User operations**: `logs/users/user_operations.jsonl`
- **Trading operations**: `logs/trading/trading_operations.jsonl`
- **Security audit**: `logs/security/security_audit.jsonl`
- **Performance metrics**: `logs/performance/performance.jsonl`

## 🚢 Production Deployment

### Docker Deployment
```bash
# Build image
docker build -t opitios-alpaca .

# Run container with secrets
docker run -d \
  -p 8090:8090 \
  -v $(pwd)/secrets.yml:/app/secrets.yml \
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

**1. Configuration Errors**
- Ensure `secrets.yml` exists and is properly formatted
- Verify all required fields are configured
- Check file permissions for secrets.yml

**2. Alpaca API Connection Errors**
- Verify Paper Trading API keys are correct
- Check Alpaca service status
- Ensure network connectivity to Alpaca endpoints

**3. Port Conflicts**
- Service runs on port 8090 (fixed)
- Ensure port is available and not blocked by firewall

### Debug Mode
```bash
# Start in debug mode
uvicorn main:app --reload --log-level debug --port 8090

# Check system health
curl http://localhost:8090/api/v1/health
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
- Review the documentation in the `docs/` folder