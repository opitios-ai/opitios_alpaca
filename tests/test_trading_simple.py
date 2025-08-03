"""
简单的交易测试脚本 - 无Unicode字符
"""

import time
import requests
import json
from app.middleware import create_jwt_token

def create_test_token():
    user_data = {
        "user_id": "test_trader_001", 
        "account_id": "trading_account_001",
        "permissions": ["trading", "market_data", "account_access", "options"]
    }
    return create_jwt_token(user_data)

def test_trading():
    base_url = "http://localhost:8080/api/v1"
    token = create_test_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("=== Trading Endpoint Tests ===")
    
    # Test account routing
    print("\n1. Account Info Routing:")
    accounts = ["account_001", "account_002", "account_003"]
    
    for account_id in accounts:
        try:
            response = requests.get(f"{base_url}/account?account_id={account_id}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] {account_id}: Account {data['account_number']}, Buying Power ${data['buying_power']:,.2f}")
            else:
                print(f"   [FAIL] {account_id}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {account_id}: {e}")
    
    # Test positions
    print("\n2. Positions Routing:")
    for account_id in accounts:
        try:
            response = requests.get(f"{base_url}/positions?account_id={account_id}", headers=headers)
            if response.status_code == 200:
                positions = response.json()
                print(f"   [OK] {account_id}: {len(positions)} positions")
            else:
                print(f"   [FAIL] {account_id}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {account_id}: {e}")
    
    # Test stock orders
    print("\n3. Stock Order Tests:")
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
                print(f"   [OK] {order_data['symbol']} -> {order_data['account_id']}: Order ID {result.get('id', 'N/A')}")
            else:
                print(f"   [FAIL] {order_data['symbol']} -> {order_data['account_id']}: HTTP {response.status_code}")
                if response.text:
                    print(f"      Error: {response.text}")
        except Exception as e:
            print(f"   [ERROR] {order_data['symbol']} -> {order_data['account_id']}: {e}")
    
    # Test quick trading
    print("\n4. Quick Trading Tests:")
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
                print(f"   [OK] {trade['action'].upper()} {trade['symbol']} -> {trade['account_id']}: Success")
            else:
                print(f"   [FAIL] {trade['action'].upper()} {trade['symbol']} -> {trade['account_id']}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   [ERROR] {trade['action'].upper()} {trade['symbol']} -> {trade['account_id']}: {e}")

def test_performance():
    base_url = "http://localhost:8080/api/v1"
    
    print("\n=== Performance Tests ===")
    
    # Test latency
    print("\n1. Request Latency Test:")
    latencies = []
    
    for i in range(10):
        start_time = time.time()
        try:
            response = requests.get(f"{base_url}/stocks/AAPL/quote")
            end_time = time.time()
            latency = (end_time - start_time) * 1000
            latencies.append(latency)
            status = "[OK]" if response.status_code == 200 else "[FAIL]"
            print(f"   Request {i+1}: {latency:.1f}ms {status}")
        except Exception as e:
            print(f"   Request {i+1}: Error - {e}")
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        print(f"\n   Average Latency: {avg_latency:.1f}ms")
        print(f"   Min Latency: {min_latency:.1f}ms") 
        print(f"   Max Latency: {max_latency:.1f}ms")
        
        if avg_latency < 100:
            print("   [TARGET MET] Low latency achieved (<100ms)")
        else:
            print("   [WARNING] High latency detected")

def test_load_balancing():
    base_url = "http://localhost:8080/api/v1"
    
    print("\n=== Load Balancing Tests ===")
    
    print("\n1. Load Distribution Test (50 requests):")
    symbols = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]
    
    success_count = 0
    start_time = time.time()
    
    for i in range(50):
        symbol = symbols[i % len(symbols)]
        routing_key = f"test_key_{i % 3}"
        
        try:
            response = requests.get(f"{base_url}/stocks/{symbol}/quote?routing_key={routing_key}")
            if response.status_code == 200:
                success_count += 1
            
            if (i + 1) % 10 == 0:
                print(f"   Completed {i + 1}/50 requests, Success rate: {success_count/(i+1)*100:.1f}%")
                
        except Exception as e:
            print(f"   Request {i+1} failed: {e}")
    
    total_time = time.time() - start_time
    requests_per_second = 50 / total_time
    
    print(f"\n   Total: {success_count}/50 successful")
    print(f"   Duration: {total_time:.2f}s")
    print(f"   Throughput: {requests_per_second:.1f} req/s")
    
    if success_count >= 45 and requests_per_second >= 10:
        print("   [PASS] Load balancing test passed")
    else:
        print("   [WARNING] Load balancing needs optimization")

if __name__ == "__main__":
    try:
        print("Multi-Account Trading System Comprehensive Test")
        print("=" * 50)
        
        test_trading()
        test_performance()
        test_load_balancing()
        
        print("\n" + "=" * 50)
        print("[COMPLETE] All tests finished")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")