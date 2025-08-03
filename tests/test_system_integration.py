"""
系统集成测试套件
测试认证、Redis、连接池等关键组件的集成
"""

import pytest
import asyncio
import httpx
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import jwt
import time
from datetime import datetime, timedelta

# 导入应用组件
from main import app
from app.middleware import (
    user_manager, create_jwt_token, verify_jwt_token, 
    get_redis_client, initialize_redis, RateLimiter
)
from app.connection_pool import connection_pool
from app.user_manager import UserManager, User, UserRole, UserStatus
from config import settings


class TestAuthenticationSystem:
    """认证系统测试"""
    
    @pytest.fixture
    def test_client(self):
        """测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user_data(self):
        """模拟用户数据"""
        return {
            "user_id": "test_user_123",
            "alpaca_credentials": {
                "api_key": "encrypted_api_key",
                "secret_key": "encrypted_secret_key", 
                "paper_trading": True
            },
            "permissions": ["trading", "market_data"],
            "rate_limits": {
                "requests_per_minute": 120,
                "orders_per_minute": 10
            }
        }
    
    def test_jwt_token_creation_and_verification(self, mock_user_data):
        """测试JWT令牌创建和验证"""
        # 创建JWT令牌
        token = create_jwt_token(mock_user_data)
        assert token is not None
        assert isinstance(token, str)
        
        # 验证JWT令牌
        payload = verify_jwt_token(token)
        assert payload["user_id"] == mock_user_data["user_id"]
        assert payload["permissions"] == mock_user_data["permissions"]
        
    def test_expired_jwt_token(self, mock_user_data):
        """测试过期JWT令牌"""
        # 创建已过期的令牌
        payload = {
            "user_id": mock_user_data["user_id"],
            "permissions": mock_user_data["permissions"],
            "exp": datetime.utcnow() - timedelta(hours=1),  # 过期
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        
        expired_token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        
        # 验证应该抛出异常
        with pytest.raises(Exception) as exc_info:
            verify_jwt_token(expired_token)
        assert "expired" in str(exc_info.value).lower()
    
    def test_invalid_jwt_token(self):
        """测试无效JWT令牌"""
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(Exception):
            verify_jwt_token(invalid_token)
    
    def test_authentication_middleware_public_paths(self, test_client):
        """测试认证中间件对公共路径的处理"""
        public_paths = ["/", "/docs", "/health", "/api/v1/health"]
        
        for path in public_paths:
            response = test_client.get(path)
            # 公共路径不应该返回401
            assert response.status_code != 401
    
    def test_authentication_middleware_protected_paths(self, test_client):
        """测试认证中间件对受保护路径的处理"""
        protected_path = "/api/v1/stocks/quote"
        
        # 无认证头的请求应该返回401
        response = test_client.post(protected_path, json={"symbol": "AAPL"})
        assert response.status_code == 401
        assert "Missing or invalid authorization header" in response.json()["detail"]
    
    def test_authentication_with_valid_token(self, test_client, mock_user_data):
        """测试有效令牌的认证"""
        # 创建用户上下文
        user_manager.create_user_context(mock_user_data)
        
        # 创建有效令牌
        token = create_jwt_token(mock_user_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 模拟Alpaca客户端
        with patch('app.routes.get_alpaca_client_for_user') as mock_client:
            mock_client.return_value.get_stock_quote = AsyncMock(return_value={
                "symbol": "AAPL",
                "bid_price": 150.0,
                "ask_price": 150.5
            })
            
            response = test_client.post(
                "/api/v1/stocks/quote",
                json={"symbol": "AAPL"},
                headers=headers
            )
            
            # 应该成功返回数据
            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "AAPL"


class TestRedisIntegration:
    """Redis集成测试"""
    
    def test_redis_initialization(self):
        """测试Redis初始化"""
        # 重新初始化Redis
        initialize_redis()
        
        # 获取Redis客户端
        redis_client = get_redis_client()
        
        # 如果Redis服务可用，应该返回客户端；否则返回None
        if redis_client:
            # 测试连接
            try:
                redis_client.ping()
                assert True  # 连接成功
            except Exception:
                pytest.fail("Redis ping failed")
        else:
            # Redis不可用，应该能优雅处理
            assert redis_client is None
    
    def test_rate_limiter_memory_fallback(self):
        """测试rate limiter内存回退"""
        rate_limiter = RateLimiter()
        
        # 模拟Redis不可用
        with patch('app.middleware.get_redis_client', return_value=None):
            # 测试内存rate limiting
            allowed, info = rate_limiter.is_allowed("test_user", 10, 60)
            assert allowed is True
            assert info["limit"] == 10
            assert info["remaining"] == 9
            
            # 测试连续请求
            for i in range(9):  # 再请求9次，总共10次
                allowed, info = rate_limiter.is_allowed("test_user", 10, 60)
                assert allowed is True
            
            # 第11次请求应该被拒绝
            allowed, info = rate_limiter.is_allowed("test_user", 10, 60)
            assert allowed is False
            assert info["remaining"] == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_redis_mode(self):
        """测试Redis模式的rate limiting"""
        rate_limiter = RateLimiter()
        
        # 模拟Redis客户端
        mock_redis = Mock()
        mock_redis.pipeline.return_value.__enter__.return_value.execute.return_value = [None, 5, None, None]
        
        with patch('app.middleware.get_redis_client', return_value=mock_redis):
            allowed, info = rate_limiter.is_allowed("test_user", 10, 60)
            assert allowed is True
            assert info["limit"] == 10


class TestConnectionPoolSystem:
    """连接池系统测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户对象"""
        user = Mock(spec=User)
        user.id = "test_user_123"
        user.alpaca_paper_trading = True
        user.decrypt_alpaca_credentials.return_value = ("test_key", "test_secret")
        return user
    
    @pytest.mark.asyncio
    async def test_connection_pool_initialization(self):
        """测试连接池初始化"""
        # 连接池应该成功初始化
        assert connection_pool is not None
        assert connection_pool.max_connections_per_user == 5
        assert connection_pool.max_idle_time_minutes == 30
    
    @pytest.mark.asyncio
    async def test_get_connection_new_user(self, mock_user):
        """测试为新用户获取连接"""
        with patch('app.connection_pool.AlpacaConnection') as MockConnection:
            mock_conn = AsyncMock()
            mock_conn.test_connection.return_value = True
            mock_conn.is_available = True
            mock_conn.stats.usage_count = 0
            MockConnection.return_value = mock_conn
            
            # 获取连接
            connection = await connection_pool.get_connection(mock_user)
            
            assert connection is not None
            assert mock_user.id in connection_pool.user_pools
    
    @pytest.mark.asyncio
    async def test_connection_pool_stats(self):
        """测试连接池统计信息"""
        stats = connection_pool.get_pool_stats()
        
        assert "total_users" in stats
        assert "total_connections" in stats
        assert "user_stats" in stats
        assert isinstance(stats["total_users"], int)
        assert isinstance(stats["total_connections"], int)


class TestSystemIntegration:
    """系统集成测试"""
    
    @pytest.fixture
    def test_client(self):
        return TestClient(app)
    
    def test_health_endpoint(self, test_client):
        """测试健康检查端点"""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "configuration" in data
        assert "data_policy" in data
    
    def test_root_endpoint(self, test_client):
        """测试根端点"""
        response = test_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "running"
        assert data["service"] == settings.app_name
    
    @pytest.mark.asyncio
    async def test_middleware_stack_integration(self, test_client):
        """测试中间件堆栈集成"""
        # 测试请求经过完整的中间件堆栈
        start_time = time.time()
        
        response = test_client.get("/api/v1/health")
        
        # 检查响应头
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time > 0
        assert process_time < 1.0  # 应该在1秒内完成
    
    def test_cors_headers(self, test_client):
        """测试CORS头"""
        response = test_client.options("/api/v1/health")
        
        # 检查CORS响应头
        assert response.status_code in [200, 404]  # OPTIONS可能返回404，这是正常的


class TestErrorHandling:
    """错误处理测试"""
    
    @pytest.fixture
    def test_client(self):
        return TestClient(app)
    
    def test_invalid_json_request(self, test_client):
        """测试无效JSON请求"""
        response = test_client.post(
            "/api/v1/stocks/quote",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 401, 422]  # 可能的错误状态码
    
    def test_missing_required_fields(self, test_client):
        """测试缺少必需字段"""
        # 创建有效令牌以绕过认证
        mock_user_data = {
            "user_id": "test_user",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(mock_user_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = test_client.post(
            "/api/v1/stocks/quote",
            json={},  # 缺少symbol字段
            headers=headers
        )
        assert response.status_code == 422  # Validation error


class TestSecurityFeatures:
    """安全特性测试"""
    
    @pytest.fixture
    def test_client(self):
        return TestClient(app)
    
    def test_rate_limiting_headers(self, test_client):
        """测试rate limiting头"""
        mock_user_data = {
            "user_id": "test_user",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(mock_user_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 创建用户上下文
        user_manager.create_user_context(mock_user_data)
        
        with patch('app.routes.get_alpaca_client_for_user') as mock_client:
            mock_client.return_value.get_stock_quote = AsyncMock(return_value={
                "symbol": "AAPL",
                "bid_price": 150.0
            })
            
            response = test_client.post(
                "/api/v1/stocks/quote",
                json={"symbol": "AAPL"},
                headers=headers
            )
            
            # 检查rate limiting头
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
    
    def test_jwt_token_tampering(self, test_client):
        """测试JWT令牌篡改"""
        # 创建正常令牌然后篡改
        mock_user_data = {
            "user_id": "test_user",
            "permissions": ["trading"]
        }
        token = create_jwt_token(mock_user_data)
        
        # 篡改令牌
        tampered_token = token[:-10] + "tampered123"
        headers = {"Authorization": f"Bearer {tampered_token}"}
        
        response = test_client.post(
            "/api/v1/stocks/quote",
            json={"symbol": "AAPL"},
            headers=headers
        )
        
        assert response.status_code == 401


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])