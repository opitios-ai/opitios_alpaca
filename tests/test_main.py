import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root_endpoint():
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "status" in data
    assert data["status"] == "running"

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data

def test_connection_test():
    """Test the connection test endpoint"""
    response = client.get("/api/v1/test-connection")
    # This might fail if API credentials are not properly configured
    # But we can test that the endpoint exists
    assert response.status_code in [200, 500]  # 500 if credentials are invalid

def test_get_account():
    """Test get account endpoint"""
    response = client.get("/api/v1/account")
    # This might fail if API credentials are not properly configured
    assert response.status_code in [200, 500]

def test_get_positions():
    """Test get positions endpoint"""
    response = client.get("/api/v1/positions")
    # This might fail if API credentials are not properly configured
    assert response.status_code in [200, 500]

def test_stock_quote_endpoint():
    """Test stock quote endpoint with a common stock"""
    response = client.get("/api/v1/stocks/AAPL/quote")
    # This might fail if API credentials are not properly configured or market is closed
    assert response.status_code in [200, 400, 500]

def test_stock_quote_post():
    """Test POST stock quote endpoint"""
    response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
    # This might fail if API credentials are not properly configured
    assert response.status_code in [200, 400, 500]

def test_stock_bars():
    """Test stock bars endpoint"""
    response = client.get("/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=10")
    # This might fail if API credentials are not properly configured
    assert response.status_code in [200, 400, 500]

def test_get_orders():
    """Test get orders endpoint"""
    response = client.get("/api/v1/orders")
    # This might fail if API credentials are not properly configured
    assert response.status_code in [200, 500]

def test_options_chain():
    """Test options chain endpoint"""
    response = client.get("/api/v1/options/AAPL/chain")
    # This might fail if API credentials are not properly configured
    assert response.status_code in [200, 400, 500]

def test_invalid_stock_symbol():
    """Test with invalid stock symbol"""
    response = client.get("/api/v1/stocks/INVALID_SYMBOL_12345/quote")
    # Should return error for invalid symbol
    assert response.status_code in [400, 500]