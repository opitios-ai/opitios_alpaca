"""
全面的账户连接池单元测试
测试连接池管理、账户路由、负载均衡和健康检查功能
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.account_pool import (
    AccountConfig, AccountConnectionPool, AlpacaAccountConnection,
    ConnectionStats, account_pool
)


class TestAccountConfig:
    """账户配置测试"""
    
    def test_account_config_creation(self):
        """测试账户配置创建"""
        config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True,
            account_name="Test Account",
            region="us",
            tier="premium",
            max_connections=5,
            enabled=True
        )
        
        assert config.account_id == "test_account"
        assert config.api_key == "test_key"
        assert config.secret_key == "test_secret"
        assert config.paper_trading is True
        assert config.account_name == "Test Account"
        assert config.region == "us"
        assert config.tier == "premium"
        assert config.max_connections == 5
        assert config.enabled is True
    
    def test_account_config_defaults(self):
        """测试账户配置默认值"""
        config = AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret"
        )
        
        assert config.paper_trading is True
        assert config.account_name is None
        assert config.region == "us"
        assert config.tier == "standard"
        assert config.max_connections == 3
        assert config.enabled is True


class TestConnectionStats:
    """连接统计测试"""
    
    def test_connection_stats_creation(self):
        """测试连接统计创建"""
        created_time = datetime.utcnow()
        stats = ConnectionStats(
            created_at=created_time,
            last_used=created_time,
            usage_count=10,
            error_count=2,
            avg_response_time=0.15,
            is_healthy=True,
            last_health_check=created_time
        )
        
        assert stats.created_at == created_time
        assert stats.last_used == created_time
        assert stats.usage_count == 10
        assert stats.error_count == 2
        assert stats.avg_response_time == 0.15
        assert stats.is_healthy is True
        assert stats.last_health_check == created_time
    
    def test_connection_stats_defaults(self):
        """测试连接统计默认值"""
        created_time = datetime.utcnow()
        stats = ConnectionStats(
            created_at=created_time,
            last_used=created_time
        )
        
        assert stats.usage_count == 0
        assert stats.error_count == 0
        assert stats.avg_response_time == 0.0
        assert stats.is_healthy is True
        assert stats.last_health_check is None


class TestAlpacaAccountConnection:
    """单个账户连接测试"""
    
    @pytest.fixture
    def mock_account_config(self):
        """模拟账户配置"""
        return AccountConfig(
            account_id="test_account",
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
    
    @pytest.fixture
    def mock_alpaca_client(self):
        """模拟Alpaca客户端"""
        with patch('app.account_pool.AlpacaClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            yield mock_instance
    
    def test_connection_creation(self, mock_account_config, mock_alpaca_client):
        """测试连接创建"""
        connection = AlpacaAccountConnection(mock_account_config)
        
        assert connection.account_config == mock_account_config
        assert connection.connection_id.startswith("test_account_")
        assert connection.alpaca_client is not None
        assert connection.stats is not None
        assert connection._in_use is False
        assert isinstance(connection.stats, ConnectionStats)
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_account_config, mock_alpaca_client):
        """测试连接健康检查成功"""
        mock_alpaca_client.test_connection.return_value = {"status": "connected"}
        
        connection = AlpacaAccountConnection(mock_account_config)
        connection.alpaca_client = mock_alpaca_client
        
        result = await connection.test_connection()
        
        assert result is True
        assert connection.stats.is_healthy is True
        assert connection.stats.usage_count == 1
        assert connection.stats.error_count == 0
        assert connection.stats.avg_response_time > 0
        assert connection.stats.last_health_check is not None
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, mock_account_config, mock_alpaca_client):
        """测试连接健康检查失败"""
        mock_alpaca_client.test_connection.return_value = {"status": "failed"}
        
        connection = AlpacaAccountConnection(mock_account_config)
        connection.alpaca_client = mock_alpaca_client
        
        result = await connection.test_connection()
        
        assert result is False
        assert connection.stats.is_healthy is False
        assert connection.stats.error_count == 1
    
    @pytest.mark.asyncio
    async def test_test_connection_exception(self, mock_account_config, mock_alpaca_client):
        """测试连接健康检查异常"""
        mock_alpaca_client.test_connection.side_effect = Exception("Connection failed")
        
        connection = AlpacaAccountConnection(mock_account_config)
        connection.alpaca_client = mock_alpaca_client
        
        result = await connection.test_connection()
        
        assert result is False
        assert connection.stats.is_healthy is False
        assert connection.stats.error_count == 1
    
    @pytest.mark.asyncio
    async def test_acquire_and_release(self, mock_account_config, mock_alpaca_client):
        """测试连接获取和释放"""
        connection = AlpacaAccountConnection(mock_account_config)
        
        # 测试获取连接
        assert connection.is_available is True
        await connection.acquire()
        assert connection._in_use is True
        assert connection.is_available is False
        
        # 测试释放连接
        connection.release()
        assert connection._in_use is False
    
    def test_age_calculation(self, mock_account_config, mock_alpaca_client):
        """测试连接年龄计算"""
        connection = AlpacaAccountConnection(mock_account_config)
        
        # 设置一个过去的创建时间
        connection.stats.created_at = datetime.utcnow() - timedelta(minutes=5)
        
        age = connection.age_minutes
        assert age >= 5.0
        assert age < 6.0  # 允许一定的时间误差


class TestAccountConnectionPool:
    """账户连接池测试"""
    
    @pytest.fixture
    def mock_settings(self):
        """模拟设置"""
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {
                "account1": {
                    "api_key": "key1",
                    "secret_key": "secret1",
                    "enabled": True,
                    "max_connections": 2
                },
                "account2": {
                    "api_key": "key2",
                    "secret_key": "secret2",
                    "enabled": True,
                    "max_connections": 3
                },
                "account3": {
                    "api_key": "key3",
                    "secret_key": "secret3",
                    "enabled": False,
                    "max_connections": 2
                }
            }
            mock_settings.alpaca_api_key = "default_key"
            mock_settings.alpaca_secret_key = "default_secret"
            mock_settings.alpaca_paper_trading = True
            yield mock_settings
    
    @pytest.fixture
    def pool(self):
        """创建测试连接池"""
        return AccountConnectionPool(
            max_connections_per_account=2,
            health_check_interval_seconds=60
        )
    
    def test_pool_creation(self, pool):
        """测试连接池创建"""
        assert pool.max_connections_per_account == 2
        assert pool.health_check_interval_seconds == 60
        assert pool.account_configs == {}
        assert pool.account_pools == {}
        assert pool.usage_queues == {}
        assert pool.account_id_list == []
        assert pool._initialized is False
    
    @pytest.mark.asyncio
    async def test_pool_initialization_with_multiple_accounts(self, pool, mock_settings):
        """测试多账户连接池初始化"""
        with patch.object(pool, '_prebuild_connections') as mock_prebuild:
            mock_prebuild.return_value = None
            
            await pool._load_account_configs()
            
            # 验证账户配置加载
            assert len(pool.account_configs) == 2  # account3被禁用
            assert "account1" in pool.account_configs
            assert "account2" in pool.account_configs
            assert "account3" not in pool.account_configs
            
            # 验证账户配置内容
            config1 = pool.account_configs["account1"]
            assert config1.api_key == "key1"
            assert config1.secret_key == "secret1"
            assert config1.max_connections == 2
            
            config2 = pool.account_configs["account2"]
            assert config2.api_key == "key2"
            assert config2.secret_key == "secret2"
            assert config2.max_connections == 3
    
    @pytest.mark.asyncio
    async def test_pool_initialization_with_default_account(self, pool):
        """测试默认单账户连接池初始化"""
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = {}
            mock_settings.alpaca_api_key = "default_key"
            mock_settings.alpaca_secret_key = "default_secret"
            mock_settings.alpaca_paper_trading = True
            
            with patch.object(pool, '_prebuild_connections') as mock_prebuild:
                mock_prebuild.return_value = None
                
                await pool._load_account_configs()
                
                # 验证默认账户配置
                assert len(pool.account_configs) == 1
                assert "default_account" in pool.account_configs
                
                default_config = pool.account_configs["default_account"]
                assert default_config.api_key == "default_key"
                assert default_config.secret_key == "default_secret"
    
    @pytest.mark.asyncio
    async def test_prebuild_connections(self, pool, mock_settings):
        """测试预建立连接"""
        # 先加载配置
        await pool._load_account_configs()
        
        # 模拟连接测试成功
        with patch('app.account_pool.AlpacaAccountConnection') as mock_conn_class:
            mock_connections = []
            
            def create_mock_connection(config):
                mock_conn = AsyncMock()
                mock_conn.test_connection.return_value = True
                mock_conn.account_config = config
                mock_connections.append(mock_conn)
                return mock_conn
            
            mock_conn_class.side_effect = create_mock_connection
            
            await pool._prebuild_connections()
            
            # 验证连接创建
            assert len(pool.account_pools) == 2
            assert len(pool.usage_queues) == 2
            
            # 验证account1的连接
            assert len(pool.account_pools["account1"]) == 2
            assert len(pool.usage_queues["account1"]) == 0
            
            # 验证account2的连接
            assert len(pool.account_pools["account2"]) == 3
            assert len(pool.usage_queues["account2"]) == 0
    
    def test_routing_strategies(self, pool):
        """测试路由策略"""
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # 测试轮询路由
        account1 = pool.get_account_by_routing(strategy="round_robin")
        assert account1 in pool.account_id_list
        
        # 测试哈希路由
        account2 = pool.get_account_by_routing("AAPL", strategy="hash")
        assert account2 in pool.account_id_list
        
        # 使用相同的routing_key应该返回相同的账户
        account3 = pool.get_account_by_routing("AAPL", strategy="hash")
        assert account2 == account3
        
        # 测试随机路由
        account4 = pool.get_account_by_routing(strategy="random")
        assert account4 in pool.account_id_list
        
        # 测试最少负载路由
        with patch.object(pool, 'account_pools') as mock_pools:
            # 模拟不同负载的连接
            mock_conn1 = Mock()
            mock_conn1.stats.usage_count = 10
            mock_conn2 = Mock()
            mock_conn2.stats.usage_count = 5
            mock_conn3 = Mock()
            mock_conn3.stats.usage_count = 15
            
            mock_pools = {
                "account1": [mock_conn1],
                "account2": [mock_conn2],
                "account3": [mock_conn3]
            }
            pool.account_pools = mock_pools
            
            account5 = pool.get_account_by_routing(strategy="least_loaded")
            assert account5 == "account2"  # 最少使用的账户
    
    def test_routing_edge_cases(self, pool):
        """测试路由边缘情况"""
        # 空账户列表
        pool.account_id_list = []
        result = pool.get_account_by_routing()
        assert result is None
        
        # 单个账户
        pool.account_id_list = ["single_account"]
        result = pool.get_account_by_routing(strategy="round_robin")
        assert result == "single_account"
        
        # 无效策略，应该回退到默认
        pool.account_id_list = ["account1", "account2"]
        result = pool.get_account_by_routing(strategy="invalid_strategy")
        assert result == "account1"
    
    @pytest.mark.asyncio
    async def test_get_connection_success(self, pool, mock_settings):
        """测试成功获取连接"""
        await pool._load_account_configs()
        
        # 模拟已初始化的连接
        mock_conn = AsyncMock()
        mock_conn.is_available = True
        mock_conn.account_config = pool.account_configs["account1"]
        mock_conn.stats = Mock()
        mock_conn.stats.usage_count = 0
        
        pool.account_pools["account1"] = [mock_conn]
        pool.usage_queues["account1"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        connection = await pool.get_connection("account1")
        
        assert connection == mock_conn
        mock_conn.acquire.assert_called_once()
        assert mock_conn in pool.usage_queues["account1"]
    
    @pytest.mark.asyncio
    async def test_get_connection_no_available(self, pool, mock_settings):
        """测试无可用连接时的处理"""
        await pool._load_account_configs()
        
        # 模拟所有连接都忙碌
        mock_conn1 = AsyncMock()
        mock_conn1.is_available = False
        mock_conn1.stats = Mock()
        mock_conn1.stats.usage_count = 5
        
        mock_conn2 = AsyncMock()
        mock_conn2.is_available = False
        mock_conn2.stats = Mock()
        mock_conn2.stats.usage_count = 3
        
        pool.account_pools["account1"] = [mock_conn1, mock_conn2]
        pool.usage_queues["account1"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 应该选择使用次数最少的连接
        connection = await pool.get_connection("account1")
        
        assert connection == mock_conn2  # 使用次数更少
        mock_conn2.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_connection_with_routing(self, pool, mock_settings):
        """测试带路由的连接获取"""
        await pool._load_account_configs()
        
        # 模拟连接
        mock_conn = AsyncMock()
        mock_conn.is_available = True
        mock_conn.stats = Mock()
        mock_conn.stats.usage_count = 0
        
        pool.account_pools["account1"] = [mock_conn]
        pool.usage_queues["account1"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 不指定账户ID，使用路由
        with patch.object(pool, 'get_account_by_routing') as mock_routing:
            mock_routing.return_value = "account1"
            
            connection = await pool.get_connection(routing_key="AAPL")
            
            assert connection == mock_conn
            mock_routing.assert_called_once_with("AAPL", strategy="round_robin")
    
    @pytest.mark.asyncio
    async def test_get_connection_invalid_account(self, pool):
        """测试获取无效账户连接"""
        pool._initialized = True
        
        with pytest.raises(Exception, match="账户不存在或无可用连接"):
            await pool.get_connection("invalid_account")
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self, pool, mock_settings):
        """测试连接上下文管理器"""
        await pool._load_account_configs()
        
        mock_conn = AsyncMock()
        mock_conn.is_available = True
        mock_conn.stats = Mock()
        mock_conn.stats.usage_count = 0
        
        pool.account_pools["account1"] = [mock_conn]
        pool.usage_queues["account1"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 测试正常使用
        async with pool.get_account_connection("account1") as connection:
            assert connection == mock_conn
            mock_conn.acquire.assert_called_once()
        
        # 连接应该被释放
        pool.release_connection.assert_called_once_with(mock_conn)
    
    @pytest.mark.asyncio
    async def test_connection_context_manager_exception(self, pool, mock_settings):
        """测试连接上下文管理器异常处理"""
        await pool._load_account_configs()
        
        mock_conn = AsyncMock()
        mock_conn.is_available = True
        mock_conn.stats = Mock()
        mock_conn.stats.usage_count = 0
        
        pool.account_pools["account1"] = [mock_conn]
        pool.usage_queues["account1"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 测试异常情况下连接仍然被释放
        with pytest.raises(ValueError):
            async with pool.get_account_connection("account1") as connection:
                assert connection == mock_conn
                raise ValueError("Test exception")
        
        # 连接应该被释放
        pool.release_connection.assert_called_once_with(mock_conn)
    
    def test_release_connection(self, pool):
        """测试连接释放"""
        mock_conn = Mock()
        pool.release_connection(mock_conn)
        mock_conn.release.assert_called_once()
    
    def test_get_pool_stats(self, pool, mock_settings):
        """测试连接池统计"""
        # 设置测试数据
        pool.account_configs = {
            "account1": AccountConfig("account1", "key1", "secret1", account_name="Account 1", tier="premium"),
            "account2": AccountConfig("account2", "key2", "secret2", enabled=False)
        }
        
        mock_conn1 = Mock()
        mock_conn1.is_available = True
        mock_conn1.stats.is_healthy = True
        mock_conn1.stats.usage_count = 10
        mock_conn1.stats.error_count = 1
        mock_conn1.stats.avg_response_time = 0.15
        mock_conn1.stats.last_health_check = datetime.utcnow()
        
        mock_conn2 = Mock()
        mock_conn2.is_available = False
        mock_conn2.stats.is_healthy = True
        mock_conn2.stats.usage_count = 5
        mock_conn2.stats.error_count = 0
        mock_conn2.stats.avg_response_time = 0.12
        mock_conn2.stats.last_health_check = datetime.utcnow()
        
        pool.account_pools = {
            "account1": [mock_conn1, mock_conn2]
        }
        
        stats = pool.get_pool_stats()
        
        assert stats["total_accounts"] == 2
        assert stats["active_accounts"] == 1  # account2 is disabled
        assert stats["total_connections"] == 2
        
        account1_stats = stats["account_stats"]["account1"]
        assert account1_stats["account_name"] == "Account 1"
        assert account1_stats["tier"] == "premium"
        assert account1_stats["connection_count"] == 2
        assert account1_stats["available_connections"] == 1
        assert account1_stats["healthy_connections"] == 2
        assert account1_stats["total_usage"] == 15
        assert account1_stats["total_errors"] == 1
        assert account1_stats["avg_response_time"] == 0.135  # (0.15 + 0.12) / 2
    
    @pytest.mark.asyncio
    async def test_health_check_loop(self, pool, mock_settings):
        """测试健康检查循环"""
        await pool._load_account_configs()
        
        # 创建模拟连接
        healthy_conn = AsyncMock()
        healthy_conn._in_use = False
        healthy_conn.test_connection.return_value = True
        
        unhealthy_conn = AsyncMock()
        unhealthy_conn._in_use = False
        unhealthy_conn.test_connection.return_value = False
        
        in_use_conn = AsyncMock()
        in_use_conn._in_use = True
        
        pool.account_pools["account1"] = [healthy_conn, unhealthy_conn, in_use_conn]
        pool._global_lock = asyncio.Lock()
        
        await pool._perform_health_checks()
        
        # 验证健康检查结果
        healthy_conn.test_connection.assert_called_once()
        unhealthy_conn.test_connection.assert_called_once()
        in_use_conn.test_connection.assert_not_called()  # 使用中的连接不检查
        
        # 不健康的连接应该被移除
        assert len(pool.account_pools["account1"]) == 2
        assert healthy_conn in pool.account_pools["account1"]
        assert in_use_conn in pool.account_pools["account1"]
        assert unhealthy_conn not in pool.account_pools["account1"]
    
    @pytest.mark.asyncio
    async def test_shutdown(self, pool):
        """测试连接池关闭"""
        # 模拟后台任务
        mock_task1 = AsyncMock()
        mock_task2 = AsyncMock()
        pool._background_tasks = [mock_task1, mock_task2]
        
        # 模拟连接
        mock_conn = Mock()
        mock_conn._in_use = True
        pool.account_pools = {"account1": [mock_conn]}
        pool.usage_queues = {"account1": []}
        pool._global_lock = asyncio.Lock()
        
        await pool.shutdown()
        
        # 验证任务被取消
        mock_task1.cancel.assert_called_once()
        mock_task2.cancel.assert_called_once()
        
        # 验证连接被释放
        mock_conn.release.assert_called_once()
        
        # 验证数据结构被清理
        assert pool.account_pools == {}
        assert pool.usage_queues == {}


class TestGlobalAccountPool:
    """全局账户连接池测试"""
    
    def test_global_pool_instance(self):
        """测试全局连接池实例"""
        from app.account_pool import account_pool, get_account_pool, connection_pool, get_connection_pool
        
        # 验证单例
        assert account_pool is not None
        assert get_account_pool() is account_pool
        
        # 验证向后兼容别名
        assert connection_pool is account_pool
        assert get_connection_pool is get_account_pool
    
    def test_pool_configuration(self):
        """测试连接池配置"""
        pool = account_pool
        
        assert pool.max_connections_per_account == 3
        assert pool.health_check_interval_seconds == 300


class TestConcurrencyAndRaceConditions:
    """并发和竞态条件测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_requests(self):
        """测试并发连接请求"""
        pool = AccountConnectionPool(max_connections_per_account=2)
        
        # 模拟账户配置
        pool.account_configs = {
            "account1": AccountConfig("account1", "key1", "secret1")
        }
        
        # 模拟连接
        mock_conn1 = AsyncMock()
        mock_conn1.is_available = True
        mock_conn1.stats = Mock()
        mock_conn1.stats.usage_count = 0
        
        mock_conn2 = AsyncMock()
        mock_conn2.is_available = True
        mock_conn2.stats = Mock()
        mock_conn2.stats.usage_count = 0
        
        pool.account_pools["account1"] = [mock_conn1, mock_conn2]
        pool.usage_queues["account1"] = []
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 模拟并发获取连接
        async def get_conn():
            return await pool.get_connection("account1")
        
        # 并发执行
        tasks = [get_conn() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # 验证所有请求都得到了连接
        assert len(results) == 5
        assert all(conn is not None for conn in results)
        
        # 验证连接被正确获取
        assert mock_conn1.acquire.call_count + mock_conn2.acquire.call_count == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        """测试并发健康检查"""
        pool = AccountConnectionPool()
        
        # 模拟连接
        mock_conn = AsyncMock()
        mock_conn._in_use = False
        mock_conn.test_connection.return_value = True
        
        pool.account_pools = {"account1": [mock_conn]}
        pool._global_lock = asyncio.Lock()
        
        # 并发执行健康检查
        tasks = [pool._perform_health_checks() for _ in range(3)]
        await asyncio.gather(*tasks)
        
        # 验证健康检查被正确执行
        assert mock_conn.test_connection.call_count >= 3


class TestErrorScenarios:
    """错误场景测试"""
    
    @pytest.mark.asyncio
    async def test_connection_creation_failure(self):
        """测试连接创建失败"""
        pool = AccountConnectionPool()
        pool.account_configs = {
            "account1": AccountConfig("account1", "invalid_key", "invalid_secret")
        }
        
        with patch('app.account_pool.AlpacaAccountConnection') as mock_conn_class:
            mock_conn_class.side_effect = Exception("Connection failed")
            
            await pool._prebuild_connections()
            
            # 失败的连接不应该被添加到池中
            assert len(pool.account_pools.get("account1", [])) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self):
        """测试健康检查异常处理"""
        pool = AccountConnectionPool()
        
        # 模拟会抛出异常的连接
        mock_conn = AsyncMock()
        mock_conn._in_use = False
        mock_conn.test_connection.side_effect = Exception("Health check failed")
        
        pool.account_pools = {"account1": [mock_conn]}
        pool._global_lock = asyncio.Lock()
        
        # 健康检查不应该抛出异常
        await pool._perform_health_checks()
        
        # 有问题的连接应该被移除
        assert len(pool.account_pools["account1"]) == 0
    
    @pytest.mark.asyncio
    async def test_background_task_exception_handling(self):
        """测试后台任务异常处理"""
        pool = AccountConnectionPool()
        
        # 模拟健康检查抛出异常
        with patch.object(pool, '_perform_health_checks') as mock_health_check:
            mock_health_check.side_effect = Exception("Health check error")
            
            # 后台任务循环应该捕获异常并继续运行
            # 这里我们只运行一次迭代来测试异常处理
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.side_effect = asyncio.CancelledError()  # 模拟任务取消
                
                with pytest.raises(asyncio.CancelledError):
                    await pool._health_check_loop()
                
                mock_health_check.assert_called()


