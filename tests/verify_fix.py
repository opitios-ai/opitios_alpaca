#!/usr/bin/env python3
"""
验证WebSocket修复是否生效 - 使用FAKEPACA测试端点
"""
import asyncio
import websockets
import json
import requests
from datetime import datetime

async def verify_fakepaca_fix():
    """验证FAKEPACA修复"""
    print("=== 验证FAKEPACA修复 ===")
    
    try:
        # 获取真实API凭据
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            print(f"SUCCESS: 获取到真实API凭据: {credentials['account_name']}")
        else:
            print(f"ERROR: 获取API凭据失败: {response.status_code}")
            return False
        
        # 连接到测试端点
        test_uri = "wss://stream.data.alpaca.markets/v2/test"
        print(f"连接到: {test_uri}")
        
        async with websockets.connect(test_uri) as websocket:
            print("SUCCESS: 连接成功")
            
            # 接收欢迎消息
            welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            welcome_data = json.loads(welcome_msg)
            print(f"欢迎消息: {welcome_data}")
            
            # 认证
            auth_message = {"action": "auth", "key": api_key, "secret": secret_key}
            await websocket.send(json.dumps(auth_message))
            
            # 接收认证响应
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_data = json.loads(auth_response)
            print(f"认证响应: {auth_data}")
            
            # 检查是否认证成功
            if isinstance(auth_data, list) and len(auth_data) > 0:
                auth_result = auth_data[0]
                if auth_result.get('T') == 'success' and 'authenticated' in str(auth_result.get('msg', '')):
                    print("SUCCESS: 认证成功!")
                    
                    # 使用正确的FAKEPACA代码订阅
                    subscribe_message = {
                        "action": "subscribe",
                        "trades": ["FAKEPACA"],
                        "quotes": ["FAKEPACA"], 
                        "bars": ["FAKEPACA"]
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    print(f"发送订阅消息: {subscribe_message}")
                    
                    # 接收订阅确认
                    sub_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    sub_data = json.loads(sub_response)
                    print(f"订阅确认: {sub_data}")
                    
                    # 尝试接收数据
                    print("等待FAKEPACA测试数据...")
                    data_received = False
                    
                    for i in range(5):  # 尝试接收5条消息
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=10)
                            data = json.loads(message)
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            
                            print(f"[{timestamp}] 收到数据: {data}")
                            data_received = True
                            
                            # 解析数据
                            if isinstance(data, list):
                                for item in data:
                                    msg_type = item.get('T', 'unknown')
                                    symbol = item.get('S', 'N/A')
                                    if symbol == 'FAKEPACA':
                                        print(f"  -> FAKEPACA数据类型: {msg_type}")
                                        if msg_type == 'q':
                                            print(f"     报价: 买${item.get('bp', 0):.2f} 卖${item.get('ap', 0):.2f}")
                                        elif msg_type == 't':
                                            print(f"     交易: ${item.get('p', 0):.2f} x{item.get('s', 0)}")
                                        elif msg_type == 'b':
                                            print(f"     K线: 开${item.get('o', 0):.2f} 收${item.get('c', 0):.2f}")
                        
                        except asyncio.TimeoutError:
                            print("等待数据超时...")
                            break
                        except Exception as e:
                            print(f"接收数据错误: {e}")
                            break
                    
                    return data_received
                else:
                    print(f"认证失败: {auth_result}")
                    return False
            else:
                print(f"认证响应格式错误: {auth_data}")
                return False
                
    except Exception as e:
        print(f"连接错误: {e}")
        return False

async def main():
    """主函数"""
    print("开始验证FAKEPACA修复...")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = await verify_fakepaca_fix()
    
    print("\n=== 修复验证结果 ===")
    if success:
        print("✅ SUCCESS: FAKEPACA修复成功！现在可以接收测试数据")
        print("✅ 测试端点使用正确的FAKEPACA股票代码")
        print("✅ WebSocket连接、认证、订阅都正常工作")
        print("✅ 真实API凭据正确应用")
    else:
        print("❌ FAILED: 仍需进一步修复")
    
    print("\n💡 现在可以打开浏览器访问: http://localhost:8091/static/websocket_test.html")
    print("💡 点击'连接测试端点'按钮，应该能看到FAKEPACA数据流！")

if __name__ == "__main__":
    asyncio.run(main())