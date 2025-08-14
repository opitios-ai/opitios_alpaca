"""
优化的预配置账户连接池管理器
基于Alpaca最佳实践，每账户只创建必要的连接
支持1000个预配置账户的高效连接管理和负载均衡
"""

import asyncio
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from collections import deque
from contextlib import asynccontextmanager
import random

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from loguru import logger

from config import settings
from app.connection_pool import AlpacaConnectionManager, ConnectionType


@dataclass
class AccountConfig:
    """优化的账户配置 - 符合Alpaca最佳实践"""
    account_id: str
    api_key: str
    secret_key: str
    paper_trading: bool = True
    account_name: Optional[str] = None
    region: str = "us"
    tier: str = "standard"  # standard, premium, vip
    enabled: bool = True
    # 移除 max_connections，改为使用Alpaca最佳实践


class OptimizedAccountConnection:
    """优化的账户连接封装 - 使用新的连接管理器"""
    
    def __init__(self, account_config: AccountConfig):
        self.account_config = account_config
        self.connection_id = f"{account_config.account_id}_{int(time.time())}"
        
        # 使用优化的连接管理器，符合Alpaca最佳实践
        self.connection_manager = AlpacaConnectionManager(
            user_id=account_config.account_id,
            api_key=account_config.api_key,
            secret_key=account_config.secret_key,
            paper_trading=account_config.paper_trading
        )
        
        # 异步锁
        self._lock = asyncio.Lock()
        self._in_use = False
        
    async def test_connection(self) -> bool:
        """测试连接健康状态"""
        try:
            async with self._lock:
                # 测试核心Trading Client连接
                is_healthy = await self.connection_manager.test_connection(
                    ConnectionType.TRADING_CLIENT
                )
                
                if not is_healthy:
                    logger.warning(f"账户连接不健康: {self.account_config.account_id}")
                
                return is_healthy
                
        except Exception as e:
            logger.error(f"连接测试失败 (账户: {self.account_config.account_id}): {e}")
            return False
    
    async def acquire(self):
        """获取连接"""
        await self._lock.acquire()
        self._in_use = True
        
    def release(self):
        """释放连接"""
        self._in_use = False
        if self._lock.locked():
            self._lock.release()
    
    async def get_trading_client(self) -> TradingClient:
        """获取Trading Client"""
        return await self.connection_manager.get_connection(ConnectionType.TRADING_CLIENT)
    
    def release_trading_client(self):
        """释放Trading Client"""
        self.connection_manager.release_connection(ConnectionType.TRADING_CLIENT)
    
    async def get_stock_data_client(self) -> StockHistoricalDataClient:
        """获取股票数据客户端"""
        return await self.connection_manager.get_connection(ConnectionType.STOCK_DATA)
    
    def release_stock_data_client(self):
        """释放股票数据客户端"""
        self.connection_manager.release_connection(ConnectionType.STOCK_DATA)
    
    @property
    def is_available(self) -> bool:
        """检查连接是否可用"""
        return not self._in_use and self.account_config.enabled
    
    @property
    def connection_count(self) -> int:
        """当前连接总数"""
        return self.connection_manager.connection_count
    
    def get_connection_stats(self) -> Dict:
        """获取连接统计信息"""
        return self.connection_manager.get_connection_stats()
    
    async def shutdown(self):
        """关闭所有连接"""
        await self.connection_manager.shutdown()


