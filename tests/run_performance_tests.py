"""
性能测试运行脚本
方便执行各种性能测试套件和生成报告
"""

import os
import sys
import subprocess
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class PerformanceTestRunner:
    """性能测试运行器"""
    
    def __init__(self, output_dir="performance_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def run_test_suite(self, test_file, test_class=None, markers=None):
        """运行测试套件"""
        print(f"\n{'='*60}")
        print(f"Running performance tests: {test_file}")
        if test_class:
            print(f"Test class: {test_class}")
        if markers:
            print(f"Markers: {markers}")
        print(f"{'='*60}")
        
        # 构建pytest命令
        cmd = [
            "python", "-m", "pytest",
            f"tests/{test_file}",
            "-v",
            "--tb=short",
            "--capture=no",  # 显示print输出
        ]
        
        # 添加标记过滤
        if markers:
            cmd.extend(["-m", markers])
        
        # 添加特定测试类
        if test_class:
            cmd.append(f"::{test_class}")
        
        # 添加性能报告
        report_file = self.output_dir / f"{test_file.replace('.py', '')}_{self.timestamp}.json"
        cmd.extend(["--json-report", f"--json-report-file={report_file}"])
        
        try:
            # 运行测试
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
            end_time = time.time()
            
            # 输出结果
            print("\nSTDOUT:")
            print(result.stdout)
            
            if result.stderr:
                print("\nSTDERR:")
                print(result.stderr)
            
            # 保存结果
            execution_time = end_time - start_time
            self.save_test_result(test_file, result, execution_time)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error running tests: {e}")
            return False
    
    def save_test_result(self, test_file, result, execution_time):
        """保存测试结果"""
        result_data = {
            "test_file": test_file,
            "timestamp": self.timestamp,
            "execution_time": execution_time,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
        result_file = self.output_dir / f"{test_file.replace('.py', '')}_result_{self.timestamp}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nTest result saved to: {result_file}")
    
    def run_all_performance_tests(self):
        """运行所有性能测试"""
        test_suites = [
            {
                "file": "test_performance_load.py",
                "description": "Performance and Load Tests",
                "markers": "performance"
            },
            {
                "file": "test_account_pool.py", 
                "description": "Account Pool Performance Tests",
                "class": "TestConcurrencyAndRaceConditions",
                "markers": "performance"
            },
            {
                "file": "test_routing_load_balancing.py",
                "description": "Routing Performance Tests", 
                "class": "TestRoutingPerformance",
                "markers": "performance"
            },
            {
                "file": "test_websocket_connections.py",
                "description": "WebSocket Performance Tests",
                "class": "TestWebSocketPerformance", 
                "markers": "performance"
            }
        ]
        
        results = {}
        
        print(f"Starting comprehensive performance test run at {datetime.now()}")
        print(f"Results will be saved to: {self.output_dir}")
        
        for suite in test_suites:
            print(f"\n{'-'*60}")
            print(f"Running: {suite['description']}")
            print(f"{'-'*60}")
            
            success = self.run_test_suite(
                suite["file"],
                suite.get("class"),
                suite.get("markers")
            )
            
            results[suite["file"]] = {
                "success": success,
                "description": suite["description"]
            }
            
            if success:
                print(f"✓ {suite['description']} completed successfully")
            else:
                print(f"✗ {suite['description']} failed")
        
        # 生成总结报告
        self.generate_summary_report(results)
        
        return results
    
    def generate_summary_report(self, results):
        """生成总结报告"""
        summary = {
            "timestamp": self.timestamp,
            "total_suites": len(results),
            "successful_suites": sum(1 for r in results.values() if r["success"]),
            "failed_suites": sum(1 for r in results.values() if not r["success"]),
            "results": results
        }
        
        # 保存JSON报告
        summary_file = self.output_dir / f"performance_summary_{self.timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # 生成HTML报告
        self.generate_html_report(summary)
        
        # 打印总结
        print(f"\n{'='*60}")
        print("PERFORMANCE TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Timestamp: {self.timestamp}")
        print(f"Total test suites: {summary['total_suites']}")
        print(f"Successful: {summary['successful_suites']}")
        print(f"Failed: {summary['failed_suites']}")
        print(f"Success rate: {summary['successful_suites']/summary['total_suites']*100:.1f}%")
        print(f"\nReports saved to: {self.output_dir}")
        print(f"Summary report: {summary_file}")
        
    def generate_html_report(self, summary):
        """生成HTML报告"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Performance Test Report - {summary['timestamp']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ background-color: #e7f3ff; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .test-result {{ margin: 10px 0; padding: 10px; border-radius: 5px; }}
        .success {{ background-color: #d4edda; border-left: 5px solid #28a745; }}
        .failure {{ background-color: #f8d7da; border-left: 5px solid #dc3545; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 20px 0; }}
        .metric {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 14px; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Performance Test Report</h1>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Test Run ID: {summary['timestamp']}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{summary['total_suites']}</div>
                <div class="metric-label">Total Test Suites</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: #28a745;">{summary['successful_suites']}</div>
                <div class="metric-label">Successful</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: #dc3545;">{summary['failed_suites']}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary['successful_suites']/summary['total_suites']*100:.1f}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
        </div>
    </div>
    
    <div class="test-results">
        <h2>Test Results</h2>
"""
        
        for test_file, result in summary['results'].items():
            status_class = "success" if result['success'] else "failure"
            status_text = "✓ PASSED" if result['success'] else "✗ FAILED"
            
            html_content += f"""
        <div class="test-result {status_class}">
            <h3>{result['description']}</h3>
            <p><strong>File:</strong> {test_file}</p>
            <p><strong>Status:</strong> {status_text}</p>
        </div>
"""
        
        html_content += """
    </div>
    
    <div class="footer">
        <h2>Performance Testing Guidelines</h2>
        <ul>
            <li><strong>Connection Pool:</strong> Tests connection acquisition, release, and routing performance</li>
            <li><strong>API Endpoints:</strong> Tests request/response times and throughput</li>
            <li><strong>WebSocket:</strong> Tests real-time data broadcasting performance</li>
            <li><strong>Load Testing:</strong> Tests system behavior under high concurrent load</li>
        </ul>
        
        <h3>Performance Targets</h3>
        <ul>
            <li>API Response Time: &lt; 100ms (P95)</li>
            <li>Connection Pool Throughput: &gt; 1000 ops/sec</li>
            <li>WebSocket Broadcast: &gt; 1000 clients/sec</li>
            <li>Concurrent Users: Support 1000+ simultaneous users</li>
        </ul>
    </div>
</body>
</html>
"""
        
        html_file = self.output_dir / f"performance_report_{self.timestamp}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML report: {html_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Run performance tests for opitios_alpaca")
    parser.add_argument("--test-file", help="Specific test file to run")
    parser.add_argument("--test-class", help="Specific test class to run")
    parser.add_argument("--markers", default="performance", help="Test markers to filter")
    parser.add_argument("--output-dir", default="performance_reports", help="Output directory for reports")
    parser.add_argument("--all", action="store_true", help="Run all performance tests")
    
    args = parser.parse_args()
    
    runner = PerformanceTestRunner(args.output_dir)
    
    if args.all or not args.test_file:
        # 运行所有性能测试
        results = runner.run_all_performance_tests()
        
        # 返回适当的退出码
        success_count = sum(1 for r in results.values() if r["success"])
        if success_count == len(results):
            print("\n🎉 All performance tests passed!")
            sys.exit(0)
        else:
            print(f"\n⚠️  {len(results) - success_count} performance test(s) failed!")
            sys.exit(1)
    else:
        # 运行特定测试
        success = runner.run_test_suite(args.test_file, args.test_class, args.markers)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()