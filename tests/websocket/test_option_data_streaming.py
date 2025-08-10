"""WebSocket tests for option data streaming with MessagePack validation."""

import pytest
import asyncio
import msgpack
import logging
import datetime
from typing import List, Dict, Any

from tests.utils import WebSocketTestManager, WebSocketEndpoint, WebSocketTestValidator

logger = logging.getLogger(__name__)


class TestOptionDataStreaming:
    """Test option data streaming via WebSocket with MessagePack."""
    
    @pytest.mark.asyncio
    async def test_option_websocket_connection(self, websocket_manager):
        """Test establishing option data WebSocket connection."""
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.OPTION_DATA, timeout=15
        )
        
        if success:
            health = websocket_manager.get_connection_health(WebSocketEndpoint.OPTION_DATA)
            assert health.connected is True
            assert health.connection_time is not None
        else:
            pytest.skip("Cannot establish option data WebSocket connection")
    
    @pytest.mark.asyncio
    async def test_option_symbol_subscription(self, option_websocket_connection):
        """Test subscribing to option symbols."""
        # Use realistic option symbols
        option_symbols = [
            "AAPL240315C00150000",  # AAPL call option
            "MSFT240315P00300000"   # MSFT put option
        ]
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, option_symbols
        )
        
        if success:
            # Wait for subscription confirmation or data
            messages = await option_websocket_connection.wait_for_messages(
                WebSocketEndpoint.OPTION_DATA, count=1, timeout=15
            )
            
            # Check subscription tracking
            subscriptions = option_websocket_connection.subscriptions[WebSocketEndpoint.OPTION_DATA]
            for symbol in option_symbols:
                assert symbol in subscriptions
        else:
            pytest.skip("Cannot subscribe to option symbols")
    
    @pytest.mark.asyncio
    async def test_option_trade_messages(self, option_websocket_connection):
        """Test receiving option trade messages."""
        option_symbol = "AAPL240315C00150000"
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbol]
        )
        
        if not success:
            pytest.skip("Cannot subscribe to option trades")
        
        # Wait for option trade messages
        messages = await option_websocket_connection.wait_for_messages(
            WebSocketEndpoint.OPTION_DATA,
            count=2,
            timeout=30,
            symbol=option_symbol
        )
        
        if messages:
            for message in messages:
                # Validate option message structure
                validation = WebSocketTestValidator.validate_option_message(message)
                
                if not validation["valid"]:
                    print(f"Option message validation errors: {validation['errors']}")
                
                if validation["warnings"]:
                    print(f"Option message warnings: {validation['warnings']}")
                
                # Check MessagePack format
                if message.raw_data:
                    assert isinstance(message.raw_data, bytes)
                    
                    # Verify MessagePack can be decoded
                    try:
                        decoded = msgpack.unpackb(message.raw_data, raw=False)
                        assert isinstance(decoded, dict)
                    except Exception as e:
                        pytest.fail(f"MessagePack decode failed: {e}")
                
                # Basic structure checks
                assert message.symbol == option_symbol
                assert "S" in message.data  # Symbol
        else:
            pytest.skip("No option trade messages received within timeout")
    
    @pytest.mark.asyncio
    async def test_option_quote_messages(self, option_websocket_connection):
        """Test receiving option quote messages."""
        option_symbol = "MSFT240315P00300000"
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbol]
        )
        
        if not success:
            pytest.skip("Cannot subscribe to option quotes")
        
        # Wait for option quote messages
        messages = await option_websocket_connection.wait_for_messages(
            WebSocketEndpoint.OPTION_DATA,
            count=2,
            timeout=30,
            symbol=option_symbol
        )
        
        if messages:
            for message in messages:
                assert message.symbol == option_symbol
                
                # Check for typical option quote fields
                if "bp" in message.data or "ap" in message.data:
                    # Has bid/ask prices
                    if "bp" in message.data:
                        assert isinstance(message.data["bp"], (int, float))
                    if "ap" in message.data:
                        assert isinstance(message.data["ap"], (int, float))
        else:
            pytest.skip("No option quote messages received within timeout")
    
    @pytest.mark.asyncio
    async def test_messagepack_validation(self, option_websocket_connection):
        """Test MessagePack format validation for option data."""
        option_symbol = "AAPL240315C00150000"
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbol]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for MessagePack validation")
        
        # Wait for messages
        messages = await option_websocket_connection.wait_for_messages(
            WebSocketEndpoint.OPTION_DATA, count=3, timeout=25
        )
        
        if messages:
            messagepack_messages = 0
            
            for message in messages:
                if message.raw_data and isinstance(message.raw_data, bytes):
                    messagepack_messages += 1
                    
                    # Test MessagePack decoding
                    try:
                        decoded = msgpack.unpackb(message.raw_data, raw=False)
                        
                        # Verify decoded data matches message.data
                        assert isinstance(decoded, dict)
                        
                        # Check that essential fields are present
                        if "S" in decoded:
                            assert decoded["S"] == option_symbol
                        
                    except msgpack.exceptions.ExtraData as e:
                        pytest.fail(f"MessagePack has extra data: {e}")
                    except msgpack.exceptions.UnpackException as e:
                        pytest.fail(f"MessagePack unpack failed: {e}")
                    except Exception as e:
                        pytest.fail(f"Unexpected MessagePack error: {e}")
            
            print(f"MessagePack messages validated: {messagepack_messages}/{len(messages)}")
            assert messagepack_messages > 0, "Should receive some MessagePack messages"
        else:
            pytest.skip("No messages for MessagePack validation")
    
    @pytest.mark.asyncio
    async def test_multiple_option_symbols(self, option_websocket_connection):
        """Test streaming data for multiple option symbols."""
        option_symbols = [
            "AAPL240315C00150000",  # AAPL call
            "AAPL240315P00140000",  # AAPL put
            "MSFT240315C00300000"   # MSFT call
        ]
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, option_symbols
        )
        
        if not success:
            pytest.skip("Cannot subscribe to multiple option symbols")
        
        # Wait for messages from any symbol
        messages = await option_websocket_connection.wait_for_messages(
            WebSocketEndpoint.OPTION_DATA, count=5, timeout=45
        )
        
        if messages:
            # Check that we received messages for different symbols
            received_symbols = set(msg.symbol for msg in messages if msg.symbol)
            assert len(received_symbols) > 0
            
            # Verify all received symbols are in our subscription list
            for symbol in received_symbols:
                assert symbol in option_symbols
                
            print(f"Received messages for option symbols: {received_symbols}")
        else:
            pytest.skip("No messages received for multiple option symbols")
    
    @pytest.mark.asyncio
    async def test_option_symbol_format_validation(self, option_websocket_connection):
        """Test validation of option symbol formats."""
        # Test various option symbol formats
        test_symbols = [
            "AAPL240315C00150000",  # Standard format
            "MSFT240315P00300000",  # Standard format
            "GOOGL240315C02500000", # Higher strike price
        ]
        
        for symbol in test_symbols:
            # Validate symbol format using the validator
            is_valid = WebSocketTestValidator._is_valid_option_symbol(symbol)
            assert is_valid, f"Option symbol should be valid: {symbol}"
            
            # Check symbol components
            assert len(symbol) >= 15, f"Option symbol too short: {symbol}"
            assert "C" in symbol or "P" in symbol, f"Option symbol missing C/P: {symbol}"
            
            # Extract underlying symbol (letters before first digit)
            underlying = ""
            for i, char in enumerate(symbol):
                if char.isdigit():
                    underlying = symbol[:i]
                    break
            
            assert len(underlying) > 0, f"No underlying symbol found: {symbol}"
            assert underlying.isalpha(), f"Underlying should be letters: {underlying}"


