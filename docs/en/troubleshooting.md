# 🔧 Troubleshooting Guide

This comprehensive troubleshooting guide helps you diagnose and resolve common issues with the Opitios Alpaca Trading Service.

## 🚨 Quick Diagnostic Tools

Before diving into specific issues, try these diagnostic tools:

```bash
# Run the comprehensive setup validator
python docs/scripts/setup_validator.py

# Check system health
python docs/scripts/health_check.py

# Test basic functionality
python test_app.py
```

## 📋 Common Issues Index

1. [Installation & Setup Issues](#installation--setup-issues)
2. [API Connection Problems](#api-connection-problems)
3. [Authentication Errors](#authentication-errors)
4. [Trading Order Issues](#trading-order-issues)
5. [Market Data Problems](#market-data-problems)
6. [Server & Performance Issues](#server--performance-issues)
7. [Configuration Problems](#configuration-problems)
8. [Python Environment Issues](#python-environment-issues)

---

## Installation & Setup Issues

### ❌ Issue: "ModuleNotFoundError" when running the application

**Symptoms:**
```
ModuleNotFoundError: No module named 'fastapi'
ModuleNotFoundError: No module named 'alpaca_trade_api'
```

**Diagnosis:**
```bash
# Check if virtual environment is activated
echo $VIRTUAL_ENV  # Linux/Mac
echo %VIRTUAL_ENV%  # Windows

# Check installed packages
pip list
```

**Solutions:**

1. **Activate Virtual Environment** (CRITICAL):
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Installation**:
   ```bash
   pip show fastapi alpaca-py
   ```

### ❌ Issue: "Permission denied" errors during installation

**Symptoms:**
```
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied
```

**Solutions:**

1. **Use Virtual Environment** (Recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **User Installation** (Alternative):
   ```bash
   pip install --user -r requirements.txt
   ```

### ❌ Issue: Python version compatibility errors

**Symptoms:**
```
python: command not found
SyntaxError: invalid syntax (async/await)
```

**Diagnosis:**
```bash
python --version
python3 --version
```

**Solution:**
Ensure Python 3.8+ is installed:
```bash
# Install Python 3.8+ if needed
# Windows: Download from python.org
# Linux: sudo apt install python3.8
# Mac: brew install python@3.8

# Use specific Python version
python3.8 -m venv venv
```

---

## API Connection Problems

### ❌ Issue: "Connection refused" or "Network unreachable"

**Symptoms:**
```json
{
  "detail": "Could not connect to Alpaca API"
}
```

**Diagnosis:**
```bash
# Test basic connectivity
curl -X GET "http://localhost:8081/api/v1/test-connection"

# Check network connectivity
ping paper-api.alpaca.markets

# Verify firewall/proxy settings
curl -I https://paper-api.alpaca.markets
```

**Solutions:**

1. **Check Internet Connection**:
   - Verify network connectivity
   - Test with different network if possible

2. **Firewall/Proxy Issues**:
   ```bash
   # Check if corporate firewall blocks API access
   # Configure proxy if needed
   export https_proxy=http://proxy.company.com:8080
   ```

3. **DNS Issues**:
   ```bash
   # Try with IP address instead of domain
   nslookup paper-api.alpaca.markets
   ```

### ❌ Issue: SSL/TLS certificate errors

**Symptoms:**
```
SSLError: certificate verify failed
```

**Solutions:**

1. **Update certificates**:
   ```bash
   pip install --upgrade certifi
   ```

2. **Corporate network workaround**:
   ```python
   # In emergency only - not recommended for production
   import ssl
   ssl._create_default_https_context = ssl._create_unverified_context
   ```

---

## Authentication Errors

### ❌ Issue: "Invalid API credentials" or "401 Unauthorized"

**Symptoms:**
```json
{
  "detail": "Unauthorized: Invalid API credentials"
}
```

**Diagnosis:**
```bash
# Check environment variables
echo $ALPACA_API_KEY
echo $ALPACA_SECRET_KEY

# Verify .env file
cat .env
```

**Solutions:**

1. **Verify API Keys**:
   ```bash
   # Check .env file format
   cat .env
   ```
   
   Correct format:
   ```env
   ALPACA_API_KEY=PKEIKZWFXA4BD1JMJAY3
   ALPACA_SECRET_KEY=your_actual_secret_key_here
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   ALPACA_PAPER_TRADING=true
   ```

2. **Regenerate API Keys**:
   - Go to [Alpaca Dashboard](https://app.alpaca.markets/)
   - Navigate to API Keys section
   - Generate new key pair
   - Update .env file

3. **Check Key Format**:
   - API Key should start with "PK" (Paper) or "AK" (Live)
   - Secret Key should be 40 characters long
   - No spaces or special characters

### ❌ Issue: "Rate limit exceeded"

**Symptoms:**
```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

**Solutions:**

1. **Implement Rate Limiting**:
   ```python
   import time
   
   # Add delays between requests
   time.sleep(1.0)  # 1 second delay
   ```

2. **Batch Requests**:
   ```bash
   # Use batch endpoints instead of individual requests
   curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch"
   ```

---

## Trading Order Issues

### ❌ Issue: "Insufficient buying power"

**Symptoms:**
```json
{
  "detail": "Insufficient buying power for this order"
}
```

**Diagnosis:**
```bash
# Check account buying power
curl -X GET "http://localhost:8081/api/v1/account"
```

**Solutions:**

1. **Reduce Order Size**:
   ```bash
   # Calculate maximum shares affordable
   # buying_power / stock_price = max_shares
   ```

2. **Check Account Status**:
   - Verify account is funded
   - Check for pending orders that tie up buying power
   - Review margin requirements

### ❌ Issue: "Order rejected by exchange"

**Symptoms:**
```json
{
  "status": "rejected",
  "reason": "Invalid order parameters"
}
```

**Common Causes & Solutions:**

1. **Market Hours**:
   ```bash
   # Check if market is open
   date  # Verify current time
   # Market hours: 9:30 AM - 4:00 PM ET, Mon-Fri
   ```

2. **Invalid Price**:
   ```bash
   # Check current stock price
   curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/quote"
   
   # Ensure limit price is reasonable (within 5% of current price)
   ```

3. **Minimum Order Value**:
   - Alpaca requires minimum $1 order value
   - Check: quantity × price ≥ $1.00

### ❌ Issue: Orders stuck in "pending_new" status

**Symptoms:**
Orders remain in pending status for extended periods.

**Diagnosis:**
```bash
# Check order status
curl -X GET "http://localhost:8081/api/v1/orders?limit=5"

# Check market hours and conditions
```

**Solutions:**

1. **Cancel and Retry**:
   ```bash
   # Cancel stuck order
   curl -X DELETE "http://localhost:8081/api/v1/orders/{order_id}"
   
   # Place new order
   ```

2. **Adjust Order Parameters**:
   - Use "day" instead of "gtc" for time_in_force
   - Adjust limit price closer to market price

---

## Market Data Problems

### ❌ Issue: "No quote data found" for valid symbols

**Symptoms:**
```json
{
  "detail": "No quote data found for AAPL"
}
```

**Diagnosis:**
```bash
# Test with known active symbol
curl -X GET "http://localhost:8081/api/v1/stocks/SPY/quote"

# Check market hours
date
```

**Solutions:**

1. **Verify Symbol Format**:
   - Use correct ticker symbols (AAPL, not Apple)
   - Check for delisted or suspended stocks

2. **Market Hours**:
   - Real-time data available during market hours
   - Pre/post-market data may be limited

3. **Data Subscription**:
   - Verify Alpaca account has market data access
   - Check subscription status in Alpaca dashboard

### ❌ Issue: Delayed or stale market data

**Symptoms:**
Quotes show old timestamps or seem delayed.

**Solutions:**

1. **Check Data Subscription**:
   - Verify real-time data subscription
   - Some accounts may have 15-minute delayed data

2. **Network Latency**:
   ```bash
   # Test network latency to Alpaca
   ping paper-api.alpaca.markets
   ```

---

## Server & Performance Issues

### ❌ Issue: "Server failed to start" or immediate shutdown

**Symptoms:**
```
ERROR: Error loading ASGI app. Could not import module "main".
[ERROR] Application startup failed.
```

**Diagnosis:**
```bash
# Check Python path and imports
python -c "import app.routes"
python -c "import config"

# Check for syntax errors
python -m py_compile main.py
```

**Solutions:**

1. **Check File Structure**:
   ```
   opitios_alpaca/
   ├── app/
   │   ├── __init__.py
   │   ├── routes.py
   │   └── models.py
   ├── main.py
   └── config.py
   ```

2. **Fix Import Errors**:
   ```python
   # Verify all imports are correct
   from app.routes import router  # Check this path
   from config import settings    # Check this path
   ```

### ❌ Issue: High memory usage or slow performance

**Symptoms:**
- Server becomes unresponsive
- High CPU/memory usage
- Slow API responses

**Diagnosis:**
```bash
# Monitor system resources
top
htop  # If available

# Check Python process
ps aux | grep python
```

**Solutions:**

1. **Restart Server**:
   ```bash
   # Stop server (Ctrl+C)
   # Restart
   python main.py
   ```

2. **Check for Memory Leaks**:
   ```python
   # Add memory monitoring
   import psutil
   import os
   
   process = psutil.Process(os.getpid())
   print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
   ```

### ❌ Issue: Port already in use

**Symptoms:**
```
OSError: [Errno 48] Address already in use
```

**Solutions:**

1. **Find and Kill Process**:
   ```bash
   # Windows
   netstat -ano | findstr :8081
   taskkill /PID <process_id> /F
   
   # Linux/Mac
   lsof -i :8081
   kill -9 <process_id>
   ```

2. **Use Different Port**:
   ```bash
   # Change port in .env or command line
   python main.py --port 8082
   ```

---

## Configuration Problems

### ❌ Issue: Environment variables not loading

**Symptoms:**
```
ValueError: ALPACA_API_KEY environment variable is required
```

**Diagnosis:**
```bash
# Check .env file exists and format
ls -la .env
cat .env

# Test environment loading
python -c "from config import settings; print(settings.alpaca_api_key)"
```

**Solutions:**

1. **Verify .env File**:
   ```env
   # Correct format (no spaces around =)
   ALPACA_API_KEY=PKEIKZWFXA4BD1JMJAY3
   ALPACA_SECRET_KEY=your_secret_key
   
   # Incorrect format
   ALPACA_API_KEY = PKEIKZWFXA4BD1JMJAY3  # No spaces!
   ```

2. **Check File Location**:
   ```bash
   # .env should be in project root
   ls -la .env
   pwd  # Should be in opitios_alpaca directory
   ```

### ❌ Issue: Database connection errors

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Solutions:**

1. **Check File Permissions**:
   ```bash
   ls -la users.db
   chmod 644 users.db  # If needed
   ```

2. **Close Existing Connections**:
   ```bash
   # Restart the server to close DB connections
   # Check for multiple server instances
   ```

---

## Python Environment Issues

### ❌ Issue: Virtual environment not working properly

**Symptoms:**
- Packages installed globally instead of in venv
- Wrong Python version being used
- Import errors despite installation

**Diagnosis:**
```bash
# Check virtual environment status
which python
which pip
echo $VIRTUAL_ENV  # Should show venv path

# Check Python version
python --version
```

**Solutions:**

1. **Recreate Virtual Environment**:
   ```bash
   # Remove old venv
   rm -rf venv
   
   # Create new venv
   python3 -m venv venv
   
   # Activate
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Verify Activation**:
   ```bash
   # After activation, prompt should show (venv)
   # Example: (venv) user@machine:~/opitios_alpaca$
   ```

### ❌ Issue: Package version conflicts

**Symptoms:**
```
ERROR: pip's dependency resolver does not currently consider all the versions that satisfy the requirements
```

**Solutions:**

1. **Clean Installation**:
   ```bash
   pip uninstall -r requirements.txt -y
   pip install -r requirements.txt
   ```

2. **Update pip**:
   ```bash
   pip install --upgrade pip
   pip install --upgrade setuptools wheel
   ```

---

## 🚨 Emergency Troubleshooting

### When Nothing Works

1. **Complete Reset**:
   ```bash
   # Save your .env file
   cp .env .env.backup
   
   # Clean slate
   rm -rf venv
   python3 -m venv venv
   venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   
   # Restore configuration
   cp .env.backup .env
   
   # Test
   python test_app.py
   ```

2. **Minimal Test**:
   ```bash
   # Test basic Python functionality
   python -c "print('Python works')"
   
   # Test FastAPI installation
   python -c "import fastapi; print('FastAPI works')"
   
   # Test Alpaca API
   python -c "import alpaca_trade_api; print('Alpaca API works')"
   ```

### Getting Help

1. **Collect Debug Information**:
   ```bash
   # Run comprehensive diagnostics
   python docs/scripts/setup_validator.py > debug_info.txt 2>&1
   
   # System information
   python --version >> debug_info.txt
   pip list >> debug_info.txt
   ```

2. **Check Logs**:
   ```bash
   # Check application logs
   tail -f logs/alpaca_service.log
   
   # Check system logs if needed
   ```

3. **Contact Support**:
   - Include debug_info.txt
   - Describe exact error messages
   - List steps to reproduce the issue

---

## ✅ Prevention Best Practices

### Regular Maintenance

1. **Keep Dependencies Updated**:
   ```bash
   pip list --outdated
   pip install --upgrade -r requirements.txt
   ```

2. **Monitor Logs**:
   ```bash
   # Check logs regularly
   tail logs/alpaca_service.log
   ```

3. **Test Regularly**:
   ```bash
   # Run tests periodically
   python test_app.py
   pytest
   ```

### Development Best Practices

1. **Always Use Virtual Environments**
2. **Keep .env files secure and updated**
3. **Test changes in paper trading first**
4. **Monitor API rate limits**
5. **Implement proper error handling**

---

## 📞 Support Resources

### Self-Help Tools
- **Setup Validator**: `python docs/scripts/setup_validator.py`
- **Health Check**: `python docs/scripts/health_check.py`
- **Configuration Helper**: `python docs/scripts/config_helper.py`

### Documentation
- **Quick Start**: [Quick Start Guide](quickstart.md)
- **API Reference**: [API Examples](api-examples.md)
- **Architecture**: [System Architecture](architecture.md)

### External Resources
- [Alpaca API Documentation](https://alpaca.markets/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Python Virtual Environments Guide](https://docs.python.org/3/tutorial/venv.html)

---

**Troubleshooting Guide Version**: 1.0.0  
**Last Updated**: January 2025  
**Next**: [Setup Validation](setup-validation.md)