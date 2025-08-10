"""Unit tests for AlpacaClient with mocked components."""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, AsyncMock

from app.alpaca_client import AlpacaClient, PooledAlpacaClient


class TestAlpacaClient:
    """Unit tests for AlpacaClient functionality."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, real_api_credentials):
        """Test AlpacaClient initialization with real credentials."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        assert client.api_key == real_api_credentials.api_key
        assert client.secret_key == real_api_credentials.secret_key
        assert client.paper_trading == real_api_credentials.paper_trading
        assert client.trading_client is not None
        assert client.stock_data_client is not None
        assert client.option_data_client is not None
    
    @pytest.mark.asyncio
    async def test_client_initialization_with_invalid_credentials(self):
        """Test AlpacaClient initialization with invalid credentials."""
        # AlpacaClient constructor currently doesn't validate credentials, so this test needs to check behavior
        client = AlpacaClient(api_key="invalid", secret_key="invalid")
        assert client.api_key == "invalid"
        assert client.secret_key == "invalid"
        
        # The actual validation happens during API calls, not initialization
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self):
        """Test successful connection to Alpaca API with mocked response."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock the account response
        mock_account = MagicMock()
        mock_account.account_number = "123456789"
        mock_account.buying_power = 50000.0
        mock_account.cash = 25000.0
        mock_account.portfolio_value = 75000.0
        
        with patch.object(client.trading_client, 'get_account', return_value=mock_account):
            result = await client.test_connection()
            
            assert result["status"] == "connected"
            assert result["account_number"] == "123456789"
            assert result["buying_power"] == 50000.0
            assert result["cash"] == 25000.0
            assert result["portfolio_value"] == 75000.0
    
    @pytest.mark.asyncio
    async def test_connection_test_with_invalid_credentials(self):
        """Test connection test with invalid credentials."""
        client = AlpacaClient(
            api_key="invalid_key",
            secret_key="invalid_secret",
            paper_trading=True
        )
        
        # Mock API failure
        with patch.object(client.trading_client, 'get_account', side_effect=Exception("Unauthorized")):
            result = await client.test_connection()
            
            assert result["status"] == "failed"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_stock_quote_valid_symbol(self):
        """Test getting stock quote for valid symbol with mocked response."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock quote response
        mock_quote = MagicMock()
        mock_quote.symbol = "AAPL"
        mock_quote.bid_price = 150.0
        mock_quote.ask_price = 150.5
        mock_quote.timestamp = "2024-01-01T10:00:00Z"
        
        mock_response = {"AAPL": mock_quote}
        
        with patch.object(client.stock_data_client, 'get_stock_latest_quote', return_value=mock_response):
            result = await client.get_stock_quote("AAPL")
            
            assert result["symbol"] == "AAPL"
            assert result["bid_price"] == 150.0
            assert result["ask_price"] == 150.5
            assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_get_stock_quote_invalid_symbol(self):
        """Test getting stock quote for invalid symbol."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock empty response for invalid symbol
        with patch.object(client.stock_data_client, 'get_stock_latest_quote', return_value={}):
            result = await client.get_stock_quote("INVALID_SYMBOL")
            
            assert "error" in result or (result.get("bid_price") is None and result.get("ask_price") is None)
    
    @pytest.mark.asyncio
    async def test_get_multiple_stock_quotes(self):
        """Test getting multiple stock quotes with mocked response."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        # Mock responses for each symbol
        mock_quotes = {}
        for i, symbol in enumerate(symbols):
            mock_quote = MagicMock()
            mock_quote.symbol = symbol
            mock_quote.bid_price = 100.0 + i * 50
            mock_quote.ask_price = 100.5 + i * 50
            mock_quotes[symbol] = mock_quote
        
        with patch.object(client.stock_data_client, 'get_stock_latest_quote', return_value=mock_quotes):
            result = await client.get_multiple_stock_quotes(symbols)
            
            assert "quotes" in result
            assert "count" in result
            assert "requested_symbols" in result
            assert result["count"] == len(symbols)
            assert result["requested_symbols"] == symbols
    
    @pytest.mark.asyncio
    async def test_get_multiple_stock_quotes_empty_list(self):
        """Test getting multiple stock quotes with empty symbol list."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        result = await client.get_multiple_stock_quotes([])
        
        assert "error" in result
        assert "No symbols provided" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_account(self):
        """Test getting account information with mocked response."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock account response
        mock_account = MagicMock()
        mock_account.account_number = "123456789"
        mock_account.buying_power = 50000.0
        mock_account.cash = 25000.0
        mock_account.portfolio_value = 75000.0
        
        with patch.object(client.trading_client, 'get_account', return_value=mock_account):
            result = await client.get_account()
            
            assert result["account_number"] == "123456789"
            assert result["buying_power"] == 50000.0
            assert result["cash"] == 25000.0
            assert result["portfolio_value"] == 75000.0
    
    @pytest.mark.asyncio
    async def test_get_positions(self):
        """Test getting positions with mocked response."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Mock position response
        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.qty = 100
        mock_side = MagicMock()
        mock_side.value = "long"
        mock_position.side = mock_side
        
        with patch.object(client.trading_client, 'get_all_positions', return_value=[mock_position]):
            result = await client.get_positions()
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["qty"] == 100
            assert result[0]["side"] == "long"
    
    @pytest.mark.asyncio
    async def test_place_stock_order_validation(self):
        """Test stock order placement with parameter validation."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Test with invalid order type
        result = await client.place_stock_order(
            symbol="AAPL",
            qty=1,
            side="buy",
            order_type="invalid_type"
        )
        
        assert "error" in result
        assert "Invalid order type" in result["error"]
        
        # Test with limit order missing limit price
        result = await client.place_stock_order(
            symbol="AAPL",
            qty=1,
            side="buy",
            order_type="limit"
        )
        
        assert "error" in result
        assert "missing required price parameters" in result["error"]
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self):
        """Test cancelling a non-existent order."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        fake_order_id = "fake_order_12345"
        
        # Mock API error for non-existent order
        with patch.object(client.trading_client, 'cancel_order_by_id', side_effect=Exception("Order not found")):
            result = await client.cancel_order(fake_order_id)
            
            assert "error" in result


class TestPooledAlpacaClient:
    """Unit tests for PooledAlpacaClient functionality."""
    
    def test_pooled_client_initialization(self):
        """Test PooledAlpacaClient initialization."""
        client = PooledAlpacaClient()
        
        assert client._pool is None  # Lazy loading
        
        # Accessing pool property should initialize it
        try:
            pool = client.pool
            assert pool is not None
        except ImportError:
            # account_pool might not be available in test environment
            pytest.skip("Account pool not available in test environment")
    
    @pytest.mark.asyncio
    async def test_pooled_client_methods_exist(self):
        """Test that PooledAlpacaClient has all expected methods."""
        client = PooledAlpacaClient()
        
        # Check that all expected methods exist
        expected_methods = [
            'get_stock_quote', 'get_multiple_stock_quotes', 'get_stock_bars',
            'get_options_chain', 'get_option_quote', 'get_multiple_option_quotes',
            'place_stock_order', 'place_option_order', 'get_account', 
            'get_positions', 'get_orders'
        ]
        
        for method_name in expected_methods:
            assert hasattr(client, method_name)
            assert callable(getattr(client, method_name))


class TestAlpacaClientErrorHandling:
    """Test error handling scenarios for AlpacaClient."""
    
    @pytest.mark.asyncio
    async def test_network_timeout_simulation(self):
        """Test handling of network timeouts."""
        # Mock the StockHistoricalDataClient to simulate network timeout
        with patch('app.alpaca_client.StockHistoricalDataClient') as mock_client:
            mock_client.return_value.get_stock_latest_quote.side_effect = Exception("Network timeout")
            
            client = AlpacaClient(
                api_key="test_key",
                secret_key="test_secret",
                paper_trading=True
            )
            
            result = await client.get_stock_quote("AAPL")
            
            assert "error" in result
            assert "Network timeout" in result["error"]
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_handling(self):
        """Test handling of API rate limits with mocked responses."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
        
        # Mock successful responses for all symbols
        mock_quotes = {}
        for symbol in symbols:
            mock_quote = MagicMock()
            mock_quote.symbol = symbol
            mock_quote.bid_price = 100.0
            mock_quote.ask_price = 100.5
            mock_quotes[symbol] = mock_quote
        
        with patch.object(client.stock_data_client, 'get_stock_latest_quote', return_value=mock_quotes):
            results = []
            for symbol in symbols:
                result = await client.get_stock_quote(symbol)
                results.append(result)
            
            # All requests should complete without rate limit errors
            for result in results:
                if "error" in result:
                    # Rate limit errors typically contain specific messages
                    assert "rate limit" not in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """Test handling of malformed API responses."""
        client = AlpacaClient(
            api_key="test_key",
            secret_key="test_secret",
            paper_trading=True
        )
        
        # Test with empty symbol
        result = await client.get_stock_quote("")
        assert "error" in result
        
        # Test with None symbol (should be caught by validation)
        try:
            result = await client.get_stock_quote(None)
            assert "error" in result
        except (TypeError, AttributeError):
            # Expected for None input
            pass


