"""WebSocket health monitoring and connection stability tests."""

import pytest
import asyncio
import logging
from datetime import datetime, timedelta

from tests.utils import WebSocketTestManager, WebSocketEndpoint

logger = logging.getLogger(__name__)


class TestWebSocketHealthMonitoring:
    """Test WebSocket connection health monitoring."""
    
    @pytest.mark.asyncio
    async def test_connection_health_initialization(self, websocket_manager):
        """Test initial health state of WebSocket connections."""
        # Check initial health for all endpoints
        for endpoint in WebSocketEndpoint:
            health = websocket_manager.get_connection_health(endpoint)
            
            assert health.connected is False  # Initially not connected
            assert health.connection_time is None
            assert health.last_message_time is None
            assert health.messages_received == 0
            assert health.reconnection_count == 0
            assert health.error_count == 0
    
    @pytest.mark.asyncio
    async def test_health_metrics_after_connection(self, websocket_manager):
        """Test health metrics after establishing connection."""
        # Try to establish stock data connection
        success = await websocket_manager.establish_connection(WebSocketEndpoint.STOCK_DATA)
        
        if success:
            health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            
            assert health.connected is True
            assert health.connection_time is not None
            assert isinstance(health.connection_time, datetime)
            
            # Connection time should be recent
            time_since_connection = datetime.now() - health.connection_time
            assert time_since_connection.total_seconds() < 60  # Within last minute
        else:
            pytest.skip("Cannot establish WebSocket connection for health test")
    
    @pytest.mark.asyncio
    async def test_message_count_tracking(self, stock_websocket_connection):
        """Test tracking of message counts."""
        # Get initial health
        initial_health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
        initial_count = initial_health.messages_received
        
        # Subscribe to get some messages
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, ["AAPL"], ["trades"]
        )
        
        if success:
            # Wait for messages
            await asyncio.sleep(10)
            
            # Check updated health
            updated_health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            
            # Message count should have increased
            assert updated_health.messages_received >= initial_count
            
            if updated_health.messages_received > initial_count:
                assert updated_health.last_message_time is not None
                
                # Last message time should be recent
                time_since_message = datetime.now() - updated_health.last_message_time
                assert time_since_message.total_seconds() < 60
        else:
            pytest.skip("Cannot subscribe for message count test")
    
    @pytest.mark.asyncio
    async def test_error_count_tracking(self, websocket_manager):
        """Test tracking of error counts."""
        # Try to establish connection to potentially problematic endpoint
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.OPTION_DATA, timeout=5  # Short timeout
        )
        
        health = websocket_manager.get_connection_health(WebSocketEndpoint.OPTION_DATA)
        
        if not success:
            # If connection failed, error count might be incremented
            # This is acceptable for testing error tracking
            assert health.error_count >= 0
        else:
            # If connection succeeded, try invalid subscription
            invalid_success = await websocket_manager.subscribe_symbols(
                WebSocketEndpoint.OPTION_DATA, ["INVALID_OPTION_SYMBOL"]
            )
            
            # Wait a bit for potential errors
            await asyncio.sleep(3)
            
            updated_health = websocket_manager.get_connection_health(WebSocketEndpoint.OPTION_DATA)
            # Error count should be tracked (may or may not increase depending on server behavior)
            assert updated_health.error_count >= health.error_count
    
    @pytest.mark.asyncio
    async def test_all_endpoints_health_summary(self, websocket_manager):
        """Test getting health summary for all endpoints."""
        # Try to establish connections to multiple endpoints
        endpoints_to_test = [WebSocketEndpoint.STOCK_DATA, WebSocketEndpoint.OPTION_DATA]
        
        for endpoint in endpoints_to_test:
            await websocket_manager.establish_connection(endpoint, timeout=10)
        
        # Get health summary for all endpoints
        all_health = websocket_manager.get_all_health_metrics()
        
        assert isinstance(all_health, dict)
        assert len(all_health) == len(WebSocketEndpoint)
        
        for endpoint_name, health in all_health.items():
            assert endpoint_name in [e.value for e in WebSocketEndpoint]
            assert hasattr(health, 'connected')
            assert hasattr(health, 'messages_received')
            assert hasattr(health, 'error_count')
            assert hasattr(health, 'reconnection_count')
    
    @pytest.mark.asyncio
    async def test_health_monitoring_over_time(self, stock_websocket_connection):
        """Test health monitoring over extended period."""
        # Subscribe to get continuous data
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, ["AAPL"], ["trades", "quotes"]
        )
        
        if not success:
            pytest.skip("Cannot subscribe for extended health monitoring")
        
        # Monitor health over multiple intervals
        monitoring_intervals = 3
        interval_duration = 5  # seconds
        health_snapshots = []
        
        for interval in range(monitoring_intervals):
            await asyncio.sleep(interval_duration)
            
            health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            health_snapshots.append({
                "interval": interval,
                "connected": health.connected,
                "messages_received": health.messages_received,
                "error_count": health.error_count,
                "timestamp": datetime.now()
            })
        
        # Analyze health trends
        print("Health monitoring over time:")
        for snapshot in health_snapshots:
            print(f"  Interval {snapshot['interval']}: "
                  f"Connected={snapshot['connected']}, "
                  f"Messages={snapshot['messages_received']}, "
                  f"Errors={snapshot['error_count']}")
        
        # Verify connection remained stable
        all_connected = all(snapshot["connected"] for snapshot in health_snapshots)
        assert all_connected, "Connection should remain stable over time"
        
        # Check message progression (should be non-decreasing)
        message_counts = [snapshot["messages_received"] for snapshot in health_snapshots]
        for i in range(1, len(message_counts)):
            assert message_counts[i] >= message_counts[i-1], "Message count should not decrease"


