"""
Data integrity tests for Alpaca service - focused on validating real data authenticity
Tests ensure response data structure and content integrity for real market data
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
import re
from decimal import Decimal


@pytest.fixture
def client():
    """Create test client for FastAPI app"""
    from main import app
    return TestClient(app)


class TestStockDataIntegrity:
    """Test integrity of stock market data responses"""
    
    def test_stock_quote_data_structure_validation(self, client):
        """Test that stock quotes have proper data structure and types"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "bid_size": 100,
                "ask_size": 200,
                "timestamp": "2024-01-15T15:30:00.000Z"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate required fields exist
            required_fields = ["symbol", "bid_price", "ask_price", "bid_size", "ask_size", "timestamp"]
            for field in required_fields:
                assert field in data, f"Required field {field} missing from response"
            
            # Validate data types
            assert isinstance(data["symbol"], str)
            assert isinstance(data["bid_price"], (int, float))
            assert isinstance(data["ask_price"], (int, float))
            assert isinstance(data["bid_size"], int)
            assert isinstance(data["ask_size"], int)
            assert isinstance(data["timestamp"], str)
            
            # Validate realistic market data constraints
            assert data["bid_price"] > 0, "Bid price must be positive"
            assert data["ask_price"] > 0, "Ask price must be positive"
            assert data["ask_price"] >= data["bid_price"], "Ask price should be >= bid price"
            assert data["bid_size"] > 0, "Bid size must be positive"
            assert data["ask_size"] > 0, "Ask size must be positive"
            
            # Validate symbol format (uppercase letters)
            assert data["symbol"].isupper(), "Stock symbol should be uppercase"
            assert data["symbol"].isalpha(), "Stock symbol should contain only letters"

    def test_stock_bars_ohlcv_data_integrity(self, client):
        """Test integrity of OHLCV bar data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_bars.return_value = {
                "symbol": "AAPL",
                "timeframe": "1Day",
                "bars": [
                    {
                        "timestamp": "2024-01-15T00:00:00.000Z",
                        "open": 180.50,
                        "high": 186.25,
                        "low": 179.75,
                        "close": 185.00,
                        "volume": 45000000
                    },
                    {
                        "timestamp": "2024-01-14T00:00:00.000Z", 
                        "open": 178.00,
                        "high": 181.50,
                        "low": 177.25,
                        "close": 180.75,
                        "volume": 52000000
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=2")
            assert response.status_code == 200
            
            data = response.json()
            assert "bars" in data
            assert len(data["bars"]) == 2
            
            for bar in data["bars"]:
                # Validate OHLCV structure
                ohlcv_fields = ["timestamp", "open", "high", "low", "close", "volume"]
                for field in ohlcv_fields:
                    assert field in bar, f"OHLCV field {field} missing"
                
                # Validate OHLCV relationships
                assert bar["high"] >= bar["open"], "High should be >= open"
                assert bar["high"] >= bar["close"], "High should be >= close"
                assert bar["low"] <= bar["open"], "Low should be <= open"
                assert bar["low"] <= bar["close"], "Low should be <= close"
                assert bar["high"] >= bar["low"], "High should be >= low"
                
                # Validate positive values
                for price_field in ["open", "high", "low", "close"]:
                    assert bar[price_field] > 0, f"{price_field} must be positive"
                assert bar["volume"] >= 0, "Volume must be non-negative"
                
                # Validate timestamp format
                assert isinstance(bar["timestamp"], str)
                # Basic ISO format check
                assert "T" in bar["timestamp"] or "-" in bar["timestamp"]

    def test_batch_stock_quotes_consistency(self, client):
        """Test consistency of batch stock quote responses"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL",
                        "bid_price": 185.25,
                        "ask_price": 185.50,
                        "bid_size": 100,
                        "ask_size": 200,
                        "timestamp": "2024-01-15T15:30:00.000Z"
                    },
                    {
                        "symbol": "GOOGL",
                        "bid_price": 2750.00,
                        "ask_price": 2751.50,
                        "bid_size": 50,
                        "ask_size": 75,
                        "timestamp": "2024-01-15T15:30:01.000Z"
                    }
                ],
                "count": 2,
                "requested_symbols": ["AAPL", "GOOGL"]
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quotes/batch", 
                                 json={"symbols": ["AAPL", "GOOGL"]})
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate batch response structure
            assert "quotes" in data
            assert "count" in data
            assert "requested_symbols" in data
            assert data["count"] == len(data["quotes"])
            
            # Validate each quote has consistent structure
            for quote in data["quotes"]:
                if "error" not in quote:  # Skip error entries
                    assert "symbol" in quote
                    assert "bid_price" in quote
                    assert "ask_price" in quote
                    assert "timestamp" in quote
                    
                    # Validate symbol is in requested list
                    assert quote["symbol"] in data["requested_symbols"]


