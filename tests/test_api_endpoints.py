"""
Integration tests for API endpoints - focused on verifying no mock data is returned
Tests ensure all endpoints return only real Alpaca market data
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


@pytest.fixture
def mock_alpaca_responses():
    """Mock Alpaca API responses with real-like data structure"""
    return {
        "account": {
            "account_number": "TEST123456789",
            "buying_power": "50000.00",
            "cash": "25000.00", 
            "portfolio_value": "75000.00",
            "equity": "75000.00",
            "last_equity": "74500.00",
            "multiplier": "4",
            "pattern_day_trader": False
        },
        "stock_quote": {
            "symbol": "AAPL",
            "bid_price": 185.25,
            "ask_price": 185.50,
            "bid_size": 100,
            "ask_size": 200,
            "timestamp": datetime.now().isoformat()
        },
        "options_chain": {
            "underlying_symbol": "AAPL",
            "underlying_price": 185.0,
            "expiration_dates": ["2024-03-15", "2024-04-19"],
            "options_count": 45,
            "quote_failures": 5,
            "options": [
                {
                    "symbol": "AAPL240315C00180000",
                    "underlying_symbol": "AAPL", 
                    "strike_price": 180.0,
                    "expiration_date": "2024-03-15",
                    "option_type": "call",
                    "bid_price": 8.25,
                    "ask_price": 8.50
                }
            ]
        }
    }


class TestHealthAndConfigEndpoints:
    """Test health and configuration endpoints for real data policy"""
    
    def test_health_endpoint_declares_real_data_policy(self, client):
        """Test that health endpoint explicitly declares real data only policy"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "data_policy" in data
        assert "Real Alpaca market data only" in data["data_policy"]
        assert "no calculated or mock data" in data["data_policy"]
        
        # Verify configuration flags
        config = data["configuration"]
        assert config["real_data_only"] is True
        assert config["mock_data_enabled"] is False
        assert config["strict_error_handling"] is True

    def test_connection_test_validates_real_api(self, client, mock_alpaca_responses):
        """Test that connection test validates real Alpaca API connection"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.test_connection.return_value = {
                "status": "connected",
                **mock_alpaca_responses["account"]
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/test-connection")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "connected"
            assert data["account_number"] == "TEST123456789"
            
            # Verify no mock indicators
            assert "mock" not in str(data).lower()
            assert "simulated" not in str(data).lower()
            assert "test_mode" not in data


class TestStockDataEndpoints:
    """Test stock data endpoints for real data only"""
    
    def test_single_stock_quote_returns_real_data_only(self, client, mock_alpaca_responses):
        """Test single stock quote endpoint returns only real market data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = mock_alpaca_responses["stock_quote"]
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 200
            
            data = response.json()
            assert data["symbol"] == "AAPL"
            assert "bid_price" in data
            assert "ask_price" in data
            assert "timestamp" in data
            
            # Verify no synthetic data fields
            assert "calculated_price" not in data
            assert "estimated_spread" not in data
            assert "mock_data" not in data
            assert "theoretical_value" not in data

    def test_stock_quote_fails_cleanly_when_no_real_data(self, client):
        """Test stock quote fails properly when no real data available"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "No quote data found for INVALID_SYMBOL"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "INVALID_SYMBOL"})
            assert response.status_code == 400
            
            data = response.json()
            assert "No quote data found" in data["detail"]
            
            # Verify no fallback data provided
            assert "fallback_quote" not in str(data)
            assert "estimated_price" not in str(data)

    def test_batch_stock_quotes_handles_partial_real_data(self, client):
        """Test batch stock quotes with partial real data availability"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL",
                        "bid_price": 185.25,
                        "ask_price": 185.50,
                        "timestamp": datetime.now().isoformat()
                    },
                    {
                        "symbol": "INVALID",
                        "error": "No quote data found for INVALID"
                    }
                ],
                "count": 2,
                "requested_symbols": ["AAPL", "INVALID"]
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quotes/batch", 
                                 json={"symbols": ["AAPL", "INVALID"]})
            assert response.status_code == 200
            
            data = response.json()
            assert data["count"] == 2
            
            # Verify successful quote has real data
            success_quote = next(q for q in data["quotes"] if "error" not in q)
            assert success_quote["symbol"] == "AAPL"
            assert "bid_price" in success_quote
            
            # Verify failed quote has no fallback
            failed_quote = next(q for q in data["quotes"] if "error" in q)
            assert "No quote data found" in failed_quote["error"]
            assert "mock_price" not in failed_quote

    def test_stock_bars_returns_only_real_historical_data(self, client):
        """Test stock bars return only real historical OHLCV data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_bars.return_value = {
                "symbol": "AAPL",
                "timeframe": "1Day",
                "bars": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "open": 180.0,
                        "high": 186.0,
                        "low": 179.5,
                        "close": 185.0,
                        "volume": 45000000
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=10")
            assert response.status_code == 200
            
            data = response.json()
            assert data["symbol"] == "AAPL"
            assert len(data["bars"]) == 1
            
            bar = data["bars"][0]
            # Verify standard OHLCV fields only
            required_fields = ["timestamp", "open", "high", "low", "close", "volume"]
            for field in required_fields:
                assert field in bar
            
            # Verify no calculated indicators
            forbidden_fields = ["sma", "ema", "rsi", "macd", "bollinger_bands", "synthetic_volume"]
            for field in forbidden_fields:
                assert field not in bar


class TestOptionsEndpoints:
    """Test options endpoints for real data validation"""
    
    def test_options_chain_returns_real_contracts_only(self, client, mock_alpaca_responses):
        """Test options chain returns only real option contracts"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_options_chain.return_value = mock_alpaca_responses["options_chain"]
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/chain", 
                                 json={"underlying_symbol": "AAPL", "expiration_date": "2024-03-15"})
            assert response.status_code == 200
            
            data = response.json()
            assert data["underlying_symbol"] == "AAPL"
            assert data["options_count"] == 45
            assert data["quote_failures"] == 5  # Some real quotes unavailable
            
            # Verify option contract structure
            option = data["options"][0]
            assert option["symbol"] == "AAPL240315C00180000"
            assert option["strike_price"] == 180.0
            assert option["option_type"] == "call"
            
            # Verify no synthetic Greeks or pricing
            assert "black_scholes_price" not in option
            assert "delta" not in option
            assert "gamma" not in option
            assert "theta" not in option
            assert "vega" not in option
            assert "synthetic_iv" not in option

    def test_options_chain_fails_when_no_real_data_available(self, client):
        """Test options chain fails appropriately when no real data exists"""
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
            assert error_detail["underlying_symbol"] == "PENNY_STOCK"
            
            # Verify no synthetic chain provided
            assert "synthetic_chain" not in str(data)
            assert "estimated_options" not in str(data)

    def test_single_option_quote_validates_real_symbol(self, client):
        """Test single option quote validates real option symbol format"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_option_quote.return_value = {
                "symbol": "AAPL240315C00180000",
                "underlying_symbol": "AAPL",
                "strike_price": 180.0,
                "expiration_date": "2024-03-15",
                "option_type": "call",
                "bid_price": 8.25,
                "ask_price": 8.50,
                "timestamp": datetime.now().isoformat()
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quote", 
                                 json={"option_symbol": "AAPL240315C00180000"})
            assert response.status_code == 200
            
            data = response.json()
            assert data["symbol"] == "AAPL240315C00180000"
            assert data["underlying_symbol"] == "AAPL"
            assert data["strike_price"] == 180.0
            assert data["option_type"] == "call"
            
            # Verify only real market data fields
            assert "bid_price" in data
            assert "ask_price" in data
            assert "timestamp" in data
            
            # Verify no theoretical pricing
            assert "intrinsic_value" not in data
            assert "time_value" not in data
            assert "theoretical_price" not in data

    def test_option_quote_rejects_invalid_symbols(self, client):
        """Test option quote properly rejects invalid symbols"""
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
            assert error_detail["error_code"] == "REAL_DATA_UNAVAILABLE"
            
            # Verify no synthetic data provided
            assert "estimated_price" not in str(data)
            assert "mock_option" not in str(data)

    def test_batch_option_quotes_handles_mixed_availability(self, client):
        """Test batch option quotes with mixed real data availability"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_multiple_option_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL240315C00180000",
                        "bid_price": 8.25,
                        "ask_price": 8.50,
                        "underlying_symbol": "AAPL"
                    },
                    {
                        "error": "No real market data available for TSLA240315C00200000"
                    }
                ],
                "count": 2,
                "successful_count": 1,
                "failed_count": 1,
                "requested_symbols": ["AAPL240315C00180000", "TSLA240315C00200000"],
                "failed_symbols": ["TSLA240315C00200000"]
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quotes/batch", 
                                 json={"option_symbols": ["AAPL240315C00180000", "TSLA240315C00200000"]})
            assert response.status_code == 200
            
            data = response.json()
            assert data["count"] == 2
            assert data["successful_count"] == 1
            assert data["failed_count"] == 1
            assert data["failed_symbols"] == ["TSLA240315C00200000"]
            
            # Verify no fallback quotes provided
            failed_quote = next(q for q in data["quotes"] if "error" in q)
            assert "No real market data available" in failed_quote["error"]
            assert "synthetic_quote" not in failed_quote

    def test_batch_option_quotes_enforces_symbol_limit(self, client):
        """Test batch option quotes enforces symbol limit for performance"""
        # Create request with too many symbols
        too_many_symbols = [f"AAPL24031{i}C00180000" for i in range(51)]  # Assuming limit is 50
        
        response = client.post("/api/v1/options/quotes/batch", 
                             json={"option_symbols": too_many_symbols})
        assert response.status_code == 400
        
        data = response.json()
        error_detail = data["detail"]
        assert "Maximum" in error_detail["error"]
        assert "option symbols allowed per request" in error_detail["error"]
        assert error_detail["error_code"] == "REQUEST_LIMIT_EXCEEDED"


