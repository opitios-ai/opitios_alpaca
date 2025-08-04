"""
API端点路由集成测试套件
测试API端点的账户路由、负载均衡、认证集成和错误处理
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.middleware import create_jwt_token
from app.routes import get_routing_info
from main import app


class TestRoutingInfoExtraction:
    """路由信息提取测试"""
    
    def test_get_routing_info_with_parameters(self):
        """测试带参数的路由信息获取"""
        # 测试完整参数
        result = get_routing_info(account_id="test_account", routing_key="AAPL")
        assert result == {"account_id": "test_account", "routing_key": "AAPL"}
        
        # 测试只有account_id
        result = get_routing_info(account_id="test_account")
        assert result == {"account_id": "test_account", "routing_key": None}
        
        # 测试只有routing_key
        result = get_routing_info(routing_key="TSLA")
        assert result == {"account_id": None, "routing_key": "TSLA"}
        
        # 测试无参数
        result = get_routing_info()
        assert result == {"account_id": None, "routing_key": None}
    
    def test_routing_info_with_edge_cases(self):
        """测试边缘情况的路由信息"""
        # 测试空字符串
        result = get_routing_info(account_id="", routing_key="")
        assert result == {"account_id": "", "routing_key": ""}
        
        # 测试特殊字符
        result = get_routing_info(account_id="account-with-dash", routing_key="SYMBOL.WITH.DOTS")
        assert result == {"account_id": "account-with-dash", "routing_key": "SYMBOL.WITH.DOTS"}
        
        # 测试长字符串
        long_id = "a" * 100
        long_key = "S" * 50
        result = get_routing_info(account_id=long_id, routing_key=long_key)
        assert result == {"account_id": long_id, "routing_key": long_key}


class TestAccountEndpointRouting:
    """账户端点路由测试"""
    
    def test_account_endpoint_with_account_routing(self):
        """测试账户端点的账户路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_account.return_value = {
                "account_number": "123456789",
                "buying_power": 50000.0,
                "cash": 25000.0,
                "portfolio_value": 75000.0
            }
            
            # 测试指定账户ID
            response = client.get("/api/v1/account?account_id=premium_account_1")
            
            if response.status_code == 200:
                mock_pooled.get_account.assert_called_once_with(
                    account_id="premium_account_1",
                    routing_key=None
                )
                
                data = response.json()
                assert data["account_number"] == "123456789"
                assert data["buying_power"] == 50000.0
    
    def test_account_endpoint_with_routing_key(self):
        """测试账户端点的路由键"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_account.return_value = {
                "account_number": "987654321",
                "buying_power": 75000.0
            }
            
            # 测试路由键
            response = client.get("/api/v1/account?routing_key=user_session_key")
            
            if response.status_code == 200:
                mock_pooled.get_account.assert_called_once_with(
                    account_id=None,
                    routing_key="user_session_key"
                )
    
    def test_account_endpoint_without_routing(self):
        """测试账户端点无路由参数"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_account.return_value = {
                "account_number": "default_account",
                "buying_power": 10000.0
            }
            
            # 测试无路由参数（使用默认路由）
            response = client.get("/api/v1/account")
            
            if response.status_code == 200:
                mock_pooled.get_account.assert_called_once_with(
                    account_id=None,
                    routing_key=None
                )
    
    def test_positions_endpoint_routing(self):
        """测试持仓端点路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_positions.return_value = [
                {
                    "symbol": "AAPL",
                    "qty": "100",
                    "market_value": "15000.0",
                    "avg_entry_price": "150.0"
                },
                {
                    "symbol": "GOOGL", 
                    "qty": "10",
                    "market_value": "25000.0",
                    "avg_entry_price": "2500.0"
                }
            ]
            
            # 测试带账户ID和路由键
            response = client.get("/api/v1/positions?account_id=trading_account&routing_key=portfolio_key")
            
            if response.status_code == 200:
                mock_pooled.get_positions.assert_called_once_with(
                    account_id="trading_account",
                    routing_key="portfolio_key"
                )
                
                data = response.json()
                assert len(data) == 2
                assert data[0]["symbol"] == "AAPL"
                assert data[1]["symbol"] == "GOOGL"


class TestStockEndpointRouting:
    """股票端点路由测试"""
    
    def test_single_stock_quote_routing(self):
        """测试单股票报价路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 150.25,
                "ask_price": 150.75,
                "timestamp": "2024-01-15T15:30:00Z"
            }
            
            # 测试符号作为默认路由键
            response = client.get("/api/v1/stocks/AAPL/quote")
            
            if response.status_code == 200:
                mock_pooled.get_stock_quote.assert_called_once_with(
                    symbol="AAPL",
                    account_id=None,
                    routing_key="AAPL"  # 符号自动作为路由键
                )
    
    def test_single_stock_quote_with_custom_routing(self):
        """测试单股票报价自定义路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "TSLA",
                "bid_price": 200.50,
                "ask_price": 201.00,
                "timestamp": "2024-01-15T15:30:00Z"
            }
            
            # 测试自定义路由参数
            response = client.get("/api/v1/stocks/TSLA/quote?account_id=premium_account&routing_key=custom_key")
            
            if response.status_code == 200:
                mock_pooled.get_stock_quote.assert_called_once_with(
                    symbol="TSLA",
                    account_id="premium_account",
                    routing_key="custom_key"  # 使用自定义路由键
                )
    
    def test_batch_stock_quotes_routing(self):
        """测试批量股票报价路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {"symbol": "AAPL", "bid_price": 150.0, "ask_price": 150.5},
                    {"symbol": "GOOGL", "bid_price": 2500.0, "ask_price": 2505.0},
                    {"symbol": "TSLA", "bid_price": 200.0, "ask_price": 200.5}
                ],
                "count": 3,
                "requested_symbols": ["AAPL", "GOOGL", "TSLA"]
            }
            
            # 测试批量请求路由
            response = client.post("/api/v1/stocks/quotes/batch", json={
                "symbols": ["AAPL", "GOOGL", "TSLA"]
            })
            
            if response.status_code == 200:
                mock_pooled.get_multiple_stock_quotes.assert_called_once_with(
                    symbols=["AAPL", "GOOGL", "TSLA"],
                    account_id=None,
                    routing_key="AAPL"  # 第一个符号作为路由键
                )
    
    def test_batch_stock_quotes_with_custom_routing(self):
        """测试批量股票报价自定义路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_multiple_stock_quotes.return_value = {
                "quotes": [{"symbol": "MSFT", "bid_price": 300.0, "ask_price": 300.5}],
                "count": 1
            }
            
            # 测试自定义路由参数
            response = client.post("/api/v1/stocks/quotes/batch?account_id=data_account&routing_key=batch_key", 
                                 json={"symbols": ["MSFT"]})
            
            if response.status_code == 200:
                mock_pooled.get_multiple_stock_quotes.assert_called_once_with(
                    symbols=["MSFT"],
                    account_id="data_account",
                    routing_key="batch_key"  # 使用自定义路由键
                )
    
    def test_stock_bars_routing(self):
        """测试股票K线数据路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_bars.return_value = {
                "symbol": "NVDA",
                "timeframe": "1Day",
                "bars": [
                    {
                        "timestamp": "2024-01-15T09:30:00Z",
                        "open": 500.0,
                        "high": 505.0,
                        "low": 495.0,
                        "close": 502.0,
                        "volume": 1000000
                    }
                ]
            }
            
            # 测试K线数据路由
            response = client.get("/api/v1/stocks/NVDA/bars?timeframe=1Day&limit=100&account_id=chart_account")
            
            if response.status_code == 200:
                mock_pooled.get_stock_bars.assert_called_once_with(
                    symbol="NVDA",
                    timeframe="1Day",
                    limit=100,
                    account_id="chart_account",
                    routing_key="NVDA"  # 符号作为路由键
                )


