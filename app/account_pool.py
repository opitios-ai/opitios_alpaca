"""
Modern Alpaca Account Connection Pool
Clean, simple architecture without legacy compatibility layers
"""

import asyncio
import time
import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from collections import deque
from contextlib import asynccontextmanager

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from loguru import logger

from config import settings
from app.connection_pool import ConnectionManager, ConnectionType


@dataclass
class AccountConfig:
    """Account configuration"""
    account_id: str
    api_key: str
    secret_key: str
    paper_trading: bool = True
    account_name: Optional[str] = None
    region: str = "us"
    tier: str = "standard"
    enabled: bool = True


class AccountConnection:
    """Single account connection wrapper"""
    
    def __init__(self, account_config: AccountConfig):
        self.account_config = account_config
        self.connection_id = f"{account_config.account_id}_{int(time.time())}"
        
        # Connection manager for this account
        self.connection_manager = ConnectionManager(
            user_id=account_config.account_id,
            api_key=account_config.api_key,
            secret_key=account_config.secret_key,
            paper_trading=account_config.paper_trading
        )
        
        # Connection state
        self._lock = asyncio.Lock()
        self._in_use = False
        
    async def test_connection(self) -> bool:
        """Test connection health, validate account type, and check minimum balance"""
        try:
            async with self._lock:
                trading_client = await self.connection_manager.get_connection(ConnectionType.TRADING_CLIENT)
                try:
                    account = trading_client.get_account()
                    if account is not None:
                        # Account type detection: Check if account number starts with "PA" (paper) or not (live)
                        account_number = account.account_number
                        is_paper_account = account_number.startswith("PA")
                        expected_paper = self.account_config.paper_trading
                        
                        if is_paper_account != expected_paper:
                            expected_emoji = "📄" if expected_paper else "💰"
                            actual_emoji = "📄" if is_paper_account else "💰"
                            logger.warning(f"⚠️ 🔄 Account type mismatch for {self.account_config.account_id}: "
                                         f"Expected {expected_emoji} paper_trading={expected_paper}, but account {account_number} is "
                                         f"{actual_emoji} {'paper' if is_paper_account else 'live'}")
                        
                        # Balance validation: Check minimum balance requirement
                        from config import settings
                        min_balance = settings.minimum_balance
                        current_balance = float(account.cash) if account.cash else 0.0
                        
                        if current_balance < min_balance:
                            logger.error(f"❌ 💸 Account {self.account_config.account_id} balance ${current_balance:,.2f} "
                                       f"is below minimum required ${min_balance:,.2f}")
                            # Update health status before returning
                            if ConnectionType.TRADING_CLIENT in self.connection_manager.connection_stats:
                                self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].is_healthy = False
                                self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].error_count += 1
                            return False
                        
                        account_type_emoji = "📄" if is_paper_account else "💰"
                        trading_type = "paper" if is_paper_account else "live"
                        logger.info(f"✅ {account_type_emoji} Account {self.account_config.account_id} ({account_number}) validated: "
                                  f"{trading_type} trading, balance ${current_balance:,.2f}")
                        # Update health status on success
                        if ConnectionType.TRADING_CLIENT in self.connection_manager.connection_stats:
                            self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].is_healthy = True
                        return True
                    
                    # Update health status when account is None
                    if ConnectionType.TRADING_CLIENT in self.connection_manager.connection_stats:
                        self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].is_healthy = False
                        self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].error_count += 1
                    return False
                finally:
                    self.connection_manager.release_connection(ConnectionType.TRADING_CLIENT)
        except Exception as e:
            logger.error(f"Connection test failed for account {self.account_config.account_id}: {e}")
            # Update health status on exception
            if ConnectionType.TRADING_CLIENT in self.connection_manager.connection_stats:
                self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].is_healthy = False
                self.connection_manager.connection_stats[ConnectionType.TRADING_CLIENT].error_count += 1
            return False
    
    @property
    def alpaca_client(self):
        """Get AlpacaClient compatible interface"""
        from app.alpaca_client import AlpacaClient
        return AlpacaClient(
            api_key=self.account_config.api_key,
            secret_key=self.account_config.secret_key,
            paper_trading=self.account_config.paper_trading
        )
    
    async def get_trading_client(self):
        """Get trading client from connection manager"""
        return await self.connection_manager.get_connection(ConnectionType.TRADING_CLIENT)
    
    async def get_stock_data_client(self):
        """Get stock data client from connection manager"""
        return await self.connection_manager.get_connection(ConnectionType.STOCK_DATA)
    
    async def get_option_data_client(self):
        """Get option data client from connection manager"""
        return await self.connection_manager.get_connection(ConnectionType.OPTION_DATA)
    
    async def acquire(self):
        """Acquire connection"""
        await self._lock.acquire()
        self._in_use = True
        
    def release(self):
        """Release connection"""
        self._in_use = False
        if self._lock.locked():
            self._lock.release()
    
    
    @property
    def is_available(self) -> bool:
        """Check if connection is available"""
        return not self._in_use and self.account_config.enabled
    
    @property
    def connection_count(self) -> int:
        """Current connection count"""
        return self.connection_manager.connection_count
    
    @property
    def age_minutes(self) -> float:
        """Connection age in minutes"""
        # Use trading client creation time as reference
        stats = self.get_connection_stats()
        trading_stats = stats.get('connections', {}).get('trading_client', {})
        if 'created_at' in trading_stats:
            from datetime import datetime
            created_at_str = trading_stats['created_at']
            created_at = datetime.fromisoformat(created_at_str)
            age_seconds = (datetime.utcnow() - created_at).total_seconds()
            return age_seconds / 60.0
        return 0.0
    
    def get_connection_stats(self) -> Dict:
        """Get connection statistics"""
        return self.connection_manager.get_connection_stats()
    
    async def shutdown(self):
        """Shutdown connection"""
        await self.connection_manager.shutdown()


