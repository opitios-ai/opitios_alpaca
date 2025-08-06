# Development Guide

## Architecture

This is a FastAPI-based trading service with WebSocket support for real-time data streaming.

### Core Components
- **FastAPI Backend**: RESTful API with WebSocket endpoints
- **WebSocket Streaming**: Real-time stock and option data
- **Alpaca Integration**: Trading API and market data
- **MsgPack Support**: Binary data format for options

### Tech Stack
- **Backend**: Python 3.8+, FastAPI, WebSockets
- **Frontend**: HTML, JavaScript, MsgPack library
- **Data**: JSON (stocks), MsgPack (options)
- **Authentication**: JWT tokens, API keys

## API Testing Commands

### Health Check
```bash
curl http://localhost:8090/api/v1/health
```

### Get API Credentials  
```bash
curl http://localhost:8090/api/v1/auth/alpaca-credentials
```

### WebSocket Test
```bash
# Open browser
http://localhost:8090/static/websocket_test.html
```

## Security & Performance

### Security Features
- JWT authentication
- API key validation
- CORS protection
- Input sanitization

### Performance Optimizations
- WebSocket connection pooling
- Binary data streaming (MsgPack)
- Efficient error handling
- CDN fallback mechanisms

## Multi-Account System

The service supports multiple trading accounts with proper isolation:
- Account-specific WebSocket streams
- Separate API credentials per account
- Role-based access control
- Data segregation