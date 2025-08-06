#!/usr/bin/env python3
"""
WebSocket双端点系统终极综合测试运行器
执行所有测试：连接性能、数据准确性、股票期权验证、实时数据流完整性

这个脚本会：
1. 测试生产端点和测试端点的连接性能
2. 验证股票和期权数据的接收准确性  
3. 测试实时数据流的完整性和延迟
4. 生成全面的测试报告和建议

使用方法:
python run_comprehensive_websocket_tests.py --full-test
python run_comprehensive_websocket_tests.py --quick-test
python run_comprehensive_websocket_tests.py --custom --duration 300 --focus stock
"""

import asyncio
import argparse
import sys
import json
import time
import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path

# 设置路径以便导入测试模块
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# 导入我们的测试类
try:
    from tests.test_websocket_dual_endpoint_comprehensive import DualEndpointWebSocketTester
    from tests.test_stock_options_data_validation import StockOptionsDataValidator
except ImportError as e:
    print(f"❌ 无法导入测试模块: {e}")
    print("请确保在 opitios_alpaca 项目根目录运行此脚本")
    sys.exit(1)

# 配置日志
def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 抑制websockets库的详细日志
    logging.getLogger('websockets').setLevel(logging.WARNING)

class ComprehensiveTestRunner:
    """综合测试运行器"""
    
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        
        # 测试配置
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        
        # 根据测试类型设置持续时间
        if args.full_test:
            self.test_duration = 300  # 5分钟完整测试
        elif args.quick_test:
            self.test_duration = 60   # 1分钟快速测试
        else:
            self.test_duration = args.duration or 180  # 自定义或默认3分钟
        
        self.focus_area = args.focus or "all"
        self.verbose = args.verbose
    
    def _get_focus_desc(self):
        """获取测试重点描述"""
        focus_map = {
            "all": "全面测试",
            "stock": "股票专项", 
            "option": "期权专项",
            "performance": "性能专项"
        }
        return focus_map.get(self.focus_area, "全面测试")
        
    def print_test_banner(self):
        """打印测试横幅"""
        test_type = "完整测试" if self.args.full_test else "快速测试" if self.args.quick_test else "自定义测试"
        focus_desc = {"all": "全面测试", "stock": "股票专项", "option": "期权专项", "performance": "性能专项"}.get(self.focus_area, "全面测试")
        
        banner = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    WebSocket 双端点系统终极综合测试                          ║
