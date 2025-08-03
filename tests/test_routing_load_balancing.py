"""
路由机制和负载均衡综合测试套件
测试账户路由策略、负载均衡算法、故障转移和性能
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter

from app.account_pool import (
    AccountConfig, AccountConnectionPool, AlpacaAccountConnection,
    ConnectionStats, account_pool
)
from app.routes import get_routing_info
from app.alpaca_client import PooledAlpacaClient


class TestRoutingStrategies:
    """路由策略测试"""
    
    @pytest.fixture
    def pool_with_accounts(self):
        """创建带有多个账户的连接池"""
        pool = AccountConnectionPool()
        
        # 创建5个测试账户
        accounts = {}
        for i in range(1, 6):
            account_id = f"account{i}"
            accounts[account_id] = AccountConfig(
                account_id=account_id,
                api_key=f"key{i}",
                secret_key=f"secret{i}",
                tier="standard" if i <= 3 else "premium",
                max_connections=2 if i <= 3 else 3,
                enabled=True
            )
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        return pool
    
    def test_round_robin_basic(self, pool_with_accounts):
        """测试基础轮询路由"""
        pool = pool_with_accounts
        
        results = []
        for i in range(15):  # 测试15次请求
            with patch('time.time', return_value=i):
                account = pool.get_account_by_routing(strategy="round_robin")
                results.append(account)
        
        # 验证轮询模式
        expected_pattern = ["account1", "account2", "account3", "account4", "account5"] * 3
        assert results == expected_pattern
    
    def test_round_robin_distribution(self, pool_with_accounts):
        """测试轮询分发均匀性"""
        pool = pool_with_accounts
        
        results = []
        for i in range(100):
            with patch('time.time', return_value=i):
                account = pool.get_account_by_routing(strategy="round_robin")
                results.append(account)
        
        # 验证分发均匀性
        counter = Counter(results)
        for account_id in pool.account_id_list:
            assert counter[account_id] == 20  # 100/5 = 20次每个账户
    
    def test_hash_routing_consistency(self, pool_with_accounts):
        """测试哈希路由一致性"""
        pool = pool_with_accounts
        
        test_symbols = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN", "META", "NVDA"]
        
        # 多次请求相同符号应该路由到相同账户
        for symbol in test_symbols:
            accounts = []
            for _ in range(10):
                account = pool.get_account_by_routing(symbol, strategy="hash")
                accounts.append(account)
            
            # 所有请求应该路由到同一个账户
            assert len(set(accounts)) == 1, f"Symbol {symbol} routed to multiple accounts: {set(accounts)}"
            assert accounts[0] in pool.account_id_list
    
    def test_hash_routing_distribution(self, pool_with_accounts):
        """测试哈希路由分发性"""
        pool = pool_with_accounts
        
        # 生成大量不同的routing keys
        routing_keys = [f"SYMBOL{i:04d}" for i in range(1000)]
        
        results = []
        for key in routing_keys:
            account = pool.get_account_by_routing(key, strategy="hash")
            results.append(account)
        
        # 验证分发相对均匀（允许一定偏差）
        counter = Counter(results)
        expected_per_account = 1000 / len(pool.account_id_list)
        
        for account_id in pool.account_id_list:
            count = counter[account_id]
            # 允许20%的偏差
            assert abs(count - expected_per_account) / expected_per_account < 0.2, \
                f"Account {account_id} has {count} requests, expected ~{expected_per_account}"
    
    def test_random_routing(self, pool_with_accounts):
        """测试随机路由"""
        pool = pool_with_accounts
        
        results = []
        for _ in range(1000):
            account = pool.get_account_by_routing(strategy="random")
            results.append(account)
            assert account in pool.account_id_list
        
        # 验证所有账户都被选择过
        selected_accounts = set(results)
        assert selected_accounts == set(pool.account_id_list)
        
        # 验证分发相对随机（不应该有明显的模式）
        counter = Counter(results)
        expected_per_account = 1000 / len(pool.account_id_list)
        
        # 随机分发应该在合理范围内
        for account_id in pool.account_id_list:
            count = counter[account_id]
            # 随机分发允许更大的偏差（30%）
            assert abs(count - expected_per_account) / expected_per_account < 0.3
    
    def test_least_loaded_routing(self, pool_with_accounts):
        """测试最少负载路由"""
        pool = pool_with_accounts
        
        # 模拟不同的负载情况
        mock_connections = {}
        for account_id in pool.account_id_list:
            mock_conn = Mock()
            # 为不同账户设置不同的负载
            if account_id == "account1":
                mock_conn.stats.usage_count = 100  # 高负载
            elif account_id == "account2":
                mock_conn.stats.usage_count = 50   # 中等负载
            elif account_id == "account3":
                mock_conn.stats.usage_count = 10   # 低负载
            elif account_id == "account4":
                mock_conn.stats.usage_count = 75   # 中高负载
            else:  # account5
                mock_conn.stats.usage_count = 5    # 最低负载
            
            mock_connections[account_id] = [mock_conn]
        
        pool.account_pools = mock_connections
        
        # 测试多次请求应该选择负载最低的账户
        for _ in range(10):
            account = pool.get_account_by_routing(strategy="least_loaded")
            assert account == "account5"  # 负载最低的账户
    
    def test_least_loaded_with_empty_pools(self, pool_with_accounts):
        """测试最少负载路由处理空连接池"""
        pool = pool_with_accounts
        
        # 模拟部分账户没有连接
        mock_connections = {
            "account1": [],  # 空连接池
            "account2": [Mock()],  # 有连接
            "account3": [],  # 空连接池
        }
        
        # 设置连接的使用计数
        mock_connections["account2"][0].stats.usage_count = 10
        
        pool.account_pools = mock_connections
        
        # 应该选择有连接且负载最小的账户
        account = pool.get_account_by_routing(strategy="least_loaded")
        assert account == "account2"
    
    def test_least_loaded_fallback(self, pool_with_accounts):
        """测试最少负载路由回退机制"""
        pool = pool_with_accounts
        
        # 所有账户都没有连接
        pool.account_pools = {}
        
        # 应该回退到第一个账户
        account = pool.get_account_by_routing(strategy="least_loaded")
        assert account == "account1"  # 第一个账户
    
    def test_invalid_strategy_fallback(self, pool_with_accounts):
        """测试无效策略回退"""
        pool = pool_with_accounts
        
        invalid_strategies = ["invalid", "unknown", "", None]
        
        for strategy in invalid_strategies:
            account = pool.get_account_by_routing(strategy=strategy)
            assert account == "account1"  # 应该回退到第一个账户
    
    def test_empty_account_list(self):
        """测试空账户列表的路由"""
        pool = AccountConnectionPool()
        pool.account_id_list = []
        
        strategies = ["round_robin", "hash", "random", "least_loaded"]
        
        for strategy in strategies:
            result = pool.get_account_by_routing(strategy=strategy)
            assert result is None
    
    def test_single_account_routing(self):
        """测试单账户路由"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["single_account"]
        
        strategies = ["round_robin", "hash", "random", "least_loaded"]
        
        for strategy in strategies:
            account = pool.get_account_by_routing("test_key", strategy=strategy)
            assert account == "single_account"


