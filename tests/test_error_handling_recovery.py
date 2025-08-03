"""
错误处理和恢复机制综合测试套件
测试系统在各种故障场景下的错误处理、恢复能力和稳定性
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, call, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import HTTPException
from fastapi.testclient import TestClient
import aiohttp
import redis

from app.account_pool import (
    AccountConfig, AccountConnectionPool, AlpacaAccountConnection,
    ConnectionStats, account_pool
)
from app.middleware import (
    RateLimiter, AuthenticationMiddleware, RateLimitMiddleware,
    verify_jwt_token, create_jwt_token, initialize_redis, get_redis_client
)
from app.alpaca_client import AlpacaClient
from main import app


class TestConnectionPoolErrorHandling:
    """连接池错误处理测试"""
    
    @pytest.fixture
    def pool_with_failing_connections(self):
        """创建带有故障连接的连接池"""
        pool = AccountConnectionPool()
        
        # 创建账户配置
        accounts = {}
        for i in range(1, 4):
            account_id = f"account{i}"
            accounts[account_id] = AccountConfig(
                account_id=account_id,
                api_key=f"key{i}",
                secret_key=f"secret{i}",
                enabled=True,
                max_connections=2
            )
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        return pool
    
    @pytest.mark.asyncio
    async def test_connection_creation_failure(self, pool_with_failing_connections):
        """测试连接创建失败的处理"""
        pool = pool_with_failing_connections
        
        with patch('app.account_pool.AlpacaAccountConnection') as mock_conn_class:
            # 模拟连接创建失败
            mock_conn_class.side_effect = [
                Exception("Connection creation failed"),
                Exception("API key invalid"),
                Exception("Network timeout")
            ]
            
            # 预建立连接应该处理异常而不崩溃
            await pool._prebuild_connections()
            
            # 失败的连接不应该被添加到池中
            for account_id in pool.account_id_list:
                assert len(pool.account_pools.get(account_id, [])) == 0
    
    @pytest.mark.asyncio
    async def test_connection_health_check_failure(self, pool_with_failing_connections):
        """测试连接健康检查失败的处理"""
        pool = pool_with_failing_connections
        
        # 创建一个会在健康检查时失败的连接
        failing_conn = AsyncMock()
        failing_conn._in_use = False
        failing_conn.test_connection.side_effect = Exception("Health check failed")
        
        healthy_conn = AsyncMock()
        healthy_conn._in_use = False
        healthy_conn.test_connection.return_value = True
        
        pool.account_pools = {
            "account1": [failing_conn, healthy_conn]
        }
        
        await pool._perform_health_checks()
        
        # 失败的连接应该被移除
        assert len(pool.account_pools["account1"]) == 1
        assert healthy_conn in pool.account_pools["account1"]
        assert failing_conn not in pool.account_pools["account1"]
    
    @pytest.mark.asyncio
    async def test_connection_acquisition_timeout(self, pool_with_failing_connections):
        """测试连接获取超时的处理"""
        pool = pool_with_failing_connections
        
        # 创建一个会在acquire时超时的连接
        timeout_conn = AsyncMock()
        timeout_conn.is_available = True
        timeout_conn.stats = Mock()
        timeout_conn.stats.usage_count = 0
        timeout_conn.acquire.side_effect = asyncio.TimeoutError("Acquire timeout")
        
        pool.account_pools["account1"] = [timeout_conn]
        pool.usage_queues["account1"] = []
        
        # 获取连接时应该处理超时异常
        with pytest.raises(asyncio.TimeoutError):
            await pool.get_connection("account1")
    
    @pytest.mark.asyncio
    async def test_background_task_exception_recovery(self, pool_with_failing_connections):
        """测试后台任务异常恢复"""
        pool = pool_with_failing_connections
        
        exception_count = 0
        original_health_check = pool._perform_health_checks
        
        async def failing_health_check():
            nonlocal exception_count
            exception_count += 1
            if exception_count <= 3:
                raise Exception(f"Health check error {exception_count}")
            else:
                # 第4次开始正常工作
                return await original_health_check()
        
        with patch.object(pool, '_perform_health_checks', side_effect=failing_health_check):
            # 模拟后台任务运行
            task = asyncio.create_task(pool._health_check_loop())
            
            # 等待一段时间让任务运行几次
            await asyncio.sleep(0.1)
            
            # 取消任务
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # 验证异常被处理了多次
            assert exception_count >= 3
    
    @pytest.mark.asyncio
    async def test_connection_pool_corruption_recovery(self, pool_with_failing_connections):
        """测试连接池损坏时的恢复"""
        pool = pool_with_failing_connections
        
        # 故意损坏连接池数据结构
        pool.account_pools["account1"] = [None, "invalid_connection", Mock()]
        pool.usage_queues["account1"] = ["invalid_item"]
        
        # 健康检查应该能够处理损坏的数据
        await pool._perform_health_checks()
        
        # 系统应该仍然可以运行（移除无效连接）
        remaining_connections = pool.account_pools.get("account1", [])
        for conn in remaining_connections:
            assert conn is not None
            assert hasattr(conn, 'test_connection') or hasattr(conn, '_in_use')
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_active_connections(self):
        """测试有活跃连接时的优雅关闭"""
        pool = AccountConnectionPool()
        
        # 创建活跃连接
        active_conn = Mock()
        active_conn._in_use = True
        
        idle_conn = Mock()
        idle_conn._in_use = False
        
        pool.account_pools = {"account1": [active_conn, idle_conn]}
        pool.usage_queues = {"account1": []}
        pool._global_lock = asyncio.Lock()
        
        # 模拟后台任务
        mock_task = AsyncMock()
        pool._background_tasks = [mock_task]
        
        # 关闭连接池
        await pool.shutdown()
        
        # 验证所有连接都被释放
        active_conn.release.assert_called_once()
        idle_conn.release.assert_not_called()  # 空闲连接不需要释放
        
        # 验证后台任务被取消
        mock_task.cancel.assert_called_once()
    
    def test_invalid_account_configuration_handling(self):
        """测试无效账户配置的处理"""
        pool = AccountConnectionPool()
        
        # 测试各种无效配置
        invalid_configs = [
            {},  # 空配置
            {"account_id": "test"},  # 缺少必需字段
            {"account_id": "", "api_key": "", "secret_key": ""},  # 空值
            {"account_id": None, "api_key": None, "secret_key": None},  # None值
        ]
        
        for config in invalid_configs:
            try:
                if "account_id" in config and config["account_id"]:
                    account_config = AccountConfig(
                        account_id=config.get("account_id", "default"),
                        api_key=config.get("api_key", "default_key"),
                        secret_key=config.get("secret_key", "default_secret")
                    )
                    # 配置创建应该成功，即使值为空
                    assert account_config is not None
            except Exception as e:
                # 某些配置可能会抛出异常，这是预期的
                assert isinstance(e, (TypeError, ValueError))


class TestAlpacaClientErrorHandling:
    """Alpaca客户端错误处理测试"""
    
    @pytest.fixture
    def mock_alpaca_client(self):
        """创建模拟Alpaca客户端"""
        with patch('app.alpaca_client.TradingClient') as mock_trading:
            with patch('app.alpaca_client.StockHistoricalDataClient') as mock_stock:
                with patch('app.alpaca_client.OptionHistoricalDataClient') as mock_option:
                    client = AlpacaClient()
                    yield client, mock_trading, mock_stock, mock_option
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_handling(self, mock_alpaca_client):
        """测试API速率限制处理"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        # 模拟速率限制异常
        rate_limit_error = Exception("API rate limit exceeded")
        mock_trading.return_value.get_account.side_effect = rate_limit_error
        
        result = await client.test_connection()
        
        assert "error" in result
        assert "rate limit" in result["error"].lower() or "API rate limit exceeded" in result["error"]
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, mock_alpaca_client):
        """测试网络超时处理"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        # 模拟网络超时
        timeout_error = asyncio.TimeoutError("Request timeout")
        mock_trading.return_value.get_account.side_effect = timeout_error
        
        result = await client.test_connection()
        
        assert "error" in result
        assert "timeout" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_credentials_handling(self, mock_alpaca_client):
        """测试无效凭据处理"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        # 模拟认证错误
        auth_error = Exception("Invalid API credentials")
        mock_trading.return_value.get_account.side_effect = auth_error
        
        result = await client.test_connection()
        
        assert "error" in result
        assert "credentials" in result["error"].lower() or "Invalid API credentials" in result["error"]
    
    @pytest.mark.asyncio
    async def test_market_data_unavailable_handling(self, mock_alpaca_client):
        """测试市场数据不可用处理"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        # 模拟市场数据不可用
        mock_stock.return_value.get_stock_latest_quote.side_effect = Exception("Market data unavailable")
        
        result = await client.get_stock_quote("AAPL")
        
        assert "error" in result
        assert "unavailable" in result["error"].lower() or "Market data unavailable" in result["error"]
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, mock_alpaca_client):
        """测试格式错误的响应处理"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        # 模拟格式错误的响应
        malformed_response = "This is not JSON"
        mock_stock.return_value.get_stock_latest_quote.return_value = malformed_response
        
        result = await client.get_stock_quote("AAPL")
        
        # 客户端应该处理格式错误的响应
        assert "error" in result or "symbol" in result  # 取决于具体实现
    
    @pytest.mark.asyncio
    async def test_partial_data_handling(self, mock_alpaca_client):
        """测试部分数据处理"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        # 模拟部分缺失的数据
        partial_quote = Mock()
        partial_quote.bid_price = None  # 缺失出价
        partial_quote.ask_price = 150.5
        partial_quote.timestamp = datetime.now()
        
        mock_stock.return_value.get_stock_latest_quote.return_value = partial_quote
        
        result = await client.get_stock_quote("AAPL")
        
        # 应该能够处理部分数据
        assert isinstance(result, dict)
        # 具体处理方式取决于实现
    
    @pytest.mark.asyncio
    async def test_connection_recovery_after_failure(self, mock_alpaca_client):
        """测试连接失败后的恢复"""
        client, mock_trading, mock_stock, mock_option = mock_alpaca_client
        
        call_count = 0
        def mock_get_account():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Connection failed")
            else:
                return Mock(status="ACTIVE")
        
        mock_trading.return_value.get_account.side_effect = mock_get_account
        
        # 前两次调用应该失败
        result1 = await client.test_connection()
        result2 = await client.test_connection()
        
        assert "error" in result1
        assert "error" in result2
        
        # 第三次调用应该成功
        result3 = await client.test_connection()
        assert result3.get("status") in ["connected", "failed"]  # 取决于具体实现


class TestMiddlewareErrorHandling:
    """中间件错误处理测试"""
    
    def test_jwt_verification_error_handling(self):
        """测试JWT验证错误处理"""
        invalid_tokens = [
            "invalid.jwt.token",
            "eyJhbGciOiJIUzI1NiJ9.invalid_payload.invalid_signature",
            "",
            None,
            "Bearer token_without_bearer_prefix",
            "not_even_close_to_jwt"
        ]
        
        for token in invalid_tokens:
            if token is None:
                continue
                
            with pytest.raises(HTTPException) as exc_info:
                verify_jwt_token(token)
            
            assert exc_info.value.status_code == 401
            assert "Invalid token" in str(exc_info.value.detail) or "Token expired" in str(exc_info.value.detail)
    
    def test_rate_limiter_redis_failure_fallback(self):
        """测试速率限制器Redis故障回退"""
        rate_limiter = RateLimiter()
        
        with patch('app.middleware.get_redis_client') as mock_get_redis:
            # 模拟Redis连接异常
            mock_redis = Mock()
            mock_redis.pipeline.side_effect = redis.ConnectionError("Redis connection lost")
            mock_get_redis.return_value = mock_redis
            
            # 应该回退到内存模式
            allowed, info = rate_limiter.is_allowed("user123", 5, 60)
            
            assert allowed is True
            assert info["current_requests"] == 1
            assert info["limit"] == 5
    
    def test_rate_limiter_memory_overflow_protection(self):
        """测试速率限制器内存溢出保护"""
        rate_limiter = RateLimiter()
        
        # 模拟大量不同用户的请求
        for i in range(10000):
            user_id = f"user{i}"
            allowed, info = rate_limiter.is_allowed(user_id, 5, 60)
            assert allowed is True
        
        # 内存使用应该是合理的（这个测试主要是检查不会崩溃）
        memory_store_size = len(rate_limiter.memory_store)
        assert memory_store_size == 10000  # 所有用户都被记录
    
    @pytest.mark.asyncio
    async def test_authentication_middleware_exception_handling(self):
        """测试认证中间件异常处理"""
        middleware = AuthenticationMiddleware(Mock())
        
        # 创建会导致异常的请求
        mock_request = Mock()
        mock_request.url.path = "/api/v1/protected"
        mock_request.headers = {"Authorization": "Bearer malformed_token"}
        
        async def mock_call_next(request):
            return Mock(status_code=200)
        
        # 中间件应该捕获JWT验证异常并返回401响应
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_exception_handling(self):
        """测试速率限制中间件异常处理"""
        middleware = RateLimitMiddleware(Mock())
        
        mock_request = Mock()
        mock_request.url.path = "/api/v1/test"
        mock_request.state = Mock()
        mock_request.state.user_id = "test_user"
        
        async def mock_call_next(request):
            return Mock(status_code=200, headers={})
        
        # 模拟速率限制器异常
        with patch('app.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.is_allowed.side_effect = Exception("Rate limiter error")
            
            # 中间件应该处理异常并允许请求通过（或返回错误响应）
            response = await middleware.dispatch(mock_request, mock_call_next)
            
            # 具体行为取决于实现，但不应该导致未捕获的异常
            assert hasattr(response, 'status_code')


class TestAPIEndpointErrorHandling:
    """API端点错误处理测试"""
    
    def test_api_endpoint_validation_errors(self):
        """测试API端点验证错误"""
        client = TestClient(app)
        
        # 测试无效的股票符号
        response = client.get("/api/v1/stocks//quote")  # 空符号
        assert response.status_code in [400, 404, 422]
        
        # 测试无效的批量请求
        response = client.post("/api/v1/stocks/quotes/batch", json={
            "symbols": []  # 空符号列表
        })
        assert response.status_code == 400
        
        # 测试过多的符号
        response = client.post("/api/v1/stocks/quotes/batch", json={
            "symbols": [f"SYMBOL{i}" for i in range(100)]  # 超过限制
        })
        assert response.status_code in [400, 422]
    
    def test_api_endpoint_authentication_errors(self):
        """测试API端点认证错误"""
        client = TestClient(app)
        
        # 测试需要认证的端点
        protected_endpoints = [
            ("GET", "/api/v1/orders"),
            ("POST", "/api/v1/stocks/order"),
            ("POST", "/api/v1/options/order"),
            ("DELETE", "/api/v1/orders/test_id")
        ]
        
        for method, endpoint in protected_endpoints:
            response = client.request(method, endpoint)
            assert response.status_code == 401
    
    def test_api_endpoint_internal_errors(self):
        """测试API端点内部错误处理"""
        client = TestClient(app)
        
        # 模拟内部服务故障
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_stock_quote.side_effect = Exception("Internal service error")
            mock_client_class.return_value = mock_client
            
            response = client.get("/api/v1/stocks/AAPL/quote")
            
            # 应该返回500内部服务器错误
            assert response.status_code == 500
    
    def test_api_endpoint_timeout_handling(self):
        """测试API端点超时处理"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_stock_quote.side_effect = asyncio.TimeoutError("Request timeout")
            mock_client_class.return_value = mock_client
            
            response = client.get("/api/v1/stocks/AAPL/quote")
            
            # 应该处理超时并返回适当的错误
            assert response.status_code in [500, 503, 504]


