"""Unit tests for Pydantic models with real data validation scenarios."""

import pytest
from datetime import datetime, date
from pydantic import ValidationError
from decimal import Decimal

from app.models import (
    # Enums
    OrderSide, OrderType, TimeInForce, PositionSide, OptionType,
    # Stock Models
    MultiStockQuoteRequest, StockOrderRequest,
    # Options Models
    OptionsChainRequest,
)


class TestEnums:
    """Test enum classes with real trading values."""
    
    def test_order_side_values(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"
        
        # Test enum string representation
        assert str(OrderSide.BUY) == "OrderSide.BUY"
        assert str(OrderSide.SELL) == "OrderSide.SELL"
        
    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"
        
        # Test all enum members exist
        assert len(OrderType) >= 4
        
    def test_time_in_force_values(self):
        """Test TimeInForce enum values."""
        assert TimeInForce.DAY.value == "day"
        assert TimeInForce.GTC.value == "gtc"
        assert TimeInForce.IOC.value == "ioc"
        assert TimeInForce.FOK.value == "fok"
        
        # Test case insensitive handling
        assert TimeInForce.GTC.value.upper() == "GTC"
        
    def test_position_side_values(self):
        """Test PositionSide enum values."""
        assert PositionSide.LONG.value == "long"
        assert PositionSide.SHORT.value == "short"
        
    def test_option_type_values(self):
        """Test OptionType enum values."""
        assert OptionType.CALL.value == "call"
        assert OptionType.PUT.value == "put"



class TestMultiStockQuoteRequest:
    """Test MultiStockQuoteRequest model with real symbol combinations."""
    
    def test_valid_multi_stock_quote_request(self):
        """Test valid multi stock quote request creation."""
        symbols = ["AAPL", "TSLA", "GOOGL"]
        request = MultiStockQuoteRequest(symbols=symbols)
        assert request.symbols == symbols
        
    def test_large_symbol_list(self):
        """Test with large list of real symbols."""
        large_symbol_list = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX",
            "CRM", "ADBE", "INTC", "AMD", "PYPL", "SHOP", "SQ", "ROKU",
            "ZOOM", "SNOW", "PLTR", "COIN", "HOOD", "AMC", "GME", "BB"
        ]
        request = MultiStockQuoteRequest(symbols=large_symbol_list)
        assert request.symbols == large_symbol_list
        assert len(request.symbols) == len(large_symbol_list)
        
    def test_empty_symbols_list(self):
        """Test empty symbols list validation."""
        request = MultiStockQuoteRequest(symbols=[])
        assert request.symbols == []
        
    def test_mixed_case_symbols(self):
        """Test handling of mixed case symbols."""
        mixed_symbols = ["AAPL", "tsla", "GoOgL", "aMzN"]
        request = MultiStockQuoteRequest(symbols=mixed_symbols)
        assert request.symbols == mixed_symbols
        
    def test_duplicate_symbols(self):
        """Test handling of duplicate symbols in list."""
        symbols_with_duplicates = ["AAPL", "MSFT", "AAPL", "GOOGL", "MSFT"]
        request = MultiStockQuoteRequest(symbols=symbols_with_duplicates)
        assert request.symbols == symbols_with_duplicates
        
    def test_missing_symbols_fails(self):
        """Test missing symbols validation fails."""
        with pytest.raises(ValidationError):
            MultiStockQuoteRequest()


