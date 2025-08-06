#!/usr/bin/env python3
"""
简化的Alpaca WebSocket测试，专注于FAKEPACA测试端点
"""
import asyncio
import websockets
import json
import requests
from datetime import datetime

async def test_alpaca_websocket_simple():
    """测试Alpaca官方测试端点 - 使用FAKEPACA"""
    print("=== 测试Alpaca官方测试端点 (FAKEPACA) ===")
    
    try:
        # 获取真实API凭据
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            print(f"✅ 获取真实API凭据成功: {credentials['account_name']}")
            print(f"🔑 API Key: {api_key[:10]}...")
        else:
            print(f"❌ 获取API凭据失败: {response.status_code}")
            return
        
        # 连接Alpaca测试WebSocket (直接使用文档中的测试端点)
        test_uri = "wss://stream.data.alpaca.markets/v2/test"
        print(f"🔌 正在连接到: {test_uri}")
        
        async with websockets.connect(test_uri) as websocket:
            print("✅ 成功连接到Alpaca官方测试WebSocket")
            
            # 接收连接消息
            welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            welcome_data = json.loads(welcome_msg)
            print(f"📨 欢迎消息: {welcome_data}")
            
            # 发送认证消息
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            
            await websocket.send(json.dumps(auth_message))
            print(f"📤 发送认证消息...")
            
            # 接收认证响应
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_data = json.loads(auth_response)
            print(f"📥 认证响应: {auth_data}")
            
            # 检查认证是否成功
            if isinstance(auth_data, list) and len(auth_data) > 0:
                auth_result = auth_data[0]
                if auth_result.get('T') == 'success' and 'authenticated' in str(auth_result.get('msg', '')):
                    print("✅ 认证成功!")
                    
                    # 订阅FAKEPACA数据 (使用文档示例)
                    subscribe_message = {
                        "action": "subscribe",
                        "trades": ["FAKEPACA"],
                        "quotes": ["FAKEPACA"],
                        "bars": ["FAKEPACA"]
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    print(f"📤 发送订阅消息: {subscribe_message}")
                    
                    # 接收订阅确认
                    sub_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    sub_data = json.loads(sub_response)
                    print(f"📥 订阅确认: {sub_data}")
                    
                    # 接收实时数据
                    print("🎯 开始接收FAKEPACA实时测试数据...")
                    for i in range(10):  # 接收10条消息
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
                                        print(f"📊 [{timestamp}] 报价 {symbol}: 买盘${bid:.2f} 卖盘${ask:.2f}")
                                    elif msg_type == 't':  # Trade
                                        price = item.get('p', 0)
                                        size = item.get('s', 0)
                                        print(f"💰 [{timestamp}] 交易 {symbol}: ${price:.2f} x{size}")
                                    elif msg_type == 'b':  # Bar
                                        open_price = item.get('o', 0)
                                        close_price = item.get('c', 0)
                                        volume = item.get('v', 0)
                                        print(f"📈 [{timestamp}] K线 {symbol}: 开${open_price:.2f} 收${close_price:.2f} 量{volume}")
                                    else:
                                        print(f"📦 [{timestamp}] 数据 {msg_type}: {item}")
                            else:
                                print(f"📦 [{timestamp}] 原始数据: {data}")
                                
                        except asyncio.TimeoutError:
                            print("⏰ 数据接收超时，可能是市场闭市时间")
                            break
                        except Exception as e:
                            print(f"❌ 数据接收错误: {e}")
                            break
                else:
                    print(f"❌ 认证失败: {auth_result}")
            else:
                print(f"❌ 认证响应格式异常: {auth_data}")
                    
    except Exception as e:
        print(f"❌ WebSocket连接错误: {e}")

async def main():
    """主函数"""
    print("Starting Alpaca FAKEPACA test...")
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查服务器状态
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
    
    # 执行WebSocket测试
    await test_alpaca_websocket_simple()
    
    print("\nTest completed!")
    print("If you see FAKEPACA data, WebSocket connection and authentication are working!")

if __name__ == "__main__":
    asyncio.run(main())