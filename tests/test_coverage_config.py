"""
测试覆盖率配置和质量指标
配置代码覆盖率分析、质量门禁和回归测试套件
"""

import pytest
import coverage
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class CoverageAnalyzer:
    """代码覆盖率分析器"""
    
    def __init__(self, source_dirs=None, exclude_patterns=None):
        self.source_dirs = source_dirs or ['app']
        self.exclude_patterns = exclude_patterns or [
            '*/tests/*',
            '*/test_*',
            '*/conftest.py',
            '*/migrations/*',
            '*/venv/*',
            '*/__pycache__/*',
            '*/static/*',
            '*/templates/*'
        ]
        self.coverage_obj = None
        
    def start_coverage(self):
        """开始代码覆盖率收集"""
        self.coverage_obj = coverage.Coverage(
            source=self.source_dirs,
            omit=self.exclude_patterns,
            branch=True,  # 启用分支覆盖
            config_file=False
        )
        self.coverage_obj.start()
        
    def stop_coverage(self):
        """停止代码覆盖率收集"""
        if self.coverage_obj:
            self.coverage_obj.stop()
            
    def save_coverage_data(self, data_file='.coverage'):
        """保存覆盖率数据"""
        if self.coverage_obj:
            self.coverage_obj.save()
            
    def generate_coverage_report(self, output_dir='coverage_reports'):
        """生成覆盖率报告"""
        if not self.coverage_obj:
            return None
            
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 生成HTML报告
        html_dir = output_path / 'html'
        self.coverage_obj.html_report(directory=str(html_dir))
        
        # 生成XML报告
        xml_file = output_path / 'coverage.xml'
        self.coverage_obj.xml_report(outfile=str(xml_file))
        
        # 生成JSON报告
        json_file = output_path / 'coverage.json'
        with open(json_file, 'w') as f:
            json.dump(self.get_coverage_data(), f, indent=2)
        
        return {
            'html_report': html_dir,
            'xml_report': xml_file,
            'json_report': json_file
        }
    
    def get_coverage_data(self):
        """获取覆盖率数据"""
        if not self.coverage_obj:
            return None
            
        # 获取总体统计
        total = self.coverage_obj.report(show_missing=False, file=None)
        
        # 获取文件级别统计
        file_data = {}
        analysis_data = self.coverage_obj.get_data()
        
        for filename in analysis_data.measured_files():
            try:
                analysis = self.coverage_obj._analyze(filename)
                file_data[filename] = {
                    'statements': len(analysis.statements),
                    'missing': len(analysis.missing),
                    'excluded': len(analysis.excluded),
                    'coverage_percent': (len(analysis.statements) - len(analysis.missing)) / len(analysis.statements) * 100 if analysis.statements else 0
                }
            except Exception as e:
                file_data[filename] = {'error': str(e)}
        
        return {
            'total_coverage': total,
            'timestamp': datetime.now().isoformat(),
            'files': file_data
        }


