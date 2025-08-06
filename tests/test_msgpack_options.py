#!/usr/bin/env python3
"""
Test MsgPack Option WebSocket Implementation
测试MsgPack期权WebSocket实现
"""
import asyncio
import websockets
import msgpack
import requests
import json
from datetime import datetime

async def test_msgpack_option_websocket():
    """测试MsgPack期权WebSocket端点"""
    print("=== 测试MsgPack期权WebSocket端点 ===")
    
    try:
        # 获取真实API凭据
        print("📡 获取API凭据...")
        response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
        if response.status_code == 200:
            credentials = response.json()
            api_key = credentials['api_key']
            secret_key = credentials['secret_key']
            option_ws_url = credentials['endpoints']['option_ws']
            print(f"✅ 获取凭据成功: {credentials['account_name']}")
            print(f"🔗 期权端点: {option_ws_url}")
        else:
            print(f"❌ 获取API凭据失败: {response.status_code}")
            return False
        
        # 连接期权WebSocket
        print(f"🔌 连接到期权WebSocket: {option_ws_url}")
        
        async with websockets.connect(option_ws_url) as websocket:
            print("✅ WebSocket连接成功")
            
            # 第一步：接收欢迎消息
            try:
                welcome_data = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"📨 收到欢迎消息: {type(welcome_data)} - 长度: {len(welcome_data) if hasattr(welcome_data, '__len__') else 'N/A'}")
                
                # 尝试解析欢迎消息
                if isinstance(welcome_data, bytes):
                    try:
                        welcome_msg = msgpack.unpackb(welcome_data)
                        print(f"🎉 MsgPack解析欢迎消息成功: {welcome_msg}")
                    except Exception as e:
                        print(f"⚠️ MsgPack解析欢迎消息失败: {e}")
                        try:
                            welcome_msg = json.loads(welcome_data.decode())
                            print(f"📄 JSON解析欢迎消息成功: {welcome_msg}")
                        except Exception as e2:
                            print(f"❌ 欢迎消息解析完全失败: {e2}")
                            welcome_msg = None
                else:
                    try:
                        welcome_msg = json.loads(welcome_data)
                        print(f"📄 JSON解析欢迎消息: {welcome_msg}")
                    except Exception as e:
                        print(f"❌ 欢迎消息解析失败: {e}")
                        welcome_msg = None
                
            except asyncio.TimeoutError:
                print("⏰ 等待欢迎消息超时")
                welcome_msg = None
            
            # 第二步：发送认证消息 (使用MsgPack)
            print("🔐 发送MsgPack格式认证消息...")
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            
            try:
                # 打包为MsgPack格式
                auth_packed = msgpack.packb(auth_message)
                await websocket.send(auth_packed)
                print(f"📤 已发送MsgPack认证消息 (大小: {len(auth_packed)} bytes)")
                
                # 等待认证响应
                auth_response = await asyncio.wait_for(websocket.recv(), timeout=15)
                print(f"📥 收到认证响应: {type(auth_response)} - 大小: {len(auth_response) if hasattr(auth_response, '__len__') else 'N/A'}")
                
                # 解析认证响应
                auth_result = None
                if isinstance(auth_response, bytes):
                    try:
                        auth_result = msgpack.unpackb(auth_response)
                        print(f"✅ MsgPack解析认证响应: {auth_result}")
                    except Exception as e:
                        print(f"⚠️ MsgPack解析认证响应失败: {e}")
                        try:
                            auth_result = json.loads(auth_response.decode())
                            print(f"📄 JSON解析认证响应: {auth_result}")
                        except Exception as e2:
                            print(f"❌ 认证响应解析完全失败: {e2}")
                else:
                    try:
                        auth_result = json.loads(auth_response)
                        print(f"📄 JSON解析认证响应: {auth_result}")
                    except Exception as e:
                        print(f"❌ 认证响应解析失败: {e}")
                
                # 检查认证是否成功
                auth_success = False
                if auth_result:
                    if isinstance(auth_result, list) and len(auth_result) > 0:
                        first_result = auth_result[0]
                        if first_result.get('T') == 'success' and 'authenticated' in str(first_result.get('msg', '')):
                            auth_success = True
                            print("🎉 认证成功!")
                    elif isinstance(auth_result, dict):
                        if auth_result.get('T') == 'success' or 'authenticated' in str(auth_result.get('msg', '')):
                            auth_success = True
                            print("🎉 认证成功!")
                
                if not auth_success:
                    print(f"❌ 认证失败: {auth_result}")
                    return False
                
            except asyncio.TimeoutError:
                print("⏰ 认证响应超时")
                return False
            except Exception as e:
                print(f"❌ 认证过程错误: {e}")
                return False
            
            # 第三步：订阅期权数据 (使用MsgPack)
            print("📊 发送期权订阅消息...")
            test_option_symbols = [
                'UNIT250815C00007000',
                'TSLA250808C00310000', 
                'AAPL250808C00210000'
            ]
            
            subscribe_message = {
                "action": "subscribe",
                "trades": test_option_symbols[:2],  # 只订阅前两个避免过多数据
                "quotes": test_option_symbols[:2]
            }
            
            try:
                # 打包为MsgPack格式
                subscribe_packed = msgpack.packb(subscribe_message)
                await websocket.send(subscribe_packed)
                print(f"📤 已发送MsgPack订阅消息: {test_option_symbols[:2]}")
                
                # 等待订阅确认
                sub_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"📥 收到订阅响应: {type(sub_response)}")
                
                # 解析订阅响应
                if isinstance(sub_response, bytes):
                    try:
                        sub_result = msgpack.unpackb(sub_response)
                        print(f"✅ MsgPack解析订阅响应: {sub_result}")
                    except Exception as e:
                        print(f"⚠️ MsgPack解析订阅响应失败: {e}")
                else:
                    try:
                        sub_result = json.loads(sub_response)
                        print(f"📄 JSON解析订阅响应: {sub_result}")
                    except Exception as e:
                        print(f"❌ 订阅响应解析失败: {e}")
                
            except asyncio.TimeoutError:
                print("⏰ 订阅响应超时")
            except Exception as e:
                print(f"❌ 订阅过程错误: {e}")
            
            # 第四步：尝试接收期权数据
            print("📈 等待期权市场数据...")
            data_received = False
            
            for i in range(10):  # 尝试接收10条消息
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=20)
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    
                    print(f"[{timestamp}] 收到消息 #{i+1}: {type(message)}")
                    
                    # 解析数据
                    parsed_data = None
                    if isinstance(message, bytes):
                        try:
                            parsed_data = msgpack.unpackb(message)
                            print(f"  ✅ MsgPack解析成功: {type(parsed_data)}")
                            data_received = True
                            
                            # 分析数据结构
                            if isinstance(parsed_data, list):
                                print(f"    📋 收到 {len(parsed_data)} 条记录")
                                for idx, item in enumerate(parsed_data[:3]):  # 只显示前3条
                                    if isinstance(item, dict):
                                        msg_type = item.get('T', 'unknown')
                                        symbol = item.get('S', 'N/A')
                                        print(f"      [{idx}] 类型: {msg_type}, 代码: {symbol}")
                                        
                                        if msg_type == 'q':  # Quote
                                            bid = item.get('bp', 'N/A')
                                            ask = item.get('ap', 'N/A')
                                            print(f"           报价: 买盘${bid} 卖盘${ask}")
                                        elif msg_type == 't':  # Trade  
                                            price = item.get('p', 'N/A')
                                            size = item.get('s', 'N/A')
                                            print(f"           交易: ${price} x{size}")
                            elif isinstance(parsed_data, dict):
                                msg_type = parsed_data.get('T', 'unknown')
                                print(f"    📦 单条消息: {msg_type}")
                            else:
                                print(f"    📦 其他数据类型: {parsed_data}")
                                
                        except Exception as e:
                            print(f"  ❌ MsgPack解析失败: {e}")
                            # 尝试文本解析
                            try:
                                text_data = message.decode('utf-8')
                                print(f"    📄 文本内容: {text_data[:100]}...")
                            except:
                                print(f"    🔢 二进制数据长度: {len(message)}")
                    else:
                        try:
                            parsed_data = json.loads(message)
                            print(f"  📄 JSON解析成功: {parsed_data}")
                            data_received = True
                        except Exception as e:
                            print(f"  ❌ JSON解析失败: {e}")
                            print(f"    📝 原始消息: {message}")
                    
                except asyncio.TimeoutError:
                    print(f"⏰ 等待第{i+1}条消息超时 (可能市场闭市)")
                    break
                except Exception as e:
                    print(f"❌ 接收第{i+1}条消息错误: {e}")
                    break
            
            return data_received
            
    except Exception as e:
        print(f"❌ WebSocket连接错误: {e}")
        return False