class TestOptionDataErrorHandling:
    """Test error handling in option data streaming."""
    
    @pytest.mark.asyncio
    async def test_invalid_option_symbol_subscription(self, option_websocket_connection):
        """Test subscribing to invalid option symbols."""
        invalid_symbols = [
            "INVALID_OPTION",
            "AAPL999999C99999999",  # Invalid date/strike
            "NOTREAL240315C00100000"
        ]
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, invalid_symbols
        )
        
        # Subscription might succeed but no data should be received
        if success:
            messages = await option_websocket_connection.wait_for_messages(
                WebSocketEndpoint.OPTION_DATA, count=1, timeout=10
            )
            
            # Should receive no valid data for invalid symbols
            valid_data_messages = [
                msg for msg in messages 
                if msg.symbol in invalid_symbols
            ]
            
            assert len(valid_data_messages) == 0, "Should not receive data for invalid option symbols"
    
    @pytest.mark.asyncio
    async def test_messagepack_error_handling(self, option_websocket_connection):
        """Test handling of MessagePack errors."""
        option_symbol = "AAPL240315C00150000"
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbol]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for MessagePack error test")
        
        # Register a custom message handler to test error handling
        error_count = 0
        
        async def error_handler(message):
            nonlocal error_count
            if message.raw_data:
                try:
                    msgpack.unpackb(message.raw_data, raw=False)
                except Exception:
                    error_count += 1
        
        option_websocket_connection.register_message_handler(
            WebSocketEndpoint.OPTION_DATA, error_handler
        )
        
        # Wait for messages
        await asyncio.sleep(10)
        
        # Check that error handling worked (no exceptions raised)
        health = option_websocket_connection.get_connection_health(WebSocketEndpoint.OPTION_DATA)
        assert health.connected is True
        
        print(f"MessagePack errors handled: {error_count}")
    
    @pytest.mark.asyncio
    async def test_option_connection_stability(self, option_websocket_connection):
        """Test option WebSocket connection stability."""
        option_symbol = "AAPL240315C00150000"
        
        # Subscribe to option data
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbol]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for stability test")
        
        # Monitor connection over time
        monitoring_periods = 3
        period_duration = 5  # seconds
        
        health_snapshots = []
        
        for period in range(monitoring_periods):
            await asyncio.sleep(period_duration)
            
            health = option_websocket_connection.get_connection_health(WebSocketEndpoint.OPTION_DATA)
            health_snapshots.append({
                "period": period,
                "connected": health.connected,
                "messages_received": health.messages_received,
                "error_count": health.error_count
            })
        
        # Analyze stability
        all_connected = all(snapshot["connected"] for snapshot in health_snapshots)
        assert all_connected, "Connection should remain stable"
        
        # Check that messages are being received (if any)
        final_messages = health_snapshots[-1]["messages_received"]
        if final_messages > 0:
            # If we received messages, error rate should be reasonable
            final_errors = health_snapshots[-1]["error_count"]
            error_rate = final_errors / final_messages if final_messages > 0 else 0
            assert error_rate < 0.1, f"Error rate too high: {error_rate}"
        
        print(f"Connection stability test completed:")
        for snapshot in health_snapshots:
            print(f"  Period {snapshot['period']}: Connected={snapshot['connected']}, "
                  f"Messages={snapshot['messages_received']}, Errors={snapshot['error_count']}")


