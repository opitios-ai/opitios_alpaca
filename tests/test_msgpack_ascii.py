#!/usr/bin/env python3
"""
Test MsgPack Option WebSocket Implementation - ASCII Version
"""
import asyncio
import websockets
import msgpack
import requests
import json
from datetime import datetime

async def test_msgpack_option_websocket():
    """Test MsgPack option WebSocket endpoint"""
    print("=== Testing MsgPack Option WebSocket Endpoint ===")
    
    try:
        # Get real API credentials
        print("Getting API credentials...")
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            option_ws_url = credentials['endpoints']['option_ws']
            print(f"SUCCESS: Got credentials for {credentials['account_name']}")
            print(f"Option endpoint: {option_ws_url}")
        else:
            print(f"ERROR: Failed to get API credentials: {response.status_code}")
            return False
        
        # Connect to option WebSocket
        print(f"Connecting to option WebSocket: {option_ws_url}")
        
        async with websockets.connect(option_ws_url) as websocket:
            print("SUCCESS: WebSocket connected")
            
            # Step 1: Receive welcome message
            try:
                welcome_data = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"Received welcome message: {type(welcome_data)} - length: {len(welcome_data) if hasattr(welcome_data, '__len__') else 'N/A'}")
                
                # Try to parse welcome message
                if isinstance(welcome_data, bytes):
                    try:
                        welcome_msg = msgpack.unpackb(welcome_data)
                        print(f"SUCCESS: MsgPack parsed welcome: {welcome_msg}")
                    except Exception as e:
                        print(f"WARNING: MsgPack parse failed: {e}")
                        try:
                            welcome_msg = json.loads(welcome_data.decode())
                            print(f"SUCCESS: JSON parsed welcome: {welcome_msg}")
                        except Exception as e2:
                            print(f"ERROR: Welcome message parse completely failed: {e2}")
                            welcome_msg = None
                else:
                    try:
                        welcome_msg = json.loads(welcome_data)
                        print(f"SUCCESS: JSON parsed welcome: {welcome_msg}")
                    except Exception as e:
                        print(f"ERROR: Welcome message parse failed: {e}")
                        welcome_msg = None
                
            except asyncio.TimeoutError:
                print("TIMEOUT: Waiting for welcome message")
                welcome_msg = None
            
            # Step 2: Send authentication message (using MsgPack)
            print("Sending MsgPack format authentication message...")
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            
            try:
                # Pack as MsgPack format
                auth_packed = msgpack.packb(auth_message)
                await websocket.send(auth_packed)
                print(f"Sent MsgPack auth message (size: {len(auth_packed)} bytes)")
                
                # Wait for auth response
                auth_response = await asyncio.wait_for(websocket.recv(), timeout=15)
                print(f"Received auth response: {type(auth_response)} - size: {len(auth_response) if hasattr(auth_response, '__len__') else 'N/A'}")
                
                # Parse auth response
                auth_result = None
                if isinstance(auth_response, bytes):
                    try:
                        auth_result = msgpack.unpackb(auth_response)
                        print(f"SUCCESS: MsgPack parsed auth response: {auth_result}")
                    except Exception as e:
                        print(f"WARNING: MsgPack parse auth failed: {e}")
                        try:
                            auth_result = json.loads(auth_response.decode())
                            print(f"SUCCESS: JSON parsed auth response: {auth_result}")
                        except Exception as e2:
                            print(f"ERROR: Auth response parse completely failed: {e2}")
                else:
                    try:
                        auth_result = json.loads(auth_response)
                        print(f"SUCCESS: JSON parsed auth response: {auth_result}")
                    except Exception as e:
                        print(f"ERROR: Auth response parse failed: {e}")
                
                # Check if authentication succeeded
                auth_success = False
                if auth_result:
                    if isinstance(auth_result, list) and len(auth_result) > 0:
                        first_result = auth_result[0]
                        if first_result.get('T') == 'success' and 'authenticated' in str(first_result.get('msg', '')):
                            auth_success = True
                            print("SUCCESS: Authentication successful!")
                        elif first_result.get('T') == 'error':
                            print(f"ERROR: Authentication failed: {first_result.get('msg', 'Unknown error')}")
                    elif isinstance(auth_result, dict):
                        if auth_result.get('T') == 'success' or 'authenticated' in str(auth_result.get('msg', '')):
                            auth_success = True
                            print("SUCCESS: Authentication successful!")
                        elif auth_result.get('T') == 'error':
                            print(f"ERROR: Authentication failed: {auth_result.get('msg', 'Unknown error')}")
                
                if not auth_success:
                    print(f"ERROR: Authentication failed: {auth_result}")
                    return False
                
            except asyncio.TimeoutError:
                print("TIMEOUT: Authentication response timeout")
                return False
            except Exception as e:
                print(f"ERROR: Authentication process error: {e}")
                return False
            
            # Step 3: Subscribe to option data (using MsgPack)
            print("Sending option subscription message...")
            test_option_symbols = [
                'UNIT250815C00007000',
                'TSLA250808C00310000', 
                'AAPL250808C00210000'
            ]
            
            subscribe_message = {
                "action": "subscribe",
                "trades": test_option_symbols[:2],  # Subscribe to first 2 to avoid too much data
                "quotes": test_option_symbols[:2]
            }
            
            try:
                # Pack as MsgPack format
                subscribe_packed = msgpack.packb(subscribe_message)
                await websocket.send(subscribe_packed)
                print(f"Sent MsgPack subscription message: {test_option_symbols[:2]}")
                
                # Wait for subscription confirmation
                sub_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"Received subscription response: {type(sub_response)}")
                
                # Parse subscription response
                if isinstance(sub_response, bytes):
                    try:
                        sub_result = msgpack.unpackb(sub_response)
                        print(f"SUCCESS: MsgPack parsed subscription response: {sub_result}")
                    except Exception as e:
                        print(f"WARNING: MsgPack parse subscription failed: {e}")
                else:
                    try:
                        sub_result = json.loads(sub_response)
                        print(f"SUCCESS: JSON parsed subscription response: {sub_result}")
                    except Exception as e:
                        print(f"ERROR: Subscription response parse failed: {e}")
                
            except asyncio.TimeoutError:
                print("TIMEOUT: Subscription response timeout")
            except Exception as e:
                print(f"ERROR: Subscription process error: {e}")
            
            # Step 4: Try to receive option data
            print("Waiting for option market data...")
            data_received = False
            
            for i in range(10):  # Try to receive 10 messages
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=20)
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    
                    print(f"[{timestamp}] Received message #{i+1}: {type(message)}")
                    
                    # Parse data
                    parsed_data = None
                    if isinstance(message, bytes):
                        try:
                            parsed_data = msgpack.unpackb(message)
                            print(f"  SUCCESS: MsgPack parse successful: {type(parsed_data)}")
                            data_received = True
                            
                            # Analyze data structure
                            if isinstance(parsed_data, list):
                                print(f"    Received {len(parsed_data)} records")
                                for idx, item in enumerate(parsed_data[:3]):  # Show only first 3
                                    if isinstance(item, dict):
                                        msg_type = item.get('T', 'unknown')
                                        symbol = item.get('S', 'N/A')
                                        print(f"      [{idx}] Type: {msg_type}, Symbol: {symbol}")
                                        
                                        if msg_type == 'q':  # Quote
                                            bid = item.get('bp', 'N/A')
                                            ask = item.get('ap', 'N/A')
                                            print(f"           Quote: Bid=${bid} Ask=${ask}")
                                        elif msg_type == 't':  # Trade  
                                            price = item.get('p', 'N/A')
                                            size = item.get('s', 'N/A')
                                            print(f"           Trade: ${price} x{size}")
                            elif isinstance(parsed_data, dict):
                                msg_type = parsed_data.get('T', 'unknown')
                                print(f"    Single message: {msg_type}")
                            else:
                                print(f"    Other data type: {parsed_data}")
                                
                        except Exception as e:
                            print(f"  ERROR: MsgPack parse failed: {e}")
                            # Try text parsing
                            try:
                                text_data = message.decode('utf-8')
                                print(f"    Text content: {text_data[:100]}...")
                            except:
                                print(f"    Binary data length: {len(message)}")
                    else:
                        try:
                            parsed_data = json.loads(message)
                            print(f"  SUCCESS: JSON parse successful: {parsed_data}")
                            data_received = True
                        except Exception as e:
                            print(f"  ERROR: JSON parse failed: {e}")
                            print(f"    Raw message: {message}")
                    
                except asyncio.TimeoutError:
                    print(f"TIMEOUT: Waiting for message #{i+1} (market may be closed)")
                    break
                except Exception as e:
                    print(f"ERROR: Receiving message #{i+1} error: {e}")
                    break
            
            return data_received
            
    except Exception as e:
        print(f"ERROR: WebSocket connection error: {e}")
        return False

