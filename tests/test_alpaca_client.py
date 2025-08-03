"""
Unit tests for AlpacaClient - focused on verifying real data strategy
Tests ensure all methods return only real Alpaca market data and handle data unavailability correctly
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from app.alpaca_client import AlpacaClient


class TestAlpacaClientRealDataStrategy:
    """Test suite focusing on real data strategy validation"""
    
    @pytest.fixture
    def mock_alpaca_client(self):
        """Create AlpacaClient with mocked dependencies"""
        with patch('app.alpaca_client.TradingClient') as mock_trading, \
             patch('app.alpaca_client.StockHistoricalDataClient') as mock_stock_data, \
             patch('app.alpaca_client.OptionHistoricalDataClient') as mock_option_data:
            
            client = AlpacaClient()
            client.trading_client = mock_trading.return_value
            client.stock_data_client = mock_stock_data.return_value  
            client.option_data_client = mock_option_data.return_value
            return client

    @pytest.mark.asyncio
    async def test_connection_returns_real_account_data(self, mock_alpaca_client):
        """Test that connection test returns only real account data from Alpaca"""
        # Arrange
        mock_account = Mock()
        mock_account.account_number = "123456789"
        mock_account.buying_power = "10000.00"
        mock_account.cash = "5000.00"
        mock_account.portfolio_value = "15000.00"
        
        mock_alpaca_client.trading_client.get_account.return_value = mock_account
        
        # Act
        result = await mock_alpaca_client.test_connection()
        
        # Assert - verify real data structure
        assert result["status"] == "connected"
        assert result["account_number"] == "123456789"
        assert result["buying_power"] == 10000.00
        assert result["cash"] == 5000.00
        assert result["portfolio_value"] == 15000.00
        
        # Verify no mock data fields are present
        assert "mock_data" not in result
        assert "calculated_fields" not in result
        assert "simulated" not in result

    @pytest.mark.asyncio
    async def test_connection_handles_real_api_failure(self, mock_alpaca_client):
        """Test proper error handling when real Alpaca API is unavailable"""
        # Arrange
        mock_alpaca_client.trading_client.get_account.side_effect = Exception("API connection failed")
        
        # Act
        result = await mock_alpaca_client.test_connection()
        
        # Assert - verify error response without mock fallback
        assert result["status"] == "failed"
        assert "API connection failed" in result["error"]
        assert "mock_data" not in result
        assert "fallback_data" not in result

    @pytest.mark.asyncio  
    async def test_stock_quote_returns_only_real_data(self, mock_alpaca_client):
        """Test that stock quotes return only real Alpaca market data"""
        # Arrange
        mock_quote = Mock()
        mock_quote.bid_price = 150.25
        mock_quote.ask_price = 150.50
        mock_quote.bid_size = 100
        mock_quote.ask_size = 200
        mock_quote.timestamp = datetime.now()
        
        mock_alpaca_client.stock_data_client.get_stock_latest_quote.return_value = {"AAPL": mock_quote}
        
        # Act
        result = await mock_alpaca_client.get_stock_quote("AAPL")
        
        # Assert - verify only real data fields
        assert result["symbol"] == "AAPL"
        assert result["bid_price"] == 150.25
        assert result["ask_price"] == 150.50
        assert result["bid_size"] == 100
        assert result["ask_size"] == 200
        assert "timestamp" in result
        
        # Verify no calculated or mock fields
        assert "implied_price" not in result
        assert "calculated_spread" not in result
        assert "mock_data" not in result
        assert "simulated_price" not in result

    @pytest.mark.asyncio
    async def test_stock_quote_no_fallback_when_data_unavailable(self, mock_alpaca_client):
        """Test that no fallback data is provided when real data is unavailable"""
        # Arrange - simulate no data available from Alpaca
        mock_alpaca_client.stock_data_client.get_stock_latest_quote.return_value = {}
        
        # Act
        result = await mock_alpaca_client.get_stock_quote("INVALID")
        
        # Assert - verify error without fallback
        assert "error" in result
        assert "No quote data found for INVALID" in result["error"]
        assert "bid_price" not in result
        assert "ask_price" not in result
        assert "mock_data" not in result
        assert "estimated_price" not in result

    @pytest.mark.asyncio
    async def test_options_chain_returns_only_real_contracts(self, mock_alpaca_client):
        """Test that options chain returns only real option contracts from Alpaca"""
        # Arrange
        mock_contract = Mock()
        mock_contract.symbol = "AAPL240216C00150000"
        mock_contract.strike_price = 150.0
        mock_contract.expiration_date = "2024-02-16"
        mock_contract.style = Mock()
        mock_contract.style.value = "american"
        
        mock_chain = Mock()
        mock_chain.option_contracts = [mock_contract]
        
        mock_alpaca_client.option_data_client.get_option_chain.return_value = mock_chain
        
        # Mock stock quote for underlying
        mock_stock_quote = Mock()
        mock_stock_quote.ask_price = 155.0
        mock_alpaca_client.stock_data_client.get_stock_latest_quote.return_value = {"AAPL": mock_stock_quote}
        
        # Mock option quote (simulate no real quote available)
        with patch.object(mock_alpaca_client, 'get_option_quote') as mock_option_quote:
            mock_option_quote.return_value = {"error": "No real market data available"}
            
            # Act
            result = await mock_alpaca_client.get_options_chain("AAPL")
        
        # Assert - verify only real contract data is returned
        assert result["underlying_symbol"] == "AAPL"
        assert result["underlying_price"] == 155.0
        assert result["options_count"] == 1
        assert result["quote_failures"] == 1  # Real quote not available
        
        option = result["options"][0]
        assert option["symbol"] == "AAPL240216C00150000"
        assert option["strike_price"] == 150.0
        assert option["expiration_date"] == "2024-02-16"
        
        # Verify no calculated or mock options data
        assert "calculated_iv" not in option
        assert "theoretical_price" not in option
        assert "mock_greeks" not in option

    @pytest.mark.asyncio
    async def test_options_chain_fails_when_no_real_data(self, mock_alpaca_client):
        """Test that options chain fails when no real data is available"""
        # Arrange - simulate no real options data
        mock_alpaca_client.option_data_client.get_option_chain.return_value = None
        
        # Act
        result = await mock_alpaca_client.get_options_chain("INVALID")
        
        # Assert - verify error without mock fallback
        assert "error" in result
        assert "No real options chain data available" in result["error"]
        assert "options" not in result
        assert "mock_chain" not in result
        assert "simulated_options" not in result

    @pytest.mark.asyncio
    async def test_option_quote_validates_real_symbol_format(self, mock_alpaca_client):
        """Test that option quotes validate real option symbol format"""
        # Arrange
        mock_quote = Mock()
        mock_quote.bid_price = 5.25
        mock_quote.ask_price = 5.50
        mock_quote.bid_size = 10
        mock_quote.ask_size = 15
        mock_quote.timestamp = datetime.now()
        
        mock_alpaca_client.option_data_client.get_option_latest_quote.return_value = {
            "AAPL240216C00150000": mock_quote
        }
        
        # Act
        result = await mock_alpaca_client.get_option_quote("AAPL240216C00150000")
        
        # Assert - verify real option data parsing
        assert result["symbol"] == "AAPL240216C00150000"
        assert result["underlying_symbol"] == "AAPL"
        assert result["strike_price"] == 150.0
        assert result["expiration_date"] == "2024-02-16"
        assert result["option_type"] == "call"
        assert result["bid_price"] == 5.25
        assert result["ask_price"] == 5.50
        
        # Verify no synthetic data
        assert "theoretical_value" not in result
        assert "black_scholes_price" not in result
        assert "synthetic_greeks" not in result

    @pytest.mark.asyncio
    async def test_option_quote_rejects_invalid_symbol(self, mock_alpaca_client):
        """Test that invalid option symbols are rejected without fallback"""
        # Act
        result = await mock_alpaca_client.get_option_quote("INVALID_SYMBOL")
        
        # Assert - verify rejection without mock data
        assert "error" in result
        assert "Invalid option symbol format" in result["error"]
        assert "bid_price" not in result
        assert "estimated_price" not in result
        assert "mock_data" not in result

    @pytest.mark.asyncio
    async def test_multiple_option_quotes_handles_partial_real_data(self, mock_alpaca_client):
        """Test batch option quotes with partial real data availability"""
        # Arrange
        option_symbols = ["AAPL240216C00150000", "INVALID_SYMBOL", "TSLA240216P00200000"]
        
        with patch.object(mock_alpaca_client, 'get_option_quote') as mock_quote:
            def side_effect(symbol):
                if symbol == "AAPL240216C00150000":
                    return {
                        "symbol": symbol,
                        "bid_price": 5.25,
                        "ask_price": 5.50,
                        "underlying_symbol": "AAPL"
                    }
                else:
                    return {"error": f"No real market data available for {symbol}"}
            
            mock_quote.side_effect = side_effect
            
            # Act
            result = await mock_alpaca_client.get_multiple_option_quotes(option_symbols)
        
        # Assert - verify mixed results without mock fallback
        assert result["count"] == 3
        assert result["successful_count"] == 1
        assert result["failed_count"] == 2
        assert result["failed_symbols"] == ["INVALID_SYMBOL", "TSLA240216P00200000"]
        
        # Verify successful quote is real data
        successful_quote = next(q for q in result["quotes"] if "error" not in q)
        assert successful_quote["symbol"] == "AAPL240216C00150000"
        assert successful_quote["bid_price"] == 5.25
        
        # Verify failed quotes have no fallback
        failed_quotes = [q for q in result["quotes"] if "error" in q]
        assert len(failed_quotes) == 2
        for quote in failed_quotes:
            assert "mock_data" not in quote
            assert "estimated_price" not in quote

    @pytest.mark.asyncio
    async def test_stock_bars_returns_only_real_historical_data(self, mock_alpaca_client):
        """Test that stock bars return only real historical data"""
        # Arrange
        mock_bar = Mock()
        mock_bar.timestamp = datetime.now() - timedelta(days=1)
        mock_bar.open = 150.0
        mock_bar.high = 155.0  
        mock_bar.low = 149.0
        mock_bar.close = 154.0
        mock_bar.volume = 1000000
        
        mock_alpaca_client.stock_data_client.get_stock_bars.return_value = {"AAPL": [mock_bar]}
        
        # Act
        result = await mock_alpaca_client.get_stock_bars("AAPL", "1Day", 10)
        
        # Assert - verify only real OHLCV data
        assert result["symbol"] == "AAPL"
        assert result["timeframe"] == "1Day"
        assert len(result["bars"]) == 1
        
        bar = result["bars"][0]
        assert bar["open"] == 150.0
        assert bar["high"] == 155.0
        assert bar["low"] == 149.0
        assert bar["close"] == 154.0
        assert bar["volume"] == 1000000
        
        # Verify no calculated indicators
        assert "sma" not in bar
        assert "rsi" not in bar
        assert "synthetic_volume" not in bar

    def test_option_symbol_parsing_validates_real_format(self, mock_alpaca_client):
        """Test that option symbol parsing validates real Alpaca format"""
        # Test valid real format
        underlying, strike, exp_date, option_type = mock_alpaca_client._parse_option_symbol("AAPL240216C00150000")
        assert underlying == "AAPL"
        assert strike == 150.0
        assert exp_date == "2024-02-16"
        assert option_type == "call"
        
        # Test invalid format returns None (no fallback parsing)
        result = mock_alpaca_client._parse_option_symbol("INVALID_FORMAT")
        assert all(x is None for x in result)

    @pytest.mark.asyncio
    async def test_account_info_returns_only_real_data(self, mock_alpaca_client):
        """Test that account info returns only real account data"""
        # Arrange
        mock_account = Mock()
        mock_account.account_number = "123456789"
        mock_account.buying_power = "25000.00"
        mock_account.cash = "10000.00"
        mock_account.portfolio_value = "35000.00"
        mock_account.equity = "35000.00"
        mock_account.last_equity = "34500.00"
        mock_account.multiplier = "4"
        mock_account.pattern_day_trader = False
        
        mock_alpaca_client.trading_client.get_account.return_value = mock_account
        
        # Act
        result = await mock_alpaca_client.get_account()
        
        # Assert - verify only real account fields
        assert result["account_number"] == "123456789"
        assert result["buying_power"] == 25000.00
        assert result["cash"] == 10000.00
        assert result["portfolio_value"] == 35000.00
        assert result["equity"] == 35000.00
        assert result["last_equity"] == 34500.00
        assert result["multiplier"] == "4"
        assert result["pattern_day_trader"] is False
        
        # Verify no calculated or mock fields
        assert "virtual_cash" not in result
        assert "simulated_buying_power" not in result
        assert "mock_account" not in result

    @pytest.mark.asyncio
    async def test_positions_return_only_real_positions(self, mock_alpaca_client):
        """Test that positions return only real portfolio positions"""
        # Arrange
        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.qty = "10"
        mock_position.side = Mock()
        mock_position.side.value = "long"
        mock_position.market_value = "1500.00"
        mock_position.cost_basis = "1400.00"
        mock_position.unrealized_pl = "100.00"
        mock_position.unrealized_plpc = "0.0714"
        mock_position.avg_entry_price = "140.00"
        
        mock_alpaca_client.trading_client.get_all_positions.return_value = [mock_position]
        
        # Act
        result = await mock_alpaca_client.get_positions()
        
        # Assert - verify only real position data
        assert len(result) == 1
        position = result[0]
        assert position["symbol"] == "AAPL"
        assert position["qty"] == 10.0
        assert position["side"] == "long"
        assert position["market_value"] == 1500.00
        assert position["cost_basis"] == 1400.00
        assert position["unrealized_pl"] == 100.00
        
        # Verify no virtual positions
        assert "virtual_positions" not in str(result)
        assert "paper_positions" not in str(result)
        assert "simulated_pnl" not in position

    @pytest.mark.asyncio
    async def test_api_errors_do_not_provide_mock_fallback(self, mock_alpaca_client):
        """Test that API errors do not trigger mock data fallback"""
        # Test connection error
        mock_alpaca_client.trading_client.get_account.side_effect = Exception("Network timeout")
        result = await mock_alpaca_client.test_connection()
        assert result["status"] == "failed"
        assert "mock_data" not in result
        
        # Test quote error  
        mock_alpaca_client.stock_data_client.get_stock_latest_quote.side_effect = Exception("Rate limit exceeded")
        result = await mock_alpaca_client.get_stock_quote("AAPL")
        assert "error" in result
        assert "fallback_quote" not in result
        
        # Test options error
        mock_alpaca_client.option_data_client.get_option_chain.side_effect = Exception("Service unavailable")
        result = await mock_alpaca_client.get_options_chain("AAPL")
        assert "error" in result
        assert "synthetic_chain" not in result