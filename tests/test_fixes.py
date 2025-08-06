#!/usr/bin/env python3
"""
测试修复后的WebSocket连接
"""

import asyncio
import websockets
import json
import time
import aiohttp
from datetime import datetime

async def test_jwt_endpoint():
    """测试JWT端点"""
    print("🔑 测试JWT Token端点...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8090/api/v1/auth/demo-token') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get('access_token', '')
                    print(f"✅ JWT Token获取成功: {token[:50]}...")
                    return token
                else:
                    print(f"❌ JWT Token获取失败: {resp.status}")
                    return None
    except Exception as e:
        print(f"❌ JWT请求错误: {e}")
        return None

async def test_websocket_connection():
    """测试WebSocket连接"""
    print("\n🌐 测试WebSocket连接...")
    try:
        async with websockets.connect("ws://localhost:8090/api/v1/ws/market-data") as websocket:
            print("✅ WebSocket连接成功!")
            
            # 等待欢迎消息
            try:
                welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📨 接收到消息: {welcome_msg}")
                
                data = json.loads(welcome_msg)
                if data.get('type') == 'welcome':
                    print("✅ 收到欢迎消息")
                    if 'default_stocks' in data:
                        print(f"📈 默认股票: {data['default_stocks']}")
                    if 'default_options' in data:
                        print(f"📊 默认期权: {data['default_options']}")
                else:
                    print(f"📊 收到数据消息: {data.get('type', 'unknown')}")
                
                return True
                
            except asyncio.TimeoutError:
                print("⏰ 等待消息超时")
                return False
                
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

async def test_favicon_access():
    """测试favicon访问"""
    print("\n🎨 测试favicon访问...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8090/favicon.ico') as resp:
                print(f"📄 Favicon状态码: {resp.status}")
                if resp.status in [200, 404]:  # 404也是正常的，表示没有401错误
                    print("✅ Favicon访问正常 (无认证错误)")
                    return True
                else:
                    print(f"⚠️ Favicon状态: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ Favicon测试错误: {e}")
        return False

async def test_websocket_page():
    """测试WebSocket测试页面"""
    print("\n📄 测试WebSocket测试页面...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8090/static/websocket_test.html') as resp:
                if resp.status == 200:
                    content = await resp.text()
                    if 'ws://localhost:8090' in content:
                        print("✅ 测试页面端口已更新为8090")
                        return True
                    else:
                        print("⚠️ 测试页面端口未更新")
                        return False
                else:
                    print(f"❌ 测试页面访问失败: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ 测试页面检查错误: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始修复验证测试")
    print("=" * 50)
    
    # 运行所有测试
    tests = [
        ("JWT Token获取", test_jwt_endpoint()),
        ("WebSocket连接", test_websocket_connection()),
        ("Favicon访问", test_favicon_access()),
        ("测试页面", test_websocket_page())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"\n🧪 运行测试: {test_name}")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 测试结果总结:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{len(results)} 测试通过")
    
    if passed == len(results):
        print("🎉 所有修复验证通过！系统已就绪")
    else:
        print("⚠️ 部分测试失败，可能需要重新启动服务器")
        print("💡 建议执行: Ctrl+C 停止服务器，然后重新运行 python main.py")

if __name__ == "__main__":
    asyncio.run(main())