async def verify_msgpack_library():
    """验证MsgPack库可用性"""
    print("=== 验证MsgPack库 ===")
    try:
        # 测试基本打包解包
        test_data = {"test": "message", "number": 42, "array": [1, 2, 3]}
        packed = msgpack.packb(test_data)
        unpacked = msgpack.unpackb(packed)
        
        print(f"✅ MsgPack库工作正常")
        print(f"   原始数据: {test_data}")
        print(f"   打包后大小: {len(packed)} bytes")
        print(f"   解包后数据: {unpacked}")
        print(f"   数据一致性: {test_data == unpacked}")
        return True
    except ImportError:
        print("❌ MsgPack库未安装: pip install msgpack")
        return False
    except Exception as e:
        print(f"❌ MsgPack库测试失败: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 开始MsgPack期权WebSocket测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查服务器状态
    try:
        health_response = requests.get("http://localhost:8091/api/v1/health", timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"🖥️ 服务器状态: {health_data['status']}")
        else:
            print(f"⚠️ 服务器健康检查失败: {health_response.status_code}")
            return
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}")
        return
    
    # 验证MsgPack库
    msgpack_ok = await verify_msgpack_library()
    if not msgpack_ok:
        print("❌ MsgPack库不可用，无法继续测试")
        return
    
    print()
    
    # 执行期权WebSocket测试
    success = await test_msgpack_option_websocket()
    
    print()
    print("=== 测试结果总结 ===")
    if success:
        print("🎉 SUCCESS: MsgPack期权WebSocket测试成功!")
        print("✅ WebSocket连接正常")
        print("✅ MsgPack编码/解码工作")
        print("✅ 认证流程成功")
        print("✅ 期权数据接收成功")
        print()
        print("💡 现在可以访问: http://localhost:8091/static/websocket_test.html")
        print("💡 点击'连接期权端点'应该能正常工作!")
    else:
        print("❌ FAILED: 测试未完全成功")
        print("🔍 请检查:")
        print("   - API连接限制 (Error 406)")
        print("   - 市场开放时间")
        print("   - 网络连接")
        print("   - 期权数据订阅权限")

if __name__ == "__main__":
    asyncio.run(main())