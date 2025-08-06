#!/usr/bin/env python3
"""
详细的WebSocket连接测试脚本
"""
import asyncio
import websockets
import json
import time
from datetime import datetime

async def detailed_websocket_test():
    """执行详细的WebSocket连接测试"""
    
    print("=== WebSocket详细测试开始 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        uri = 'ws://localhost:8090/api/v1/ws/market-data'
        print(f"连接到: {uri}")
        
        # 连接WebSocket
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket连接建立成功")
            
            # 1. 接收欢迎消息
            print("\n--- 步骤1: 接收欢迎消息 ---")
            welcome_raw = await websocket.recv()
            welcome_data = json.loads(welcome_raw)
            
            print(f"客户端ID: {welcome_data.get('client_id', 'N/A')}")
            print(f"消息: {welcome_data.get('message', 'N/A')}")
            print(f"数据源: {welcome_data.get('data_source', 'N/A')}")
            
            # 账户信息
            account_info = welcome_data.get('account_info', {})
            print(f"账户ID: {account_info.get('account_id', 'N/A')}")
            print(f"账户层级: {account_info.get('tier', 'N/A')}")
            print(f"模拟交易: {account_info.get('paper_trading', 'N/A')}")
            
            # 能力信息
            capabilities = welcome_data.get('capabilities', {})
            print(f"股票数据: {capabilities.get('stock_data', False)}")
            print(f"期权数据: {capabilities.get('option_data', False)}")
            print(f"实时数据: {capabilities.get('real_time', False)}")
            print(f"股票端点: {capabilities.get('stock_endpoint', 'N/A')}")
            print(f"期权端点: {capabilities.get('option_endpoint', 'N/A')}")
            
            # 默认符号
            default_stocks = welcome_data.get('default_stocks', [])
            default_options = welcome_data.get('default_options', [])
            print(f"默认股票数量: {len(default_stocks)}")
            print(f"默认期权数量: {len(default_options)}")
            
            # 2. 接收订阅确认
            print("\n--- 步骤2: 接收订阅确认 ---")
            subscription_raw = await websocket.recv()
            subscription_data = json.loads(subscription_raw)
            
            print(f"订阅类型: {subscription_data.get('type', 'N/A')}")
            print(f"消息: {subscription_data.get('message', 'N/A')}")
            print(f"状态: {subscription_data.get('status', 'N/A')}")
            
            subscribed_symbols = subscription_data.get('subscribed_symbols', [])
            print(f"订阅符号总数: {len(subscribed_symbols)}")
            
            # 分类符号
            stock_symbols = [s for s in subscribed_symbols if len(s) <= 10]
            option_symbols = [s for s in subscribed_symbols if len(s) > 10]
            print(f"股票符号: {len(stock_symbols)} ({stock_symbols[:3]}...)")
            print(f"期权符号: {len(option_symbols)} ({option_symbols[:2]}...)")
            
            # 3. 等待实时数据
            print("\n--- 步骤3: 等待实时数据流 ---")
            print("监听15秒，期待接收实时数据...")
            
            data_messages = []
            error_messages = []
            other_messages = []
            
            for i in range(15):  # 监听15秒
                try:
                    message_raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message_data = json.loads(message_raw)
                    
                    msg_type = message_data.get('type', 'unknown')
                    
                    if msg_type in ['quote', 'trade']:
                        # 市场数据
                        symbol = message_data.get('symbol', 'N/A')
                        data_type = message_data.get('data_type', 'N/A')
                        timestamp = message_data.get('timestamp', 'N/A')
                        
                        data_messages.append({
                            'type': msg_type,
                            'symbol': symbol,
                            'data_type': data_type,
                            'timestamp': timestamp
                        })
                        
                        print(f"📊 {data_type.upper()} {msg_type.upper()}: {symbol} @ {timestamp}")
                        
                    elif msg_type == 'error':
                        # 错误消息
                        error_msg = message_data.get('message', 'Unknown error')
                        error_messages.append(error_msg)
                        print(f"❌ 错误: {error_msg}")
                        
                    else:
                        # 其他消息
                        other_messages.append(message_data)
                        print(f"ℹ️ 其他消息: {msg_type}")
                        
                except asyncio.TimeoutError:
                    # 超时是正常的，继续等待
                    if i % 5 == 4:  # 每5秒显示一次进度
                        print(f"⏳ 等待中... ({i+1}/15秒)")
                    continue
                except Exception as e:
                    print(f"❌ 接收消息错误: {e}")
                    break
            
            # 4. 测试结果总结
            print("\n=== 测试结果总结 ===")
            print(f"✓ WebSocket连接: 成功")
            print(f"✓ 欢迎消息: 已接收")
            print(f"✓ 订阅确认: 已接收")
            print(f"📊 数据消息: {len(data_messages)} 条")
            print(f"❌ 错误消息: {len(error_messages)} 条")
            print(f"ℹ️ 其他消息: {len(other_messages)} 条")
            
            if data_messages:
                print("\n--- 收到的数据样本 ---")
                for i, msg in enumerate(data_messages[:5]):  # 显示前5条
                    print(f"{i+1}. {msg['data_type']} {msg['type']}: {msg['symbol']}")
            
            if error_messages:
                print("\n--- 错误消息 ---")
                for i, error in enumerate(error_messages[:3]):  # 显示前3条
                    print(f"{i+1}. {error}")
            
            # 5. 诊断分析
            print("\n=== 诊断分析 ===")
            if len(data_messages) > 0:
                print("✅ WebSocket数据流正常工作")
                stock_count = len([m for m in data_messages if m['data_type'] == 'stock'])
                option_count = len([m for m in data_messages if m['data_type'] == 'option'])
                print(f"   - 股票数据: {stock_count} 条")
                print(f"   - 期权数据: {option_count} 条")
            else:
                print("⚠️ 没有收到实时数据，可能原因:")
                print("   - 非交易时间 (美股市场已关闭)")
                print("   - Alpaca WebSocket连接问题")
                print("   - API权限限制")
                print("   - 网络连接问题")
            
            if error_messages:
                print("⚠️ 发现错误消息，需要检查服务器日志")
            
            print("\n✓ 详细测试完成")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket连接意外关闭: {e}")
    except ConnectionRefusedError:
        print("❌ 无法连接到服务器 - 请确认服务器正在运行在端口8090")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("开始WebSocket详细测试...")
    asyncio.run(detailed_websocket_test())