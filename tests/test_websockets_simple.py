#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket双端点简单测试脚本
"""

import asyncio
import websockets
import json
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebSocketTester:
    def __init__(self):
        self.production_url = "ws://localhost:8091/api/v1/ws/market-data"
        self.test_url = "wss://stream.data.alpaca.markets/v2/test"
        
        # 测试结果
        self.results = {
            "production": {
                "connected": False,
                "messages_received": 0,
                "symbols_received": set(),
                "connection_time": 0,
                "errors": []
            },
            "alpaca_test": {
                "connected": False,
                "messages_received": 0,
                "symbols_received": set(),
                "connection_time": 0,
                "errors": []
            }
        }
    
    async def test_production_endpoint(self, duration=30):
        """测试生产端点"""
        logger.info("开始测试生产端点...")
        start_time = time.time()
        
        try:
            async with websockets.connect(self.production_url) as websocket:
                connect_time = time.time() - start_time
                self.results["production"]["connection_time"] = connect_time
                self.results["production"]["connected"] = True
                
                logger.info(f"生产端点连接成功! 耗时: {connect_time:.3f}秒")
                
                # 接收消息
                end_time = time.time() + duration
                while time.time() < end_time:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5)
                        data = json.loads(message)
                        
                        self.results["production"]["messages_received"] += 1
                        
                        # 记录符号
                        if "symbol" in data:
                            self.results["production"]["symbols_received"].add(data["symbol"])
                        
                        # 打印关键消息
                        msg_type = data.get("type", "unknown")
                        if msg_type in ["welcome", "subscription"]:
                            logger.info(f"生产端点 - {msg_type}: {data.get('message', str(data))}")
                        elif msg_type == "quote":
                            symbol = data.get("symbol", "UNKNOWN")
                            bid = data.get("bid_price", "N/A")
                            ask = data.get("ask_price", "N/A")
                            logger.info(f"生产端点 - 报价 {symbol}: Bid={bid}, Ask={ask}")
                            
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        self.results["production"]["errors"].append(str(e))
                        logger.warning(f"生产端点消息处理错误: {e}")
                        
        except Exception as e:
            self.results["production"]["errors"].append(str(e))
            logger.error(f"生产端点连接失败: {e}")
    
    async def test_alpaca_endpoint(self, duration=30):
        """测试Alpaca测试端点"""
        logger.info("开始测试Alpaca测试端点...")
        start_time = time.time()
        
        try:
            async with websockets.connect(self.test_url) as websocket:
                connect_time = time.time() - start_time
                self.results["alpaca_test"]["connection_time"] = connect_time
                self.results["alpaca_test"]["connected"] = True
                
                logger.info(f"Alpaca端点连接成功! 耗时: {connect_time:.3f}秒")
                
                # 发送认证消息
                auth_msg = {
                    "action": "auth",
                    "key": "test_api_key",
                    "secret": "test_secret_key"
                }
                await websocket.send(json.dumps(auth_msg))
                
                # 接收消息
                end_time = time.time() + duration
                while time.time() < end_time:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5)
                        data_list = json.loads(message)
                        
                        if isinstance(data_list, list):
                            for data in data_list:
                                self.results["alpaca_test"]["messages_received"] += 1
                                self._process_alpaca_message(data)
                        else:
                            self.results["alpaca_test"]["messages_received"] += 1
                            self._process_alpaca_message(data_list)
                            
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        self.results["alpaca_test"]["errors"].append(str(e))
                        logger.warning(f"Alpaca端点消息处理错误: {e}")
                        
        except Exception as e:
            self.results["alpaca_test"]["errors"].append(str(e))
            logger.error(f"Alpaca端点连接失败: {e}")
    
    def _process_alpaca_message(self, data):
        """处理Alpaca消息"""
        msg_type = data.get("T", "unknown")
        
        if msg_type == "success":
            logger.info(f"Alpaca端点 - 认证成功: {data.get('msg', '')}")
        elif msg_type == "error":
            logger.warning(f"Alpaca端点 - 错误: {data.get('msg', '')}")
        elif msg_type == "q":  # Quote
            symbol = data.get("S", "UNKNOWN")
            self.results["alpaca_test"]["symbols_received"].add(symbol)
            bid = data.get("bp", "N/A")
            ask = data.get("ap", "N/A")
            logger.info(f"Alpaca端点 - 报价 {symbol}: Bid={bid}, Ask={ask}")
        elif msg_type == "subscription":
            logger.info(f"Alpaca端点 - 订阅确认: {data}")
    
    async def run_tests(self, duration=30):
        """运行所有测试"""
        logger.info(f"开始WebSocket双端点测试 (持续{duration}秒)...")
        
        # 并行测试两个端点
        tasks = [
            self.test_production_endpoint(duration),
            self.test_alpaca_endpoint(duration)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.print_results()
    
    def print_results(self):
        """打印测试结果"""
        print("\n" + "="*60)
        print("WebSocket 双端点测试结果报告")
        print("="*60)
        
        # 生产端点结果
        prod = self.results["production"]
        print(f"\n【生产端点】 {self.production_url}")
        print(f"  连接状态: {'成功' if prod['connected'] else '失败'}")
        print(f"  连接时间: {prod['connection_time']:.3f}秒")
        print(f"  接收消息: {prod['messages_received']:,}条")
        print(f"  符号数量: {len(prod['symbols_received'])}个")
        if prod['symbols_received']:
            print(f"  符号列表: {', '.join(sorted(prod['symbols_received']))}")
        if prod['errors']:
            print(f"  错误信息: {len(prod['errors'])}个错误")
            for error in prod['errors'][:3]:  # 只显示前3个错误
                print(f"    - {error}")
        
        # Alpaca端点结果
        alpaca = self.results["alpaca_test"]
        print(f"\n【Alpaca测试端点】 {self.test_url}")
        print(f"  连接状态: {'成功' if alpaca['connected'] else '失败'}")
        print(f"  连接时间: {alpaca['connection_time']:.3f}秒")
        print(f"  接收消息: {alpaca['messages_received']:,}条")
        print(f"  符号数量: {len(alpaca['symbols_received'])}个")
        if alpaca['symbols_received']:
            print(f"  符号列表: {', '.join(sorted(alpaca['symbols_received']))}")
        if alpaca['errors']:
            print(f"  错误信息: {len(alpaca['errors'])}个错误")
            for error in alpaca['errors'][:3]:
                print(f"    - {error}")
        
        # 性能比较
        print(f"\n【性能对比】")
        if prod['connected'] and alpaca['connected']:
            prod_rate = prod['messages_received'] / max(prod['connection_time'], 0.001)
            alpaca_rate = alpaca['messages_received'] / max(alpaca['connection_time'], 0.001)
            
            faster_endpoint = "生产端点" if prod_rate > alpaca_rate else "Alpaca端点"
            print(f"  消息速率: 生产端点 {prod_rate:.2f} msg/s vs Alpaca端点 {alpaca_rate:.2f} msg/s")
            print(f"  推荐选择: {faster_endpoint}")
        
        # 总结
        success_count = sum(1 for r in self.results.values() if r['connected'])
        total_messages = sum(r['messages_received'] for r in self.results.values())
        total_symbols = len(set().union(*(r['symbols_received'] for r in self.results.values())))
        
        print(f"\n【测试总结】")
        print(f"  成功连接: {success_count}/2 个端点")
        print(f"  总消息数: {total_messages:,} 条")
        print(f"  总符号数: {total_symbols} 个")
        print(f"  测试状态: {'通过' if success_count >= 1 else '失败'}")
        print("="*60)

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='WebSocket双端点测试')
    parser.add_argument('--duration', type=int, default=30, help='测试持续时间(秒)')
    args = parser.parse_args()
    
    tester = WebSocketTester()
    await tester.run_tests(args.duration)

if __name__ == "__main__":
    asyncio.run(main())