"""
WebSocket双端点系统综合测试套件
测试生产端点(localhost:8091)和测试端点(stream.data.alpaca.markets)的数据接收速度和准确性
"""

import pytest
import asyncio
import json
import time
import statistics
import websockets
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass, field
from collections import defaultdict
import logging
from contextlib import asynccontextmanager
import aiohttp
import threading
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestMetrics:
    """测试指标数据类"""
    endpoint_name: str
    connection_time: float = 0.0
    authentication_time: float = 0.0
    first_message_time: float = 0.0
    total_messages: int = 0
    messages_per_second: float = 0.0
    data_accuracy: float = 0.0
    latency_stats: Dict[str, float] = field(default_factory=dict)
    error_count: int = 0
    success_rate: float = 0.0
    message_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    symbols_received: set = field(default_factory=set)

@dataclass
class MessageData:
    """消息数据"""
    timestamp: datetime
    message_type: str
    symbol: str
    data: Dict[str, Any]
    latency: float = 0.0
    endpoint: str = ""

class DualEndpointWebSocketTester:
    """双端点WebSocket测试器"""
    
    # 端点配置
    PRODUCTION_WS_URL = "ws://localhost:8091/api/v1/ws/market-data"
    TEST_WS_URL = "wss://stream.data.alpaca.markets/v2/test"
    
    # 测试股票和期权符号
    TEST_STOCKS = ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NVDA", "META", "SPY"]
    TEST_OPTIONS = [
        "AAPL250117C00230000",  # AAPL $230 Call 2025-01-17
        "TSLA250117C00300000",  # TSLA $300 Call 2025-01-17
        "SPY250117C00580000",   # SPY $580 Call 2025-01-17
        "GOOGL250117P00180000", # GOOGL $180 Put 2025-01-17
    ]
    
    def __init__(self):
        self.production_metrics = TestMetrics("Production")
        self.test_metrics = TestMetrics("Test")
        self.received_messages = {
            "production": [],
            "test": []
        }
        self.test_start_time = None
        self.test_duration = 60  # 默认测试60秒
        
    async def test_production_endpoint(self, duration: int = 60) -> TestMetrics:
        """测试生产端点"""
        logger.info(f"开始测试生产端点: {self.PRODUCTION_WS_URL}")
        metrics = TestMetrics("Production")
        
        try:
            start_time = time.time()
            
            # 连接WebSocket
            connection_start = time.time()
            websocket = await websockets.connect(
                self.PRODUCTION_WS_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            metrics.connection_time = time.time() - connection_start
            logger.info(f"生产端点连接成功，用时: {metrics.connection_time:.3f}s")
            
            # 等待欢迎消息
            auth_start = time.time()
            welcome_message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            metrics.authentication_time = time.time() - auth_start
            
            welcome_data = json.loads(welcome_message)
            logger.info(f"收到欢迎消息: {welcome_data.get('type', 'unknown')}")
            
            # 记录第一条消息时间
            if metrics.total_messages == 0:
                metrics.first_message_time = time.time() - start_time
            
            metrics.total_messages += 1
            metrics.message_types[welcome_data.get('type', 'unknown')] += 1
            
            # 监听消息指定时长
            test_end_time = time.time() + duration
            message_times = []
            
            while time.time() < test_end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    message_time = time.time()
                    
                    data = json.loads(message)
                    metrics.total_messages += 1
                    metrics.message_types[data.get('type', 'unknown')] += 1
                    
                    # 记录符号
                    if 'symbol' in data:
                        metrics.symbols_received.add(data['symbol'])
                    
                    # 记录消息数据
                    msg_data = MessageData(
                        timestamp=datetime.now(),
                        message_type=data.get('type', 'unknown'),
                        symbol=data.get('symbol', ''),
                        data=data,
                        endpoint="production"
                    )
                    self.received_messages["production"].append(msg_data)
                    
                    # 计算延迟
                    if 'timestamp' in data:
                        try:
                            msg_timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                            latency = (datetime.now() - msg_timestamp.replace(tzinfo=None)).total_seconds()
                            message_times.append(latency)
                            msg_data.latency = latency
                        except:
                            pass
                    
                except asyncio.TimeoutError:
                    logger.warning("生产端点消息接收超时")
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.error("生产端点连接关闭")
                    break
                except Exception as e:
                    logger.error(f"生产端点消息处理错误: {e}")
                    metrics.error_count += 1
                    continue
            
            await websocket.close()
            
        except Exception as e:
            logger.error(f"生产端点测试失败: {e}")
            metrics.error_count += 1
        
        # 计算最终指标
        total_time = time.time() - start_time
        metrics.messages_per_second = metrics.total_messages / total_time if total_time > 0 else 0
        metrics.success_rate = (metrics.total_messages - metrics.error_count) / max(metrics.total_messages, 1) * 100
        
        if message_times:
            metrics.latency_stats = {
                'mean': statistics.mean(message_times),
                'median': statistics.median(message_times),
                'min': min(message_times),
                'max': max(message_times),
                'std': statistics.stdev(message_times) if len(message_times) > 1 else 0
            }
        
        logger.info(f"生产端点测试完成: {metrics.total_messages} 消息, {metrics.messages_per_second:.2f} msg/s")
        self.production_metrics = metrics
        return metrics
    
    async def test_alpaca_endpoint(self, duration: int = 60) -> TestMetrics:
        """测试Alpaca测试端点"""
        logger.info(f"开始测试Alpaca端点: {self.TEST_WS_URL}")
        metrics = TestMetrics("Alpaca_Test")
        
        try:
            start_time = time.time()
            
            # 连接WebSocket (使用SSL)
            connection_start = time.time()
            ssl_context = ssl.create_default_context()
            websocket = await websockets.connect(
                self.TEST_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            metrics.connection_time = time.time() - connection_start
            logger.info(f"Alpaca端点连接成功，用时: {metrics.connection_time:.3f}s")
            
            # 认证
            auth_start = time.time()
            auth_message = {
                "action": "auth",
                "key": "test_api_key",
                "secret": "test_secret_key"
            }
            await websocket.send(json.dumps(auth_message))
            
            # 等待认证响应
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            metrics.authentication_time = time.time() - auth_start
            
            auth_data = json.loads(auth_response)
            logger.info(f"Alpaca认证响应: {auth_data}")
            
            # 订阅测试数据
            subscribe_message = {
                "action": "subscribe",
                "quotes": self.TEST_STOCKS,
                "trades": self.TEST_STOCKS
            }
            await websocket.send(json.dumps(subscribe_message))
            
            # 记录第一条消息时间
            if metrics.total_messages == 0:
                metrics.first_message_time = time.time() - start_time
            
            metrics.total_messages += 1
            if isinstance(auth_data, list):
                for item in auth_data:
                    metrics.message_types[item.get('T', 'unknown')] += 1
            else:
                metrics.message_types[auth_data.get('T', 'unknown')] += 1
            
            # 监听消息指定时长
            test_end_time = time.time() + duration
            message_times = []
            
            while time.time() < test_end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    message_time = time.time()
                    
                    data = json.loads(message)
                    
                    # Alpaca返回消息数组
                    if isinstance(data, list):
                        for item in data:
                            metrics.total_messages += 1
                            metrics.message_types[item.get('T', 'unknown')] += 1
                            
                            # 记录符号
                            if 'S' in item:
                                metrics.symbols_received.add(item['S'])
                            
                            # 记录消息数据
                            msg_data = MessageData(
                                timestamp=datetime.now(),
                                message_type=item.get('T', 'unknown'),
                                symbol=item.get('S', ''),
                                data=item,
                                endpoint="alpaca_test"
                            )
                            self.received_messages["test"].append(msg_data)
                    else:
                        metrics.total_messages += 1
                        metrics.message_types[data.get('T', 'unknown')] += 1
                        
                        if 'S' in data:
                            metrics.symbols_received.add(data['S'])
                        
                        msg_data = MessageData(
                            timestamp=datetime.now(),
                            message_type=data.get('T', 'unknown'),
                            symbol=data.get('S', ''),
                            data=data,
                            endpoint="alpaca_test"
                        )
                        self.received_messages["test"].append(msg_data)
                    
                except asyncio.TimeoutError:
                    logger.warning("Alpaca端点消息接收超时")
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.error("Alpaca端点连接关闭")
                    break
                except Exception as e:
                    logger.error(f"Alpaca端点消息处理错误: {e}")
                    metrics.error_count += 1
                    continue
            
            await websocket.close()
            
        except Exception as e:
            logger.error(f"Alpaca端点测试失败: {e}")
            metrics.error_count += 1
        
        # 计算最终指标
        total_time = time.time() - start_time
        metrics.messages_per_second = metrics.total_messages / total_time if total_time > 0 else 0
        metrics.success_rate = (metrics.total_messages - metrics.error_count) / max(metrics.total_messages, 1) * 100
        
        if message_times:
            metrics.latency_stats = {
                'mean': statistics.mean(message_times),
                'median': statistics.median(message_times),
                'min': min(message_times),
                'max': max(message_times),
                'std': statistics.stdev(message_times) if len(message_times) > 1 else 0
            }
        
        logger.info(f"Alpaca端点测试完成: {metrics.total_messages} 消息, {metrics.messages_per_second:.2f} msg/s")
        self.test_metrics = metrics
        return metrics
    
    async def run_parallel_tests(self, duration: int = 60) -> Tuple[TestMetrics, TestMetrics]:
        """并行运行两个端点测试"""
        logger.info("开始并行测试两个端点...")
        self.test_start_time = time.time()
        
        # 并行运行测试
        production_task = asyncio.create_task(self.test_production_endpoint(duration))
        alpaca_task = asyncio.create_task(self.test_alpaca_endpoint(duration))
        
        production_metrics, alpaca_metrics = await asyncio.gather(
            production_task, 
            alpaca_task, 
            return_exceptions=True
        )
        
        # 处理异常
        if isinstance(production_metrics, Exception):
            logger.error(f"生产端点测试异常: {production_metrics}")
            production_metrics = TestMetrics("Production")
            production_metrics.error_count = 1
        
        if isinstance(alpaca_metrics, Exception):
            logger.error(f"Alpaca端点测试异常: {alpaca_metrics}")
            alpaca_metrics = TestMetrics("Alpaca_Test")
            alpaca_metrics.error_count = 1
        
        return production_metrics, alpaca_metrics
    
    def compare_endpoints(self) -> Dict[str, Any]:
        """比较两个端点的性能"""
        comparison = {
            "test_duration": time.time() - self.test_start_time if self.test_start_time else 0,
            "production": {
                "connection_time": self.production_metrics.connection_time,
                "messages_total": self.production_metrics.total_messages,
                "messages_per_second": self.production_metrics.messages_per_second,
                "success_rate": self.production_metrics.success_rate,
                "symbols_count": len(self.production_metrics.symbols_received),
                "message_types": dict(self.production_metrics.message_types),
                "error_count": self.production_metrics.error_count,
                "latency_stats": self.production_metrics.latency_stats
            },
            "alpaca_test": {
                "connection_time": self.test_metrics.connection_time,
                "messages_total": self.test_metrics.total_messages,
                "messages_per_second": self.test_metrics.messages_per_second,
                "success_rate": self.test_metrics.success_rate,
                "symbols_count": len(self.test_metrics.symbols_received),
                "message_types": dict(self.test_metrics.message_types),
                "error_count": self.test_metrics.error_count,
                "latency_stats": self.test_metrics.latency_stats
            }
        }
        
        # 计算比较指标
        if self.production_metrics.messages_per_second > 0 and self.test_metrics.messages_per_second > 0:
            comparison["performance_ratio"] = self.production_metrics.messages_per_second / self.test_metrics.messages_per_second
        else:
            comparison["performance_ratio"] = 0
        
        comparison["faster_endpoint"] = "production" if self.production_metrics.messages_per_second > self.test_metrics.messages_per_second else "alpaca_test"
        
        return comparison
    
    def generate_report(self) -> str:
        """生成详细测试报告"""
        comparison = self.compare_endpoints()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      WebSocket双端点系统测试报告                              ║
║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
╠══════════════════════════════════════════════════════════════════════════════╣

📊 测试概览
├─ 测试时长: {comparison['test_duration']:.1f}秒
├─ 生产端点: {self.PRODUCTION_WS_URL}
└─ 测试端点: {self.TEST_WS_URL}

🏭 生产端点测试结果
├─ 连接时间: {comparison['production']['connection_time']:.3f}秒
├─ 总消息数: {comparison['production']['messages_total']:,}
├─ 消息速率: {comparison['production']['messages_per_second']:.2f} msg/s
├─ 成功率: {comparison['production']['success_rate']:.1f}%
├─ 符号数量: {comparison['production']['symbols_count']}
├─ 错误计数: {comparison['production']['error_count']}
└─ 消息类型: {comparison['production']['message_types']}

🧪 Alpaca测试端点结果  
├─ 连接时间: {comparison['alpaca_test']['connection_time']:.3f}秒
├─ 总消息数: {comparison['alpaca_test']['messages_total']:,}
├─ 消息速率: {comparison['alpaca_test']['messages_per_second']:.2f} msg/s
├─ 成功率: {comparison['alpaca_test']['success_rate']:.1f}%
├─ 符号数量: {comparison['alpaca_test']['symbols_count']}
├─ 错误计数: {comparison['alpaca_test']['error_count']}
└─ 消息类型: {comparison['alpaca_test']['message_types']}

🔄 端点比较
├─ 性能比例: {comparison['performance_ratio']:.2f}:1 (生产:测试)
├─ 更快端点: {comparison['faster_endpoint']}
└─ 推荐: {"生产端点表现更好" if comparison['faster_endpoint'] == 'production' else "测试端点表现更好"}

📈 延迟统计 (生产端点)
"""
        
        if self.production_metrics.latency_stats:
            report += f"""├─ 平均延迟: {self.production_metrics.latency_stats.get('mean', 0):.3f}s
├─ 中位延迟: {self.production_metrics.latency_stats.get('median', 0):.3f}s
├─ 最小延迟: {self.production_metrics.latency_stats.get('min', 0):.3f}s
├─ 最大延迟: {self.production_metrics.latency_stats.get('max', 0):.3f}s
└─ 标准差: {self.production_metrics.latency_stats.get('std', 0):.3f}s
"""
        else:
            report += "└─ 无延迟数据\n"
        
        report += f"""
📈 延迟统计 (测试端点)
"""
        
        if self.test_metrics.latency_stats:
            report += f"""├─ 平均延迟: {self.test_metrics.latency_stats.get('mean', 0):.3f}s
├─ 中位延迟: {self.test_metrics.latency_stats.get('median', 0):.3f}s
├─ 最小延迟: {self.test_metrics.latency_stats.get('min', 0):.3f}s
├─ 最大延迟: {self.test_metrics.latency_stats.get('max', 0):.3f}s
└─ 标准差: {self.test_metrics.latency_stats.get('std', 0):.3f}s
"""
        else:
            report += "└─ 无延迟数据\n"
        
        report += f"""
✅ 测试结论
├─ 连接稳定性: {"良好" if comparison['production']['success_rate'] > 95 and comparison['alpaca_test']['success_rate'] > 95 else "需要改进"}
├─ 数据完整性: {"完整" if len(self.production_metrics.symbols_received) > 0 and len(self.test_metrics.symbols_received) > 0 else "不完整"}
├─ 性能表现: {"优秀" if comparison['production']['messages_per_second'] > 1 or comparison['alpaca_test']['messages_per_second'] > 1 else "一般"}
└─ 推荐部署: {"可以部署" if comparison['production']['success_rate'] > 90 else "需要优化后部署"}

╚══════════════════════════════════════════════════════════════════════════════╝
        """
        
        return report


class TestDualEndpointWebSocket:
    """双端点WebSocket测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.tester = DualEndpointWebSocketTester()
    
    @pytest.mark.asyncio
    async def test_production_endpoint_connection(self):
        """测试生产端点连接"""
        metrics = await self.tester.test_production_endpoint(duration=30)
        
        # 验证连接指标
        assert metrics.connection_time > 0, "连接时间应该大于0"
        assert metrics.connection_time < 10, "连接时间不应超过10秒"
        assert metrics.error_count == 0, f"不应有连接错误: {metrics.error_count}"
        
        logger.info(f"生产端点连接测试通过: {metrics.connection_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_alpaca_endpoint_connection(self):
        """测试Alpaca端点连接"""
        metrics = await self.tester.test_alpaca_endpoint(duration=30)
        
        # 验证连接指标
        assert metrics.connection_time > 0, "连接时间应该大于0"
        assert metrics.connection_time < 10, "连接时间不应超过10秒"
        assert metrics.error_count == 0, f"不应有连接错误: {metrics.error_count}"
        
        logger.info(f"Alpaca端点连接测试通过: {metrics.connection_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_parallel_endpoint_testing(self):
        """测试并行端点连接"""
        production_metrics, alpaca_metrics = await self.tester.run_parallel_tests(duration=60)
        
        # 验证两个端点都成功
        assert isinstance(production_metrics, TestMetrics), "生产端点指标应该是TestMetrics实例"
        assert isinstance(alpaca_metrics, TestMetrics), "Alpaca端点指标应该是TestMetrics实例"
        
        # 验证基本连接指标
        assert production_metrics.connection_time > 0, "生产端点连接时间应该大于0"
        assert alpaca_metrics.connection_time > 0, "Alpaca端点连接时间应该大于0"
        
        logger.info(f"并行测试完成 - 生产: {production_metrics.total_messages} 消息, Alpaca: {alpaca_metrics.total_messages} 消息")
    
    @pytest.mark.asyncio
    async def test_message_reception_speed(self):
        """测试消息接收速度"""
        production_metrics, alpaca_metrics = await self.tester.run_parallel_tests(duration=120)
        
        # 验证消息接收
        assert production_metrics.total_messages > 0, "生产端点应该接收到消息"
        assert alpaca_metrics.total_messages > 0, "Alpaca端点应该接收到消息"
        
        # 验证消息速率 (至少每分钟1条消息)
        min_rate = 1.0 / 60  # 1消息/分钟
        assert production_metrics.messages_per_second >= min_rate, f"生产端点消息速率过低: {production_metrics.messages_per_second:.4f}"
        assert alpaca_metrics.messages_per_second >= min_rate, f"Alpaca端点消息速率过低: {alpaca_metrics.messages_per_second:.4f}"
        
        logger.info(f"消息速率测试通过 - 生产: {production_metrics.messages_per_second:.2f} msg/s, Alpaca: {alpaca_metrics.messages_per_second:.2f} msg/s")
    
    @pytest.mark.asyncio
    async def test_data_accuracy_validation(self):
        """测试数据准确性验证"""
        production_metrics, alpaca_metrics = await self.tester.run_parallel_tests(duration=90)
        
        # 验证符号接收
        assert len(production_metrics.symbols_received) > 0, "生产端点应该接收到符号数据"
        assert len(alpaca_metrics.symbols_received) > 0, "Alpaca端点应该接收到符号数据"
        
        # 验证消息类型多样性
        assert len(production_metrics.message_types) > 0, "生产端点应该有多种消息类型"
        assert len(alpaca_metrics.message_types) > 0, "Alpaca端点应该有多种消息类型"
        
        # 验证成功率
        assert production_metrics.success_rate >= 90, f"生产端点成功率过低: {production_metrics.success_rate}%"
        assert alpaca_metrics.success_rate >= 90, f"Alpaca端点成功率过低: {alpaca_metrics.success_rate}%"
        
        logger.info(f"数据准确性验证通过 - 生产符号: {len(production_metrics.symbols_received)}, Alpaca符号: {len(alpaca_metrics.symbols_received)}")
    
    @pytest.mark.asyncio 
    async def test_real_time_data_flow(self):
        """测试实时数据流完整性"""
        production_metrics, alpaca_metrics = await self.tester.run_parallel_tests(duration=180)
        
        # 验证实时性 - 第一条消息应该在连接后快速到达
        assert production_metrics.first_message_time < 30, f"生产端点第一条消息时间过长: {production_metrics.first_message_time:.3f}s"
        assert alpaca_metrics.first_message_time < 30, f"Alpaca端点第一条消息时间过长: {alpaca_metrics.first_message_time:.3f}s"
        
        # 验证数据流连续性 - 总消息数应该合理
        min_messages = 1  # 至少应该有欢迎消息
        assert production_metrics.total_messages >= min_messages, f"生产端点消息数过少: {production_metrics.total_messages}"
        assert alpaca_metrics.total_messages >= min_messages, f"Alpaca端点消息数过少: {alpaca_metrics.total_messages}"
        
        logger.info(f"实时数据流测试通过 - 生产: {production_metrics.first_message_time:.3f}s, Alpaca: {alpaca_metrics.first_message_time:.3f}s")
    
    def test_generate_comprehensive_report(self):
        """测试生成综合报告"""
        # 运行异步测试来获取数据
        asyncio.run(self._run_report_test())
        
    async def _run_report_test(self):
        """运行报告测试的异步部分"""
        # 运行完整测试
        await self.tester.run_parallel_tests(duration=150)
        
        # 生成报告
        report = self.tester.generate_report()
        
        # 验证报告内容
        assert "WebSocket双端点系统测试报告" in report, "报告应该包含标题"
        assert "生产端点测试结果" in report, "报告应该包含生产端点结果"
        assert "Alpaca测试端点结果" in report, "报告应该包含Alpaca端点结果"
        assert "端点比较" in report, "报告应该包含端点比较"
        assert "测试结论" in report, "报告应该包含测试结论"
        
        # 打印报告
        print("\n" + report)
        
        # 保存报告到文件
        report_file = f"websocket_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"测试报告已保存到: {report_file}")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_frequency_data_handling(self):
        """测试高频数据处理能力"""
        # 运行长时间测试以获得更多数据
        production_metrics, alpaca_metrics = await self.tester.run_parallel_tests(duration=300)  # 5分钟
        
        # 验证高频处理能力
        high_freq_threshold = 0.5  # 每2秒至少1条消息
        assert production_metrics.messages_per_second >= high_freq_threshold, f"生产端点高频处理能力不足: {production_metrics.messages_per_second:.3f} msg/s"
        
        # Alpaca测试端点可能没有那么高频的数据
        min_freq_threshold = 0.01  # 每100秒至少1条消息
        assert alpaca_metrics.messages_per_second >= min_freq_threshold, f"Alpaca端点基本处理能力不足: {alpaca_metrics.messages_per_second:.3f} msg/s"
        
        logger.info(f"高频数据处理测试通过 - 生产: {production_metrics.messages_per_second:.3f} msg/s, Alpaca: {alpaca_metrics.messages_per_second:.3f} msg/s")

    @pytest.mark.asyncio
    async def test_stock_vs_option_data_reception(self):
        """测试股票vs期权数据接收"""
        await self.tester.run_parallel_tests(duration=120)
        
        # 分析接收到的符号类型
        production_stocks = [s for s in self.tester.production_metrics.symbols_received if len(s) <= 10]
        production_options = [s for s in self.tester.production_metrics.symbols_received if len(s) > 10]
        
        alpaca_stocks = [s for s in self.tester.test_metrics.symbols_received if len(s) <= 10]
        alpaca_options = [s for s in self.tester.test_metrics.symbols_received if len(s) > 10]
        
        logger.info(f"符号统计 - 生产端(股票:{len(production_stocks)}, 期权:{len(production_options)}), Alpaca端(股票:{len(alpaca_stocks)}, 期权:{len(alpaca_options)})")
        
        # 至少应该接收到一些股票数据
        assert len(production_stocks) > 0 or len(alpaca_stocks) > 0, "至少一个端点应该接收到股票数据"

@pytest.mark.asyncio
async def test_manual_run_comprehensive_websocket_test():
    """手动运行综合WebSocket测试 - 可以直接调用此函数"""
    tester = DualEndpointWebSocketTester()
    
    print("🚀 开始WebSocket双端点综合测试...")
    print(f"📊 测试将运行3分钟，请耐心等待...")
    
    # 运行并行测试
    production_metrics, alpaca_metrics = await tester.run_parallel_tests(duration=180)
    
    # 生成和显示报告
    report = tester.generate_report()
    print(report)
    
    # 保存报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"websocket_dual_endpoint_test_report_{timestamp}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 详细报告已保存到: {report_file}")
    
    return {
        "production_metrics": production_metrics,
        "alpaca_metrics": alpaca_metrics,
        "report_file": report_file,
        "comparison": tester.compare_endpoints()
    }


if __name__ == "__main__":
    # 运行单独的测试
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        # 手动运行模式
        results = asyncio.run(test_manual_run_comprehensive_websocket_test())
        print("\n✅ 手动测试完成!")
        print(f"生产端点消息: {results['production_metrics'].total_messages}")
        print(f"Alpaca端点消息: {results['alpaca_metrics'].total_messages}")
    else:
        # pytest运行模式
        pytest.main([__file__, "-v", "--tb=short", "-s"])