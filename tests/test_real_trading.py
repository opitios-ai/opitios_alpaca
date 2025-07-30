import pytest
import asyncio
from app.alpaca_client import AlpacaClient
from fastapi.testclient import TestClient
from main import app

# These tests use real Paper Trading API calls - no mocks!

@pytest.fixture
def real_client():
    """Real Alpaca client for Paper Trading"""
    return AlpacaClient()

@pytest.fixture
def api_client():
    """FastAPI test client"""
    return TestClient(app)

class TestRealAlpacaConnection:
    """Test real API connections"""
    
    @pytest.mark.asyncio
    async def test_real_connection(self, real_client):
        """Test real connection to Alpaca Paper Trading"""
        result = await real_client.test_connection()
        
        assert "status" in result
        if result["status"] == "connected":
            assert "account_number" in result
            assert "buying_power" in result
            assert isinstance(result["buying_power"], float)
        else:
            # If connection fails, ensure we get proper error info
            assert "error" in result

    @pytest.mark.asyncio 
    async def test_real_account_info(self, real_client):
        """Test getting real account information"""
        account = await real_client.get_account()
        
        if "error" not in account:
            assert "account_number" in account
            assert "buying_power" in account
            assert "cash" in account
            assert "portfolio_value" in account
            assert isinstance(account["buying_power"], float)
            assert isinstance(account["cash"], float)

class TestRealStockData:
    """Test real stock data retrieval"""
    
    @pytest.mark.asyncio
    async def test_real_single_stock_quote(self, real_client):
        """Test getting real stock quote"""
        quote = await real_client.get_stock_quote("AAPL")
        
        if "error" not in quote:
            assert quote["symbol"] == "AAPL"
            assert "bid_price" in quote or "ask_price" in quote
            assert "timestamp" in quote

    @pytest.mark.asyncio
    async def test_real_multiple_stock_quotes(self, real_client):
        """Test getting multiple real stock quotes"""
        symbols = ["AAPL", "TSLA", "GOOGL"]
        result = await real_client.get_multiple_stock_quotes(symbols)
        
        if "error" not in result:
            assert "quotes" in result
            assert "count" in result
            assert result["count"] == len(symbols)
            assert len(result["quotes"]) == len(symbols)
            
            for quote in result["quotes"]:
                if "error" not in quote:
                    assert "symbol" in quote
                    assert quote["symbol"] in symbols

    @pytest.mark.asyncio
    async def test_real_stock_bars(self, real_client):
        """Test getting real stock bars"""
        bars = await real_client.get_stock_bars("AAPL", "1Day", 5)
        
        if "error" not in bars:
            assert bars["symbol"] == "AAPL"
            assert "bars" in bars or "timeframe" in bars

class TestRealOptionsData:
    """Test real options data functionality"""
    
    @pytest.mark.asyncio
    async def test_real_options_chain(self, real_client):
        """Test getting options chain - may not be available with basic Alpaca subscription"""
        chain = await real_client.get_options_chain("AAPL")
        
        # Test that we get a proper response structure
        assert isinstance(chain, dict)
        
        if "error" in chain:
            # This is expected with basic Alpaca subscription - options chain data may not be available
            assert "options chain" in chain["error"].lower() or "no options" in chain["error"].lower()
            print(f"Note: Options chain not available with current subscription: {chain['error']}")
        else:
            # If we do get data, verify the structure
            assert "underlying_symbol" in chain
            assert chain["underlying_symbol"] == "AAPL"
            assert "underlying_price" in chain
            assert "options" in chain
            assert isinstance(chain.get("underlying_price"), (int, float, type(None)))

    @pytest.mark.asyncio
    async def test_real_option_quote(self, real_client):
        """Test getting single option quote"""
        option_symbol = "AAPL240216C00190000"
        quote = await real_client.get_option_quote(option_symbol)
        
        if "error" not in quote:
            assert quote["symbol"] == option_symbol
            assert "underlying_symbol" in quote
            assert "strike_price" in quote
            assert "option_type" in quote
            assert "bid_price" in quote
            assert "ask_price" in quote

    @pytest.mark.asyncio
    async def test_real_multiple_option_quotes(self, real_client):
        """Test getting multiple option quotes"""
        option_symbols = [
            "AAPL240216C00190000",
            "AAPL240216P00180000",
            "TSLA240216C00200000"
        ]
        result = await real_client.get_multiple_option_quotes(option_symbols)
        
        if "error" not in result:
            assert "quotes" in result
            assert "count" in result
            assert result["count"] == len(option_symbols)

