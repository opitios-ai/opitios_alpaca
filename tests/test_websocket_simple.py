#!/usr/bin/env python3
"""
简化的WebSocket连接测试脚本
"""
import asyncio
import websockets
import json
import time
from datetime import datetime

async def simple_websocket_test():
    """执行简化的WebSocket连接测试"""
    
    print("=== WebSocket Test Started ===")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        uri = 'ws://localhost:8090/api/v1/ws/market-data'
        print(f"Connecting to: {uri}")
        
        # 连接WebSocket
        async with websockets.connect(uri) as websocket:
            print("SUCCESS: WebSocket connected")
            
            # 1. 接收欢迎消息
            print("\n--- Step 1: Welcome Message ---")
            welcome_raw = await websocket.recv()
            welcome_data = json.loads(welcome_raw)
            
            print(f"Client ID: {welcome_data.get('client_id', 'N/A')}")
            print(f"Message: {welcome_data.get('message', 'N/A')}")
            print(f"Data Source: {welcome_data.get('data_source', 'N/A')}")
            
            # 账户信息
            account_info = welcome_data.get('account_info', {})
            print(f"Account ID: {account_info.get('account_id', 'N/A')}")
            print(f"Account Tier: {account_info.get('tier', 'N/A')}")
            print(f"Paper Trading: {account_info.get('paper_trading', 'N/A')}")
            
            # 能力信息
            capabilities = welcome_data.get('capabilities', {})
            print(f"Stock Data: {capabilities.get('stock_data', False)}")
            print(f"Option Data: {capabilities.get('option_data', False)}")
            print(f"Real Time: {capabilities.get('real_time', False)}")
            print(f"Stock Endpoint: {capabilities.get('stock_endpoint', 'N/A')}")
            print(f"Option Endpoint: {capabilities.get('option_endpoint', 'N/A')}")
            
            # 2. 接收订阅确认
            print("\n--- Step 2: Subscription Confirmation ---")
            subscription_raw = await websocket.recv()
            subscription_data = json.loads(subscription_raw)
            
            print(f"Type: {subscription_data.get('type', 'N/A')}")
            print(f"Message: {subscription_data.get('message', 'N/A')}")
            print(f"Status: {subscription_data.get('status', 'N/A')}")
            
            subscribed_symbols = subscription_data.get('subscribed_symbols', [])
            print(f"Total subscribed symbols: {len(subscribed_symbols)}")
            
            # 分类符号
            stock_symbols = [s for s in subscribed_symbols if len(s) <= 10]
            option_symbols = [s for s in subscribed_symbols if len(s) > 10]
            print(f"Stock symbols: {len(stock_symbols)}")
            print(f"Option symbols: {len(option_symbols)}")
            if stock_symbols:
                print(f"Stock examples: {stock_symbols[:3]}")
            if option_symbols:
                print(f"Option examples: {option_symbols[:2]}")
            
            # 3. 等待实时数据
            print("\n--- Step 3: Waiting for Real-time Data ---")
            print("Listening for 15 seconds...")
            
            data_count = 0
            stock_data_count = 0
            option_data_count = 0
            error_count = 0
            
            for i in range(15):  # 监听15秒
                try:
                    message_raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message_data = json.loads(message_raw)
                    
                    msg_type = message_data.get('type', 'unknown')
                    
                    if msg_type in ['quote', 'trade']:
                        # 市场数据
                        symbol = message_data.get('symbol', 'N/A')
                        data_type = message_data.get('data_type', 'N/A')
                        
                        data_count += 1
                        if data_type == 'stock':
                            stock_data_count += 1
                        elif data_type == 'option':
                            option_data_count += 1
                        
                        print(f"DATA: {data_type} {msg_type} - {symbol}")
                        
                    elif msg_type == 'error':
                        error_count += 1
                        error_msg = message_data.get('message', 'Unknown error')
                        print(f"ERROR: {error_msg}")
                        
                    else:
                        print(f"OTHER: {msg_type}")
                        
                except asyncio.TimeoutError:
                    if i % 5 == 4:  # 每5秒显示一次进度
                        print(f"Waiting... ({i+1}/15 seconds)")
                    continue
                except Exception as e:
                    print(f"ERROR receiving message: {e}")
                    break
            
            # 4. 测试结果
            print("\n=== Test Results ===")
            print(f"WebSocket Connection: SUCCESS")
            print(f"Welcome Message: RECEIVED")
            print(f"Subscription Confirmation: RECEIVED")
            print(f"Data Messages: {data_count}")
            print(f"  - Stock Data: {stock_data_count}")
            print(f"  - Option Data: {option_data_count}")
            print(f"Error Messages: {error_count}")
            
            # 5. 诊断
            print("\n=== Diagnosis ===")
            if data_count > 0:
                print("STATUS: WebSocket data stream is working normally")
                print("RESULT: Real-time data is being received successfully")
            else:
                print("STATUS: No real-time data received")
                print("POSSIBLE REASONS:")
                print("  - Market is closed (non-trading hours)")
                print("  - Alpaca WebSocket connection issues")
                print("  - API permission limitations")
                print("  - Network connectivity issues")
            
            if error_count > 0:
                print("WARNING: Error messages detected - check server logs")
            
            print("\nTest completed successfully")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"ERROR: WebSocket connection closed unexpectedly: {e}")
    except ConnectionRefusedError:
        print("ERROR: Cannot connect to server - ensure server is running on port 8090")
    except Exception as e:
        print(f"ERROR: Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting WebSocket detailed test...")
    asyncio.run(simple_websocket_test())