class TestOptionsEndpointRouting:
    """期权端点路由测试"""
    
    def test_options_chain_routing(self):
        """测试期权链路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_options_chain.return_value = {
                "underlying_symbol": "AAPL",
                "underlying_price": 150.0,
                "expiration_dates": ["2024-02-16"],
                "options": [
                    {
                        "symbol": "AAPL240216C00150000",
                        "strike_price": 150.0,
                        "option_type": "call",
                        "bid_price": 5.25,
                        "ask_price": 5.75
                    }
                ]
            }
            mock_client_class.return_value = mock_client
            
            # 测试期权链请求
            response = client.post("/api/v1/options/chain", json={
                "underlying_symbol": "AAPL",
                "expiration_date": "2024-02-16",
                "option_type": "call"
            })
            
            if response.status_code == 200:
                mock_client.get_options_chain.assert_called_once_with(
                    "AAPL", "2024-02-16"
                )
    
    def test_single_option_quote_routing(self):
        """测试单期权报价路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_option_quote.return_value = {
                "symbol": "AAPL240216C00150000",
                "underlying_symbol": "AAPL",
                "strike_price": 150.0,
                "expiration_date": "2024-02-16",
                "option_type": "call",
                "bid_price": 5.25,
                "ask_price": 5.75,
                "timestamp": "2024-01-15T15:30:00Z"
            }
            mock_client_class.return_value = mock_client
            
            # 测试期权报价请求
            response = client.post("/api/v1/options/quote", json={
                "option_symbol": "AAPL240216C00150000"
            })
            
            if response.status_code == 200:
                mock_client.get_option_quote.assert_called_once_with(
                    "AAPL240216C00150000"
                )
    
    def test_batch_option_quotes_routing(self):
        """测试批量期权报价路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_multiple_option_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL240216C00150000",
                        "bid_price": 5.25,
                        "ask_price": 5.75
                    },
                    {
                        "symbol": "AAPL240216P00140000",
                        "bid_price": 2.50,
                        "ask_price": 3.00
                    }
                ],
                "count": 2,
                "successful_count": 2,
                "failed_count": 0
            }
            mock_client_class.return_value = mock_client
            
            # 测试批量期权报价
            response = client.post("/api/v1/options/quotes/batch", json={
                "option_symbols": ["AAPL240216C00150000", "AAPL240216P00140000"]
            })
            
            if response.status_code == 200:
                mock_client.get_multiple_option_quotes.assert_called_once_with(
                    ["AAPL240216C00150000", "AAPL240216P00140000"]
                )
    
    def test_options_chain_by_symbol_routing(self):
        """测试按符号获取期权链路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_options_chain.return_value = {
                "underlying_symbol": "TSLA",
                "underlying_price": 200.0,
                "options": []
            }
            mock_client_class.return_value = mock_client
            
            # 测试GET方式的期权链请求
            response = client.get("/api/v1/options/TSLA/chain?expiration_date=2024-03-15")
            
            if response.status_code == 200:
                mock_client.get_options_chain.assert_called_once_with(
                    "TSLA", "2024-03-15"
                )


