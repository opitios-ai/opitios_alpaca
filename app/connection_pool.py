"""
Modern Alpaca Connection Manager
Clean, simple architecture for individual account connections
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from alpaca.data.live.option import OptionDataStream
from loguru import logger


class ConnectionType(Enum):
    """Connection type enumeration"""
    TRADING_CLIENT = "trading_client"    # REST API client
    TRADING_STREAM = "trading_stream"    # Trading updates WebSocket
    STOCK_DATA = "stock_data"           # Stock historical data client
    OPTION_DATA = "option_data"         # Option historical data client
    STOCK_STREAM = "stock_stream"       # Stock real-time data stream
    OPTION_STREAM = "option_stream"     # Option real-time data stream


@dataclass
class ConnectionStats:
    """Connection statistics"""
    connection_type: ConnectionType
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    is_healthy: bool = True


class ConnectionManager:
    """Single user's Alpaca connection manager"""
    
    def __init__(self, user_id: str, api_key: str, secret_key: str, paper_trading: bool = True):
        self.user_id = user_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper_trading = paper_trading
        
        # Connection containers
        self.connections: Dict[ConnectionType, any] = {}
        self.connection_stats: Dict[ConnectionType, ConnectionStats] = {}
        
        # Async locks
        self._locks: Dict[ConnectionType, asyncio.Lock] = {}
        self._in_use: Dict[ConnectionType, bool] = {}
        
        # Initialize core connections
        self._initialize_core_connections()
    
    def _initialize_core_connections(self):
        """Initialize core connections required for each user"""
        try:
            # Trading Client - for REST API calls (orders, account queries, etc.)
            self.connections[ConnectionType.TRADING_CLIENT] = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper_trading
            )
            self.connection_stats[ConnectionType.TRADING_CLIENT] = ConnectionStats(
                connection_type=ConnectionType.TRADING_CLIENT,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow()
            )
            self._locks[ConnectionType.TRADING_CLIENT] = asyncio.Lock()
            self._in_use[ConnectionType.TRADING_CLIENT] = False
            
            # logger.info(f"Trading Client initialized successfully (user: {self.user_id})")
            
            # Verify account access to ensure API is working
            self._verify_account_access()
            
        except Exception as e:
            logger.error(f"Failed to initialize core connections (user: {self.user_id}): {e}")
            raise

    def _create_data_connection(self, connection_type: ConnectionType):
        """Create data connections on demand"""
        try:
            if connection_type == ConnectionType.STOCK_DATA:
                connection = StockHistoricalDataClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
            elif connection_type == ConnectionType.OPTION_DATA:
                connection = OptionHistoricalDataClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
            elif connection_type == ConnectionType.TRADING_STREAM:
                connection = TradingStream(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                    paper=self.paper_trading
                )
            elif connection_type == ConnectionType.STOCK_STREAM:
                connection = StockDataStream(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
            elif connection_type == ConnectionType.OPTION_STREAM:
                connection = OptionDataStream(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
            else:
                raise ValueError(f"Unsupported connection type: {connection_type}")
            
            self.connections[connection_type] = connection
            self.connection_stats[connection_type] = ConnectionStats(
                connection_type=connection_type,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow()
            )
            self._locks[connection_type] = asyncio.Lock()
            self._in_use[connection_type] = False
            
            logger.info(f"Created {connection_type.value} connection successfully (user: {self.user_id})")
            return connection
            
        except Exception as e:
            logger.error(f"Failed to create {connection_type.value} connection (user: {self.user_id}): {e}")
            raise

    async def get_connection(self, connection_type: ConnectionType):
        """Get connection of specified type"""
        # Create connection if it doesn't exist (except core connections)
        if connection_type not in self.connections:
            if connection_type == ConnectionType.TRADING_CLIENT:
                raise ValueError("Trading Client should be created during initialization")
            self._create_data_connection(connection_type)
        
        # Ensure lock exists
        if connection_type not in self._locks:
            self._locks[connection_type] = asyncio.Lock()
        
        # Acquire connection lock
        await self._locks[connection_type].acquire()
        self._in_use[connection_type] = True
        
        # Update usage statistics
        stats = self.connection_stats[connection_type]
        stats.last_used = datetime.utcnow()
        stats.usage_count += 1
        
        return self.connections[connection_type]

    def release_connection(self, connection_type: ConnectionType):
        """Release connection of specified type"""
        if connection_type in self._locks and self._locks[connection_type].locked():
            self._locks[connection_type].release()
        self._in_use[connection_type] = False

    async def test_connection(self, connection_type: ConnectionType) -> bool:
        """Test health of specified connection"""
        try:
            if connection_type not in self.connections:
                return False
                
            start_time = time.time()
            
            # Different health checks based on connection type
            if connection_type == ConnectionType.TRADING_CLIENT:
                # Test Trading Client - get account information
                account = self.connections[connection_type].get_account()
                success = account is not None
            else:
                # For data connections, consider existence as health
                success = True
                
            response_time = time.time() - start_time
            
            # Update statistics
            stats = self.connection_stats[connection_type]
            stats.avg_response_time = (
                (stats.avg_response_time * (stats.usage_count - 1) + response_time) 
                / max(stats.usage_count, 1)
            )
            stats.is_healthy = success
            
            return success
            
        except Exception as e:
            if connection_type in self.connection_stats:
                self.connection_stats[connection_type].error_count += 1
                self.connection_stats[connection_type].is_healthy = False
            logger.error(f"{connection_type.value} connection test failed (user: {self.user_id}): {e}")
            return False

    def is_connection_available(self, connection_type: ConnectionType) -> bool:
        """Check if connection is available"""
        if connection_type not in self.connections:
            return True  # Non-existent connections can be created
        
        return (not self._in_use.get(connection_type, False) and 
                self.connection_stats[connection_type].is_healthy)

    @property
    def connection_count(self) -> int:
        """Current total connection count"""
        return len(self.connections)

    def get_connection_stats(self) -> Dict:
        """Get connection statistics"""
        stats = {
            "user_id": self.user_id,
            "total_connections": len(self.connections),
            "connections": {}
        }
        
        for conn_type, conn_stats in self.connection_stats.items():
            stats["connections"][conn_type.value] = {
                "created_at": conn_stats.created_at.isoformat(),
                "last_used": conn_stats.last_used.isoformat(),
                "usage_count": conn_stats.usage_count,
                "error_count": conn_stats.error_count,
                "avg_response_time": conn_stats.avg_response_time,
                "is_healthy": conn_stats.is_healthy,
                "in_use": self._in_use.get(conn_type, False)
            }
        
        return stats

    async def shutdown(self):
        """Shutdown all connections"""
        logger.info(f"Shutting down all connections for user {self.user_id}...")
        
        # Release all locks
        for conn_type in list(self._locks.keys()):
            if self._locks[conn_type].locked():
                self._locks[conn_type].release()
        
        # Clean up connections (WebSocket connections need special handling)
        for conn_type, connection in list(self.connections.items()):
            try:
                if conn_type in [ConnectionType.TRADING_STREAM, ConnectionType.STOCK_STREAM, ConnectionType.OPTION_STREAM]:
                    # WebSocket connections need close() method
                    if hasattr(connection, 'close'):
                        await connection.close()
                # REST clients don't need special cleanup
            except Exception as e:
                logger.error(f"Error closing {conn_type.value} connection: {e}")
        
        # Clean up data structures
        self.connections.clear()
        self.connection_stats.clear()
        self._locks.clear()
        self._in_use.clear()
        
        logger.info(f"Connection cleanup complete for user {self.user_id}")

    def _verify_account_access(self):
        """Verify account access to ensure API is working"""
        try:
            if ConnectionType.TRADING_CLIENT not in self.connections:
                logger.error(f"Trading Client not initialized, cannot verify account access (user: {self.user_id})")
                return

            # Get Trading Client connection
            trading_client = self.connections[ConnectionType.TRADING_CLIENT]
            
            # Get account information
            account_info = trading_client.get_account()
            
            if account_info:
                # Extract key account information
                account_id = str(account_info.id) if hasattr(account_info, 'id') else 'N/A'
                equity = float(account_info.equity) if hasattr(account_info, 'equity') else 0.0
                buying_power = float(account_info.buying_power) if hasattr(account_info, 'buying_power') else 0.0
                cash = float(account_info.cash) if hasattr(account_info, 'cash') else 0.0
                status = account_info.status if hasattr(account_info, 'status') else 'UNKNOWN'
                account_type = 'Paper Trading' if getattr(account_info, 'pattern_day_trader', None) is not None else 'Live'
                
                # Log successful account verification - One line format for easy tracking
                logger.info('================')
                logger.info(f"OK {self.user_id}: {status} | Account#{account_id[:8]}... | Equity=${equity:,.2f} | Cash=${cash:,.2f} | BuyPower=${buying_power:,.2f} | Type={account_type}")
                
                # Check account status
                if status.upper() != 'ACTIVE':
                    logger.warning(f"Account status abnormal (user: {self.user_id}): {status}")
                
                # Check if equity is reasonable (basic validation)
                if equity < 0:
                    logger.warning(f"Account equity is negative (user: {self.user_id}): ${equity:,.2f}")
                    
                # logger.info(f"API connection verification complete, account running normally (user: {self.user_id})")
                
            else:
                logger.error(f"Cannot get account information, API may be abnormal (user: {self.user_id})")
                
        except Exception as e:
            logger.error(f"Account access verification failed (user: {self.user_id}): {e}")
            logger.warning(f"API connection may have issues, please check API keys and network connection (user: {self.user_id})")
            # Don't throw exception, allow program to continue running


class PoolManager:
    """Modern connection pool manager"""
    
    def __init__(self, max_idle_time_minutes: int = 30, health_check_interval_seconds: int = 300):
        self.max_idle_time_minutes = max_idle_time_minutes
        self.health_check_interval_seconds = health_check_interval_seconds
        
        # User connection managers {user_id: ConnectionManager}
        self.user_managers: Dict[str, ConnectionManager] = {}
        
        # Global lock (delayed initialization)
        self._global_lock = None
        
        # Background tasks
        self._background_tasks = []
        self._start_background_tasks()
        
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        try:
            # Only create tasks when event loop is running
            loop = asyncio.get_running_loop()
            
            # Health check task
            health_check_task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.append(health_check_task)
            
            # Connection cleanup task
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._background_tasks.append(cleanup_task)
            
        except RuntimeError:
            # No running event loop, delay task startup
            logger.info("No running event loop, background tasks will be started later")
    
    async def _ensure_async_components(self):
        """Ensure async components are initialized"""
        if self._global_lock is None:
            self._global_lock = asyncio.Lock()
        
        # If background tasks haven't started, try to start them
        if not self._background_tasks:
            self._start_background_tasks()
        
    async def _health_check_loop(self):
        """Health check loop"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval_seconds)
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                
    async def _cleanup_loop(self):
        """Connection cleanup loop"""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute
                await self._cleanup_idle_connections()
            except Exception as e:
                logger.error(f"Connection cleanup loop error: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks"""
        await self._ensure_async_components()
        async with self._global_lock:
            for user_id, manager in self.user_managers.items():
                # Check health of each connection in connection manager
                for conn_type in list(manager.connections.keys()):
                    try:
                        await manager.test_connection(conn_type)
                    except Exception as e:
                        logger.error(f"Health check failed (user: {user_id}, connection: {conn_type.value}): {e}")
    
    async def _cleanup_idle_connections(self):
        """Clean up idle connections"""
        await self._ensure_async_components()
        async with self._global_lock:
            for user_id, manager in list(self.user_managers.items()):
                # Check if connections in manager have been idle too long
                idle_connections = []
                
                for conn_type, stats in manager.connection_stats.items():
                    idle_time = (datetime.utcnow() - stats.last_used).total_seconds() / 60
                    
                    if idle_time > self.max_idle_time_minutes and not manager._in_use.get(conn_type, False):
                        # Don't clean up core connections (TRADING_CLIENT)
                        if conn_type != ConnectionType.TRADING_CLIENT:
                            idle_connections.append(conn_type)
                
                # Clean up idle connections
                for conn_type in idle_connections:
                    try:
                        if conn_type in manager.connections:
                            connection = manager.connections[conn_type]
                            # WebSocket connections need to be closed
                            if conn_type in [ConnectionType.TRADING_STREAM, ConnectionType.STOCK_STREAM, ConnectionType.OPTION_STREAM]:
                                if hasattr(connection, 'close'):
                                    await connection.close()
                            
                            # Remove connection from manager
                            del manager.connections[conn_type]
                            del manager.connection_stats[conn_type]
                            if conn_type in manager._locks:
                                del manager._locks[conn_type]
                            if conn_type in manager._in_use:
                                del manager._in_use[conn_type]
                            
                            logger.info(f"Cleaned up idle connection (user: {user_id}, connection: {conn_type.value}, idle time: {idle_time:.1f} minutes)")
                    except Exception as e:
                        logger.error(f"Failed to cleanup connection (user: {user_id}, connection: {conn_type.value}): {e}")
                
                # If user only has core connection and hasn't been used for a long time, consider cleaning up entire manager
                if len(manager.connections) == 1 and ConnectionType.TRADING_CLIENT in manager.connections:
                    trading_stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
                    idle_time = (datetime.utcnow() - trading_stats.last_used).total_seconds() / 60
                    
                    if idle_time > self.max_idle_time_minutes * 2:  # Core connections kept longer
                        try:
                            await manager.shutdown()
                            del self.user_managers[user_id]
                            logger.info(f"Cleaned up user manager (user: {user_id}, idle time: {idle_time:.1f} minutes)")
                        except Exception as e:
                            logger.error(f"Failed to cleanup user manager (user: {user_id}): {e}")
    
    async def get_user_manager(self, user) -> ConnectionManager:
        """Get user connection manager"""
        user_id = user.id
        
        # Ensure async components are initialized
        await self._ensure_async_components()
        
        async with self._global_lock:
            # If user manager doesn't exist, create it
            if user_id not in self.user_managers:
                try:
                    api_key, secret_key = user.decrypt_alpaca_credentials()
                    manager = ConnectionManager(
                        user_id=user_id,
                        api_key=api_key,
                        secret_key=secret_key,
                        paper_trading=user.alpaca_paper_trading
                    )
                    self.user_managers[user_id] = manager
                    logger.info(f"Created user connection manager (user: {user_id})")
                    
                except Exception as e:
                    logger.error(f"Failed to create user connection manager (user: {user_id}): {e}")
                    raise
            
            return self.user_managers[user_id]

    def get_pool_stats(self) -> Dict:
        """Get connection pool statistics"""
        stats = {
            "total_users": len(self.user_managers),
            "total_connections": sum(manager.connection_count for manager in self.user_managers.values()),
            "user_stats": {}
        }
        
        for user_id, manager in self.user_managers.items():
            stats["user_stats"][user_id] = manager.get_connection_stats()
        
        return stats
    
    async def shutdown(self):
        """Shutdown connection pool"""
        logger.info("Shutting down connection pool...")
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Shutdown all user managers
        if self._global_lock is not None:
            async with self._global_lock:
                for user_id, manager in list(self.user_managers.items()):
                    try:
                        await manager.shutdown()
                    except Exception as e:
                        logger.error(f"Failed to shutdown user manager (user: {user_id}): {e}")
                
                self.user_managers.clear()
        else:
            # If no lock, clean up directly
            for user_id, manager in list(self.user_managers.items()):
                try:
                    await manager.shutdown()
                except Exception as e:
                    logger.error(f"Failed to shutdown user manager (user: {user_id}): {e}")
            
            self.user_managers.clear()
        
        logger.info("Connection pool shutdown complete")


# Global connection pool instance
pool_manager = PoolManager(
    max_idle_time_minutes=30,
    health_check_interval_seconds=300
)


# Dependency injection function
def get_pool_manager() -> PoolManager:
    """Get connection pool instance"""
    return pool_manager


# Export connection types for use by other modules
__all__ = ['PoolManager', 'ConnectionType', 'ConnectionManager', 'get_pool_manager']