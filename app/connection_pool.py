"""
高性能连接池管理器
支持多用户并发连接、连接复用、智能负载均衡
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from collections import deque
from contextlib import asynccontextmanager

import aiohttp
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from loguru import logger

from app.logging_config import UserLogger, PerformanceMonitor
from app.user_manager import User


@dataclass
class ConnectionStats:
    """连接统计信息"""
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    is_healthy: bool = True


class AlpacaConnection:
    """Alpaca连接封装"""
    
    def __init__(self, user_id: str, api_key: str, secret_key: str, paper_trading: bool = True):
        self.user_id = user_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper_trading = paper_trading
        
        # 初始化客户端
        self.trading_client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper_trading
        )
        
        self.data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key
        )
        
        # 连接统计
        self.stats = ConnectionStats(
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow()
        )
        
        # 异步锁 (立即初始化以避免竞态条件)
        self._lock = asyncio.Lock()
        self._in_use = False
        
    def _ensure_lock(self):
        """确保锁已初始化 (现在不需要了，但保留兼容性)"""
        if self._lock is None:
            self._lock = asyncio.Lock()
    
    async def test_connection(self) -> bool:
        """测试连接健康状态"""
        try:
            self._ensure_lock()
            async with self._lock:
                start_time = time.time()
                
                # 尝试获取账户信息
                account = self.trading_client.get_account()
                
                response_time = time.time() - start_time
                
                # 更新统计信息
                self.stats.last_used = datetime.utcnow()
                self.stats.usage_count += 1
                self.stats.avg_response_time = (
                    (self.stats.avg_response_time * (self.stats.usage_count - 1) + response_time) 
                    / self.stats.usage_count
                )
                self.stats.is_healthy = True
                
                return account is not None
                
        except Exception as e:
            self.stats.error_count += 1
            self.stats.is_healthy = False
            logger.error(f"连接测试失败 (用户: {self.user_id}): {e}")
            return False
    
    async def acquire(self):
        """获取连接"""
        self._ensure_lock()
        await self._lock.acquire()
        self._in_use = True
        self.stats.last_used = datetime.utcnow()
        
    def release(self):
        """释放连接"""
        self._in_use = False
        if self._lock and self._lock.locked():
            self._lock.release()
    
    @property
    def is_available(self) -> bool:
        """检查连接是否可用"""
        return not self._in_use and self.stats.is_healthy
    
    @property
    def age_minutes(self) -> float:
        """连接年龄(分钟)"""
        return (datetime.utcnow() - self.stats.created_at).total_seconds() / 60


class ConnectionPool:
    """连接池管理器"""
    
    def __init__(self, max_connections_per_user: int = 5, max_idle_time_minutes: int = 30,
                 health_check_interval_seconds: int = 300):
        self.max_connections_per_user = max_connections_per_user
        self.max_idle_time_minutes = max_idle_time_minutes
        self.health_check_interval_seconds = health_check_interval_seconds
        
        # 用户连接池 {user_id: [AlpacaConnection]}
        self.user_pools: Dict[str, List[AlpacaConnection]] = {}
        
        # 连接使用队列 {user_id: deque[AlpacaConnection]}
        self.usage_queues: Dict[str, deque[AlpacaConnection]] = {}
        
        # 全局锁 (延迟初始化)
        self._global_lock = None
        
        # 启动后台任务
        self._background_tasks = []
        self._start_background_tasks()
        
    def _start_background_tasks(self):
        """启动后台维护任务"""
        try:
            # 只有在事件循环运行时才创建任务
            loop = asyncio.get_running_loop()
            
            # 健康检查任务
            health_check_task = asyncio.create_task(self._health_check_loop())
            self._background_tasks.append(health_check_task)
            
            # 连接清理任务
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._background_tasks.append(cleanup_task)
            
        except RuntimeError:
            # 没有运行的事件循环，延迟启动任务
            logger.info("No running event loop, background tasks will be started later")
    
    async def _ensure_async_components(self):
        """确保异步组件已初始化"""
        if self._global_lock is None:
            self._global_lock = asyncio.Lock()
        
        # 如果后台任务未启动，尝试启动
        if not self._background_tasks:
            self._start_background_tasks()
        
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
        await self._ensure_async_components()
        async with self._global_lock:
            for user_id, connections in self.user_pools.items():
                healthy_connections = []
                
                for conn in connections:
                    if not conn.is_available:
                        healthy_connections.append(conn)
                        continue
                        
                    # 测试连接健康状态
                    is_healthy = await conn.test_connection()
                    
                    if is_healthy:
                        healthy_connections.append(conn)
                    else:
                        logger.warning(f"移除不健康连接 (用户: {user_id})")
                        UserLogger.log_user_operation(
                            user_id=user_id,
                            operation="connection_health_check_failed",
                            details={"error_count": conn.stats.error_count},
                            success=False
                        )
                
                self.user_pools[user_id] = healthy_connections
    
    async def _cleanup_idle_connections(self):
        """清理空闲连接"""
        await self._ensure_async_components()
        async with self._global_lock:
            for user_id, connections in list(self.user_pools.items()):
                active_connections = []
                
                for conn in connections:
                    # 检查连接是否空闲过久
                    idle_time = (datetime.utcnow() - conn.stats.last_used).total_seconds() / 60
                    
                    if idle_time < self.max_idle_time_minutes or conn._in_use:
                        active_connections.append(conn)
                    else:
                        logger.info(f"清理空闲连接 (用户: {user_id}, 空闲时间: {idle_time:.1f}分钟)")
                
                if active_connections:
                    self.user_pools[user_id] = active_connections
                else:
                    # 如果没有活跃连接，移除用户池
                    del self.user_pools[user_id]
                    if user_id in self.usage_queues:
                        del self.usage_queues[user_id]
    
    async def get_connection(self, user: User) -> AlpacaConnection:
        """获取用户连接"""
        user_id = user.id
        
        # 确保异步组件已初始化
        await self._ensure_async_components()
        
        async with self._global_lock:
            # 初始化用户池
            if user_id not in self.user_pools:
                self.user_pools[user_id] = []
                self.usage_queues[user_id] = deque()
            
            connections = self.user_pools[user_id]
            usage_queue = self.usage_queues[user_id]
            
            # 寻找可用连接
            available_conn = None
            for conn in connections:
                if conn.is_available:
                    available_conn = conn
                    break
            
            # 如果没有可用连接且未达到最大限制，创建新连接
            if not available_conn and len(connections) < self.max_connections_per_user:
                try:
                    api_key, secret_key = user.decrypt_alpaca_credentials()
                    available_conn = AlpacaConnection(
                        user_id=user_id,
                        api_key=api_key,
                        secret_key=secret_key,
                        paper_trading=user.alpaca_paper_trading
                    )
                    
                    # 测试新连接
                    if await available_conn.test_connection():
                        connections.append(available_conn)
                        logger.info(f"创建新连接 (用户: {user_id}, 总连接数: {len(connections)})")
                    else:
                        raise Exception("连接测试失败")
                        
                except Exception as e:
                    logger.error(f"创建连接失败 (用户: {user_id}): {e}")
                    raise
            
            # 如果仍然没有可用连接，使用最少使用的连接
            if not available_conn and connections:
                # 按使用次数排序，选择最少使用的
                available_conn = min(connections, key=lambda c: c.stats.usage_count)
                logger.warning(f"复用繁忙连接 (用户: {user_id})")
            
            if not available_conn:
                raise Exception(f"无法获取连接 (用户: {user_id})")
            
            # 获取连接
            await available_conn.acquire()
            
            # 更新使用队列
            if available_conn in usage_queue:
                usage_queue.remove(available_conn)
            usage_queue.append(available_conn)
            
            return available_conn
    
    def release_connection(self, connection: AlpacaConnection):
        """释放连接"""
        connection.release()
        
        # 记录性能指标
        UserLogger.log_performance_metric(
            metric_name="connection_usage_count",
            value=connection.stats.usage_count,
            unit="count",
            user_id=connection.user_id,
            additional_data={
                "avg_response_time": connection.stats.avg_response_time,
                "error_count": connection.stats.error_count
            }
        )
    
    @asynccontextmanager
    async def get_user_connection(self, user: User):
        """连接上下文管理器"""
        connection = None
        try:
            connection = await self.get_connection(user)
            yield connection
        finally:
            if connection:
                self.release_connection(connection)
    
    def get_pool_stats(self) -> Dict:
        """获取连接池统计信息"""
        stats = {
            "total_users": len(self.user_pools),
            "total_connections": sum(len(conns) for conns in self.user_pools.values()),
            "user_stats": {}
        }
        
        for user_id, connections in self.user_pools.items():
            user_stats = {
                "connection_count": len(connections),
                "available_connections": sum(1 for c in connections if c.is_available),
                "healthy_connections": sum(1 for c in connections if c.stats.is_healthy),
                "total_usage": sum(c.stats.usage_count for c in connections),
                "total_errors": sum(c.stats.error_count for c in connections),
                "avg_response_time": sum(c.stats.avg_response_time for c in connections) / len(connections) if connections else 0
            }
            stats["user_stats"][user_id] = user_stats
        
        return stats
    
    async def shutdown(self):
        """关闭连接池"""
        logger.info("关闭连接池...")
        
        # 取消后台任务
        for task in self._background_tasks:
            task.cancel()
            
        # 等待任务完成
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # 清理所有连接
        if self._global_lock is not None:
            async with self._global_lock:
                for user_id, connections in self.user_pools.items():
                    for conn in connections:
                        if conn._in_use:
                            conn.release()
                
                self.user_pools.clear()
                self.usage_queues.clear()
        else:
            # 如果没有锁，直接清理
            for user_id, connections in self.user_pools.items():
                for conn in connections:
                    if conn._in_use:
                        conn.release()
            
            self.user_pools.clear()
            self.usage_queues.clear()
        
        logger.info("连接池关闭完成")


# 全局连接池实例
connection_pool = ConnectionPool(
    max_connections_per_user=5,
    max_idle_time_minutes=30,
    health_check_interval_seconds=300
)


# 依赖注入函数
def get_connection_pool() -> ConnectionPool:
    """获取连接池实例"""
    return connection_pool