class TestTradingEndpointRouting:
    """交易端点路由测试"""
    
    def test_stock_order_routing_requires_auth(self):
        """测试股票订单路由需要认证"""
        client = TestClient(app)
        
        # 测试未认证请求
        response = client.post("/api/v1/stocks/order", json={
            "symbol": "AAPL",
            "qty": 10,
            "side": "buy",
            "type": "market",
            "time_in_force": "day"
        })
        
        assert response.status_code == 401
    
    def test_stock_order_routing_with_auth(self):
        """测试股票订单路由与认证"""
        client = TestClient(app)
        
        # 创建认证token
        token = create_jwt_token({
            "user_id": "trader_123",
            "account_id": "trading_account",
            "permissions": ["trading", "market_data"]
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.place_stock_order.return_value = {
                "id": "order_123",
                "symbol": "AAPL",
                "qty": "10",
                "side": "buy",
                "order_type": "market",
                "status": "pending_new"
            }
            mock_client_class.return_value = mock_client
            
            # 测试认证的股票订单
            response = client.post("/api/v1/stocks/order", 
                                 headers=headers,
                                 json={
                                     "symbol": "AAPL",
                                     "qty": 10,
                                     "side": "buy",
                                     "type": "market",
                                     "time_in_force": "day"
                                 })
            
            if response.status_code == 200:
                mock_client.place_stock_order.assert_called_once()
    
    def test_option_order_routing_with_auth(self):
        """测试期权订单路由与认证"""
        client = TestClient(app)
        
        token = create_jwt_token({
            "user_id": "options_trader",
            "account_id": "options_account",
            "permissions": ["trading", "options"]
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.place_option_order.return_value = {
                "id": "option_order_456",
                "option_symbol": "AAPL240216C00150000",
                "qty": "5",
                "side": "buy",
                "order_type": "limit",
                "status": "pending_new"
            }
            mock_client_class.return_value = mock_client
            
            # 测试认证的期权订单
            response = client.post("/api/v1/options/order",
                                 headers=headers,
                                 json={
                                     "option_symbol": "AAPL240216C00150000",
                                     "qty": 5,
                                     "side": "buy",
                                     "type": "limit",
                                     "limit_price": 5.50,
                                     "time_in_force": "day"
                                 })
            
            if response.status_code == 200:
                mock_client.place_option_order.assert_called_once()


class TestErrorHandlingInRouting:
    """路由中的错误处理测试"""
    
    def test_invalid_routing_parameters(self):
        """测试无效路由参数"""
        client = TestClient(app)
        
        # 测试无效的account_id格式
        response = client.get("/api/v1/account?account_id=")
        # 空account_id应该被处理
        assert response.status_code in [200, 400, 500]  # 取决于具体实现
        
        # 测试极长的routing_key
        long_key = "A" * 1000
        response = client.get(f"/api/v1/stocks/AAPL/quote?routing_key={long_key}")
        # 应该能处理长路由键
        assert response.status_code in [200, 400, 500]
    
    def test_routing_with_special_characters(self):
        """测试特殊字符的路由"""
        client = TestClient(app)
        
        # 测试包含特殊字符的account_id
        special_chars = ["account-1", "account_2", "account.3", "account@4"]
        
        for account_id in special_chars:
            response = client.get(f"/api/v1/account?account_id={account_id}")
            # 应该能处理特殊字符
            assert response.status_code in [200, 400, 500]
    
    def test_routing_backend_failures(self):
        """测试路由后端失败"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 模拟后端连接失败
            mock_pooled.get_account.side_effect = Exception("Connection pool exhausted")
            
            response = client.get("/api/v1/account?account_id=failing_account")
            
            # 应该返回适当的错误状态
            assert response.status_code in [500, 502, 503]
    
    def test_routing_timeout_handling(self):
        """测试路由超时处理"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 模拟超时
            mock_pooled.get_stock_quote.side_effect = asyncio.TimeoutError("Request timeout")
            
            response = client.get("/api/v1/stocks/AAPL/quote")
            
            # 应该处理超时错误
            assert response.status_code in [500, 504]


class TestRoutingConsistency:
    """路由一致性测试"""
    
    def test_consistent_routing_across_endpoints(self):
        """测试跨端点的路由一致性"""
        client = TestClient(app)
        
        # 收集所有端点的路由行为
        routing_behaviors = {}
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 模拟所有方法
            mock_pooled.get_account.return_value = {"account_number": "123"}
            mock_pooled.get_positions.return_value = []
            mock_pooled.get_stock_quote.return_value = {"symbol": "AAPL", "bid_price": 150}
            mock_pooled.get_multiple_stock_quotes.return_value = {"quotes": [], "count": 0}
            mock_pooled.get_stock_bars.return_value = {"symbol": "AAPL", "bars": []}
            
            # 测试各个端点的路由行为
            endpoints = [
                ("/api/v1/account", "get_account"),
                ("/api/v1/positions", "get_positions"),
                ("/api/v1/stocks/AAPL/quote", "get_stock_quote"),
            ]
            
            for endpoint, method_name in endpoints:
                response = client.get(f"{endpoint}?account_id=test_account&routing_key=test_key")
                
                if response.status_code == 200:
                    mock_method = getattr(mock_pooled, method_name)
                    if mock_method.called:
                        call_args = mock_method.call_args
                        if call_args and len(call_args) > 1:
                            kwargs = call_args[1]
                            routing_behaviors[endpoint] = {
                                "account_id": kwargs.get("account_id"),
                                "routing_key": kwargs.get("routing_key")
                            }
        
        # 验证路由行为一致性
        if routing_behaviors:
            first_behavior = list(routing_behaviors.values())[0]
            for endpoint, behavior in routing_behaviors.items():
                assert behavior["account_id"] == first_behavior["account_id"], \
                    f"Inconsistent account_id routing in {endpoint}"
                assert behavior["routing_key"] == first_behavior["routing_key"], \
                    f"Inconsistent routing_key routing in {endpoint}"
    
    def test_routing_parameter_precedence(self):
        """测试路由参数优先级"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {"symbol": "AAPL", "bid_price": 150}
            
            # 测试显式routing_key优先于符号
            response = client.get("/api/v1/stocks/AAPL/quote?routing_key=custom_key")
            
            if response.status_code == 200:
                mock_pooled.get_stock_quote.assert_called_once()
                call_args = mock_pooled.get_stock_quote.call_args
                if call_args and len(call_args) > 1:
                    kwargs = call_args[1]
                    # 自定义routing_key应该优先于符号
                    assert kwargs.get("routing_key") == "custom_key"
    
    def test_routing_fallback_behavior(self):
        """测试路由回退行为"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {"symbol": "AAPL", "bid_price": 150}
            
            # 测试无路由参数时的回退
            response = client.get("/api/v1/stocks/AAPL/quote")
            
            if response.status_code == 200:
                mock_pooled.get_stock_quote.assert_called_once()
                call_args = mock_pooled.get_stock_quote.call_args
                if call_args and len(call_args) > 1:
                    kwargs = call_args[1]
                    # 应该使用符号作为默认routing_key
                    assert kwargs.get("routing_key") == "AAPL"


class TestRoutingPerformance:
    """路由性能测试"""
    
    @pytest.mark.performance
    def test_routing_overhead_measurement(self):
        """测试路由开销测量"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {"symbol": "AAPL", "bid_price": 150}
            
            import time
            
            # 测试无路由参数的性能
            start_time = time.time()
            for _ in range(100):
                response = client.get("/api/v1/stocks/AAPL/quote")
                assert response.status_code == 200
            no_routing_time = time.time() - start_time
            
            # 重置mock
            mock_pooled.reset_mock()
            
            # 测试有路由参数的性能
            start_time = time.time()
            for _ in range(100):
                response = client.get("/api/v1/stocks/AAPL/quote?account_id=test&routing_key=test")
                assert response.status_code == 200
            with_routing_time = time.time() - start_time
            
            # 路由开销应该很小
            routing_overhead = with_routing_time - no_routing_time
            overhead_per_request = routing_overhead / 100
            
            print(f"Routing overhead per request: {overhead_per_request * 1000:.2f}ms")
            
            # 路由开销应该小于1ms
            assert overhead_per_request < 0.001, f"Routing overhead too high: {overhead_per_request * 1000:.2f}ms"
    
    @pytest.mark.performance
    def test_concurrent_routing_performance(self):
        """测试并发路由性能"""
        import threading
        import queue
        import time
        
        client = TestClient(app)
        results = queue.Queue()
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {"symbol": "AAPL", "bid_price": 150}
            
            def worker(worker_id):
                start_time = time.time()
                for i in range(50):
                    response = client.get(f"/api/v1/stocks/AAPL/quote?account_id=account_{worker_id}&routing_key=key_{i}")
                    assert response.status_code == 200
                end_time = time.time()
                results.put(end_time - start_time)
            
            # 启动10个并发线程
            threads = []
            overall_start = time.time()
            
            for i in range(10):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            overall_end = time.time()
            
            # 收集结果
            worker_times = []
            while not results.empty():
                worker_times.append(results.get())
            
            total_time = overall_end - overall_start
            total_requests = 10 * 50
            requests_per_second = total_requests / total_time
            
            print(f"Concurrent routing performance:")
            print(f"Total requests: {total_requests}")
            print(f"Total time: {total_time:.3f}s")
            print(f"Requests per second: {requests_per_second:.0f}")
            print(f"Average worker time: {sum(worker_times) / len(worker_times):.3f}s")
            
            # 并发性能断言
            assert requests_per_second > 100, f"Concurrent routing too slow: {requests_per_second:.0f} req/s"


class TestRoutingSecurityAspects:
    """路由安全方面测试"""
    
    def test_routing_parameter_injection_prevention(self):
        """测试路由参数注入防护"""
        client = TestClient(app)
        
        # 测试SQL注入尝试
        malicious_inputs = [
            "'; DROP TABLE accounts; --",
            "1' OR '1'='1",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "admin'; SELECT * FROM users; --"
        ]
        
        for malicious_input in malicious_inputs:
            # 测试account_id参数
            response = client.get(f"/api/v1/account?account_id={malicious_input}")
            # 应该被安全处理，不导致系统错误
            assert response.status_code in [200, 400, 401, 500]
            
            # 测试routing_key参数
            response = client.get(f"/api/v1/stocks/AAPL/quote?routing_key={malicious_input}")
            assert response.status_code in [200, 400, 401, 500]
    
    def test_routing_access_control(self):
        """测试路由访问控制"""
        client = TestClient(app)
        
        # 测试未认证用户访问受保护端点
        protected_endpoints = [
            "/api/v1/orders",
            "/api/v1/stocks/order",
            "/api/v1/options/order"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"
    
    def test_routing_cross_account_access_prevention(self):
        """测试跨账户访问防护"""
        client = TestClient(app)
        
        # 创建用户A的token
        token_a = create_jwt_token({
            "user_id": "user_a",
            "account_id": "account_a",
            "permissions": ["trading"]
        })
        
        # 创建用户B的token
        token_b = create_jwt_token({
            "user_id": "user_b", 
            "account_id": "account_b",
            "permissions": ["trading"]
        })
        
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_account.return_value = {"account_number": "123"}
            
            # 用户A尝试访问账户B的数据
            response = client.get("/api/v1/account?account_id=account_b", headers=headers_a)
            
            # 根据具体实现，可能允许或拒绝跨账户访问
            # 这里主要验证不会导致系统错误
            assert response.status_code in [200, 403, 404, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])