#!/usr/bin/env python3
"""
测试修复的WebSocket实现
"""

import asyncio
import websockets
import json
import time
from datetime import datetime

async def test_websocket_client():
    """测试WebSocket客户端"""
    uri = "ws://localhost:8090/api/v1/ws/market-data"
    
    print(f"🔗 连接到WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功!")
            
            # 等待欢迎消息
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            print(f"📨 欢迎消息: {json.dumps(welcome_data, indent=2, ensure_ascii=False)}")
            
            # 发送状态请求
            status_request = {
                "type": "status"
            }
            await websocket.send(json.dumps(status_request))
            print("📤 已发送状态请求")
            
            # 接收消息
            message_count = 0
            start_time = time.time()
            
            while message_count < 20:  # 接收20条消息后退出
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    message_count += 1
                    
                    msg_type = data.get("type")
                    timestamp = data.get("timestamp", "")
                    
                    if msg_type == "status_response":
                        print(f"📊 状态响应: {json.dumps(data['status'], indent=2, ensure_ascii=False)}")
                    elif msg_type == "quote":
                        symbol = data.get("symbol")
                        bid = data.get("bid_price")
                        ask = data.get("ask_price")
                        source = data.get("source")
                        print(f"💰 报价 [{source}] {symbol}: Bid=${bid}, Ask=${ask}")
                    elif msg_type == "trade":
                        symbol = data.get("symbol")
                        price = data.get("price")
                        size = data.get("size")
                        source = data.get("source")
                        print(f"📈 交易 [{source}] {symbol}: ${price} x {size}")
                    elif msg_type == "bar":
                        symbol = data.get("symbol")
                        close = data.get("close")
                        volume = data.get("volume")
                        source = data.get("source")
                        print(f"📊 K线 [{source}] {symbol}: Close=${close}, Vol={volume}")
                    elif msg_type == "trade_update":
                        event = data.get("event")
                        symbol = data.get("symbol")
                        side = data.get("side")
                        qty = data.get("qty")
                        print(f"🔄 交易更新: {event} - {symbol} {side} {qty}")
                    elif msg_type == "ping":
                        # 响应ping
                        pong_response = {
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send(json.dumps(pong_response))
                        print("🏓 收到ping，已发送pong")
                    else:
                        print(f"📨 消息 [{msg_type}]: {json.dumps(data, ensure_ascii=False)}")
                    
                except asyncio.TimeoutError:
                    print("⏰ 接收超时，继续等待...")
                    continue
            
            elapsed_time = time.time() - start_time
            print(f"\n📊 测试完成:")
            print(f"   - 接收消息数: {message_count}")
            print(f"   - 运行时间: {elapsed_time:.2f}秒")
            print(f"   - 平均消息频率: {message_count/elapsed_time:.2f}消息/秒")
            
    except Exception as e:
        print(f"❌ WebSocket测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_rest_api():
    """测试REST API状态"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # 测试WebSocket状态端点
            async with session.get("http://localhost:8090/api/v1/ws/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"🌐 WebSocket状态: {json.dumps(data, indent=2, ensure_ascii=False)}")
                else:
                    print(f"❌ WebSocket状态请求失败: {response.status}")
                    
            # 测试健康检查
            async with session.get("http://localhost:8090/api/v1/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"💚 健康检查: {json.dumps(data, indent=2, ensure_ascii=False)}")
                else:
                    print(f"❌ 健康检查失败: {response.status}")
                    
    except Exception as e:
        print(f"❌ REST API测试失败: {e}")

async def main():
    """主测试函数"""
    print("🚀 开始测试修复的WebSocket实现")
    print("=" * 50)
    
    # 1. 测试REST API
    print("1️⃣ 测试REST API...")
    await test_rest_api()
    
    print("\n" + "=" * 50)
    
    # 2. 测试WebSocket
    print("2️⃣ 测试WebSocket连接...")
    await test_websocket_client()
    
    print("\n🎉 测试完成!")

if __name__ == "__main__":
    asyncio.run(main())