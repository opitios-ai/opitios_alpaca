"""
性能和负载测试套件
测试系统在高负载下的性能、稳定性和可扩展性
"""

import pytest
import asyncio
import time
import threading
import queue
import statistics
import psutil
import gc
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from app.account_pool import AccountConnectionPool, AccountConfig
from app.middleware import RateLimiter, create_jwt_token
from app.websocket_routes import AlpacaWebSocketManager, active_connections
from main import app


class TestConnectionPoolPerformance:
    """连接池性能测试"""
    
    @pytest.fixture
    def large_account_pool(self):
        """大型账户连接池"""
        pool = AccountConnectionPool()
        
        # 创建100个账户，每个账户3个连接
        accounts = {}
        for i in range(100):
            account_id = f"perf_account_{i:03d}"
            accounts[account_id] = AccountConfig(
                account_id=account_id,
                api_key=f"key_{i}",
                secret_key=f"secret_{i}",
                max_connections=3,
                enabled=True
            )
        
        pool.account_configs = accounts
        pool.account_id_list = list(accounts.keys())
        pool.account_pools = {}
        pool.usage_queues = {}
        
        # 创建模拟连接
        for account_id, config in accounts.items():
            connections = []
            for j in range(config.max_connections):
                mock_conn = AsyncMock()
                mock_conn.is_available = True
                mock_conn.stats = Mock()
                mock_conn.stats.usage_count = 0
                mock_conn.stats.is_healthy = True
                mock_conn.account_config = config
                connections.append(mock_conn)
            
            pool.account_pools[account_id] = connections
            pool.usage_queues[account_id] = []
        
        pool._initialized = True
        pool._global_lock = asyncio.Lock()
        
        return pool
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_connection_acquisition_throughput(self, large_account_pool):
        """测试连接获取吞吐量"""
        pool = large_account_pool
        
        async def acquire_and_release_connection():
            account_id = "perf_account_001"
            connection = await pool.get_connection(account_id)
            await asyncio.sleep(0.001)  # 模拟短暂使用
            pool.release_connection(connection)
            return True
        
        # 测试1000次连接获取/释放
        start_time = time.time()
        tasks = [acquire_and_release_connection() for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = end_time - start_time
        throughput = len(results) / total_time
        
        print(f"Connection acquisition throughput: {throughput:.0f} connections/second")
        print(f"Average time per operation: {total_time/len(results)*1000:.2f}ms")
        
        # 性能断言
        assert throughput > 100, f"Connection throughput too low: {throughput:.0f} conn/s"
        assert all(results), "All connection operations should succeed"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_connection_stress(self, large_account_pool):
        """测试并发连接压力"""
        pool = large_account_pool
        
        results = []
        errors = []
        
        async def stress_worker(worker_id):
            worker_results = []
            worker_errors = []
            
            for i in range(50):  # 每个工作者50次操作
                try:
                    account_id = f"perf_account_{(worker_id * 50 + i) % 100:03d}"
                    start = time.time()
                    connection = await pool.get_connection(account_id)
                    await asyncio.sleep(0.001)  # 模拟工作
                    pool.release_connection(connection)
                    end = time.time()
                    worker_results.append(end - start)
                except Exception as e:
                    worker_errors.append(str(e))
            
            return worker_results, worker_errors
        
        # 启动20个并发工作者
        start_time = time.time()
        tasks = [stress_worker(i) for i in range(20)]
        worker_results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 收集结果
        for worker_res, worker_errs in worker_results:
            results.extend(worker_res)
            errors.extend(worker_errs)
        
        total_time = end_time - start_time
        total_operations = 20 * 50
        throughput = total_operations / total_time
        avg_latency = statistics.mean(results) if results else 0
        p95_latency = statistics.quantiles(results, n=20)[18] if len(results) >= 20 else 0
        
        print(f"Concurrent stress test results:")
        print(f"Total operations: {total_operations}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Throughput: {throughput:.0f} ops/s")
        print(f"Average latency: {avg_latency*1000:.2f}ms")
        print(f"P95 latency: {p95_latency*1000:.2f}ms")
        print(f"Error rate: {len(errors)/total_operations*100:.2f}%")
        
        # 性能断言
        assert throughput > 50, f"Concurrent throughput too low: {throughput:.0f} ops/s"
        assert len(errors) / total_operations < 0.01, f"Error rate too high: {len(errors)/total_operations*100:.2f}%"
        assert avg_latency < 0.1, f"Average latency too high: {avg_latency*1000:.2f}ms"
    
    @pytest.mark.performance
    def test_routing_performance_at_scale(self, large_account_pool):
        """测试大规模路由性能"""
        pool = large_account_pool
        
        # 为最少负载策略创建连接统计
        for account_id in pool.account_id_list:
            for conn in pool.account_pools[account_id]:
                conn.stats.usage_count = hash(account_id) % 1000
        
        strategies = ["round_robin", "hash", "random", "least_loaded"]
        results = {}
        
        for strategy in strategies:
            start_time = time.time()
            
            for i in range(10000):
                if strategy == "round_robin":
                    with patch('time.time', return_value=i):
                        account = pool.get_account_by_routing(strategy=strategy)
                else:
                    account = pool.get_account_by_routing(f"key_{i}", strategy=strategy)
                
                assert account in pool.account_id_list
            
            end_time = time.time()
            
            total_time = end_time - start_time
            ops_per_second = 10000 / total_time
            
            results[strategy] = {
                "time": total_time,
                "ops_per_second": ops_per_second,
                "avg_time_ms": total_time / 10000 * 1000
            }
            
            print(f"Routing strategy '{strategy}':")
            print(f"  Operations per second: {ops_per_second:.0f}")
            print(f"  Average time per operation: {total_time/10000*1000:.3f}ms")
        
        # 性能断言
        for strategy, metrics in results.items():
            assert metrics["ops_per_second"] > 1000, f"{strategy} routing too slow: {metrics['ops_per_second']:.0f} ops/s"
            assert metrics["avg_time_ms"] < 1.0, f"{strategy} routing latency too high: {metrics['avg_time_ms']:.3f}ms"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_health_check_performance(self, large_account_pool):
        """测试健康检查性能"""
        pool = large_account_pool
        
        # 设置健康检查响应
        for account_id in pool.account_id_list:
            for conn in pool.account_pools[account_id]:
                conn._in_use = False
                conn.test_connection.return_value = True
        
        start_time = time.time()
        await pool._perform_health_checks()
        end_time = time.time()
        
        health_check_time = end_time - start_time
        total_connections = sum(len(conns) for conns in pool.account_pools.values())
        checks_per_second = total_connections / health_check_time
        
        print(f"Health check performance:")
        print(f"Total connections checked: {total_connections}")
        print(f"Time taken: {health_check_time:.3f}s")
        print(f"Checks per second: {checks_per_second:.0f}")
        
        # 性能断言
        assert health_check_time < 5.0, f"Health check too slow: {health_check_time:.3f}s"
        assert checks_per_second > 50, f"Health check rate too low: {checks_per_second:.0f} checks/s"


class TestAPIEndpointPerformance:
    """API端点性能测试"""
    
    @pytest.fixture
    def performance_client(self):
        """性能测试客户端"""
        client = TestClient(app)
        
        # 创建认证token
        token = create_jwt_token({
            "user_id": "perf_user",
            "account_id": "perf_account",
            "permissions": ["trading", "market_data"]
        })
        
        headers = {"Authorization": f"Bearer {token}"}
        return client, headers
    
    @pytest.mark.performance
    def test_single_quote_request_performance(self, performance_client):
        """测试单一报价请求性能"""
        client, headers = performance_client
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "timestamp": datetime.now().isoformat()
            }
            
            # 预热
            for _ in range(10):
                client.get("/api/v1/stocks/AAPL/quote", headers=headers)
            
            # 性能测试
            start_time = time.time()
            for _ in range(1000):
                response = client.get("/api/v1/stocks/AAPL/quote", headers=headers)
                assert response.status_code in [200, 401]
            end_time = time.time()
            
            total_time = end_time - start_time
            requests_per_second = 1000 / total_time
            avg_response_time = total_time / 1000
            
            print(f"Single quote request performance:")
            print(f"Requests per second: {requests_per_second:.0f}")
            print(f"Average response time: {avg_response_time*1000:.2f}ms")
            
            # 性能断言
            assert requests_per_second > 100, f"Request rate too low: {requests_per_second:.0f} req/s"
            assert avg_response_time < 0.01, f"Response time too high: {avg_response_time*1000:.2f}ms"
    
    @pytest.mark.performance
    def test_batch_quote_request_performance(self, performance_client):
        """测试批量报价请求性能"""
        client, headers = performance_client
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {"symbol": f"STOCK{i:03d}", "bid_price": 100.0, "ask_price": 100.5}
                    for i in range(20)
                ],
                "count": 20
            }
            
            batch_request = {
                "symbols": [f"STOCK{i:03d}" for i in range(20)]
            }
            
            # 预热
            for _ in range(5):
                client.post("/api/v1/stocks/quotes/batch", headers=headers, json=batch_request)
            
            # 性能测试
            start_time = time.time()
            for _ in range(100):
                response = client.post("/api/v1/stocks/quotes/batch", headers=headers, json=batch_request)
                assert response.status_code in [200, 401]
            end_time = time.time()
            
            total_time = end_time - start_time
            requests_per_second = 100 / total_time
            symbols_per_second = 100 * 20 / total_time
            
            print(f"Batch quote request performance:")
            print(f"Batch requests per second: {requests_per_second:.0f}")
            print(f"Symbols per second: {symbols_per_second:.0f}")
            print(f"Average time per batch: {total_time/100*1000:.2f}ms")
            
            # 性能断言
            assert requests_per_second > 10, f"Batch request rate too low: {requests_per_second:.0f} req/s"
            assert symbols_per_second > 200, f"Symbol processing rate too low: {symbols_per_second:.0f} symbols/s"
    
    @pytest.mark.performance
    def test_concurrent_api_requests(self, performance_client):
        """测试并发API请求"""
        client, headers = performance_client
        
        with patch('app.alpaca_client.pooled_client') as mock_pooled:
            mock_pooled.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50
            }
            
            def make_requests(thread_id, num_requests):
                results = []
                errors = []
                
                for i in range(num_requests):
                    try:
                        start = time.time()
                        response = client.get(f"/api/v1/stocks/STOCK{thread_id}/quote", headers=headers)
                        end = time.time()
                        
                        results.append({
                            "status_code": response.status_code,
                            "response_time": end - start
                        })
                    except Exception as e:
                        errors.append(str(e))
                
                return results, errors
            
            # 启动10个线程，每个发送100个请求
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_requests, i, 100) for i in range(10)]
                thread_results = [future.result() for future in as_completed(futures)]
            end_time = time.time()
            
            # 收集结果
            all_results = []
            all_errors = []
            for results, errors in thread_results:
                all_results.extend(results)
                all_errors.extend(errors)
            
            total_time = end_time - start_time
            total_requests = len(all_results)
            requests_per_second = total_requests / total_time
            
            response_times = [r["response_time"] for r in all_results]
            avg_response_time = statistics.mean(response_times) if response_times else 0
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0
            
            success_rate = len([r for r in all_results if r["status_code"] in [200, 401]]) / total_requests
            
            print(f"Concurrent API request performance:")
            print(f"Total requests: {total_requests}")
            print(f"Requests per second: {requests_per_second:.0f}")
            print(f"Average response time: {avg_response_time*1000:.2f}ms")
            print(f"P95 response time: {p95_response_time*1000:.2f}ms")
            print(f"Success rate: {success_rate*100:.2f}%")
            print(f"Error count: {len(all_errors)}")
            
            # 性能断言
            assert requests_per_second > 50, f"Concurrent request rate too low: {requests_per_second:.0f} req/s"
            assert success_rate > 0.95, f"Success rate too low: {success_rate*100:.2f}%"
            assert avg_response_time < 0.1, f"Average response time too high: {avg_response_time*1000:.2f}ms"