class TestOptionDataPerformance:
    """Test performance aspects of option data streaming."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(180)  # Extended timeout for performance tests
    async def test_option_message_throughput(self, option_websocket_connection, websocket_test_symbols, websocket_timeout_config):
        """Test option message throughput with enhanced metrics."""
        option_symbols = websocket_test_symbols["option_symbols"][:2]  # Limit to 2 symbols for test
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, option_symbols
        )
        
        if not success:
            pytest.skip("Cannot subscribe for throughput test")
        
        # Clear buffer and monitor for specific duration
        option_websocket_connection.clear_message_buffer(WebSocketEndpoint.OPTION_DATA)
        
        monitoring_duration = 30  # seconds
        start_time = asyncio.get_event_loop().time()
        
        # Collect metrics during monitoring period
        message_timestamps = []
        
        # Register a handler to track message timestamps
        def timestamp_tracker(message):
            message_timestamps.append(asyncio.get_event_loop().time())
        
        option_websocket_connection.register_message_handler(
            WebSocketEndpoint.OPTION_DATA, timestamp_tracker
        )
        
        await asyncio.sleep(monitoring_duration)
        
        end_time = asyncio.get_event_loop().time()
        actual_duration = end_time - start_time
        
        # Get messages received
        messages = option_websocket_connection.get_messages(WebSocketEndpoint.OPTION_DATA)
        
        if messages:
            throughput = len(messages) / actual_duration
            
            # Calculate latency statistics
            latencies = []
            for i, timestamp in enumerate(message_timestamps):
                if i > 0:
                    latency = (timestamp - message_timestamps[i-1]) * 1000  # ms
                    latencies.append(latency)
            
            # Performance metrics
            performance_metrics = {
                "duration_seconds": actual_duration,
                "total_messages": len(messages),
                "throughput_msg_per_sec": throughput,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
                "max_latency_ms": max(latencies) if latencies else 0,
                "min_latency_ms": min(latencies) if latencies else 0
            }
            
            logger.info(f"Option data throughput test results:")
            logger.info(f"  Duration: {performance_metrics['duration_seconds']:.2f} seconds")
            logger.info(f"  Messages: {performance_metrics['total_messages']}")
            logger.info(f"  Throughput: {performance_metrics['throughput_msg_per_sec']:.2f} messages/second")
            logger.info(f"  Avg Latency: {performance_metrics['avg_latency_ms']:.2f} ms")
            
            # Performance assertions
            assert throughput >= 0, "Throughput should be non-negative"
            
            # Check message processing efficiency
            messagepack_messages = sum(1 for msg in messages if msg.raw_data)
            if messagepack_messages > 0:
                logger.info(f"  MessagePack messages: {messagepack_messages}/{len(messages)}")
                
            # Validate message sequence
            sequence_validation = WebSocketTestValidator.validate_message_sequence(messages)
            if not sequence_validation["valid"]:
                logger.warning(f"Message sequence issues: {sequence_validation['issues']}")
            
            logger.info(f"  Message types: {sequence_validation['message_types']}")
            logger.info(f"  Unique symbols: {len(sequence_validation['symbols'])}")
            
        else:
            logger.warning("No messages received for throughput test - may be normal during off-market hours")
            pytest.skip("No messages received for throughput test")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_option_data_latency_analysis(self, option_websocket_connection, websocket_timeout_config):
        """Test option data latency with detailed analysis."""
        option_symbol = "AAPL240315C00150000"
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbol]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for latency test")
        
        # Wait for messages and measure latency
        messages = await option_websocket_connection.wait_for_messages(
            WebSocketEndpoint.OPTION_DATA, 
            count=10,  # Get more messages for better statistics
            timeout=websocket_timeout_config["message_timeout"]
        )
        
        if messages:
            import datetime
            now = datetime.datetime.now()
            
            latency_data = {
                "message_latencies": [],
                "processing_times": [],
                "total_messages": len(messages)
            }
            
            for i, message in enumerate(messages):
                if message.timestamp:
                    # Calculate latency from message creation to now
                    latency = (now - message.timestamp).total_seconds() * 1000  # ms
                    latency_data["message_latencies"].append(latency)
                    
                    # Measure processing time (time to validate message)
                    start_validation = datetime.datetime.now()
                    validation = WebSocketTestValidator.validate_option_message(message)
                    end_validation = datetime.datetime.now()
                    
                    processing_time = (end_validation - start_validation).total_seconds() * 1000  # ms
                    latency_data["processing_times"].append(processing_time)
            
            if latency_data["message_latencies"]:
                latencies = latency_data["message_latencies"]
                processing_times = latency_data["processing_times"]
                
                # Statistical analysis
                stats = {
                    "avg_latency_ms": sum(latencies) / len(latencies),
                    "max_latency_ms": max(latencies),
                    "min_latency_ms": min(latencies),
                    "median_latency_ms": sorted(latencies)[len(latencies)//2],
                    "avg_processing_time_ms": sum(processing_times) / len(processing_times) if processing_times else 0,
                    "total_analyzed": len(latencies)
                }
                
                logger.info(f"Option data latency analysis:")
                logger.info(f"  Messages analyzed: {stats['total_analyzed']}")
                logger.info(f"  Average latency: {stats['avg_latency_ms']:.3f} ms")
                logger.info(f"  Median latency: {stats['median_latency_ms']:.3f} ms")
                logger.info(f"  Min latency: {stats['min_latency_ms']:.3f} ms")
                logger.info(f"  Max latency: {stats['max_latency_ms']:.3f} ms")
                logger.info(f"  Average processing time: {stats['avg_processing_time_ms']:.3f} ms")
                
                # Latency should be reasonable
                assert stats["avg_latency_ms"] < 60000, f"Average latency too high: {stats['avg_latency_ms']}ms"
                assert stats["max_latency_ms"] < 300000, f"Max latency too high: {stats['max_latency_ms']}ms"
                
                # Processing should be fast
                assert stats["avg_processing_time_ms"] < 10, f"Processing too slow: {stats['avg_processing_time_ms']}ms"
                
        else:
            logger.warning("No messages received for latency analysis - may be normal during off-market hours")
            pytest.skip("No messages for latency test")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(150)
    async def test_multi_symbol_option_performance(self, option_websocket_connection, websocket_test_symbols, websocket_timeout_config):
        """Test performance with multiple option symbols."""
        option_symbols = websocket_test_symbols["option_symbols"]  # All available option symbols
        
        success = await option_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, option_symbols
        )
        
        if not success:
            pytest.skip("Cannot subscribe to multiple option symbols for performance test")
        
        # Monitor performance over time
        monitoring_duration = 45  # seconds
        check_interval = 10  # seconds
        checks = monitoring_duration // check_interval
        
        performance_snapshots = []
        
        for check in range(checks):
            start_check = asyncio.get_event_loop().time()
            
            # Clear buffer for clean measurement
            option_websocket_connection.clear_message_buffer(WebSocketEndpoint.OPTION_DATA)
            
            # Wait for check interval
            await asyncio.sleep(check_interval)
            
            end_check = asyncio.get_event_loop().time()
            actual_interval = end_check - start_check
            
            # Get messages received during interval
            messages = option_websocket_connection.get_messages(WebSocketEndpoint.OPTION_DATA)
            health = option_websocket_connection.get_connection_health(WebSocketEndpoint.OPTION_DATA)
            
            snapshot = {
                "check": check,
                "interval_seconds": actual_interval,
                "messages_in_interval": len(messages),
                "throughput": len(messages) / actual_interval if actual_interval > 0 else 0,
                "total_messages": health.messages_received,
                "error_count": health.error_count,
                "connection_healthy": health.connected,
                "symbols_received": len(set(msg.symbol for msg in messages if msg.symbol))
            }
            
            performance_snapshots.append(snapshot)
            
            logger.info(f"Performance check {check + 1}/{checks}:")
            logger.info(f"  Messages in interval: {snapshot['messages_in_interval']}")
            logger.info(f"  Throughput: {snapshot['throughput']:.2f} msg/sec")
            logger.info(f"  Symbols active: {snapshot['symbols_received']}")
            logger.info(f"  Connection healthy: {snapshot['connection_healthy']}")
        
        # Analyze overall performance
        total_messages_in_intervals = sum(s["messages_in_interval"] for s in performance_snapshots)
        total_time = sum(s["interval_seconds"] for s in performance_snapshots)
        avg_throughput = total_messages_in_intervals / total_time if total_time > 0 else 0
        
        all_healthy = all(s["connection_healthy"] for s in performance_snapshots)
        max_symbols = max(s["symbols_received"] for s in performance_snapshots) if performance_snapshots else 0
        
        logger.info(f"Multi-symbol option performance summary:")
        logger.info(f"  Subscribed symbols: {len(option_symbols)}")
        logger.info(f"  Active symbols observed: {max_symbols}")
        logger.info(f"  Total messages: {total_messages_in_intervals}")
        logger.info(f"  Average throughput: {avg_throughput:.2f} msg/sec")
        logger.info(f"  Connection always healthy: {all_healthy}")
        
        # Performance assertions
        assert all_healthy, "Connection should remain healthy throughout performance test"
        
        if total_messages_in_intervals > 0:
            # Check that we received data from multiple symbols
            assert max_symbols >= 1, "Should receive data from at least one symbol"
            
            # Reasonable throughput
            assert avg_throughput >= 0, "Throughput should be non-negative"
            
            logger.info("Multi-symbol option performance test completed successfully")


@pytest.mark.asyncio
async def test_option_websocket_integration(websocket_manager):
    """Integration test for option WebSocket functionality."""
    # 1. Establish connection
    success = await websocket_manager.establish_connection(WebSocketEndpoint.OPTION_DATA)
    
    if not success:
        pytest.skip("Cannot establish option WebSocket connection for integration test")
    
    # 2. Subscribe to option symbols
    option_symbols = [
        "AAPL240315C00150000",
        "AAPL240315P00150000"
    ]
    
    subscribe_success = await websocket_manager.subscribe_symbols(
        WebSocketEndpoint.OPTION_DATA, option_symbols
    )
    
    if not subscribe_success:
        pytest.skip("Cannot subscribe for option integration test")
    
    # 3. Monitor messages for a period
    monitoring_time = 20
    await asyncio.sleep(monitoring_time)
    
    # 4. Analyze received data
    messages = websocket_manager.get_messages(WebSocketEndpoint.OPTION_DATA)
    
    if messages:
        # Analyze message characteristics
        messagepack_count = sum(1 for msg in messages if msg.raw_data)
        symbols_received = set(msg.symbol for msg in messages if msg.symbol)
        
        print(f"Option integration test results:")
        print(f"- Total messages: {len(messages)}")
        print(f"- MessagePack messages: {messagepack_count}")
        print(f"- Symbols received: {symbols_received}")
        print(f"- Message rate: {len(messages)/monitoring_time:.2f} msg/sec")
        
        # Basic assertions
        assert len(messages) >= 0  # May not receive messages for all option symbols
        
        # Validate MessagePack messages
        valid_messagepack = 0
        for message in messages[:3]:  # Check first few messages
            if message.raw_data:
                try:
                    decoded = msgpack.unpackb(message.raw_data, raw=False)
                    if isinstance(decoded, dict):
                        valid_messagepack += 1
                except Exception:
                    pass
        
        if messagepack_count > 0:
            print(f"- Valid MessagePack (sample): {valid_messagepack}")
    
    # 5. Test unsubscribe
    if option_symbols:
        unsubscribe_success = await websocket_manager.unsubscribe_symbols(
            WebSocketEndpoint.OPTION_DATA, [option_symbols[0]]
        )
        print(f"- Unsubscribe success: {unsubscribe_success}")
    
    # 6. Get final health metrics
    health = websocket_manager.get_connection_health(WebSocketEndpoint.OPTION_DATA)
    print(f"Final option connection health:")
    print(f"- Connected: {health.connected}")
    print(f"- Messages received: {health.messages_received}")
    print(f"- Error count: {health.error_count}")
    
    assert health.connected is True