# ✅ Setup Validation Guide

Ensure your Opitios Alpaca Trading Service is correctly configured and running with interactive validation tools and system diagnostics.

## 🚀 Quick Validation

**Recommended: Use Automated Validation Tools**

```bash
# Run comprehensive setup validator (recommended)
python docs/scripts/setup_validator.py

# System health monitoring
python docs/scripts/health_check.py

# Basic functionality test
python test_app.py
```

## 📋 Validation Checklist

### Prerequisites Validation
- [ ] **Python 3.8+**: `python --version`
- [ ] **Virtual Environment**: Activated with visible `(venv)` prompt
- [ ] **Dependencies**: All packages from requirements.txt installed
- [ ] **Project Structure**: All required files and directories present
- [ ] **Configuration**: .env file with correct API keys

### Service Validation
- [ ] **Server Startup**: Starts without errors
- [ ] **Port Access**: Port 8081 accessible
- [ ] **API Documentation**: http://localhost:8081/docs accessible
- [ ] **Health Endpoint**: `/api/v1/health` returns success
- [ ] **API Connection**: Successfully connects to Alpaca API

### Functionality Validation
- [ ] **Account Access**: Can retrieve account information
- [ ] **Market Data**: Stock quotes work correctly
- [ ] **Basic Trading**: Paper trading orders can be executed
- [ ] **Logging**: Log files generated correctly

## 🔍 Interactive Validation Tools

### Setup Validator Features

**Run Command:**
```bash
python docs/scripts/setup_validator.py
```

**Validation Steps:**
1. **Python Version Check**: Confirms Python 3.8+ compatibility
2. **Virtual Environment Check**: Verifies venv activation status
3. **Package Dependencies Check**: Confirms all required packages installed
4. **Project Structure Validation**: Checks file and directory structure
5. **Configuration Validation**: Validates environment variables and API keys
6. **API Connectivity Test**: Tests Alpaca API connectivity
7. **Local Server Test**: Validates local server startup

**Expected Output Example:**
```
================================================================
            Opitios Alpaca Trading Service - Setup Validator
================================================================

[STEP] 1 - Checking Python version compatibility
✅ Python 3.9.7

[STEP] 2 - Checking virtual environment
✅ Active virtual environment: D:\Github\opitios_alpaca\venv

[STEP] 3 - Checking required packages
✅ All required packages are installed

[STEP] 4 - Validating project structure
✅ Project structure is correct

[STEP] 5 - Checking configuration
✅ Configuration is valid
ℹ️  ALPACA_API_KEY: ****MJAY3
ℹ️  ALPACA_SECRET_KEY: ****cret
ℹ️  ALPACA_BASE_URL: https://paper-api.alpaca.markets
ℹ️  ALPACA_PAPER_TRADING: true

[STEP] 6 - Testing Alpaca API connectivity
✅ Connected successfully. Buying power: $200000.0

[STEP] 7 - Testing local server startup
✅ Local server started successfully

================================================================
                           Validation Results
================================================================
Passed: 7/7
Success Rate: 100.0%
🎉 Excellent! Your setup is ready for production use.
```

### Health Check Tool Features

**Run Command:**
```bash
python docs/scripts/health_check.py
```

**Monitoring Areas:**
1. **Server Process**: Checks running server processes
2. **Port Availability**: Validates port 8081 status
3. **API Endpoints**: Tests all core endpoints
4. **System Resources**: Monitors CPU, memory, disk usage
5. **Log Files**: Analyzes log files for errors and warnings
6. **Database Connectivity**: Tests database connectivity
7. **Configuration Validation**: Validates environment variables
8. **Health Score**: Calculates overall system health score

**Health Scoring System:**
- **90-100 Points**: Excellent - System running perfectly
- **70-89 Points**: Good - Minor issues but functional
- **< 70 Points**: Needs Attention - Major issues present

## 🛠️ Manual Validation Steps

If automated tools are not available, follow these manual validation steps:

### Step 1: Environment Validation

```bash
# Check Python version
python --version
# Expected: Python 3.8.0 or higher

# Check virtual environment
echo $VIRTUAL_ENV  # Linux/Mac
echo %VIRTUAL_ENV%  # Windows
# Expected: Shows venv path

# Verify package installation
pip list | grep -E "(fastapi|alpaca|pydantic|uvicorn)"
# Expected: Shows all core packages
```

### Step 2: Configuration Validation

```bash
# Check .env file exists
ls -la .env
# Expected: Shows .env file

# Validate API key format (without showing actual keys)
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('ALPACA_API_KEY', '')
secret_key = os.getenv('ALPACA_SECRET_KEY', '')
print(f'API Key format: {\"Valid\" if api_key.startswith((\"PK\", \"AK\")) else \"Invalid\"}')
print(f'Secret Key length: {len(secret_key)} chars')
"
# Expected: API Key format: Valid, Secret Key length: 40 chars
```

