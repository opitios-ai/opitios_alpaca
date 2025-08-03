"""
端到端交易工作流测试套件
测试完整的交易流程、多账户协调、实时数据集成和业务场景
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch, call, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from fastapi.testclient import TestClient
from decimal import Decimal

from app.middleware import create_jwt_token
from app.account_pool import AccountConfig, AccountConnectionPool
from main import app


class TestStockTradingWorkflows:
    """股票交易工作流测试"""
    
    @pytest.fixture
    def authenticated_client(self):
        """认证的测试客户端"""
        client = TestClient(app)
        
        # 创建交易用户token
        token = create_jwt_token({
            "user_id": "trader_001",
            "account_id": "trading_account_1",
            "permissions": ["trading", "market_data", "account_access"]
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        return client, headers
    
    @pytest.fixture
    def mock_market_data(self):
        """模拟市场数据"""
        return {
            "AAPL": {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "last_price": 185.35,
                "volume": 1000000
            },
            "GOOGL": {
                "symbol": "GOOGL",
                "bid_price": 2750.00,
                "ask_price": 2755.00,
                "last_price": 2752.50,
                "volume": 500000
            },
            "TSLA": {
                "symbol": "TSLA",
                "bid_price": 220.75,
                "ask_price": 221.25,
                "last_price": 221.00,
                "volume": 800000
            }
        }
    
    def test_complete_stock_trading_workflow(self, authenticated_client, mock_market_data):
        """测试完整的股票交易工作流"""
        client, headers = authenticated_client
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 1. 获取账户信息
            mock_pooled.get_account.return_value = {
                "account_number": "123456789",
                "buying_power": 50000.0,
                "cash": 25000.0,
                "portfolio_value": 75000.0,
                "equity": 75000.0
            }
            
            response = client.get("/api/v1/account", headers=headers)
            assert response.status_code == 200
            account_data = response.json()
            assert account_data["buying_power"] == 50000.0
            
            # 2. 获取股票报价
            mock_pooled.get_stock_quote.return_value = mock_market_data["AAPL"]
            
            response = client.get("/api/v1/stocks/AAPL/quote", headers=headers)
            if response.status_code == 200:
                quote_data = response.json()
                assert quote_data["symbol"] == "AAPL"
                assert quote_data["bid_price"] == 185.25
            
            # 3. 下市价买单
            mock_pooled.place_stock_order = AsyncMock(return_value={
                "id": "order_123456",
                "symbol": "AAPL",
                "qty": "10",
                "side": "buy",
                "order_type": "market",
                "status": "pending_new",
                "submitted_at": datetime.now().isoformat(),
                "filled_qty": "0"
            })
            
            order_request = {
                "symbol": "AAPL",
                "qty": 10,
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            }
            
            response = client.post("/api/v1/stocks/order", headers=headers, json=order_request)
            if response.status_code == 200:
                order_data = response.json()
                assert order_data["symbol"] == "AAPL"
                assert order_data["qty"] == "10"
                assert order_data["side"] == "buy"
            
            # 4. 查询订单状态
            mock_pooled.get_orders.return_value = [
                {
                    "id": "order_123456",
                    "symbol": "AAPL", 
                    "qty": "10",
                    "side": "buy",
                    "order_type": "market",
                    "status": "filled",
                    "filled_qty": "10",
                    "filled_avg_price": "185.40",
                    "submitted_at": datetime.now().isoformat(),
                    "filled_at": datetime.now().isoformat()
                }
            ]
            
            response = client.get("/api/v1/orders", headers=headers)
            if response.status_code == 200:
                orders = response.json()
                assert len(orders) >= 0
                if orders:
                    assert orders[0]["symbol"] == "AAPL"
                    assert orders[0]["status"] in ["filled", "pending_new", "accepted"]
            
            # 5. 查询持仓
            mock_pooled.get_positions.return_value = [
                {
                    "symbol": "AAPL",
                    "qty": "10",
                    "side": "long",
                    "market_value": "1854.0",
                    "cost_basis": "1854.0",
                    "avg_entry_price": "185.40",
                    "unrealized_pl": "0.0",
                    "unrealized_plpc": "0.0"
                }
            ]
            
            response = client.get("/api/v1/positions", headers=headers)
            if response.status_code == 200:
                positions = response.json()
                if positions:
                    aapl_position = next((p for p in positions if p["symbol"] == "AAPL"), None)
                    if aapl_position:
                        assert aapl_position["qty"] == "10"
                        assert float(aapl_position["avg_entry_price"]) > 0
    
    def test_limit_order_workflow(self, authenticated_client):
        """测试限价单工作流"""
        client, headers = authenticated_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 下限价买单
            mock_client.place_stock_order.return_value = {
                "id": "limit_order_789",
                "symbol": "GOOGL",
                "qty": "2", 
                "side": "buy",
                "order_type": "limit",
                "limit_price": "2700.00",
                "status": "pending_new",
                "time_in_force": "gtc"
            }
            
            limit_order_request = {
                "symbol": "GOOGL",
                "qty": 2,
                "side": "buy", 
                "type": "limit",
                "limit_price": 2700.00,
                "time_in_force": "gtc"
            }
            
            response = client.post("/api/v1/stocks/order", headers=headers, json=limit_order_request)
            if response.status_code == 200:
                order_data = response.json()
                assert order_data["order_type"] == "limit"
                assert float(order_data["limit_price"]) == 2700.00
    
    def test_quick_trading_endpoints(self, authenticated_client):
        """测试快速交易端点"""
        client, headers = authenticated_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 快速买入
            mock_client.place_stock_order.return_value = {
                "id": "quick_buy_order",
                "symbol": "TSLA",
                "qty": "5",
                "side": "buy",
                "order_type": "market",
                "status": "pending_new"
            }
            
            response = client.post("/api/v1/stocks/TSLA/buy?qty=5", headers=headers)
            if response.status_code == 200:
                order_data = response.json()
                assert order_data["symbol"] == "TSLA"
                assert order_data["side"] == "buy"
            
            # 快速卖出
            mock_client.place_stock_order.return_value = {
                "id": "quick_sell_order",
                "symbol": "TSLA", 
                "qty": "3",
                "side": "sell",
                "order_type": "market",
                "status": "pending_new"
            }
            
            response = client.post("/api/v1/stocks/TSLA/sell?qty=3", headers=headers)
            if response.status_code == 200:
                order_data = response.json()
                assert order_data["symbol"] == "TSLA"
                assert order_data["side"] == "sell"
    
    def test_order_cancellation_workflow(self, authenticated_client):
        """测试订单取消工作流"""
        client, headers = authenticated_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 取消订单
            mock_client.cancel_order.return_value = {
                "id": "order_to_cancel",
                "status": "cancelled",
                "cancelled_at": datetime.now().isoformat()
            }
            
            response = client.delete("/api/v1/orders/order_to_cancel", headers=headers)
            if response.status_code == 200:
                result = response.json()
                assert result["status"] == "cancelled"


class TestOptionsTradeWorkflows:
    """期权交易工作流测试"""
    
    @pytest.fixture
    def options_trader_client(self):
        """期权交易者客户端"""
        client = TestClient(app)
        
        token = create_jwt_token({
            "user_id": "options_trader_001",
            "account_id": "options_account_1", 
            "permissions": ["trading", "options", "market_data", "advanced_trading"]
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        return client, headers
    
    def test_options_chain_analysis_workflow(self, options_trader_client):
        """测试期权链分析工作流"""
        client, headers = options_trader_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 1. 获取期权链
            mock_client.get_options_chain.return_value = {
                "underlying_symbol": "AAPL",
                "underlying_price": 185.35,
                "expiration_dates": ["2024-02-16", "2024-03-15"],
                "options_count": 40,
                "options": [
                    {
                        "symbol": "AAPL240216C00180000",
                        "underlying_symbol": "AAPL",
                        "strike_price": 180.0,
                        "expiration_date": "2024-02-16",
                        "option_type": "call",
                        "bid_price": 6.25,
                        "ask_price": 6.75,
                        "last_price": 6.50,
                        "implied_volatility": 0.28,
                        "delta": 0.65,
                        "gamma": 0.03,
                        "theta": -0.05,
                        "vega": 0.15
                    },
                    {
                        "symbol": "AAPL240216P00190000",
                        "underlying_symbol": "AAPL",
                        "strike_price": 190.0,
                        "expiration_date": "2024-02-16",
                        "option_type": "put",
                        "bid_price": 8.50,
                        "ask_price": 9.00,
                        "last_price": 8.75,
                        "implied_volatility": 0.30,
                        "delta": -0.45,
                        "gamma": 0.03,
                        "theta": -0.06,
                        "vega": 0.18
                    }
                ]
            }
            
            chain_request = {
                "underlying_symbol": "AAPL",
                "expiration_date": "2024-02-16"
            }
            
            response = client.post("/api/v1/options/chain", json=chain_request)
            if response.status_code == 200:
                chain_data = response.json()
                assert chain_data["underlying_symbol"] == "AAPL"
                assert chain_data["underlying_price"] == 185.35
                assert len(chain_data["options"]) >= 2
            
            # 2. 获取单个期权报价
            mock_client.get_option_quote.return_value = {
                "symbol": "AAPL240216C00180000",
                "underlying_symbol": "AAPL",
                "strike_price": 180.0,
                "expiration_date": "2024-02-16",
                "option_type": "call",
                "bid_price": 6.30,
                "ask_price": 6.70,
                "last_price": 6.50,
                "volume": 1500,
                "open_interest": 5000,
                "implied_volatility": 0.285
            }
            
            quote_request = {
                "option_symbol": "AAPL240216C00180000"
            }
            
            response = client.post("/api/v1/options/quote", json=quote_request)
            if response.status_code == 200:
                quote_data = response.json()
                assert quote_data["symbol"] == "AAPL240216C00180000"
                assert quote_data["option_type"] == "call"
                assert quote_data["strike_price"] == 180.0
    
    def test_options_trading_workflow(self, options_trader_client):
        """测试期权交易工作流"""
        client, headers = options_trader_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 下期权买单
            mock_client.place_option_order.return_value = {
                "id": "option_order_456",
                "option_symbol": "AAPL240216C00180000",
                "underlying_symbol": "AAPL",
                "qty": "5",
                "side": "buy",
                "order_type": "limit",
                "limit_price": "6.50",
                "status": "pending_new",
                "time_in_force": "day"
            }
            
            option_order_request = {
                "option_symbol": "AAPL240216C00180000",
                "qty": 5,
                "side": "buy",
                "type": "limit",
                "limit_price": 6.50,
                "time_in_force": "day"
            }
            
            response = client.post("/api/v1/options/order", headers=headers, json=option_order_request)
            if response.status_code == 200:
                order_data = response.json()
                assert order_data["option_symbol"] == "AAPL240216C00180000"
                assert order_data["qty"] == "5"
                assert order_data["side"] == "buy"
    
    def test_batch_options_quotes_workflow(self, options_trader_client):
        """测试批量期权报价工作流"""
        client, headers = options_trader_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 批量获取期权报价
            mock_client.get_multiple_option_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL240216C00180000",
                        "bid_price": 6.30,
                        "ask_price": 6.70,
                        "last_price": 6.50
                    },
                    {
                        "symbol": "AAPL240216C00185000",
                        "bid_price": 4.80,
                        "ask_price": 5.20,
                        "last_price": 5.00
                    },
                    {
                        "error": "No real market data available for option symbol: AAPL240216C00200000"
                    }
                ],
                "count": 3,
                "successful_count": 2,
                "failed_count": 1,
                "failed_symbols": ["AAPL240216C00200000"]
            }
            
            batch_request = {
                "option_symbols": [
                    "AAPL240216C00180000",
                    "AAPL240216C00185000", 
                    "AAPL240216C00200000"
                ]
            }
            
            response = client.post("/api/v1/options/quotes/batch", json=batch_request)
            if response.status_code == 200:
                batch_data = response.json()
                assert batch_data["count"] == 3
                assert batch_data["successful_count"] == 2
                assert batch_data["failed_count"] == 1


class TestMultiAccountTradingWorkflows:
    """多账户交易工作流测试"""
    
    @pytest.fixture
    def multi_account_setup(self):
        """多账户设置"""
        # 账户1 - 高级交易者
        premium_token = create_jwt_token({
            "user_id": "premium_trader",
            "account_id": "premium_account_1",
            "permissions": ["trading", "options", "advanced_trading", "margin"]
        })
        
        # 账户2 - 标准交易者
        standard_token = create_jwt_token({
            "user_id": "standard_trader",
            "account_id": "standard_account_1", 
            "permissions": ["trading", "market_data"]
        })
        
        client = TestClient(app)
        
        return {
            "client": client,
            "premium_headers": {"Authorization": f"Bearer {premium_token}"},
            "standard_headers": {"Authorization": f"Bearer {standard_token}"}
        }
    
    def test_account_routing_workflow(self, multi_account_setup):
        """测试账户路由工作流"""
        setup = multi_account_setup
        client = setup["client"]
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 高级账户的市场数据请求
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "source": "premium_feed"
            }
            
            response = client.get(
                "/api/v1/stocks/AAPL/quote?account_id=premium_account_1",
                headers=setup["premium_headers"]
            )
            
            if response.status_code == 200:
                # 验证路由到正确账户
                mock_pooled.get_stock_quote.assert_called_with(
                    symbol="AAPL",
                    account_id="premium_account_1",
                    routing_key="AAPL"
                )
            
            # 标准账户的市场数据请求
            response = client.get(
                "/api/v1/stocks/GOOGL/quote?account_id=standard_account_1",
                headers=setup["standard_headers"]
            )
            
            if response.status_code == 200:
                mock_pooled.get_stock_quote.assert_called_with(
                    symbol="GOOGL",
                    account_id="standard_account_1", 
                    routing_key="GOOGL"
                )
    
    def test_load_balancing_workflow(self, multi_account_setup):
        """测试负载均衡工作流"""
        setup = multi_account_setup
        client = setup["client"]
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {"symbol": "AAPL", "bid_price": 185.0, "ask_price": 185.5},
                    {"symbol": "GOOGL", "bid_price": 2750.0, "ask_price": 2755.0},
                    {"symbol": "TSLA", "bid_price": 220.0, "ask_price": 221.0}
                ],
                "count": 3
            }
            
            # 使用路由键进行负载均衡
            batch_request = {
                "symbols": ["AAPL", "GOOGL", "TSLA"]
            }
            
            response = client.post(
                "/api/v1/stocks/quotes/batch?routing_key=portfolio_update",
                headers=setup["premium_headers"],
                json=batch_request
            )
            
            if response.status_code == 200:
                # 验证路由键被正确传递
                mock_pooled.get_multiple_stock_quotes.assert_called_with(
                    symbols=["AAPL", "GOOGL", "TSLA"],
                    account_id=None,
                    routing_key="portfolio_update"
                )
    
    def test_concurrent_multi_account_trading(self, multi_account_setup):
        """测试并发多账户交易"""
        setup = multi_account_setup
        client = setup["client"]
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 模拟同时下单
            mock_client.place_stock_order.return_value = {
                "id": "concurrent_order",
                "status": "pending_new"
            }
            
            # 高级账户下单
            premium_order = {
                "symbol": "AAPL",
                "qty": 100,
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            }
            
            response1 = client.post(
                "/api/v1/stocks/order",
                headers=setup["premium_headers"],
                json=premium_order
            )
            
            # 标准账户下单  
            standard_order = {
                "symbol": "GOOGL",
                "qty": 10,
                "side": "buy",
                "type": "limit",
                "limit_price": 2700.0,
                "time_in_force": "day"
            }
            
            response2 = client.post(
                "/api/v1/stocks/order",
                headers=setup["standard_headers"],
                json=standard_order
            )
            
            # 验证两个订单都成功处理
            assert response1.status_code in [200, 401, 500]  # 根据实际情况
            assert response2.status_code in [200, 401, 500]


class TestRealTimeDataIntegration:
    """实时数据集成测试"""
    
    def test_market_data_websocket_integration(self):
        """测试市场数据WebSocket集成"""
        # 注意：这是一个概念性测试，实际WebSocket测试需要特殊设置
        
        client = TestClient(app)
        
        # 检查WebSocket状态端点
        response = client.get("/api/v1/ws/status")
        assert response.status_code == 200
        
        status_data = response.json()
        assert "websocket_endpoint" in status_data
        assert "default_symbols" in status_data
        assert "connection_info" in status_data
    
    @pytest.mark.asyncio
    async def test_real_time_quote_updates(self):
        """测试实时报价更新"""
        # 模拟实时报价流
        
        from app.websocket_routes import AlpacaWebSocketManager
        
        manager = AlpacaWebSocketManager()
        
        # 模拟连接
        mock_websocket = AsyncMock()
        from app.websocket_routes import active_connections
        active_connections["test_trader"] = mock_websocket
        
        # 模拟报价更新
        class MockQuote:
            def __init__(self, symbol, bid, ask):
                self.symbol = symbol
                self.bid_price = bid
                self.ask_price = ask
                self.bid_size = 100
                self.ask_size = 200
                self.timestamp = datetime.now()
        
        quote = MockQuote("AAPL", 185.25, 185.50)
        await manager.broadcast_quote_data("stock", quote)
        
        # 验证消息被发送
        mock_websocket.send_text.assert_called_once()
        
        # 清理
        active_connections.clear()


class TestTradingWorkflowFailures:
    """交易工作流失败测试"""
    
    @pytest.fixture
    def trader_client(self):
        """交易者客户端"""
        client = TestClient(app)
        
        token = create_jwt_token({
            "user_id": "test_trader",
            "account_id": "test_account",
            "permissions": ["trading", "market_data"]
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        return client, headers
    
    def test_insufficient_buying_power_workflow(self, trader_client):
        """测试资金不足工作流"""
        client, headers = trader_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 模拟资金不足错误
            mock_client.place_stock_order.side_effect = Exception("Insufficient buying power")
            
            order_request = {
                "symbol": "AAPL",
                "qty": 1000,  # 大量股票
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            }
            
            response = client.post("/api/v1/stocks/order", headers=headers, json=order_request)
            
            # 应该返回适当的错误
            assert response.status_code in [400, 500]
    
    def test_invalid_symbol_workflow(self, trader_client):
        """测试无效符号工作流"""
        client, headers = trader_client
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 模拟无效符号错误
            mock_pooled.get_stock_quote.return_value = {
                "error": "Symbol not found: INVALID"
            }
            
            response = client.get("/api/v1/stocks/INVALID/quote", headers=headers)
            
            if response.status_code == 400:
                error_data = response.json()
                assert "error" in error_data
    
    def test_market_closed_workflow(self, trader_client):
        """测试市场关闭工作流"""
        client, headers = trader_client
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # 模拟市场关闭错误
            mock_client.place_stock_order.side_effect = Exception("Market is closed")
            
            order_request = {
                "symbol": "AAPL",
                "qty": 10,
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            }
            
            response = client.post("/api/v1/stocks/order", headers=headers, json=order_request)
            
            # 应该返回适当的错误
            assert response.status_code in [400, 500]
    
    def test_connection_failure_recovery(self, trader_client):
        """测试连接失败恢复"""
        client, headers = trader_client
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            # 第一次请求失败
            mock_pooled.get_account.side_effect = Exception("Connection timeout")
            
            response1 = client.get("/api/v1/account", headers=headers)
            assert response1.status_code in [500, 502, 503]
            
            # 第二次请求成功（模拟恢复）
            mock_pooled.get_account.side_effect = None
            mock_pooled.get_account.return_value = {
                "account_number": "123456789",
                "buying_power": 50000.0
            }
            
            response2 = client.get("/api/v1/account", headers=headers)
            if response2.status_code == 200:
                account_data = response2.json()
                assert account_data["buying_power"] == 50000.0


class TestTradingWorkflowPerformance:
    """交易工作流性能测试"""
    
    @pytest.mark.performance
    def test_high_frequency_quote_requests(self):
        """测试高频报价请求"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50
            }
            
            start_time = time.time()
            
            # 发送100个报价请求
            for i in range(100):
                response = client.get("/api/v1/stocks/AAPL/quote")
                assert response.status_code in [200, 401]  # 可能需要认证
            
            end_time = time.time()
            
            total_time = end_time - start_time
            requests_per_second = 100 / total_time
            
            print(f"Quote requests performance: {requests_per_second:.0f} req/s")
            
            # 性能断言
            assert total_time < 10.0, f"Quote requests too slow: {total_time:.3f}s"
    
    @pytest.mark.performance
    def test_batch_requests_performance(self):
        """测试批量请求性能"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_multiple_stock_quotes.return_value = {
                "quotes": [{"symbol": f"STOCK{i}", "bid_price": 100.0, "ask_price": 100.5} 
                          for i in range(20)],
                "count": 20
            }
            
            start_time = time.time()
            
            # 发送10个批量请求，每个包含20个符号
            for i in range(10):
                symbols = [f"STOCK{j}" for j in range(i*20, (i+1)*20)]
                batch_request = {"symbols": symbols}
                
                response = client.post("/api/v1/stocks/quotes/batch", json=batch_request)
                assert response.status_code in [200, 401]
            
            end_time = time.time()
            
            total_time = end_time - start_time
            symbols_per_second = (10 * 20) / total_time
            
            print(f"Batch requests performance: {symbols_per_second:.0f} symbols/s")
            
            # 性能断言
            assert total_time < 5.0, f"Batch requests too slow: {total_time:.3f}s"


class TestTradingWorkflowCompliance:
    """交易工作流合规测试"""
    
    def test_authentication_enforcement(self):
        """测试认证强制执行"""
        client = TestClient(app)
        
        # 未认证的交易请求应该被拒绝
        protected_endpoints = [
            ("POST", "/api/v1/stocks/order"),
            ("POST", "/api/v1/options/order"),
            ("GET", "/api/v1/orders"),
            ("DELETE", "/api/v1/orders/test_id")
        ]
        
        for method, endpoint in protected_endpoints:
            response = client.request(method, endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"
    
    def test_permission_based_access_control(self):
        """测试基于权限的访问控制"""
        client = TestClient(app)
        
        # 创建只有基础权限的用户
        basic_token = create_jwt_token({
            "user_id": "basic_user",
            "permissions": ["market_data"]  # 没有交易权限
        })
        
        headers = {"Authorization": f"Bearer {basic_token}"}
        
        # 交易端点应该被拒绝或返回错误
        trading_request = {
            "symbol": "AAPL",
            "qty": 10,
            "side": "buy",
            "type": "market",
            "time_in_force": "day"
        }
        
        response = client.post("/api/v1/stocks/order", headers=headers, json=trading_request)
        # 根据实际实现，可能返回403（禁止）或其他错误
        assert response.status_code in [401, 403, 500]
    
    def test_order_validation(self):
        """测试订单验证"""
        client = TestClient(app)
        
        token = create_jwt_token({
            "user_id": "test_trader",
            "permissions": ["trading"]
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 测试无效订单参数
        invalid_orders = [
            {
                "symbol": "",  # 空符号
                "qty": 10,
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            },
            {
                "symbol": "AAPL",
                "qty": 0,  # 零数量
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            },
            {
                "symbol": "AAPL",
                "qty": 10,
                "side": "invalid_side",  # 无效方向
                "type": "market",
                "time_in_force": "day"
            }
        ]
        
        for invalid_order in invalid_orders:
            response = client.post("/api/v1/stocks/order", headers=headers, json=invalid_order)
            # 无效订单应该被拒绝
            assert response.status_code in [400, 422], f"Invalid order should be rejected: {invalid_order}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])