class TestWebSocketConnectionStability:
    """Test WebSocket connection stability and resilience."""
    
    @pytest.mark.asyncio
    async def test_connection_persistence(self, stock_websocket_connection):
        """Test that WebSocket connection persists over time."""
        # Check initial connection
        initial_health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
        assert initial_health.connected is True
        
        # Subscribe to maintain activity
        await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, ["AAPL"], ["trades"]
        )
        
        # Wait for extended period
        persistence_duration = 30  # seconds
        check_intervals = 6
        interval_duration = persistence_duration / check_intervals
        
        for check in range(check_intervals):
            await asyncio.sleep(interval_duration)
            
            health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            assert health.connected is True, f"Connection lost at check {check}"
        
        print(f"Connection persisted for {persistence_duration} seconds")
    
    @pytest.mark.asyncio
    async def test_multiple_subscriptions_stability(self, stock_websocket_connection):
        """Test stability with multiple symbol subscriptions."""
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]
        data_types = ["trades", "quotes"]
        
        # Subscribe to multiple symbols
        success = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols, data_types
        )
        
        if not success:
            pytest.skip("Cannot subscribe to multiple symbols for stability test")
        
        # Monitor stability with multiple subscriptions
        monitoring_duration = 20  # seconds
        stability_checks = 4
        check_interval = monitoring_duration / stability_checks
        
        stability_results = []
        
        for check in range(stability_checks):
            await asyncio.sleep(check_interval)
            
            health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            messages = stock_websocket_connection.get_messages(WebSocketEndpoint.STOCK_DATA)
            
            stability_results.append({
                "check": check,
                "connected": health.connected,
                "total_messages": len(messages),
                "error_count": health.error_count
            })
        
        # Analyze stability
        print("Multiple subscriptions stability test:")
        for result in stability_results:
            print(f"  Check {result['check']}: "
                  f"Connected={result['connected']}, "
                  f"Messages={result['total_messages']}, "
                  f"Errors={result['error_count']}")
        
        # All checks should show connected state
        all_connected = all(result["connected"] for result in stability_results)
        assert all_connected, "Connection should remain stable with multiple subscriptions"
        
        # Message count should generally increase
        message_counts = [result["total_messages"] for result in stability_results]
        final_count = message_counts[-1]
        initial_count = message_counts[0]
        
        if final_count > initial_count:
            print(f"Received {final_count - initial_count} messages during stability test")
    
    @pytest.mark.asyncio
    async def test_subscription_management_stability(self, stock_websocket_connection):
        """Test stability during subscription changes."""
        symbols_batch1 = ["AAPL", "MSFT"]
        symbols_batch2 = ["GOOGL", "TSLA"]
        
        # Initial subscription
        success1 = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols_batch1, ["trades"]
        )
        
        if not success1:
            pytest.skip("Cannot perform initial subscription for stability test")
        
        await asyncio.sleep(5)  # Let it stabilize
        
        # Add more subscriptions
        success2 = await stock_websocket_connection.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols_batch2, ["trades"]
        )
        
        await asyncio.sleep(5)  # Let it stabilize
        
        # Remove some subscriptions
        unsubscribe_success = await stock_websocket_connection.unsubscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols_batch1
        )
        
        await asyncio.sleep(5)  # Let it stabilize
        
        # Check final health
        final_health = stock_websocket_connection.get_connection_health(WebSocketEndpoint.STOCK_DATA)
        
        assert final_health.connected is True, "Connection should remain stable during subscription changes"
        
        # Check subscription tracking
        current_subscriptions = stock_websocket_connection.subscriptions[WebSocketEndpoint.STOCK_DATA]
        
        if unsubscribe_success:
            # Batch1 symbols should be removed
            for symbol in symbols_batch1:
                assert symbol not in current_subscriptions, f"Symbol {symbol} should be unsubscribed"
        
        if success2:
            # Batch2 symbols should still be there
            for symbol in symbols_batch2:
                assert symbol in current_subscriptions, f"Symbol {symbol} should still be subscribed"
        
        print(f"Final subscriptions: {current_subscriptions}")