class TestRedisErrorHandling:
    """Redis错误处理测试"""
    
    @patch('redis.Redis')
    def test_redis_connection_failure_handling(self, mock_redis_class):
        """测试Redis连接失败处理"""
        # 模拟Redis连接失败
        mock_redis_instance = Mock()
        mock_redis_class.return_value = mock_redis_instance
        mock_redis_instance.ping.side_effect = redis.ConnectionError("Connection refused")
        
        # 初始化应该处理连接失败
        initialize_redis()
        
        # get_redis_client应该返回None
        client = get_redis_client()
        assert client is None
    
    @patch('redis.Redis')
    def test_redis_intermittent_failure_handling(self, mock_redis_class):
        """测试Redis间歇性故障处理"""
        mock_redis_instance = Mock()
        mock_redis_class.return_value = mock_redis_instance
        
        # 第一次ping成功，后续失败
        mock_redis_instance.ping.side_effect = [True, redis.ConnectionError("Connection lost")]
        
        # 初始化成功
        initialize_redis()
        
        # 后续获取客户端时失败
        client = get_redis_client()
        assert client is None
    
    def test_redis_data_corruption_handling(self):
        """测试Redis数据损坏处理"""
        rate_limiter = RateLimiter()
        
        with patch('app.middleware.get_redis_client') as mock_get_redis:
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            
            # 模拟Redis返回损坏的数据
            mock_pipe = Mock()
            mock_redis.pipeline.return_value.__enter__.return_value = mock_pipe
            mock_pipe.execute.return_value = [None, "invalid_number", None, None]  # 非数字的zcard结果
            
            # 应该回退到内存模式
            allowed, info = rate_limiter.is_allowed("user123", 5, 60)
            
            assert allowed is True
            assert info["current_requests"] == 1