class TestPerformanceMetrics:
    """性能指标测试"""
    
    def test_response_time_calculation(self):
        """测试响应时间计算"""
        config = AccountConfig("test", "key", "secret")
        connection = AlpacaAccountConnection(config)
        
        # 模拟多次请求的平均响应时间计算
        connection.stats.usage_count = 0
        connection.stats.avg_response_time = 0.0
        
        # 第一次请求
        response_time_1 = 0.1
        connection.stats.usage_count = 1
        connection.stats.avg_response_time = response_time_1
        
        # 第二次请求
        response_time_2 = 0.2
        connection.stats.usage_count = 2
        connection.stats.avg_response_time = (
            (connection.stats.avg_response_time * 1 + response_time_2) / 2
        )
        
        assert connection.stats.avg_response_time == 0.15
        
        # 第三次请求
        response_time_3 = 0.3
        connection.stats.usage_count = 3
        connection.stats.avg_response_time = (
            (connection.stats.avg_response_time * 2 + response_time_3) / 3
        )
        
        assert connection.stats.avg_response_time == 0.2
    
    def test_error_rate_tracking(self):
        """测试错误率跟踪"""
        config = AccountConfig("test", "key", "secret")
        connection = AlpacaAccountConnection(config)
        
        # 初始状态
        assert connection.stats.error_count == 0
        assert connection.stats.usage_count == 0
        
        # 模拟成功和失败的请求
        connection.stats.usage_count = 10
        connection.stats.error_count = 2
        
        error_rate = connection.stats.error_count / connection.stats.usage_count
        assert error_rate == 0.2  # 20% 错误率