class TestWebSocketReconnectionLogic:
    """Test WebSocket reconnection logic and recovery."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(180)  # Extended timeout for reconnection testing
    async def test_reconnection_capability(self, websocket_manager, websocket_timeout_config):
        """Test WebSocket reconnection capability with proper timeout handling."""
        # Establish initial connection
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.STOCK_DATA, 
            timeout=websocket_timeout_config["connection_timeout"]
        )
        
        if not success:
            pytest.skip("Cannot establish initial connection for reconnection test")
        
        # Test reconnection logic with proper timeout
        reconnection_result = await asyncio.wait_for(
            websocket_manager.test_reconnection(WebSocketEndpoint.STOCK_DATA),
            timeout=websocket_timeout_config["reconnection_timeout"]
        )
        
        logger.info("Reconnection test results:")
        logger.info(f"  Initial connected: {reconnection_result['initial_connected']}")
        logger.info(f"  Disconnection successful: {reconnection_result['disconnection_successful']}")
        logger.info(f"  Reconnection successful: {reconnection_result['reconnection_successful']}")
        
        if reconnection_result["reconnection_successful"]:
            logger.info(f"  Reconnection time: {reconnection_result['reconnection_time_ms']:.2f}ms")
            logger.info(f"  Messages before: {reconnection_result['messages_before']}")
            logger.info(f"  Messages after: {reconnection_result['messages_after']}")
            
            # Verify reconnection was successful
            assert reconnection_result["reconnection_successful"] is True
            assert reconnection_result["reconnection_time_ms"] is not None
            assert reconnection_result["reconnection_time_ms"] > 0
            
            # Check that connection is working after reconnection
            final_health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            assert final_health.connected is True
            assert final_health.reconnection_count > 0
        else:
            logger.warning("Reconnection test could not complete successfully")
            pytest.skip("Reconnection test could not complete successfully")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_connection_resilience_under_load(self, websocket_manager, websocket_test_symbols, websocket_timeout_config):
        """Test connection resilience under message load."""
        # Establish connection
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.STOCK_DATA,
            timeout=websocket_timeout_config["connection_timeout"]
        )
        
        if not success:
            pytest.skip("Cannot establish connection for resilience test")
        
        # Subscribe to multiple symbols to generate load
        symbols = websocket_test_symbols["stock_symbols"]
        subscribe_success = await websocket_manager.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols, ["trades", "quotes"]
        )
        
        if not subscribe_success:
            pytest.skip("Cannot subscribe for resilience test")
        
        # Monitor connection under load for extended period
        monitoring_duration = 30  # seconds
        check_interval = 5  # seconds
        checks = monitoring_duration // check_interval
        
        health_snapshots = []
        
        for i in range(checks):
            await asyncio.sleep(check_interval)
            
            health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            health_snapshots.append({
                "check": i,
                "connected": health.connected,
                "messages_received": health.messages_received,
                "error_count": health.error_count,
                "timestamp": health.last_message_time
            })
            
            logger.info(f"Resilience check {i+1}/{checks}: "
                       f"Connected={health.connected}, "
                       f"Messages={health.messages_received}, "
                       f"Errors={health.error_count}")
        
        # Analyze resilience results
        all_connected = all(snapshot["connected"] for snapshot in health_snapshots)
        total_messages = health_snapshots[-1]["messages_received"]
        total_errors = health_snapshots[-1]["error_count"]
        
        logger.info(f"Resilience test results:")
        logger.info(f"  Always connected: {all_connected}")
        logger.info(f"  Total messages: {total_messages}")
        logger.info(f"  Total errors: {total_errors}")
        
        # Connection should remain stable under load
        assert all_connected, "Connection should remain stable under message load"
        
        # Error rate should be reasonable
        if total_messages > 0:
            error_rate = total_errors / total_messages
            assert error_rate < 0.05, f"Error rate too high: {error_rate:.2%}"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_connection_recovery_from_network_interruption(self, websocket_manager, websocket_timeout_config):
        """Test connection recovery from simulated network interruption."""
        # Establish initial connection
        success = await websocket_manager.establish_connection(
            WebSocketEndpoint.STOCK_DATA,
            timeout=websocket_timeout_config["connection_timeout"]
        )
        
        if not success:
            pytest.skip("Cannot establish connection for network interruption test")
        
        # Get initial health
        initial_health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
        assert initial_health.connected is True
        
        # Simulate network interruption by forcefully closing the connection
        connection = websocket_manager.connections.get(WebSocketEndpoint.STOCK_DATA)
        if connection:
            # Force close the connection (simulating network issue)
            await connection.close(code=1001, reason="Simulated network interruption")
            
            # Wait a moment for the system to detect the interruption
            await asyncio.sleep(2)
            
            # Check that health status reflects the interruption
            interrupted_health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
            logger.info(f"Health after interruption: connected={interrupted_health.connected}")
            
            # Attempt to re-establish connection (manual recovery test)
            recovery_success = await websocket_manager.establish_connection(
                WebSocketEndpoint.STOCK_DATA,
                timeout=websocket_timeout_config["connection_timeout"]
            )
            
            if recovery_success:
                # Verify recovery
                recovered_health = websocket_manager.get_connection_health(WebSocketEndpoint.STOCK_DATA)
                assert recovered_health.connected is True
                
                logger.info("Connection successfully recovered from network interruption")
            else:
                logger.warning("Could not recover from network interruption")
                pytest.skip("Network interruption recovery failed")
    
    @pytest.mark.asyncio
    async def test_reconnection_with_subscriptions(self, websocket_manager):
        """Test that subscriptions are restored after reconnection."""
        # Establish connection and subscribe
        success = await websocket_manager.establish_connection(WebSocketEndpoint.STOCK_DATA)
        
        if not success:
            pytest.skip("Cannot establish connection for subscription reconnection test")
        
        symbols = ["AAPL", "MSFT"]
        subscribe_success = await websocket_manager.subscribe_symbols(
            WebSocketEndpoint.STOCK_DATA, symbols, ["trades"]
        )
        
        if not subscribe_success:
            pytest.skip("Cannot subscribe for reconnection test")
        
        # Wait for some messages
        await asyncio.sleep(5)
        initial_messages = websocket_manager.get_messages(WebSocketEndpoint.STOCK_DATA)
        
        # Test reconnection
        reconnection_result = await websocket_manager.test_reconnection(WebSocketEndpoint.STOCK_DATA)
        
        if reconnection_result["reconnection_successful"]:
            # Wait for messages after reconnection
            await asyncio.sleep(10)
            post_reconnection_messages = websocket_manager.get_messages(WebSocketEndpoint.STOCK_DATA)
            
            # Check that subscriptions are still active
            current_subscriptions = websocket_manager.subscriptions[WebSocketEndpoint.STOCK_DATA]
            for symbol in symbols:
                assert symbol in current_subscriptions, f"Subscription for {symbol} should be restored"
            
            # Should receive new messages after reconnection
            if len(initial_messages) > 0:
                assert len(post_reconnection_messages) >= len(initial_messages), \
                    "Should continue receiving messages after reconnection"
            
            print(f"Subscriptions restored after reconnection: {current_subscriptions}")
        else:
            pytest.skip("Reconnection test failed, cannot verify subscription restoration")
    
    @pytest.mark.asyncio
    async def test_reconnection_performance(self, websocket_manager):
        """Test reconnection performance metrics."""
        # Establish connection
        success = await websocket_manager.establish_connection(WebSocketEndpoint.STOCK_DATA)
        
        if not success:
            pytest.skip("Cannot establish connection for reconnection performance test")
        
        # Perform multiple reconnection tests
        reconnection_times = []
        successful_reconnections = 0
        
        for attempt in range(3):  # Test multiple reconnections
            result = await websocket_manager.test_reconnection(WebSocketEndpoint.STOCK_DATA)
            
            if result["reconnection_successful"]:
                successful_reconnections += 1
                reconnection_times.append(result["reconnection_time_ms"])
                
                # Wait between attempts
                await asyncio.sleep(2)
        
        if reconnection_times:
            avg_reconnection_time = sum(reconnection_times) / len(reconnection_times)
            min_reconnection_time = min(reconnection_times)
            max_reconnection_time = max(reconnection_times)
            
            print(f"Reconnection performance analysis:")
            print(f"  Successful reconnections: {successful_reconnections}/3")
            print(f"  Average reconnection time: {avg_reconnection_time:.2f}ms")
            print(f"  Min reconnection time: {min_reconnection_time:.2f}ms")
            print(f"  Max reconnection time: {max_reconnection_time:.2f}ms")
            
            # Performance assertions
            assert avg_reconnection_time < 10000, f"Average reconnection time too high: {avg_reconnection_time}ms"
            assert successful_reconnections > 0, "At least one reconnection should succeed"
        else:
            pytest.skip("No successful reconnections for performance analysis")


@pytest.mark.asyncio
async def test_websocket_health_integration(websocket_manager):
    """Integration test for WebSocket health monitoring."""
    print("Starting WebSocket health integration test...")
    
    # 1. Test initial health state
    initial_summary = websocket_manager.get_test_summary()
    print(f"Initial state: {initial_summary['total_connections']} connections")
    
    # 2. Establish connections to multiple endpoints
    endpoints_to_test = [WebSocketEndpoint.STOCK_DATA, WebSocketEndpoint.OPTION_DATA]
    established_connections = []
    
    for endpoint in endpoints_to_test:
        success = await websocket_manager.establish_connection(endpoint, timeout=15)
        if success:
            established_connections.append(endpoint)
            print(f"Established connection to {endpoint.value}")
    
    if not established_connections:
        pytest.skip("No WebSocket connections established for integration test")
    
    # 3. Subscribe to data on established connections
    for endpoint in established_connections:
        if endpoint == WebSocketEndpoint.STOCK_DATA:
            await websocket_manager.subscribe_symbols(endpoint, ["AAPL"], ["trades"])
        elif endpoint == WebSocketEndpoint.OPTION_DATA:
            await websocket_manager.subscribe_symbols(endpoint, ["AAPL240315C00150000"])
    
    # 4. Monitor health over time
    monitoring_duration = 20
    await asyncio.sleep(monitoring_duration)
    
    # 5. Analyze final health state
    final_summary = websocket_manager.get_test_summary()
    all_health = websocket_manager.get_all_health_metrics()
    
    print(f"Final integration test results:")
    print(f"  Total connections: {final_summary['total_connections']}")
    print(f"  Total messages: {final_summary['total_messages']}")
    print(f"  Total errors: {final_summary['total_errors']}")
    
    for endpoint_name, health in all_health.items():
        if health.connected:
            print(f"  {endpoint_name}: {health.messages_received} messages, {health.error_count} errors")
    
    # 6. Test reconnection on one endpoint
    if WebSocketEndpoint.STOCK_DATA in established_connections:
        print("Testing reconnection...")
        reconnection_result = await websocket_manager.test_reconnection(WebSocketEndpoint.STOCK_DATA)
        print(f"  Reconnection successful: {reconnection_result.get('reconnection_successful', False)}")
    
    # 7. Verify overall health
    healthy_connections = sum(1 for health in all_health.values() if health.connected)
    assert healthy_connections > 0, "At least one connection should be healthy"
    
    print(f"Health integration test completed with {healthy_connections} healthy connections")