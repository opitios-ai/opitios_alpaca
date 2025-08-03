"""
端到端测试套件
测试完整的用户流程和系统集成
"""

import pytest
import httpx
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from main import app
from app.middleware import create_jwt_token, user_manager
from app.user_manager import UserManager, User, UserRole, UserStatus


class TestCompleteUserJourney:
    """完整用户旅程测试"""
    
    @pytest.fixture
    def test_client(self):
        return TestClient(app)
    
    @pytest.fixture
    def authenticated_user(self):
        """创建已认证用户"""
        user_data = {
            "user_id": "e2e_test_user",
            "alpaca_credentials": {
                "api_key": "test_api_key_encrypted",
                "secret_key": "test_secret_key_encrypted",
                "paper_trading": True
            },
            "permissions": ["trading", "market_data", "account_management"],
            "rate_limits": {
                "requests_per_minute": 120,
                "orders_per_minute": 10,
                "market_data_per_second": 20
            }
        }
        
        # 创建用户上下文
        context = user_manager.create_user_context(user_data)
        
        # 创建JWT令牌
        token = create_jwt_token(user_data)
        
        return {
            "context": context,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
            "data": user_data
        }
    
    def test_complete_trading_workflow(self, test_client, authenticated_user):
        """测试完整的交易工作流程"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            # 模拟Alpaca客户端
            mock_client = Mock()
            mock_client_factory.return_value = mock_client
            
            # 1. 检查账户信息
            mock_client.get_account = AsyncMock(return_value={
                "account_number": "123456789",
                "buying_power": 50000.0,
                "cash": 25000.0,
                "portfolio_value": 75000.0,
                "status": "ACTIVE"
            })
            
            account_response = test_client.get("/api/v1/account", headers=headers)
            assert account_response.status_code == 200
            account_data = account_response.json()
            assert account_data["buying_power"] == 50000.0
            
            # 2. 获取股票报价
            mock_client.get_stock_quote = AsyncMock(return_value={
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.75,
                "last_price": 185.50,
                "timestamp": "2024-01-15T15:30:00Z"
            })
            
            quote_response = test_client.post(
                "/api/v1/stocks/quote",
                json={"symbol": "AAPL"},
                headers=headers
            )
            assert quote_response.status_code == 200
            quote_data = quote_response.json()
            assert quote_data["symbol"] == "AAPL"
            assert quote_data["bid_price"] == 185.25
            
            # 3. 下单买入股票
            mock_client.place_stock_order = AsyncMock(return_value={
                "id": "order_123",
                "symbol": "AAPL",
                "qty": 10,
                "side": "buy",
                "order_type": "market",
                "status": "pending_new",
                "filled_qty": 0,
                "submitted_at": "2024-01-15T15:31:00Z"
            })
            
            order_response = test_client.post(
                "/api/v1/stocks/order",
                json={
                    "symbol": "AAPL",
                    "qty": 10,
                    "side": "buy",
                    "type": "market",
                    "time_in_force": "day"
                },
                headers=headers
            )
            assert order_response.status_code == 200
            order_data = order_response.json()
            assert order_data["symbol"] == "AAPL"
            assert order_data["qty"] == 10
            
            # 4. 查看订单状态
            mock_client.get_orders = AsyncMock(return_value=[{
                "id": "order_123",
                "symbol": "AAPL",
                "qty": 10,
                "side": "buy",
                "status": "filled",
                "filled_qty": 10,
                "filled_avg_price": 185.50
            }])
            
            orders_response = test_client.get("/api/v1/orders", headers=headers)
            assert orders_response.status_code == 200
            orders_data = orders_response.json()
            assert len(orders_data) == 1
            assert orders_data[0]["status"] == "filled"
            
            # 5. 查看持仓
            mock_client.get_positions = AsyncMock(return_value=[{
                "symbol": "AAPL",
                "qty": 10,
                "side": "long",
                "market_value": 1855.0,
                "cost_basis": 1855.0,
                "unrealized_pl": 0.0,
                "avg_entry_price": 185.50
            }])
            
            positions_response = test_client.get("/api/v1/positions", headers=headers)
            assert positions_response.status_code == 200
            positions_data = positions_response.json()
            assert len(positions_data) == 1
            assert positions_data[0]["symbol"] == "AAPL"
            assert positions_data[0]["qty"] == 10
    
    def test_options_trading_workflow(self, test_client, authenticated_user):
        """测试期权交易工作流程"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            mock_client = Mock()
            mock_client_factory.return_value = mock_client
            
            # 1. 获取期权链
            mock_client.get_options_chain = AsyncMock(return_value={
                "underlying_symbol": "AAPL",
                "underlying_price": 185.50,
                "expiration_dates": ["2024-02-16"],
                "options_count": 20,
                "options": [
                    {
                        "symbol": "AAPL240216C00185000",
                        "strike_price": 185.0,
                        "option_type": "call",
                        "expiration_date": "2024-02-16",
                        "bid_price": 5.25,
                        "ask_price": 5.75,
                        "last_price": 5.50,
                        "implied_volatility": 0.28
                    },
                    {
                        "symbol": "AAPL240216P00185000",
                        "strike_price": 185.0,
                        "option_type": "put",
                        "expiration_date": "2024-02-16",
                        "bid_price": 4.80,
                        "ask_price": 5.20,
                        "last_price": 5.00,
                        "implied_volatility": 0.26
                    }
                ]
            })
            
            chain_response = test_client.post(
                "/api/v1/options/chain",
                json={
                    "underlying_symbol": "AAPL",
                    "expiration_date": "2024-02-16"
                },
                headers=headers
            )
            assert chain_response.status_code == 200
            chain_data = chain_response.json()
            assert chain_data["underlying_symbol"] == "AAPL"
            assert len(chain_data["options"]) == 2
            
            # 2. 获取特定期权报价
            mock_client.get_option_quote = AsyncMock(return_value={
                "symbol": "AAPL240216C00185000",
                "underlying_symbol": "AAPL",
                "strike_price": 185.0,
                "option_type": "call",
                "expiration_date": "2024-02-16",
                "bid_price": 5.25,
                "ask_price": 5.75,
                "last_price": 5.50,
                "implied_volatility": 0.28,
                "timestamp": "2024-01-15T15:30:00Z"
            })
            
            option_quote_response = test_client.post(
                "/api/v1/options/quote",
                json={"option_symbol": "AAPL240216C00185000"},
                headers=headers
            )
            assert option_quote_response.status_code == 200
            option_data = option_quote_response.json()
            assert option_data["symbol"] == "AAPL240216C00185000"
            assert option_data["strike_price"] == 185.0
            
            # 3. 下期权订单
            mock_client.place_option_order = AsyncMock(return_value={
                "id": "option_order_456",
                "option_symbol": "AAPL240216C00185000",
                "qty": 1,
                "side": "buy",
                "order_type": "limit",
                "limit_price": 5.50,
                "status": "pending_new",
                "submitted_at": "2024-01-15T15:32:00Z"
            })
            
            option_order_response = test_client.post(
                "/api/v1/options/order",
                json={
                    "option_symbol": "AAPL240216C00185000",
                    "qty": 1,
                    "side": "buy",
                    "type": "limit",
                    "limit_price": 5.50,
                    "time_in_force": "day"
                },
                headers=headers
            )
            assert option_order_response.status_code == 200
            option_order_data = option_order_response.json()
            assert option_order_data["option_symbol"] == "AAPL240216C00185000"
    
    def test_batch_quote_workflow(self, test_client, authenticated_user):
        """测试批量报价工作流程"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            mock_client = Mock()
            mock_client_factory.return_value = mock_client
            
            # 批量股票报价
            mock_client.get_multiple_stock_quotes = AsyncMock(return_value={
                "quotes": [
                    {"symbol": "AAPL", "bid_price": 185.25, "ask_price": 185.75, "timestamp": "2024-01-15T15:30:00Z"},
                    {"symbol": "GOOGL", "bid_price": 142.50, "ask_price": 142.90, "timestamp": "2024-01-15T15:30:00Z"},
                    {"symbol": "MSFT", "bid_price": 375.20, "ask_price": 375.80, "timestamp": "2024-01-15T15:30:00Z"}
                ],
                "count": 3,
                "requested_symbols": ["AAPL", "GOOGL", "MSFT"]
            })
            
            batch_response = test_client.post(
                "/api/v1/stocks/quotes/batch",
                json={"symbols": ["AAPL", "GOOGL", "MSFT"]},
                headers=headers
            )
            assert batch_response.status_code == 200
            batch_data = batch_response.json()
            assert batch_data["count"] == 3
            assert len(batch_data["quotes"]) == 3
            
            # 批量期权报价
            mock_client.get_multiple_option_quotes = AsyncMock(return_value={
                "quotes": [
                    {"symbol": "AAPL240216C00185000", "bid_price": 5.25, "ask_price": 5.75},
                    {"symbol": "AAPL240216P00185000", "bid_price": 4.80, "ask_price": 5.20}
                ],
                "count": 2,
                "successful_count": 2,
                "failed_count": 0,
                "failed_symbols": []
            })
            
            option_batch_response = test_client.post(
                "/api/v1/options/quotes/batch",
                json={"option_symbols": ["AAPL240216C00185000", "AAPL240216P00185000"]},
                headers=headers
            )
            assert option_batch_response.status_code == 200
            option_batch_data = option_batch_response.json()
            assert option_batch_data["successful_count"] == 2


class TestErrorScenarios:
    """错误场景端到端测试"""
    
    @pytest.fixture
    def test_client(self):
        return TestClient(app)
    
    @pytest.fixture
    def authenticated_user(self):
        user_data = {
            "user_id": "error_test_user",
            "alpaca_credentials": {
                "api_key": "test_key",
                "secret_key": "test_secret",
                "paper_trading": True
            },
            "permissions": ["trading", "market_data"],
            "rate_limits": {"requests_per_minute": 120}
        }
        
        user_manager.create_user_context(user_data)
        token = create_jwt_token(user_data)
        
        return {
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"}
        }
    
    def test_alpaca_api_error_handling(self, test_client, authenticated_user):
        """测试Alpaca API错误处理"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            mock_client = Mock()
            mock_client_factory.return_value = mock_client
            
            # 模拟API错误
            mock_client.get_stock_quote = AsyncMock(return_value={
                "error": "Symbol not found"
            })
            
            response = test_client.post(
                "/api/v1/stocks/quote",
                json={"symbol": "INVALID"},
                headers=headers
            )
            assert response.status_code == 400
            error_data = response.json()
            assert "error" in error_data["detail"]
    
    def test_rate_limiting_error(self, test_client, authenticated_user):
        """测试rate limiting错误"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            mock_client = Mock()
            mock_client_factory.return_value = mock_client
            mock_client.get_stock_quote = AsyncMock(return_value={
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.75
            })
            
            # 模拟rate limiter返回拒绝
            with patch('app.middleware.RateLimiter.is_allowed') as mock_rate_limit:
                mock_rate_limit.return_value = (False, {
                    "limit": 60,
                    "remaining": 0,
                    "reset_time": 1642262400
                })
                
                response = test_client.post(
                    "/api/v1/stocks/quote",
                    json={"symbol": "AAPL"},
                    headers=headers
                )
                assert response.status_code == 429
                assert "Rate limit exceeded" in response.json()["detail"]
    
    def test_authentication_error_scenarios(self, test_client):
        """测试认证错误场景"""
        # 1. 无认证头
        response = test_client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
        assert response.status_code == 401
        assert "Missing or invalid authorization header" in response.json()["detail"]
        
        # 2. 无效令牌格式
        response = test_client.post(
            "/api/v1/stocks/quote",
            json={"symbol": "AAPL"},
            headers={"Authorization": "InvalidToken"}
        )
        assert response.status_code == 401
        
        # 3. 过期令牌
        expired_token = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoidGVzdCIsImV4cCI6MTAwfQ.invalid"
        response = test_client.post(
            "/api/v1/stocks/quote",
            json={"symbol": "AAPL"},
            headers={"Authorization": expired_token}
        )
        assert response.status_code == 401
    
    def test_validation_error_scenarios(self, test_client, authenticated_user):
        """测试验证错误场景"""
        headers = authenticated_user["headers"]
        
        # 1. 缺少必需字段
        response = test_client.post("/api/v1/stocks/quote", json={}, headers=headers)
        assert response.status_code == 422
        
        # 2. 无效符号格式
        response = test_client.post(
            "/api/v1/stocks/quote",
            json={"symbol": ""},
            headers=headers
        )
        assert response.status_code == 422
        
        # 3. 批量请求超过限制
        symbols = [f"SYM{i}" for i in range(25)]  # 超过20个符号的限制
        response = test_client.post(
            "/api/v1/stocks/quotes/batch",
            json={"symbols": symbols},
            headers=headers
        )
        assert response.status_code == 400


class TestSystemResiliency:
    """系统弹性测试"""
    
    @pytest.fixture
    def test_client(self):
        return TestClient(app)
    
    @pytest.fixture
    def authenticated_user(self):
        user_data = {
            "user_id": "resiliency_test_user",
            "permissions": ["trading", "market_data"]
        }
        user_manager.create_user_context(user_data)
        token = create_jwt_token(user_data)
        return {"headers": {"Authorization": f"Bearer {token}"}}
    
    def test_service_degradation(self, test_client, authenticated_user):
        """测试服务降级"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            # 模拟Alpaca服务不可用
            mock_client_factory.side_effect = Exception("Service unavailable")
            
            response = test_client.post(
                "/api/v1/stocks/quote",
                json={"symbol": "AAPL"},
                headers=headers
            )
            assert response.status_code == 500
            assert "Failed to initialize trading client" in response.json()["detail"]
    
    def test_partial_data_handling(self, test_client, authenticated_user):
        """测试部分数据处理"""
        headers = authenticated_user["headers"]
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client_factory:
            mock_client = Mock()
            mock_client_factory.return_value = mock_client
            
            # 模拟批量请求中部分失败
            mock_client.get_multiple_option_quotes = AsyncMock(return_value={
                "quotes": [
                    {"symbol": "AAPL240216C00185000", "bid_price": 5.25},
                    {"error": "No data available for INVALID240216C00185000"}
                ],
                "count": 2,
                "successful_count": 1,
                "failed_count": 1,
                "failed_symbols": ["INVALID240216C00185000"]
            })
            
            response = test_client.post(
                "/api/v1/options/quotes/batch",
                json={"option_symbols": ["AAPL240216C00185000", "INVALID240216C00185000"]},
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["successful_count"] == 1
            assert data["failed_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])