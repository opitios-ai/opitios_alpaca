#!/usr/bin/env python3
"""
Performance Testing - Script Execution Tests

This module validates the performance characteristics of interactive scripts
and documentation system components, ensuring they meet speed and efficiency
requirements for optimal user experience.

Test Focus:
- Script execution time benchmarks
- Memory usage optimization
- Network request efficiency  
- Documentation loading performance
- Resource utilization monitoring
- Scalability under load

Usage:
    python docs/testing/performance/script_execution_tests.py
"""

import os
import sys
import time
import psutil
import threading
import concurrent.futures
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import statistics
import gc

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class PerformanceMetric(Enum):
    """Performance metrics to measure"""
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"


@dataclass
class PerformanceResult:
    """Result of performance test"""
    test_name: str
    script_name: str
    execution_time: float
    memory_peak_mb: float
    memory_avg_mb: float
    cpu_peak_percent: float
    cpu_avg_percent: float
    disk_read_mb: float
    disk_write_mb: float
    success: bool
    iterations: int
    percentiles: Dict[str, float]
    error_message: Optional[str] = None


class PerformanceTester:
    """Tests performance characteristics of documentation system scripts"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.scripts_path = self.project_root / "docs" / "scripts"
        self.results: List[PerformanceResult] = []
        
        # Performance targets
        self.performance_targets = {
            'setup_validator': {
                'execution_time': 5.0,      # seconds
                'memory_peak': 100.0,       # MB
                'cpu_peak': 80.0           # percent
            },
            'health_check': {
                'execution_time': 10.0,     # seconds
                'memory_peak': 50.0,        # MB
                'cpu_peak': 70.0           # percent
            },
            'config_helper': {
                'execution_time': 3.0,      # seconds
                'memory_peak': 30.0,        # MB
                'cpu_peak': 50.0           # percent
            },
            'doc_validator': {
                'execution_time': 15.0,     # seconds
                'memory_peak': 75.0,        # MB
                'cpu_peak': 60.0           # percent
            }
        }
    
    def _monitor_process(self, process: psutil.Process, duration: float, 
                        interval: float = 0.1) -> Dict[str, List[float]]:
        """Monitor process resource usage"""
        metrics = {
            'memory_mb': [],
            'cpu_percent': [],
            'disk_read_mb': [],
            'disk_write_mb': []
        }
        
        start_time = time.time()
        initial_io = None
        
        try:
            # Get initial I/O counters
            try:
                initial_io = process.io_counters()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            while time.time() - start_time < duration:
                try:
                    # Memory usage
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    metrics['memory_mb'].append(memory_mb)
                    
                    # CPU usage
                    cpu_percent = process.cpu_percent()
                    metrics['cpu_percent'].append(cpu_percent)
                    
                    # Disk I/O
                    try:
                        current_io = process.io_counters()
                        if initial_io:
                            disk_read_mb = (current_io.read_bytes - initial_io.read_bytes) / 1024 / 1024
                            disk_write_mb = (current_io.write_bytes - initial_io.write_bytes) / 1024 / 1024
                            metrics['disk_read_mb'].append(disk_read_mb)
                            metrics['disk_write_mb'].append(disk_write_mb)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                
                time.sleep(interval)
                
        except Exception:
            pass
        
        return metrics
    
    def _run_script_with_monitoring(self, script_path: Path, timeout: int = 60) -> Tuple[bool, float, Dict[str, List[float]], str]:
        """Run script with resource monitoring"""
        start_time = time.time()
        
        try:
            # Start the script
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.project_root)
            )
            
            # Monitor the process
            psutil_process = psutil.Process(process.pid)
            monitoring_thread = threading.Thread(
                target=lambda: self._monitor_process(psutil_process, timeout),
                daemon=True
            )
            
            metrics = {'memory_mb': [], 'cpu_percent': [], 'disk_read_mb': [], 'disk_write_mb': []}
            
            # Start monitoring in background
            def monitor():
                nonlocal metrics
                metrics = self._monitor_process(psutil_process, timeout)
            
            monitor_thread = threading.Thread(target=monitor, daemon=True)
            monitor_thread.start()
            
            # Wait for process completion
            stdout, stderr = process.communicate(timeout=timeout)
            execution_time = time.time() - start_time
            
            # Wait for monitoring to complete
            monitor_thread.join(timeout=1.0)
            
            success = process.returncode == 0
            error_output = stderr if not success else ""
            
            return success, execution_time, metrics, error_output
            
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait()
            except:
                pass
            
            execution_time = time.time() - start_time
            return False, execution_time, {}, "Script execution timeout"
        
        except Exception as e:
            execution_time = time.time() - start_time
            return False, execution_time, {}, str(e)
    
    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate performance percentiles"""
        if not values:
            return {'p50': 0, 'p90': 0, 'p95': 0, 'p99': 0}
        
        return {
            'p50': statistics.median(values),
            'p90': statistics.quantiles(sorted(values), n=10)[8],  # 90th percentile
            'p95': statistics.quantiles(sorted(values), n=20)[18], # 95th percentile
            'p99': statistics.quantiles(sorted(values), n=100)[98] # 99th percentile
        }
    
    def test_script_performance(self, script_name: str, iterations: int = 3) -> PerformanceResult:
        """Test performance of a specific script"""
        script_path = self.scripts_path / script_name
        
        if not script_path.exists():
            return PerformanceResult(
                test_name="script_performance",
                script_name=script_name,
                execution_time=0,
                memory_peak_mb=0,
                memory_avg_mb=0,
                cpu_peak_percent=0,
                cpu_avg_percent=0,
                disk_read_mb=0,
                disk_write_mb=0,
                success=False,
                iterations=0,
                percentiles={},
                error_message=f"Script not found: {script_path}"
            )
        
        print(f"\n📊 Testing {script_name} performance ({iterations} iterations)")
        
        execution_times = []
        memory_peaks = []
        memory_avgs = []
        cpu_peaks = []
        cpu_avgs = []
        disk_reads = []
        disk_writes = []
        success_count = 0
        errors = []
        
        for i in range(iterations):
            print(f"  Iteration {i+1}/{iterations}...", end=" ")
            
            # Force garbage collection before test
            gc.collect()
            
            success, exec_time, metrics, error = self._run_script_with_monitoring(script_path)
            
            if success:
                success_count += 1
                execution_times.append(exec_time)
                
                if metrics.get('memory_mb'):
                    memory_peaks.append(max(metrics['memory_mb']))
                    memory_avgs.append(statistics.mean(metrics['memory_mb']))
                
                if metrics.get('cpu_percent'):
                    cpu_peaks.append(max(metrics['cpu_percent']))
                    cpu_avgs.append(statistics.mean(metrics['cpu_percent']))
                
                if metrics.get('disk_read_mb'):
                    disk_reads.append(max(metrics['disk_read_mb']) if metrics['disk_read_mb'] else 0)
                
                if metrics.get('disk_write_mb'):
                    disk_writes.append(max(metrics['disk_write_mb']) if metrics['disk_write_mb'] else 0)
                
                print(f"✅ {exec_time:.2f}s")
            else:
                errors.append(error)
                print(f"❌ {error[:50]}...")
        
        # Calculate aggregated metrics
        overall_success = success_count > 0
        avg_exec_time = statistics.mean(execution_times) if execution_times else 0
        peak_memory = max(memory_peaks) if memory_peaks else 0
        avg_memory = statistics.mean(memory_avgs) if memory_avgs else 0
        peak_cpu = max(cpu_peaks) if cpu_peaks else 0
        avg_cpu = statistics.mean(cpu_avgs) if cpu_avgs else 0
        total_disk_read = max(disk_reads) if disk_reads else 0
        total_disk_write = max(disk_writes) if disk_writes else 0
        
        # Calculate percentiles for execution time
        percentiles = self._calculate_percentiles(execution_times)
        
        return PerformanceResult(
            test_name="script_performance",
            script_name=script_name,
            execution_time=avg_exec_time,
            memory_peak_mb=peak_memory,
            memory_avg_mb=avg_memory,
            cpu_peak_percent=peak_cpu,
            cpu_avg_percent=avg_cpu,
            disk_read_mb=total_disk_read,
            disk_write_mb=total_disk_write,
            success=overall_success,
            iterations=success_count,
            percentiles=percentiles,
            error_message="; ".join(errors[:3]) if errors else None
        )
    
    def test_concurrent_execution(self, script_name: str, concurrent_runs: int = 3) -> PerformanceResult:
        """Test script performance under concurrent execution"""
        script_path = self.scripts_path / script_name
        
        if not script_path.exists():
            return PerformanceResult(
                test_name="concurrent_execution",
                script_name=script_name,
                execution_time=0,
                memory_peak_mb=0,
                memory_avg_mb=0,
                cpu_peak_percent=0,
                cpu_avg_percent=0,
                disk_read_mb=0,
                disk_write_mb=0,
                success=False,
                iterations=0,
                percentiles={},
                error_message=f"Script not found: {script_path}"
            )
        
        print(f"\n🔄 Testing {script_name} concurrent execution ({concurrent_runs} parallel runs)")
        
        start_time = time.time()
        
        # Monitor system resources during concurrent execution
        initial_memory = psutil.virtual_memory().used / 1024 / 1024
        initial_cpu = psutil.cpu_percent(interval=None)
        
        def run_single_instance():
            """Run single script instance"""
            try:
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.project_root)
                )
                return result.returncode == 0, time.time()
            except subprocess.TimeoutExpired:
                return False, time.time()
            except Exception:
                return False, time.time()
        
        # Run concurrent instances
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_runs) as executor:
            futures = [executor.submit(run_single_instance) for _ in range(concurrent_runs)]
            
            # Monitor resources during execution
            resource_samples = []
            monitoring_start = time.time()
            
            while not all(f.done() for f in futures):
                memory_usage = psutil.virtual_memory().used / 1024 / 1024
                cpu_usage = psutil.cpu_percent(interval=None)
                resource_samples.append({
                    'memory_mb': memory_usage,
                    'cpu_percent': cpu_usage,
                    'timestamp': time.time() - monitoring_start
                })
                time.sleep(0.1)
            
            # Collect results
            results = [f.result() for f in futures]
        
        total_execution_time = time.time() - start_time
        successful_runs = sum(1 for success, _ in results if success)
        
        # Calculate resource usage
        if resource_samples:
            peak_memory = max(sample['memory_mb'] for sample in resource_samples) - initial_memory
            avg_memory = statistics.mean(sample['memory_mb'] for sample in resource_samples) - initial_memory
            peak_cpu = max(sample['cpu_percent'] for sample in resource_samples)
            avg_cpu = statistics.mean(sample['cpu_percent'] for sample in resource_samples)
        else:
            peak_memory = avg_memory = peak_cpu = avg_cpu = 0
        
        return PerformanceResult(
            test_name="concurrent_execution",
            script_name=script_name,
            execution_time=total_execution_time,
            memory_peak_mb=max(0, peak_memory),
            memory_avg_mb=max(0, avg_memory),
            cpu_peak_percent=peak_cpu,
            cpu_avg_percent=avg_cpu,
            disk_read_mb=0,  # Not measured in concurrent test
            disk_write_mb=0,
            success=successful_runs == concurrent_runs,
            iterations=successful_runs,
            percentiles={'concurrent_runs': concurrent_runs, 'successful_runs': successful_runs},
            error_message=None if successful_runs == concurrent_runs else f"Only {successful_runs}/{concurrent_runs} runs succeeded"
        )
    
    def test_memory_leak_detection(self, script_name: str, iterations: int = 5) -> PerformanceResult:
        """Test for memory leaks in script execution"""
        script_path = self.scripts_path / script_name
        
        if not script_path.exists():
            return PerformanceResult(
                test_name="memory_leak_detection",
                script_name=script_name,
                execution_time=0,
                memory_peak_mb=0,
                memory_avg_mb=0,
                cpu_peak_percent=0,
                cpu_avg_percent=0,
                disk_read_mb=0,
                disk_write_mb=0,
                success=False,
                iterations=0,
                percentiles={},
                error_message=f"Script not found: {script_path}"
            )
        
        print(f"\n🔍 Testing {script_name} for memory leaks ({iterations} sequential runs)")
        
        memory_usage_history = []
        execution_times = []
        
        # Baseline memory usage
        gc.collect()
        baseline_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        for i in range(iterations):
            print(f"  Run {i+1}/{iterations}...", end=" ")
            
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.project_root)
                )
                
                execution_time = time.time() - start_time
                execution_times.append(execution_time)
                
                # Measure memory after execution
                gc.collect()  # Force garbage collection
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_usage_history.append(current_memory - baseline_memory)
                
                print(f"✅ {execution_time:.2f}s, Memory: +{current_memory - baseline_memory:.1f}MB")
                
            except subprocess.TimeoutExpired:
                print("❌ Timeout")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                break
        
        # Analyze memory usage trend
        if len(memory_usage_history) >= 3:
            # Check if memory usage is consistently increasing
            memory_trend = []
            for i in range(1, len(memory_usage_history)):
                memory_trend.append(memory_usage_history[i] - memory_usage_history[i-1])
            
            # Memory leak detected if average trend is positive and significant
            avg_trend = statistics.mean(memory_trend)
            memory_leak_detected = avg_trend > 5.0  # More than 5MB average increase per run
        else:
            memory_leak_detected = False
            avg_trend = 0
        
        return PerformanceResult(
            test_name="memory_leak_detection",
            script_name=script_name,
            execution_time=statistics.mean(execution_times) if execution_times else 0,
            memory_peak_mb=max(memory_usage_history) if memory_usage_history else 0,
            memory_avg_mb=statistics.mean(memory_usage_history) if memory_usage_history else 0,
            cpu_peak_percent=0,  # Not measured in this test
            cpu_avg_percent=0,
            disk_read_mb=0,
            disk_write_mb=0,
            success=not memory_leak_detected,
            iterations=len(execution_times),
            percentiles={'memory_trend': avg_trend, 'leak_detected': memory_leak_detected},
            error_message="Potential memory leak detected" if memory_leak_detected else None
        )
    
    def run_comprehensive_performance_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance test suite"""
        print("🚀 Starting Performance Testing Suite")
        print("Testing interactive scripts for speed, memory usage, and efficiency")
        
        # Scripts to test
        scripts_to_test = [
            "setup_validator.py",
            "health_check.py"
        ]
        
        # Optional scripts (test if they exist)
        optional_scripts = [
            "config_helper.py",
            "doc_validator.py"
        ]
        
        for script in optional_scripts:
            if (self.scripts_path / script).exists():
                scripts_to_test.append(script)
        
        # Run performance tests
        for script_name in scripts_to_test:
            print(f"\n{'='*60}")
            print(f"Testing Script: {script_name}")
            print(f"{'='*60}")
            
            # Single execution performance test
            result = self.test_script_performance(script_name, iterations=3)
            self.results.append(result)
            
            # Concurrent execution test
            if result.success:
                concurrent_result = self.test_concurrent_execution(script_name, concurrent_runs=2)
                self.results.append(concurrent_result)
                
                # Memory leak detection
                leak_result = self.test_memory_leak_detection(script_name, iterations=3)
                self.results.append(leak_result)
        
        # Calculate overall metrics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        overall_success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Performance target analysis
        target_violations = []
        target_compliance = 0
        
        for result in self.results:
            if result.test_name == "script_performance":
                script_base_name = result.script_name.replace('.py', '')
                if script_base_name in self.performance_targets:
                    targets = self.performance_targets[script_base_name]
                    
                    compliant = True
                    if result.execution_time > targets['execution_time']:
                        target_violations.append(f"{result.script_name} execution time: {result.execution_time:.1f}s > {targets['execution_time']}s")
                        compliant = False
                    
                    if result.memory_peak_mb > targets['memory_peak']:
                        target_violations.append(f"{result.script_name} memory usage: {result.memory_peak_mb:.1f}MB > {targets['memory_peak']}MB")
                        compliant = False
                    
                    if result.cpu_peak_percent > targets['cpu_peak']:
                        target_violations.append(f"{result.script_name} CPU usage: {result.cpu_peak_percent:.1f}% > {targets['cpu_peak']}%")
                        compliant = False
                    
                    if compliant:
                        target_compliance += 1
        
        performance_target_rate = (target_compliance / len([r for r in self.results if r.test_name == "script_performance"]) * 100) if any(r.test_name == "script_performance" for r in self.results) else 0
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'overall_success_rate': overall_success_rate,
            'performance_target_rate': performance_target_rate,
            'target_violations': target_violations,
            'meets_performance_targets': len(target_violations) == 0,
            'scripts_tested': scripts_to_test,
            'performance_targets': self.performance_targets,
            'detailed_results': self.results
        }
    
    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """Generate comprehensive performance test report"""
        report = f"""
