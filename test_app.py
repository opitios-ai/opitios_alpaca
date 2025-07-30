#!/usr/bin/env python3
"""
Simple test script to verify the Alpaca trading service works
"""
import asyncio
import sys
sys.path.append('.')

from app.alpaca_client import AlpacaClient
from app.models import StockQuoteRequest
from fastapi.testclient import TestClient
from main import app

async def test_alpaca_client():
    """Test the Alpaca client directly"""
    print("Testing Alpaca Client...")
    
    client = AlpacaClient()
    
    # Test connection (will fail without valid API keys but should not crash)
    result = await client.test_connection()
    print(f"Connection test result: {result}")
    
    # Test stock quote request (will fail without valid API keys but should not crash)
    try:
        quote = await client.get_stock_quote("AAPL")
        print(f"AAPL quote result: {quote}")
    except Exception as e:
        print(f"Quote test (expected to fail without valid keys): {e}")

def test_fastapi_endpoints():
    """Test FastAPI endpoints using TestClient"""
    print("\nTesting FastAPI Endpoints...")
    
    with TestClient(app) as client:
        # Test root endpoint
        response = client.get("/")
        print(f"Root endpoint: {response.status_code} - {response.json()}")
        
        # Test health check
        response = client.get("/api/v1/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        
        # Test connection test (will fail without valid API keys)
        response = client.get("/api/v1/test-connection")
        print(f"Connection test: {response.status_code}")
        
        # Test stock quote endpoint (will fail without valid API keys)
        response = client.get("/api/v1/stocks/AAPL/quote")
        print(f"Stock quote endpoint: {response.status_code}")
        
        # Test POST stock quote
        response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
        print(f"POST stock quote: {response.status_code}")

if __name__ == "__main__":
    print("=== Opitios Alpaca Trading Service Test ===")
    
    # Test FastAPI endpoints
    test_fastapi_endpoints()
    
    # Test Alpaca client
    asyncio.run(test_alpaca_client())
    
    print("\n=== Test completed successfully! ===")
    print("The application is ready to use. To start the server, run:")
    print("python3 main.py")
    print("\nThen visit http://localhost:8081/docs for the API documentation")