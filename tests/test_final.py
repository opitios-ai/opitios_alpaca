#!/usr/bin/env python3
"""
Final Alpaca WebSocket test - No Unicode, pure ASCII
"""
import asyncio
import websockets
import json
import requests
from datetime import datetime

async def test_alpaca_websocket():
    """Test Alpaca official test endpoint using FAKEPACA"""
    print("=== Testing Alpaca Official Test Endpoint (FAKEPACA) ===")
    
    try:
        # Get real API credentials
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            print(f"SUCCESS: Got real API credentials: {credentials['account_name']}")
            print(f"API Key: {api_key[:10]}...")
        else:
            print(f"ERROR: Failed to get API credentials: {response.status_code}")
            return
        
        # Connect to Alpaca test WebSocket
        test_uri = "wss://stream.data.alpaca.markets/v2/test"
        print(f"Connecting to: {test_uri}")
        
        async with websockets.connect(test_uri) as websocket:
            print("SUCCESS: Connected to Alpaca official test WebSocket")
            
            # Receive welcome message
            welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            welcome_data = json.loads(welcome_msg)
            print(f"Welcome message: {welcome_data}")
            
            # Send authentication message
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            
            await websocket.send(json.dumps(auth_message))
            print("Sent authentication message...")
            
            # Receive authentication response
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_data = json.loads(auth_response)
            print(f"Auth response: {auth_data}")
            
            # Check authentication success
            if isinstance(auth_data, list) and len(auth_data) > 0:
                auth_result = auth_data[0]
                if auth_result.get('T') == 'success' and 'authenticated' in str(auth_result.get('msg', '')):
                    print("SUCCESS: Authentication successful!")
                    
                    # Subscribe to FAKEPACA data
                    subscribe_message = {
                        "action": "subscribe",
                        "trades": ["FAKEPACA"],
                        "quotes": ["FAKEPACA"],
                        "bars": ["FAKEPACA"]
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    print(f"Sent subscription message: {subscribe_message}")
                    
                    # Receive subscription confirmation
                    sub_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    sub_data = json.loads(sub_response)
                    print(f"Subscription confirmation: {sub_data}")
                    
                    # Receive real-time data
                    print("Starting to receive FAKEPACA real-time test data...")
                    for i in range(15):  # Try to receive 15 messages
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=15)
                            data = json.loads(message)
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            
                            if isinstance(data, list) and len(data) > 0:
                                for item in data:
                                    msg_type = item.get('T', 'unknown')
                                    symbol = item.get('S', 'N/A')
                                    
                                    if msg_type == 'q':  # Quote
                                        bid = item.get('bp', 0)
                                        ask = item.get('ap', 0)
                                        print(f"QUOTE [{timestamp}] {symbol}: Bid=${bid:.2f} Ask=${ask:.2f}")
                                    elif msg_type == 't':  # Trade
                                        price = item.get('p', 0)
                                        size = item.get('s', 0)
                                        print(f"TRADE [{timestamp}] {symbol}: ${price:.2f} x{size}")
                                    elif msg_type == 'b':  # Bar
                                        open_price = item.get('o', 0)
                                        close_price = item.get('c', 0)
                                        volume = item.get('v', 0)
                                        print(f"BAR [{timestamp}] {symbol}: Open=${open_price:.2f} Close=${close_price:.2f} Vol={volume}")
                                    else:
                                        print(f"DATA [{timestamp}] Type={msg_type}: {item}")
                            else:
                                print(f"RAW DATA [{timestamp}]: {data}")
                                
                        except asyncio.TimeoutError:
                            print("TIMEOUT: No data received (may be outside market hours)")
                            break
                        except Exception as e:
                            print(f"ERROR: Data reception error: {e}")
                            break
                else:
                    print(f"ERROR: Authentication failed: {auth_result}")
            else:
                print(f"ERROR: Unexpected auth response format: {auth_data}")
                    
    except Exception as e:
        print(f"ERROR: WebSocket connection error: {e}")

async def main():
    """Main function"""
    print("Starting Alpaca FAKEPACA WebSocket Test")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check server status
    try:
        health_response = requests.get("http://localhost:8091/api/v1/health", timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"Server status: {health_data['status']}")
            print(f"Configuration: real_data_only={health_data['configuration']['real_data_only']}")
        else:
            print(f"Server health check failed: {health_response.status_code}")
            return
    except Exception as e:
        print(f"Cannot connect to server: {e}")
        return
    
    # Execute WebSocket test
    await test_alpaca_websocket()
    
    print("\n=== TEST COMPLETED ===")
    print("If you see FAKEPACA data above, WebSocket connection and authentication work!")
    print("This proves:")
    print("1. Real API credentials are being used")
    print("2. WebSocket connection is successful")  
    print("3. Authentication with Alpaca servers works")
    print("4. Data streaming is functional")

if __name__ == "__main__":
    asyncio.run(main())