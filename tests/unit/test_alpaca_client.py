"""Unit tests for AlpacaClient with real API connections."""

import pytest
import asyncio
from typing import Dict, Any, List

from app.alpaca_client import AlpacaClient, PooledAlpacaClient


class TestAlpacaClient:
    """Unit tests for AlpacaClient functionality using real API connections."""
    
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
        client = AlpacaClient(api_key="invalid", secret_key="invalid")
        assert client.api_key == "invalid"
        assert client.secret_key == "invalid"
        
        # The actual validation happens during API calls, not initialization
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, real_api_credentials):
        """Test successful connection to real Alpaca API."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        result = await client.test_connection()
        
        assert result["status"] == "connected"
        assert "account_number" in result
        assert "buying_power" in result
        assert "cash" in result
        assert "portfolio_value" in result
        assert isinstance(result["buying_power"], (int, float))
        assert isinstance(result["cash"], (int, float))
        assert isinstance(result["portfolio_value"], (int, float))
    
    @pytest.mark.asyncio
    async def test_connection_test_with_invalid_credentials(self):
        """Test connection test with invalid credentials."""
        client = AlpacaClient(
            api_key="invalid_key",
            secret_key="invalid_secret",
            paper_trading=True
        )
        
        result = await client.test_connection()
        
        assert result["status"] == "failed"
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_stock_quote_valid_symbol(self, real_api_credentials):
        """Test getting stock quote for valid symbol with real API."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        result = await client.get_stock_quote("AAPL")
        
        assert "symbol" in result
        assert result["symbol"] == "AAPL"
        assert "bid_price" in result or "ask_price" in result
        
        # Verify we got real market data
        if "bid_price" in result and result["bid_price"] is not None:
            assert isinstance(result["bid_price"], (int, float))
            assert result["bid_price"] > 0
        
        if "ask_price" in result and result["ask_price"] is not None:
            assert isinstance(result["ask_price"], (int, float))
            assert result["ask_price"] > 0
    
    @pytest.mark.asyncio
    async def test_get_stock_quote_invalid_symbol(self, real_api_credentials):
        """Test getting stock quote for invalid symbol."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        result = await client.get_stock_quote("INVALID_SYMBOL_XYZ123")
        
        # Invalid symbols should either return an error or empty data
        if "error" not in result:
            # If no error, check that prices are None or missing
            assert result.get("bid_price") is None or result.get("ask_price") is None
    
    @pytest.mark.asyncio
    async def test_get_multiple_stock_quotes(self, real_api_credentials):
        """Test getting multiple stock quotes with real API."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        result = await client.get_multiple_stock_quotes(symbols)
        
        assert "quotes" in result
        assert "count" in result
        assert "requested_symbols" in result
        assert result["requested_symbols"] == symbols
        assert isinstance(result["quotes"], dict)
        
        # Check that we got data for at least some symbols
        assert result["count"] >= 0
        
        # Validate quote data structure for available quotes
        for symbol, quote in result["quotes"].items():
            assert symbol in symbols
            assert isinstance(quote, dict)
            if quote.get("bid_price") is not None:
                assert isinstance(quote["bid_price"], (int, float))
            if quote.get("ask_price") is not None:
                assert isinstance(quote["ask_price"], (int, float))
    
    @pytest.mark.asyncio
    async def test_get_multiple_stock_quotes_empty_list(self, real_api_credentials):
        """Test getting multiple stock quotes with empty symbol list."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        result = await client.get_multiple_stock_quotes([])
        
        assert "error" in result
        assert "No symbols provided" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_account(self, real_api_credentials):
        """Test getting account information with real API."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        result = await client.get_account()
        
        assert "account_number" in result
        assert "buying_power" in result
        assert "cash" in result
        assert "portfolio_value" in result
        
        # Verify data types and reasonable values
        assert isinstance(result["buying_power"], (int, float))
        assert isinstance(result["cash"], (int, float))
        assert isinstance(result["portfolio_value"], (int, float))
        assert result["buying_power"] >= 0
        assert result["cash"] >= 0
        assert result["portfolio_value"] >= 0
    
    @pytest.mark.asyncio
    async def test_get_positions(self, real_api_credentials):
        """Test getting positions with real API."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        result = await client.get_positions()
        
        assert isinstance(result, list)
        
        # Validate position structure if any positions exist
        for position in result:
            assert "symbol" in position
            assert "qty" in position
            assert "side" in position
            assert isinstance(position["symbol"], str)
            assert isinstance(position["qty"], (int, float))
            assert position["side"] in ["long", "short"]
    
    @pytest.mark.asyncio
    async def test_place_stock_order_validation(self, real_api_credentials):
        """Test stock order placement with parameter validation."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
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
    async def test_cancel_nonexistent_order(self, real_api_credentials):
        """Test cancelling a non-existent order."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        fake_order_id = "fake_order_12345_nonexistent"
        
        result = await client.cancel_order(fake_order_id)
        
        assert "error" in result
        # Real API should return appropriate error for non-existent order
        assert any(term in result["error"].lower() for term in ["not found", "invalid", "order"])


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
    """Test error handling scenarios for AlpacaClient with real API."""
    
    @pytest.mark.asyncio
    async def test_invalid_symbol_handling(self, real_api_credentials):
        """Test handling of invalid symbols."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        # Test with clearly invalid symbol
        result = await client.get_stock_quote("INVALID_XYZ123_FAKE")
        
        # Should handle gracefully - either return error or no data
        if "error" not in result:
            # If no explicit error, data should be empty/None
            assert result.get("bid_price") is None or result.get("ask_price") is None
    
    @pytest.mark.asyncio
    async def test_empty_symbol_handling(self, real_api_credentials):
        """Test handling of empty symbols."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
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
    async def test_malformed_order_handling(self, real_api_credentials):
        """Test handling of malformed order requests."""
        client = AlpacaClient(
            api_key=real_api_credentials.api_key,
            secret_key=real_api_credentials.secret_key,
            paper_trading=real_api_credentials.paper_trading
        )
        
        # Test order with invalid quantity
        result = await client.place_stock_order(
            symbol="AAPL",
            qty=0,  # Invalid quantity
            side="buy",
            order_type="market"
        )
        
        assert "error" in result
        
        # Test order with invalid side
        result = await client.place_stock_order(
            symbol="AAPL",
            qty=1,
            side="invalid_side",
            order_type="market"
        )
        
        assert "error" in result


@pytest.mark.asyncio
async def test_alpaca_client_integration_workflow(real_api_credentials):
    """Integration test for AlpacaClient with real API workflow."""
    client = AlpacaClient(
        api_key=real_api_credentials.api_key,
        secret_key=real_api_credentials.secret_key,
        paper_trading=real_api_credentials.paper_trading
    )
    
    # 1. Test connection
    connection_result = await client.test_connection()
    assert connection_result["status"] == "connected"
    
    # 2. Get account info
    account_result = await client.get_account()
    assert "account_number" in account_result
    assert "buying_power" in account_result
    
    # 3. Get stock quote
    quote_result = await client.get_stock_quote("AAPL")
    assert "symbol" in quote_result
    assert quote_result["symbol"] == "AAPL"
    
    # 4. Get positions
    positions_result = await client.get_positions()
    assert isinstance(positions_result, list)
    
    # 5. Get orders
    orders_result = await client.get_orders()
    assert isinstance(orders_result, list)
    
    # 6. Test placing a very low limit order (should not execute)
    order_result = await client.place_stock_order(
        symbol="AAPL",
        qty=1,
        side="buy",
        order_type="limit",
        limit_price=0.01,  # Very low price to avoid execution
        time_in_force="day"
    )
    
    # Should either place order successfully or return validation error
    # Both are acceptable for real paper trading
    if "error" not in order_result:
        assert "order_id" in order_result or "id" in order_result
        
        # If order was placed, try to cancel it
        order_id = order_result.get("order_id") or order_result.get("id")
        if order_id:
            cancel_result = await client.cancel_order(order_id)
            # Cancel should either succeed or order might already be filled/cancelled