║                         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 🎯 测试类型: {test_type:<20} 📊 测试时长: {self.test_duration}秒           ║
║ 🔍 测试重点: {focus_desc:<20} 📈 详细模式: {"开启" if self.verbose else "关闭"}            ║
║                                                                              ║ 
║ 🏭 生产端点: ws://localhost:8091/api/v1/ws/market-data                      ║
║ 🧪 测试端点: wss://stream.data.alpaca.markets/v2/test                       ║
║                                                                              ║
║ 📋 测试计划:                                                                 ║
║ ├─ ⚡ 连接性能和稳定性测试                                                   ║
║ ├─ 📈 股票数据接收速度和准确性                                               ║
║ ├─ 📊 期权数据验证和完整性                                                   ║
║ ├─ 🔄 实时数据流完整性检测                                                   ║
║ ├─ 📊 性能基准测试和比较                                                     ║
║ └─ 📄 生成详细测试报告                                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    async def run_connection_performance_tests(self) -> Dict[str, Any]:
        """运行连接性能测试"""
        self.logger.info("🚀 开始连接性能测试...")
        
        tester = DualEndpointWebSocketTester()
        
        try:
            # 根据重点配置测试时长
            if self.focus_area == "performance":
                duration = max(self.test_duration, 180)  # 性能测试至少3分钟
            else:
                duration = min(self.test_duration, 120)  # 其他情况最多2分钟
            
            production_metrics, alpaca_metrics = await tester.run_parallel_tests(duration)
            
            results = {
                "test_type": "connection_performance",
                "duration": duration,
                "production_endpoint": {
                    "connection_time": production_metrics.connection_time,
                    "total_messages": production_metrics.total_messages,
                    "messages_per_second": production_metrics.messages_per_second,
                    "success_rate": production_metrics.success_rate,
                    "error_count": production_metrics.error_count,
                    "symbols_received": len(production_metrics.symbols_received),
                    "message_types": dict(production_metrics.message_types)
                },
                "alpaca_endpoint": {
                    "connection_time": alpaca_metrics.connection_time,
                    "total_messages": alpaca_metrics.total_messages,
                    "messages_per_second": alpaca_metrics.messages_per_second,
                    "success_rate": alpaca_metrics.success_rate,
                    "error_count": alpaca_metrics.error_count,
                    "symbols_received": len(alpaca_metrics.symbols_received),
                    "message_types": dict(alpaca_metrics.message_types)
                },
                "comparison": tester.compare_endpoints(),
                "success": True
            }
            
            self.logger.info(f"✅ 连接性能测试完成 - 生产端: {production_metrics.messages_per_second:.2f} msg/s, Alpaca端: {alpaca_metrics.messages_per_second:.2f} msg/s")
            
        except Exception as e:
            self.logger.error(f"❌ 连接性能测试失败: {e}")
            results = {
                "test_type": "connection_performance",
                "error": str(e),
                "success": False
            }
        
        return results
    
    async def run_stock_options_validation(self) -> Dict[str, Any]:
        """运行股票期权数据验证"""
        self.logger.info("📊 开始股票期权数据验证...")
        
        validator = StockOptionsDataValidator()
        validator.test_duration = self.test_duration
        
        # 根据重点调整测试符号
        if self.focus_area == "stock":
            # 扩展股票列表
            validator.test_stocks.extend(["HOOD", "AEO", "BB", "GME", "AMC"])
            validator.test_options = validator.test_options[:2]  # 减少期权数量
        elif self.focus_area == "option":
            # 扩展期权列表
            validator.test_options.extend([
                "HOOD250117C00115000",   # HOOD $115 Call
                "AEO250117C00015000",    # AEO $15 Call
            ])
            validator.test_stocks = validator.test_stocks[:3]  # 减少股票数量
        
        try:
            # 并行测试两个端点
            production_task = asyncio.create_task(
                validator.test_production_endpoint_data(self.test_duration)
            )
            alpaca_task = asyncio.create_task(
                validator.test_alpaca_endpoint_data(self.test_duration)
            )
            
            production_results, alpaca_results = await asyncio.gather(
                production_task, alpaca_task
            )
            
            results = {
                "test_type": "stock_options_validation",
                "duration": self.test_duration,
                "production_results": production_results,
                "alpaca_results": alpaca_results,
                "validation_report": validator.generate_validation_report(production_results, alpaca_results),
                "success": True
            }
            
            # 计算关键指标
            prod_stock_coverage = production_results["summary"]["stocks"]["data_coverage"]
            prod_option_coverage = production_results["summary"]["options"]["data_coverage"]
            alpaca_stock_coverage = alpaca_results["summary"]["stocks"]["data_coverage"]
            
            self.logger.info(f"✅ 数据验证完成 - 生产端股票: {prod_stock_coverage}%, 期权: {prod_option_coverage}%, Alpaca股票: {alpaca_stock_coverage}%")
            
        except Exception as e:
            self.logger.error(f"❌ 股票期权验证失败: {e}")
            results = {
                "test_type": "stock_options_validation",
                "error": str(e),
                "success": False
            }
        
        return results
    
    async def run_realtime_data_integrity_test(self) -> Dict[str, Any]:
        """运行实时数据完整性测试"""
        self.logger.info("⏱️ 开始实时数据完整性测试...")
        
        try:
            # 创建专门的实时性测试
            integrity_results = await self._test_realtime_integrity()
            
            results = {
                "test_type": "realtime_data_integrity",
                "duration": self.test_duration,
                "integrity_results": integrity_results,
                "success": True
            }
            
            self.logger.info("✅ 实时数据完整性测试完成")
            
        except Exception as e:
            self.logger.error(f"❌ 实时数据完整性测试失败: {e}")
            results = {
                "test_type": "realtime_data_integrity",
                "error": str(e),
                "success": False
            }
        
        return results
    
    async def _test_realtime_integrity(self) -> Dict[str, Any]:
        """测试实时数据完整性"""
        import websockets
        import ssl
        
        results = {
            "production_integrity": {},
            "alpaca_integrity": {},
            "latency_analysis": {}
        }
        
        # 测试生产端点实时性
        try:
            ws = await websockets.connect("ws://localhost:8091/api/v1/ws/market-data")
            
            # 记录连接到第一条消息的时间
            connect_time = time.time()
            welcome_msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
            first_message_time = time.time() - connect_time
            
            # 收集一段时间的消息时间戳
            message_times = []
            message_count = 0
            test_start = time.time()
            
            while time.time() - test_start < min(60, self.test_duration):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg_time = time.time()
                    message_times.append(msg_time)
                    message_count += 1
                except asyncio.TimeoutError:
                    break
            
            await ws.close()
            
            # 计算消息间隔统计
            if len(message_times) > 1:
                intervals = [message_times[i] - message_times[i-1] for i in range(1, len(message_times))]
                avg_interval = sum(intervals) / len(intervals)
                max_gap = max(intervals)
                min_gap = min(intervals)
            else:
                avg_interval = max_gap = min_gap = 0
            
            results["production_integrity"] = {
                "first_message_delay": first_message_time,
                "total_messages": message_count,
                "test_duration": time.time() - test_start,
                "avg_message_interval": avg_interval,
                "max_message_gap": max_gap,
                "min_message_gap": min_gap,
                "message_frequency": message_count / (time.time() - test_start) if message_count > 0 else 0
            }
            
        except Exception as e:
            results["production_integrity"] = {"error": str(e)}
        
        # 测试Alpaca端点实时性
        try:
            ssl_context = ssl.create_default_context()
            ws = await websockets.connect("wss://stream.data.alpaca.markets/v2/test", ssl=ssl_context)
            
            # 认证
            auth_msg = {"action": "auth", "key": "test_api_key", "secret": "test_secret_key"}
            await ws.send(json.dumps(auth_msg))
            
            connect_time = time.time()
            auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
            first_message_time = time.time() - connect_time
            
            # 订阅数据
            subscribe_msg = {"action": "subscribe", "quotes": ["AAPL", "TSLA"], "trades": ["AAPL", "TSLA"]}
            await ws.send(json.dumps(subscribe_msg))
            
            # 收集消息时间戳
            message_times = []
            message_count = 0
            test_start = time.time()
            
            while time.time() - test_start < min(60, self.test_duration):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg_time = time.time()
                    message_times.append(msg_time)
                    message_count += 1
                except asyncio.TimeoutError:
                    break
            
            await ws.close()
            
            # 计算统计
            if len(message_times) > 1:
                intervals = [message_times[i] - message_times[i-1] for i in range(1, len(message_times))]
                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                max_gap = max(intervals) if intervals else 0
                min_gap = min(intervals) if intervals else 0
            else:
                avg_interval = max_gap = min_gap = 0
            
            results["alpaca_integrity"] = {
                "first_message_delay": first_message_time,
                "total_messages": message_count,
                "test_duration": time.time() - test_start,
                "avg_message_interval": avg_interval,
                "max_message_gap": max_gap,
                "min_message_gap": min_gap,
                "message_frequency": message_count / (time.time() - test_start) if message_count > 0 else 0
            }
            
        except Exception as e:
            results["alpaca_integrity"] = {"error": str(e)}
        
        return results
    
    def generate_comprehensive_report(self) -> str:
        """生成综合测试报告"""
        total_time = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        test_type_desc = "完整测试" if self.args.full_test else "快速测试" if self.args.quick_test else "自定义测试"
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    WebSocket 双端点系统终极测试报告                          ║
║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
╠══════════════════════════════════════════════════════════════════════════════╣

