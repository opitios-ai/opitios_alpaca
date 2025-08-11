"""WebSocket testing utilities and connection managers for real-time data testing."""

import asyncio
import json
import logging
import msgpack
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from tests.config import TestCredentials

logger = logging.getLogger(__name__)


class WebSocketEndpoint(Enum):
    """WebSocket endpoint types."""
    STOCK_DATA = "stock_data"
    OPTION_DATA = "option_data"
    TRADE_UPDATES = "trade_updates"


@dataclass
class WebSocketMessage:
    """Represents a received WebSocket message."""
    endpoint: WebSocketEndpoint
    message_type: str
    symbol: Optional[str]
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Optional[bytes] = None


@dataclass
class ConnectionHealth:
    """WebSocket connection health metrics."""
    connected: bool
    connection_time: Optional[datetime]
    last_message_time: Optional[datetime]
    messages_received: int
    reconnection_count: int
    error_count: int
    latency_ms: Optional[float] = None


class WebSocketTestManager:
    """
    Manages WebSocket connections for testing with real Alpaca endpoints.
    Provides connection health monitoring, message validation, and reconnection testing.
    """
    
    def __init__(self, credentials: TestCredentials):
        """
        Initialize WebSocket test manager.
        
        Args:
            credentials: Test credentials for authentication
        """
        self.credentials = credentials
        self.connections: Dict[WebSocketEndpoint, websockets.WebSocketServerProtocol] = {}
        self.message_buffers: Dict[WebSocketEndpoint, List[WebSocketMessage]] = {}
        self.health_monitors: Dict[WebSocketEndpoint, ConnectionHealth] = {}
        self.subscriptions: Dict[WebSocketEndpoint, Set[str]] = {}
        self.message_handlers: Dict[WebSocketEndpoint, List[Callable]] = {}
        
        # Connection URLs
        self.endpoints = {
            WebSocketEndpoint.STOCK_DATA: "wss://stream.data.alpaca.markets/v2/sip",
            WebSocketEndpoint.OPTION_DATA: "wss://stream.data.alpaca.markets/v1beta1/option",
            WebSocketEndpoint.TRADE_UPDATES: "wss://paper-api.alpaca.markets/stream"
        }
        
        # Initialize buffers and health monitors
        for endpoint in WebSocketEndpoint:
            self.message_buffers[endpoint] = []
            self.health_monitors[endpoint] = ConnectionHealth(
                connected=False,
                connection_time=None,
                last_message_time=None,
                messages_received=0,
                reconnection_count=0,
                error_count=0
            )
            self.subscriptions[endpoint] = set()
            self.message_handlers[endpoint] = []
        
        # Test configuration - Enhanced with better timeout settings
        self.connection_timeout = 30
        self.message_timeout = 60
        self.auth_timeout = 15
        self.subscription_timeout = 20
        self.health_check_timeout = 10
        self.cleanup_timeout = 15
        self.reconnection_timeout = 45
        self.max_reconnection_attempts = 3
        self.reconnection_delay = 5
        
        logger.info("Initialized WebSocket test manager")
    
    async def establish_connection(self, endpoint: WebSocketEndpoint, 
                                 timeout: int = None) -> bool:
        """
        Establish WebSocket connection to specified endpoint.
        
        Args:
            endpoint: WebSocket endpoint to connect to
            timeout: Connection timeout in seconds (uses default if None)
        
        Returns:
            bool: True if connection successful
        """
        timeout = timeout or self.connection_timeout
        
        try:
            url = self.endpoints[endpoint]
            logger.info(f"Establishing WebSocket connection to {endpoint.value}: {url}")
            
            # Connect with timeout using asyncio.wait_for for better control
            connection = await asyncio.wait_for(
                websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=self.cleanup_timeout,
                    max_size=2**20,  # 1MB max message size
                    max_queue=100    # Max queued messages
                ),
                timeout=timeout
            )
            
            self.connections[endpoint] = connection
            
            # Update health monitor
            health = self.health_monitors[endpoint]
            health.connected = True
            health.connection_time = datetime.now()
            
            # Start message listener
            asyncio.create_task(self._message_listener(endpoint))
            
            # Authenticate if required with specific timeout
            await asyncio.wait_for(
                self._authenticate_connection(endpoint),
                timeout=self.auth_timeout
            )
            
            logger.info(f"Successfully established WebSocket connection to {endpoint.value}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout for {endpoint.value} after {timeout}s")
            self.health_monitors[endpoint].error_count += 1
            return False
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"WebSocket connection failed with status {e.status_code} for {endpoint.value}")
            self.health_monitors[endpoint].error_count += 1
            return False
        except Exception as e:
            logger.error(f"Failed to establish connection to {endpoint.value}: {e}")
            self.health_monitors[endpoint].error_count += 1
            return False
    
    async def _authenticate_connection(self, endpoint: WebSocketEndpoint) -> None:
        """Authenticate WebSocket connection."""
        connection = self.connections.get(endpoint)
        if not connection:
            return
        
        try:
            if endpoint == WebSocketEndpoint.STOCK_DATA:
                # Authenticate for stock data stream
                auth_message = {
                    "action": "auth",
                    "key": self.credentials.api_key,
                    "secret": self.credentials.secret_key
                }
                await connection.send(json.dumps(auth_message))
                
            elif endpoint == WebSocketEndpoint.OPTION_DATA:
                # Authenticate for option data stream
                auth_message = {
                    "action": "auth",
                    "key": self.credentials.api_key,
                    "secret": self.credentials.secret_key
                }
                await connection.send(json.dumps(auth_message))
                
            elif endpoint == WebSocketEndpoint.TRADE_UPDATES:
                # Authenticate for trade updates
                auth_message = {
                    "action": "authenticate",
                    "data": {
                        "key_id": self.credentials.api_key,
                        "secret_key": self.credentials.secret_key
                    }
                }
                await connection.send(json.dumps(auth_message))
            
            logger.debug(f"Sent authentication for {endpoint.value}")
            
        except Exception as e:
            logger.error(f"Authentication failed for {endpoint.value}: {e}")
            raise
    
    async def _message_listener(self, endpoint: WebSocketEndpoint) -> None:
        """Listen for messages on WebSocket connection with enhanced error handling."""
        connection = self.connections.get(endpoint)
        if not connection:
            return
        
        health = self.health_monitors[endpoint]
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            async for message in connection:
                try:
                    # Reset error counter on successful message
                    consecutive_errors = 0
                    
                    # Parse message based on endpoint type
                    if endpoint == WebSocketEndpoint.OPTION_DATA:
                        # Option data uses MessagePack
                        if isinstance(message, bytes):
                            parsed_data = msgpack.unpackb(message, raw=False)
                        else:
                            # Fallback to JSON for some option endpoints
                            parsed_data = json.loads(message)
                    else:
                        # Stock data and trade updates use JSON
                        if isinstance(message, str):
                            parsed_data = json.loads(message)
                        else:
                            parsed_data = json.loads(message.decode('utf-8'))
                    
                    # Create WebSocket message object
                    ws_message = WebSocketMessage(
                        endpoint=endpoint,
                        message_type=parsed_data.get("T", "unknown"),
                        symbol=parsed_data.get("S"),
                        data=parsed_data,
                        raw_data=message if isinstance(message, bytes) else None
                    )
                    
                    # Update health metrics
                    health.messages_received += 1
                    health.last_message_time = datetime.now()
                    
                    # Store message in buffer (with size limit)
                    buffer = self.message_buffers[endpoint]
                    buffer.append(ws_message)
                    
                    # Keep buffer size manageable (last 1000 messages)
                    if len(buffer) > 1000:
                        buffer.pop(0)
                    
                    # Call registered handlers
                    for handler in self.message_handlers[endpoint]:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(ws_message)
                            else:
                                handler(ws_message)
                        except Exception as e:
                            logger.error(f"Message handler error: {e}")
                    
                    logger.debug(f"Received message on {endpoint.value}: {ws_message.message_type}")
                    
                except json.JSONDecodeError as e:
                    consecutive_errors += 1
                    logger.error(f"JSON decode error on {endpoint.value}: {e}")
                    health.error_count += 1
                    
                except msgpack.exceptions.ExtraData as e:
                    consecutive_errors += 1
                    logger.error(f"MessagePack decode error on {endpoint.value}: {e}")
                    health.error_count += 1
                    
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error processing message on {endpoint.value}: {e}")
                    health.error_count += 1
                
                # Break if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}) on {endpoint.value}, stopping listener")
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket connection closed for {endpoint.value}")
            health.connected = False
        except asyncio.CancelledError:
            logger.info(f"Message listener cancelled for {endpoint.value}")
            raise
        except Exception as e:
            logger.error(f"Message listener error for {endpoint.value}: {e}")
            health.connected = False
            health.error_count += 1
        finally:
            health.connected = False
            logger.info(f"Message listener ended for {endpoint.value}")
    
    async def subscribe_symbols(self, endpoint: WebSocketEndpoint, 
                               symbols: List[str], 
                               data_types: Optional[List[str]] = None) -> bool:
        """
        Subscribe to symbols on WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint
            symbols: List of symbols to subscribe to
            data_types: List of data types (e.g., ["trades", "quotes", "bars"])
        
        Returns:
            bool: True if subscription successful
        """
        connection = self.connections.get(endpoint)
        if not connection:
            logger.error(f"No connection available for {endpoint.value}")
            return False
        
        try:
            if endpoint == WebSocketEndpoint.STOCK_DATA:
                # Subscribe to stock data
                data_types = data_types or ["trades", "quotes"]
                subscribe_message = {
                    "action": "subscribe",
                    "trades": symbols if "trades" in data_types else [],
                    "quotes": symbols if "quotes" in data_types else [],
                    "bars": symbols if "bars" in data_types else []
                }
                
            elif endpoint == WebSocketEndpoint.OPTION_DATA:
                # Subscribe to option data
                subscribe_message = {
                    "action": "subscribe",
                    "trades": symbols,
                    "quotes": symbols
                }
                
            elif endpoint == WebSocketEndpoint.TRADE_UPDATES:
                # Subscribe to trade updates
                subscribe_message = {
                    "action": "listen",
                    "data": {
                        "streams": ["trade_updates"]
                    }
                }
            
            await connection.send(json.dumps(subscribe_message))
            
            # Track subscriptions
            self.subscriptions[endpoint].update(symbols)
            
            logger.info(f"Subscribed to {len(symbols)} symbols on {endpoint.value}")
            return True
            
        except Exception as e:
            logger.error(f"Subscription failed for {endpoint.value}: {e}")
            return False
    
    async def unsubscribe_symbols(self, endpoint: WebSocketEndpoint, 
                                 symbols: List[str]) -> bool:
        """Unsubscribe from symbols on WebSocket endpoint."""
        connection = self.connections.get(endpoint)
        if not connection:
            return False
        
        try:
            if endpoint == WebSocketEndpoint.STOCK_DATA:
                unsubscribe_message = {
                    "action": "unsubscribe",
                    "trades": symbols,
                    "quotes": symbols,
                    "bars": symbols
                }
                
            elif endpoint == WebSocketEndpoint.OPTION_DATA:
                unsubscribe_message = {
                    "action": "unsubscribe",
                    "trades": symbols,
                    "quotes": symbols
                }
                
            elif endpoint == WebSocketEndpoint.TRADE_UPDATES:
                # Trade updates don't support symbol-specific unsubscribe
                return True
            
            await connection.send(json.dumps(unsubscribe_message))
            
            # Remove from tracked subscriptions
            self.subscriptions[endpoint].difference_update(symbols)
            
            logger.info(f"Unsubscribed from {len(symbols)} symbols on {endpoint.value}")
            return True
            
        except Exception as e:
            logger.error(f"Unsubscription failed for {endpoint.value}: {e}")
            return False
    
    def register_message_handler(self, endpoint: WebSocketEndpoint, 
                                handler: Callable[[WebSocketMessage], None]) -> None:
        """Register a message handler for an endpoint."""
        self.message_handlers[endpoint].append(handler)
        logger.debug(f"Registered message handler for {endpoint.value}")
    
    def get_messages(self, endpoint: WebSocketEndpoint, 
                    message_type: Optional[str] = None,
                    symbol: Optional[str] = None,
                    limit: Optional[int] = None) -> List[WebSocketMessage]:
        """
        Get messages from buffer with optional filtering.
        
        Args:
            endpoint: WebSocket endpoint
            message_type: Filter by message type
            symbol: Filter by symbol
            limit: Maximum number of messages to return
        
        Returns:
            List of WebSocket messages
        """
        messages = self.message_buffers[endpoint]
        
        # Apply filters
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        if symbol:
            messages = [m for m in messages if m.symbol == symbol]
        
        # Apply limit
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def clear_message_buffer(self, endpoint: WebSocketEndpoint) -> None:
        """Clear message buffer for endpoint."""
        self.message_buffers[endpoint].clear()
        logger.debug(f"Cleared message buffer for {endpoint.value}")
    
    async def wait_for_messages(self, endpoint: WebSocketEndpoint, 
                               count: int = 1,
                               timeout: int = None,
                               message_type: Optional[str] = None,
                               symbol: Optional[str] = None) -> List[WebSocketMessage]:
        """
        Wait for specific number of messages with timeout and enhanced filtering.
        
        Args:
            endpoint: WebSocket endpoint
            count: Number of messages to wait for
            timeout: Timeout in seconds (uses default if None)
            message_type: Filter by message type
            symbol: Filter by symbol
        
        Returns:
            List of received messages
        """
        timeout = timeout or self.message_timeout
        start_time = datetime.now()
        last_count = 0
        no_progress_timeout = 30  # Timeout if no new messages for 30 seconds
        
        logger.info(f"Waiting for {count} messages on {endpoint.value} "
                   f"(timeout: {timeout}s, type: {message_type}, symbol: {symbol})")
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            messages = self.get_messages(endpoint, message_type, symbol)
            current_count = len(messages)
            
            if current_count >= count:
                logger.info(f"Received {current_count} messages on {endpoint.value}")
                return messages[:count]
            
            # Check for progress
            if current_count > last_count:
                last_count = current_count
                logger.debug(f"Progress: {current_count}/{count} messages on {endpoint.value}")
            else:
                # Check if we've been stuck without progress for too long
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > no_progress_timeout and current_count == 0:
                    logger.warning(f"No messages received on {endpoint.value} after {elapsed:.1f}s")
                    break
            
            await asyncio.sleep(0.1)
        
        # Timeout reached or no progress
        messages = self.get_messages(endpoint, message_type, symbol)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Log different timeout scenarios
        if len(messages) == 0:
            logger.warning(f"No messages received on {endpoint.value} after {elapsed:.1f}s timeout")
        else:
            logger.warning(f"Partial messages on {endpoint.value}: got {len(messages)}/{count} "
                         f"after {elapsed:.1f}s timeout")
        
        return messages
    
    async def test_reconnection(self, endpoint: WebSocketEndpoint) -> Dict[str, Any]:
        """
        Test reconnection logic by closing and reopening connection.
        
        Args:
            endpoint: WebSocket endpoint to test
        
        Returns:
            Dict containing reconnection test results
        """
        logger.info(f"Testing reconnection for {endpoint.value}")
        
        result = {
            "endpoint": endpoint.value,
            "initial_connected": False,
            "disconnection_successful": False,
            "reconnection_successful": False,
            "reconnection_time_ms": None,
            "messages_before": 0,
            "messages_after": 0
        }
        
        try:
            # Check initial connection
            health = self.health_monitors[endpoint]
            result["initial_connected"] = health.connected
            result["messages_before"] = health.messages_received
            
            if not health.connected:
                logger.error(f"Cannot test reconnection - no initial connection for {endpoint.value}")
                return result
            
            # Close connection
            connection = self.connections.get(endpoint)
            if connection:
                await connection.close()
                result["disconnection_successful"] = True
                health.connected = False
                
                # Wait a moment for disconnection to register
                await asyncio.sleep(1)
            
            # Attempt reconnection
            reconnection_start = datetime.now()
            
            for attempt in range(self.max_reconnection_attempts):
                logger.info(f"Reconnection attempt {attempt + 1} for {endpoint.value}")
                
                success = await self.establish_connection(endpoint)
                
                if success:
                    reconnection_time = datetime.now() - reconnection_start
                    result["reconnection_successful"] = True
                    result["reconnection_time_ms"] = reconnection_time.total_seconds() * 1000
                    
                    health.reconnection_count += 1
                    
                    # Re-subscribe to previous symbols
                    if self.subscriptions[endpoint]:
                        await self.subscribe_symbols(endpoint, list(self.subscriptions[endpoint]))
                    
                    # Wait for messages to verify connection
                    await asyncio.sleep(2)
                    result["messages_after"] = health.messages_received
                    
                    logger.info(f"Reconnection successful for {endpoint.value} "
                               f"in {result['reconnection_time_ms']:.2f}ms")
                    break
                
                if attempt < self.max_reconnection_attempts - 1:
                    await asyncio.sleep(self.reconnection_delay)
            
            return result
            
        except Exception as e:
            logger.error(f"Reconnection test failed for {endpoint.value}: {e}")
            result["error"] = str(e)
            return result
    
    def get_connection_health(self, endpoint: WebSocketEndpoint) -> ConnectionHealth:
        """Get connection health metrics for endpoint."""
        return self.health_monitors[endpoint]
    
    def get_all_health_metrics(self) -> Dict[str, ConnectionHealth]:
        """Get health metrics for all endpoints."""
        return {endpoint.value: health for endpoint, health in self.health_monitors.items()}
    
    async def close_connection(self, endpoint: WebSocketEndpoint) -> None:
        """Close WebSocket connection for endpoint with timeout."""
        connection = self.connections.get(endpoint)
        if connection:
            try:
                # Use timeout for close operation to prevent hanging
                await asyncio.wait_for(
                    connection.close(),
                    timeout=self.cleanup_timeout
                )
                logger.info(f"Closed WebSocket connection for {endpoint.value}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout closing connection for {endpoint.value}")
            except Exception as e:
                logger.error(f"Error closing connection for {endpoint.value}: {e}")
            finally:
                self.health_monitors[endpoint].connected = False
                if endpoint in self.connections:
                    del self.connections[endpoint]
    
    async def close_all_connections(self) -> None:
        """Close all WebSocket connections with timeout protection."""
        logger.info("Closing all WebSocket connections")
        
        # Close all connections concurrently with timeout
        close_tasks = []
        for endpoint in list(self.connections.keys()):
            task = asyncio.create_task(self.close_connection(endpoint))
            close_tasks.append(task)
        
        if close_tasks:
            try:
                # Wait for all connections to close with overall timeout
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=self.cleanup_timeout * 2
                )
            except asyncio.TimeoutError:
                logger.error("Timeout during connection cleanup - some connections may not be properly closed")
        
        # Clear all buffers and subscriptions
        for endpoint in WebSocketEndpoint:
            self.message_buffers[endpoint].clear()
            self.subscriptions[endpoint].clear()
            self.message_handlers[endpoint].clear()
        
        logger.info("All WebSocket connections closed")
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        return {
            "endpoints": {
                endpoint.value: {
                    "connected": health.connected,
                    "messages_received": health.messages_received,
                    "error_count": health.error_count,
                    "reconnection_count": health.reconnection_count,
                    "subscriptions": list(self.subscriptions[endpoint]),
                    "buffer_size": len(self.message_buffers[endpoint])
                }
                for endpoint, health in self.health_monitors.items()
            },
            "total_connections": len([h for h in self.health_monitors.values() if h.connected]),
            "total_messages": sum(h.messages_received for h in self.health_monitors.values()),
            "total_errors": sum(h.error_count for h in self.health_monitors.values())
        }


