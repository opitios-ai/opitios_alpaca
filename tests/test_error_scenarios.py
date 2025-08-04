"""
Error scenario tests for Alpaca service - focused on real data unavailability handling
Tests ensure proper error responses when real market data is not available
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json
from datetime import datetime


@pytest.fixture
def client():
    """Create test client for FastAPI app"""
    from main import app
    return TestClient(app)


class TestAlpacaAPIConnectivityErrors:
    """Test error handling when Alpaca API is unavailable"""
    
    def test_connection_failure_returns_proper_error(self, client):
        """Test connection failure returns error without fallback"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.test_connection.return_value = {
                "status": "failed",
                "error": "Connection to Alpaca API failed: Network timeout"
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/test-connection")
            assert response.status_code == 500
            
            data = response.json()
            assert "Connection to Alpaca API failed" in data["detail"]
            
            # Verify no fallback connection provided
            assert "offline_mode" not in str(data)
            assert "cached_connection" not in str(data)
            assert "backup_api" not in str(data)

    def test_api_key_invalid_error_handling(self, client):
        """Test invalid API key error handling"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.test_connection.return_value = {
                "status": "failed", 
                "error": "Invalid API credentials"
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/test-connection")
            assert response.status_code == 500
            
            data = response.json()
            assert "Invalid API credentials" in data["detail"]
            
            # Verify no test credentials suggested
            assert "demo_mode" not in str(data)
            assert "sample_credentials" not in str(data)

    def test_rate_limiting_error_handling(self, client):
        """Test rate limiting error handling without retry mechanisms"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.side_effect = Exception("Rate limit exceeded")
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 500
            
            data = response.json()
            assert "Rate limit exceeded" in data["detail"]
            
            # Verify no retry suggestions or cached data
            assert "retry_after" not in str(data)
            assert "cached_quote" not in str(data)
            assert "fallback_provider" not in str(data)


class TestDataUnavailabilityScenarios:
    """Test scenarios where real market data is not available"""
    
    def test_nonexistent_stock_symbol_handling(self, client):
        """Test handling of nonexistent stock symbols"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "No quote data found for FAKESYMBOL"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "FAKESYMBOL"})
            assert response.status_code == 400
            
            data = response.json()
            assert "No quote data found for FAKESYMBOL" in data["detail"]
            
            # Verify no symbol suggestions or alternatives
            assert "similar_symbols" not in str(data)
            assert "did_you_mean" not in str(data)
            assert "suggested_alternatives" not in str(data)

    def test_delisted_stock_handling(self, client):
        """Test handling of delisted stocks"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "Symbol DELISTED no longer available for trading"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "DELISTED"})
            assert response.status_code == 400
            
            data = response.json()
            assert "no longer available for trading" in data["detail"]
            
            # Verify no historical data fallback
            assert "last_traded_price" not in str(data)
            assert "historical_quote" not in str(data)

    def test_options_unavailable_for_underlying(self, client):
        """Test handling when options are not available for underlying stock"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_options_chain.return_value = {
                "error": "No real options chain data available for PENNY_STOCK"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/chain", 
                                 json={"underlying_symbol": "PENNY_STOCK"})
            assert response.status_code == 404
            
            data = response.json()
            error_detail = data["detail"]
            assert "No real options chain data available" in error_detail["error"]
            assert error_detail["error_code"] == "OPTIONS_CHAIN_UNAVAILABLE"
            
            # Verify no synthetic options provided
            assert "synthetic_chain" not in str(data)
            assert "estimated_options" not in str(data)
            assert "calculated_strikes" not in str(data)

    def test_expired_option_contract_handling(self, client):
        """Test handling of expired option contracts"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_option_quote.return_value = {
                "error": "Option contract AAPL230120C00150000 has expired"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quote", 
                                 json={"option_symbol": "AAPL230120C00150000"})
            assert response.status_code == 404
            
            data = response.json()
            error_detail = data["detail"]
            assert "has expired" in error_detail["error"] or "No real market data available" in error_detail["error"]
            
            # Verify no historical option data provided
            assert "expiration_value" not in str(data)
            assert "final_settlement" not in str(data)

    def test_illiquid_option_no_quotes_available(self, client):
        """Test handling of illiquid options with no real quotes"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_option_quote.return_value = {
                "error": "No real market data available for option symbol: AAPL241201C00500000"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quote", 
                                 json={"option_symbol": "AAPL241201C00500000"})
            assert response.status_code == 404
            
            data = response.json()
            error_detail = data["detail"]
            assert "No real market data available" in error_detail["error"]
            assert error_detail["error_code"] == "REAL_DATA_UNAVAILABLE"
            
            # Verify no theoretical pricing provided
            assert "theoretical_bid" not in str(data)
            assert "estimated_price" not in str(data)
            assert "black_scholes_value" not in str(data)


class TestMarketHoursAndTradingRestrictions:
    """Test market hours and trading restriction scenarios"""
    
    def test_after_hours_data_unavailability(self, client):
        """Test after hours when real-time data may be unavailable"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "Real-time quotes not available outside market hours"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 400
            
            data = response.json()
            assert "not available outside market hours" in data["detail"]
            
            # Verify no after-hours estimates provided
            assert "extended_hours_price" not in str(data)
            assert "pre_market_price" not in str(data)
            assert "previous_close" not in str(data)

    def test_weekend_market_closed_handling(self, client):
        """Test weekend/holiday market closed scenarios"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "Market is closed - no current quotes available"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 400
            
            data = response.json()
            assert "Market is closed" in data["detail"]
            
            # Verify no stale data provided
            assert "last_friday_close" not in str(data)
            assert "stale_quote" not in str(data)

    def test_halted_stock_trading_suspension(self, client):
        """Test handling of halted/suspended stocks"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "Trading halted for HALTED_STOCK - no quotes available"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "HALTED_STOCK"})
            assert response.status_code == 400
            
            data = response.json()
            assert "Trading halted" in data["detail"]
            
            # Verify no pre-halt quotes provided
            assert "pre_halt_price" not in str(data)
            assert "last_trade_before_halt" not in str(data)


