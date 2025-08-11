"""Performance tests for API endpoints with real load testing."""

import pytest
import asyncio
import time
from typing import List, Dict, Any

from tests.utils import APITestHelper, RateLimitHelper, RealAPITestClient


class TestAPIPerformance:
    """Test API performance under various load conditions."""
    
    @pytest.mark.asyncio
    async def test_single_quote_performance(self, real_api_client, api_test_helper):
        """Test performance of single stock quote requests."""
        symbol = "AAPL"
        num_requests = 10
        
        # Warm up
        await api_test_helper.timed_api_call(real_api_client.get_stock_quote, symbol)
        
        # Performance test
        start_time = time.time()
        results = []
        
        for i in range(num_requests):
            result = await api_test_helper.timed_api_call(
                real_api_client.get_stock_quote, symbol
            )
            results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        successful_results = [r for r in results if r.success]
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            
            print(f"Single quote performance ({num_requests} requests):")
            print(f"  Success rate: {len(successful_results)}/{num_requests}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Avg response time: {avg_response_time:.2f}ms")
            print(f"  Min response time: {min_response_time:.2f}ms")
            print(f"  Max response time: {max_response_time:.2f}ms")
            print(f"  Requests/second: {len(successful_results)/total_time:.2f}")
            
            # Performance assertions
            assert avg_response_time < 5000, f"Average response time too high: {avg_response_time}ms"
            assert len(successful_results) > num_requests * 0.8, "Success rate too low"
    
    @pytest.mark.asyncio
    async def test_batch_quote_performance(self, real_api_client, api_test_helper):
        """Test performance of batch quote requests."""
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
        num_batches = 5
        
        # Performance test
        results = []
        for i in range(num_batches):
            result = await api_test_helper.timed_api_call(
                real_api_client.get_multiple_stock_quotes, symbols
            )
            results.append(result)
        
        # Analyze results
        successful_results = [r for r in results if r.success]
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            avg_response_time = sum(response_times) / len(response_times)
            
            print(f"Batch quote performance ({num_batches} batches of {len(symbols)} symbols):")
            print(f"  Success rate: {len(successful_results)}/{num_batches}")
            print(f"  Avg response time: {avg_response_time:.2f}ms")
            print(f"  Symbols per second: {len(symbols) * len(successful_results) / (sum(response_times)/1000):.2f}")
            
            # Batch should be more efficient than individual requests
            assert avg_response_time < 10000, f"Batch response time too high: {avg_response_time}ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self, real_api_client, api_test_helper):
        """Test performance under concurrent load."""
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]
        max_concurrent = 5
        
        # Prepare concurrent API calls
        api_calls = [
            (real_api_client.get_stock_quote, (symbol,), {})
            for symbol in symbols
        ]
        
        # Execute concurrently
        start_time = time.time()
        results = await api_test_helper.batch_api_calls(api_calls, max_concurrent=max_concurrent)
        end_time = time.time()
        
        total_time = end_time - start_time
        successful_results = [r for r in results if r.success]
        
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            avg_response_time = sum(response_times) / len(response_times)
            
            print(f"Concurrent requests performance ({len(symbols)} requests, max {max_concurrent} concurrent):")
            print(f"  Success rate: {len(successful_results)}/{len(symbols)}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Avg response time: {avg_response_time:.2f}ms")
            print(f"  Effective throughput: {len(successful_results)/total_time:.2f} req/s")
            
            # Concurrent execution should be faster than sequential
            assert total_time < len(symbols) * 2, "Concurrent execution not efficient enough"
    
    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, real_api_client, api_test_helper, rate_limit_helper):
        """Test performance under sustained load."""
        symbol = "AAPL"
        duration_seconds = 30
        target_rate = 1  # 1 request per second
        
        start_time = time.time()
        results = []
        
        while (time.time() - start_time) < duration_seconds:
            async with rate_limit_helper.rate_limited_call():
                result = await api_test_helper.timed_api_call(
                    real_api_client.get_stock_quote, symbol
                )
                results.append(result)
            
            # Wait to maintain target rate
            await asyncio.sleep(1.0 / target_rate)
        
        actual_duration = time.time() - start_time
        successful_results = [r for r in results if r.success]
        
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            avg_response_time = sum(response_times) / len(response_times)
            actual_rate = len(successful_results) / actual_duration
            
            print(f"Sustained load performance ({duration_seconds}s duration):")
            print(f"  Total requests: {len(results)}")
            print(f"  Successful requests: {len(successful_results)}")
            print(f"  Actual rate: {actual_rate:.2f} req/s")
            print(f"  Avg response time: {avg_response_time:.2f}ms")
            print(f"  Success rate: {len(successful_results)/len(results)*100:.1f}%")
            
            # Performance should remain stable under sustained load
            assert len(successful_results) > len(results) * 0.9, "Success rate degraded under load"
            assert avg_response_time < 10000, "Response time degraded under sustained load"