class WebSocketTestValidator:
    """Validates WebSocket message content and structure with enhanced validation."""
    
    @staticmethod
    def validate_stock_trade_message(message: WebSocketMessage) -> Dict[str, Any]:
        """Validate stock trade message structure with comprehensive checks."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        data = message.data
        
        # Required fields for stock trades
        required_fields = ["T", "S", "p", "s", "t"]
        for field in required_fields:
            if field not in data:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Missing required field: {field}")
        
        # Validate data types and ranges
        if "p" in data:
            price = data["p"]
            if not isinstance(price, (int, float)):
                validation_result["valid"] = False
                validation_result["errors"].append("Price (p) must be numeric")
            elif price <= 0:
                validation_result["valid"] = False
                validation_result["errors"].append("Price (p) must be positive")
            elif price > 10000:  # Reasonable upper bound
                validation_result["warnings"].append(f"Unusually high price: ${price}")
        
        if "s" in data:
            size = data["s"]
            if not isinstance(size, int):
                validation_result["valid"] = False
                validation_result["errors"].append("Size (s) must be integer")
            elif size <= 0:
                validation_result["valid"] = False
                validation_result["errors"].append("Size (s) must be positive")
        
        # Validate timestamp format
        if "t" in data:
            timestamp = data["t"]
            if not isinstance(timestamp, (int, str)):
                validation_result["warnings"].append("Timestamp format may be unusual")
        
        # Validate symbol format
        if "S" in data:
            symbol = data["S"]
            if not isinstance(symbol, str):
                validation_result["valid"] = False
                validation_result["errors"].append("Symbol (S) must be string")
            elif len(symbol) < 1 or len(symbol) > 10:
                validation_result["warnings"].append(f"Unusual symbol length: {symbol}")
            elif not symbol.isupper():
                validation_result["warnings"].append(f"Symbol not uppercase: {symbol}")
        
        # Validate message type
        if message.message_type != "t":
            validation_result["valid"] = False
            validation_result["errors"].append(f"Expected trade message type 't', got '{message.message_type}'")
        
        return validation_result
    
    @staticmethod
    def validate_stock_quote_message(message: WebSocketMessage) -> Dict[str, Any]:
        """Validate stock quote message structure."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        data = message.data
        
        # Required fields for stock quotes
        required_fields = ["T", "S"]
        for field in required_fields:
            if field not in data:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Missing required field: {field}")
        
        # At least one quote field should be present
        quote_fields = ["bp", "ap", "bs", "as"]  # bid price, ask price, bid size, ask size
        has_quote_data = any(field in data for field in quote_fields)
        
        if not has_quote_data:
            validation_result["warnings"].append("No quote data fields found")
        
        # Validate price fields
        for price_field in ["bp", "ap"]:
            if price_field in data:
                price = data[price_field]
                if not isinstance(price, (int, float, type(None))):
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"{price_field} must be numeric or null")
                elif price is not None and price <= 0:
                    validation_result["warnings"].append(f"Non-positive price in {price_field}: {price}")
        
        # Validate size fields
        for size_field in ["bs", "as"]:
            if size_field in data:
                size = data[size_field]
                if not isinstance(size, (int, type(None))):
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"{size_field} must be integer or null")
                elif size is not None and size <= 0:
                    validation_result["warnings"].append(f"Non-positive size in {size_field}: {size}")
        
        # Validate message type
        if message.message_type != "q":
            validation_result["valid"] = False
            validation_result["errors"].append(f"Expected quote message type 'q', got '{message.message_type}'")
        
        return validation_result
    
    @staticmethod
    def validate_option_message(message: WebSocketMessage) -> Dict[str, Any]:
        """Validate option message structure with enhanced MessagePack validation."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        data = message.data
        
        # Check if MessagePack was used for option data
        if message.raw_data and isinstance(message.raw_data, bytes):
            try:
                # Validate MessagePack format
                decoded = msgpack.unpackb(message.raw_data, raw=False)
                if not isinstance(decoded, dict):
                    validation_result["valid"] = False
                    validation_result["errors"].append("MessagePack data is not a dictionary")
                
                # Verify decoded data matches parsed data
                if decoded != data:
                    validation_result["warnings"].append("Decoded MessagePack differs from parsed data")
                    
            except msgpack.exceptions.ExtraData as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"MessagePack has extra data: {e}")
            except msgpack.exceptions.UnpackException as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"MessagePack unpack failed: {e}")
            except Exception as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"MessagePack validation error: {e}")
        
        # Validate option symbol format
        if "S" in data:
            symbol = data["S"]
            if not WebSocketTestValidator._is_valid_option_symbol(symbol):
                validation_result["warnings"].append(f"Unusual option symbol format: {symbol}")
        
        # Validate option-specific fields
        if message.message_type == "q":  # Option quote
            # Option quotes may have different field names
            option_quote_fields = ["bp", "ap", "bs", "as", "bid", "ask", "bid_size", "ask_size"]
            has_option_quote_data = any(field in data for field in option_quote_fields)
            
            if not has_option_quote_data:
                validation_result["warnings"].append("No recognizable option quote data found")
        
        elif message.message_type == "t":  # Option trade
            # Option trades should have price and size
            if "p" not in data and "price" not in data:
                validation_result["warnings"].append("No price field found in option trade")
            
            if "s" not in data and "size" not in data:
                validation_result["warnings"].append("No size field found in option trade")
        
        return validation_result
    
    @staticmethod
    def validate_connection_health(health: ConnectionHealth) -> Dict[str, Any]:
        """Validate connection health metrics."""
        validation_result = {
            "healthy": True,
            "issues": [],
            "recommendations": []
        }
        
        # Check connection status
        if not health.connected:
            validation_result["healthy"] = False
            validation_result["issues"].append("Connection is not active")
        
        # Check for recent activity
        if health.last_message_time:
            from datetime import datetime, timedelta
            time_since_last_message = datetime.now() - health.last_message_time
            
            if time_since_last_message > timedelta(minutes=5):
                validation_result["issues"].append(f"No messages for {time_since_last_message.total_seconds():.0f} seconds")
                validation_result["recommendations"].append("Check if subscriptions are active")
        
        # Check error rate
        if health.messages_received > 0:
            error_rate = health.error_count / health.messages_received
            if error_rate > 0.1:  # More than 10% error rate
                validation_result["healthy"] = False
                validation_result["issues"].append(f"High error rate: {error_rate:.1%}")
                validation_result["recommendations"].append("Check connection stability and data format")
        
        # Check reconnection frequency
        if health.reconnection_count > 3:
            validation_result["issues"].append(f"Frequent reconnections: {health.reconnection_count}")
            validation_result["recommendations"].append("Check network stability")
        
        return validation_result
    
    @staticmethod
    def _is_valid_option_symbol(symbol: str) -> bool:
        """Check if symbol follows option naming convention with enhanced validation."""
        if not isinstance(symbol, str) or len(symbol) < 15:
            return False
        
        # Option symbol format: UNDERLYING + YYMMDD + C/P + STRIKE
        # Example: AAPL240315C00150000
        
        # Find the underlying symbol (letters before first digit)
        underlying = ""
        for i, char in enumerate(symbol):
            if char.isdigit():
                underlying = symbol[:i]
                remainder = symbol[i:]
                break
        else:
            return False  # No digits found
        
        if not underlying or not underlying.isalpha():
            return False
        
        # Check remainder format: YYMMDD + C/P + STRIKE
        if len(remainder) < 9:  # At least 6 digits for date + 1 for C/P + 2 for strike
            return False
        
        # Check for C (Call) or P (Put)
        has_call_put = 'C' in remainder or 'P' in remainder
        if not has_call_put:
            return False
        
        # Check that there are enough digits for a valid strike price
        digit_count = sum(1 for c in remainder if c.isdigit())
        if digit_count < 8:  # 6 for date + at least 2 for strike
            return False
        
        return True
    
    @staticmethod
    def validate_message_sequence(messages: List[WebSocketMessage]) -> Dict[str, Any]:
        """Validate a sequence of WebSocket messages for consistency."""
        validation_result = {
            "valid": True,
            "total_messages": len(messages),
            "message_types": {},
            "symbols": set(),
            "issues": [],
            "statistics": {}
        }
        
        if not messages:
            validation_result["issues"].append("No messages to validate")
            return validation_result
        
        # Analyze message distribution
        for message in messages:
            # Count message types
            msg_type = message.message_type
            validation_result["message_types"][msg_type] = validation_result["message_types"].get(msg_type, 0) + 1
            
            # Track symbols
            if message.symbol:
                validation_result["symbols"].add(message.symbol)
        
        # Check for reasonable message distribution
        total_messages = len(messages)
        if total_messages > 10:  # Only check distribution for reasonable sample sizes
            # Check if we have a good mix of message types
            unique_types = len(validation_result["message_types"])
            if unique_types == 1:
                validation_result["issues"].append("Only one message type received")
            
            # Check for unusually high error message ratio
            error_messages = validation_result["message_types"].get("error", 0)
            if error_messages > total_messages * 0.2:  # More than 20% errors
                validation_result["valid"] = False
                validation_result["issues"].append(f"High error message ratio: {error_messages}/{total_messages}")
        
        # Generate statistics
        validation_result["statistics"] = {
            "unique_message_types": len(validation_result["message_types"]),
            "unique_symbols": len(validation_result["symbols"]),
            "most_common_type": max(validation_result["message_types"], key=validation_result["message_types"].get) if validation_result["message_types"] else None,
        }
        
        return validation_result