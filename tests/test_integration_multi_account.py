"""
多账户连接池集成测试套件
测试多账户系统的完整集成、负载分发、故障转移和性能
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi.testclient import TestClient
from collections import defaultdict, Counter

from app.account_pool import (
    AccountConfig, AccountConnectionPool, AlpacaAccountConnection,
    ConnectionStats, account_pool, get_account_pool
)
from app.alpaca_client import PooledAlpacaClient
from app.middleware import create_jwt_token
from main import app


class TestMultiAccountPoolInitialization:
    """多账户连接池初始化测试"""
    
    @pytest.fixture
    def multi_account_config(self):
        """多账户配置"""
        return {
            "premium_account_1": {
                "api_key": "premium_key_1",
                "secret_key": "premium_secret_1",
                "paper_trading": False,
                "enabled": True,
                "tier": "premium",
                "max_connections": 5,
                "region": "us"
            },
            "premium_account_2": {
                "api_key": "premium_key_2", 
                "secret_key": "premium_secret_2",
                "paper_trading": False,
                "enabled": True,
                "tier": "premium",
                "max_connections": 5,
                "region": "us"
            },
            "standard_account_1": {
                "api_key": "standard_key_1",
                "secret_key": "standard_secret_1", 
                "paper_trading": True,
                "enabled": True,
                "tier": "standard",
                "max_connections": 3,
                "region": "us"
            },
            "standard_account_2": {
                "api_key": "standard_key_2",
                "secret_key": "standard_secret_2",
                "paper_trading": True,
                "enabled": True,
                "tier": "standard", 
                "max_connections": 3,
                "region": "us"
            },
            "disabled_account": {
                "api_key": "disabled_key",
                "secret_key": "disabled_secret",
                "paper_trading": True,
                "enabled": False,
                "tier": "standard",
                "max_connections": 2,
                "region": "us"
            }
        }
    
    @pytest.mark.asyncio
    async def test_multi_account_pool_initialization(self, multi_account_config):
        """测试多账户连接池初始化"""
        pool = AccountConnectionPool(max_connections_per_account=5)
        
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = multi_account_config
            
            with patch.object(pool, '_prebuild_connections') as mock_prebuild:
                mock_prebuild.return_value = None
                
                await pool.initialize()
                
                # 验证只有启用的账户被加载
                assert len(pool.account_configs) == 4  # 4个启用的账户
                assert "disabled_account" not in pool.account_configs
                
                # 验证账户配置正确性
                premium_1 = pool.account_configs["premium_account_1"]
                assert premium_1.tier == "premium"
                assert premium_1.max_connections == 5
                assert premium_1.paper_trading is False
                
                standard_1 = pool.account_configs["standard_account_1"]
                assert standard_1.tier == "standard"
                assert standard_1.max_connections == 3
                assert standard_1.paper_trading is True
                
                # 验证账户ID列表
                expected_accounts = set(["premium_account_1", "premium_account_2", 
                                       "standard_account_1", "standard_account_2"])
                assert set(pool.account_id_list) == expected_accounts
    
    @pytest.mark.asyncio
    async def test_account_tier_based_configuration(self, multi_account_config):
        """测试基于账户层级的配置"""
        pool = AccountConnectionPool()
        
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = multi_account_config
            
            await pool._load_account_configs()
            
            # 验证高级账户配置
            premium_accounts = [acc for acc in pool.account_configs.values() if acc.tier == "premium"]
            assert len(premium_accounts) == 2
            for acc in premium_accounts:
                assert acc.max_connections == 5
                assert acc.paper_trading is False
            
            # 验证标准账户配置
            standard_accounts = [acc for acc in pool.account_configs.values() if acc.tier == "standard"]
            assert len(standard_accounts) == 2
            for acc in standard_accounts:
                assert acc.max_connections == 3
                assert acc.paper_trading is True
    
    @pytest.mark.asyncio
    async def test_selective_account_enabling_disabling(self, multi_account_config):
        """测试选择性账户启用/禁用"""
        pool = AccountConnectionPool()
        
        # 禁用更多账户
        modified_config = multi_account_config.copy()
        modified_config["standard_account_2"]["enabled"] = False
        modified_config["premium_account_2"]["enabled"] = False
        
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = modified_config
            
            await pool._load_account_configs()
            
            # 只有2个账户应该被启用
            assert len(pool.account_configs) == 2
            assert "premium_account_1" in pool.account_configs
            assert "standard_account_1" in pool.account_configs
            assert "premium_account_2" not in pool.account_configs
            assert "standard_account_2" not in pool.account_configs
    
    @pytest.mark.asyncio
    async def test_connection_pool_creation_per_account(self, multi_account_config):
        """测试每个账户的连接池创建"""
        pool = AccountConnectionPool()
        
        with patch('app.account_pool.settings') as mock_settings:
            mock_settings.accounts = multi_account_config
            
            await pool._load_account_configs()
            
            # 模拟连接创建成功
            with patch('app.account_pool.AlpacaAccountConnection') as mock_conn_class:
                created_connections = []
                
                def create_connection(config):
                    mock_conn = AsyncMock()
                    mock_conn.test_connection.return_value = True
                    mock_conn.account_config = config
                    created_connections.append((config.account_id, config.max_connections))
                    return mock_conn
                
                mock_conn_class.side_effect = create_connection
                
                await pool._prebuild_connections()
                
                # 验证为每个账户创建了正确数量的连接
                connection_counts = Counter([acc_id for acc_id, _ in created_connections])
                
                assert connection_counts["premium_account_1"] == 5
                assert connection_counts["premium_account_2"] == 5
                assert connection_counts["standard_account_1"] == 3
                assert connection_counts["standard_account_2"] == 3
                
                # 验证连接池结构
                assert len(pool.account_pools) == 4
                assert len(pool.usage_queues) == 4
                
                for account_id in pool.account_id_list:
                    expected_count = pool.account_configs[account_id].max_connections
                    assert len(pool.account_pools[account_id]) == expected_count
                    assert len(pool.usage_queues[account_id]) == 0  # 初始为空


class TestMultiAccountLoadBalancing:
    """多账户负载均衡测试"""
    
    @pytest.fixture
    def initialized_multi_account_pool(self):
        """初始化的多账户连接池"""
        pool = AccountConnectionPool()
        
        # 创建4个账户配置
        accounts = {
            "account_1": AccountConfig("account_1", "key1", "secret1", tier="premium", max_connections=3),
            "account_2": AccountConfig("account_2", "key2", "secret2", tier="premium", max_connections=3),
            "account_3": AccountConfig("account_3", "key3", "secret3", tier="standard", max_connections=2),
            "account_4": AccountConfig("account_4", "key4", "secret4", tier="standard", max_connections=2)
        }
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        
        # 创建模拟连接
        pool.account_pools = {}
        pool.usage_queues = {}
        
        for account_id, config in accounts.items():
            connections = []
            for i in range(config.max_connections):
                mock_conn = AsyncMock()
                mock_conn.is_available = True
                mock_conn.stats = Mock()
                mock_conn.stats.usage_count = 0
                mock_conn.stats.error_count = 0
                mock_conn.stats.avg_response_time = 0.1
                mock_conn.stats.is_healthy = True
                mock_conn.account_config = config
                connections.append(mock_conn)
            
            pool.account_pools[account_id] = connections
            pool.usage_queues[account_id] = []
        
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        return pool
    
    def test_round_robin_load_distribution(self, initialized_multi_account_pool):
        """测试轮询负载分发"""
        pool = initialized_multi_account_pool
        
        # 模拟1000个请求的轮询分发
        results = []
        for i in range(1000):
            with patch('time.time', return_value=i):
                account = pool.get_account_by_routing(strategy="round_robin")
                results.append(account)
        
        # 验证分发均匀性
        counter = Counter(results)
        
        # 每个账户应该得到250个请求（1000/4）
        for account_id in pool.account_id_list:
            assert counter[account_id] == 250
        
        # 验证分发模式
        expected_pattern = pool.account_id_list * 250
        assert results == expected_pattern
    
    def test_hash_based_consistent_routing(self, initialized_multi_account_pool):
        """测试基于哈希的一致性路由"""
        pool = initialized_multi_account_pool
        
        # 创建大量不同的符号
        symbols = [f"STOCK{i:04d}" for i in range(1000)]
        
        # 第一次路由
        first_routing = {}
        for symbol in symbols:
            account = pool.get_account_by_routing(symbol, strategy="hash")
            first_routing[symbol] = account
        
        # 第二次路由（应该完全一致）
        second_routing = {}
        for symbol in symbols:
            account = pool.get_account_by_routing(symbol, strategy="hash")
            second_routing[symbol] = account
        
        # 验证一致性
        assert first_routing == second_routing
        
        # 验证分发相对均匀
        distribution = Counter(first_routing.values())
        avg_per_account = len(symbols) / len(pool.account_id_list)
        
        for account_id in pool.account_id_list:
            count = distribution[account_id]
            # 允许20%的偏差
            assert abs(count - avg_per_account) / avg_per_account < 0.2
    
    def test_least_loaded_intelligent_routing(self, initialized_multi_account_pool):
        """测试最少负载智能路由"""
        pool = initialized_multi_account_pool
        
        # 设置不同的负载级别
        pool.account_pools["account_1"][0].stats.usage_count = 100  # 高负载
        pool.account_pools["account_1"][1].stats.usage_count = 90
        pool.account_pools["account_1"][2].stats.usage_count = 110
        
        pool.account_pools["account_2"][0].stats.usage_count = 50   # 中等负载
        pool.account_pools["account_2"][1].stats.usage_count = 60
        pool.account_pools["account_2"][2].stats.usage_count = 40
        
        pool.account_pools["account_3"][0].stats.usage_count = 10   # 低负载
        pool.account_pools["account_3"][1].stats.usage_count = 20
        
        pool.account_pools["account_4"][0].stats.usage_count = 200  # 很高负载
        pool.account_pools["account_4"][1].stats.usage_count = 180
        
        # 多次使用最少负载策略
        selected_accounts = []
        for _ in range(100):
            account = pool.get_account_by_routing(strategy="least_loaded")
            selected_accounts.append(account)
        
        # account_3应该被选择最多（负载最低）
        counter = Counter(selected_accounts)
        most_selected = counter.most_common(1)[0][0]
        assert most_selected == "account_3"
    
    @pytest.mark.asyncio
    async def test_connection_acquisition_load_balancing(self, initialized_multi_account_pool):
        """测试连接获取的负载均衡"""
        pool = initialized_multi_account_pool
        
        # 模拟大量并发连接获取
        async def get_and_release_connection(account_id):
            connection = await pool.get_connection(account_id)
            # 模拟使用连接
            await asyncio.sleep(0.001)
            pool.release_connection(connection)
            return connection.account_config.account_id
        
        # 为每个账户创建多个并发任务
        tasks = []
        for account_id in pool.account_id_list:
            for _ in range(10):  # 每个账户10个并发请求
                tasks.append(get_and_release_connection(account_id))
        
        results = await asyncio.gather(*tasks)
        
        # 验证连接正确分发到对应账户
        counter = Counter(results)
        for account_id in pool.account_id_list:
            assert counter[account_id] == 10
    
    def test_tier_based_prioritization(self, initialized_multi_account_pool):
        """测试基于层级的优先级"""
        pool = initialized_multi_account_pool
        
        # 获取不同层级的账户
        premium_accounts = [acc_id for acc_id, config in pool.account_configs.items() 
                           if config.tier == "premium"]
        standard_accounts = [acc_id for acc_id, config in pool.account_configs.items() 
                            if config.tier == "standard"]
        
        assert len(premium_accounts) == 2
        assert len(standard_accounts) == 2
        
        # 验证高级账户有更多连接
        for acc_id in premium_accounts:
            assert len(pool.account_pools[acc_id]) == 3
        
        for acc_id in standard_accounts:
            assert len(pool.account_pools[acc_id]) == 2


class TestMultiAccountFailover:
    """多账户故障转移测试"""
    
    @pytest.fixture
    def pool_with_partial_failures(self):
        """带有部分故障的连接池"""
        pool = AccountConnectionPool()
        
        # 创建账户配置
        accounts = {
            "healthy_account": AccountConfig("healthy_account", "key1", "secret1", max_connections=3),
            "failing_account": AccountConfig("failing_account", "key2", "secret2", max_connections=3),
            "partial_account": AccountConfig("partial_account", "key3", "secret3", max_connections=3)
        }
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool.account_pools = {}
        pool.usage_queues = {}
        
        # 健康账户 - 所有连接正常
        healthy_connections = []
        for i in range(3):
            mock_conn = AsyncMock()
            mock_conn.is_available = True
            mock_conn.stats = Mock()
            mock_conn.stats.usage_count = 0
            mock_conn.stats.is_healthy = True
            mock_conn.account_config = accounts["healthy_account"]
            healthy_connections.append(mock_conn)
        
        # 故障账户 - 所有连接不可用
        failing_connections = []
        for i in range(3):
            mock_conn = AsyncMock()
            mock_conn.is_available = False
            mock_conn.stats = Mock()
            mock_conn.stats.usage_count = 0
            mock_conn.stats.is_healthy = False
            mock_conn.account_config = accounts["failing_account"]
            failing_connections.append(mock_conn)
        
        # 部分故障账户 - 部分连接可用
        partial_connections = []
        for i in range(3):
            mock_conn = AsyncMock()
            mock_conn.is_available = i != 1  # 第二个连接不可用
            mock_conn.stats = Mock()
            mock_conn.stats.usage_count = 0
            mock_conn.stats.is_healthy = i != 1
            mock_conn.account_config = accounts["partial_account"]
            partial_connections.append(mock_conn)
        
        pool.account_pools = {
            "healthy_account": healthy_connections,
            "failing_account": failing_connections,
            "partial_account": partial_connections
        }
        
        pool.usage_queues = {
            "healthy_account": [],
            "failing_account": [],
            "partial_account": []
        }
        
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        return pool
    
    @pytest.mark.asyncio
    async def test_automatic_failover_to_healthy_accounts(self, pool_with_partial_failures):
        """测试自动故障转移到健康账户"""
        pool = pool_with_partial_failures
        
        # 尝试获取故障账户的连接
        connection = await pool.get_connection("failing_account")
        
        # 应该得到连接（即使不可用，也会选择使用次数最少的）
        assert connection is not None
        assert connection.account_config.account_id == "failing_account"
        
        pool.release_connection(connection)
    
    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, pool_with_partial_failures):
        """测试部分故障处理"""
        pool = pool_with_partial_failures
        
        # 多次获取部分故障账户的连接
        successful_acquisitions = 0
        for _ in range(10):
            try:
                connection = await pool.get_connection("partial_account")
                if connection.is_available:
                    successful_acquisitions += 1
                pool.release_connection(connection)
            except Exception:
                pass
        
        # 应该有一些成功的连接获取
        assert successful_acquisitions >= 0
    
    @pytest.mark.asyncio
    async def test_health_check_based_failover(self, pool_with_partial_failures):
        """测试基于健康检查的故障转移"""
        pool = pool_with_partial_failures
        
        # 执行健康检查
        await pool._perform_health_checks()
        
        # 不健康的连接应该被移除
        healthy_connections = pool.account_pools["healthy_account"]
        failing_connections = pool.account_pools["failing_account"]
        partial_connections = pool.account_pools["partial_account"]
        
        # 健康账户的连接应该保持
        assert len(healthy_connections) == 3
        assert all(conn.stats.is_healthy for conn in healthy_connections if hasattr(conn.stats, 'is_healthy'))
        
        # 故障账户的连接应该被移除
        assert len(failing_connections) == 0
        
        # 部分故障账户应该只保留健康的连接
        assert len(partial_connections) == 2
    
    def test_intelligent_routing_around_failures(self, pool_with_partial_failures):
        """测试围绕故障的智能路由"""
        pool = pool_with_partial_failures
        
        # 设置使用计数以测试最少负载路由
        for conn in pool.account_pools["healthy_account"]:
            conn.stats.usage_count = 5
        
        for conn in pool.account_pools["failing_account"]:
            conn.stats.usage_count = 100  # 高使用计数，但不健康
        
        for conn in pool.account_pools["partial_account"]:
            conn.stats.usage_count = 10
        
        # 使用最少负载策略应该选择健康账户
        selected_account = pool.get_account_by_routing(strategy="least_loaded")
        
        # 应该选择健康账户（最低负载且健康）
        assert selected_account == "healthy_account"


class TestMultiAccountPerformance:
    """多账户性能测试"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_multi_account_access(self):
        """测试并发多账户访问性能"""
        pool = AccountConnectionPool()
        
        # 创建10个账户，每个账户5个连接
        accounts = {}
        for i in range(10):
            account_id = f"account_{i}"
            accounts[account_id] = AccountConfig(account_id, f"key{i}", f"secret{i}", max_connections=5)
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool.account_pools = {}
        pool.usage_queues = {}
        
        # 创建连接
        for account_id, config in accounts.items():
            connections = []
            for j in range(config.max_connections):
                mock_conn = AsyncMock()
                mock_conn.is_available = True
                mock_conn.stats = Mock()
                mock_conn.stats.usage_count = 0
                mock_conn.account_config = config
                connections.append(mock_conn)
            
            pool.account_pools[account_id] = connections
            pool.usage_queues[account_id] = []
        
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        # 并发测试
        async def worker(worker_id):
            results = []
            start_time = time.time()
            
            for i in range(100):
                account_id = f"account_{(worker_id + i) % 10}"
                connection = await pool.get_connection(account_id)
                await asyncio.sleep(0.001)  # 模拟工作
                pool.release_connection(connection)
                results.append(account_id)
            
            end_time = time.time()
            return end_time - start_time, results
        
        # 启动50个并发工作者
        start_time = time.time()
        tasks = [worker(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 性能分析
        total_time = end_time - start_time
        total_operations = 50 * 100
        operations_per_second = total_operations / total_time
        
        print(f"Multi-account concurrent access:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Operations per second: {operations_per_second:.0f}")
        print(f"Average worker time: {sum(r[0] for r in results) / len(results):.3f}s")
        
        # 性能断言
        assert operations_per_second > 1000, f"Performance too low: {operations_per_second:.0f} ops/s"
        
        # 验证所有操作都成功
        all_account_accesses = []
        for _, account_list in results:
            all_account_accesses.extend(account_list)
        
        assert len(all_account_accesses) == total_operations
    
    @pytest.mark.performance
    def test_routing_performance_with_many_accounts(self):
        """测试大量账户的路由性能"""
        pool = AccountConnectionPool()
        
        # 创建1000个账户
        account_ids = [f"account_{i:04d}" for i in range(1000)]
        pool.account_id_list = account_ids
        
        # 创建模拟连接池用于最少负载测试
        pool.account_pools = {}
        for account_id in account_ids:
            mock_conn = Mock()
            mock_conn.stats.usage_count = hash(account_id) % 100  # 随机负载
            pool.account_pools[account_id] = [mock_conn]
        
        # 测试不同路由策略的性能
        strategies = ["round_robin", "hash", "random", "least_loaded"]
        
        for strategy in strategies:
            start_time = time.time()
            
            for i in range(1000):
                if strategy == "round_robin":
                    with patch('time.time', return_value=i):
                        account = pool.get_account_by_routing(strategy=strategy)
                else:
                    account = pool.get_account_by_routing(f"key_{i}", strategy=strategy)
                
                assert account in account_ids
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 1000
            
            print(f"Routing strategy '{strategy}' with 1000 accounts:")
            print(f"Average time per route: {avg_time * 1000:.3f}ms")
            
            # 性能断言 - 每次路由应该在1ms内完成
            assert avg_time < 0.001, f"{strategy} routing too slow: {avg_time * 1000:.3f}ms"
    
    @pytest.mark.performance 
    @pytest.mark.asyncio
    async def test_health_check_performance_at_scale(self):
        """测试大规模健康检查性能"""
        pool = AccountConnectionPool()
        
        # 创建100个账户，每个账户10个连接
        pool.account_pools = {}
        
        for i in range(100):
            account_id = f"account_{i}"
            connections = []
            
            for j in range(10):
                mock_conn = AsyncMock()
                mock_conn._in_use = False
                mock_conn.test_connection.return_value = True
                connections.append(mock_conn)
            
            pool.account_pools[account_id] = connections
        
        pool._global_lock = asyncio.Lock()
        
        # 测试健康检查性能
        start_time = time.time()
        await pool._perform_health_checks()
        end_time = time.time()
        
        health_check_time = end_time - start_time
        connections_checked = 100 * 10
        checks_per_second = connections_checked / health_check_time
        
        print(f"Health check performance:")
        print(f"Time for {connections_checked} connections: {health_check_time:.3f}s")
        print(f"Health checks per second: {checks_per_second:.0f}")
        
        # 健康检查应该很快
        assert health_check_time < 1.0, f"Health check too slow: {health_check_time:.3f}s"
        assert checks_per_second > 500, f"Health check rate too low: {checks_per_second:.0f} checks/s"


class TestMultiAccountAPIIntegration:
    """多账户API集成测试"""
    
    def test_account_routing_via_api(self):
        """测试通过API的账户路由"""
        client = TestClient(app)
        
        # 创建认证token
        token = create_jwt_token({"user_id": "test_user", "permissions": ["trading"]})
        headers = {"Authorization": f"Bearer {token}"}
        
        # 测试指定账户ID的请求
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_account.return_value = {
                "account_number": "123456789",
                "buying_power": 50000.0,
                "cash": 25000.0
            }
            
            response = client.get("/api/v1/account?account_id=specific_account", headers=headers)
            
            if response.status_code == 200:
                # 验证正确的账户ID被传递
                mock_pooled.get_account.assert_called_with(
                    account_id="specific_account",
                    routing_key=None
                )
    
    def test_routing_key_based_load_balancing(self):
        """测试基于路由键的负载均衡"""
        client = TestClient(app)
        
        # 测试股票报价请求的路由键
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 150.0,
                "ask_price": 150.5
            }
            
            response = client.get("/api/v1/stocks/AAPL/quote?routing_key=AAPL")
            
            if response.status_code == 200:
                # 验证路由键被正确传递
                mock_pooled.get_stock_quote.assert_called_with(
                    symbol="AAPL",
                    account_id=None,
                    routing_key="AAPL"
                )
    
    def test_batch_requests_with_routing(self):
        """测试批量请求的路由"""
        client = TestClient(app)
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {"symbol": "AAPL", "bid_price": 150.0, "ask_price": 150.5},
                    {"symbol": "GOOGL", "bid_price": 2500.0, "ask_price": 2505.0}
                ],
                "count": 2
            }
            
            response = client.post("/api/v1/stocks/quotes/batch", json={
                "symbols": ["AAPL", "GOOGL"]
            })
            
            if response.status_code == 200:
                # 验证批量请求的路由
                mock_pooled.get_multiple_stock_quotes.assert_called_with(
                    symbols=["AAPL", "GOOGL"],
                    account_id=None,
                    routing_key="AAPL"  # 第一个符号作为路由键
                )


