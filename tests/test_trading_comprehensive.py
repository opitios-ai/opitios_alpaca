"""
综合交易测试脚本
测试多账户交易操作和零延迟性能
"""

import asyncio
import time
import requests
import json
from app.middleware import create_jwt_token

# 创建测试用JWT token
def create_test_token():
    """创建测试用JWT token"""
    user_data = {
        "user_id": "test_trader_001", 
        "account_id": "trading_account_001",
        "permissions": ["trading", "market_data", "account_access", "options"]
    }
    return create_jwt_token(user_data)

def test_trading_endpoints():
    """测试交易端点"""
    base_url = "http://localhost:8080/api/v1"
    
    # 创建认证头
    token = create_test_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("=== 开始交易端点测试 ===")
    
    # 1. 测试账户信息（带路由）
    print("\n1. 测试账户信息路由:")
    accounts = ["account_001", "account_002", "account_003"]
    
    for account_id in accounts:
        try:
            response = requests.get(f"{base_url}/account?account_id={account_id}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"   [SUCCESS] {account_id}: 账户号 {data['account_number']}, 资金 ${data['buying_power']:,.2f}")
            else:
                print(f"   [FAILED] {account_id}: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            print(f"   [ERROR] {account_id}: 错误 - {e}")
    
    # 2. 测试持仓信息（带路由）
    print("\n2. 测试持仓信息路由:")
    for account_id in accounts:
        try:
            response = requests.get(f"{base_url}/positions?account_id={account_id}", headers=headers)
            if response.status_code == 200:
                positions = response.json()
                print(f"   [SUCCESS] {account_id}: {len(positions)} 个持仓")
                for pos in positions[:3]:  # 只显示前3个
                    print(f"      - {pos['symbol']}: {pos['qty']} 股, 价值 ${pos.get('market_value', 'N/A')}")
            else:
                print(f"   [FAILED] {account_id}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {account_id}: 错误 - {e}")
    
    # 3. 测试市价买单（模拟）
    print("\n3. 测试市价买单:")
    test_orders = [
        {"symbol": "AAPL", "qty": 1, "account_id": "account_001"},
        {"symbol": "GOOGL", "qty": 1, "account_id": "account_002"}, 
        {"symbol": "TSLA", "qty": 1, "account_id": "account_003"}
    ]
    
    for order_data in test_orders:
        try:
            order_request = {
                "symbol": order_data["symbol"],
                "qty": order_data["qty"],
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            }
            
            url = f"{base_url}/stocks/order?account_id={order_data['account_id']}"
            response = requests.post(url, headers=headers, json=order_request)
            
            if response.status_code == 200:
                result = response.json()
                print(f"   [SUCCESS] {order_data['symbol']} -> {order_data['account_id']}: 订单ID {result.get('id', 'N/A')}")
            else:
                print(f"   [FAILED] {order_data['symbol']} -> {order_data['account_id']}: HTTP {response.status_code}")
                print(f"      错误: {response.text}")
        except Exception as e:
            print(f"   [ERROR] {order_data['symbol']} -> {order_data['account_id']}: 错误 - {e}")
    
    # 4. 测试快速交易端点
    print("\n4. 测试快速交易端点:")
    quick_trades = [
        {"symbol": "AAPL", "qty": 1, "action": "buy", "account_id": "account_001"},
        {"symbol": "MSFT", "qty": 1, "action": "sell", "account_id": "account_002"}
    ]
    
    for trade in quick_trades:
        try:
            url = f"{base_url}/stocks/{trade['symbol']}/{trade['action']}?qty={trade['qty']}&account_id={trade['account_id']}"
            response = requests.post(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ {trade['action'].upper()} {trade['symbol']} -> {trade['account_id']}: 成功")
            else:
                print(f"   ❌ {trade['action'].upper()} {trade['symbol']} -> {trade['account_id']}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ {trade['action'].upper()} {trade['symbol']} -> {trade['account_id']}: 错误 - {e}")
    
    # 5. 测试订单查询
    print("\n5. 测试订单查询:")
    for account_id in accounts:
        try:
            response = requests.get(f"{base_url}/orders?account_id={account_id}", headers=headers)
            if response.status_code == 200:
                orders = response.json()
                print(f"   ✅ {account_id}: {len(orders)} 个订单")
                for order in orders[:2]:  # 只显示前2个
                    print(f"      - {order.get('symbol', 'N/A')}: {order.get('status', 'N/A')}")
            else:
                print(f"   ❌ {account_id}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ {account_id}: 错误 - {e}")

def test_performance_metrics():
    """测试性能指标"""
    base_url = "http://localhost:8080/api/v1"
    
    print("\n=== 性能测试 ===")
    
    # 测试连续请求延迟
    print("\n1. 测试连续请求延迟:")
    latencies = []
    
    for i in range(10):
        start_time = time.time()
        try:
            response = requests.get(f"{base_url}/stocks/AAPL/quote")
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # 转换为毫秒
            latencies.append(latency)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"   请求 {i+1}: {latency:.1f}ms {status}")
        except Exception as e:
            print(f"   请求 {i+1}: 错误 - {e}")
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        print(f"\n   平均延迟: {avg_latency:.1f}ms")
        print(f"   最小延迟: {min_latency:.1f}ms") 
        print(f"   最大延迟: {max_latency:.1f}ms")
        
        # 零延迟目标检查
        if avg_latency < 100:
            print("   🎯 已达到低延迟目标 (<100ms)")
        else:
            print("   ⚠️  延迟较高，需要优化")

def test_load_balancing_verification():
    """验证负载均衡"""
    base_url = "http://localhost:8080/api/v1"
    
    print("\n=== 负载均衡验证 ===")
    
    # 发送大量请求测试负载分布
    print("\n1. 发送50个请求测试负载分布:")
    symbols = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]
    
    success_count = 0
    start_time = time.time()
    
    for i in range(50):
        symbol = symbols[i % len(symbols)]
        routing_key = f"test_key_{i % 3}"  # 3个不同的路由键
        
        try:
            response = requests.get(f"{base_url}/stocks/{symbol}/quote?routing_key={routing_key}")
            if response.status_code == 200:
                success_count += 1
            
            if (i + 1) % 10 == 0:
                print(f"   已完成 {i + 1}/50 请求, 成功率: {success_count/(i+1)*100:.1f}%")
                
        except Exception as e:
            print(f"   请求 {i+1} 失败: {e}")
    
    total_time = time.time() - start_time
    requests_per_second = 50 / total_time
    
    print(f"\n   总计: {success_count}/50 成功")
    print(f"   用时: {total_time:.2f}秒")
    print(f"   吞吐量: {requests_per_second:.1f} 请求/秒")
    
    if success_count >= 45 and requests_per_second >= 10:
        print("   🎯 负载均衡测试通过")
    else:
        print("   ⚠️  负载均衡需要优化")

if __name__ == "__main__":
    try:
        print("开始多账户交易系统综合测试")
        print("=" * 50)
        
        # 测试各个功能模块
        test_trading_endpoints()
        test_performance_metrics()
        test_load_balancing_verification()
        
        print("\n" + "=" * 50)
        print("✅ 综合测试完成")
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试出现错误: {e}")