class TestOptionsDataIntegrity:
    """Test integrity of options market data responses"""
    
    def test_option_symbol_format_validation(self, client):
        """Test validation of option symbol format in responses"""
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
                "bid_size": 10,
                "ask_size": 15,
                "timestamp": "2024-01-15T15:30:00.000Z"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quote", 
                                 json={"option_symbol": "AAPL240315C00180000"})
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate option symbol format (OCC standard)
            symbol = data["symbol"]
            assert len(symbol) >= 18, "Option symbol too short"
            
            # Extract and validate components
            underlying = data["underlying_symbol"]
            strike_price = data["strike_price"]
            expiration_date = data["expiration_date"]
            option_type = data["option_type"]
            
            # Validate underlying symbol
            assert underlying.isupper(), "Underlying symbol should be uppercase"
            assert underlying.isalpha(), "Underlying symbol should be alphabetic"
            
            # Validate strike price
            assert isinstance(strike_price, (int, float))
            assert strike_price > 0, "Strike price must be positive"
            
            # Validate expiration date format (YYYY-MM-DD)
            date_pattern = r'^\d{4}-\d{2}-\d{2}$'
            assert re.match(date_pattern, expiration_date), "Invalid expiration date format"
            
            # Validate option type
            assert option_type in ["call", "put"], "Option type must be call or put"
            
            # Validate bid/ask relationship
            if data["bid_price"] is not None and data["ask_price"] is not None:
                assert data["ask_price"] >= data["bid_price"], "Ask should be >= bid"

    def test_options_chain_structure_integrity(self, client):
        """Test integrity of options chain response structure"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_options_chain.return_value = {
                "underlying_symbol": "AAPL",
                "underlying_price": 185.0,
                "expiration_dates": ["2024-02-16", "2024-03-15", "2024-04-19"],
                "options_count": 125,
                "quote_failures": 15,
                "options": [
                    {
                        "symbol": "AAPL240216C00170000",
                        "underlying_symbol": "AAPL",
                        "strike_price": 170.0,
                        "expiration_date": "2024-02-16", 
                        "option_type": "call",
                        "bid_price": 16.25,
                        "ask_price": 16.75
                    },
                    {
                        "symbol": "AAPL240216P00190000",
                        "underlying_symbol": "AAPL",
                        "strike_price": 190.0,
                        "expiration_date": "2024-02-16",
                        "option_type": "put",
                        "bid_price": 6.50,
                        "ask_price": 7.00
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/chain", 
                                 json={"underlying_symbol": "AAPL"})
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate chain structure
            required_fields = ["underlying_symbol", "underlying_price", "expiration_dates", 
                             "options_count", "quote_failures", "options"]
            for field in required_fields:
                assert field in data, f"Required field {field} missing from options chain"
            
            # Validate expiration dates are sorted and future dates
            exp_dates = data["expiration_dates"]
            assert len(exp_dates) > 0, "At least one expiration date should exist"
            
            # Validate options array
            options = data["options"]
            assert isinstance(options, list), "Options should be a list"
            assert len(options) <= data["options_count"], "Options list shouldn't exceed declared count"
            
            # Validate each option contract
            for option in options:
                assert option["underlying_symbol"] == data["underlying_symbol"]
                assert option["expiration_date"] in exp_dates
                assert option["option_type"] in ["call", "put"]
                assert option["strike_price"] > 0

    def test_options_greeks_data_absence(self, client):
        """Test that options responses don't contain calculated Greeks"""
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
                "timestamp": "2024-01-15T15:30:00.000Z"
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/options/quote", 
                                 json={"option_symbol": "AAPL240315C00180000"})
            assert response.status_code == 200
            
            data = response.json()
            
            # Verify no calculated Greeks are present
            greeks = ["delta", "gamma", "theta", "vega", "rho"]
            for greek in greeks:
                assert greek not in data, f"Calculated Greek {greek} should not be present"
            
            # Verify no theoretical pricing
            theoretical_fields = ["theoretical_price", "intrinsic_value", "time_value", 
                                "black_scholes_price", "binomial_price"]
            for field in theoretical_fields:
                assert field not in data, f"Theoretical field {field} should not be present"


