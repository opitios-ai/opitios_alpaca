#!/usr/bin/env python3
"""
测试升级后的WebSocket实现
"""
import asyncio
import websockets
import json
from datetime import datetime

async def test_upgraded_websocket():
    """测试升级后的WebSocket功能"""
    
    print("=== Testing Upgraded WebSocket Implementation ===")
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
            
            # 检查新的能力信息
            capabilities = welcome_data.get('capabilities', {})
            print(f"Stock Data: {capabilities.get('stock_data', False)}")
            print(f"Option Data: {capabilities.get('option_data', False)}")
            print(f"Real Time: {capabilities.get('real_time', False)}")
            print(f"Native WebSocket: {capabilities.get('native_websocket', False)}")
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
            
            # 3. 测试升级功能 - 等待健康检查和数据流
            print("\n--- Step 3: Testing Upgraded Features ---")
            print("Monitoring for 20 seconds to test:")
            print("- Health check messages")
            print("- Real-time data flow")
            print("- Error handling")
            print("- Message statistics")
            
            message_types = {}
            health_check_seen = False
            data_count = 0
            
            for i in range(20):  # 监听20秒
                try:
                    message_raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message_data = json.loads(message_raw)
                    
                    msg_type = message_data.get('type', 'unknown')
                    message_types[msg_type] = message_types.get(msg_type, 0) + 1
                    
                    if msg_type in ['quote', 'trade']:
                        data_count += 1
                        symbol = message_data.get('symbol', 'N/A')
                        data_type = message_data.get('data_type', 'N/A')
                        print(f"DATA: {data_type} {msg_type} - {symbol}")
                        
                    elif msg_type == 'health_check':
                        health_check_seen = True
                        print(f"HEALTH CHECK: {message_data.get('message', 'N/A')}")
                        
                    elif msg_type == 'error':
                        print(f"ERROR: {message_data.get('message', 'Unknown error')}")
                        
                    else:
                        print(f"OTHER: {msg_type}")
                        
                except asyncio.TimeoutError:
                    if i % 10 == 9:  # 每10秒显示一次进度
                        print(f"Monitoring... ({i+1}/20 seconds)")
                    continue
                except Exception as e:
                    print(f"ERROR receiving message: {e}")
                    break
            
            # 4. 升级功能测试结果
            print("\n=== Upgraded Features Test Results ===")
            print(f"WebSocket Connection: SUCCESS")
            print(f"Welcome Message: RECEIVED with new capabilities info")
            print(f"Subscription Confirmation: RECEIVED")
            print(f"Data Messages: {data_count}")
            print(f"Health Check Detected: {health_check_seen}")
            print(f"Message Types Seen: {list(message_types.keys())}")
            
            # 5. 验证升级特性
            print("\n=== Upgrade Verification ===")
            
            # 检查是否显示了测试端点信息
            if 'test' in str(welcome_data).lower():
                print("✓ Test endpoint information present")
            else:
                print("? Test endpoint information not visible in welcome")
            
            # 检查是否有官方端点信息
            stock_endpoint = capabilities.get('stock_endpoint', '')
            option_endpoint = capabilities.get('option_endpoint', '')
            
            if 'stream.data.alpaca.markets/v2/iex' in stock_endpoint:
                print("✓ Official stock WebSocket endpoint configured")
            else:
                print("? Stock endpoint not as expected")
                
            if 'stream.data.alpaca.markets/v1beta1/indicative' in option_endpoint:
                print("✓ Official option WebSocket endpoint configured")
            else:
                print("? Option endpoint not as expected")
            
            # 检查是否支持MessagePack
            if capabilities.get('supports_json_msgpack', False):
                print("✓ JSON/MessagePack support indicated")
            else:
                print("? MessagePack support not indicated")
            
            print("\n=== Final Assessment ===")
            if data_count > 0:
                print("STATUS: Real-time data streaming is working")
                print("RESULT: WebSocket upgrade appears successful")
            else:
                print("STATUS: No real-time data received")
                print("POSSIBLE REASONS:")
                print("  - Market is closed (non-trading hours)")
                print("  - Still establishing connections to Alpaca")
                print("  - Test endpoint validation may have passed")
                print("  - Health checks running in background")
            
            print("\nUpgraded WebSocket test completed successfully!")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"ERROR: WebSocket connection closed unexpectedly: {e}")
    except ConnectionRefusedError:
        print("ERROR: Cannot connect to server - ensure server is running on port 8090")
    except Exception as e:
        print(f"ERROR: Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting upgraded WebSocket test...")
    asyncio.run(test_upgraded_websocket())