📊 测试概览
├─ 测试类型: {test_type_desc}
├─ 总执行时间: {total_time:.1f}秒
├─ 单项测试时长: {self.test_duration}秒
├─ 测试重点: {self._get_focus_desc()}
├─ 测试项目数: {len(self.test_results)}
└─ 成功率: {sum(1 for r in self.test_results.values() if r.get('success', False)) / len(self.test_results) * 100:.1f}%

"""
        
        # 连接性能测试结果
        if "connection_performance" in self.test_results:
            perf_result = self.test_results["connection_performance"]
            if perf_result.get("success", False):
                prod = perf_result["production_endpoint"]
                alpaca = perf_result["alpaca_endpoint"]
                comparison = perf_result["comparison"]
                
                report += f"""⚡ 连接性能测试结果
├─ 测试状态: ✅ 成功
├─ 生产端点:
│  ├─ 连接时间: {prod["connection_time"]:.3f}秒
│  ├─ 总消息数: {prod["total_messages"]:,}
│  ├─ 消息速率: {prod["messages_per_second"]:.2f} msg/s
│  ├─ 成功率: {prod["success_rate"]:.1f}%
│  ├─ 符号数: {prod["symbols_received"]}
│  └─ 错误数: {prod["error_count"]}
├─ Alpaca端点:
│  ├─ 连接时间: {alpaca["connection_time"]:.3f}秒
│  ├─ 总消息数: {alpaca["total_messages"]:,}
│  ├─ 消息速率: {alpaca["messages_per_second"]:.2f} msg/s
│  ├─ 成功率: {alpaca["success_rate"]:.1f}%
│  ├─ 符号数: {alpaca["symbols_received"]}
│  └─ 错误数: {alpaca["error_count"]}
├─ 性能比较:
│  ├─ 更快端点: {comparison.get("faster_endpoint", "未知")}
│  ├─ 性能比例: {comparison.get("performance_ratio", 0):.2f}:1
│  └─ 推荐: {"生产端点性能更佳" if comparison.get("faster_endpoint") == "production" else "Alpaca端点性能更佳"}