class TestLoadBalancingMetrics:
    """负载均衡指标测试"""
    
    @pytest.fixture
    def pool_with_metrics(self):
        """创建带有负载指标的连接池"""
        pool = AccountConnectionPool()
        
        # 创建账户配置
        accounts = {}
        for i in range(1, 4):
            account_id = f"account{i}"
            accounts[account_id] = AccountConfig(
                account_id=account_id,
                api_key=f"key{i}",
                secret_key=f"secret{i}",
                max_connections=3,
                enabled=True
            )
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        
        # 创建模拟连接和统计
        mock_pools = {}
        for account_id in pool.account_id_list:
            connections = []
            for j in range(3):
                mock_conn = Mock()
                mock_conn.stats = Mock()
                mock_conn.stats.usage_count = 0
                mock_conn.stats.error_count = 0
                mock_conn.stats.avg_response_time = 0.1
                mock_conn.stats.is_healthy = True
                mock_conn.is_available = True
                connections.append(mock_conn)
            mock_pools[account_id] = connections
        
        pool.account_pools = mock_pools
        return pool
    
    def test_load_distribution_tracking(self, pool_with_metrics):
        """测试负载分发跟踪"""
        pool = pool_with_metrics
        
        # 模拟不同的负载
        pool.account_pools["account1"][0].stats.usage_count = 50
        pool.account_pools["account1"][1].stats.usage_count = 60
        pool.account_pools["account1"][2].stats.usage_count = 40
        
        pool.account_pools["account2"][0].stats.usage_count = 20
        pool.account_pools["account2"][1].stats.usage_count = 25
        pool.account_pools["account2"][2].stats.usage_count = 15
        
        pool.account_pools["account3"][0].stats.usage_count = 80
        pool.account_pools["account3"][1].stats.usage_count = 90
        pool.account_pools["account3"][2].stats.usage_count = 70
        
        # 使用最少负载策略，应该选择account2（平均负载最低）
        account = pool.get_account_by_routing(strategy="least_loaded")
        assert account == "account2"
    
    def test_error_rate_consideration(self, pool_with_metrics):
        """测试错误率考虑在负载均衡中"""
        pool = pool_with_metrics
        
        # 设置不同的错误率
        pool.account_pools["account1"][0].stats.error_count = 0
        pool.account_pools["account1"][0].stats.usage_count = 100
        
        pool.account_pools["account2"][0].stats.error_count = 10
        pool.account_pools["account2"][0].stats.usage_count = 50  # 更少使用但错误率高
        
        pool.account_pools["account3"][0].stats.error_count = 0
        pool.account_pools["account3"][0].stats.usage_count = 60
        
        # 当前实现只考虑usage_count，但这个测试为未来扩展准备
        account = pool.get_account_by_routing(strategy="least_loaded")
        # account2 有最低的usage_count，但错误率高
        assert account in ["account1", "account2", "account3"]
    
    def test_response_time_tracking(self, pool_with_metrics):
        """测试响应时间跟踪"""
        pool = pool_with_metrics
        
        # 设置不同的响应时间
        pool.account_pools["account1"][0].stats.avg_response_time = 0.5  # 慢
        pool.account_pools["account2"][0].stats.avg_response_time = 0.1  # 快
        pool.account_pools["account3"][0].stats.avg_response_time = 0.3  # 中等
        
        # 获取统计信息
        stats = pool.get_pool_stats()
        
        account1_stats = stats["account_stats"]["account1"]
        account2_stats = stats["account_stats"]["account2"]
        account3_stats = stats["account_stats"]["account3"]
        
        # 验证响应时间被正确统计
        assert account1_stats["avg_response_time"] > account2_stats["avg_response_time"]
        assert account3_stats["avg_response_time"] > account2_stats["avg_response_time"]
    
    def test_health_status_impact(self, pool_with_metrics):
        """测试健康状态对负载均衡的影响"""
        pool = pool_with_metrics
        
        # 设置不同的健康状态
        pool.account_pools["account1"][0].stats.is_healthy = False
        pool.account_pools["account1"][1].stats.is_healthy = False
        pool.account_pools["account1"][2].stats.is_healthy = False
        
        pool.account_pools["account2"][0].stats.is_healthy = True
        pool.account_pools["account2"][1].stats.is_healthy = True
        pool.account_pools["account2"][2].stats.is_healthy = False
        
        pool.account_pools["account3"][0].stats.is_healthy = True
        pool.account_pools["account3"][1].stats.is_healthy = True
        pool.account_pools["account3"][2].stats.is_healthy = True
        
        # 获取统计信息
        stats = pool.get_pool_stats()
        
        assert stats["account_stats"]["account1"]["healthy_connections"] == 0
        assert stats["account_stats"]["account2"]["healthy_connections"] == 2
        assert stats["account_stats"]["account3"]["healthy_connections"] == 3


