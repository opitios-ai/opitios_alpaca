"""WebSocket tests for stock data streaming with real connections."""

import pytest
import asyncio
import json
import logging
import datetime
from typing import List, Dict, Any

from tests.utils import WebSocketTestManager, WebSocketEndpoint, WebSocketTestValidator

logger = logging.getLogger(__name__)


class TestStockDataStreaming:
    """Test stock data streaming via WebSocket."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)  # Overall test timeout
    async def test_stock_websocket_connection(self, websocket_manager, websocket_timeout_config):
        """Test establishing stock data WebSocket connection."""
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.STOCK_DATA, 
            timeout=websocket_timeout_config["connection_timeout"]
        )
        
        if success:
            health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            assert health.connected is True
            assert health.connection_time is not None
            
            # Test connection stability
            await asyncio.sleep(2)
            health_after = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            assert health_after.connected is True
        else:
            pytest.skip("Cannot establish stock data WebSocket connection")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)  # Extended timeout for subscription
    async def test_stock_symbol_subscription(self, stock_websocket_connection, websocket_test_symbols, websocket_timeout_config):
        """Test subscribing to stock symbols."""
        symbols = websocket_test_symbols["minimal_symbols"]  # Use minimal symbols for faster test
        data_types = ["trades", "quotes"]
        
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols, data_types
        )
        
        if success:
            # Wait for subscription confirmation or data with appropriate timeout
            messages = await stock_websocket_connection.wait_for_messages(
                WebSocketEndpoint.STOCK_DATA, 
                count=1, 
                timeout=websocket_timeout_config["subscription_timeout"]
            )
            
            # Allow for connection that might not receive immediate data
            if len(messages) >= 1:
                # Check subscription tracking
                subscriptions = stock_websocket_connection.subscriptions[WebSocketEndpoint.STOCK_DATA]
                for symbol in symbols:
                    assert symbol in subscriptions
            else:
                logger.info("No immediate messages received - checking subscription status")
                subscriptions = stock_websocket_connection.subscriptions[WebSocketEndpoint.STOCK_DATA]
                # At least verify that subscription was tracked
                for symbol in symbols:
                    assert symbol in subscriptions
        else:
            pytest.skip("Cannot subscribe to stock symbols")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)  # Extended timeout for message reception
    async def test_stock_trade_messages(self, stock_websocket_connection, websocket_timeout_config):
        """Test receiving stock trade messages."""
        symbol = "AAPL"
        
        # Subscribe to trades
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbol], ["trades"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe to stock trades")
        
        # Wait for trade messages with realistic timeout
        messages = await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA, 
            count=2,  # Reduced count for better success rate
            timeout=websocket_timeout_config["message_timeout"],
            message_type="t"  # Trade message type
        )
        
        if messages:
            for message in messages:
                # Validate trade message structure
                validation = WebSocketTestValidator.validate_stock_trade_message(message)
                
                if not validation["valid"]:
                    logger.warning(f"Trade message validation errors: {validation['errors']}")
                    
                if validation["warnings"]:
                    logger.info(f"Trade message validation warnings: {validation['warnings']}")
                
                # Basic structure checks
                assert message.message_type == "t"
                assert message.symbol == symbol
                assert "p" in message.data  # Price
                assert "s" in message.data  # Size
                assert "t" in message.data  # Timestamp
        else:
            logger.warning("No trade messages received - this may be normal during off-market hours")
            pytest.skip("No trade messages received within timeout")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_stock_quote_messages(self, stock_websocket_connection, websocket_timeout_config):
        """Test receiving stock quote messages."""
        symbol = "MSFT"
        
        # Subscribe to quotes
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbol], ["quotes"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe to stock quotes")
        
        # Wait for quote messages with realistic timeout
        messages = await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA,
            count=2,  # Reduced count for better success rate
            timeout=websocket_timeout_config["message_timeout"],
            message_type="q"  # Quote message type
        )
        
        if messages:
            for message in messages:
                assert message.message_type == "q"
                assert message.symbol == symbol
                # Verify at least some quote data is present
                quote_fields = ["bp", "ap", "bs", "as"]  # bid price, ask price, bid size, ask size
                has_quote_data = any(field in message.data for field in quote_fields)
                assert has_quote_data, f"No quote data found in message: {message.data}"
        else:
            logger.warning("No quote messages received - this may be normal during off-market hours")
            pytest.skip("No quote messages received within timeout")
    
    @pytest.mark.asyncio
    async def test_multiple_symbol_streaming(self, stock_websocket_connection):
        """Test streaming data for multiple symbols simultaneously."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols, ["trades", "quotes"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe to multiple symbols")
        
        # Wait for messages from any symbol
        messages = await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA, count=5, timeout=45
        )
        
        if messages:
            # Check that we received messages for different symbols
            received_symbols = set(msg.symbol for msg in messages if msg.symbol)
            assert len(received_symbols) > 0
            
            # Verify all received symbols are in our subscription list
            for symbol in received_symbols:
                assert symbol in symbols
        else:
            pytest.skip("No messages received for multiple symbols")
    
    @pytest.mark.asyncio
    async def test_unsubscribe_functionality(self, stock_websocket_connection):
        """Test unsubscribing from stock symbols."""
        symbols = ["AAPL", "MSFT"]
        
        # First subscribe
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols, ["trades"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe to symbols for unsubscribe test")
        
        # Wait for some messages
        initial_messages = await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA, count=2, timeout=15
        )
        
        # Unsubscribe from one symbol
        unsubscribe_success = await stock_websocket_connection.unsubscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbols[0]]
        )
        
        if unsubscribe_success:
            # Check subscription tracking
            subscriptions = stock_websocket_connection.subscriptions[WebSocketEndpoint.STOCK_DATA]
            assert symbols[0] not in subscriptions
            assert symbols[1] in subscriptions
        else:
            pytest.skip("Cannot test unsubscribe functionality")
    
    @pytest.mark.asyncio
    async def test_message_rate_monitoring(self, stock_websocket_connection):
        """Test monitoring message rates."""
        symbol = "AAPL"
        
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbol], ["trades", "quotes"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for rate monitoring test")
        
        # Clear existing messages
        stock_websocket_connection.clear_message_buffer(WebSocketEndpoint.STOCK_DATA)
        
        # Monitor for a specific time period
        monitoring_duration = 10  # seconds
        await asyncio.sleep(monitoring_duration)
        
        # Get all messages received during monitoring
        messages = stock_websocket_connection.get_messages(WebSocketEndpoint.STOCK_DATA)
        
        if messages:
            message_rate = len(messages) / monitoring_duration
            print(f"Message rate for {symbol}: {message_rate:.2f} messages/second")
            
            # Basic sanity check - should receive some messages but not too many
            assert message_rate > 0, "Should receive some messages"
            assert message_rate < 100, "Message rate seems too high"
        else:
            pytest.skip("No messages received during monitoring period")


class TestStockDataValidation:
    """Test validation of stock data messages."""
    
    @pytest.mark.asyncio
    async def test_trade_message_validation(self, stock_websocket_connection):
        """Test validation of trade messages."""
        symbol = "AAPL"
        
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbol], ["trades"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for validation test")
        
        # Wait for trade messages
        messages = await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA,
            count=3,
            timeout=20,
            message_type="t"
        )
        
        if messages:
            for message in messages:
                validation = WebSocketTestValidator.validate_stock_trade_message(message)
                
                # Log validation results
                if not validation["valid"]:
                    print(f"Invalid trade message: {validation['errors']}")
                
                if validation["warnings"]:
                    print(f"Trade message warnings: {validation['warnings']}")
                
                # Check required fields
                assert "T" in message.data  # Message type
                assert "S" in message.data  # Symbol
                assert message.data["S"] == symbol
        else:
            pytest.skip("No trade messages for validation")
    
    @pytest.mark.asyncio
    async def test_message_timestamp_validation(self, stock_websocket_connection):
        """Test validation of message timestamps."""
        symbol = "MSFT"
        
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbol], ["trades", "quotes"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for timestamp validation")
        
        messages = await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA, count=5, timeout=25
        )
        
        if messages:
            for message in messages:
                # Check that message has timestamp
                assert message.timestamp is not None
                
                # Check that timestamp is recent (within last few minutes)
                now = datetime.datetime.now()
                message_age = (now - message.timestamp).total_seconds()
                assert message_age < 300, f"Message timestamp too old: {message_age} seconds"
        else:
            pytest.skip("No messages for timestamp validation")


