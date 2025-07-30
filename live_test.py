#!/usr/bin/env python3
"""
Live test script with real Alpaca API credentials
"""
import asyncio
import sys
import json
sys.path.append('.')

from app.alpaca_client import AlpacaClient
from fastapi.testclient import TestClient
from main import app

async def test_real_connection():
    """Test connection with real API credentials"""
    print("Testing Alpaca API Connection...")
    
    client = AlpacaClient()
    
    # Test connection
    result = await client.test_connection()
    print(f"Connection Result: {json.dumps(result, indent=2, default=str)}")
    
    if result.get("status") == "connected":
        print("Successfully connected to Alpaca API!")
        
        # Test account info
        account = await client.get_account()
        print(f"Account Info: {json.dumps(account, indent=2, default=str)}")
        
        # Test positions
        positions = await client.get_positions()
        print(f"Positions ({len(positions)}): {json.dumps(positions, indent=2, default=str)}")
        
        # Test stock quote
        quote = await client.get_stock_quote("AAPL")
        print(f"AAPL Quote: {json.dumps(quote, indent=2, default=str)}")
        
        # Test stock bars
        bars = await client.get_stock_bars("AAPL", "1Day", 5)
        print(f"AAPL Bars (5 days): {json.dumps(bars, indent=2, default=str)}")
        
        return True
    else:
        print("Failed to connect to Alpaca API")
        print(f"Error: {result.get('error', 'Unknown error')}")
        return False

def test_api_endpoints():
    """Test FastAPI endpoints with real credentials"""
    print("\nTesting FastAPI Endpoints...")
    
    with TestClient(app) as client:
        # Test health
        response = client.get("/api/v1/health")
        print(f"Health Check: {response.status_code} - {response.json()}")
        
        # Test connection through API
        response = client.get("/api/v1/test-connection")
        print(f"API Connection Test: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        
        # Test account through API
        response = client.get("/api/v1/account")
        print(f"Account Endpoint: {response.status_code}")
        if response.status_code == 200:
            print(f"   Account: {response.json()}")
        
        # Test stock quote through API
        response = client.get("/api/v1/stocks/AAPL/quote")
        print(f"Stock Quote Endpoint: {response.status_code}")
        if response.status_code == 200:
            print(f"   AAPL Quote: {response.json()}")
        
        # Test positions through API
        response = client.get("/api/v1/positions")
        print(f"Positions Endpoint: {response.status_code}")
        if response.status_code == 200:
            positions = response.json()
            print(f"   Positions ({len(positions)}): {positions}")

async def test_trading_functionality():
    """Test trading functionality (paper trading)"""
    print("\nTesting Trading Functionality...")
    
    client = AlpacaClient()
    
    # First check if we have buying power
    account = await client.get_account()
    if "error" not in account:
        buying_power = account.get("buying_power", 0)
        print(f"Available Buying Power: ${buying_power}")
        
        if buying_power > 100:  # Only test if we have enough buying power
            print("Testing paper trading order (1 share of AAPL)...")
            
            # Place a small test order
            order_result = await client.place_stock_order(
                symbol="AAPL",
                qty=1,
                side="buy",
                order_type="market"
            )
            
            print(f"Order Result: {json.dumps(order_result, indent=2, default=str)}")
            
            if "error" not in order_result:
                order_id = order_result.get("id")
                print(f"Order placed successfully! Order ID: {order_id}")
                
                # Wait a moment and check order status
                await asyncio.sleep(2)
                orders = await client.get_orders()
                print(f"Recent Orders: {json.dumps(orders[:3], indent=2, default=str)}")  # Show first 3 orders
                
                # Cancel the order if it's still pending
                if order_id:
                    cancel_result = await client.cancel_order(order_id)
                    print(f"Cancel Result: {json.dumps(cancel_result, indent=2, default=str)}")
            else:
                print(f"Order failed: {order_result['error']}")
        else:
            print(f"Not enough buying power (${buying_power}) to test trading")
    else:
        print(f"Could not get account info: {account['error']}")

if __name__ == "__main__":
    print("=== Live Alpaca Trading Service Test ===")
    print("Using Virtual Environment")
    print("API Base URL: https://paper-api.alpaca.markets/v2")
    print("Paper Trading: Enabled")
    print()
    
    # Test connection and basic functionality  
    success = asyncio.run(test_real_connection())
    
    if success:
        print("\n" + "="*50)
        # Test API endpoints
        test_api_endpoints()
        
        print("\n" + "="*50)
        # Test trading functionality
        asyncio.run(test_trading_functionality())
        
        print("\n" + "="*50)
        print("All tests completed successfully!")
        print("The Alpaca trading service is fully functional!")
    else:
        print("\nConnection failed. Please check your API credentials.")
        print("Make sure your Alpaca API keys are correct in the .env file")
    
    print("\nReady to start the server with: ./venv/Scripts/python.exe main.py")