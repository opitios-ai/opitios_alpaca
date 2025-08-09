# Opitios Alpaca WebSocket Trading Service 🚀

<div align="center">
  <img src="https://trading.opitios.com/assets/img/brand-logos/desktop-logo.png" alt="美股智投 Opitios" height="60px">
  <br>
  <strong>Powered by 美股智投 (Opitios) - Professional US Stock Trading Platform</strong>
</div>

<div align="center">

![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)
![WebSocket Support](https://img.shields.io/badge/websocket-real--time-brightgreen?style=flat-square)
![MsgPack Support](https://img.shields.io/badge/msgpack-binary--streaming-blue?style=flat-square)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)
![FastAPI Version](https://img.shields.io/badge/fastapi-0.104.1-blue?style=flat-square)
![Option Trading](https://img.shields.io/badge/options-real--time-green?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Last Updated](https://img.shields.io/badge/updated-August%202025-blue?style=flat-square)

</div>

---

## 🏢 About Opitios

This open-source WebSocket trading service is developed and maintained by **美股智投 (Opitios)**, a professional US stock trading platform dedicated to providing advanced trading tools and real-time market data solutions for institutional and individual traders.

**🌐 Visit:** [trading.opitios.com](https://trading.opitios.com) | **📧 Contact:** Support Team

---

## 📖 Project Overview

A comprehensive FastAPI-based trading service with **real-time WebSocket streaming** for stock and options trading. Features intelligent endpoint detection, MsgPack binary support for option data, and comprehensive market data integration with Alpaca Trading API.

## ✨ Key Features

- 🔄 **Intelligent WebSocket Streaming** - Smart endpoint detection (SIP → IEX → Test fallback)
- 📊 **Option WebSocket Support** - MsgPack binary format for real-time option data
- 🔐 **Dynamic Authentication** - Real API credentials with automatic tier detection
- 🎯 **Production-Grade Reliability** - Connection limits, error recovery, health monitoring
- 📈 **Comprehensive UI** - Interactive WebSocket test interface
- 🛡️ **Advanced Error Recovery** - Production-specific error handling and fallback mechanisms
- 🌐 **Enterprise Ready** - Docker support, auto port management, and deployment configurations
- 🚀 **Opitios Powered** - Built by professional trading platform experts

## 🚀 Quick Start

### Prerequisites

```bash
# 1. Python 3.8+ with virtual environment (REQUIRED)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt
```

### Configuration

1. **Copy and configure secrets file:**
```bash
cp secrets.example.yml secrets.yml
```

2. **Add your Alpaca API credentials to `secrets.yml`:**
```yaml
alpaca:
  api_key: "YOUR_ALPACA_API_KEY"
  secret_key: "YOUR_ALPACA_SECRET_KEY" 
  paper_trading: true  # Set to false for live trading
  account_name: "Primary Trading Account"
```

### Start the Server

```bash
# Development server
python main.py

# Or use the startup script
python start_server.py
```

**Server will be available at:** `http://localhost:8090`

## 🌐 WebSocket Streaming

### Access the Interactive WebSocket Test Interface

**URL:** `http://localhost:8090/static/websocket_test.html`

### WebSocket Endpoints

| Endpoint | Type | Data Format | Purpose |
|----------|------|-------------|---------|
| `ws://localhost:8090/api/v1/ws/market-data` | Production | JSON | Local real-time stock data |
| `wss://stream.data.alpaca.markets/v2/test` | Test | JSON | Alpaca test data (FAKEPACA) |
| `wss://stream.data.alpaca.markets/v1beta1/indicative` | Options | **MsgPack** | Real-time option data |

### WebSocket Features

- ✅ **Simultaneous Connections** - Connect to all three endpoints at once
- ✅ **Real-time Data Comparison** - Compare production vs test data
- ✅ **Option Subscription Management** - Add/remove option symbols dynamically
- ✅ **MsgPack Binary Decoding** - Automatic binary data processing
- ✅ **Comprehensive Logging** - Real-time message logging and debugging
- ✅ **Status Monitoring** - Connection status and message counters

## 📊 Option WebSocket Usage

### Default Option Symbols
```javascript
// Automatically subscribed option symbols
[
  'UNIT250815C00007000',  // UNIT Call $7.00 exp 08/15
  'TSLA250808C00310000',  // TSLA Call $310.00 exp 08/08
  'AAPL250808C00210000',  // AAPL Call $210.00 exp 08/08
  'NVDA250808C00180000',  // NVDA Call $180.00 exp 08/08
  // ... and more
]
```

### Adding Custom Option Subscriptions
1. Open WebSocket test page
2. Connect to option endpoint
3. Enter option symbol in format: `SYMBOL + YYMMDD + C/P + STRIKE`
4. Example: `AAPL250815C00215000` (AAPL Call $215 exp 08/15/25)

### MsgPack Binary Data
- Option endpoint uses **MsgPack binary format** (not JSON)
- JavaScript library automatically loaded via CDN
- Fallback mechanisms ensure reliability
- Real-time encode/decode validation

## 🛠️ Development

### Testing WebSocket Functionality

**Comprehensive Test Suite:**
```bash
# Test all WebSocket endpoints
python tests/test_msgpack_ascii.py

# Test specific functionality
python tests/test_final.py
python tests/test_websocket_real_data.py
```

### Running the Full Test Suite
```bash
python run_tests.py
```

### Development Commands

```bash
# Start development server with auto-reload
python main.py

# Check server health
curl http://localhost:8090/api/v1/health

# Get API credentials endpoint
curl http://localhost:8090/api/v1/auth/alpaca-credentials
```

## 🐳 Docker Deployment

### Docker Compose (Recommended)

```bash
# Build and start services
docker-compose up --build

# Run in background
docker-compose up -d
```

### Manual Docker Build

```bash
# Build image
docker build -t opitios-alpaca .

# Run container
docker run -p 8090:8090 \
  -v $(pwd)/secrets.yml:/app/secrets.yml:ro \
  opitios-alpaca
```

## 🌐 Server Deployment

### Prerequisites for Production

1. **Server Requirements:**
   - Python 3.8+
   - Port 8090 accessible
   - SSL certificate (for WSS endpoints)

2. **Environment Setup:**
```bash
# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp secrets.example.yml secrets.yml
# Edit with your production API keys
```

### Production Deployment Options

#### Option 1: Direct Python Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Start production server
python main.py

# Or with process manager
nohup python main.py > server.log 2>&1 &
```

#### Option 2: Systemd Service (Linux)
Create `/etc/systemd/system/opitios-alpaca.service`:
```ini
[Unit]
Description=Opitios Alpaca WebSocket Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/opitios-alpaca
ExecStart=/opt/opitios-alpaca/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable opitios-alpaca
sudo systemctl start opitios-alpaca
sudo systemctl status opitios-alpaca
```

#### Option 3: Nginx Reverse Proxy
```nginx
# /etc/nginx/sites-available/opitios-alpaca
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### Cloud Platform Deployment

#### AWS EC2 Deployment
```bash
# 1. Launch EC2 instance (t3.micro or larger)
# 2. Install Python and dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv

# 3. Clone repository
git clone https://github.com/yourusername/opitios_alpaca.git
cd opitios_alpaca

# 4. Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure secrets and start service
cp secrets.example.yml secrets.yml
# Edit secrets.yml with your API keys
python main.py
```

#### Heroku Deployment
```bash
# 1. Install Heroku CLI
# 2. Create Procfile
echo "web: python main.py" > Procfile

# 3. Deploy
heroku create your-app-name
git push heroku main
heroku config:set ALPACA_API_KEY=your_key_here
heroku config:set ALPACA_SECRET_KEY=your_secret_here
```

#### DigitalOcean App Platform
```yaml
# app.yaml
name: opitios-alpaca
services:
- name: web
  source_dir: /
  github:
    repo: yourusername/opitios_alpaca
    branch: main
  run_command: python main.py
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8090
  env:
  - key: ALPACA_API_KEY
    value: your_api_key_here
  - key: ALPACA_SECRET_KEY
    value: your_secret_key_here
```

## 🔧 Configuration

### Environment Variables
```bash
# .env file (optional, overrides secrets.yml)
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_PAPER_TRADING=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8090
```

### secrets.yml Configuration
```yaml
alpaca:
  api_key: "YOUR_ALPACA_API_KEY"
  secret_key: "YOUR_ALPACA_SECRET_KEY"
  paper_trading: true
  account_name: "Primary Trading Account"
  
server:
  host: "0.0.0.0"
  port: 8090
  real_data_only: true
```

## 📚 API Documentation

### Interactive API Docs
- **Swagger UI:** `http://localhost:8090/docs`
- **ReDoc:** `http://localhost:8090/redoc`

### Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Server health check |
| `/api/v1/auth/alpaca-credentials` | GET | Get real API credentials |
| `/api/v1/auth/demo-token` | GET | Get demo JWT token |
| `/api/v1/ws/market-data` | WebSocket | Real-time market data |
| `/static/websocket_test.html` | GET | WebSocket test interface |

## 🐛 Troubleshooting

### Common Issues

#### WebSocket Connection Failed
```bash
# Check server is running
curl http://localhost:8090/api/v1/health

# Check port availability
netstat -an | grep 8090
```

#### MsgPack Library Not Loading
1. Check browser console for CDN errors
2. Verify network connectivity
3. Try manual refresh of WebSocket test page

#### Option WebSocket Authentication Failed
1. Verify API keys in `secrets.yml`
2. Check Alpaca account permissions for option data
3. Ensure paper trading is enabled

### Server Logs
```bash
# View server logs
tail -f logs/app.log

# Check specific WebSocket activity
grep "WebSocket" logs/app.log
```

### Performance Monitoring
```bash
# Monitor server resources
htop

# Check WebSocket connections
ss -tuln | grep 8090
```

## 📈 Features Roadmap

- [ ] **Real-time Portfolio Monitoring** - Live P&L tracking
- [ ] **Advanced Order Management** - OCO, Bracket orders
- [ ] **Options Strategy Builder** - Pre-built strategy templates
- [ ] **Risk Management Tools** - Position sizing, stop-loss automation
- [ ] **Historical Data Analysis** - Backtesting capabilities
- [ ] **Mobile App Integration** - React Native companion app

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details.

### Development Setup

```bash
# Fork the repository
git fork https://github.com/yourusername/opitios_alpaca.git

# Clone and setup
git clone https://github.com/yourusername/opitios_alpaca.git
cd opitios_alpaca
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run tests
python run_tests.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Alpaca Trading API](https://alpaca.markets/) for market data and trading infrastructure
- [FastAPI](https://fastapi.tiangolo.com/) for the high-performance web framework  
- [MsgPack](https://msgpack.org/) for efficient binary serialization

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/opitios_alpaca/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/opitios_alpaca/discussions)
- **Documentation:** [docs/](docs/) directory

---

**⚠️ Important:** This software is for educational and development purposes. Always test thoroughly in paper trading mode before using with real money. Trading involves significant risk of loss.

**🔐 Security:** Never commit API keys or secrets to version control. Always use environment variables or secure secret management systems in production.

---

## Quick Commands Reference

```bash
# Start server
python main.py

# Test WebSocket
open http://localhost:8090/static/websocket_test.html

# Run tests  
python tests/test_msgpack_ascii.py

# Docker deployment
docker-compose up --build

# Check health
curl http://localhost:8090/api/v1/health
```

**Ready to trade with real-time data!** 🚀📊