class AccountPool:
    """Modern account connection pool"""
    
    def __init__(self, health_check_interval_seconds: int = 300):
        self.health_check_interval_seconds = health_check_interval_seconds
        
        # Account configurations and connections
        self.account_configs: Dict[str, AccountConfig] = {}
        self.account_connections: Dict[str, AccountConnection] = {}
        self.usage_queues: Dict[str, deque[AccountConnection]] = {}
        
        # Account lookup maps
        self.account_id_list: List[str] = []
        self.account_name_to_id: Dict[str, str] = {}
        
        # Async components
        self._global_lock = None
        self._background_tasks = []
        self._initialized = False
        
    async def initialize(self):
        """Initialize the account pool"""
        if self._initialized:
            return
            
        logger.info("Initializing account connection pool...")
        
        await self._ensure_async_components()
        await self._load_account_configs()
        await self._create_connections()
        self._start_background_tasks()
        
        self._initialized = True
        logger.info(f"Account pool initialized: {len(self.account_configs)} accounts, {sum(conn.connection_count for conn in self.account_connections.values())} connections")
    
    async def _ensure_async_components(self):
        """Ensure async components are initialized"""
        if self._global_lock is None:
            self._global_lock = asyncio.Lock()
    
    async def _load_account_configs(self):
        """Load account configurations"""
        accounts_config = getattr(settings, 'accounts', {})
        
        if not accounts_config:
            logger.error("No account configurations found. Please configure accounts in database or secrets.yml.")
            raise ValueError("No account configurations found. Multi-account setup required.")
        
        # Load multi-account configurations
        for account_id, config in accounts_config.items():
            # 防护：检查config是否为None（由于配置格式错误可能导致）
            if config is None:
                logger.error(f"Account {account_id} has invalid configuration (None). Check database or YAML formatting.")
                continue
                
            if not config.get('enabled', True):
                logger.info(f"Skipping disabled account: {account_id}")
                continue
                
            account_config = AccountConfig(
                account_id=account_id,
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                paper_trading=config.get('paper_trading', True),
                account_name=config.get('name', account_id),
                region=config.get('region', 'us'),
                tier=config.get('tier', 'standard'),
                enabled=config.get('enabled', True)
            )
            
            self.account_configs[account_id] = account_config
        
        self.account_id_list = list(self.account_configs.keys())
        
        # Build account name to ID mapping
        self.account_name_to_id.clear()
        for account_id, config in self.account_configs.items():
            if config.account_name:
                self.account_name_to_id[config.account_name.lower()] = account_id
        
        logger.info(f"Loaded {len(self.account_configs)} account configurations")
    
    async def _create_connections(self):
        """Create account connections"""
        logger.info("Creating account connections...")
        
        for account_id, account_config in self.account_configs.items():
            if not account_config.enabled:
                continue
                
            # logger.info(f"Creating connection for account {account_id}")
            
            self.usage_queues[account_id] = deque()
            
            try:
                connection = AccountConnection(account_config)
                
                if await connection.test_connection():
                    self.account_connections[account_id] = connection
                    # logger.debug(f"Account {account_id} connection created successfully")
                else:
                    logger.error(f"Account {account_id} connection test failed")
                    
            except Exception as e:
                logger.error(f"Failed to create connection for account {account_id}: {e}")
        
        total_connections = sum(
            conn.connection_count for conn in self.account_connections.values()
        )
        logger.info(f"Connection creation complete: {len(self.account_connections)} accounts, {total_connections} connections")
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        try:
            loop = asyncio.get_running_loop()
            
            # Health check task
            health_check_task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.append(health_check_task)
            
            # Cleanup task
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._background_tasks.append(cleanup_task)
            
            logger.info("Background tasks started")
            
        except RuntimeError:
            logger.info("No running event loop, background tasks will start later")
    
    async def _health_check_loop(self):
        """Health check loop"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval_seconds)
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                
    async def _cleanup_loop(self):
        """Cleanup loop"""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute
                await self._cleanup_idle_connections()
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks"""
        # Perform health checks concurrently for all accounts without global lock
        tasks = []
        for account_id, connection in self.account_connections.items():
            task = asyncio.create_task(self._health_check_account(account_id, connection))
            tasks.append(task)
        
        # Wait for all health checks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _health_check_account(self, account_id: str, connection: AccountConnection):
        """Health check for a single account"""
        try:
            await connection.test_connection()
        except Exception as e:
            logger.error(f"Health check failed for account {account_id}: {e}")
    
    async def _cleanup_idle_connections(self):
        """Cleanup idle connections"""
        # Perform cleanup concurrently for all accounts without global lock
        tasks = []
        for account_id, connection in self.account_connections.items():
            task = asyncio.create_task(self._cleanup_account(account_id, connection))
            tasks.append(task)
        
        # Wait for all cleanup operations to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _cleanup_account(self, account_id: str, connection: AccountConnection):
        """Cleanup for a single account"""
        try:
            # Get connection stats for cleanup decisions
            stats = connection.get_connection_stats()
            logger.debug(f"Account {account_id} connection stats: {stats.get('total_connections', 0)} connections")
            
            # Cleanup if connection has been idle for too long
            if stats.get('idle_time_seconds', 0) > 300:  # 5 minutes
                logger.info(f"Cleaning up idle connection for account {account_id}")
                await connection.cleanup_idle_connections()
                
        except Exception as e:
            logger.error(f"Failed to cleanup connections for account {account_id}: {e}")
    
    def get_account_by_routing(self, routing_key: Optional[str] = None, strategy: str = "round_robin") -> Optional[str]:
        """Get account ID by routing strategy"""
        if not self.account_id_list:
            return None
        
        if strategy == "round_robin":
            current_time = int(time.time())
            index = current_time % len(self.account_id_list)
            return self.account_id_list[index]
            
        elif strategy == "hash" and routing_key:
            hash_value = hashlib.md5(routing_key.encode()).hexdigest()
            index = int(hash_value, 16) % len(self.account_id_list)
            return self.account_id_list[index]
            
        elif strategy == "random":
            return random.choice(self.account_id_list)
            
        elif strategy == "least_loaded":
            min_load = float('inf')
            selected_account = None
            
            for account_id in self.account_id_list:
                connection = self.account_connections.get(account_id)
                if not connection:
                    continue
                    
                stats = connection.get_connection_stats()
                total_usage = sum(
                    conn_info.get('usage_count', 0) 
                    for conn_info in stats.get('connections', {}).values()
                )
                
                if total_usage < min_load:
                    min_load = total_usage
                    selected_account = account_id
            
            return selected_account or self.account_id_list[0]
        
        return self.account_id_list[0]
    
    def resolve_account_id(self, account_identifier: Optional[str]) -> Optional[str]:
        """Resolve account identifier to account ID"""
        if not account_identifier:
            return None
            
        # Check if it's a direct account ID
        if account_identifier in self.account_configs:
            return account_identifier
        
        # Check if it's an account name
        account_name_lower = account_identifier.lower()
        if account_name_lower in self.account_name_to_id:
            resolved_id = self.account_name_to_id[account_name_lower]
            logger.debug(f"Account name '{account_identifier}' resolved to ID: {resolved_id}")
            return resolved_id
        
        # No partial matching - exact match only for security
        # Partial matching is dangerous and can lead to wrong account selection
        
        logger.warning(f"Cannot resolve account identifier: {account_identifier}")
        return None
    
    def get_account_config(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Optional[AccountConfig]:
        """获取账户配置 - 无锁，用于HTTP客户端创建"""
        # 优先使用account_id
        resolved_account_id = None
        if account_id:
            resolved_account_id = self.resolve_account_id(account_id)
            # 如果指定了account_id但无法解析，直接返回None，不要fallback到其他账户
            if not resolved_account_id:
                logger.warning(f"Account ID '{account_id}' not found")
                return None
        
        return self.account_configs.get(resolved_account_id) if resolved_account_id else None

    async def get_connection(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> AccountConnection:
        """Get account connection"""
        if not self._initialized:
            await self.initialize()
        
        # Resolve account identifier
        resolved_account_id = None
        if account_id:
            resolved_account_id = self.resolve_account_id(account_id)
            if not resolved_account_id:
                raise Exception(f"Cannot resolve account identifier: {account_id}")
        
        # Use routing if no specific account
        if not resolved_account_id:
            resolved_account_id = self.get_account_by_routing(routing_key, strategy="round_robin")
        
        if not resolved_account_id or resolved_account_id not in self.account_connections:
            available_accounts = list(self.account_connections.keys())
            available_names = [self.account_configs[aid].account_name for aid in available_accounts if self.account_configs[aid].account_name]
            raise Exception(
                f"Account not found: {resolved_account_id}. "
                f"Available accounts: {available_accounts}. "
                f"Available names: {available_names}"
            )
        
        # Get connection and usage queue (no global lock needed)
        connection = self.account_connections[resolved_account_id]
        usage_queue = self.usage_queues[resolved_account_id]
        
        if not connection.is_available:
            logger.warning(f"Connection busy, waiting for availability (account: {resolved_account_id})")
        
        await connection.acquire()
        
        # Update usage queue (atomic operation with connection's own lock)
        if connection in usage_queue:
            usage_queue.remove(connection)
        usage_queue.append(connection)
        
        logger.debug(f"Successfully acquired account connection (account: {resolved_account_id})")
        return connection
    
    def release_connection(self, connection: AccountConnection):
        """Release connection"""
        connection.release()
    
    @asynccontextmanager
    async def get_account_connection(self, account_id: Optional[str] = None, routing_key: Optional[str] = None):
        """Connection context manager"""
        connection = None
        try:
            connection = await self.get_connection(account_id, routing_key)
            yield connection
        finally:
            if connection:
                self.release_connection(connection)
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        total_connections = sum(
            conn.connection_count for conn in self.account_connections.values()
        )
        
        stats = {
            "total_accounts": len(self.account_configs),
            "active_accounts": len([acc for acc in self.account_configs.values() if acc.enabled]),
            "total_connections": total_connections,
            "account_stats": {}
        }
        
        for account_id, connection in self.account_connections.items():
            account_config = self.account_configs.get(account_id)
            connection_stats = connection.get_connection_stats()
            
            account_stats = {
                "account_name": account_config.account_name if account_config else account_id,
                "tier": account_config.tier if account_config else "unknown",
                "connection_count": connection.connection_count,
                "is_available": connection.is_available,
                "connection_details": connection_stats.get('connections', {})
            }
            stats["account_stats"][account_id] = account_stats
        
        return stats
    
    async def get_all_accounts(self) -> Dict[str, Any]:
        """Get all account connections for position management"""
        if not self._initialized:
            await self.initialize()
        return self.account_connections
    
    async def shutdown(self):
        """Shutdown account pool"""
        logger.info("Shutting down account pool...")
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Shutdown all connections
        if self._global_lock:
            async with self._global_lock:
                for account_id, connection in list(self.account_connections.items()):
                    try:
                        await connection.shutdown()
                    except Exception as e:
                        logger.error(f"Failed to shutdown connection for account {account_id}: {e}")
                
                self.account_connections.clear()
                self.usage_queues.clear()
        
        logger.info("Account pool shutdown complete")


# Global account pool instance
account_pool = AccountPool(health_check_interval_seconds=300)


# Dependency injection function
def get_account_pool() -> AccountPool:
    """Get account pool instance"""
    return account_pool