# Performance Testing Report

## Executive Summary
- **Total Tests**: {metrics['total_tests']}
- **Passed Tests**: {metrics['passed_tests']}
- **Failed Tests**: {metrics['failed_tests']}
- **Overall Success Rate**: {metrics['overall_success_rate']:.1f}%
- **Performance Target Compliance**: {metrics['performance_target_rate']:.1f}%
- **Meets Performance Targets**: {'✅ YES' if metrics['meets_performance_targets'] else '❌ NO'}

## Performance Targets
"""
        
        for script, targets in metrics['performance_targets'].items():
            report += f"### {script}.py\n"
            report += f"- **Execution Time**: <{targets['execution_time']}s\n"
            report += f"- **Memory Peak**: <{targets['memory_peak']}MB\n"  
            report += f"- **CPU Peak**: <{targets['cpu_peak']}%\n\n"
        
        report += "## Test Results by Script\n\n"
        
        # Group results by script
        script_results = {}
        for result in metrics['detailed_results']:
            if result.script_name not in script_results:
                script_results[result.script_name] = []
            script_results[result.script_name].append(result)
        
        for script_name, results in script_results.items():
            report += f"### {script_name}\n"
            
            for result in results:
                status = "✅ PASS" if result.success else "❌ FAIL"
                report += f"#### {result.test_name.replace('_', ' ').title()} {status}\n"
                
                if result.test_name == "script_performance":
                    report += f"- **Execution Time**: {result.execution_time:.2f}s (avg of {result.iterations} runs)\n"
                    report += f"- **Memory Peak**: {result.memory_peak_mb:.1f}MB\n"
                    report += f"- **Memory Average**: {result.memory_avg_mb:.1f}MB\n"
                    report += f"- **CPU Peak**: {result.cpu_peak_percent:.1f}%\n"
                    report += f"- **CPU Average**: {result.cpu_avg_percent:.1f}%\n"
                    
                    if result.percentiles:
                        report += f"- **95th Percentile**: {result.percentiles.get('p95', 0):.2f}s\n"
                        report += f"- **99th Percentile**: {result.percentiles.get('p99', 0):.2f}s\n"
                
                elif result.test_name == "concurrent_execution":
                    concurrent_runs = result.percentiles.get('concurrent_runs', 0)
                    successful_runs = result.percentiles.get('successful_runs', 0)
                    report += f"- **Concurrent Runs**: {concurrent_runs}\n"
                    report += f"- **Successful Runs**: {successful_runs}\n"
                    report += f"- **Total Time**: {result.execution_time:.2f}s\n"
                    report += f"- **Memory Impact**: +{result.memory_peak_mb:.1f}MB\n"
                
                elif result.test_name == "memory_leak_detection":
                    memory_trend = result.percentiles.get('memory_trend', 0)
                    leak_detected = result.percentiles.get('leak_detected', False)
                    report += f"- **Memory Trend**: {memory_trend:+.2f}MB per run\n"
                    report += f"- **Leak Detected**: {'⚠️ YES' if leak_detected else '✅ NO'}\n"
                    report += f"- **Peak Memory**: {result.memory_peak_mb:.1f}MB\n"
                
                if result.error_message:
                    report += f"- **Error**: {result.error_message}\n"
                
                report += "\n"
        
        # Performance violations
        if metrics['target_violations']:
            report += "## Performance Target Violations\n\n"
            for violation in metrics['target_violations']:
                report += f"- ⚠️ {violation}\n"
            report += "\n"
        
        # Performance insights
        report += "## Performance Insights\n\n"
        
        # Execution time analysis
        perf_results = [r for r in metrics['detailed_results'] if r.test_name == "script_performance" and r.success]
        if perf_results:
            fastest_script = min(perf_results, key=lambda x: x.execution_time)
            slowest_script = max(perf_results, key=lambda x: x.execution_time)
            
            report += f"### Execution Time Analysis\n"
            report += f"- **Fastest Script**: {fastest_script.script_name} ({fastest_script.execution_time:.2f}s)\n"
            report += f"- **Slowest Script**: {slowest_script.script_name} ({slowest_script.execution_time:.2f}s)\n"
            
            avg_exec_time = sum(r.execution_time for r in perf_results) / len(perf_results)
            report += f"- **Average Execution Time**: {avg_exec_time:.2f}s\n\n"
        
        # Memory usage analysis
        if perf_results:
            least_memory = min(perf_results, key=lambda x: x.memory_peak_mb)
            most_memory = max(perf_results, key=lambda x: x.memory_peak_mb)
            
            report += f"### Memory Usage Analysis\n"
            report += f"- **Most Efficient**: {least_memory.script_name} ({least_memory.memory_peak_mb:.1f}MB peak)\n"
            report += f"- **Most Memory Intensive**: {most_memory.script_name} ({most_memory.memory_peak_mb:.1f}MB peak)\n"
            
            avg_memory = sum(r.memory_peak_mb for r in perf_results) / len(perf_results)
            report += f"- **Average Memory Usage**: {avg_memory:.1f}MB\n\n"
        
        # Recommendations
        report += "## Recommendations\n\n"
        
        if metrics['meets_performance_targets']:
            report += "🎉 **Excellent Performance** - All scripts meet performance targets!\n\n"
        else:
            report += "⚠️ **Performance Optimization Needed**\n\n"
        
        if metrics['target_violations']:
            report += "### Priority Optimizations:\n"
            for violation in metrics['target_violations'][:3]:  # Top 3 violations
                script_name = violation.split()[0]
                if 'execution time' in violation:
                    report += f"- Optimize {script_name} execution speed\n"
                elif 'memory usage' in violation:
                    report += f"- Reduce {script_name} memory consumption\n"
                elif 'CPU usage' in violation:
                    report += f"- Optimize {script_name} CPU efficiency\n"
        
        # General recommendations
        report += f"""
