#!/usr/bin/env python3
"""
System Health Check Script for Opitios Alpaca Trading Service

This script performs comprehensive health monitoring and diagnostics
for the running trading service.

Usage:
    python docs/scripts/health_check.py

Features:
- Real-time system monitoring
- API endpoint health checking
- Performance metrics collection
- Database connectivity testing
- Alert generation for critical issues
"""

import os
import sys
import time
import json
import requests
import psutil
import socket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Import color utilities from setup_validator
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def check_server_process() -> Tuple[bool, Dict]:
    """Check if the server process is running"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'cpu_percent']):
            try:
                if 'python' in proc.info['name'].lower() and proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'main.py' in cmdline or 'uvicorn' in cmdline:
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline,
                            'memory_mb': proc.info['memory_info'].rss / 1024 / 1024,
                            'cpu_percent': proc.info['cpu_percent']
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if processes:
            return True, {'processes': processes, 'count': len(processes)}
        else:
            return False, {'error': 'No server processes found'}
            
    except Exception as e:
        return False, {'error': str(e)}

def check_port_availability(port: int = 8081) -> Tuple[bool, str]:
    """Check if the service port is available/in use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            if result == 0:
                return True, f"Port {port} is in use (service running)"
            else:
                return False, f"Port {port} is not in use (service not running)"
    except Exception as e:
        return False, f"Error checking port {port}: {str(e)}"

def check_api_endpoints(base_url: str = "http://localhost:8081") -> Dict[str, Dict]:
    """Check health of API endpoints"""
    endpoints = {
        'root': '/',
        'health': '/api/v1/health',
        'test_connection': '/api/v1/test-connection',
        'account': '/api/v1/account',
        'docs': '/docs'
    }
    
    results = {}
    
    for name, endpoint in endpoints.items():
        try:
            start_time = time.time()
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            results[name] = {
                'status_code': response.status_code,
                'response_time_ms': round(response_time, 2),
                'success': 200 <= response.status_code < 300,
                'content_length': len(response.content),
                'headers': dict(response.headers)
            }
            
            # Try to parse JSON response
            try:
                results[name]['json_response'] = response.json()
            except:
                results[name]['json_response'] = None
                
        except requests.exceptions.ConnectionError:
            results[name] = {
                'error': 'Connection refused - server not running?',
                'success': False
            }
        except requests.exceptions.Timeout:
            results[name] = {
                'error': 'Request timeout',
                'success': False
            }
        except Exception as e:
            results[name] = {
                'error': str(e),
                'success': False
            }
    
    return results

def check_system_resources() -> Dict:
    """Check system resource usage"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage for current directory
        disk = psutil.disk_usage('.')
        
        # Network stats (if available)
        try:
            network = psutil.net_io_counters()
            network_stats = {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
        except:
            network_stats = None
        
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            },
            'memory': {
                'total_gb': round(memory.total / 1024**3, 2),
                'available_gb': round(memory.available / 1024**3, 2),
                'percent_used': memory.percent,
                'free_gb': round(memory.free / 1024**3, 2)
            },
            'disk': {
                'total_gb': round(disk.total / 1024**3, 2),
                'free_gb': round(disk.free / 1024**3, 2),
                'used_gb': round(disk.used / 1024**3, 2),
                'percent_used': round((disk.used / disk.total) * 100, 1)
            },
            'network': network_stats
        }
        
    except Exception as e:
        return {'error': str(e)}

def check_log_files() -> Dict:
    """Check log files for errors and status"""
    log_dir = Path('logs')
    results = {}
    
    if not log_dir.exists():
        return {'error': 'Log directory not found'}
    
    log_files = list(log_dir.glob('*.log'))
    
    for log_file in log_files:
        try:
            file_stats = log_file.stat()
            
            # Get recent log entries (last 100 lines)
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            # Count error levels
            error_count = sum(1 for line in recent_lines if 'ERROR' in line.upper())
            warning_count = sum(1 for line in recent_lines if 'WARNING' in line.upper())
            
            results[log_file.name] = {
                'size_mb': round(file_stats.st_size / 1024 / 1024, 2),
                'modified': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'total_lines': len(lines),
                'recent_errors': error_count,
                'recent_warnings': warning_count,
                'recent_lines_sample': recent_lines[-5:] if recent_lines else []
            }
            
        except Exception as e:
            results[log_file.name] = {'error': str(e)}
    
    return results

def check_database_connectivity() -> Tuple[bool, str]:
    """Check database connectivity"""
    db_file = Path('users.db')
    
    if not db_file.exists():
        return False, "Database file (users.db) not found"
    
    try:
        import sqlite3
        
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Get file size
        file_size = db_file.stat().st_size
        
        conn.close()
        
        return True, f"Database accessible, {len(tables)} tables, {file_size} bytes"
        
    except Exception as e:
        return False, f"Database error: {str(e)}"

def check_environment_config() -> Dict:
    """Check environment configuration"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        return {'error': 'python-dotenv not available'}
    
    env_vars = [
        'ALPACA_API_KEY',
        'ALPACA_SECRET_KEY',
        'ALPACA_BASE_URL',
        'ALPACA_PAPER_TRADING',
        'HOST',
        'PORT',
        'DEBUG'
    ]
    
    config = {}
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive information
            if 'KEY' in var or 'SECRET' in var:
                config[var] = f"{'*' * (len(value) - 4)}{value[-4:]}" if len(value) > 4 else "***"
            else:
                config[var] = value
        else:
            config[var] = "NOT SET"
    
    return config

