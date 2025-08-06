#!/usr/bin/env python3
"""
Test WebSocket connections with real API credentials and option symbols
测试WebSocket连接使用真实API密钥接收股票和期权数据
"""
import asyncio
import websockets
import json
import requests
from datetime import datetime, timedelta

async def test_production_websocket():
    """Test local production WebSocket endpoint"""
    print("=== Testing Local Production WebSocket ===")
    
    try:
        # Get JWT Token
        response = requests.get("http://localhost:8091/api/v1/auth/demo-token")
        if response.status_code == 200:
            token_data = response.json()
            jwt_token = token_data['access_token']
            print(f"JWT Token acquired successfully")
        else:
            print(f"Failed to get JWT Token: {response.status_code}")
            return
        
        # Connect to WebSocket
        uri = f"ws://localhost:8091/api/v1/ws/stocks"
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            print("Successfully connected to local production WebSocket")
            
            # Subscribe to stock data (local production endpoint format)
            subscribe_message = {
                "action": "subscribe",
                "symbols": ["AAPL", "TSLA", "SPY"],
                "data_types": ["quotes", "trades", "bars"]
            }
            
            await websocket.send(json.dumps(subscribe_message))
            print(f"Sent subscription message: {subscribe_message}")
            
            # Receive messages
            for i in range(5):  # Receive 5 messages
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    data = json.loads(message)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Received data: {data}")
                except asyncio.TimeoutError:
                    print("Data reception timeout")
                    break
                except Exception as e:
                    print(f"Data reception error: {e}")
                    break
                    
    except Exception as e:
        print(f"Local WebSocket connection error: {e}")

async def test_alpaca_websocket():
    """Test Alpaca official test WebSocket endpoint"""
    print("\n=== Testing Alpaca Official Test WebSocket ===")
    
    try:
        # Get real API credentials
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            print(f"Successfully got real API credentials: {credentials['account_name']}")
        else:
            print(f"Failed to get API credentials: {response.status_code}")
            return
        
        # Connect to Alpaca test WebSocket
        uri = "wss://stream.data.alpaca.markets/v2/test"
        
        async with websockets.connect(uri) as websocket:
            print("Successfully connected to Alpaca official test WebSocket")
            
            # Send authentication message
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            
            await websocket.send(json.dumps(auth_message))
            print(f"Sent auth message: {{'action': 'auth', 'key': '{api_key[:10]}...'}}")
            
            # Receive authentication response
            try:
                auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                auth_data = json.loads(auth_response)
                print(f"Auth response: {auth_data}")
                
                # Handle list response format
                auth_result = auth_data[0] if isinstance(auth_data, list) else auth_data
                if auth_result.get('msg') == 'authenticated':
                    print("Authentication successful")
                    
                    # Subscribe to test data using correct test symbol
                    subscribe_message = {
                        "action": "subscribe",
                        "trades": ["FAKEPACA"],
                        "quotes": ["FAKEPACA"],
                        "bars": ["FAKEPACA"]
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    print(f"Sent subscription message: {subscribe_message}")
                    
                    # Receive data
                    for i in range(5):
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=10)
                            data = json.loads(message)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Alpaca data: {data}")
                        except asyncio.TimeoutError:
                            print("Alpaca data reception timeout")
                            break
                        except Exception as e:
                            print(f"Alpaca data reception error: {e}")
                            break
                else:
                    print(f"Authentication failed: {auth_data}")
                    
            except asyncio.TimeoutError:
                print("Authentication response timeout")
            except Exception as e:
                print(f"Authentication process error: {e}")
                
    except Exception as e:
        print(f"Alpaca WebSocket connection error: {e}")

def generate_option_symbols():
    """Generate some common option symbols for testing"""
    # Option symbol format: AAPL251219C00190000 (AAPL, Dec 19, 2025, Call, $190 strike)
    base_date = datetime.now() + timedelta(days=45)  # About 6 weeks out
    exp_date = base_date.strftime("%y%m%d")  # YYMMDD format
    
    option_symbols = [
        f"AAPL{exp_date}C00180000",  # AAPL Call $180
        f"AAPL{exp_date}P00180000",  # AAPL Put $180
        f"SPY{exp_date}C00420000",   # SPY Call $420
        f"SPY{exp_date}P00420000",   # SPY Put $420
        f"TSLA{exp_date}C00250000",  # TSLA Call $250
        f"TSLA{exp_date}P00250000",  # TSLA Put $250
    ]
    return option_symbols

async def test_option_websocket():
    """Test option WebSocket endpoint"""
    print("\n=== Testing Option WebSocket ===")
    
    try:
        # Get real API credentials
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            print(f"Successfully got real API credentials: {credentials['account_name']}")
        else:
            print(f"Failed to get API credentials: {response.status_code}")
            return
        
        # Option WebSocket endpoint (using paper trading environment)
        option_uri = credentials['endpoints']['option_ws']  # wss://stream.data.alpaca.markets/v1beta1/indicative
        
        async with websockets.connect(option_uri) as websocket:
            print(f"Successfully connected to Option WebSocket: {option_uri}")
            
            # Send authentication message
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            
            await websocket.send(json.dumps(auth_message))
            print(f"Sent auth message: {{'action': 'auth', 'key': '{api_key[:10]}...'}}")
            
            # Receive authentication response
            try:
                auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                auth_data = json.loads(auth_response)
                print(f"Auth response: {auth_data}")
                
                if isinstance(auth_data, list) and len(auth_data) > 0:
                    auth_result = auth_data[0]
                    if auth_result.get('T') == 'success' and 'authenticated' in auth_result.get('msg', ''):
                        print("Option authentication successful")
                        
                        # Generate option symbols
                        option_symbols = generate_option_symbols()
                        print(f"Generated option symbols: {option_symbols[:3]}...")  # Show first 3
                        
                        # Subscribe to option data
                        subscribe_message = {
                            "action": "subscribe",
                            "trades": option_symbols[:3],  # Subscribe to first 3 for testing
                            "quotes": option_symbols[:3]
                        }
                        
                        await websocket.send(json.dumps(subscribe_message))
                        print(f"Sent option subscription message: {subscribe_message}")
                        
                        # Receive option data
                        for i in range(10):  # Try to receive 10 messages
                            try:
                                message = await asyncio.wait_for(websocket.recv(), timeout=15)
                                data = json.loads(message)
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Option data: {data}")
                            except asyncio.TimeoutError:
                                print("Option data reception timeout")
                                break
                            except Exception as e:
                                print(f"Option data reception error: {e}")
                                break
                    else:
                        print(f"Option authentication failed: {auth_result}")
                else:
                    print(f"Unexpected auth response format: {auth_data}")
                    
            except asyncio.TimeoutError:
                print("Option authentication response timeout")
            except Exception as e:
                print(f"Option authentication process error: {e}")
                
    except Exception as e:
        print(f"Option WebSocket connection error: {e}")

async def main():
    """Main test function"""
    print("Starting WebSocket real data test...")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test server health first
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
    
    # Test all WebSocket endpoints
    await test_production_websocket()
    await test_alpaca_websocket()
    await test_option_websocket()
    
    print("\n=== All WebSocket Tests Completed ===")
    print("Summary:")
    print("- Local Production WebSocket: Stock data via local server")
    print("- Alpaca Test WebSocket: FAKEPACA test data")
    print("- Option WebSocket: Real option contracts data")
    print("All endpoints tested with real API credentials!")

if __name__ == "__main__":
    asyncio.run(main())