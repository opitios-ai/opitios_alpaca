# Opitios Alpaca Trading Service Documentation

A multi-user, production-ready trading API service built on FastAPI with real-time stock and options data from Alpaca Markets. Features JWT authentication, paper trading, WebSocket support, and comprehensive bilingual documentation.

## 🔥 Key Features

- **Multi-User Authentication**: JWT-based user management with secure credentials
- **WebSocket Support**: Real-time market data streaming (Alpaca Paper Trading compatible)
- **Paper Trading**: Full Alpaca Paper Trading integration with live market data
- **Real-Time Data**: Stock quotes, options pricing, account data, and order management
- **Comprehensive API**: 20+ endpoints with complete OpenAPI documentation
- **Production Ready**: Rate limiting, logging, error handling, and security middleware
- **Bilingual Documentation**: Complete English and Chinese documentation with interactive tools

## 📚 Documentation Structure

### English Documentation
- **[Quick Start Guide](en/quickstart.md)** - Get up and running in minutes
- **[API Examples](en/api-examples.md)** - Comprehensive API usage examples  
- **[Troubleshooting Guide](en/troubleshooting.md)** - Common issues and solutions
- **[Setup Validation](en/setup-validation.md)** - Interactive setup verification

### Chinese Documentation (中文文档)
- **[快速开始指南](zh/快速开始指南.md)** - 快速上手指南
- **[API 使用示例](zh/API使用示例.md)** - 完整的API使用例子
- **[故障排除指南](zh/故障排除指南.md)** - 常见问题和解决方案
- **[安装验证](zh/安装验证.md)** - 交互式安装验证

## 🔧 Interactive Tools

Get your system set up and validated with our interactive tools:

```bash
# Interactive setup validation (recommended for first-time users)
python docs/scripts/setup_validator.py

# System health monitoring
python docs/scripts/health_check.py

# Configuration helper
python docs/scripts/config_helper.py

# Documentation validation
python docs/scripts/doc_validator.py
```

## 🚀 Quick Start

**5-Minute Setup**: [English Guide](en/quickstart.md) | [中文指南](zh/快速开始指南.md)

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

### 3. Validate Setup
```bash
python docs/scripts/setup_validator.py
```

### 4. Start Server
```bash
python main.py
# Service runs on port 8090
# Access API docs: http://localhost:8090/docs
```

## 📖 Documentation Index

### Core Guides
| Document | English | Chinese | Description |
|----------|---------|---------|-------------|
| **Quick Start** | [📖 EN](en/quickstart.md) | [📖 中文](zh/快速开始指南.md) | Get started in 5 minutes |
| **API Examples** | [📖 EN](en/api-examples.md) | [📖 中文](zh/API使用示例.md) | Complete API usage guide |
| **Troubleshooting** | [📖 EN](en/troubleshooting.md) | [📖 中文](zh/故障排除指南.md) | Problem solving guide |
| **Setup Validation** | [📖 EN](en/setup-validation.md) | [📖 中文](zh/安装验证.md) | Interactive setup checker |

### Interactive Tools
| Tool | Script | Description |
|------|--------|-------------|
| **Setup Validator** | `docs/scripts/setup_validator.py` | Progressive setup validation |
| **Health Monitor** | `docs/scripts/health_check.py` | System health checking |
| **Config Helper** | `docs/scripts/config_helper.py` | Interactive configuration |
| **Doc Validator** | `docs/scripts/doc_validator.py` | Documentation QA |

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

## 💡 Getting Help

### Quick Solutions
- **Setup Issues**: Run the [Setup Validator](scripts/setup_validator.py)
- **API Issues**: Check [API Examples](en/api-examples.md) or [API 示例](zh/API使用示例.md)
- **Problems**: See [Troubleshooting](en/troubleshooting.md) or [故障排除](zh/故障排除指南.md)
- **Setup Validation**: Run the [Setup Validator](scripts/setup_validator.py)

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

---

**Documentation Version**: 1.0.0  
**Last Updated**: January 2025  
**Supported Languages**: English, 中文 (Chinese)