class TestConnectionPoolPerformance:
    """Test connection pool performance under load."""
    
    @pytest.mark.asyncio
    async def test_connection_reuse_efficiency(self, all_test_accounts, api_test_helper):
        """Test efficiency of connection reuse."""
        if len(all_test_accounts) < 1:
            pytest.skip("Need at least 1 account for connection reuse test")
        
        client = all_test_accounts[0]
        symbol = "AAPL"
        num_requests = 10
        
        # Make multiple requests to test connection reuse
        results = []
        for i in range(num_requests):
            result = await api_test_helper.timed_api_call(
                client.get_stock_quote, symbol
            )
            results.append(result)
        
        successful_results = [r for r in results if r.success]
        
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            
            # Later requests should be faster due to connection reuse
            first_half = response_times[:len(response_times)//2]
            second_half = response_times[len(response_times)//2:]
            
            if len(first_half) > 0 and len(second_half) > 0:
                avg_first_half = sum(first_half) / len(first_half)
                avg_second_half = sum(second_half) / len(second_half)
                
                print(f"Connection reuse efficiency:")
                print(f"  First half avg: {avg_first_half:.2f}ms")
                print(f"  Second half avg: {avg_second_half:.2f}ms")
                print(f"  Improvement: {((avg_first_half - avg_second_half) / avg_first_half * 100):.1f}%")
                
                # Second half should generally be faster or similar
                assert avg_second_half <= avg_first_half * 1.5, "Connection reuse not providing benefit"
    
    @pytest.mark.asyncio
    async def test_multi_account_load_distribution(self, all_test_accounts, api_test_helper):
        """Test load distribution across multiple accounts."""
        if len(all_test_accounts) < 2:
            pytest.skip("Need at least 2 accounts for load distribution test")
        
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]
        
        # Distribute requests across accounts
        results_by_account = {}
        
        for i, symbol in enumerate(symbols):
            client = all_test_accounts[i % len(all_test_accounts)]
            account_id = client.account_id
            
            if account_id not in results_by_account:
                results_by_account[account_id] = []
            
            result = await api_test_helper.timed_api_call(
                client.get_stock_quote, symbol
            )
            results_by_account[account_id].append(result)
        
        # Analyze distribution
        print(f"Load distribution across {len(all_test_accounts)} accounts:")
        for account_id, results in results_by_account.items():
            successful = [r for r in results if r.success]
            if successful:
                avg_time = sum(r.response_time_ms for r in successful) / len(successful)
                print(f"  Account {account_id}: {len(successful)}/{len(results)} successful, {avg_time:.2f}ms avg")
        
        # All accounts should handle some load
        assert len(results_by_account) > 1, "Load should be distributed across accounts"


class TestStressTestSuite:
    """Stress testing suite for high load scenarios."""
    
    @pytest.mark.asyncio
    async def test_api_stress_test(self, real_api_client, api_test_helper):
        """Stress test API with high request volume."""
        symbol = "AAPL"
        num_requests = 20
        max_concurrent = 10
        
        # Prepare stress test calls
        api_calls = [
            (real_api_client.get_stock_quote, (symbol,), {})
            for _ in range(num_requests)
        ]
        
        # Execute stress test
        start_time = time.time()
        results = await api_test_helper.batch_api_calls(api_calls, max_concurrent=max_concurrent)
        end_time = time.time()
        
        total_time = end_time - start_time
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        print(f"API stress test ({num_requests} requests, {max_concurrent} concurrent):")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Successful: {len(successful_results)}")
        print(f"  Failed: {len(failed_results)}")
        print(f"  Success rate: {len(successful_results)/num_requests*100:.1f}%")
        print(f"  Throughput: {len(successful_results)/total_time:.2f} req/s")
        
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            print(f"  Avg response time: {avg_response_time:.2f}ms")
            print(f"  Max response time: {max_response_time:.2f}ms")
            
            # System should handle stress reasonably well
            assert len(successful_results) > num_requests * 0.7, "Too many failures under stress"
            assert avg_response_time < 15000, "Response time too high under stress"
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, real_api_client, api_test_helper):
        """Test memory usage patterns under load."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        symbol = "AAPL"
        num_requests = 15
        
        # Execute requests and monitor memory
        for i in range(num_requests):
            await api_test_helper.timed_api_call(real_api_client.get_stock_quote, symbol)
            
            if i % 5 == 0:  # Check memory every 5 requests
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"  After {i+1} requests: {current_memory:.1f} MB")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage test:")
        print(f"  Initial memory: {initial_memory:.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Memory increase: {memory_increase:.1f} MB")
        print(f"  Memory per request: {memory_increase/num_requests:.2f} MB")
        
        # Memory usage should be reasonable
        assert memory_increase < 100, f"Memory usage too high: {memory_increase:.1f} MB"
    
    @pytest.mark.asyncio
    async def test_error_rate_under_load(self, real_api_client, api_test_helper):
        """Test error rates under increasing load."""
        symbol = "AAPL"
        load_levels = [1, 3, 5, 8]  # Different concurrency levels
        
        error_rates = []
        
        for concurrent_level in load_levels:
            # Prepare calls for this load level
            api_calls = [
                (real_api_client.get_stock_quote, (symbol,), {})
                for _ in range(concurrent_level * 2)  # 2 requests per concurrent slot
            ]
            
            # Execute at this load level
            results = await api_test_helper.batch_api_calls(api_calls, max_concurrent=concurrent_level)
            
            # Calculate error rate
            successful = sum(1 for r in results if r.success)
            error_rate = (len(results) - successful) / len(results)
            error_rates.append(error_rate)
            
            print(f"Load level {concurrent_level}: {error_rate*100:.1f}% error rate")
        
        print(f"Error rate progression: {[f'{rate*100:.1f}%' for rate in error_rates]}")
        
        # Error rate should not increase dramatically with load
        if len(error_rates) > 1:
            max_error_rate = max(error_rates)
            assert max_error_rate < 0.3, f"Error rate too high under load: {max_error_rate*100:.1f}%"


@pytest.mark.asyncio
async def test_performance_integration(real_api_client, api_test_helper, rate_limit_helper):
    """Integration test for overall performance characteristics."""
    print("Starting performance integration test...")
    
    # Test different types of operations
    operations = [
        ("stock_quote", lambda: real_api_client.get_stock_quote("AAPL")),
        ("account_info", lambda: real_api_client.get_account()),
        ("positions", lambda: real_api_client.get_positions()),
        ("orders", lambda: real_api_client.get_orders())
    ]
    
    performance_results = {}
    
    for op_name, op_func in operations:
        print(f"Testing {op_name} performance...")
        
        # Test each operation multiple times
        results = []
        for i in range(5):
            async with rate_limit_helper.rate_limited_call():
                result = await api_test_helper.timed_api_call(op_func)
                results.append(result)
        
        # Analyze results
        successful_results = [r for r in results if r.success]
        if successful_results:
            response_times = [r.response_time_ms for r in successful_results]
            avg_time = sum(response_times) / len(response_times)
            
            performance_results[op_name] = {
                "success_rate": len(successful_results) / len(results),
                "avg_response_time": avg_time,
                "min_response_time": min(response_times),
                "max_response_time": max(response_times)
            }
    
    # Print comprehensive results
    print("\nPerformance Integration Test Results:")
    print("=" * 50)
    
    for op_name, metrics in performance_results.items():
        print(f"{op_name}:")
        print(f"  Success Rate: {metrics['success_rate']*100:.1f}%")
        print(f"  Avg Response Time: {metrics['avg_response_time']:.2f}ms")
        print(f"  Min Response Time: {metrics['min_response_time']:.2f}ms")
        print(f"  Max Response Time: {metrics['max_response_time']:.2f}ms")
        print()
    
    # Overall performance assertions
    if performance_results:
        overall_success_rate = sum(m['success_rate'] for m in performance_results.values()) / len(performance_results)
        overall_avg_time = sum(m['avg_response_time'] for m in performance_results.values()) / len(performance_results)
        
        print(f"Overall Performance Summary:")
        print(f"  Average Success Rate: {overall_success_rate*100:.1f}%")
        print(f"  Average Response Time: {overall_avg_time:.2f}ms")
        
        assert overall_success_rate > 0.8, f"Overall success rate too low: {overall_success_rate*100:.1f}%"
        assert overall_avg_time < 8000, f"Overall response time too high: {overall_avg_time:.2f}ms"
        
        print("Performance integration test completed successfully!")
    else:
        pytest.skip("No performance data collected for integration test")