def generate_health_score(results: Dict) -> Tuple[int, List[str]]:
    """Generate overall health score and recommendations"""
    score = 100
    issues = []
    
    # Server process check (30 points)
    if not results.get('server_process', {}).get('success', False):
        score -= 30
        issues.append("Server process not running")
    
    # API endpoints check (25 points)
    api_results = results.get('api_endpoints', {})
    failed_endpoints = sum(1 for endpoint, data in api_results.items() 
                          if not data.get('success', False))
    if failed_endpoints > 0:
        penalty = min(25, failed_endpoints * 5)
        score -= penalty
        issues.append(f"{failed_endpoints} API endpoints failing")
    
    # System resources check (20 points)
    resources = results.get('system_resources', {})
    if resources.get('memory', {}).get('percent_used', 0) > 90:
        score -= 10
        issues.append("High memory usage (>90%)")
    if resources.get('cpu', {}).get('percent', 0) > 80:
        score -= 10
        issues.append("High CPU usage (>80%)")
    
    # Log files check (15 points)
    log_results = results.get('log_files', {})
    for log_name, log_data in log_results.items():
        if log_data.get('recent_errors', 0) > 5:
            score -= 5
            issues.append(f"Many recent errors in {log_name}")
    
    # Database check (10 points)
    if not results.get('database', {}).get('success', False):
        score -= 10
        issues.append("Database connectivity issues")
    
    return max(0, score), issues

def format_uptime(start_time: datetime) -> str:
    """Format uptime duration"""
    uptime = datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"

