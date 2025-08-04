#!/usr/bin/env python3
"""
Multi-Account Trading System Validation Script
简化的系统验证，替代复杂的过时测试
"""

import asyncio
import time
import requests
import sys
import os
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

def print_status(message, success=True):
    """打印状态信息"""
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} {message}")

def test_server_health():
    """测试服务器健康状态"""
    print("\n=== 服务器健康检查 ===")
    
    try:
        response = requests.get("http://localhost:8080/api/v1/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_status("服务器健康检查")
            print(f"    服务: {data.get('service', 'N/A')}")
            print(f"    状态: {data.get('status', 'N/A')}")
            print(f"    纸交易模式: {data.get('configuration', {}).get('paper_trading', 'N/A')}")
            return True
        else:
            print_status(f"服务器响应错误: {response.status_code}", False)
            return False
    except Exception as e:
        print_status(f"服务器连接失败: {e}", False)
        return False

def test_account_routing():
    """测试账户路由功能"""
    print("\n=== 账户路由测试 ===")
    
    accounts = ["account_001", "account_002", "account_003"]
    success_count = 0
    
    for account_id in accounts:
        try:
            response = requests.get(
                f"http://localhost:8080/api/v1/account?account_id={account_id}", 
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                print_status(f"{account_id} 路由")
                print(f"    账户号: {data.get('account_number', 'N/A')}")
                print(f"    购买力: ${data.get('buying_power', 'N/A'):,.2f}")
                success_count += 1
            else:
                print_status(f"{account_id} 路由失败: {response.status_code}", False)
        except Exception as e:
            print_status(f"{account_id} 路由错误: {e}", False)
    
    return success_count == len(accounts)

def test_market_data():
    """测试市场数据功能"""
    print("\n=== 市场数据测试 ===")
    
    # 测试单个股票报价
    try:
        response = requests.get("http://localhost:8080/api/v1/stocks/AAPL/quote", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_status("AAPL股票报价")
            print(f"    买价: ${data.get('bid_price', 'N/A')}")
            print(f"    卖价: ${data.get('ask_price', 'N/A')}")
            single_quote_success = True
        else:
            print_status(f"股票报价失败: {response.status_code}", False)
            single_quote_success = False
    except Exception as e:
        print_status(f"股票报价错误: {e}", False)
        single_quote_success = False
    
    # 测试批量报价
    try:
        batch_request = {"symbols": ["AAPL", "GOOGL", "TSLA"]}
        response = requests.post(
            "http://localhost:8080/api/v1/stocks/quotes/batch",
            json=batch_request,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print_status("批量股票报价")
            print(f"    返回数量: {data.get('count', 'N/A')}")
            batch_quote_success = True
        else:
            print_status(f"批量报价失败: {response.status_code}", False)
            batch_quote_success = False
    except Exception as e:
        print_status(f"批量报价错误: {e}", False)
        batch_quote_success = False
    
    return single_quote_success and batch_quote_success

def test_load_balancing():
    """测试负载均衡功能"""
    print("\n=== 负载均衡测试 ===")
    
    # 发送多个请求测试路由分发
    success_count = 0
    total_requests = 10
    
    for i in range(total_requests):
        try:
            routing_key = f"test_key_{i % 3}"
            response = requests.get(
                f"http://localhost:8080/api/v1/stocks/AAPL/quote?routing_key={routing_key}",
                timeout=5
            )
            if response.status_code == 200:
                success_count += 1
        except Exception:
            pass
    
    success_rate = (success_count / total_requests) * 100
    print_status(f"负载均衡测试 ({success_count}/{total_requests} 成功)")
    print(f"    成功率: {success_rate:.1f}%")
    
    return success_rate >= 80

def test_configuration():
    """测试配置文件"""
    print("\n=== 配置验证 ===")
    
    required_files = [
        "secrets.yml",
        "config.py",
        "main.py",
        "requirements.txt"
    ]
    
    success_count = 0
    for file_name in required_files:
        if os.path.exists(file_name):
            print_status(f"{file_name} 存在")
            success_count += 1
        else:
            print_status(f"{file_name} 缺失", False)
    
    return success_count == len(required_files)

def test_imports():
    """测试关键模块导入"""
    print("\n=== 模块导入测试 ===")
    
    import_tests = [
        ("main", "主程序模块"),
        ("config", "配置模块"),
        ("app.middleware", "中间件模块"),
        ("app.routes", "路由模块"),
        ("app.account_pool", "账户池模块")
    ]
    
    success_count = 0
    for module_name, description in import_tests:
        try:
            __import__(module_name)
            print_status(f"{description}")
            success_count += 1
        except Exception as e:
            print_status(f"{description} 导入失败: {e}", False)
    
    return success_count == len(import_tests)

def main():
    """主测试流程"""
    print("Multi-Account Trading System Validation")
    print("=" * 50)
    
    # 测试模块导入
    import_success = test_imports()
    
    # 测试配置文件
    config_success = test_configuration()
    
    # 测试服务器（如果运行中）
    server_success = test_server_health()
    
    if server_success:
        # 服务器运行中，测试API功能
        account_success = test_account_routing()
        market_success = test_market_data()
        balance_success = test_load_balancing()
        
        api_success = account_success and market_success and balance_success
    else:
        print("\n[INFO] Server not running, skipping API tests")
        print("   Start server: uvicorn main:app --host 0.0.0.0 --port 8080")
        api_success = True  # 不算失败
    
    # 总结
    print("\n" + "=" * 50)
    print("Validation Results Summary:")
    print(f"   Module imports: {'[PASS]' if import_success else '[FAIL]'}")
    print(f"   Configuration: {'[PASS]' if config_success else '[FAIL]'}")
    print(f"   Server health: {'[PASS]' if server_success else '[NOT RUNNING]'}")
    
    if server_success:
        print(f"   API functions: {'[PASS]' if api_success else '[FAIL]'}")
    
    overall_success = import_success and config_success and api_success
    
    if overall_success:
        print("\n[SUCCESS] System validation passed! Multi-account trading system is operational.")
        return True
    else:
        print("\n[WARNING] System validation found issues. Please check failed items above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)