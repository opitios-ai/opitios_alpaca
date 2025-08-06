#!/usr/bin/env python3
"""
简单的WebSocket测试脚本
"""

import asyncio
import websockets
import json
import ssl

async def test_production_websocket():
    """测试生产WebSocket端点"""
    try:
        print("Testing production WebSocket endpoint...")
        uri = "ws://localhost:8090/api/v1/ws/market-data"
        
        async with websockets.connect(uri) as websocket:
            print("Production WebSocket connected successfully!")
            
            # 等待欢迎消息
            welcome = await websocket.recv()
            print(f"Received welcome message: {welcome}")
            
            # 发送ping消息
            ping_msg = {
                "type": "ping",
                "timestamp": "2025-08-06T10:00:00Z"
            }
            await websocket.send(json.dumps(ping_msg))
            print("Sent ping message")
            
            # 等待pong响应
            pong = await asyncio.wait_for(websocket.recv(), timeout=5)
            print(f"Received pong response: {pong}")
            
    except Exception as e:
        print(f"Production WebSocket test failed: {e}")

async def test_alpaca_websocket():
    """测试Alpaca官方WebSocket端点"""
    try:
        print("Testing Alpaca official WebSocket endpoint...")
        uri = "wss://stream.data.alpaca.markets/v2/test"
        
        # 创建SSL上下文
        ssl_context = ssl.create_default_context()
        
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("Alpaca WebSocket connected successfully!")
            
            # 发送认证消息
            auth_msg = {
                "action": "auth",
                "key": "test_api_key",
                "secret": "test_secret_key"
            }
            await websocket.send(json.dumps(auth_msg))
            print("Sent authentication message")
            
            # 等待认证响应
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"Authentication response: {auth_response}")
            
            # 发送订阅消息
            subscribe_msg = {
                "action": "subscribe",
                "quotes": ["AAPL", "TSLA"]
            }
            await websocket.send(json.dumps(subscribe_msg))
            print("Sent subscription message")
            
            # 等待订阅确认
            sub_response = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"Subscription response: {sub_response}")
            
    except Exception as e:
        print(f"Alpaca WebSocket test failed: {e}")

async def main():
    print("Starting WebSocket dual endpoint test")
    print("=" * 50)
    
    # 测试生产端点
    await test_production_websocket()
    
    print("\n" + "=" * 50)
    
    # 测试Alpaca端点
    await test_alpaca_websocket()
    
    print("\n" + "=" * 50)
    print("WebSocket dual endpoint test completed!")

if __name__ == "__main__":
    asyncio.run(main())