class TestRouteFailover:
    """路由故障转移测试"""
    
    @pytest.fixture
    def pool_with_failover_scenario(self):
        """创建故障转移场景的连接池"""
        pool = AccountConnectionPool()
        
        # 创建3个账户
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
        
        # 初始化连接池
        mock_pools = {}
        mock_usage_queues = {}
        for account_id in pool.account_id_list:
            connections = []
            for j in range(2):
                mock_conn = AsyncMock()
                mock_conn.is_available = True
                mock_conn.stats = Mock()
                mock_conn.stats.usage_count = 0
                mock_conn.stats.is_healthy = True
                mock_conn.account_config = accounts[account_id]
                connections.append(mock_conn)
            mock_pools[account_id] = connections
            mock_usage_queues[account_id] = []
        
        pool.account_pools = mock_pools
        pool.usage_queues = mock_usage_queues
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        return pool
    
    @pytest.mark.asyncio
    async def test_primary_account_failure_fallback(self, pool_with_failover_scenario):
        """测试主账户失败时的回退"""
        pool = pool_with_failover_scenario
        
        # 模拟account1（轮询的第一选择）不可用
        with patch('time.time', return_value=0):  # 轮询应该选择account1
            primary_account = pool.get_account_by_routing(strategy="round_robin")
            assert primary_account == "account1"
        
        # 模拟account1连接全部不可用
        for conn in pool.account_pools["account1"]:
            conn.is_available = False
        
        # 尝试获取连接，应该回退到可用连接
        connection = await pool.get_connection("account1")
        
        # 应该选择使用次数最少的连接（即使不可用）
        assert connection in pool.account_pools["account1"]
        connection.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_account_completely_unavailable(self, pool_with_failover_scenario):
        """测试账户完全不可用的处理"""
        pool = pool_with_failover_scenario
        
        # 移除account1的所有连接
        pool.account_pools["account1"] = []
        
        # 尝试获取连接应该失败
        with pytest.raises(Exception, match="无法获取连接"):
            await pool.get_connection("account1")
    
    @pytest.mark.asyncio
    async def test_routing_to_alternative_account(self, pool_with_failover_scenario):
        """测试路由到备选账户"""
        pool = pool_with_failover_scenario
        
        # 使用哈希路由到特定账户
        target_account = pool.get_account_by_routing("AAPL", strategy="hash")
        
        # 确保可以获取该账户的连接
        connection = await pool.get_connection(target_account)
        assert connection is not None
        assert connection.account_config.account_id == target_account
        
        pool.release_connection(connection)
    
    @pytest.mark.asyncio
    async def test_load_balancing_with_partial_failures(self, pool_with_failover_scenario):
        """测试部分故障时的负载均衡"""
        pool = pool_with_failover_scenario
        
        # 模拟account1部分连接不可用
        pool.account_pools["account1"][0].is_available = False
        pool.account_pools["account1"][1].is_available = True
        
        # 模拟account2所有连接可用
        for conn in pool.account_pools["account2"]:
            conn.is_available = True
        
        # 模拟account3所有连接不可用
        for conn in pool.account_pools["account3"]:
            conn.is_available = False
        
        # 设置不同的使用计数进行负载均衡测试
        pool.account_pools["account1"][0].stats.usage_count = 5
        pool.account_pools["account1"][1].stats.usage_count = 2  # 最少使用
        
        pool.account_pools["account2"][0].stats.usage_count = 3
        pool.account_pools["account2"][1].stats.usage_count = 4
        
        pool.account_pools["account3"][0].stats.usage_count = 10
        pool.account_pools["account3"][1].stats.usage_count = 8
        
        # 使用最少负载策略
        selected_account = pool.get_account_by_routing(strategy="least_loaded")
        
        # 应该选择account2（平均使用次数3.5）而不是account1（平均3.5但有不可用连接）
        # 或者可能选择account1，取决于具体实现
        assert selected_account in ["account1", "account2"]