class TestStockOrderRequest:
    """Test StockOrderRequest model with real trading scenarios."""
    
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
        
    def test_realistic_order_quantities(self):
        """Test realistic order quantities."""
        realistic_quantities = [1, 10, 100, 1000, 0.1, 0.01, 999.99]
        
        for qty in realistic_quantities:
            order = StockOrderRequest(
                symbol="SPY",
                qty=qty,
                side=OrderSide.BUY
            )
            assert order.qty == qty
            
    def test_realistic_limit_prices(self):
        """Test realistic limit prices."""
        realistic_prices = [
            0.01,    # Penny stock
            1.50,    # Low price stock
            150.75,  # Mid-range stock
            3500.00, # High price stock (like BRK.A scaled)
            999999.99  # Very high price
        ]
        
        for price in realistic_prices:
            order = StockOrderRequest(
                symbol="AAPL",
                qty=1.0,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                limit_price=price
            )
            assert order.limit_price == price
            
    def test_stop_loss_order(self):
        """Test stop loss order configuration."""
        order = StockOrderRequest(
            symbol="TSLA",
            qty=10.0,
            side=OrderSide.SELL,
            type=OrderType.STOP,
            stop_price=200.00
        )
        assert order.type == OrderType.STOP
        assert order.stop_price == 200.00
        
    def test_stop_limit_order(self):
        """Test stop limit order configuration."""
        order = StockOrderRequest(
            symbol="NVDA",
            qty=5.0,
            side=OrderSide.SELL,
            type=OrderType.STOP_LIMIT,
            stop_price=450.00,
            limit_price=445.00
        )
        assert order.type == OrderType.STOP_LIMIT
        assert order.stop_price == 450.00
        assert order.limit_price == 445.00
        
    def test_gtc_order(self):
        """Test Good Till Cancelled order."""
        order = StockOrderRequest(
            symbol="AMZN",
            qty=1.0,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            limit_price=3000.00,
            time_in_force=TimeInForce.GTC
        )
        assert order.time_in_force == TimeInForce.GTC
        
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
            
    def test_negative_limit_price_fails(self):
        """Test negative limit price validation fails."""
        with pytest.raises(ValidationError):
            StockOrderRequest(
                symbol="AAPL",
                qty=10.0,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                limit_price=-150.00
            )
            
    def test_missing_required_fields_fails(self):
        """Test missing required fields validation fails."""
        with pytest.raises(ValidationError):
            StockOrderRequest(symbol="AAPL")  # missing qty and side


class TestOptionsChainRequest:
    """Test OptionsChainRequest model with real options scenarios."""
    
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
        
    def test_real_expiration_dates(self):
        """Test with real option expiration date formats."""
        expiration_dates = [
            "2024-12-20",  # Monthly expiration
            "2024-12-27",  # Weekly expiration
            "2025-01-17",  # LEAPS expiration
            "2024-12-31",  # Year-end expiration
        ]
        
        for exp_date in expiration_dates:
            request = OptionsChainRequest(
                underlying_symbol="SPY",
                expiration_date=exp_date,
                option_type=OptionType.CALL
            )
            assert request.expiration_date == exp_date
            
    def test_popular_underlying_symbols(self):
        """Test with popular options underlying symbols."""
        popular_symbols = [
            "SPY", "QQQ", "IWM",  # ETFs
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",  # Tech stocks
            "JPM", "BAC", "GS",  # Financials
            "XOM", "CVX",  # Energy
        ]
        
        for symbol in popular_symbols:
            request = OptionsChainRequest(
                underlying_symbol=symbol,
                option_type=OptionType.CALL
            )
            assert request.underlying_symbol == symbol
            
    def test_both_option_types(self):
        """Test both call and put options."""
        for option_type in [OptionType.CALL, OptionType.PUT]:
            request = OptionsChainRequest(
                underlying_symbol="AAPL",
                expiration_date="2024-12-20",
                option_type=option_type
            )
            assert request.option_type == option_type
        
    def test_missing_underlying_symbol_fails(self):
        """Test missing underlying symbol validation fails."""
        with pytest.raises(ValidationError):
            OptionsChainRequest()


class TestModelSerialization:
    """Test model serialization and deserialization with real data."""
    
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
        
    def test_complex_order_serialization(self):
        """Test complex order with all fields serialization."""
        order = StockOrderRequest(
            symbol="TSLA",
            qty=25.5,
            side=OrderSide.SELL,
            type=OrderType.STOP_LIMIT,
            limit_price=245.75,
            stop_price=250.00,
            time_in_force=TimeInForce.GTC
        )
        
        order_dict = order.dict()
        assert order_dict["symbol"] == "TSLA"
        assert order_dict["qty"] == 25.5
        assert order_dict["side"] == "sell"
        assert order_dict["type"] == "stop_limit"
        assert order_dict["limit_price"] == 245.75
        assert order_dict["stop_price"] == 250.00
        assert order_dict["time_in_force"] == "gtc"
        
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
        
    def test_options_chain_serialization(self):
        """Test options chain request serialization."""
        request = OptionsChainRequest(
            underlying_symbol="SPY",
            expiration_date="2024-12-20",
            option_type=OptionType.PUT
        )
        
        request_dict = request.dict()
        assert request_dict["underlying_symbol"] == "SPY"
        assert request_dict["expiration_date"] == "2024-12-20"
        assert request_dict["option_type"] == "put"