class AccountConnectionPool:
    """优化的账户连接池管理器 - 基于Alpaca最佳实践"""
    
    def __init__(self, health_check_interval_seconds: int = 300):
        self.health_check_interval_seconds = health_check_interval_seconds
        
        # 账户配置 {account_id: AccountConfig}
        self.account_configs: Dict[str, AccountConfig] = {}
        
        # 账户连接管理器 {account_id: OptimizedAccountConnection}
        self.account_managers: Dict[str, OptimizedAccountConnection] = {}
        
        # 连接使用队列 {account_id: deque[OptimizedAccountConnection]} 
        self.usage_queues: Dict[str, deque[OptimizedAccountConnection]] = {}
        
        # 账户ID映射 (用于路由算法)
        self.account_id_list: List[str] = []
        
        # 全局锁
        self._global_lock = None
        
        # 后台任务
        self._background_tasks = []
        
        # 初始化标志
        self._initialized = False
        
    async def initialize(self):
        """初始化连接池"""
        if self._initialized:
            return
            
        logger.info("开始初始化账户连接池...")
        
        # 确保异步组件已初始化
        await self._ensure_async_components()
        
        # 加载账户配置
        await self._load_account_configs()
        
        # 预建立连接
        await self._prebuild_connections()
        
        # 启动后台任务
        self._start_background_tasks()
        
        self._initialized = True
        logger.info(f"账户连接池初始化完成: {len(self.account_configs)} 个账户, {sum(manager.connection_count for manager in self.account_managers.values())} 个连接管理器")
    
    async def _ensure_async_components(self):
        """确保异步组件已初始化"""
        if self._global_lock is None:
            self._global_lock = asyncio.Lock()
    
    async def _load_account_configs(self):
        """从配置文件加载账户配置"""
        # 从secrets.yml加载多账户配置
        accounts_config = getattr(settings, 'accounts', {})
        
        if not accounts_config:
            # 如果没有多账户配置，使用默认单账户配置
            logger.warning("未找到多账户配置，使用默认单账户配置")
            default_account = AccountConfig(
                account_id="default_account",
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                paper_trading=settings.alpaca_paper_trading,
                account_name="Default Account"
            )
            self.account_configs["default_account"] = default_account
            self.account_id_list = ["default_account"]
            return
        
        # 加载多账户配置
        for account_id, config in accounts_config.items():
            if not config.get('enabled', True):
                logger.info(f"跳过已禁用的账户: {account_id}")
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
                # 移除 max_connections，改为使用Alpaca最佳实践（每账户1个核心连接）
            )
            
            self.account_configs[account_id] = account_config
        
        self.account_id_list = list(self.account_configs.keys())
        logger.info(f"加载了 {len(self.account_configs)} 个账户配置")
    
    async def _prebuild_connections(self):
        """优化的连接预建立 - 每账户只创建1个核心连接管理器"""
        logger.info("开始初始化账户连接管理器...")
        
        for account_id, account_config in self.account_configs.items():
            if not account_config.enabled:
                continue
                
            logger.info(f"为账户 {account_id} 初始化连接管理器 (核心连接: 1个)")
            
            self.usage_queues[account_id] = deque()
            
            try:
                # 创建优化的账户连接管理器（每账户1个）
                connection_manager = OptimizedAccountConnection(account_config)
                
                # 测试核心连接
                if await connection_manager.test_connection():
                    self.account_managers[account_id] = connection_manager
                    logger.debug(f"账户 {account_id} 连接管理器初始化成功")
                else:
                    logger.error(f"账户 {account_id} 连接管理器测试失败")
                    
            except Exception as e:
                logger.error(f"初始化账户 {account_id} 连接管理器失败: {e}")
        
        total_connections = sum(
            manager.connection_count for manager in self.account_managers.values()
        )
        logger.info(f"连接管理器初始化完成: {len(self.account_managers)} 个管理器, {total_connections} 个核心连接")
    
    def _start_background_tasks(self):
        """启动后台维护任务"""
        try:
            loop = asyncio.get_running_loop()
            
            # 健康检查任务
            health_check_task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.append(health_check_task)
            
            # 连接清理任务
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._background_tasks.append(cleanup_task)
            
            logger.info("后台维护任务启动完成")
            
        except RuntimeError:
            logger.info("没有运行的事件循环，后台任务将稍后启动")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval_seconds)
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"健康检查循环错误: {e}")
                
    async def _cleanup_loop(self):
        """连接清理循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                await self._cleanup_idle_connections()
            except Exception as e:
                logger.error(f"连接清理循环错误: {e}")
    
    async def _perform_health_checks(self):
        """执行健康检查"""
        if not self._global_lock:
            return
            
        async with self._global_lock:
            for account_id, manager in self.account_managers.items():
                try:
                    # 对每个账户管理器进行健康检查
                    await manager.test_connection()
                except Exception as e:
                    logger.error(f"账户 {account_id} 健康检查失败: {e}")
    
    async def _cleanup_idle_connections(self):
        """智能连接清理 - 只清理非核心连接"""
        # 对于预配置账户，只清理数据连接，保持核心Trading Client连接
        if not self._global_lock:
            return
            
        async with self._global_lock:
            for account_id, manager in self.account_managers.items():
                try:
                    # 获取连接管理器的统计信息
                    stats = manager.get_connection_stats()
                    
                    # 检查是否有空闲的数据连接可以清理
                    # 核心连接（TRADING_CLIENT）会保持活跃
                    # 这个清理逻辑由底层的AlpacaConnectionManager处理
                    
                    logger.debug(f"账户 {account_id} 连接状态: 总连接数={stats.get('total_connections', 0)}")
                    
                except Exception as e:
                    logger.error(f"清理账户 {account_id} 空闲连接失败: {e}")
    
    def get_account_by_routing(self, routing_key: Optional[str] = None, strategy: str = "round_robin") -> Optional[str]:
        """根据路由策略获取账户ID"""
        if not self.account_id_list:
            return None
        
        if strategy == "round_robin":
            # 简单轮询
            current_time = int(time.time())
            index = current_time % len(self.account_id_list)
            return self.account_id_list[index]
            
        elif strategy == "hash" and routing_key:
            # 基于routing_key的哈希路由
            hash_value = hashlib.md5(routing_key.encode()).hexdigest()
            index = int(hash_value, 16) % len(self.account_id_list)
            return self.account_id_list[index]
            
        elif strategy == "random":
            # 随机选择
            return random.choice(self.account_id_list)
            
        elif strategy == "least_loaded":
            # 选择负载最小的账户
            min_load = float('inf')
            selected_account = None
            
            for account_id in self.account_id_list:
                manager = self.account_managers.get(account_id)
                if not manager:
                    continue
                    
                # 获取管理器的连接统计信息
                stats = manager.get_connection_stats()
                total_usage = sum(
                    conn_info.get('usage_count', 0) 
                    for conn_info in stats.get('connections', {}).values()
                )
                
                if total_usage < min_load:
                    min_load = total_usage
                    selected_account = account_id
            
            return selected_account or self.account_id_list[0]
        
        # 默认返回第一个账户
        return self.account_id_list[0]
    
    async def get_connection(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> OptimizedAccountConnection:
        """获取优化的账户连接"""
        if not self._initialized:
            await self.initialize()
        
        # 如果没有指定账户ID，使用路由策略选择
        if not account_id:
            account_id = self.get_account_by_routing(routing_key, strategy="round_robin")
        
        if not account_id or account_id not in self.account_managers:
            raise Exception(f"账户不存在或无可用连接管理器: {account_id}")
        
        async with self._global_lock:
            manager = self.account_managers[account_id]
            usage_queue = self.usage_queues[account_id]
            
            # 检查连接管理器是否可用
            if not manager.is_available:
                logger.warning(f"连接管理器繁忙，等待可用 (账户: {account_id})")
                # 这里可以等待或者直接返回，根据业务需求决定
            
            # 获取连接管理器
            await manager.acquire()
            
            # 更新使用队列
            if manager in usage_queue:
                usage_queue.remove(manager)
            usage_queue.append(manager)
            
            return manager
    
    def release_connection(self, connection: OptimizedAccountConnection):
        """释放连接"""
        connection.release()
    
    @asynccontextmanager
    async def get_account_connection(self, account_id: Optional[str] = None, routing_key: Optional[str] = None):
        """连接上下文管理器"""
        connection = None
        try:
            connection = await self.get_connection(account_id, routing_key)
            yield connection
        finally:
            if connection:
                self.release_connection(connection)
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取优化的连接池统计信息"""
        total_connections = sum(
            manager.connection_count for manager in self.account_managers.values()
        )
        
        stats = {
            "total_accounts": len(self.account_configs),
            "active_accounts": len([acc for acc in self.account_configs.values() if acc.enabled]),
            "total_connections": total_connections,
            "account_stats": {}
        }
        
        for account_id, manager in self.account_managers.items():
            account_config = self.account_configs.get(account_id)
            manager_stats = manager.get_connection_stats()
            
            account_stats = {
                "account_name": account_config.account_name if account_config else account_id,
                "tier": account_config.tier if account_config else "unknown",
                "connection_count": manager.connection_count,
                "is_available": manager.is_available,
                "connection_details": manager_stats.get('connections', {})
            }
            stats["account_stats"][account_id] = account_stats
        
        return stats
    
    async def shutdown(self):
        """关闭连接池"""
        logger.info("关闭账户连接池...")
        
        # 取消后台任务
        for task in self._background_tasks:
            task.cancel()
            
        # 等待任务完成
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # 关闭所有账户连接管理器
        if self._global_lock:
            async with self._global_lock:
                for account_id, manager in list(self.account_managers.items()):
                    try:
                        await manager.shutdown()
                    except Exception as e:
                        logger.error(f"关闭账户 {account_id} 连接管理器失败: {e}")
                
                self.account_managers.clear()
                self.usage_queues.clear()
        
        logger.info("账户连接池关闭完成")


# 全局账户连接池实例 - 优化配置
account_pool = AccountConnectionPool(
    health_check_interval_seconds=300  # 移除max_connections_per_account，使用Alpaca最佳实践
)


# 依赖注入函数
def get_account_pool() -> AccountConnectionPool:
    """获取优化的账户连接池实例"""
    return account_pool


# 向后兼容的别名（替代原来的connection_pool）
connection_pool = account_pool
get_connection_pool = get_account_pool