def main():
    """Main health check workflow"""
    print_header("Opitios Alpaca Trading Service - Health Check")
    print(f"{Colors.WHITE}Comprehensive system health monitoring and diagnostics{Colors.END}")
    
    start_time = time.time()
    all_results = {}
    
    # 1. Check Server Process
    print(f"\n{Colors.CYAN}[1/8] Checking server process...{Colors.END}")
    server_ok, server_data = check_server_process()
    all_results['server_process'] = {'success': server_ok, 'data': server_data}
    
    if server_ok:
        processes = server_data['processes']
        print_success(f"Found {len(processes)} server process(es)")
        for proc in processes:
            print_info(f"PID {proc['pid']}: {proc['memory_mb']:.1f}MB, {proc['cpu_percent']:.1f}% CPU")
    else:
        print_error(f"Server process check failed: {server_data.get('error', 'Unknown error')}")
    
    # 2. Check Port Availability
    print(f"\n{Colors.CYAN}[2/8] Checking port availability...{Colors.END}")
    port_ok, port_msg = check_port_availability()
    all_results['port_check'] = {'success': port_ok, 'message': port_msg}
    
    if port_ok:
        print_success(port_msg)
    else:
        print_warning(port_msg)
    
    # 3. Check API Endpoints
    print(f"\n{Colors.CYAN}[3/8] Testing API endpoints...{Colors.END}")
    api_results = check_api_endpoints()
    all_results['api_endpoints'] = api_results
    
    for endpoint, result in api_results.items():
        if result.get('success', False):
            response_time = result.get('response_time_ms', 0)
            print_success(f"{endpoint}: {result['status_code']} ({response_time}ms)")
        else:
            error = result.get('error', 'Unknown error')
            print_error(f"{endpoint}: {error}")
    
    # 4. Check System Resources
    print(f"\n{Colors.CYAN}[4/8] Monitoring system resources...{Colors.END}")
    resource_results = check_system_resources()
    all_results['system_resources'] = resource_results
    
    if 'error' not in resource_results:
        cpu = resource_results['cpu']
        memory = resource_results['memory']
        disk = resource_results['disk']
        
        print_info(f"CPU: {cpu['percent']:.1f}% ({cpu['count']} cores)")
        print_info(f"Memory: {memory['percent_used']:.1f}% used ({memory['available_gb']:.1f}GB available)")
        print_info(f"Disk: {disk['percent_used']:.1f}% used ({disk['free_gb']:.1f}GB free)")
        
        # Resource warnings
        if memory['percent_used'] > 90:
            print_warning("High memory usage detected")
        if cpu['percent'] > 80:
            print_warning("High CPU usage detected")
        if disk['percent_used'] > 90:
            print_warning("Low disk space")
    else:
        print_error(f"Resource monitoring failed: {resource_results['error']}")
    
    # 5. Check Log Files
    print(f"\n{Colors.CYAN}[5/8] Analyzing log files...{Colors.END}")
    log_results = check_log_files()
    all_results['log_files'] = log_results
    
    if 'error' not in log_results:
        for log_name, log_data in log_results.items():
            if 'error' not in log_data:
                errors = log_data['recent_errors']
                warnings = log_data['recent_warnings']
                size = log_data['size_mb']
                
                if errors > 0 or warnings > 0:
                    print_warning(f"{log_name}: {errors} errors, {warnings} warnings ({size}MB)")
                else:
                    print_success(f"{log_name}: Clean ({size}MB)")
            else:
                print_error(f"{log_name}: {log_data['error']}")
    else:
        print_error(f"Log analysis failed: {log_results['error']}")
    
    # 6. Check Database
    print(f"\n{Colors.CYAN}[6/8] Testing database connectivity...{Colors.END}")
    db_ok, db_msg = check_database_connectivity()
    all_results['database'] = {'success': db_ok, 'message': db_msg}
    
    if db_ok:
        print_success(db_msg)
    else:
        print_error(db_msg)
    
    # 7. Check Configuration
    print(f"\n{Colors.CYAN}[7/8] Validating configuration...{Colors.END}")
    config_results = check_environment_config()
    all_results['configuration'] = config_results
    
    if 'error' not in config_results:
        configured_vars = sum(1 for value in config_results.values() if value != "NOT SET")
        total_vars = len(config_results)
        print_success(f"Configuration: {configured_vars}/{total_vars} variables set")
        
        for var, value in config_results.items():
            if value == "NOT SET":
                print_warning(f"{var}: Not configured")
            else:
                print_info(f"{var}: {value}")
    else:
        print_error(f"Configuration check failed: {config_results['error']}")
    
    # 8. Generate Health Score
    print(f"\n{Colors.CYAN}[8/8] Calculating health score...{Colors.END}")
    health_score, issues = generate_health_score(all_results)
    
    # Health Summary
    print_header("Health Summary")
    
    total_time = time.time() - start_time
    print_info(f"Health check completed in {total_time:.2f} seconds")
    
    # Overall score
    if health_score >= 90:
        print_success(f"System Health: {health_score}/100 - Excellent")
    elif health_score >= 70:
        print_warning(f"System Health: {health_score}/100 - Good with minor issues")
    else:
        print_error(f"System Health: {health_score}/100 - Needs attention")
    
    # Issues and recommendations
    if issues:
        print(f"\n{Colors.YELLOW}Issues detected:{Colors.END}")
        for issue in issues:
            print(f"  • {issue}")
        
        print(f"\n{Colors.CYAN}Recommendations:{Colors.END}")
        if "Server process not running" in issues:
            print("  • Start the server: python main.py")
        if "API endpoints failing" in issues:
            print("  • Check server logs for errors")
        if "High memory usage" in issues:
            print("  • Consider restarting the server")
        if "Database connectivity" in issues:
            print("  • Check database file permissions")
    else:
        print_success("No critical issues detected")
    
    # Service status
    print(f"\n{Colors.BOLD}Service Status:{Colors.END}")
    if server_ok and port_ok:
        print_success("🚀 Service is running and accessible")
        print_info("API Documentation: http://localhost:8081/docs")
        print_info("Service Health: http://localhost:8081/api/v1/health")
    else:
        print_error("⚠️  Service is not running properly")
        print_info("Start service: python main.py")
    
    # Save detailed report
    report_file = f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    all_results['health_summary'] = {
        'score': health_score,
        'issues': issues,
        'check_time': datetime.now().isoformat(),
        'duration_seconds': total_time
    }
    
    try:
        with open(report_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print_info(f"Detailed report saved: {report_file}")
    except Exception as e:
        print_warning(f"Could not save report: {str(e)}")
    
    return health_score >= 70

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Health check cancelled by user.{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error during health check: {str(e)}{Colors.END}")
        sys.exit(1)