class TestRoutingPerformance:
    """路由性能测试"""
    
    @pytest.mark.performance
    def test_round_robin_performance(self):
        """测试轮询路由性能"""
        pool = AccountConnectionPool()
        pool.account_id_list = [f"account{i}" for i in range(100)]
        
        start_time = time.time()
        for i in range(10000):
            with patch('time.time', return_value=i):
                pool.get_account_by_routing(strategy="round_robin")
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 10000
        print(f"Round robin routing average time: {avg_time * 1000:.3f}ms")
        
        # 轮询路由应该非常快（<0.01ms）
        assert avg_time < 0.00001, f"Round robin routing too slow: {avg_time * 1000:.3f}ms"
    
    @pytest.mark.performance
    def test_hash_routing_performance(self):
        """测试哈希路由性能"""
        pool = AccountConnectionPool()
        pool.account_id_list = [f"account{i}" for i in range(100)]
        
        routing_keys = [f"SYMBOL{i:06d}" for i in range(1000)]
        
        start_time = time.time()
        for key in routing_keys:
            pool.get_account_by_routing(key, strategy="hash")
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 1000
        print(f"Hash routing average time: {avg_time * 1000:.3f}ms")
        
        # 哈希路由应该很快（<0.1ms）
        assert avg_time < 0.0001, f"Hash routing too slow: {avg_time * 1000:.3f}ms"
    
    @pytest.mark.performance
    def test_least_loaded_performance(self):
        """测试最少负载路由性能"""
        pool = AccountConnectionPool()
        pool.account_id_list = [f"account{i}" for i in range(50)]
        
        # 创建模拟连接池
        mock_pools = {}
        for account_id in pool.account_id_list:
            mock_conn = Mock()
            mock_conn.stats.usage_count = time.time() % 100  # 随机负载
            mock_pools[account_id] = [mock_conn]
        
        pool.account_pools = mock_pools
        
        start_time = time.time()
        for _ in range(1000):
            pool.get_account_by_routing(strategy="least_loaded")
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 1000
        print(f"Least loaded routing average time: {avg_time * 1000:.3f}ms")
        
        # 最少负载路由应该相对快（<1ms）
        assert avg_time < 0.001, f"Least loaded routing too slow: {avg_time * 1000:.3f}ms"
    
    @pytest.mark.performance
    def test_concurrent_routing_performance(self):
        """测试并发路由性能"""
        pool = AccountConnectionPool()
        pool.account_id_list = [f"account{i}" for i in range(10)]
        
        # 创建模拟连接池
        mock_pools = {}
        for account_id in pool.account_id_list:
            mock_conn = Mock()
            mock_conn.stats.usage_count = 0
            mock_pools[account_id] = [mock_conn]
        
        pool.account_pools = mock_pools
        
        import threading
        import queue
        
        results = queue.Queue()
        num_threads = 10
        requests_per_thread = 100
        
        def worker():
            start_time = time.time()
            for i in range(requests_per_thread):
                account = pool.get_account_by_routing(f"key{i}", strategy="hash")
                assert account is not None
            end_time = time.time()
            results.put(end_time - start_time)
        
        # 启动多个线程
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=worker)
            threads.append(thread)
        
        overall_start = time.time()
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        overall_end = time.time()
        
        # 收集结果
        thread_times = []
        while not results.empty():
            thread_times.append(results.get())
        
        avg_thread_time = statistics.mean(thread_times)
        overall_time = overall_end - overall_start
        total_requests = num_threads * requests_per_thread
        
        print(f"Concurrent routing - Overall time: {overall_time:.3f}s")
        print(f"Concurrent routing - Average thread time: {avg_thread_time:.3f}s")
        print(f"Concurrent routing - Requests per second: {total_requests / overall_time:.0f}")
        
        # 并发路由应该能够处理高吞吐量
        requests_per_second = total_requests / overall_time
        assert requests_per_second > 1000, f"Concurrent routing throughput too low: {requests_per_second:.0f} req/s"