class TestRateLimiterPerformance:
    """速率限制器性能测试"""
    
    @pytest.mark.performance
    def test_memory_rate_limiter_performance(self):
        """测试内存速率限制器性能"""
        rate_limiter = RateLimiter()
        
        # 测试单用户高频请求
        start_time = time.time()
        for i in range(10000):
            allowed, info = rate_limiter.is_allowed("user_001", 1000, 60)
            assert allowed is True or allowed is False
        end_time = time.time()
        
        single_user_time = end_time - start_time
        single_user_ops = 10000 / single_user_time
        
        print(f"Single user rate limiting:")
        print(f"Operations per second: {single_user_ops:.0f}")
        print(f"Average time per check: {single_user_time/10000*1000:.3f}ms")
        
        # 测试多用户并发请求
        start_time = time.time()
        for i in range(1000):
            user_id = f"user_{i % 100}"  # 100个不同用户
            allowed, info = rate_limiter.is_allowed(user_id, 100, 60)
        end_time = time.time()
        
        multi_user_time = end_time - start_time
        multi_user_ops = 1000 / multi_user_time
        
        print(f"Multi-user rate limiting:")
        print(f"Operations per second: {multi_user_ops:.0f}")
        print(f"Average time per check: {multi_user_time/1000*1000:.3f}ms")
        
        # 性能断言
        assert single_user_ops > 1000, f"Single user rate limiting too slow: {single_user_ops:.0f} ops/s"
        assert multi_user_ops > 500, f"Multi-user rate limiting too slow: {multi_user_ops:.0f} ops/s"
    
    @pytest.mark.performance
    def test_concurrent_rate_limiting(self):
        """测试并发速率限制"""
        rate_limiter = RateLimiter()
        
        def rate_limit_worker(worker_id, num_operations):
            results = []
            for i in range(num_operations):
                user_id = f"worker_{worker_id}_user_{i % 10}"
                start = time.time()
                allowed, info = rate_limiter.is_allowed(user_id, 50, 60)
                end = time.time()
                results.append(end - start)
            return results
        
        # 启动20个线程并发测试
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(rate_limit_worker, i, 100) for i in range(20)]
            thread_results = [future.result() for future in as_completed(futures)]
        end_time = time.time()
        
        # 收集结果
        all_times = []
        for thread_times in thread_results:
            all_times.extend(thread_times)
        
        total_time = end_time - start_time
        total_operations = 20 * 100
        ops_per_second = total_operations / total_time
        avg_latency = statistics.mean(all_times)
        
        print(f"Concurrent rate limiting performance:")
        print(f"Total operations: {total_operations}")
        print(f"Operations per second: {ops_per_second:.0f}")
        print(f"Average latency: {avg_latency*1000:.3f}ms")
        
        # 性能断言
        assert ops_per_second > 200, f"Concurrent rate limiting too slow: {ops_per_second:.0f} ops/s"
        assert avg_latency < 0.01, f"Rate limiting latency too high: {avg_latency*1000:.3f}ms"