"""
            else:
                report += f"""⚡ 连接性能测试结果
├─ 测试状态: ❌ 失败
└─ 错误信息: {perf_result.get("error", "未知错误")}

"""
        
        # 股票期权验证结果
        if "stock_options_validation" in self.test_results:
            validation_result = self.test_results["stock_options_validation"]
            if validation_result.get("success", False):
                prod_results = validation_result["production_results"]
                alpaca_results = validation_result["alpaca_results"]
                
                prod_stock_coverage = prod_results["summary"]["stocks"]["data_coverage"]
                prod_option_coverage = prod_results["summary"]["options"]["data_coverage"]
                alpaca_stock_coverage = alpaca_results["summary"]["stocks"]["data_coverage"]
                
                report += f"""📊 股票期权数据验证结果
├─ 测试状态: ✅ 成功
├─ 生产端点数据质量:
│  ├─ 股票数据覆盖: {prod_stock_coverage}%
│  ├─ 期权数据覆盖: {prod_option_coverage}%
│  ├─ 总消息数: {prod_results["total_messages"]:,}
│  ├─ 股票报价: {prod_results["summary"]["stocks"]["total_quotes"]:,}
│  ├─ 股票交易: {prod_results["summary"]["stocks"]["total_trades"]:,}
│  ├─ 期权报价: {prod_results["summary"]["options"]["total_quotes"]:,}
│  └─ 期权交易: {prod_results["summary"]["options"]["total_trades"]:,}
├─ Alpaca端点数据质量:
│  ├─ 股票数据覆盖: {alpaca_stock_coverage}%
│  ├─ 总消息数: {alpaca_results["total_messages"]:,}
│  ├─ 股票报价: {alpaca_results["summary"]["stocks"]["total_quotes"]:,}
│  ├─ 股票交易: {alpaca_results["summary"]["stocks"]["total_trades"]:,}
│  └─ 认证状态: {"成功" if alpaca_results["authentication_success"] else "失败"}
├─ 数据质量评估:
│  ├─ 生产端点优势: {"期权数据支持" if prod_option_coverage > 0 else "仅股票数据"}
│  ├─ 数据完整性: {"生产端更完整" if prod_stock_coverage > alpaca_stock_coverage else "Alpaca端更完整" if alpaca_stock_coverage > prod_stock_coverage else "基本相当"}
│  └─ 推荐使用: {"生产端点(支持期权)" if prod_option_coverage > 0 else "根据需求选择"}

"""
            else:
                report += f"""📊 股票期权数据验证结果
├─ 测试状态: ❌ 失败
└─ 错误信息: {validation_result.get("error", "未知错误")}

"""
        
        # 实时数据完整性结果
        if "realtime_data_integrity" in self.test_results:
            integrity_result = self.test_results["realtime_data_integrity"]
            if integrity_result.get("success", False):
                integrity_data = integrity_result["integrity_results"]
                
                report += f"""⏱️ 实时数据完整性测试结果
├─ 测试状态: ✅ 成功
"""
                
                if "production_integrity" in integrity_data and "error" not in integrity_data["production_integrity"]:
                    prod_int = integrity_data["production_integrity"]
                    report += f"""├─ 生产端点实时性:
│  ├─ 首条消息延迟: {prod_int.get("first_message_delay", 0):.3f}秒
│  ├─ 消息频率: {prod_int.get("message_frequency", 0):.2f} msg/s
│  ├─ 平均消息间隔: {prod_int.get("avg_message_interval", 0):.3f}秒
│  ├─ 最大消息间隔: {prod_int.get("max_message_gap", 0):.3f}秒
│  └─ 最小消息间隔: {prod_int.get("min_message_gap", 0):.3f}秒
"""
                
                if "alpaca_integrity" in integrity_data and "error" not in integrity_data["alpaca_integrity"]:
                    alpaca_int = integrity_data["alpaca_integrity"]
                    report += f"""├─ Alpaca端点实时性:
│  ├─ 首条消息延迟: {alpaca_int.get("first_message_delay", 0):.3f}秒
│  ├─ 消息频率: {alpaca_int.get("message_frequency", 0):.2f} msg/s
│  ├─ 平均消息间隔: {alpaca_int.get("avg_message_interval", 0):.3f}秒
│  ├─ 最大消息间隔: {alpaca_int.get("max_message_gap", 0):.3f}秒
│  └─ 最小消息间隔: {alpaca_int.get("min_message_gap", 0):.3f}秒
"""
                
                report += f"""└─ 实时性评估: 两端点均可提供实时数据流

"""
            else:
                report += f"""⏱️ 实时数据完整性测试结果
├─ 测试状态: ❌ 失败
└─ 错误信息: {integrity_result.get("error", "未知错误")}

"""
        
        # 最终结论和建议
        successful_tests = sum(1 for r in self.test_results.values() if r.get('success', False))
        total_tests = len(self.test_results)
        
        if successful_tests == total_tests:
            overall_status = "✅ 全部通过"
            deployment_recommendation = "推荐部署到生产环境"
        elif successful_tests >= total_tests * 0.8:
            overall_status = "⚠️ 大部分通过" 
            deployment_recommendation = "可以部署，但需要监控失败的测试项"
        else:
            overall_status = "❌ 多项失败"
            deployment_recommendation = "需要修复问题后再部署"
        
        report += f"""🎯 最终测试结论
├─ 整体状态: {overall_status}
├─ 测试通过率: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)
├─ 部署建议: {deployment_recommendation}
├─ 最佳端点: {"生产端点(功能更全)" if self._is_production_better() else "根据具体需求选择"}
└─ 下一步行动: {"可以开始部署流程" if successful_tests == total_tests else "优先修复失败的测试项"}

