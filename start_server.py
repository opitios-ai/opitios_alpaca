#!/usr/bin/env python3
"""
Server startup script for testing
"""
import asyncio
import threading
import time
import requests
import json
from main import app
import uvicorn

def start_server():
    """Start the FastAPI server"""
    uvicorn.run(app, host="0.0.0.0", port=8081)

def test_server_endpoints():
    """Test server endpoints"""
    base_url = "http://localhost:8081"
    
    # Wait for server to start
    print("Waiting for server to start...")
    for i in range(10):
        try:
            response = requests.get(f"{base_url}/api/v1/health", timeout=2)
            if response.status_code == 200:
                print("Server is ready!")
                break
        except:
            time.sleep(1)
    else:
        print("Server failed to start")
        return
    
    print("\n=== Testing Live Server Endpoints ===")
    
    # Test health
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=10)
        print(f"Health Check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health Check Error: {e}")
    
    # Test connection
    try:
        response = requests.get(f"{base_url}/api/v1/test-connection", timeout=10)
        print(f"Connection Test: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Account: {data.get('account_number', 'N/A')}")
            print(f"  Buying Power: ${data.get('buying_power', 'N/A')}")
    except Exception as e:
        print(f"Connection Test Error: {e}")
    
    # Test account
    try:
        response = requests.get(f"{base_url}/api/v1/account", timeout=10)
        print(f"Account Info: {response.status_code}")
        if response.status_code == 200:
            account = response.json()
            print(f"  Portfolio Value: ${account.get('portfolio_value', 'N/A')}")
    except Exception as e:
        print(f"Account Info Error: {e}")
    
    # Test stock quote
    try:
        response = requests.get(f"{base_url}/api/v1/stocks/AAPL/quote", timeout=10)
        print(f"AAPL Quote: {response.status_code}")
        if response.status_code == 200:
            quote = response.json()
            print(f"  Bid: ${quote.get('bid_price', 'N/A')} Ask: ${quote.get('ask_price', 'N/A')}")
    except Exception as e:
        print(f"Stock Quote Error: {e}")
    
    # Test positions
    try:
        response = requests.get(f"{base_url}/api/v1/positions", timeout=10)
        print(f"Positions: {response.status_code}")
        if response.status_code == 200:
            positions = response.json()
            print(f"  Position Count: {len(positions)}")
    except Exception as e:
        print(f"Positions Error: {e}")
    
    print(f"\n=== Server is running at {base_url} ===")
    print(f"API Documentation: {base_url}/docs")
    print("Press Ctrl+C to stop the server")

if __name__ == "__main__":
    print("Starting Alpaca Trading Service Server...")
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Test endpoints
    test_server_endpoints()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")