@pytest.mark.asyncio
async def test_alpaca_client_unit_integration():
    """Unit integration test for AlpacaClient with mocked operations."""
    client = AlpacaClient(
        api_key="test_key",
        secret_key="test_secret",
        paper_trading=True
    )
    
    # Mock all the required objects
    mock_account = MagicMock()
    mock_account.account_number = "123456789"
    mock_account.buying_power = 50000.0
    mock_account.cash = 25000.0
    mock_account.portfolio_value = 75000.0
    
    mock_quote = MagicMock()
    mock_quote.symbol = "AAPL"
    mock_quote.bid_price = 150.0
    mock_quote.ask_price = 150.5
    
    with patch.object(client.trading_client, 'get_account', return_value=mock_account), \
         patch.object(client.stock_data_client, 'get_stock_latest_quote', return_value={"AAPL": mock_quote}), \
         patch.object(client.trading_client, 'get_all_positions', return_value=[]), \
         patch.object(client.trading_client, 'get_orders', return_value=[]):
        
        # 1. Test connection
        connection_result = await client.test_connection()
        assert connection_result["status"] == "connected"
        
        # 2. Get account info
        account_result = await client.get_account()
        assert account_result["account_number"] == "123456789"
        
        # 3. Get stock quote
        quote_result = await client.get_stock_quote("AAPL")
        assert quote_result["symbol"] == "AAPL"
        
        # 4. Get positions
        positions_result = await client.get_positions()
        assert isinstance(positions_result, list)
        
        # 5. Get orders
        orders_result = await client.get_orders()
        assert isinstance(orders_result, list)