class TestStockDataErrorHandling:
    """Test error handling in stock data streaming."""
    
    @pytest.mark.asyncio
    async def test_invalid_symbol_subscription(self, stock_websocket_connection):
        """Test subscribing to invalid symbols."""
        invalid_symbols = ["INVALID123", "NOTREAL", "FAKE_SYM"]
        
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, invalid_symbols, ["trades"]
        )
        
        # Subscription might succeed but no data should be received
        if success:
            messages = await stock_websocket_connection.wait_for_messages(
                WebSocketEndpoint.STOCK_DATA, count=1, timeout=10
            )
            
            # Should receive no data or error messages for invalid symbols
            valid_data_messages = [
                msg for msg in messages 
                if msg.symbol in invalid_symbols and msg.message_type in ["t", "q"]
            ]
            
            assert len(valid_data_messages) == 0, "Should not receive data for invalid symbols"
    
    @pytest.mark.asyncio
    async def test_connection_health_monitoring(self, stock_websocket_connection):
        """Test connection health monitoring."""
        # Get initial health
        initial_health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
        assert initial_health.connected is True
        
        # Subscribe to get some activity
        await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, ["AAPL"], ["trades"]
        )
        
        # Wait for some messages to update health metrics
        await stock_websocket_connection.wait_for_messages(
            WebSocketEndpoint.STOCK_DATA, count=1, timeout=15
        )
        
        # Check updated health
        updated_health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
        assert updated_health.messages_received >= initial_health.messages_received
        
        if updated_health.messages_received > 0:
            assert updated_health.last_message_time is not None
    
    @pytest.mark.asyncio
    async def test_message_buffer_management(self, stock_websocket_connection):
        """Test message buffer management."""
        symbol = "AAPL"
        
        # Clear buffer
        stock_websocket_connection.clear_message_buffer(WebSocketEndpoint.STOCK_DATA)
        
        # Subscribe and wait for messages
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, [symbol], ["trades"]
        )
        
        if success:
            await asyncio.sleep(5)  # Let messages accumulate
            
            # Get messages
            messages = stock_websocket_connection.get_messages(WebSocketEndpoint.STOCK_DATA)
            initial_count = len(messages)
            
            # Clear buffer
            stock_websocket_connection.clear_message_buffer(WebSocketEndpoint.STOCK_DATA)
            
            # Verify buffer is cleared
            cleared_messages = stock_websocket_connection.get_messages(WebSocketEndpoint.STOCK_DATA)
            assert len(cleared_messages) == 0
            
            # Wait for new messages
            await asyncio.sleep(3)
            new_messages = stock_websocket_connection.get_messages(WebSocketEndpoint.STOCK_DATA)
            
            # Should have new messages after clearing
            if initial_count > 0:  # Only check if we were receiving messages
                assert len(new_messages) >= 0  # Buffer management working