class QualityGate:
    """质量门禁"""
    
    def __init__(self):
        self.thresholds = {
            'line_coverage_min': 80.0,      # 最低行覆盖率
            'branch_coverage_min': 70.0,    # 最低分支覆盖率
            'complexity_max': 10,           # 最大圈复杂度
            'duplicates_max': 3.0,          # 最大重复率（%）
            'maintainability_min': 70.0,    # 最低可维护性指数
        }
        
    def check_coverage_threshold(self, coverage_data):
        """检查覆盖率阈值"""
        results = {
            'passed': True,
            'checks': []
        }
        
        total_coverage = coverage_data.get('total_coverage', 0)
        
        # 检查行覆盖率
        line_check = {
            'name': 'Line Coverage',
            'actual': total_coverage,
            'threshold': self.thresholds['line_coverage_min'],
            'passed': total_coverage >= self.thresholds['line_coverage_min']
        }
        results['checks'].append(line_check)
        
        if not line_check['passed']:
            results['passed'] = False
            
        return results
    
    def check_file_coverage(self, coverage_data, critical_files=None):
        """检查关键文件覆盖率"""
        critical_files = critical_files or [
            'app/account_pool.py',
            'app/middleware.py',
            'app/routes.py',
            'app/alpaca_client.py'
        ]
        
        results = {
            'passed': True,
            'files': []
        }
        
        files_data = coverage_data.get('files', {})
        
        for critical_file in critical_files:
            matching_files = [f for f in files_data.keys() if critical_file in f]
            
            for file_path in matching_files:
                file_data = files_data[file_path]
                coverage_percent = file_data.get('coverage_percent', 0)
                
                file_check = {
                    'file': file_path,
                    'coverage': coverage_percent,
                    'threshold': self.thresholds['line_coverage_min'],
                    'passed': coverage_percent >= self.thresholds['line_coverage_min']
                }
                
                results['files'].append(file_check)
                
                if not file_check['passed']:
                    results['passed'] = False
        
        return results
    
    def generate_quality_report(self, coverage_data, output_file='quality_report.json'):
        """生成质量报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'coverage_check': self.check_coverage_threshold(coverage_data),
            'file_coverage_check': self.check_file_coverage(coverage_data),
            'thresholds': self.thresholds,
            'overall_passed': True
        }
        
        # 检查整体是否通过
        if not report['coverage_check']['passed'] or not report['file_coverage_check']['passed']:
            report['overall_passed'] = False
        
        # 保存报告
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report


class RegressionTestSuite:
    """回归测试套件"""
    
    def __init__(self, baseline_file='test_baseline.json'):
        self.baseline_file = baseline_file
        self.baseline_data = self.load_baseline()
        
    def load_baseline(self):
        """加载基线数据"""
        if os.path.exists(self.baseline_file):
            with open(self.baseline_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_baseline(self, data):
        """保存基线数据"""
        with open(self.baseline_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def run_regression_tests(self):
        """运行回归测试"""
        # 定义核心测试套件
        core_tests = [
            'tests/test_account_pool.py::TestAccountConnectionPool::test_get_connection_success',
            'tests/test_middleware_auth.py::TestJWTTokenOperations::test_create_jwt_token_basic',
            'tests/test_routing_load_balancing.py::TestRoutingStrategies::test_round_robin_basic',
            'tests/test_error_handling_recovery.py::TestConnectionPoolErrorHandling::test_connection_creation_failure',
        ]
        
        results = {}
        
        for test in core_tests:
            try:
                cmd = ['python', '-m', 'pytest', test, '-v', '--tb=short']
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
                
                results[test] = {
                    'passed': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr if result.stderr else None
                }
                
            except Exception as e:
                results[test] = {
                    'passed': False,
                    'error': str(e)
                }
        
        return results
    
    def compare_with_baseline(self, current_results):
        """与基线对比"""
        comparison = {
            'timestamp': datetime.now().isoformat(),
            'regression_detected': False,
            'new_failures': [],
            'recovered_tests': [],
            'unchanged': []
        }
        
        for test, current_result in current_results.items():
            baseline_result = self.baseline_data.get(test, {})
            baseline_passed = baseline_result.get('passed', None)
            current_passed = current_result.get('passed', False)
            
            if baseline_passed is None:
                # 新测试
                comparison['unchanged'].append({
                    'test': test,
                    'status': 'new_test',
                    'current': current_passed
                })
            elif baseline_passed and not current_passed:
                # 回归：之前通过，现在失败
                comparison['new_failures'].append({
                    'test': test,
                    'previous': baseline_passed,
                    'current': current_passed,
                    'error': current_result.get('error')
                })
                comparison['regression_detected'] = True
            elif not baseline_passed and current_passed:
                # 恢复：之前失败，现在通过
                comparison['recovered_tests'].append({
                    'test': test,
                    'previous': baseline_passed,
                    'current': current_passed
                })
            else:
                # 状态未变
                comparison['unchanged'].append({
                    'test': test,
                    'status': 'unchanged',
                    'passed': current_passed
                })
        
        return comparison


class TestQualityManager:
    """测试质量管理器"""
    
    def __init__(self, output_dir='quality_reports'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def run_full_quality_analysis(self):
        """运行完整质量分析"""
        print("Starting comprehensive quality analysis...")
        
        # 1. 运行测试并收集覆盖率
        coverage_analyzer = CoverageAnalyzer()
        coverage_analyzer.start_coverage()
        
        try:
            # 运行测试套件
            print("Running test suite with coverage...")
            cmd = [
                'python', '-m', 'pytest',
                'tests/',
                '-v',
                '--tb=short',
                '-x',  # 遇到第一个失败就停止
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
            test_success = result.returncode == 0
            
        finally:
            coverage_analyzer.stop_coverage()
        
        # 2. 生成覆盖率报告
        print("Generating coverage reports...")
        coverage_reports = coverage_analyzer.generate_coverage_report(
            self.output_dir / f'coverage_{self.timestamp}'
        )
        coverage_data = coverage_analyzer.get_coverage_data()
        
        # 3. 质量门禁检查
        print("Running quality gate checks...")
        quality_gate = QualityGate()
        quality_report = quality_gate.generate_quality_report(
            coverage_data,
            self.output_dir / f'quality_report_{self.timestamp}.json'
        )
        
        # 4. 回归测试
        print("Running regression tests...")
        regression_suite = RegressionTestSuite(
            self.output_dir / 'test_baseline.json'
        )
        regression_results = regression_suite.run_regression_tests()
        regression_comparison = regression_suite.compare_with_baseline(regression_results)
        
        # 5. 生成综合报告
        comprehensive_report = {
            'timestamp': self.timestamp,
            'test_execution': {
                'success': test_success,
                'output': result.stdout if 'result' in locals() else None,
                'error': result.stderr if 'result' in locals() else None
            },
            'coverage': coverage_data,
            'quality_gate': quality_report,
            'regression': regression_comparison,
            'reports': {
                'coverage_html': str(coverage_reports['html_report']) if coverage_reports else None,
                'coverage_xml': str(coverage_reports['xml_report']) if coverage_reports else None,
                'quality_json': str(self.output_dir / f'quality_report_{self.timestamp}.json')
            }
        }
        
        # 保存综合报告
        comprehensive_file = self.output_dir / f'comprehensive_report_{self.timestamp}.json'
        with open(comprehensive_file, 'w') as f:
            json.dump(comprehensive_report, f, indent=2)
        
        # 生成HTML报告
        self.generate_html_quality_report(comprehensive_report)
        
        # 更新基线（如果没有回归）
        if not regression_comparison['regression_detected']:
            regression_suite.save_baseline(regression_results)
        
        # 打印摘要
        self.print_quality_summary(comprehensive_report)
        
        return comprehensive_report
    
    def generate_html_quality_report(self, report):
        """生成HTML质量报告"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Quality Report - {report['timestamp']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; border-radius: 5px; }}
        .success {{ background-color: #d4edda; border-left: 5px solid #28a745; }}
        .warning {{ background-color: #fff3cd; border-left: 5px solid #ffc107; }}
        .danger {{ background-color: #f8d7da; border-left: 5px solid #dc3545; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ font-size: 14px; color: #6c757d; }}
        pre {{ background-color: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Code Quality Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Report ID: {report['timestamp']}</p>
    </div>
"""
        
        # 测试执行结果
        test_class = "success" if report['test_execution']['success'] else "danger"
        html_content += f"""
    <div class="section {test_class}">
        <h2>Test Execution</h2>
        <p><strong>Status:</strong> {'✓ PASSED' if report['test_execution']['success'] else '✗ FAILED'}</p>
    </div>
"""
        
        # 覆盖率信息
        coverage = report.get('coverage', {})
        coverage_percent = coverage.get('total_coverage', 0)
        coverage_class = "success" if coverage_percent >= 80 else "warning" if coverage_percent >= 60 else "danger"
        
        html_content += f"""
    <div class="section {coverage_class}">
        <h2>Code Coverage</h2>
        <div class="metric">
            <div class="metric-value">{coverage_percent:.1f}%</div>
            <div class="metric-label">Total Coverage</div>
        </div>
    </div>
"""
        
        # 质量门禁
        quality_gate = report.get('quality_gate', {})
        gate_class = "success" if quality_gate.get('overall_passed', False) else "danger"
        
        html_content += f"""
    <div class="section {gate_class}">
        <h2>Quality Gate</h2>
        <p><strong>Status:</strong> {'✓ PASSED' if quality_gate.get('overall_passed', False) else '✗ FAILED'}</p>
    </div>
"""
        
        # 回归测试
        regression = report.get('regression', {})
        regression_class = "success" if not regression.get('regression_detected', False) else "danger"
        
        html_content += f"""
    <div class="section {regression_class}">
        <h2>Regression Analysis</h2>
        <p><strong>Status:</strong> {'✓ NO REGRESSION' if not regression.get('regression_detected', False) else '✗ REGRESSION DETECTED'}</p>
        <p>New Failures: {len(regression.get('new_failures', []))}</p>
        <p>Recovered Tests: {len(regression.get('recovered_tests', []))}</p>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        html_file = self.output_dir / f'quality_report_{self.timestamp}.html'
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        print(f"HTML quality report: {html_file}")
    
    def print_quality_summary(self, report):
        """打印质量摘要"""
        print(f"\n{'='*60}")
        print("QUALITY ANALYSIS SUMMARY")
        print(f"{'='*60}")
        
        # 测试执行
        test_status = "✓ PASSED" if report['test_execution']['success'] else "✗ FAILED"
        print(f"Test Execution: {test_status}")
        
        # 覆盖率
        coverage = report.get('coverage', {})
        coverage_percent = coverage.get('total_coverage', 0)
        print(f"Code Coverage: {coverage_percent:.1f}%")
        
        # 质量门禁
        quality_gate = report.get('quality_gate', {})
        gate_status = "✓ PASSED" if quality_gate.get('overall_passed', False) else "✗ FAILED"
        print(f"Quality Gate: {gate_status}")
        
        # 回归测试
        regression = report.get('regression', {})
        regression_status = "✓ NO REGRESSION" if not regression.get('regression_detected', False) else "✗ REGRESSION DETECTED"
        print(f"Regression: {regression_status}")
        
        print(f"\nReports saved to: {self.output_dir}")
        
        # 总体状态
        overall_success = (
            report['test_execution']['success'] and
            quality_gate.get('overall_passed', False) and
            not regression.get('regression_detected', False)
        )
        
        if overall_success:
            print("\n🎉 All quality checks passed!")
        else:
            print("\n⚠️  Some quality checks failed!")
        
        return overall_success


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run quality analysis for opitios_alpaca")
    parser.add_argument("--output-dir", default="quality_reports", help="Output directory")
    parser.add_argument("--coverage-only", action="store_true", help="Run coverage analysis only")
    parser.add_argument("--regression-only", action="store_true", help="Run regression tests only")
    
    args = parser.parse_args()
    
    manager = TestQualityManager(args.output_dir)
    
    if args.coverage_only:
        # 只运行覆盖率分析
        analyzer = CoverageAnalyzer()
        analyzer.start_coverage()
        # 这里需要运行测试...
        analyzer.stop_coverage()
        reports = analyzer.generate_coverage_report()
        print(f"Coverage reports generated: {reports}")
        
    elif args.regression_only:
        # 只运行回归测试
        suite = RegressionTestSuite()
        results = suite.run_regression_tests()
        comparison = suite.compare_with_baseline(results)
        print(f"Regression analysis: {comparison}")
        
    else:
        # 运行完整质量分析
        report = manager.run_full_quality_analysis()
        success = manager.print_quality_summary(report)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()