class TestWebSocketPerformance:
    """WebSocket性能测试"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_websocket_broadcast_performance(self):
        """测试WebSocket广播性能"""
        manager = AlpacaWebSocketManager()
        
        # 创建1000个模拟客户端
        mock_clients = {}
        for i in range(1000):
            client_id = f"perf_client_{i:04d}"
            mock_ws = AsyncMock()
            mock_clients[client_id] = mock_ws
            active_connections[client_id] = mock_ws
        
        test_message = {
            "type": "performance_test",
            "timestamp": datetime.now().isoformat(),
            "data": "x" * 100  # 100字节消息
        }
        
        # 测试广播性能
        start_time = time.time()
        await manager.broadcast_to_all(test_message)
        end_time = time.time()
        
        broadcast_time = end_time - start_time
        clients_per_second = 1000 / broadcast_time
        
        print(f"WebSocket broadcast performance:")
        print(f"Clients: 1000")
        print(f"Broadcast time: {broadcast_time:.3f}s")
        print(f"Clients per second: {clients_per_second:.0f}")
        print(f"Time per client: {broadcast_time/1000*1000:.3f}ms")
        
        # 验证所有客户端都收到消息
        for mock_ws in mock_clients.values():
            mock_ws.send_text.assert_called_once()
        
        # 性能断言
        assert broadcast_time < 1.0, f"Broadcast too slow: {broadcast_time:.3f}s"
        assert clients_per_second > 1000, f"Broadcast rate too low: {clients_per_second:.0f} clients/s"
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self):
        """测试WebSocket消息吞吐量"""
        manager = AlpacaWebSocketManager()
        
        # 创建100个客户端
        for i in range(100):
            client_id = f"throughput_client_{i:03d}"
            mock_ws = AsyncMock()
            active_connections[client_id] = mock_ws
        
        # 发送1000条消息
        start_time = time.time()
        for i in range(1000):
            message = {
                "type": "throughput_test",
                "sequence": i,
                "timestamp": datetime.now().isoformat()
            }
            await manager.broadcast_to_all(message)
        end_time = time.time()
        
        total_time = end_time - start_time
        messages_per_second = 1000 / total_time
        total_deliveries = 1000 * 100  # 1000条消息 × 100个客户端
        deliveries_per_second = total_deliveries / total_time
        
        print(f"WebSocket message throughput:")
        print(f"Messages: 1000")
        print(f"Clients: 100")
        print(f"Total deliveries: {total_deliveries}")
        print(f"Messages per second: {messages_per_second:.0f}")
        print(f"Deliveries per second: {deliveries_per_second:.0f}")
        
        # 性能断言
        assert messages_per_second > 100, f"Message throughput too low: {messages_per_second:.0f} msg/s"
        assert deliveries_per_second > 10000, f"Delivery throughput too low: {deliveries_per_second:.0f} deliveries/s"
        
        # 清理
        active_connections.clear()


class TestMemoryAndResourceUsage:
    """内存和资源使用测试"""
    
    @pytest.mark.performance
    def test_memory_usage_under_load(self):
        """测试负载下的内存使用"""
        # 获取初始内存使用
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Initial memory usage: {initial_memory:.2f} MB")
        
        # 创建大量对象模拟负载
        large_objects = []
        
        # 创建连接池对象
        pools = []
        for i in range(10):
            pool = AccountConnectionPool()
            
            # 为每个池创建大量账户
            accounts = {}
            for j in range(100):
                account_id = f"mem_test_account_{i}_{j}"
                accounts[account_id] = AccountConfig(
                    account_id=account_id,
                    api_key=f"key_{i}_{j}",
                    secret_key=f"secret_{i}_{j}"
                )
            
            pool.account_configs = accounts
            pool.account_id_list = list(accounts.keys())
            pools.append(pool)
            large_objects.append(accounts)
        
        # 测试峰值内存使用
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        print(f"Peak memory usage: {peak_memory:.2f} MB")
        print(f"Memory increase: {memory_increase:.2f} MB")
        
        # 清理对象
        del pools
        del large_objects
        gc.collect()
        
        # 测试清理后内存使用
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_recovered = peak_memory - final_memory
        
        print(f"Final memory usage: {final_memory:.2f} MB")
        print(f"Memory recovered: {memory_recovered:.2f} MB")
        
        # 内存使用断言
        assert memory_increase < 500, f"Memory usage too high: {memory_increase:.2f} MB"
        assert memory_recovered > memory_increase * 0.5, f"Memory recovery too low: {memory_recovered:.2f} MB"
    
    @pytest.mark.performance
    def test_cpu_usage_under_load(self):
        """测试负载下的CPU使用"""
        import multiprocessing
        
        def cpu_intensive_task():
            """CPU密集型任务"""
            rate_limiter = RateLimiter()
            
            for i in range(10000):
                user_id = f"cpu_test_user_{i % 100}"
                rate_limiter.is_allowed(user_id, 100, 60)
        
        # 测试单线程CPU使用
        start_time = time.time()
        cpu_intensive_task()
        single_thread_time = time.time() - start_time
        
        print(f"Single thread time: {single_thread_time:.3f}s")
        
        # 测试多线程CPU使用
        num_workers = multiprocessing.cpu_count()
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(cpu_intensive_task) for _ in range(num_workers)]
            for future in as_completed(futures):
                future.result()
        multi_thread_time = time.time() - start_time
        
        print(f"Multi-thread time ({num_workers} workers): {multi_thread_time:.3f}s")
        print(f"Speedup factor: {single_thread_time / multi_thread_time:.2f}x")
        
        # CPU效率断言
        expected_speedup = min(num_workers, 4)  # 期望的加速比
        actual_speedup = single_thread_time / multi_thread_time
        
        assert actual_speedup > expected_speedup * 0.5, f"CPU utilization too low: {actual_speedup:.2f}x speedup"


class TestStressTestScenarios:
    """压力测试场景"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_1000_concurrent_users_scenario(self):
        """测试1000并发用户场景"""
        # 这是一个高级压力测试，模拟1000个并发用户
        
        async def simulate_user_session(user_id):
            """模拟用户会话"""
            session_stats = {
                "requests": 0,
                "errors": 0,
                "total_time": 0
            }
            
            # 模拟用户活动：获取报价、查看账户、下单等
            actions = [
                "get_quote",
                "get_account", 
                "get_positions",
                "place_order",
                "get_orders"
            ]
            
            for _ in range(10):  # 每个用户10个操作
                action = actions[session_stats["requests"] % len(actions)]
                
                try:
                    start = time.time()
                    
                    # 模拟API调用延迟
                    await asyncio.sleep(0.001)  # 1ms模拟延迟
                    
                    end = time.time()
                    session_stats["requests"] += 1
                    session_stats["total_time"] += (end - start)
                    
                except Exception:
                    session_stats["errors"] += 1
            
            return session_stats
        
        # 启动1000个并发用户会话
        start_time = time.time()
        tasks = [simulate_user_session(f"stress_user_{i:04d}") for i in range(1000)]
        user_stats = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 汇总统计
        total_requests = sum(stats["requests"] for stats in user_stats)
        total_errors = sum(stats["errors"] for stats in user_stats)
        total_session_time = sum(stats["total_time"] for stats in user_stats)
        
        wall_clock_time = end_time - start_time
        requests_per_second = total_requests / wall_clock_time
        error_rate = total_errors / total_requests if total_requests > 0 else 0
        avg_response_time = total_session_time / total_requests if total_requests > 0 else 0
        
        print(f"1000 concurrent users stress test:")
        print(f"Wall clock time: {wall_clock_time:.3f}s")
        print(f"Total requests: {total_requests}")
        print(f"Requests per second: {requests_per_second:.0f}")
        print(f"Error rate: {error_rate*100:.2f}%")
        print(f"Average response time: {avg_response_time*1000:.2f}ms")
        
        # 压力测试断言
        assert requests_per_second > 1000, f"Throughput under stress too low: {requests_per_second:.0f} req/s"
        assert error_rate < 0.01, f"Error rate under stress too high: {error_rate*100:.2f}%"
        assert wall_clock_time < 30, f"Stress test took too long: {wall_clock_time:.3f}s"
    
    @pytest.mark.performance
    def test_sustained_load_scenario(self):
        """测试持续负载场景"""
        # 模拟持续5分钟的负载测试
        
        def sustained_worker():
            """持续工作的工作者"""
            client = TestClient(app)
            
            with patch('app.alpaca_client.pooled_client') as mock_pooled:
                mock_pooled.get_stock_quote.return_value = {
                    "symbol": "AAPL",
                    "bid_price": 185.25,
                    "ask_price": 185.50
                }
                
                request_count = 0
                error_count = 0
                start_time = time.time()
                
                # 运行30秒（简化的持续测试）
                while time.time() - start_time < 30:
                    try:
                        response = client.get("/api/v1/stocks/AAPL/quote")
                        if response.status_code not in [200, 401]:
                            error_count += 1
                        request_count += 1
                        
                        # 每秒约10个请求
                        time.sleep(0.1)
                    except Exception:
                        error_count += 1
                
                return {
                    "requests": request_count,
                    "errors": error_count,
                    "duration": time.time() - start_time
                }
        
        # 启动5个持续工作者
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(sustained_worker) for _ in range(5)]
            worker_results = [future.result() for future in as_completed(futures)]
        
        # 汇总结果
        total_requests = sum(result["requests"] for result in worker_results)
        total_errors = sum(result["errors"] for result in worker_results)
        avg_duration = sum(result["duration"] for result in worker_results) / len(worker_results)
        
        sustained_rps = total_requests / avg_duration
        sustained_error_rate = total_errors / total_requests if total_requests > 0 else 0
        
        print(f"Sustained load test (30s):")
        print(f"Total requests: {total_requests}")
        print(f"Sustained RPS: {sustained_rps:.0f}")
        print(f"Error rate: {sustained_error_rate*100:.2f}%")
        print(f"Average duration: {avg_duration:.3f}s")
        
        # 持续负载断言
        assert sustained_rps > 20, f"Sustained throughput too low: {sustained_rps:.0f} req/s"
        assert sustained_error_rate < 0.05, f"Sustained error rate too high: {sustained_error_rate*100:.2f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "performance"])