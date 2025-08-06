#!/usr/bin/env python3
"""
WebSocket双端点系统综合测试运行脚本
专门测试生产端点(localhost:8091)和Alpaca测试端点的性能和准确性

使用方法:
python run_websocket_comprehensive_tests.py [选项]

选项:
--duration 测试持续时间(秒) 默认:180
--stocks 测试股票列表，逗号分隔 默认:AAPL,TSLA,GOOGL,MSFT
--report-file 报告文件名 默认:自动生成
--production-only 只测试生产端点
--alpaca-only 只测试Alpaca端点
--parallel 并行测试两个端点(默认)
--sequential 顺序测试两个端点
--verbose 详细输出
--quiet 静默模式
"""

import asyncio
import argparse
import sys
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# 导入我们的测试类
from tests.test_websocket_dual_endpoint_comprehensive import (
    DualEndpointWebSocketTester, 
    TestMetrics, 
    test_manual_run_comprehensive_websocket_test
)

# 配置日志
def setup_logging(verbose: bool = False, quiet: bool = False):
    """配置日志"""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置websockets库的日志级别
    logging.getLogger('websockets').setLevel(logging.WARNING)

class WebSocketTestRunner:
    """WebSocket测试运行器"""
    
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        
        # 配置测试参数
        self.test_duration = args.duration
        self.test_stocks = args.stocks.split(',') if args.stocks else ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NVDA"]
        self.report_file = args.report_file
        self.verbose = args.verbose
        
        # 创建测试器并配置股票列表
        self.tester = DualEndpointWebSocketTester()
        self.tester.TEST_STOCKS = self.test_stocks
        
    def print_banner(self):
        """打印测试横幅"""
        banner = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    WebSocket 双端点系统综合测试                              ║