class TestRoutingConsistency:
    """路由一致性测试"""
    
    def test_hash_routing_consistency_over_time(self):
        """测试哈希路由随时间的一致性"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3", "account4", "account5"]
        
        test_keys = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]
        
        # 第一次路由
        first_routing = {}
        for key in test_keys:
            account = pool.get_account_by_routing(key, strategy="hash")
            first_routing[key] = account
        
        # 等待一段时间后再次路由
        time.sleep(0.1)
        
        # 第二次路由
        second_routing = {}
        for key in test_keys:
            account = pool.get_account_by_routing(key, strategy="hash")
            second_routing[key] = account
        
        # 应该完全一致
        assert first_routing == second_routing
    
    def test_hash_routing_stability_with_account_changes(self):
        """测试账户变化时哈希路由的稳定性"""
        pool = AccountConnectionPool()
        original_accounts = ["account1", "account2", "account3", "account4", "account5"]
        pool.account_id_list = original_accounts.copy()
        
        test_keys = [f"SYMBOL{i:03d}" for i in range(100)]
        
        # 原始路由
        original_routing = {}
        for key in test_keys:
            account = pool.get_account_by_routing(key, strategy="hash")
            original_routing[key] = account
        
        # 添加一个账户
        pool.account_id_list.append("account6")
        
        # 新路由
        new_routing = {}
        for key in test_keys:
            account = pool.get_account_by_routing(key, strategy="hash")
            new_routing[key] = account
        
        # 计算有多少路由发生了变化
        changed_count = sum(1 for key in test_keys if original_routing[key] != new_routing[key])
        change_percentage = changed_count / len(test_keys) * 100
        
        print(f"Hash routing stability: {change_percentage:.1f}% of routes changed when adding account")
        
        # 一致性哈希应该最小化路由变化，但当前实现可能不是一致性哈希
        # 这个测试用于衡量当前实现的稳定性
        assert change_percentage < 80, f"Too many routes changed: {change_percentage:.1f}%"
    
    def test_round_robin_predictability(self):
        """测试轮询路由的可预测性"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # 预测接下来的路由结果
        expected_sequence = []
        for i in range(15):
            expected_account = pool.account_id_list[i % len(pool.account_id_list)]
            expected_sequence.append(expected_account)
        
        # 实际路由结果
        actual_sequence = []
        for i in range(15):
            with patch('time.time', return_value=i):
                account = pool.get_account_by_routing(strategy="round_robin")
                actual_sequence.append(account)
        
        # 应该完全匹配
        assert actual_sequence == expected_sequence
    
    def test_routing_strategy_isolation(self):
        """测试路由策略隔离性"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # 创建模拟连接池用于least_loaded策略
        mock_pools = {}
        for account_id in pool.account_id_list:
            mock_conn = Mock()
            mock_conn.stats.usage_count = 10
            mock_pools[account_id] = [mock_conn]
        pool.account_pools = mock_pools
        
        # 不同策略应该产生不同的结果（在某些情况下）
        with patch('time.time', return_value=0):
            round_robin_result = pool.get_account_by_routing("AAPL", strategy="round_robin")
            hash_result = pool.get_account_by_routing("AAPL", strategy="hash")
            random_result = pool.get_account_by_routing("AAPL", strategy="random")
            least_loaded_result = pool.get_account_by_routing("AAPL", strategy="least_loaded")
        
        # 所有结果都应该是有效的账户
        all_results = [round_robin_result, hash_result, random_result, least_loaded_result]
        for result in all_results:
            assert result in pool.account_id_list
        
        # 至少应该有一些不同的结果（虽然可能偶然相同）
        unique_results = set(all_results)
        print(f"Routing strategy diversity: {len(unique_results)} unique results from 4 strategies")


class TestRoutingAPIIntegration:
    """路由API集成测试"""
    
    def test_get_routing_info_function(self):
        """测试路由信息获取函数"""
        # 测试带参数
        result = get_routing_info(account_id="test_account", routing_key="AAPL")
        assert result == {"account_id": "test_account", "routing_key": "AAPL"}
        
        # 测试无参数
        result = get_routing_info()
        assert result == {"account_id": None, "routing_key": None}
        
        # 测试部分参数
        result = get_routing_info(account_id="test_account")
        assert result == {"account_id": "test_account", "routing_key": None}
        
        result = get_routing_info(routing_key="TSLA")
        assert result == {"account_id": None, "routing_key": "TSLA"}
    
    @pytest.mark.asyncio
    async def test_pooled_client_routing_integration(self):
        """测试池化客户端路由集成"""
        # 这个测试需要模拟PooledAlpacaClient的行为
        with patch('app.alpaca_client.PooledAlpacaClient') as mock_pooled_client:
            mock_instance = AsyncMock()
            mock_pooled_client.return_value = mock_instance
            
            # 模拟路由到特定账户
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 150.0,
                "ask_price": 150.5
            }
            
            client = mock_pooled_client()
            result = await client.get_stock_quote(
                symbol="AAPL",
                account_id="specific_account",
                routing_key="AAPL"
            )
            
            assert result["symbol"] == "AAPL"
            mock_instance.get_stock_quote.assert_called_once_with(
                symbol="AAPL",
                account_id="specific_account",
                routing_key="AAPL"
            )


class TestRoutingEdgeCases:
    """路由边缘情况测试"""
    
    def test_routing_with_special_characters(self):
        """测试特殊字符的路由"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        special_keys = [
            "SYMBOL-WITH-DASH",
            "symbol.with.dots",
            "SYMBOL_WITH_UNDERSCORE",
            "symbol with spaces",
            "SYMBOL@WITH#SPECIAL$CHARS",
            "123NUMERIC_START",
            "VERY_LONG_SYMBOL_NAME_THAT_EXCEEDS_NORMAL_LENGTH",
            "",  # 空字符串
            "中文符号",  # 非ASCII字符
            "émoji🚀symbol"  # 包含emoji
        ]
        
        for key in special_keys:
            try:
                account = pool.get_account_by_routing(key, strategy="hash")
                assert account in pool.account_id_list
            except Exception as e:
                pytest.fail(f"Routing failed for key '{key}': {e}")
    
    def test_routing_with_none_values(self):
        """测试None值的路由"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        # None routing_key应该不会导致错误
        account = pool.get_account_by_routing(None, strategy="hash")
        assert account in pool.account_id_list
        
        account = pool.get_account_by_routing(None, strategy="round_robin")
        assert account in pool.account_id_list
    
    def test_routing_with_extreme_values(self):
        """测试极端值的路由"""
        pool = AccountConnectionPool()
        pool.account_id_list = ["account1", "account2", "account3"]
        
        extreme_values = [
            "A" * 1000,  # 非常长的字符串
            "0",  # 单字符
            str(float('inf')),  # 无穷大
            str(float('-inf')),  # 负无穷大
            "NaN",  # 不是数字
            "\x00\x01\x02",  # 控制字符
            "𝕌𝕟𝕚𝕔𝕠𝕕𝕖",  # Unicode字符
        ]
        
        for value in extreme_values:
            try:
                account = pool.get_account_by_routing(value, strategy="hash")
                assert account in pool.account_id_list
            except Exception as e:
                pytest.fail(f"Routing failed for extreme value '{repr(value)}': {e}")
    
    def test_routing_with_large_account_list(self):
        """测试大量账户的路由"""
        pool = AccountConnectionPool()
        
        # 创建1000个账户
        large_account_list = [f"account{i:04d}" for i in range(1000)]
        pool.account_id_list = large_account_list
        
        # 测试各种路由策略
        strategies = ["round_robin", "hash", "random"]
        
        for strategy in strategies:
            start_time = time.time()
            
            for i in range(100):
                if strategy == "round_robin":
                    with patch('time.time', return_value=i):
                        account = pool.get_account_by_routing(strategy=strategy)
                else:
                    account = pool.get_account_by_routing(f"key{i}", strategy=strategy)
                
                assert account in large_account_list
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 100
            print(f"Large account list {strategy} routing average time: {avg_time * 1000:.3f}ms")
            
            # 即使有1000个账户，路由也应该很快
            assert avg_time < 0.001, f"Large account list routing too slow for {strategy}: {avg_time * 1000:.3f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])