class TestFieldValidation:
    """Test field-specific validation rules with real trading data."""
    
    def test_symbol_field_validation(self):
        """Test symbol field accepts valid stock symbols in MultiStockQuoteRequest."""
        # Valid symbols including special cases
        valid_symbols = [
            "AAPL", "TSLA", "GOOGL", "MSFT", "SPY", "QQQ",
            "BRK.A", "BRK.B", "BF.B",  # Symbols with dots
            "GOOGL", "GOOG",  # Class A and C shares
        ]
        
        for symbol in valid_symbols:
            request = MultiStockQuoteRequest(symbols=[symbol])
            assert symbol in request.symbols
            
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
        
    def test_decimal_precision_handling(self):
        """Test handling of decimal precision in prices."""
        precise_prices = [
            150.1234,  # 4 decimal places
            0.0001,    # Very small price
            9999.9999, # Large price with precision
        ]
        
        for price in precise_prices:
            order = StockOrderRequest(
                symbol="AAPL",
                qty=1.0,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                limit_price=price
            )
            assert order.limit_price == price
        
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
        
    def test_fractional_shares_validation(self):
        """Test validation of fractional share quantities."""
        fractional_quantities = [0.1, 0.01, 0.001, 0.5, 1.5, 10.25, 100.333]
        
        for qty in fractional_quantities:
            order = StockOrderRequest(
                symbol="AAPL",
                qty=qty,
                side=OrderSide.BUY
            )
            assert order.qty == qty


class TestRealWorldScenarios:
    """Test models with real-world trading scenarios."""
    
    def test_day_trading_orders(self):
        """Test day trading order scenarios."""
        # Quick scalp trade
        scalp_order = StockOrderRequest(
            symbol="SPY",
            qty=1000.0,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            limit_price=450.50,
            time_in_force=TimeInForce.DAY
        )
        assert scalp_order.time_in_force == TimeInForce.DAY
        
    def test_swing_trading_orders(self):
        """Test swing trading order scenarios."""
        # Swing trade with stop loss
        swing_order = StockOrderRequest(
            symbol="AAPL",
            qty=50.0,
            side=OrderSide.BUY,
            type=OrderType.STOP_LIMIT,
            stop_price=148.00,
            limit_price=150.00,
            time_in_force=TimeInForce.GTC
        )
        assert swing_order.type == OrderType.STOP_LIMIT
        assert swing_order.time_in_force == TimeInForce.GTC
        
    def test_long_term_investment_orders(self):
        """Test long-term investment order scenarios."""
        # Dollar cost averaging order
        dca_order = StockOrderRequest(
            symbol="VOO",  # Vanguard S&P 500 ETF
            qty=10.0,
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY
        )
        assert dca_order.type == OrderType.MARKET
        
    def test_options_weekly_expiry(self):
        """Test options with weekly expiry dates."""
        # 0DTE options (zero days to expiration)
        today_exp = OptionsChainRequest(
            underlying_symbol="SPY",
            expiration_date="2024-12-13",  # Assuming this is today
            option_type=OptionType.CALL
        )
        assert today_exp.underlying_symbol == "SPY"
        
    def test_earnings_play_scenarios(self):
        """Test options scenarios around earnings."""
        # Earnings straddle setup
        earnings_calls = OptionsChainRequest(
            underlying_symbol="AAPL",
            expiration_date="2024-02-02",  # Earnings week
            option_type=OptionType.CALL
        )
        
        earnings_puts = OptionsChainRequest(
            underlying_symbol="AAPL",
            expiration_date="2024-02-02",  # Earnings week
            option_type=OptionType.PUT
        )
        
        assert earnings_calls.option_type == OptionType.CALL
        assert earnings_puts.option_type == OptionType.PUT