║                         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 生产端点: ws://localhost:8091/api/v1/ws/market-data                         ║
║ 测试端点: wss://stream.data.alpaca.markets/v2/test                          ║
║ 测试时长: {self.test_duration}秒                                                     ║
║ 测试股票: {', '.join(self.test_stocks[:6])}{'...' if len(self.test_stocks) > 6 else ''}                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    async def run_production_only(self) -> Dict[str, Any]:
        """只运行生产端点测试"""
        self.logger.info("开始生产端点独立测试...")
        
        production_metrics = await self.tester.test_production_endpoint(self.test_duration)
        
        return {
            "test_type": "production_only",
            "production_metrics": production_metrics,
            "alpaca_metrics": None,
            "comparison": None
        }
    
    async def run_alpaca_only(self) -> Dict[str, Any]:
        """只运行Alpaca端点测试"""
        self.logger.info("开始Alpaca端点独立测试...")
        
        alpaca_metrics = await self.tester.test_alpaca_endpoint(self.test_duration)
        
        return {
            "test_type": "alpaca_only",
            "production_metrics": None,
            "alpaca_metrics": alpaca_metrics,
            "comparison": None
        }
    
    async def run_parallel_tests(self) -> Dict[str, Any]:
        """运行并行测试"""
        self.logger.info("开始并行双端点测试...")
        
        production_metrics, alpaca_metrics = await self.tester.run_parallel_tests(self.test_duration)
        comparison = self.tester.compare_endpoints()
        
        return {
            "test_type": "parallel",
            "production_metrics": production_metrics,
            "alpaca_metrics": alpaca_metrics,
            "comparison": comparison
        }
    
    async def run_sequential_tests(self) -> Dict[str, Any]:
        """运行顺序测试"""
        self.logger.info("开始顺序双端点测试...")
        
        self.logger.info("第一步: 测试生产端点...")
        production_metrics = await self.tester.test_production_endpoint(self.test_duration)
        
        self.logger.info("第二步: 测试Alpaca端点...")
        alpaca_metrics = await self.tester.test_alpaca_endpoint(self.test_duration)
        
        # 手动设置指标以便比较
        self.tester.production_metrics = production_metrics
        self.tester.test_metrics = alpaca_metrics
        comparison = self.tester.compare_endpoints()
        
        return {
            "test_type": "sequential", 
            "production_metrics": production_metrics,
            "alpaca_metrics": alpaca_metrics,
            "comparison": comparison
        }
    
    def generate_json_report(self, results: Dict[str, Any]) -> str:
        """生成JSON格式的报告"""
        json_data = {
            "test_info": {
                "timestamp": datetime.now().isoformat(),
                "duration": self.test_duration,
                "test_type": results["test_type"],
                "test_stocks": self.test_stocks,
                "production_url": self.tester.PRODUCTION_WS_URL,
                "alpaca_url": self.tester.TEST_WS_URL
            },
            "results": {}
        }
        
        if results["production_metrics"]:
            prod_metrics = results["production_metrics"]
            json_data["results"]["production"] = {
                "connection_time": prod_metrics.connection_time,
                "authentication_time": prod_metrics.authentication_time,
                "first_message_time": prod_metrics.first_message_time,
                "total_messages": prod_metrics.total_messages,
                "messages_per_second": prod_metrics.messages_per_second,
                "success_rate": prod_metrics.success_rate,
                "error_count": prod_metrics.error_count,
                "symbols_received": list(prod_metrics.symbols_received),
                "message_types": dict(prod_metrics.message_types),
                "latency_stats": prod_metrics.latency_stats
            }
        
        if results["alpaca_metrics"]:
            alpaca_metrics = results["alpaca_metrics"]
            json_data["results"]["alpaca"] = {
                "connection_time": alpaca_metrics.connection_time,
                "authentication_time": alpaca_metrics.authentication_time,
                "first_message_time": alpaca_metrics.first_message_time,
                "total_messages": alpaca_metrics.total_messages,
                "messages_per_second": alpaca_metrics.messages_per_second,
                "success_rate": alpaca_metrics.success_rate,
                "error_count": alpaca_metrics.error_count,
                "symbols_received": list(alpaca_metrics.symbols_received),
                "message_types": dict(alpaca_metrics.message_types),
                "latency_stats": alpaca_metrics.latency_stats
            }
        
        if results["comparison"]:
            json_data["comparison"] = results["comparison"]
        
        return json.dumps(json_data, indent=2, ensure_ascii=False)
    
    def save_reports(self, results: Dict[str, Any]) -> List[str]:
        """保存测试报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_files = []
        
        # 生成文本报告
        if results["production_metrics"] and results["alpaca_metrics"]:
            text_report = self.tester.generate_report()
        else:
            # 为单端点测试生成简化报告
            text_report = self.generate_single_endpoint_report(results)
        
        # 保存文本报告
        if self.report_file:
            text_file = self.report_file
        else:
            text_file = f"websocket_test_report_{timestamp}.txt"
        
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_report)
        saved_files.append(text_file)
        
        # 保存JSON报告
        json_file = f"websocket_test_data_{timestamp}.json"
        json_report = self.generate_json_report(results)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json_report)
        saved_files.append(json_file)
        
        return saved_files
    
    def generate_single_endpoint_report(self, results: Dict[str, Any]) -> str:
        """为单端点测试生成报告"""
        test_type = results["test_type"]
        metrics = results["production_metrics"] or results["alpaca_metrics"]
        endpoint_name = "生产端点" if results["production_metrics"] else "Alpaca测试端点"
        endpoint_url = self.tester.PRODUCTION_WS_URL if results["production_metrics"] else self.tester.TEST_WS_URL
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        WebSocket {endpoint_name} 测试报告                     ║
║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
╠══════════════════════════════════════════════════════════════════════════════╣

📊 测试概览
├─ 测试类型: {test_type}
├─ 测试时长: {self.test_duration}秒
├─ 端点地址: {endpoint_url}
└─ 测试股票: {', '.join(self.test_stocks)}

📈 测试结果
├─ 连接时间: {metrics.connection_time:.3f}秒
├─ 认证时间: {metrics.authentication_time:.3f}秒
├─ 首消息时间: {metrics.first_message_time:.3f}秒
├─ 总消息数: {metrics.total_messages:,}
├─ 消息速率: {metrics.messages_per_second:.2f} msg/s
├─ 成功率: {metrics.success_rate:.1f}%
├─ 符号数量: {len(metrics.symbols_received)}
├─ 错误计数: {metrics.error_count}
└─ 消息类型: {dict(metrics.message_types)}

📈 延迟统计
"""
        
        if metrics.latency_stats:
            report += f"""├─ 平均延迟: {metrics.latency_stats.get('mean', 0):.3f}s
├─ 中位延迟: {metrics.latency_stats.get('median', 0):.3f}s
├─ 最小延迟: {metrics.latency_stats.get('min', 0):.3f}s
├─ 最大延迟: {metrics.latency_stats.get('max', 0):.3f}s
└─ 标准差: {metrics.latency_stats.get('std', 0):.3f}s
"""
        else:
            report += "└─ 无延迟数据\n"
        
        report += f"""
✅ 测试结论
├─ 连接稳定性: {"良好" if metrics.success_rate > 95 else "需要改进"}
├─ 数据完整性: {"完整" if len(metrics.symbols_received) > 0 else "不完整"}
├─ 性能表现: {"优秀" if metrics.messages_per_second > 1 else "一般"}
└─ 推荐部署: {"可以部署" if metrics.success_rate > 90 else "需要优化后部署"}

╚══════════════════════════════════════════════════════════════════════════════╝
        """
        
        return report
    
    def print_summary(self, results: Dict[str, Any], saved_files: List[str]):
        """打印测试总结"""
        print(f"\n{'='*80}")
        print(f"🎉 测试完成! 类型: {results['test_type']}")
        print(f"⏱️  测试时长: {self.test_duration}秒")
        
        if results["production_metrics"]:
            prod = results["production_metrics"]
            print(f"🏭 生产端点: {prod.total_messages}条消息, {prod.messages_per_second:.2f} msg/s, {prod.success_rate:.1f}% 成功率")
        
        if results["alpaca_metrics"]:
            alpaca = results["alpaca_metrics"]
            print(f"🧪 Alpaca端点: {alpaca.total_messages}条消息, {alpaca.messages_per_second:.2f} msg/s, {alpaca.success_rate:.1f}% 成功率")
        
        if results["comparison"]:
            comp = results["comparison"]
            print(f"🏆 更快端点: {comp['faster_endpoint']}")
            print(f"⚡ 性能比例: {comp.get('performance_ratio', 0):.2f}:1")
        
        print(f"📄 报告文件:")
        for file in saved_files:
            print(f"   - {file}")
        
        print(f"{'='*80}\n")
    
    async def run(self) -> Dict[str, Any]:
        """运行测试"""
        start_time = time.time()
        
        try:
            if self.args.production_only:
                results = await self.run_production_only()
            elif self.args.alpaca_only:
                results = await self.run_alpaca_only()
            elif self.args.sequential:
                results = await self.run_sequential_tests()
            else:  # 默认并行测试
                results = await self.run_parallel_tests()
            
            # 添加执行时间
            results["execution_time"] = time.time() - start_time
            
            return results
            
        except KeyboardInterrupt:
            self.logger.warning("测试被用户中断")
            return {"test_type": "interrupted", "error": "用户中断测试"}
        except Exception as e:
            self.logger.error(f"测试执行失败: {e}")
            return {"test_type": "failed", "error": str(e)}

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="WebSocket双端点系统综合测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_websocket_comprehensive_tests.py                    # 运行默认3分钟并行测试
  python run_websocket_comprehensive_tests.py --duration 300    # 运行5分钟测试
  python run_websocket_comprehensive_tests.py --production-only # 只测试生产端点
  python run_websocket_comprehensive_tests.py --alpaca-only     # 只测试Alpaca端点
  python run_websocket_comprehensive_tests.py --sequential      # 顺序测试
  python run_websocket_comprehensive_tests.py --stocks "AAPL,TSLA,NVDA" # 自定义股票
        """
    )
    
    parser.add_argument(
        '--duration', 
        type=int, 
        default=180,
        help='测试持续时间(秒) [默认: 180]'
    )
    
    parser.add_argument(
        '--stocks',
        type=str,
        default="AAPL,TSLA,GOOGL,MSFT,AMZN,NVDA,META,SPY",
        help='测试股票列表，逗号分隔 [默认: AAPL,TSLA,GOOGL,MSFT,AMZN,NVDA,META,SPY]'
    )
    
    parser.add_argument(
        '--report-file',
        type=str,
        help='报告文件名 [默认: 自动生成时间戳文件名]'
    )
    
    # 测试模式选项
    test_mode = parser.add_mutually_exclusive_group()
    test_mode.add_argument(
        '--production-only',
        action='store_true',
        help='只测试生产端点'
    )
    test_mode.add_argument(
        '--alpaca-only', 
        action='store_true',
        help='只测试Alpaca端点'
    )
    
    # 执行模式选项
    exec_mode = parser.add_mutually_exclusive_group()
    exec_mode.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        help='并行测试两个端点(默认)'
    )
    exec_mode.add_argument(
        '--sequential',
        action='store_true',
        help='顺序测试两个端点'
    )
    
    # 日志选项
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )
    log_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='静默模式'
    )
    
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_arguments()
    
    # 配置日志
    setup_logging(args.verbose, args.quiet)
    
    # 创建测试运行器
    runner = WebSocketTestRunner(args)
    
    # 打印横幅
    if not args.quiet:
        runner.print_banner()
    
    # 运行测试
    results = await runner.run()
    
    # 处理结果
    if "error" in results:
        print(f"❌ 测试失败: {results['error']}")
        return 1
    
    # 保存报告
    saved_files = runner.save_reports(results)
    
    # 打印总结
    if not args.quiet:
        runner.print_summary(results, saved_files)
    
    return 0

if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("❌ 此脚本需要Python 3.7或更高版本")
        sys.exit(1)
    
    # 检查依赖
    try:
        import websockets
        import aiohttp
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install websockets aiohttp")
        sys.exit(1)
    
    # 运行主函数
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 意外错误: {e}")
        sys.exit(1)