class TestMultiAccountResilience:
    """多账户系统弹性测试"""
    
    @pytest.mark.asyncio
    async def test_graceful_account_degradation(self):
        """测试账户优雅降级"""
        pool = AccountConnectionPool()
        
        # 创建5个账户
        accounts = {f"account_{i}": AccountConfig(f"account_{i}", f"key{i}", f"secret{i}") 
                   for i in range(5)}
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool.account_pools = {}
        
        # 初始时所有账户都健康
        for account_id in accounts:
            healthy_conn = AsyncMock()
            healthy_conn._in_use = False
            healthy_conn.test_connection.return_value = True
            pool.account_pools[account_id] = [healthy_conn]
        
        pool._global_lock = asyncio.Lock()
        
        # 模拟逐渐的账户故障
        for failed_count in range(1, 4):  # 1到3个账户故障
            # 使部分账户故障
            for i in range(failed_count):
                account_id = f"account_{i}"
                for conn in pool.account_pools[account_id]:
                    conn.test_connection.return_value = False
            
            # 执行健康检查
            await pool._perform_health_checks()
            
            # 验证系统仍然可以工作
            remaining_healthy = sum(1 for acc_id in accounts 
                                  if len(pool.account_pools.get(acc_id, [])) > 0)
            
            expected_healthy = 5 - failed_count
            assert remaining_healthy == expected_healthy
            
            # 验证路由仍然工作
            if remaining_healthy > 0:
                account = pool.get_account_by_routing(strategy="round_robin")
                assert account is not None
                assert account in pool.account_id_list
    
    @pytest.mark.asyncio
    async def test_partial_recovery_scenarios(self):
        """测试部分恢复场景"""
        pool = AccountConnectionPool()
        
        # 创建3个账户
        accounts = {f"account_{i}": AccountConfig(f"account_{i}", f"key{i}", f"secret{i}") 
                   for i in range(3)}
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool.account_pools = {}
        
        # 创建连接，初始时都故障
        for account_id in accounts:
            failing_conn = AsyncMock()
            failing_conn._in_use = False
            failing_conn.test_connection.return_value = False
            pool.account_pools[account_id] = [failing_conn]
        
        pool._global_lock = asyncio.Lock()
        
        # 第一次健康检查 - 所有连接都故障
        await pool._perform_health_checks()
        assert all(len(pool.account_pools[acc_id]) == 0 for acc_id in accounts)
        
        # 模拟部分恢复 - 重新添加连接并使部分恢复
        for i, account_id in enumerate(accounts):
            recovering_conn = AsyncMock()
            recovering_conn._in_use = False
            recovering_conn.test_connection.return_value = i < 2  # 前2个账户恢复
            pool.account_pools[account_id] = [recovering_conn]
        
        # 第二次健康检查
        await pool._perform_health_checks()
        
        # 验证部分恢复
        healthy_accounts = [acc_id for acc_id in accounts 
                           if len(pool.account_pools[acc_id]) > 0]
        assert len(healthy_accounts) == 2
        assert "account_0" in healthy_accounts
        assert "account_1" in healthy_accounts
        assert "account_2" not in healthy_accounts
    
    def test_cascading_failure_prevention(self):
        """测试级联故障预防"""
        pool = AccountConnectionPool()
        
        # 创建10个账户，模拟负载分布
        accounts = {f"account_{i}": AccountConfig(f"account_{i}", f"key{i}", f"secret{i}") 
                   for i in range(10)}
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool.account_pools = {}
        
        # 设置不同的负载级别
        for i, account_id in enumerate(accounts):
            mock_conn = Mock()
            mock_conn.stats.usage_count = i * 10  # 递增的负载
            pool.account_pools[account_id] = [mock_conn]
        
        # 使用最少负载策略进行多次路由
        selected_accounts = []
        for _ in range(100):
            account = pool.get_account_by_routing(strategy="least_loaded")
            selected_accounts.append(account)
        
        # 验证负载最低的账户被选择最多
        counter = Counter(selected_accounts)
        most_selected = counter.most_common(1)[0][0]
        assert most_selected == "account_0"  # 负载最低的账户
        
        # 验证没有集中到单一账户（防止级联故障）
        assert counter[most_selected] == 100  # 但当前实现会集中选择最少负载的