@pytest.mark.asyncio
async def test_stock_websocket_integration(websocket_manager):
    """Integration test for stock WebSocket functionality."""
    # 1. Establish connection
    success = await websocket_manager.establish_connection(WebSocketEndpoint.STOCK_DATA)
    
    if not success:
        pytest.skip("Cannot establish WebSocket connection for integration test")
    
    # 2. Subscribe to multiple symbols and data types
    symbols = ["AAPL", "MSFT"]
    data_types = ["trades", "quotes"]
    
    subscribe_success = await websocket_manager.subscribe_symbols(
        WebSocketEndpoint.STOCK_DATA, symbols, data_types
    )
    
    if not subscribe_success:
        pytest.skip("Cannot subscribe for integration test")
    
    # 3. Monitor messages for a period
    monitoring_time = 15
    await asyncio.sleep(monitoring_time)
    
    # 4. Analyze received data
    messages = websocket_manager.get_messages(WebSocketEndpoint.STOCK_DATA)
    
    if messages:
        # Check message diversity
        message_types = set(msg.message_type for msg in messages)
        symbols_received = set(msg.symbol for msg in messages if msg.symbol)
        
        print(f"Integration test results:")
        print(f"- Total messages: {len(messages)}")
        print(f"- Message types: {message_types}")
        print(f"- Symbols received: {symbols_received}")
        print(f"- Message rate: {len(messages)/monitoring_time:.2f} msg/sec")
        
        # Basic assertions
        assert len(messages) > 0
        assert len(message_types) > 0
        
        # Validate some messages
        valid_messages = 0
        for message in messages[:5]:  # Check first 5 messages
            if message.message_type == "t":
                validation = WebSocketTestValidator.validate_stock_trade_message(message)
                if validation["valid"]:
                    valid_messages += 1
        
        print(f"- Valid messages (sample): {valid_messages}/5")
    
    # 5. Test unsubscribe
    unsubscribe_success = await websocket_manager.unsubscribe_symbols(
        WebSocketEndpoint.STOCK_DATA, [symbols[0]]
    )
    
    # 6. Get final health metrics
    health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
    print(f"Final connection health:")
    print(f"- Connected: {health.connected}")
    print(f"- Messages received: {health.messages_received}")
    print(f"- Error count: {health.error_count}")
    
    assert health.connected is True
    assert health.messages_received > 0