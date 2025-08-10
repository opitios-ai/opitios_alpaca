"""Unit tests for Pydantic models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    # Enums
    OrderSide, OrderType, TimeInForce, PositionSide, OptionType,
    # Stock Models
    StockQuoteRequest, MultiStockQuoteRequest, StockOrderRequest,
    # Options Models
    OptionsChainRequest,
)


class TestEnums:
    """Test enum classes."""
    
    def test_order_side_values(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"
        
    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"
        
    def test_time_in_force_values(self):
        """Test TimeInForce enum values."""
        assert TimeInForce.DAY.value == "day"
        assert TimeInForce.GTC.value == "gtc"
        assert TimeInForce.IOC.value == "ioc"
        assert TimeInForce.FOK.value == "fok"
        
    def test_position_side_values(self):
        """Test PositionSide enum values."""
        assert PositionSide.LONG.value == "long"
        assert PositionSide.SHORT.value == "short"
        
    def test_option_type_values(self):
        """Test OptionType enum values."""
        assert OptionType.CALL.value == "call"
        assert OptionType.PUT.value == "put"


class TestStockQuoteRequest:
    """Test StockQuoteRequest model."""
    
    def test_valid_stock_quote_request(self):
        """Test valid stock quote request creation."""
        request = StockQuoteRequest(symbol="AAPL")
        assert request.symbol == "AAPL"
        
    def test_empty_symbol_accepted(self):
        """Test empty symbol is accepted (model doesn't enforce non-empty)."""
        # The model accepts empty strings, which is fine
        request = StockQuoteRequest(symbol="")
        assert request.symbol == ""
            
    def test_missing_symbol_fails(self):
        """Test missing symbol validation fails."""
        with pytest.raises(ValidationError):
            StockQuoteRequest()


class TestMultiStockQuoteRequest:
    """Test MultiStockQuoteRequest model."""
    
    def test_valid_multi_stock_quote_request(self):
        """Test valid multi stock quote request creation."""
        symbols = ["AAPL", "TSLA", "GOOGL"]
        request = MultiStockQuoteRequest(symbols=symbols)
        assert request.symbols == symbols
        
    def test_empty_symbols_list(self):
        """Test empty symbols list validation."""
        request = MultiStockQuoteRequest(symbols=[])
        assert request.symbols == []
        
    def test_missing_symbols_fails(self):
        """Test missing symbols validation fails."""
        with pytest.raises(ValidationError):
            MultiStockQuoteRequest()


class TestStockOrderRequest:
    """Test StockOrderRequest model."""
    
    def test_valid_market_order(self):
        """Test valid market order creation."""
        order = StockOrderRequest(
            symbol="AAPL",
            qty=10.0,
            side=OrderSide.BUY
        )
        assert order.symbol == "AAPL"
        assert order.qty == 10.0
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.MARKET  # default
        assert order.time_in_force == TimeInForce.DAY  # default
        
    def test_valid_limit_order(self):
        """Test valid limit order creation."""
        order = StockOrderRequest(
            symbol="TSLA",
            qty=5.5,
            side=OrderSide.SELL,
            type=OrderType.LIMIT,
            limit_price=250.50
        )
        assert order.symbol == "TSLA"
        assert order.qty == 5.5
        assert order.side == OrderSide.SELL
        assert order.type == OrderType.LIMIT
        assert order.limit_price == 250.50
        
    def test_zero_quantity_fails(self):
        """Test zero quantity validation fails."""
        with pytest.raises(ValidationError):
            StockOrderRequest(
                symbol="AAPL",
                qty=0.0,
                side=OrderSide.BUY
            )
            
    def test_negative_quantity_fails(self):
        """Test negative quantity validation fails."""
        with pytest.raises(ValidationError):
            StockOrderRequest(
                symbol="AAPL",
                qty=-10.0,
                side=OrderSide.BUY
            )
            
    def test_missing_required_fields_fails(self):
        """Test missing required fields validation fails."""
        with pytest.raises(ValidationError):
            StockOrderRequest(symbol="AAPL")  # missing qty and side


class TestOptionsChainRequest:
    """Test OptionsChainRequest model."""
    
    def test_valid_options_chain_request_minimal(self):
        """Test valid options chain request with minimal data."""
        request = OptionsChainRequest(underlying_symbol="AAPL")
        assert request.underlying_symbol == "AAPL"
        assert request.expiration_date is None
        assert request.option_type is None
        
    def test_valid_options_chain_request_full(self):
        """Test valid options chain request with all data."""
        request = OptionsChainRequest(
            underlying_symbol="AAPL",
            expiration_date="2024-02-16",
            option_type=OptionType.CALL
        )
        assert request.underlying_symbol == "AAPL"
        assert request.expiration_date == "2024-02-16"
        assert request.option_type == OptionType.CALL
        
    def test_missing_underlying_symbol_fails(self):
        """Test missing underlying symbol validation fails."""
        with pytest.raises(ValidationError):
            OptionsChainRequest()


class TestModelSerialization:
    """Test model serialization and deserialization."""
    
    def test_stock_order_request_dict(self):
        """Test stock order request to dict conversion."""
        order = StockOrderRequest(
            symbol="AAPL",
            qty=10.0,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            limit_price=150.0
        )
        order_dict = order.dict()
        
        assert order_dict["symbol"] == "AAPL"
        assert order_dict["qty"] == 10.0
        assert order_dict["side"] == "buy"
        assert order_dict["type"] == "limit"
        assert order_dict["limit_price"] == 150.0
        
    def test_stock_order_request_json(self):
        """Test stock order request JSON serialization."""
        order = StockOrderRequest(
            symbol="AAPL",
            qty=10.0,
            side=OrderSide.BUY
        )
        json_str = order.json()
        assert "AAPL" in json_str
        assert "buy" in json_str
        assert "market" in json_str
        
    def test_from_dict_creation(self):
        """Test model creation from dictionary."""
        data = {
            "symbol": "TSLA",
            "qty": 5.0,
            "side": "sell",
            "type": "limit",
            "limit_price": 200.0
        }
        order = StockOrderRequest(**data)
        assert order.symbol == "TSLA"
        assert order.qty == 5.0
        assert order.side == OrderSide.SELL
        assert order.type == OrderType.LIMIT
        assert order.limit_price == 200.0


class TestFieldValidation:
    """Test field-specific validation rules."""
    
    def test_symbol_field_validation(self):
        """Test symbol field accepts valid stock symbols."""
        # Valid symbols
        valid_symbols = ["AAPL", "TSLA", "GOOGL", "MSFT", "SPY", "QQQ"]
        for symbol in valid_symbols:
            request = StockQuoteRequest(symbol=symbol)
            assert request.symbol == symbol
            
    def test_price_field_validation(self):
        """Test price fields accept valid numeric values."""
        order = StockOrderRequest(
            symbol="AAPL",
            qty=10.0,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            limit_price=150.75,
            stop_price=145.25
        )
        assert order.limit_price == 150.75
        assert order.stop_price == 145.25
        
    def test_enum_field_validation(self):
        """Test enum fields accept valid enum values."""
        order = StockOrderRequest(
            symbol="AAPL",
            qty=10.0,
            side=OrderSide.BUY,
            type=OrderType.STOP_LIMIT,
            time_in_force=TimeInForce.GTC
        )
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.STOP_LIMIT
        assert order.time_in_force == TimeInForce.GTC