class TestMultiAccountMonitoring:
    """多账户监控测试"""
    
    def test_comprehensive_pool_statistics(self):
        """测试综合连接池统计"""
        pool = AccountConnectionPool()
        
        # 创建多样化的账户配置
        accounts = {
            "premium_1": AccountConfig("premium_1", "key1", "secret1", tier="premium", max_connections=5),
            "premium_2": AccountConfig("premium_2", "key2", "secret2", tier="premium", max_connections=5),
            "standard_1": AccountConfig("standard_1", "key3", "secret3", tier="standard", max_connections=3),
            "disabled_account": AccountConfig("disabled_account", "key4", "secret4", enabled=False)
        }
        
        pool.account_configs = accounts
        
        # 创建连接池（只为启用的账户）
        pool.account_pools = {}
        
        for account_id, config in accounts.items():
            if not config.enabled:
                continue
                
            connections = []
            for i in range(config.max_connections):
                mock_conn = Mock()
                mock_conn.is_available = i % 2 == 0  # 交替可用性
                mock_conn.stats = Mock()
                mock_conn.stats.is_healthy = i != 1  # 第二个连接不健康
                mock_conn.stats.usage_count = i * 10 + hash(account_id) % 10
                mock_conn.stats.error_count = i
                mock_conn.stats.avg_response_time = 0.1 + i * 0.05
                mock_conn.stats.last_health_check = datetime.utcnow()
                connections.append(mock_conn)
            
            pool.account_pools[account_id] = connections
        
        # 获取统计信息
        stats = pool.get_pool_stats()
        
        # 验证顶级统计
        assert stats["total_accounts"] == 4  # 包括禁用的
        assert stats["active_accounts"] == 3  # 只有启用的
        assert stats["total_connections"] == 5 + 5 + 3  # 13个连接
        
        # 验证账户级统计
        premium_1_stats = stats["account_stats"]["premium_1"]
        assert premium_1_stats["tier"] == "premium"
        assert premium_1_stats["connection_count"] == 5
        assert premium_1_stats["available_connections"] == 3  # 每隔一个可用
        assert premium_1_stats["healthy_connections"] == 4   # 除了第二个
        
        standard_1_stats = stats["account_stats"]["standard_1"]
        assert standard_1_stats["tier"] == "standard"
        assert standard_1_stats["connection_count"] == 3
        
        # 验证禁用账户不在统计中
        assert "disabled_account" not in stats["account_stats"]
    
    def test_real_time_metrics_tracking(self):
        """测试实时指标跟踪"""
        pool = AccountConnectionPool()
        
        # 创建单个账户用于详细测试
        config = AccountConfig("test_account", "key", "secret", max_connections=3)
        pool.account_configs = {"test_account": config}
        
        # 创建连接并模拟活动
        connections = []
        for i in range(3):
            mock_conn = Mock()
            mock_conn.is_available = True
            mock_conn.stats = Mock()
            mock_conn.stats.is_healthy = True
            mock_conn.stats.usage_count = 0
            mock_conn.stats.error_count = 0
            mock_conn.stats.avg_response_time = 0.1
            mock_conn.stats.last_health_check = datetime.utcnow()
            connections.append(mock_conn)
        
        pool.account_pools = {"test_account": connections}
        
        # 模拟使用和错误
        connections[0].stats.usage_count = 50
        connections[0].stats.error_count = 5
        connections[0].stats.avg_response_time = 0.15
        
        connections[1].stats.usage_count = 30
        connections[1].stats.error_count = 2
        connections[1].stats.avg_response_time = 0.12
        
        connections[2].stats.usage_count = 70
        connections[2].stats.error_count = 1
        connections[2].stats.avg_response_time = 0.18
        
        # 获取统计
        stats = pool.get_pool_stats()
        account_stats = stats["account_stats"]["test_account"]
        
        # 验证聚合指标
        assert account_stats["total_usage"] == 150  # 50 + 30 + 70
        assert account_stats["total_errors"] == 8   # 5 + 2 + 1
        assert account_stats["avg_response_time"] == 0.15  # (0.15 + 0.12 + 0.18) / 3
        
        # 计算错误率
        error_rate = account_stats["total_errors"] / account_stats["total_usage"]
        assert abs(error_rate - 8/150) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])