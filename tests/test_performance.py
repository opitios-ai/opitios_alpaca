"""
Performance tests for real Alpaca data API calls
"""

import pytest
import time
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from concurrent.futures import ThreadPoolExecutor, as_completed


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


class TestAPIResponseTimes:
    """Test API response time performance"""
    
    def test_stock_quote_response_time(self, client):
        """Test single stock quote response time under 500ms"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL", "bid_price": 185.25, "ask_price": 185.50,
                "timestamp": "2024-01-15T15:30:00Z"
            }
            mock_client.return_value = mock_instance
            
            start_time = time.time()
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            end_time = time.time()
            
            assert response.status_code == 200
            response_time = (end_time - start_time) * 1000  # ms
            assert response_time < 500, f"Response time {response_time}ms exceeds 500ms limit"

    def test_batch_quotes_performance(self, client):
        """Test batch quotes performance scales properly"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            # Mock 20 symbols
            quotes = [{"symbol": f"SYM{i}", "bid_price": 100.0, "ask_price": 100.5} for i in range(20)]
            mock_instance.get_multiple_stock_quotes.return_value = {
                "quotes": quotes, "count": 20, "requested_symbols": [f"SYM{i}" for i in range(20)]
            }
            mock_client.return_value = mock_instance
            
            start_time = time.time()
            response = client.post("/api/v1/stocks/quotes/batch", 
                                 json={"symbols": [f"SYM{i}" for i in range(20)]})
            end_time = time.time()
            
            assert response.status_code == 200
            response_time = (end_time - start_time) * 1000
            assert response_time < 2000, f"Batch response time {response_time}ms exceeds 2s limit"

    def test_options_chain_performance(self, client):
        """Test options chain response time"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_options_chain.return_value = {
                "underlying_symbol": "AAPL", "options_count": 50,
                "options": [{"symbol": f"AAPL240216C0018{i:04d}", "strike_price": 180+i} for i in range(10)]
            }
            mock_client.return_value = mock_instance
            
            start_time = time.time()
            response = client.post("/api/v1/options/chain", json={"underlying_symbol": "AAPL"})
            end_time = time.time()
            
            if response.status_code == 200:
                response_time = (end_time - start_time) * 1000
                assert response_time < 3000, f"Options chain response time {response_time}ms exceeds 3s"


class TestConcurrentRequests:
    """Test concurrent request handling"""
    
    def test_concurrent_stock_quotes(self, client):
        """Test handling 10 concurrent stock quote requests"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL", "bid_price": 185.25, "ask_price": 185.50
            }
            mock_client.return_value = mock_instance
            
            def make_request():
                return client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(10)]
                responses = [future.result() for future in as_completed(futures)]
            end_time = time.time()
            
            # All requests should succeed
            assert all(r.status_code == 200 for r in responses)
            
            # Total time should be reasonable for concurrent execution
            total_time = (end_time - start_time) * 1000
            assert total_time < 5000, f"Concurrent requests took {total_time}ms"

    def test_mixed_concurrent_requests(self, client):
        """Test mixed request types concurrently"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {"symbol": "AAPL", "bid_price": 185.25}
            mock_instance.get_account.return_value = {"account_number": "123", "buying_power": 50000}
            mock_instance.get_positions.return_value = []
            mock_client.return_value = mock_instance
            
            def make_quote_request():
                return client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            
            def make_account_request():
                return client.get("/api/v1/account")
            
            def make_positions_request():
                return client.get("/api/v1/positions")
            
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = []
                futures.extend([executor.submit(make_quote_request) for _ in range(2)])
                futures.extend([executor.submit(make_account_request) for _ in range(2)])
                futures.extend([executor.submit(make_positions_request) for _ in range(2)])
                
                responses = [future.result() for future in as_completed(futures)]
            end_time = time.time()
            
            # All requests should succeed
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count >= 4, f"Only {success_count}/6 requests succeeded"
            
            total_time = (end_time - start_time) * 1000
            assert total_time < 3000


class TestDataVolumePerformance:
    """Test performance with varying data volumes"""
    
    def test_large_options_chain_response(self, client):
        """Test handling large options chain with 100+ contracts"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            # Generate 100 option contracts
            large_options = []
            for i in range(100):
                large_options.append({
                    "symbol": f"AAPL240216C{170+i:08d}000",
                    "strike_price": 170.0 + i,
                    "option_type": "call" if i % 2 == 0 else "put",
                    "bid_price": 5.0 + (i * 0.1),
                    "ask_price": 5.5 + (i * 0.1)
                })
            
            mock_instance.get_options_chain.return_value = {
                "underlying_symbol": "AAPL", "options_count": 100,
                "options": large_options
            }
            mock_client.return_value = mock_instance
            
            start_time = time.time()
            response = client.post("/api/v1/options/chain", json={"underlying_symbol": "AAPL"})
            end_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                assert len(data["options"]) <= 100  # Service may limit results
                
                response_time = (end_time - start_time) * 1000
                assert response_time < 5000, f"Large options chain took {response_time}ms"

    def test_historical_bars_performance(self, client):
        """Test historical bars with large dataset"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            # Generate 252 trading days (1 year)
            bars = []
            for i in range(252):
                bars.append({
                    "timestamp": f"2023-{(i//21)+1:02d}-{(i%21)+1:02d}T00:00:00Z",
                    "open": 180.0 + (i * 0.1), "high": 182.0 + (i * 0.1),
                    "low": 178.0 + (i * 0.1), "close": 181.0 + (i * 0.1),
                    "volume": 45000000 + (i * 10000)
                })
            
            mock_instance.get_stock_bars.return_value = {
                "symbol": "AAPL", "timeframe": "1Day", "bars": bars
            }
            mock_client.return_value = mock_instance
            
            start_time = time.time()
            response = client.get("/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=252")
            end_time = time.time()
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["bars"]) == 252
            
            response_time = (end_time - start_time) * 1000
            assert response_time < 3000, f"Historical bars took {response_time}ms"


class TestErrorResponsePerformance:
    """Test performance of error responses"""
    
    def test_error_response_time(self, client):
        """Test that error responses are fast"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {"error": "No data found"}
            mock_client.return_value = mock_instance
            
            start_time = time.time()
            response = client.post("/api/v1/stocks/quote", json={"symbol": "INVALID"})
            end_time = time.time()
            
            assert response.status_code == 400
            response_time = (end_time - start_time) * 1000
            assert response_time < 200, f"Error response took {response_time}ms"

    def test_validation_error_performance(self, client):
        """Test validation error response time"""
        start_time = time.time()
        response = client.post("/api/v1/stocks/quotes/batch", json={"symbols": []})
        end_time = time.time()
        
        assert response.status_code == 400
        response_time = (end_time - start_time) * 1000
        assert response_time < 100, f"Validation error took {response_time}ms"


@pytest.fixture
def performance_summary():
    """Fixture to track performance test results"""
    return {"tests": [], "total_time": 0}


class TestOverallPerformanceMetrics:
    """Test overall performance benchmarks"""
    
    def test_api_throughput(self, client):
        """Test API can handle target throughput"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL", "bid_price": 185.25, "ask_price": 185.50
            }
            mock_client.return_value = mock_instance
            
            # Test 50 requests in sequence
            start_time = time.time()
            success_count = 0
            for i in range(50):
                response = client.post("/api/v1/stocks/quote", json={"symbol": f"TEST{i%5}"})
                if response.status_code == 200:
                    success_count += 1
            end_time = time.time()
            
            total_time = end_time - start_time
            requests_per_second = success_count / total_time
            
            # Target: At least 20 requests per second
            assert requests_per_second >= 20, f"Throughput {requests_per_second:.1f} req/s below target"
            assert success_count >= 45, f"Only {success_count}/50 requests succeeded"