class TestAccountAndTradingEndpoints:
    """Test account and trading endpoints for real data"""
    
    def test_account_endpoint_returns_real_account_data(self, client, mock_alpaca_responses):
        """Test account endpoint returns only real account information"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_account.return_value = mock_alpaca_responses["account"]
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/account")
            assert response.status_code == 200
            
            data = response.json()
            assert data["account_number"] == "TEST123456789"
            assert data["buying_power"] == 50000.00
            assert data["cash"] == 25000.00
            assert data["portfolio_value"] == 75000.00
            
            # Verify no virtual account fields
            assert "virtual_cash" not in data
            assert "paper_account" not in data
            assert "simulated_balance" not in data

    def test_positions_return_real_portfolio_data(self, client):
        """Test positions endpoint returns only real portfolio positions"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_positions.return_value = [
                {
                    "symbol": "AAPL",
                    "qty": 100.0,
                    "side": "long",
                    "market_value": 18500.00,
                    "cost_basis": 17000.00,
                    "unrealized_pl": 1500.00,
                    "unrealized_plpc": 0.0882,
                    "avg_entry_price": 170.00
                }
            ]
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/positions")
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 1
            
            position = data[0]
            assert position["symbol"] == "AAPL"
            assert position["qty"] == 100.0
            assert position["market_value"] == 18500.00
            
            # Verify no synthetic positions
            assert "virtual_position" not in position
            assert "paper_pnl" not in position

    def test_orders_return_real_order_data(self, client):
        """Test orders endpoint returns only real order information"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_orders.return_value = [
                {
                    "id": "order_123",
                    "symbol": "AAPL",
                    "qty": 10.0,
                    "side": "buy",
                    "order_type": "market",
                    "status": "filled",
                    "filled_qty": 10.0,
                    "filled_avg_price": 185.50,
                    "submitted_at": datetime.now().isoformat(),
                    "filled_at": datetime.now().isoformat()
                }
            ]
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/orders")
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 1
            
            order = data[0]
            assert order["id"] == "order_123"
            assert order["status"] == "filled"
            assert order["filled_qty"] == 10.0
            
            # Verify no simulated orders
            assert "test_order" not in order
            assert "simulated_fill" not in order


class TestErrorHandlingForRealDataPolicy:
    """Test error handling when real data is unavailable"""
    
    def test_alpaca_api_errors_are_properly_surfaced(self, client):
        """Test that Alpaca API errors are properly surfaced without fallback"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.side_effect = Exception("Alpaca API rate limit exceeded")
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 500
            
            data = response.json()
            assert "Alpaca API rate limit exceeded" in data["detail"]
            
            # Verify no fallback data provided
            assert "fallback_mode" not in str(data)
            assert "cached_data" not in str(data)

    def test_invalid_symbols_return_proper_errors(self, client):
        """Test that invalid symbols return proper errors without suggestions"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "No quote data found for NONEXISTENT"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "NONEXISTENT"})
            assert response.status_code == 400
            
            data = response.json()
            assert "No quote data found" in data["detail"]
            
            # Verify no symbol suggestions or alternatives
            assert "did_you_mean" not in str(data)
            assert "similar_symbols" not in str(data)
            assert "suggested_alternatives" not in str(data)

    def test_market_closed_does_not_trigger_synthetic_data(self, client):
        """Test that market closed scenarios don't trigger synthetic data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "Market is currently closed"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 400
            
            data = response.json()
            assert "Market is currently closed" in data["detail"]
            
            # Verify no after-hours estimates or last known prices
            assert "last_known_price" not in str(data)
            assert "after_hours_estimate" not in str(data)
            assert "previous_close" not in str(data)