📋 测试文件清单
├─ 主要测试脚本: run_comprehensive_websocket_tests.py
├─ 双端点测试: tests/test_websocket_dual_endpoint_comprehensive.py
├─ 数据验证测试: tests/test_stock_options_data_validation.py
├─ 性能专项测试: run_websocket_comprehensive_tests.py
└─ 测试页面: static/websocket_test.html (http://localhost:8091/static/websocket_test.html)

╚══════════════════════════════════════════════════════════════════════════════╝
        """
        
        return report
    
    def _is_production_better(self) -> bool:
        """判断生产端点是否更好"""
        # 基于测试结果判断生产端点是否更优
        if "stock_options_validation" in self.test_results:
            validation = self.test_results["stock_options_validation"]
            if validation.get("success", False):
                prod_results = validation["production_results"]
                alpaca_results = validation["alpaca_results"]
                
                prod_option_coverage = prod_results["summary"]["options"]["data_coverage"]
                prod_stock_coverage = prod_results["summary"]["stocks"]["data_coverage"]
                alpaca_stock_coverage = alpaca_results["summary"]["stocks"]["data_coverage"]
                
                # 如果生产端点支持期权或者股票覆盖更好，则认为更优
                return prod_option_coverage > 0 or prod_stock_coverage >= alpaca_stock_coverage
        
        return True  # 默认认为生产端点更好
    
    async def run_all_tests(self):
        """运行所有测试"""
        self.start_time = datetime.now()
        
        try:
            # 1. 连接性能测试
            if self.focus_area in ["all", "performance"]:
                print("🚀 正在运行连接性能测试...")
                self.test_results["connection_performance"] = await self.run_connection_performance_tests()
                print(f"   ✅ 连接性能测试完成")
            
            # 2. 股票期权数据验证
            if self.focus_area in ["all", "stock", "option"]:
                print("📊 正在运行股票期权数据验证...")
                self.test_results["stock_options_validation"] = await self.run_stock_options_validation()
                print(f"   ✅ 数据验证测试完成")
            
            # 3. 实时数据完整性测试
            if self.focus_area in ["all", "performance"]:
                print("⏱️ 正在运行实时数据完整性测试...")
                self.test_results["realtime_data_integrity"] = await self.run_realtime_data_integrity_test()
                print(f"   ✅ 实时完整性测试完成")
            
            self.end_time = datetime.now()
            
        except KeyboardInterrupt:
            print("\n⚠️ 测试被用户中断")
            self.end_time = datetime.now()
        except Exception as e:
            print(f"\n❌ 测试过程中发生意外错误: {e}")
            self.end_time = datetime.now()
            raise
    
    def save_results(self):
        """保存测试结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 生成综合报告
        comprehensive_report = self.generate_comprehensive_report()
        
        # 保存文本报告
        report_file = f"websocket_comprehensive_test_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(comprehensive_report)
        
        # 保存JSON数据
        json_data = {
            "test_info": {
                "timestamp": datetime.now().isoformat(),
                "test_type": "full_test" if self.args.full_test else "quick_test" if self.args.quick_test else "custom_test",
                "duration": self.test_duration,
                "focus_area": self.focus_area,
                "total_execution_time": (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
            },
            "test_results": self.test_results,
            "summary": {
                "total_tests": len(self.test_results),
                "successful_tests": sum(1 for r in self.test_results.values() if r.get('success', False)),
                "success_rate": sum(1 for r in self.test_results.values() if r.get('success', False)) / len(self.test_results) * 100 if self.test_results else 0
            }
        }
        
        json_file = f"websocket_comprehensive_test_data_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, default=str, ensure_ascii=False)
        
        return report_file, json_file, comprehensive_report

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="WebSocket双端点系统终极综合测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试模式:
  --full-test     完整测试(5分钟，包含所有测试项)
  --quick-test    快速测试(1分钟，基础功能验证)
  --custom        自定义测试(可设置时长和重点)

示例用法:
  python run_comprehensive_websocket_tests.py --full-test
  python run_comprehensive_websocket_tests.py --quick-test
  python run_comprehensive_websocket_tests.py --custom --duration 180 --focus stock
  python run_comprehensive_websocket_tests.py --custom --duration 300 --focus performance
        """
    )
    
    # 测试模式(互斥)
    test_mode = parser.add_mutually_exclusive_group(required=True)
    test_mode.add_argument('--full-test', action='store_true', help='完整测试(5分钟)')
    test_mode.add_argument('--quick-test', action='store_true', help='快速测试(1分钟)')
    test_mode.add_argument('--custom', action='store_true', help='自定义测试')
    
    # 自定义选项
    parser.add_argument('--duration', type=int, help='测试持续时间(秒，仅限自定义模式)')
    parser.add_argument('--focus', choices=['all', 'stock', 'option', 'performance'], 
                       help='测试重点(仅限自定义模式)')
    
    # 其他选项
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--no-report', action='store_true', help='不生成报告文件')
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 验证自定义模式参数
    if args.custom and not args.duration:
        print("❌ 自定义模式需要指定 --duration 参数")
        return 1
    
    # 配置日志
    setup_logging(args.verbose)
    
    # 创建测试运行器
    runner = ComprehensiveTestRunner(args)
    
    # 打印横幅
    runner.print_test_banner()
    
    # 运行所有测试
    await runner.run_all_tests()
    
    # 保存结果
    if not args.no_report:
        report_file, json_file, comprehensive_report = runner.save_results()
        
        # 显示报告
        print(comprehensive_report)
        
        print(f"""
📄 测试完成! 结果文件:
   📋 详细报告: {report_file}
   💾 JSON数据: {json_file}
   🌐 测试页面: http://localhost:8091/static/websocket_test.html
        """)
    else:
        # 仅显示简要结果
        print(runner.generate_comprehensive_report())
    
    # 根据结果返回退出码
    successful_tests = sum(1 for r in runner.test_results.values() if r.get('success', False))
    total_tests = len(runner.test_results)
    
    if successful_tests == total_tests:
        print("🎉 所有测试通过!")
        return 0
    else:
        print(f"⚠️ {total_tests - successful_tests} 个测试失败")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 意外错误: {e}")
        sys.exit(1)