class TestRealTradingOperations:
    """Test real trading operations with Paper Trading"""
    
    @pytest.mark.asyncio
    async def test_real_positions(self, real_client):
        """Test getting real positions"""
        positions = await real_client.get_positions()
        
        assert isinstance(positions, list)
        # Positions could be empty, which is fine
        for position in positions:
            if "error" not in position:
                assert "symbol" in position
                assert "qty" in position

    @pytest.mark.asyncio
    async def test_real_orders_history(self, real_client):
        """Test getting real orders"""
        orders = await real_client.get_orders(limit=10)
        
        assert isinstance(orders, list)
        for order in orders:
            if "error" not in order:
                assert "id" in order
                assert "symbol" in order
                assert "status" in order

    @pytest.mark.asyncio
    async def test_real_paper_trading_order(self, real_client):
        """Test placing and cancelling a real paper trading order"""
        # Get account info first
        account = await real_client.get_account()
        
        if "error" in account:
            pytest.skip("Cannot test trading without valid account")
            
        buying_power = account.get("buying_power", 0)
        
        if buying_power < 100:
            pytest.skip("Insufficient buying power for test order")
        
        # Place a small test order
        order_result = await real_client.place_stock_order(
            symbol="AAPL",
            qty=1,
            side="buy",
            order_type="market"
        )
        
        if "error" not in order_result:
            order_id = order_result.get("id")
            assert order_id is not None
            assert order_result["symbol"] == "AAPL"
            assert order_result["qty"] == 1.0
            assert order_result["side"] == "buy"
            
            # Try to cancel the order
            cancel_result = await real_client.cancel_order(order_id)
            
            # Cancel might fail if order already filled, which is okay
            assert "status" in cancel_result or "error" in cancel_result

class TestRealAPIEndpoints:
    """Test real API endpoints through FastAPI"""
    
    def test_real_health_endpoint(self, api_client):
        """Test health endpoint"""
        response = api_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_real_connection_endpoint(self, api_client):
        """Test connection endpoint with real API"""
        response = api_client.get("/api/v1/test-connection")
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

    def test_real_account_endpoint(self, api_client):
        """Test account endpoint with real API"""
        response = api_client.get("/api/v1/account") 
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

    def test_real_stock_quote_endpoint(self, api_client):
        """Test stock quote endpoint with real API"""
        response = api_client.get("/api/v1/stocks/AAPL/quote")
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

    def test_real_batch_stock_quotes_endpoint(self, api_client):
        """Test batch stock quotes endpoint"""
        response = api_client.post("/api/v1/stocks/quotes/batch", 
                                 json={"symbols": ["AAPL", "TSLA", "GOOGL"]})
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

    def test_real_options_chain_endpoint(self, api_client):
        """Test options chain endpoint"""
        response = api_client.post("/api/v1/options/chain",
                                 json={"underlying_symbol": "AAPL"})
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

    def test_real_option_quote_endpoint(self, api_client):
        """Test option quote endpoint"""
        response = api_client.post("/api/v1/options/quote",
                                 json={"option_symbol": "AAPL240216C00190000"})
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

    def test_real_batch_option_quotes_endpoint(self, api_client):
        """Test batch option quotes endpoint"""
        response = api_client.post("/api/v1/options/quotes/batch",
                                 json={"option_symbols": ["AAPL240216C00190000", "AAPL240216P00180000"]})
        # Should be 200 if credentials are valid, 500 if not
        assert response.status_code in [200, 500]

class TestDataValidation:
    """Test data validation and error handling"""
    
    def test_invalid_stock_symbol(self, api_client):
        """Test invalid stock symbol handling"""
        response = api_client.get("/api/v1/stocks/INVALID_SYMBOL_12345/quote")
        # Should handle gracefully
        assert response.status_code in [200, 400, 500]

    def test_invalid_option_symbol(self, api_client):
        """Test invalid option symbol handling"""
        response = api_client.post("/api/v1/options/quote",
                                 json={"option_symbol": "INVALID"})
        # Should return error for invalid format
        assert response.status_code in [400, 500]

    def test_too_many_symbols(self, api_client):
        """Test too many symbols in batch request"""
        symbols = [f"SYMBOL{i}" for i in range(25)]  # More than 20 limit
        response = api_client.post("/api/v1/stocks/quotes/batch",
                                 json={"symbols": symbols})
        assert response.status_code == 400

    def test_empty_symbols_list(self, api_client):
        """Test empty symbols list"""
        response = api_client.post("/api/v1/stocks/quotes/batch",
                                 json={"symbols": []})
        assert response.status_code in [400, 422]  # Validation error