async def verify_msgpack_library():
    """Verify MsgPack library availability"""
    print("=== Verifying MsgPack Library ===")
    try:
        # Test basic pack/unpack
        test_data = {"test": "message", "number": 42, "array": [1, 2, 3]}
        packed = msgpack.packb(test_data)
        unpacked = msgpack.unpackb(packed)
        
        print(f"SUCCESS: MsgPack library working normally")
        print(f"   Original data: {test_data}")
        print(f"   Packed size: {len(packed)} bytes")
        print(f"   Unpacked data: {unpacked}")
        print(f"   Data consistency: {test_data == unpacked}")
        return True
    except ImportError:
        print("ERROR: MsgPack library not installed: pip install msgpack")
        return False
    except Exception as e:
        print(f"ERROR: MsgPack library test failed: {e}")
        return False

async def main():
    """Main function"""
    print("Starting MsgPack Option WebSocket Test")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check server status
    try:
        health_response = requests.get("http://localhost:8091/api/v1/health", timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"Server status: {health_data['status']}")
        else:
            print(f"WARNING: Server health check failed: {health_response.status_code}")
            return
    except Exception as e:
        print(f"ERROR: Cannot connect to server: {e}")
        return
    
    # Verify MsgPack library
    msgpack_ok = await verify_msgpack_library()
    if not msgpack_ok:
        print("ERROR: MsgPack library not available, cannot continue test")
        return
    
    print()
    
    # Execute option WebSocket test
    success = await test_msgpack_option_websocket()
    
    print()
    print("=== Test Results Summary ===")
    if success:
        print("SUCCESS: MsgPack Option WebSocket test successful!")
        print("- WebSocket connection normal")
        print("- MsgPack encoding/decoding working")
        print("- Authentication process successful")
        print("- Option data reception successful")
        print()
        print("You can now visit: http://localhost:8091/static/websocket_test.html")
        print("Click 'Connect Option Endpoint' should work normally!")
    else:
        print("FAILED: Test not completely successful")
        print("Please check:")
        print("   - API connection limits (Error 406)")
        print("   - Market open hours")
        print("   - Network connection")
        print("   - Option data subscription permissions")

if __name__ == "__main__":
    asyncio.run(main())