### General Performance Guidelines:
- Keep script execution time under 5 seconds for optimal user experience
- Minimize memory usage to ensure compatibility with resource-constrained systems
- Implement progress indicators for operations taking >3 seconds
- Use async/await patterns for I/O-bound operations
- Cache frequently accessed data to reduce redundant processing

### Monitoring and Maintenance:
- Set up automated performance regression testing
- Monitor performance metrics in production
- Establish performance budgets for new features
- Regular performance profiling and optimization

---

**Test Environment**: {sys.platform}  
**Python Version**: {sys.version.split()[0]}  
**Test Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Framework Version**: 1.0.0
"""
        
        return report


def main():
    """Main test execution"""
    tester = PerformanceTester()
    
    # Run comprehensive performance tests
    metrics = tester.run_comprehensive_performance_tests()
    
    # Generate and display report
    report = tester.generate_report(metrics)
    print("\n" + "="*80)
    print(report)
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"performance_test_results_{timestamp}.json"
    
    # Prepare serializable data
    serializable_results = []
    for result in tester.results:
        serializable_results.append({
            'test_name': result.test_name,
            'script_name': result.script_name,
            'execution_time': result.execution_time,
            'memory_peak_mb': result.memory_peak_mb,
            'memory_avg_mb': result.memory_avg_mb,
            'cpu_peak_percent': result.cpu_peak_percent,
            'cpu_avg_percent': result.cpu_avg_percent,
            'disk_read_mb': result.disk_read_mb,
            'disk_write_mb': result.disk_write_mb,
            'success': result.success,
            'iterations': result.iterations,
            'percentiles': result.percentiles,
            'error_message': result.error_message
        })
    
    save_data = {
        'metrics': metrics,
        'detailed_results': serializable_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Return success if performance targets are met
    return metrics['meets_performance_targets'] and metrics['overall_success_rate'] >= 80


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)