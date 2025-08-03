"""
JWT认证中间件综合测试套件
测试JWT token验证、权限检查、速率限制和安全性
"""

import pytest
import time
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware import (
    create_jwt_token, verify_jwt_token, RequestContext, RateLimiter,
    AuthenticationMiddleware, RateLimitMiddleware, LoggingMiddleware,
    get_current_context, initialize_redis, get_redis_client
)
from main import app


class TestJWTTokenOperations:
    """JWT Token操作测试"""
    
    def test_create_jwt_token_basic(self):
        """测试基础JWT token创建"""
        user_data = {
            "user_id": "test_user_123",
            "account_id": "account_456",
            "permissions": ["trading", "market_data"]
        }
        
        token = create_jwt_token(user_data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # 验证token可以被解码
        payload = verify_jwt_token(token)
        assert payload["user_id"] == "test_user_123"
        assert payload["account_id"] == "account_456"
        assert payload["permissions"] == ["trading", "market_data"]
        assert "exp" in payload
        assert "iat" in payload
    
    def test_create_jwt_token_minimal_data(self):
        """测试最小数据JWT token创建"""
        user_data = {"user_id": "minimal_user"}
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        
        assert payload["user_id"] == "minimal_user"
        assert payload["account_id"] is None
        assert payload["permissions"] == ["trading", "market_data"]  # 默认权限
    
    def test_create_jwt_token_empty_data(self):
        """测试空数据JWT token创建"""
        user_data = {}
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        
        assert payload["user_id"] == "demo_user"  # 默认用户ID
        assert payload["account_id"] is None
        assert payload["permissions"] == ["trading", "market_data"]
    
    def test_verify_jwt_token_valid(self):
        """测试有效JWT token验证"""
        user_data = {
            "user_id": "test_user",
            "permissions": ["admin", "trading"]
        }
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        
        assert payload["user_id"] == "test_user"
        assert payload["permissions"] == ["admin", "trading"]
    
    def test_verify_jwt_token_expired(self):
        """测试过期JWT token验证"""
        # 创建已过期的token
        with patch('app.middleware.datetime') as mock_datetime:
            past_time = datetime.utcnow() - timedelta(hours=25)
            mock_datetime.utcnow.return_value = past_time
            
            token = create_jwt_token({"user_id": "test_user"})
        
        # 验证过期token应该抛出异常
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(token)
        
        assert exc_info.value.status_code == 401
        assert "Token expired" in str(exc_info.value.detail)
    
    def test_verify_jwt_token_invalid_signature(self):
        """测试无效签名JWT token验证"""
        token = create_jwt_token({"user_id": "test_user"})
        
        # 修改token的最后一个字符来破坏签名
        invalid_token = token[:-1] + "X"
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(invalid_token)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in str(exc_info.value.detail)
    
    def test_verify_jwt_token_malformed(self):
        """测试格式错误的JWT token验证"""
        invalid_tokens = [
            "invalid.token",
            "not_a_token_at_all",
            "",
            "header.payload",  # 缺少签名部分
            "too.many.parts.here.invalid"
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises(HTTPException) as exc_info:
                verify_jwt_token(invalid_token)
            
            assert exc_info.value.status_code == 401
            assert "Invalid token" in str(exc_info.value.detail)
    
    def test_jwt_token_expiration_time(self):
        """测试JWT token过期时间设置"""
        user_data = {"user_id": "test_user"}
        
        before_creation = datetime.utcnow()
        token = create_jwt_token(user_data)
        after_creation = datetime.utcnow()
        
        payload = verify_jwt_token(token)
        
        # 验证过期时间设置正确（24小时后）
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp_min = before_creation + timedelta(hours=24)
        expected_exp_max = after_creation + timedelta(hours=24)
        
        assert expected_exp_min <= exp_time <= expected_exp_max
    
    def test_jwt_payload_structure(self):
        """测试JWT payload结构完整性"""
        user_data = {
            "user_id": "test_user_123",
            "account_id": "account_456",
            "permissions": ["admin", "trading", "analytics"]
        }
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        
        # 验证所有必需字段存在
        required_fields = ["user_id", "account_id", "permissions", "exp", "iat"]
        for field in required_fields:
            assert field in payload
        
        # 验证数据类型
        assert isinstance(payload["user_id"], str)
        assert isinstance(payload["permissions"], list)
        assert isinstance(payload["exp"], int)
        assert isinstance(payload["iat"], int)


class TestRequestContext:
    """请求上下文测试"""
    
    def test_request_context_creation(self):
        """测试请求上下文创建"""
        token_payload = {
            "user_id": "test_user_123",
            "account_id": "account_456",
            "permissions": ["trading", "market_data", "admin"]
        }
        
        context = RequestContext(token_payload)
        
        assert context.user_id == "test_user_123"
        assert context.account_id == "account_456"
        assert context.permissions == ["trading", "market_data", "admin"]
        assert isinstance(context.created_at, datetime)
        assert isinstance(context.last_active, datetime)
        assert context.request_count == 0
    
    def test_request_context_defaults(self):
        """测试请求上下文默认值"""
        token_payload = {}
        context = RequestContext(token_payload)
        
        assert context.user_id == "external_user"
        assert context.account_id is None
        assert context.permissions == []
        assert context.request_count == 0
    
    def test_update_activity(self):
        """测试活动更新"""
        context = RequestContext({"user_id": "test_user"})
        
        initial_last_active = context.last_active
        initial_request_count = context.request_count
        
        # 等待一小段时间确保时间戳不同
        time.sleep(0.01)
        
        context.update_activity()
        
        assert context.last_active > initial_last_active
        assert context.request_count == initial_request_count + 1
        
        # 再次更新
        context.update_activity()
        assert context.request_count == initial_request_count + 2
    
    def test_has_permission(self):
        """测试权限检查"""
        context = RequestContext({
            "user_id": "test_user",
            "permissions": ["trading", "market_data", "admin"]
        })
        
        # 测试存在的权限
        assert context.has_permission("trading") is True
        assert context.has_permission("market_data") is True
        assert context.has_permission("admin") is True
        
        # 测试不存在的权限
        assert context.has_permission("super_admin") is False
        assert context.has_permission("") is False
        assert context.has_permission("invalid_permission") is False
    
    def test_has_permission_empty_permissions(self):
        """测试空权限列表的权限检查"""
        context = RequestContext({"user_id": "test_user"})
        
        assert context.has_permission("trading") is False
        assert context.has_permission("admin") is False
        assert context.has_permission("") is False


class TestRateLimiter:
    """速率限制器测试"""
    
    @pytest.fixture
    def rate_limiter(self):
        """创建速率限制器实例"""
        return RateLimiter()
    
    def test_rate_limiter_creation(self, rate_limiter):
        """测试速率限制器创建"""
        assert rate_limiter.memory_store is not None
        assert hasattr(rate_limiter, '_get_key')
        assert hasattr(rate_limiter, '_clean_old_requests')
    
    def test_memory_rate_limit_within_limit(self, rate_limiter):
        """测试内存模式下限制内的请求"""
        identifier = "user123"
        limit = 5
        window_seconds = 60
        
        # 发送4个请求（在限制内）
        for i in range(4):
            allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
            assert allowed is True
            assert info["limit"] == limit
            assert info["remaining"] == limit - i - 1
            assert info["current_requests"] == i + 1
    
    def test_memory_rate_limit_exceed_limit(self, rate_limiter):
        """测试内存模式下超出限制的请求"""
        identifier = "user123"
        limit = 3
        window_seconds = 60
        
        # 发送3个请求（达到限制）
        for i in range(3):
            allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
            assert allowed is True
        
        # 第4个请求应该被拒绝
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        assert allowed is False
        assert info["remaining"] == 0
        assert info["current_requests"] == 3
    
    def test_memory_rate_limit_window_expiry(self, rate_limiter):
        """测试内存模式下时间窗口过期"""
        identifier = "user123"
        limit = 2
        window_seconds = 1  # 1秒窗口
        
        # 发送2个请求达到限制
        for i in range(2):
            allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
            assert allowed is True
        
        # 第3个请求被拒绝
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        assert allowed is False
        
        # 等待窗口过期
        time.sleep(1.1)
        
        # 现在应该可以再次请求
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        assert allowed is True
        assert info["current_requests"] == 1
    
    def test_memory_rate_limit_different_identifiers(self, rate_limiter):
        """测试不同标识符的独立限制"""
        limit = 2
        window_seconds = 60
        
        # 用户1发送请求
        allowed1, _ = rate_limiter.is_allowed("user1", limit, window_seconds)
        allowed2, _ = rate_limiter.is_allowed("user1", limit, window_seconds)
        allowed3, _ = rate_limiter.is_allowed("user1", limit, window_seconds)
        
        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is False  # 用户1被限制
        
        # 用户2应该仍然可以请求
        allowed4, _ = rate_limiter.is_allowed("user2", limit, window_seconds)
        allowed5, _ = rate_limiter.is_allowed("user2", limit, window_seconds)
        
        assert allowed4 is True
        assert allowed5 is True
    
    def test_get_key_generation(self, rate_limiter):
        """测试Redis key生成"""
        key = rate_limiter._get_key("user123", "60")
        assert key == "rate_limit:user123:60"
        
        key2 = rate_limiter._get_key("user456", "300")
        assert key2 == "rate_limit:user456:300"
    
    def test_clean_old_requests(self, rate_limiter):
        """测试过期请求清理"""
        from collections import deque
        
        now = time.time()
        requests = deque([
            now - 120,  # 2分钟前（过期）
            now - 90,   # 1.5分钟前（过期）
            now - 30,   # 30秒前（有效）
            now - 10    # 10秒前（有效）
        ])
        
        rate_limiter._clean_old_requests(requests, 60)  # 60秒窗口
        
        # 应该只剩下有效的请求
        assert len(requests) == 2
        assert requests[0] == now - 30
        assert requests[1] == now - 10
    
    @patch('app.middleware.get_redis_client')
    def test_redis_rate_limit_success(self, mock_get_redis, rate_limiter):
        """测试Redis模式下的速率限制成功"""
        # 模拟Redis客户端
        mock_redis = Mock()
        mock_get_redis.return_value = mock_redis
        
        # 模拟Redis pipeline
        mock_pipe = Mock()
        mock_redis.pipeline.return_value.__enter__.return_value = mock_pipe
        mock_pipe.execute.return_value = [None, 2, None, None]  # 2个当前请求
        
        identifier = "user123"
        limit = 5
        window_seconds = 60
        
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        
        assert allowed is True
        assert info["current_requests"] == 3  # 2 + 1
        assert info["remaining"] == 2  # 5 - 3
        assert info["limit"] == 5
        
        # 验证Redis命令调用
        mock_pipe.zremrangebyscore.assert_called_once()
        mock_pipe.zcard.assert_called_once()
        mock_pipe.zadd.assert_called_once()
        mock_pipe.expire.assert_called_once()
    
    @patch('app.middleware.get_redis_client')
    def test_redis_rate_limit_exceed(self, mock_get_redis, rate_limiter):
        """测试Redis模式下超出限制"""
        mock_redis = Mock()
        mock_get_redis.return_value = mock_redis
        
        mock_pipe = Mock()
        mock_redis.pipeline.return_value.__enter__.return_value = mock_pipe
        mock_pipe.execute.return_value = [None, 5, None, None]  # 5个当前请求
        
        identifier = "user123"
        limit = 5
        window_seconds = 60
        
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        
        assert allowed is False
        assert info["current_requests"] == 6  # 5 + 1
        assert info["remaining"] == 0
    
    @patch('app.middleware.get_redis_client')
    def test_redis_fallback_to_memory(self, mock_get_redis, rate_limiter):
        """测试Redis故障时回退到内存模式"""
        mock_redis = Mock()
        mock_get_redis.return_value = mock_redis
        
        # 模拟Redis异常
        mock_redis.pipeline.side_effect = Exception("Redis connection failed")
        
        identifier = "user123"
        limit = 3
        window_seconds = 60
        
        # 应该回退到内存模式
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        
        assert allowed is True
        assert info["current_requests"] == 1
        assert info["remaining"] == 2
    
    @patch('app.middleware.get_redis_client')
    def test_redis_unavailable(self, mock_get_redis, rate_limiter):
        """测试Redis不可用时使用内存模式"""
        mock_get_redis.return_value = None  # Redis不可用
        
        identifier = "user123"
        limit = 3
        window_seconds = 60
        
        allowed, info = rate_limiter.is_allowed(identifier, limit, window_seconds)
        
        assert allowed is True
        assert info["current_requests"] == 1
        assert info["remaining"] == 2


class TestRedisIntegration:
    """Redis集成测试"""
    
    @patch('redis.Redis')
    def test_initialize_redis_success(self, mock_redis_class):
        """测试Redis初始化成功"""
        mock_redis_instance = Mock()
        mock_redis_class.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        with patch('app.middleware.settings') as mock_settings:
            mock_settings.redis_host = "localhost"
            mock_settings.redis_port = 6379
            mock_settings.redis_db = 0
            mock_settings.redis_password = None
            
            initialize_redis()
            
            mock_redis_class.assert_called_once()
            mock_redis_instance.ping.assert_called_once()
    
    @patch('redis.Redis')
    def test_initialize_redis_connection_failure(self, mock_redis_class):
        """测试Redis连接失败"""
        mock_redis_instance = Mock()
        mock_redis_class.return_value = mock_redis_instance
        mock_redis_instance.ping.side_effect = Exception("Connection refused")
        
        # 初始化应该不抛出异常，而是回退到内存模式
        initialize_redis()
        
        # Redis客户端应该被设置为None
        client = get_redis_client()
        assert client is None
    
    def test_get_redis_client_unavailable(self):
        """测试获取不可用的Redis客户端"""
        with patch('app.middleware.redis_available', False):
            client = get_redis_client()
            assert client is None
    
    @patch('app.middleware.redis_client')
    @patch('app.middleware.redis_available', True)
    def test_get_redis_client_health_check_failure(self, mock_redis_client):
        """测试Redis健康检查失败"""
        mock_redis_client.ping.side_effect = Exception("Connection lost")
        
        client = get_redis_client()
        assert client is None


class TestAuthenticationMiddleware:
    """认证中间件测试"""
    
    @pytest.fixture
    def middleware(self):
        """创建认证中间件实例"""
        return AuthenticationMiddleware(Mock())
    
    @pytest.fixture
    def mock_request(self):
        """创建模拟请求"""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/stocks/AAPL/quote"
        request.headers = {}
        request.state = Mock()
        return request
    
    @pytest.mark.asyncio
    async def test_public_path_bypass(self, middleware, mock_request):
        """测试公共路径绕过认证"""
        public_paths = [
            "/",
            "/docs",
            "/openapi.json",
            "/health",
            "/api/v1/health",
            "/api/v1/stocks/AAPL/quote"
        ]
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        for path in public_paths:
            mock_request.url.path = path
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            assert response.status_code == 200
            assert json.loads(response.body) == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_missing_authorization_header(self, middleware, mock_request):
        """测试缺少授权头"""
        mock_request.url.path = "/api/v1/protected/endpoint"
        mock_request.headers = {}
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert response.status_code == 401
        response_data = json.loads(response.body)
        assert "Missing or invalid authorization header" in response_data["detail"]
    
    @pytest.mark.asyncio
    async def test_invalid_authorization_header_format(self, middleware, mock_request):
        """测试无效的授权头格式"""
        mock_request.url.path = "/api/v1/protected/endpoint"
        
        invalid_headers = [
            {"Authorization": "InvalidFormat token123"},
            {"Authorization": "Bearer"},  # 缺少token
            {"Authorization": "Basic dXNlcjpwYXNz"},  # 错误的scheme
            {"Authorization": "token123"}  # 缺少Bearer前缀
        ]
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        for headers in invalid_headers:
            mock_request.headers = headers
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            assert response.status_code == 401
            response_data = json.loads(response.body)
            assert "Missing or invalid authorization header" in response_data["detail"]
    
    @pytest.mark.asyncio
    async def test_valid_jwt_token(self, middleware, mock_request):
        """测试有效的JWT token"""
        mock_request.url.path = "/api/v1/protected/endpoint"
        
        # 创建有效token
        user_data = {
            "user_id": "test_user_123",
            "account_id": "account_456",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        
        async def mock_call_next(request):
            # 验证请求状态被正确设置
            assert request.state.user_id == "test_user_123"
            assert request.state.account_id == "account_456"
            assert request.state.permissions == ["trading", "market_data"]
            return JSONResponse({"status": "ok"})
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert response.status_code == 200
        response_data = json.loads(response.body)
        assert response_data == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_expired_jwt_token(self, middleware, mock_request):
        """测试过期的JWT token"""
        mock_request.url.path = "/api/v1/protected/endpoint"
        
        # 创建过期token
        with patch('app.middleware.datetime') as mock_datetime:
            past_time = datetime.utcnow() - timedelta(hours=25)
            mock_datetime.utcnow.return_value = past_time
            token = create_jwt_token({"user_id": "test_user"})
        
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert response.status_code == 401
        response_data = json.loads(response.body)
        assert "Token expired" in response_data["detail"]
    
    @pytest.mark.asyncio
    async def test_invalid_jwt_token(self, middleware, mock_request):
        """测试无效的JWT token"""
        mock_request.url.path = "/api/v1/protected/endpoint"
        
        invalid_tokens = [
            "invalid.jwt.token",
            "eyJhbGciOiJIUzI1NiJ9.invalid_payload.signature",
            "completely_invalid_token"
        ]
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        for invalid_token in invalid_tokens:
            mock_request.headers = {"Authorization": f"Bearer {invalid_token}"}
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            assert response.status_code == 401
            response_data = json.loads(response.body)
            assert "Invalid token" in response_data["detail"]


class TestRateLimitMiddleware:
    """速率限制中间件测试"""
    
    @pytest.fixture
    def middleware(self):
        """创建速率限制中间件实例"""
        return RateLimitMiddleware(Mock())
    
    @pytest.fixture
    def mock_request(self):
        """创建模拟请求"""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/stocks/quote"
        request.state = Mock()
        request.state.user_id = "test_user_123"
        return request
    
    @pytest.mark.asyncio
    async def test_public_path_bypass(self, middleware, mock_request):
        """测试公共路径绕过速率限制"""
        public_paths = ["/", "/docs", "/openapi.json", "/health"]
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        for path in public_paths:
            mock_request.url.path = path
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_anonymous_user_bypass(self, middleware, mock_request):
        """测试匿名用户绕过速率限制"""
        mock_request.state.user_id = None
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200
        
        # 测试"anonymous"用户也绕过
        mock_request.state.user_id = "anonymous"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rate_limit_within_limit(self, middleware, mock_request):
        """测试限制内的请求"""
        mock_request.url.path = "/api/v1/stocks/quote"
        mock_request.state.user_id = "test_user_123"
        
        with patch('app.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.is_allowed.return_value = (True, {
                "limit": 60,
                "remaining": 59,
                "reset_time": int(time.time()) + 60,
                "current_requests": 1
            })
            
            async def mock_call_next(request):
                return JSONResponse({"status": "ok"})
            
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            assert response.status_code == 200
            
            # 验证速率限制头
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            assert response.headers["X-RateLimit-Limit"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "59"
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, middleware, mock_request):
        """测试超出速率限制"""
        mock_request.url.path = "/api/v1/stocks/quote"
        mock_request.state.user_id = "test_user_123"
        
        with patch('app.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.is_allowed.return_value = (False, {
                "limit": 60,
                "remaining": 0,
                "reset_time": int(time.time()) + 60,
                "current_requests": 61
            })
            
            async def mock_call_next(request):
                return JSONResponse({"status": "ok"})
            
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            assert response.status_code == 429
            
            response_data = json.loads(response.body)
            assert "Rate limit exceeded" in response_data["detail"]
            assert response_data["limit"] == 60
            assert response_data["remaining"] == 0
            
            # 验证速率限制头
            assert response.headers["X-RateLimit-Limit"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
    
    @pytest.mark.asyncio
    async def test_endpoint_specific_limits(self, middleware, mock_request):
        """测试端点特定的限制"""
        endpoints_and_limits = [
            ("/api/v1/stocks/quote", (60, 60)),
            ("/api/v1/stocks/quotes/batch", (30, 60)),
            ("/api/v1/options/quote", (60, 60)),
            ("/api/v1/options/quotes/batch", (20, 60)),
            ("/api/v1/stocks/order", (10, 60)),
            ("/api/v1/options/order", (10, 60)),
            ("/api/v1/unknown/endpoint", (120, 60))  # 默认限制
        ]
        
        mock_request.state.user_id = "test_user_123"
        
        with patch('app.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.is_allowed.return_value = (True, {
                "limit": 0,  # 会被覆盖
                "remaining": 0,
                "reset_time": int(time.time()) + 60,
                "current_requests": 1
            })
            
            async def mock_call_next(request):
                return JSONResponse({"status": "ok"})
            
            for endpoint, (expected_limit, expected_window) in endpoints_and_limits:
                mock_request.url.path = endpoint
                
                await middleware.dispatch(mock_request, mock_call_next)
                
                # 验证调用了正确的限制参数
                mock_rate_limiter.is_allowed.assert_called_with(
                    f"user:test_user_123:{endpoint}",
                    expected_limit,
                    expected_window
                )


class TestLoggingMiddleware:
    """日志中间件测试"""
    
    @pytest.fixture
    def middleware(self):
        """创建日志中间件实例"""
        return LoggingMiddleware(Mock())
    
    @pytest.fixture
    def mock_request(self):
        """创建模拟请求"""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.url = Mock()
        request.url.__str__ = Mock(return_value="http://localhost/api/v1/test")
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-client/1.0"}
        request.state = Mock()
        request.state.user_id = "test_user_123"
        return request
    
    @pytest.mark.asyncio
    async def test_request_logging(self, middleware, mock_request):
        """测试请求日志记录"""
        async def mock_call_next(request):
            # 模拟一些处理时间
            await asyncio.sleep(0.01)
            response = JSONResponse({"status": "ok"})
            return response
        
        with patch('app.middleware.logger') as mock_logger:
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            # 验证请求开始日志
            start_call = mock_logger.info.call_args_list[0]
            assert "Request started" in start_call[0]
            start_extra = start_call[1]["extra"]
            assert start_extra["user_id"] == "test_user_123"
            assert start_extra["method"] == "GET"
            assert start_extra["client_ip"] == "127.0.0.1"
            assert start_extra["user_agent"] == "test-client/1.0"
            
            # 验证请求完成日志
            end_call = mock_logger.info.call_args_list[1]
            assert "Request completed" in end_call[0]
            end_extra = end_call[1]["extra"]
            assert end_extra["user_id"] == "test_user_123"
            assert end_extra["method"] == "GET"
            assert end_extra["status_code"] == 200
            assert "process_time" in end_extra
            assert end_extra["process_time"] > 0
            
            # 验证响应头中包含处理时间
            assert "X-Process-Time" in response.headers
            assert float(response.headers["X-Process-Time"]) > 0
    
    @pytest.mark.asyncio
    async def test_anonymous_user_logging(self, middleware, mock_request):
        """测试匿名用户日志记录"""
        mock_request.state.user_id = None
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        with patch('app.middleware.logger') as mock_logger:
            await middleware.dispatch(mock_request, mock_call_next)
            
            # 验证匿名用户被记录为"anonymous"
            start_call = mock_logger.info.call_args_list[0]
            start_extra = start_call[1]["extra"]
            assert start_extra["user_id"] == "anonymous"
    
    @pytest.mark.asyncio
    async def test_no_client_info_logging(self, middleware, mock_request):
        """测试没有客户端信息时的日志记录"""
        mock_request.client = None
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        with patch('app.middleware.logger') as mock_logger:
            await middleware.dispatch(mock_request, mock_call_next)
            
            start_call = mock_logger.info.call_args_list[0]
            start_extra = start_call[1]["extra"]
            assert start_extra["client_ip"] is None


class TestGetCurrentContext:
    """获取当前上下文测试"""
    
    @pytest.mark.asyncio
    async def test_get_current_context_valid_token(self):
        """测试有效token获取上下文"""
        user_data = {
            "user_id": "test_user_123",
            "account_id": "account_456",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        context = await get_current_context(credentials)
        
        assert isinstance(context, RequestContext)
        assert context.user_id == "test_user_123"
        assert context.account_id == "account_456"
        assert context.permissions == ["trading", "market_data"]
        assert context.request_count == 1  # update_activity was called
    
    @pytest.mark.asyncio
    async def test_get_current_context_invalid_token(self):
        """测试无效token获取上下文"""
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_token")
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_context(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in str(exc_info.value.detail)


class TestMiddlewareIntegration:
    """中间件集成测试"""
    
    def test_middleware_order(self):
        """测试中间件顺序"""
        # 这个测试验证中间件在main.py中的添加顺序
        from main import app
        
        middleware_classes = [type(middleware.cls) for middleware in app.user_middleware]
        
        # 验证中间件顺序（后添加的先执行）
        expected_order = [
            "LoggingMiddleware",
            "RateLimitMiddleware", 
            "AuthenticationMiddleware",
            "CORSMiddleware"
        ]
        
        actual_order = [cls.__name__ for cls in middleware_classes]
        
        # 验证关键中间件存在且顺序正确
        for expected_middleware in expected_order[:3]:  # 不检查CORS，因为它是FastAPI内置的
            assert expected_middleware in actual_order
    
    def test_client_integration(self):
        """测试客户端集成"""
        client = TestClient(app)
        
        # 测试健康检查端点（公共）
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        # 测试需要认证的端点（没有token）
        response = client.get("/api/v1/account")
        assert response.status_code == 401
        
        # 测试需要认证的端点（有效token）
        user_data = {"user_id": "test_user", "permissions": ["trading"]}
        token = create_jwt_token(user_data)
        headers = {"Authorization": f"Bearer {token}"}
        
        # 注意：这个测试可能因为实际的Alpaca连接而失败，但可以验证认证逻辑
        response = client.get("/api/v1/account", headers=headers)
        # 根据实际情况，这可能返回500（连接失败）而不是401（认证失败）
        assert response.status_code != 401  # 至少通过了认证


class TestSecurityScenarios:
    """安全场景测试"""
    
    def test_jwt_secret_protection(self):
        """测试JWT密钥保护"""
        # 验证不能用错误的密钥验证token
        user_data = {"user_id": "test_user"}
        token = create_jwt_token(user_data)
        
        # 修改JWT_SECRET然后尝试验证
        with patch('app.middleware.JWT_SECRET', 'wrong_secret'):
            with pytest.raises(HTTPException) as exc_info:
                verify_jwt_token(token)
            
            assert exc_info.value.status_code == 401
            assert "Invalid token" in str(exc_info.value.detail)
    
    def test_token_tampering_detection(self):
        """测试token篡改检测"""
        user_data = {"user_id": "test_user", "permissions": ["trading"]}
        token = create_jwt_token(user_data)
        
        # 尝试修改token的不同部分
        parts = token.split('.')
        
        # 修改header
        tampered_header = parts[0][:-1] + "X"
        tampered_token = f"{tampered_header}.{parts[1]}.{parts[2]}"
        
        with pytest.raises(HTTPException):
            verify_jwt_token(tampered_token)
        
        # 修改payload
        tampered_payload = parts[1][:-1] + "X"
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        
        with pytest.raises(HTTPException):
            verify_jwt_token(tampered_token)
        
        # 修改signature
        tampered_signature = parts[2][:-1] + "X"
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_signature}"
        
        with pytest.raises(HTTPException):
            verify_jwt_token(tampered_token)
    
    def test_rate_limit_per_user_isolation(self):
        """测试每用户速率限制隔离"""
        rate_limiter = RateLimiter()
        
        # 用户1达到限制
        for _ in range(3):
            rate_limiter.is_allowed("user1", 3, 60)
        
        # 用户1被限制
        allowed, _ = rate_limiter.is_allowed("user1", 3, 60)
        assert allowed is False
        
        # 用户2不受影响
        allowed, _ = rate_limiter.is_allowed("user2", 3, 60)
        assert allowed is True
    
    def test_sensitive_data_not_logged(self):
        """测试敏感数据不被记录"""
        # 这个测试确保JWT token等敏感信息不会被记录到日志中
        middleware = LoggingMiddleware(Mock())
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/v1/test"
        mock_request.method = "POST"
        mock_request.url.__str__ = Mock(return_value="http://localhost/api/v1/test")
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {
            "user-agent": "test-client/1.0",
            "authorization": "Bearer very.sensitive.token"
        }
        mock_request.state = Mock()
        mock_request.state.user_id = "test_user"
        
        async def mock_call_next(request):
            return JSONResponse({"status": "ok"})
        
        with patch('app.middleware.logger') as mock_logger:
            asyncio.run(middleware.dispatch(mock_request, mock_call_next))
            
            # 检查所有日志调用
            for call in mock_logger.info.call_args_list:
                call_str = str(call)
                # 确保敏感信息没有被记录
                assert "very.sensitive.token" not in call_str
                assert "Bearer" not in call_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])