### Step 3: Server Startup Validation

```bash
# Start server
python main.py &
# Expected: No error messages, shows startup info

# Wait a few seconds for server to start
sleep 5

# Test basic endpoint
curl -s http://localhost:8081/api/v1/health
# Expected: {"status": "healthy", "service": "Opitios Alpaca Trading Service"}
```

### Step 4: API Functionality Validation

```bash
# Test account access
curl -s http://localhost:8081/api/v1/account | head -c 100
# Expected: JSON response with account information

# Test stock quotes
curl -s http://localhost:8081/api/v1/stocks/AAPL/quote | head -c 100
# Expected: JSON response with AAPL quote data

# Test API documentation
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/docs
# Expected: 200
```

## 🚨 Common Validation Failures and Solutions

### Validation Failure: Virtual Environment Not Activated

**Symptoms:**
```
❌ No virtual environment detected
```

**Solution:**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Verify activation
echo $VIRTUAL_ENV
```

### Validation Failure: Missing Dependencies

**Symptoms:**
```
❌ Missing packages: fastapi, uvicorn, alpaca-py
```

**Solution:**
```bash
# Ensure virtual environment is activated
pip install -r requirements.txt

# Verify installation
pip list | grep fastapi
```

### Validation Failure: API Connection

**Symptoms:**
```
❌ Authentication failed - check API credentials
```

**Solution:**
1. Verify API keys in .env file
2. Check key status in Alpaca dashboard
3. Confirm network connectivity

### Validation Failure: Server Startup

**Symptoms:**
```
❌ Server not responding on localhost:8081
```

**Solution:**
1. Check if port 8081 is in use
2. Review server startup error logs
3. Verify firewall settings

## 📊 Performance Benchmarks

### Response Time Benchmarks

Run performance tests to validate system performance:

```bash
# Health check response time
time curl -s http://localhost:8081/api/v1/health
# Expected: < 100ms

# Account info response time
time curl -s http://localhost:8081/api/v1/account
# Expected: < 500ms

# Stock quote response time
time curl -s http://localhost:8081/api/v1/stocks/AAPL/quote
# Expected: < 1000ms
```

### Resource Usage Benchmarks

```bash
# Check memory usage
ps aux | grep python | grep main.py
# Expected: RSS < 100MB

# Check CPU usage
top -p $(pgrep -f "python main.py") -n 1
# Expected: CPU < 5% when idle
```

## 🔄 Continuous Validation

### Automated Monitoring Script

Create a regular validation script:

```bash
#!/bin/bash
# save as validate_health.sh

echo "$(date): Starting health validation"

# Run health check
python docs/scripts/health_check.py

# Check critical endpoints
endpoints=("/api/v1/health" "/api/v1/account" "/docs")
for endpoint in "${endpoints[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8081$endpoint")
    if [ "$status" -eq 200 ]; then
        echo "✅ $endpoint: OK"
    else
        echo "❌ $endpoint: FAILED ($status)"
    fi
done

echo "$(date): Health validation completed"
```

### Setting Up Monitoring Schedule

```bash
# Setup hourly health checks (Linux/Mac)
crontab -e
# Add: 0 * * * * /path/to/validate_health.sh >> /path/to/health.log 2>&1

# Windows Task Scheduler
# Create task to run validation script hourly
```

## 📈 Validation Success Criteria

### Production Ready Checklist

System is considered ready for production when:

- [ ] **100% Validation Pass Rate**: All automated checks pass
- [ ] **Response Times** < 1 second for all API calls
- [ ] **Memory Usage** < 200MB under normal load
- [ ] **CPU Usage** < 10% under normal load
- [ ] **No Critical Errors** in logs
- [ ] **All Endpoints** return expected responses
- [ ] **API Documentation** accessible
- [ ] **Database Connection** stable

### High Availability Standards

For production environments, also validate:

- [ ] **Failover**: Service recovers automatically after restart
- [ ] **Load Testing**: System handles concurrent requests
- [ ] **Security**: API keys stored securely
- [ ] **Monitoring**: Logging and error tracking working
- [ ] **Backup**: Configuration and data regularly backed up

## 🎯 Validation Report

After successful validation, your system will have:

- ✅ **Fully Functional Trading API**
- ✅ **Real-time Market Data Access**
- ✅ **Stable Server Performance**
- ✅ **Comprehensive Error Handling**
- ✅ **Detailed Logging**
- ✅ **Interactive API Documentation**
- ✅ **Health Monitoring System**

**Next Steps:**
1. **Start Trading**: Review [API Examples](api-examples.md)
2. **Production Deployment**: See [Architecture Guide](architecture.md)
3. **Monitoring Setup**: Run health checks regularly
4. **Troubleshooting**: If issues arise, see [Troubleshooting Guide](troubleshooting.md)

---

**Validation Guide Version**: 1.0.0  
**Last Updated**: January 2025  
**Target Success Rate**: >90%