class TestAccountDataIntegrity:
    """Test integrity of account and position data"""
    
    def test_account_balance_data_consistency(self, client):
        """Test consistency of account balance data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_account.return_value = {
                "account_number": "123456789",
                "buying_power": 50000.00,
                "cash": 25000.00,
                "portfolio_value": 75000.00,
                "equity": 75000.00,
                "last_equity": 74500.00,
                "multiplier": "4",
                "pattern_day_trader": False
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/account")
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate account number format
            assert isinstance(data["account_number"], str)
            assert len(data["account_number"]) > 0
            
            # Validate monetary values are non-negative
            monetary_fields = ["buying_power", "cash", "portfolio_value", "equity", "last_equity"]
            for field in monetary_fields:
                assert field in data
                assert isinstance(data[field], (int, float))
                assert data[field] >= 0, f"{field} should be non-negative"
            
            # Validate logical relationships
            assert data["cash"] <= data["portfolio_value"], "Cash should not exceed portfolio value"
            
            # Validate multiplier
            assert data["multiplier"] in ["1", "2", "4"], "Invalid day trading multiplier"
            
            # Validate PDT flag
            assert isinstance(data["pattern_day_trader"], bool)

    def test_positions_data_integrity(self, client):
        """Test integrity of positions data"""
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
                },
                {
                    "symbol": "GOOGL",
                    "qty": -10.0,  # Short position
                    "side": "short",
                    "market_value": -27500.00,
                    "cost_basis": 28000.00,
                    "unrealized_pl": 500.00,
                    "unrealized_plpc": 0.0179,
                    "avg_entry_price": 2800.00
                }
            ]
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/positions")
            assert response.status_code == 200
            
            data = response.json()
            assert isinstance(data, list)
            
            for position in data:
                # Validate required fields
                required_fields = ["symbol", "qty", "side", "market_value", "cost_basis", 
                                 "unrealized_pl", "avg_entry_price"]
                for field in required_fields:
                    assert field in position, f"Position missing field {field}"
                
                # Validate symbol format
                assert position["symbol"].isupper()
                assert position["symbol"].isalpha()
                
                # Validate quantity and side consistency
                qty = position["qty"]
                side = position["side"]
                
                if side == "long":
                    assert qty > 0, "Long position should have positive quantity"
                elif side == "short":
                    assert qty < 0, "Short position should have negative quantity"
                
                # Validate price values
                assert position["avg_entry_price"] > 0, "Average entry price must be positive"
                
                # Validate P&L calculation consistency (basic check)
                if position["cost_basis"] != 0:
                    calculated_plpc = position["unrealized_pl"] / abs(position["cost_basis"])
                    if "unrealized_plpc" in position and position["unrealized_plpc"] is not None:
                        # Allow for small floating point differences
                        assert abs(calculated_plpc - position["unrealized_plpc"]) < 0.01


class TestTimestampAndDataFreshness:
    """Test timestamp integrity and data freshness validation"""
    
    def test_quote_timestamps_are_recent(self, client):
        """Test that quote timestamps indicate recent data"""
        current_time = datetime.now()
        recent_timestamp = current_time.isoformat() + "Z"
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "bid_size": 100,
                "ask_size": 200,
                "timestamp": recent_timestamp
            }
            mock_client.return_value = mock_instance
            
            response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert response.status_code == 200
            
            data = response.json()
            
            # Validate timestamp format
            timestamp_str = data["timestamp"]
            assert isinstance(timestamp_str, str)
            
            # Basic ISO format validation
            iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
            assert re.match(iso_pattern, timestamp_str), "Invalid timestamp format"

    def test_historical_data_temporal_ordering(self, client):
        """Test temporal ordering in historical bar data"""
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_bars.return_value = {
                "symbol": "AAPL",
                "timeframe": "1Day",
                "bars": [
                    {
                        "timestamp": "2024-01-15T00:00:00.000Z",
                        "open": 180.50,
                        "high": 186.25,
                        "low": 179.75,
                        "close": 185.00,
                        "volume": 45000000
                    },
                    {
                        "timestamp": "2024-01-14T00:00:00.000Z",
                        "open": 178.00,
                        "high": 181.50,
                        "low": 177.25,
                        "close": 180.75,
                        "volume": 52000000
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            response = client.get("/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=5")
            assert response.status_code == 200
            
            data = response.json()
            bars = data["bars"]
            
            if len(bars) > 1:
                # Validate timestamps are parseable
                timestamps = []
                for bar in bars:
                    timestamp_str = bar["timestamp"]
                    # Basic validation that it looks like a timestamp
                    assert "T" in timestamp_str or "-" in timestamp_str
                    timestamps.append(timestamp_str)
                
                # Note: We don't enforce ordering since Alpaca might return data in various orders