class TestDataQualityAndValidation:
    """Test data quality validation and error handling"""
    
    def test_malformed_api_response_handling(self, client):
        """Test handling of malformed responses from Alpaca API"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.side_effect = Exception("Malformed response from Alpaca API")
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 500
            
            data = response.json()
            assert "Malformed response from Alpaca API" in data["detail"]
            
            # Verify no data reconstruction attempted
            assert "reconstructed_quote" not in str(data)
            assert "estimated_values" not in str(data)

    def test_invalid_option_symbol_format_rejection(self, client):
        """Test rejection of invalid option symbol formats"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_option_quote.return_value = {
                "error": "Invalid option symbol format: INVALID_FORMAT"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quote", 
                                 json={"option_symbol": "INVALID_FORMAT"})
            assert response.status_code == 404
            
            data = response.json()
            error_detail = data["detail"]
            assert "Invalid option symbol format" in error_detail["error"]
            
            # Verify no format correction attempted
            assert "corrected_symbol" not in str(data)
            assert "suggested_format" not in str(data)

    def test_partial_quote_data_rejection(self, client):
        """Test rejection of partial/incomplete quote data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            # Simulate partial data where only bid is available
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": None,  # Missing ask price
                "bid_size": 100,
                "ask_size": None,   # Missing ask size
                "timestamp": datetime.now().isoformat()
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            # This should still succeed as partial data is valid from Alpaca
            assert response.status_code == 200
            
            data = response.json()
            assert data["bid_price"] == 185.25
            assert data["ask_price"] is None
            
            # Verify no data interpolation
            assert "interpolated_ask" not in data
            assert "estimated_spread" not in data


class TestBatchRequestErrorHandling:
    """Test error handling in batch requests"""
    
    def test_batch_stock_quotes_partial_failures(self, client):
        """Test batch stock quotes with partial failures"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL",
                        "bid_price": 185.25,
                        "ask_price": 185.50
                    },
                    {
                        "symbol": "INVALID1",
                        "error": "No quote data found for INVALID1"
                    },
                    {
                        "symbol": "DELISTED2", 
                        "error": "Symbol no longer available"
                    }
                ],
                "count": 3,
                "requested_symbols": ["AAPL", "INVALID1", "DELISTED2"]
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quotes/batch", 
                                 json={"symbols": ["AAPL", "INVALID1", "DELISTED2"]})
            assert response.status_code == 200
            
            data = response.json()
            assert data["count"] == 3
            
            # Verify failed symbols have no fallback data
            failed_quotes = [q for q in data["quotes"] if "error" in q]
            assert len(failed_quotes) == 2
            
            for failed_quote in failed_quotes:
                assert "fallback_price" not in failed_quote
                assert "estimated_quote" not in failed_quote

    def test_batch_option_quotes_all_failures(self, client):
        """Test batch option quotes when all requests fail"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_multiple_option_quotes.return_value = {
                "quotes": [
                    {"error": "No real market data available for FAKE1"},
                    {"error": "Invalid option symbol format: FAKE2"},
                    {"error": "Option contract expired: FAKE3"}
                ],
                "count": 3,
                "successful_count": 0,
                "failed_count": 3,
                "requested_symbols": ["FAKE1", "FAKE2", "FAKE3"],
                "failed_symbols": ["FAKE1", "FAKE2", "FAKE3"]
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quotes/batch", 
                                 json={"option_symbols": ["FAKE1", "FAKE2", "FAKE3"]})
            assert response.status_code == 200
            
            data = response.json()
            assert data["successful_count"] == 0
            assert data["failed_count"] == 3
            assert len(data["failed_symbols"]) == 3
            
            # Verify no synthetic quotes provided
            for quote in data["quotes"]:
                assert "error" in quote
                assert "synthetic_data" not in quote

    def test_batch_request_size_limit_enforcement(self, client):
        """Test batch request size limits are enforced"""
        # Test exceeding maximum symbols per request
        too_many_symbols = [f"SYMBOL{i}" for i in range(101)]  # Assuming limit is 100
        
        response = client.post("/api/v1/stocks/quotes/batch", 
                             json={"symbols": too_many_symbols})
        assert response.status_code == 400
        
        data = response.json()
        assert "Maximum" in data["detail"]
        assert "symbols allowed" in data["detail"]
        
        # Verify no partial processing
        assert "partial_results" not in str(data)
        assert "truncated_request" not in str(data)


class TestServiceUnavailabilityScenarios:
    """Test complete service unavailability scenarios"""
    
    def test_alpaca_service_completely_down(self, client):
        """Test when Alpaca service is completely unavailable"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_client.side_effect = Exception("Alpaca service unavailable")
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 500
            
            data = response.json()
            assert "Alpaca service unavailable" in data["detail"]
            
            # Verify no backup service used
            assert "backup_provider" not in str(data)
            assert "alternative_source" not in str(data)

    def test_network_connectivity_issues(self, client):
        """Test network connectivity issues"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.side_effect = Exception("Network timeout")
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 500
            
            data = response.json()
            assert "Network timeout" in data["detail"]
            
            # Verify no cached responses served
            assert "cached_response" not in str(data)
            assert "offline_data" not in str(data)