class TestLoadBalancingStrategies:
    """负载均衡策略测试"""
    
    def test_hash_consistency(self):
        """测试哈希路由的一致性"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # 相同的routing_key应该总是路由到相同的账户
        account1 = pool.get_account_by_routing("AAPL", strategy="hash")
        account2 = pool.get_account_by_routing("AAPL", strategy="hash")
        account3 = pool.get_account_by_routing("AAPL", strategy="hash")
        
        assert account1 == account2 == account3
        
        # 不同的routing_key可能路由到不同的账户
        account_googl = pool.get_account_by_routing("GOOGL", strategy="hash")
        account_tsla = pool.get_account_by_routing("TSLA", strategy="hash")
        
        # 这些可能相同也可能不同，但应该都是有效的账户
        assert account_googl in pool.account_id_list
        assert account_tsla in pool.account_id_list
    
    def test_round_robin_distribution(self):
        """测试轮询分发"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # 收集多个时间点的路由结果
        results = []
        for i in range(10):
            with patch('time.time', return_value=i):
                account = pool.get_account_by_routing(strategy="round_robin")
                results.append(account)
        
        # 应该循环使用所有账户
        expected_pattern = ["account1", "account2", "account3"] * 4  # 12个结果，取前10个
        assert results == expected_pattern[:10]
    
    def test_least_loaded_selection(self):
        """测试最少负载选择"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # 模拟不同负载的连接
        mock_conn1 = Mock()
        mock_conn1.stats.usage_count = 100  # 高负载
        
        mock_conn2 = Mock()
        mock_conn2.stats.usage_count = 10   # 低负载
        
        mock_conn3 = Mock()
        mock_conn3.stats.usage_count = 50   # 中等负载
        
        pool.account_pools = {
            "account1": [mock_conn1, mock_conn1],  # 平均 100
            "account2": [mock_conn2, mock_conn2],  # 平均 10
            "account3": [mock_conn3]               # 平均 50
        }
        
        selected_account = pool.get_account_by_routing(strategy="least_loaded")
        assert selected_account == "account2"  # 负载最轻的账户


# 性能基准测试
class TestPerformanceBenchmarks:
    """性能基准测试"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_connection_acquisition_performance(self):
        """测试连接获取性能"""
        pool = AccountConnectionPool(max_connections_per_account=10)
        
        # 模拟大量连接
        mock_connections = []
        for i in range(10):
            mock_conn = AsyncMock()
            mock_conn.is_available = True
            mock_conn.stats = Mock()
            mock_conn.stats.usage_count = i
            mock_connections.append(mock_conn)
        
        pool.account_configs = {"account1": AccountConfig("account1", "key", "secret")}
        pool.account_pools = {"account1": mock_connections}
        pool.usage_queues = {"account1": []}
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 性能测试
        start_time = time.time()
        for _ in range(100):
            conn = await pool.get_connection("account1")
            pool.release_connection(conn)
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 100
        print(f"Average connection acquisition time: {avg_time * 1000:.2f}ms")
        
        # 性能断言（连接获取应该在1ms内完成）
        assert avg_time < 0.001, f"Connection acquisition too slow: {avg_time * 1000:.2f}ms"
    
    @pytest.mark.performance
    def test_routing_performance(self):
        """测试路由性能"""
        pool = AccountConnectionPool()
        pool.account_id_list = [f"account{i}" for i in range(100)]
        
        # 测试不同路由策略的性能
        strategies = ["round_robin", "hash", "random", "least_loaded"]
        
        for strategy in strategies:
            if strategy == "least_loaded":
                # 为最少负载策略创建模拟连接
                pool.account_pools = {}
                for account_id in pool.account_id_list:
                    mock_conn = Mock()
                    mock_conn.stats.usage_count = 0
                    pool.account_pools[account_id] = [mock_conn]
            
            start_time = time.time()
            for i in range(1000):
                pool.get_account_by_routing(f"symbol{i}", strategy=strategy)
            end_time = time.time()
            
            avg_time = (end_time - start_time) / 1000
            print(f"{strategy} routing average time: {avg_time * 1000:.2f}ms")
            
            # 路由应该在0.1ms内完成
            assert avg_time < 0.0001, f"{strategy} routing too slow: {avg_time * 1000:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])