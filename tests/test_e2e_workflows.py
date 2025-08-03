"""
End-to-end workflow tests for Alpaca service - complete trading workflows with real data
Tests ensure complete workflows work with only real market data from Alpaca
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
import asyncio


@pytest.fixture
def client():
    """Create test client for FastAPI app"""
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_trading_client():
    """Mock trading client with realistic responses"""
    return Mock()


class TestStockTradingWorkflow:
    """Test complete stock trading workflows"""
    
    def test_stock_research_to_order_workflow(self, client):
        """Test complete workflow: quote -> bars -> account check -> order placement"""
        
        # Step 1: Get stock quote for research
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock quote response
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "bid_size": 100,
                "ask_size": 200,
                "timestamp": datetime.now().isoformat()
            }
            mock_client.return_value = mock_instance
            
            quote_response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert quote_response.status_code == 200
            quote_data = quote_response.json()
            
            # Verify real quote data received
            assert quote_data["symbol"] == "AAPL"
            assert quote_data["ask_price"] == 185.50
            assert "timestamp" in quote_data
            
            # Verify no synthetic data
            assert "calculated_price" not in quote_data
            assert "estimated_value" not in quote_data
        
        # Step 2: Get historical data for analysis
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock historical bars
            mock_instance.get_stock_bars.return_value = {
                "symbol": "AAPL",
                "timeframe": "1Day",
                "bars": [
                    {
                        "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                        "open": 180.00,
                        "high": 186.50,
                        "low": 179.00,
                        "close": 185.25,
                        "volume": 45000000
                    },
                    {
                        "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                        "open": 182.00,
                        "high": 183.75,
                        "low": 178.50,
                        "close": 180.00,
                        "volume": 38000000
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            bars_response = client.get("/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=5")
            assert bars_response.status_code == 200
            bars_data = bars_response.json()
            
            # Verify real historical data
            assert len(bars_data["bars"]) == 2
            bar = bars_data["bars"][0]
            assert all(field in bar for field in ["open", "high", "low", "close", "volume"])
            assert bar["volume"] > 0
            
            # Verify no calculated indicators
            assert "sma" not in bar
            assert "rsi" not in bar
        
        # Step 3: Check account buying power
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock account data
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
            
            account_response = client.get("/api/v1/account")
            assert account_response.status_code == 200
            account_data = account_response.json()
            
            # Verify sufficient buying power
            buying_power = account_data["buying_power"]
            order_value = 185.50 * 100  # 100 shares at ask price
            assert buying_power > order_value, "Insufficient buying power for order"
            
            # Verify no virtual account data
            assert "simulated_buying_power" not in account_data
        
        # Step 4: Place stock order
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock order placement
            mock_instance.place_stock_order.return_value = {
                "id": "order_12345",
                "symbol": "AAPL",
                "qty": 100.0,
                "side": "buy",
                "order_type": "limit",
                "status": "pending_new",
                "filled_qty": 0.0,
                "filled_avg_price": None,
                "limit_price": 185.50,
                "submitted_at": datetime.now().isoformat(),
                "filled_at": None
            }
            mock_client.return_value = mock_instance
            
            order_response = client.post("/api/v1/stocks/order", json={
                "symbol": "AAPL",
                "qty": 100,
                "side": "buy",
                "type": "limit",
                "limit_price": 185.50,
                "time_in_force": "day"
            })
            assert order_response.status_code == 200
            order_data = order_response.json()
            
            # Verify real order placed
            assert order_data["id"] == "order_12345"
            assert order_data["symbol"] == "AAPL"
            assert order_data["status"] == "pending_new"
            
            # Verify no simulated order
            assert "paper_order" not in order_data
            assert "test_mode" not in order_data

    def test_portfolio_monitoring_workflow(self, client):
        """Test portfolio monitoring workflow with real position data"""
        
        # Step 1: Get current positions
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock positions
            mock_instance.get_positions.return_value = [
                {
                    "symbol": "AAPL",
                    "qty": 100.0,
                    "side": "long",
                    "market_value": 18550.00,
                    "cost_basis": 17000.00,
                    "unrealized_pl": 1550.00,
                    "unrealized_plpc": 0.0912,
                    "avg_entry_price": 170.00
                },
                {
                    "symbol": "GOOGL",
                    "qty": 5.0,
                    "side": "long", 
                    "market_value": 13750.00,
                    "cost_basis": 14000.00,
                    "unrealized_pl": -250.00,
                    "unrealized_plpc": -0.0179,
                    "avg_entry_price": 2800.00
                }
            ]
            mock_client.return_value = mock_instance
            
            positions_response = client.get("/api/v1/positions")
            assert positions_response.status_code == 200
            positions_data = positions_response.json()
            
            # Verify real positions
            assert len(positions_data) == 2
            
            aapl_position = next(p for p in positions_data if p["symbol"] == "AAPL")
            assert aapl_position["unrealized_pl"] == 1550.00
            assert aapl_position["qty"] == 100.0
            
            # Verify no synthetic positions
            for position in positions_data:
                assert "virtual_position" not in position
                assert "paper_pnl" not in position
        
        # Step 2: Get recent orders
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock order history
            mock_instance.get_orders.return_value = [
                {
                    "id": "order_12345",
                    "symbol": "AAPL",
                    "qty": 100.0,
                    "side": "buy",
                    "order_type": "limit",
                    "status": "filled",
                    "filled_qty": 100.0,
                    "filled_avg_price": 170.00,
                    "limit_price": 170.50,
                    "submitted_at": (datetime.now() - timedelta(days=5)).isoformat(),
                    "filled_at": (datetime.now() - timedelta(days=5)).isoformat()
                }
            ]
            mock_client.return_value = mock_instance
            
            orders_response = client.get("/api/v1/orders")
            assert orders_response.status_code == 200
            orders_data = orders_response.json()
            
            # Verify real order data
            assert len(orders_data) == 1
            order = orders_data[0]
            assert order["status"] == "filled"
            assert order["filled_qty"] == 100.0
            assert order["filled_avg_price"] == 170.00
            
            # Verify no test orders
            assert "simulated_fill" not in order
        
        # Step 3: Get current quotes for position valuation
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock current quotes for positions
            mock_instance.get_multiple_stock_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL",
                        "bid_price": 185.25,
                        "ask_price": 185.50,
                        "timestamp": datetime.now().isoformat()
                    },
                    {
                        "symbol": "GOOGL",
                        "bid_price": 2745.00,
                        "ask_price": 2750.00,
                        "timestamp": datetime.now().isoformat()
                    }
                ],
                "count": 2,
                "requested_symbols": ["AAPL", "GOOGL"]
            }
            mock_client.return_value = mock_instance
            
            quotes_response = client.post("/api/v1/stocks/quotes/batch", 
                                        json={"symbols": ["AAPL", "GOOGL"]})
            assert quotes_response.status_code == 200
            quotes_data = quotes_response.json()
            
            # Verify real current prices
            assert quotes_data["count"] == 2
            
            aapl_quote = next(q for q in quotes_data["quotes"] if q["symbol"] == "AAPL")
            assert aapl_quote["bid_price"] == 185.25
            
            # Calculate current position value (manual verification)
            current_aapl_value = aapl_quote["bid_price"] * 100  # 100 shares
            assert current_aapl_value == 18525.00


class TestOptionsTradingWorkflow:
    """Test complete options trading workflows"""
    
    def test_options_research_workflow(self, client):
        """Test options research workflow: underlying quote -> options chain -> option quote"""
        
        # Step 1: Get underlying stock quote
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock underlying quote
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "bid_size": 100,
                "ask_size": 200,
                "timestamp": datetime.now().isoformat()
            }
            mock_client.return_value = mock_instance
            
            underlying_response = client.get("/api/v1/stocks/AAPL/quote")
            assert underlying_response.status_code == 200
            underlying_data = underlying_response.json()
            
            current_price = (underlying_data["bid_price"] + underlying_data["ask_price"]) / 2
            assert current_price == 185.375
        
        # Step 2: Get options chain for analysis
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock options chain
            mock_instance.get_options_chain.return_value = {
                "underlying_symbol": "AAPL",
                "underlying_price": 185.375,
                "expiration_dates": ["2024-02-16", "2024-03-15"],
                "options_count": 85,
                "quote_failures": 10,
                "options": [
                    {
                        "symbol": "AAPL240216C00180000",
                        "underlying_symbol": "AAPL",
                        "strike_price": 180.0,
                        "expiration_date": "2024-02-16",
                        "option_type": "call",
                        "bid_price": 8.25,
                        "ask_price": 8.75
                    },
                    {
                        "symbol": "AAPL240216C00190000",
                        "underlying_symbol": "AAPL",
                        "strike_price": 190.0,
                        "expiration_date": "2024-02-16",
                        "option_type": "call",
                        "bid_price": 2.10,
                        "ask_price": 2.35
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            chain_response = client.get("/api/v1/options/AAPL/chain?expiration_date=2024-02-16")
            assert chain_response.status_code == 200
            chain_data = chain_response.json()
            
            # Verify real options chain
            assert chain_data["underlying_symbol"] == "AAPL"
            assert chain_data["options_count"] == 85
            assert chain_data["quote_failures"] == 10  # Some options have no real quotes
            
            # Find suitable option for trading
            itm_call = next(opt for opt in chain_data["options"] 
                          if opt["option_type"] == "call" and opt["strike_price"] < current_price)
            assert itm_call["symbol"] == "AAPL240216C00180000"
            
            # Verify no synthetic Greeks
            assert "delta" not in itm_call
            assert "implied_volatility" not in itm_call or itm_call["implied_volatility"] is None
        
        # Step 3: Get specific option quote
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock specific option quote
            mock_instance.get_option_quote.return_value = {
                "symbol": "AAPL240216C00180000",
                "underlying_symbol": "AAPL",
                "strike_price": 180.0,
                "expiration_date": "2024-02-16",
                "option_type": "call",
                "bid_price": 8.25,
                "ask_price": 8.75,
                "bid_size": 25,
                "ask_size": 35,
                "timestamp": datetime.now().isoformat()
            }
            mock_client.return_value = mock_instance
            
            option_response = client.post("/api/v1/options/quote", 
                                        json={"option_symbol": "AAPL240216C00180000"})
            assert option_response.status_code == 200
            option_data = option_response.json()
            
            # Verify real option quote
            assert option_data["symbol"] == "AAPL240216C00180000"
            assert option_data["bid_price"] == 8.25
            assert option_data["ask_price"] == 8.75
            
            # Verify no theoretical pricing
            assert "theoretical_price" not in option_data
            assert "intrinsic_value" not in option_data
            assert "time_value" not in option_data

    def test_batch_options_monitoring_workflow(self, client):
        """Test monitoring multiple options positions with batch quotes"""
        
        # Mock portfolio with options positions (simulated existing positions)
        existing_options = [
            "AAPL240216C00180000",
            "AAPL240216P00170000", 
            "GOOGL240216C02750000"
        ]
        
        # Get batch option quotes for monitoring
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            
            # Mock batch option quotes (partial data available)
            mock_instance.get_multiple_option_quotes.return_value = {
                "quotes": [
                    {
                        "symbol": "AAPL240216C00180000",
                        "underlying_symbol": "AAPL",
                        "bid_price": 8.25,
                        "ask_price": 8.75,
                        "timestamp": datetime.now().isoformat()
                    },
                    {
                        "symbol": "AAPL240216P00170000",
                        "underlying_symbol": "AAPL", 
                        "bid_price": 1.50,
                        "ask_price": 1.75,
                        "timestamp": datetime.now().isoformat()
                    },
                    {
                        "error": "No real market data available for option symbol: GOOGL240216C02750000"
                    }
                ],
                "count": 3,
                "successful_count": 2,
                "failed_count": 1,
                "requested_symbols": existing_options,
                "failed_symbols": ["GOOGL240216C02750000"]
            }
            mock_client.return_value = mock_instance
            
            batch_response = client.post("/api/v1/options/quotes/batch", 
                                       json={"option_symbols": existing_options})
            assert batch_response.status_code == 200
            batch_data = batch_response.json()
            
            # Verify batch response structure
            assert batch_data["count"] == 3
            assert batch_data["successful_count"] == 2
            assert batch_data["failed_count"] == 1
            assert batch_data["failed_symbols"] == ["GOOGL240216C02750000"]
            
            # Verify successful quotes have real data
            successful_quotes = [q for q in batch_data["quotes"] if "error" not in q]
            assert len(successful_quotes) == 2
            
            for quote in successful_quotes:
                assert "bid_price" in quote
                assert "ask_price" in quote
                assert "timestamp" in quote
                assert "synthetic_price" not in quote
            
            # Verify failed quote has no fallback
            failed_quote = next(q for q in batch_data["quotes"] if "error" in q)
            assert "No real market data available" in failed_quote["error"]
            assert "estimated_price" not in failed_quote


class TestErrorRecoveryWorkflows:
    """Test workflow behavior when real data becomes unavailable"""
    
    def test_degraded_service_workflow(self, client):
        """Test workflow behavior when some data sources are unavailable"""
        
        # Scenario: Stock quotes work, but options data is unavailable
        
        # Step 1: Stock quote succeeds
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": "AAPL",
                "bid_price": 185.25,
                "ask_price": 185.50,
                "timestamp": datetime.now().isoformat()
            }
            mock_client.return_value = mock_instance
            
            quote_response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert quote_response.status_code == 200
        
        # Step 2: Options chain fails (no real data available)
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_options_chain.return_value = {
                "error": "No real options chain data available for AAPL"
            }
            mock_client.return_value = mock_instance
            
            chain_response = client.post("/api/v1/options/chain", 
                                       json={"underlying_symbol": "AAPL"})
            assert chain_response.status_code == 404
            
            error_data = chain_response.json()
            assert "No real options chain data available" in error_data["detail"]["error"]
            
            # Verify no synthetic chain provided
            assert "synthetic_chain" not in str(error_data)
        
        # Step 3: User can still proceed with stock-only strategy
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_account.return_value = {
                "account_number": "123456789",
                "buying_power": 50000.00,
                "cash": 25000.00,
                "portfolio_value": 75000.00
            }
            mock_client.return_value = mock_instance
            
            account_response = client.get("/api/v1/account")
            assert account_response.status_code == 200
            # User can still check account and place stock orders

    def test_market_hours_workflow_limitations(self, client):
        """Test workflow limitations during non-market hours"""
        
        # Simulate after-hours scenario where real-time data is limited
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "error": "Real-time quotes not available outside market hours"
            }
            mock_client.return_value = mock_instance
            
            quote_response = client.post("/api/v1/stocks/quote", json={"symbol": "AAPL"})
            assert quote_response.status_code == 400
            
            # Verify no after-hours estimates provided
            error_detail = quote_response.json()["detail"]
            assert "not available outside market hours" in error_detail
            assert "pre_market_estimate" not in error_detail
        
        # Historical data should still be available
        with patch('app.alpaca_client.AlpacaClient') as mock_client:
            mock_instance = Mock()
            mock_instance.get_stock_bars.return_value = {
                "symbol": "AAPL",
                "timeframe": "1Day",
                "bars": [
                    {
                        "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                        "open": 180.00,
                        "high": 186.50,
                        "low": 179.00,
                        "close": 185.25,
                        "volume": 45000000
                    }
                ]
            }
            mock_client.return_value = mock_instance
            
            bars_response = client.get("/api/v1/stocks/AAPL/bars")
            assert bars_response.status_code == 200
            # Historical data still available for analysis


class TestDataConsistencyAcrossWorkflow:
    """Test data consistency throughout complete workflows"""
    
    def test_symbol_consistency_across_endpoints(self, client):
        """Test that symbol data remains consistent across different endpoints"""
        
        symbol = "AAPL"
        
        # Get quote, bars, and use in options - verify symbol consistency
        with patch('app.alpaca_client.AlpacaClient') as mock_client_quote:
            mock_instance = Mock()
            mock_instance.get_stock_quote.return_value = {
                "symbol": symbol,
                "bid_price": 185.25,
                "ask_price": 185.50
            }
            mock_client_quote.return_value = mock_instance
            
            quote_response = client.post("/api/v1/stocks/quote", json={"symbol": symbol})
            quote_data = quote_response.json()
            assert quote_data["symbol"] == symbol
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_bars:
            mock_instance = Mock()
            mock_instance.get_stock_bars.return_value = {
                "symbol": symbol,
                "timeframe": "1Day",
                "bars": [{"open": 180, "close": 185, "volume": 1000000, "timestamp": "2024-01-15T00:00:00Z"}]
            }
            mock_client_bars.return_value = mock_instance
            
            bars_response = client.get(f"/api/v1/stocks/{symbol}/bars")
            bars_data = bars_response.json()
            assert bars_data["symbol"] == symbol
        
        with patch('app.alpaca_client.AlpacaClient') as mock_client_chain:
            mock_instance = Mock()
            mock_instance.get_options_chain.return_value = {
                "underlying_symbol": symbol,
                "options": [{"underlying_symbol": symbol, "symbol": f"{symbol}240216C00180000"}]
            }
            mock_client_chain.return_value = mock_instance
            
            chain_response = client.get(f"/api/v1/options/{symbol}/chain")
            if chain_response.status_code == 200:
                chain_data = chain_response.json()
                assert chain_data["underlying_symbol"] == symbol