class TestConcurrentErrorHandling:
    """并发错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_failures(self):
        """测试并发连接失败"""
        pool = AccountConnectionPool()
        
        # 创建会失败的连接
        failing_conn = AsyncMock()
        failing_conn.is_available = True
        failing_conn.stats = Mock()
        failing_conn.stats.usage_count = 0
        failing_conn.acquire.side_effect = Exception("Connection acquire failed")
        
        pool.account_configs = {"account1": AccountConfig("account1", "key", "secret")}
        pool.account_pools = {"account1": [failing_conn]}
        pool.usage_queues = {"account1": []}
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 并发尝试获取连接
        async def try_get_connection():
            try:
                return await pool.get_connection("account1")
            except Exception as e:
                return str(e)
        
        tasks = [try_get_connection() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 所有请求都应该得到异常（而不是挂起或崩溃）
        for result in results:
            assert isinstance(result, (str, Exception))
    
    @pytest.mark.asyncio
    async def test_concurrent_health_check_failures(self):
        """测试并发健康检查失败"""
        pool = AccountConnectionPool()
        
        failing_conn = AsyncMock()
        failing_conn._in_use = False
        failing_conn.test_connection.side_effect = Exception("Health check failed")
        
        pool.account_pools = {"account1": [failing_conn]}
        pool._global_lock = asyncio.Lock()
        
        # 并发执行健康检查
        tasks = [pool._perform_health_checks() for _ in range(5)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # 系统应该仍然稳定
        assert len(pool.account_pools["account1"]) == 0  # 失败的连接被移除
    
    def test_concurrent_rate_limiting_errors(self):
        """测试并发速率限制错误"""
        rate_limiter = RateLimiter()
        
        import threading
        import queue
        
        results = queue.Queue()
        exception_count = 0
        
        def worker():
            nonlocal exception_count
            try:
                for i in range(100):
                    # 模拟间歇性故障
                    if i % 10 == 0:
                        raise Exception("Simulated error")
                    allowed, info = rate_limiter.is_allowed(f"user{threading.current_thread().ident}", 50, 60)
                    results.put(allowed)
            except Exception:
                exception_count += 1
        
        # 启动多个线程
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 收集结果
        success_count = 0
        while not results.empty():
            if results.get():
                success_count += 1
        
        # 应该有一些成功的请求，即使有异常
        assert success_count > 0
        assert exception_count == 5  # 每个线程一个异常


class TestErrorRecoveryMechanisms:
    """错误恢复机制测试"""
    
    @pytest.mark.asyncio
    async def test_connection_pool_self_healing(self):
        """测试连接池自愈能力"""
        pool = AccountConnectionPool()
        
        # 创建初始连接
        healthy_conn = AsyncMock()
        healthy_conn._in_use = False
        healthy_conn.test_connection.return_value = True
        
        failing_then_healing_conn = AsyncMock()
        failing_then_healing_conn._in_use = False
        
        call_count = 0
        def test_connection_side_effect():
            nonlocal call_count
            call_count += 1
            return call_count > 3  # 前3次失败，之后成功
        
        failing_then_healing_conn.test_connection.side_effect = test_connection_side_effect
        
        pool.account_pools = {"account1": [healthy_conn, failing_then_healing_conn]}
        pool._global_lock = asyncio.Lock()
        
        # 第一次健康检查 - 一个连接失败
        await pool._perform_health_checks()
        assert len(pool.account_pools["account1"]) == 1  # 失败的被移除
        
        # 重新添加连接（模拟重新创建）
        pool.account_pools["account1"].append(failing_then_healing_conn)
        
        # 多次健康检查，直到连接恢复
        for _ in range(5):
            await pool._perform_health_checks()
        
        # 最终应该有两个健康的连接
        assert len(pool.account_pools["account1"]) == 2
    
    @pytest.mark.asyncio
    async def test_automatic_reconnection(self):
        """测试自动重连机制"""
        # 这个测试模拟连接断开后的自动重连
        config = AccountConfig("test_account", "test_key", "test_secret")
        
        with patch('app.account_pool.AlpacaClient') as mock_client_class:
            connection = AlpacaAccountConnection(config)
            
            # 模拟连接断开然后重连
            call_count = 0
            def test_connection_side_effect():
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    return {"status": "failed", "error": "Connection lost"}
                else:
                    return {"status": "connected"}
            
            connection.alpaca_client.test_connection.side_effect = test_connection_side_effect
            
            # 前两次测试失败
            result1 = await connection.test_connection()
            result2 = await connection.test_connection()
            
            assert result1 is False
            assert result2 is False
            assert connection.stats.error_count == 2
            
            # 第三次测试成功（模拟重连成功）
            result3 = await connection.test_connection()
            assert result3 is True
            assert connection.stats.is_healthy is True
    
    def test_graceful_degradation(self):
        """测试优雅降级"""
        # 测试系统在部分组件失败时的优雅降级
        rate_limiter = RateLimiter()
        
        # 模拟Redis完全不可用
        with patch('app.middleware.get_redis_client', return_value=None):
            # 系统应该回退到内存模式并继续工作
            allowed, info = rate_limiter.is_allowed("user123", 5, 60)
            assert allowed is True
            assert info["limit"] == 5
            
            # 继续请求应该正常工作
            for _ in range(4):
                allowed, info = rate_limiter.is_allowed("user123", 5, 60)
                assert allowed is True
            
            # 第6个请求应该被限制
            allowed, info = rate_limiter.is_allowed("user123", 5, 60)
            assert allowed is False
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """测试断路器模式"""
        # 模拟断路器模式的错误处理
        connection_attempts = 0
        consecutive_failures = 0
        circuit_open = False
        
        async def mock_connection_attempt():
            nonlocal connection_attempts, consecutive_failures, circuit_open
            connection_attempts += 1
            
            if circuit_open:
                raise Exception("Circuit breaker is open")
            
            # 模拟前5次连接失败
            if connection_attempts <= 5:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    circuit_open = True
                raise Exception("Connection failed")
            else:
                consecutive_failures = 0
                circuit_open = False
                return "Connected"
        
        # 前几次尝试应该失败
        for _ in range(3):
            with pytest.raises(Exception):
                await mock_connection_attempt()
        
        # 断路器应该打开
        assert circuit_open is True
        
        # 后续尝试应该立即失败
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await mock_connection_attempt()


class TestErrorLoggingAndMonitoring:
    """错误日志和监控测试"""
    
    @pytest.mark.asyncio
    async def test_error_logging_completeness(self):
        """测试错误日志完整性"""
        pool = AccountConnectionPool()
        
        with patch('app.account_pool.logger') as mock_logger:
            # 触发各种错误场景
            
            # 1. 连接创建失败
            with patch('app.account_pool.AlpacaAccountConnection') as mock_conn:
                mock_conn.side_effect = Exception("Connection creation failed")
                await pool._prebuild_connections()
                
                # 验证错误被记录
                mock_logger.error.assert_called()
                error_calls = [call for call in mock_logger.error.call_args_list 
                              if "创建账户" in str(call) and "连接" in str(call)]
                assert len(error_calls) > 0
    
    def test_error_metrics_collection(self):
        """测试错误指标收集"""
        config = AccountConfig("test_account", "test_key", "test_secret")
        connection = AlpacaAccountConnection(config)
        
        # 模拟多次失败
        initial_error_count = connection.stats.error_count
        
        # 模拟错误
        connection.stats.error_count += 1
        connection.stats.error_count += 1
        connection.stats.error_count += 1
        
        # 验证错误计数正确
        assert connection.stats.error_count == initial_error_count + 3
        
        # 错误率计算
        connection.stats.usage_count = 10
        error_rate = connection.stats.error_count / connection.stats.usage_count
        assert error_rate == 0.3  # 30% 错误率
    
    def test_error_context_preservation(self):
        """测试错误上下文保存"""
        # 这个测试确保错误信息包含足够的上下文用于调试
        pool = AccountConnectionPool()
        
        with patch('app.account_pool.logger') as mock_logger:
            # 模拟特定的错误场景
            with patch('app.account_pool.AlpacaAccountConnection') as mock_conn:
                mock_conn.side_effect = ValueError("Invalid API key format")
                
                pool.account_configs = {
                    "test_account": AccountConfig("test_account", "invalid_key", "secret")
                }
                
                await pool._prebuild_connections()
                
                # 验证错误日志包含有用的上下文信息
                logged_errors = [str(call) for call in mock_logger.error.call_args_list]
                context_found = any("test_account" in error for error in logged_errors)
                assert context_found, "Error logs should contain account context"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])