"""
优化的Alpaca连接池管理器
基于Alpaca最佳实践，分离Trading和Market Data连接
- Trading Client: 每用户1个，用于下单和账户操作
- Trading Stream: 每用户1个WebSocket，用于交易更新通知  
- Market Data Clients: 按需创建，用于历史数据和实时数据
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Union
from dataclasses import dataclass
from collections import deque
from contextlib import asynccontextmanager
from enum import Enum

import aiohttp
from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from alpaca.data.live.option import OptionDataStream
from loguru import logger

# from app.logging_config import UserLogger, PerformanceMonitor
# from app.user_manager import User


class ConnectionType(Enum):
    """连接类型枚举"""
    TRADING_CLIENT = "trading_client"  # REST API客户端
    TRADING_STREAM = "trading_stream"  # 交易更新WebSocket
    STOCK_DATA = "stock_data"          # 股票历史数据客户端
    OPTION_DATA = "option_data"        # 期权历史数据客户端
    STOCK_STREAM = "stock_stream"      # 股票实时数据流
    OPTION_STREAM = "option_stream"    # 期权实时数据流


@dataclass
class ConnectionStats:
    """连接统计信息"""
    connection_type: ConnectionType
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    is_healthy: bool = True


class AlpacaConnectionManager:
    """单个用户的Alpaca连接管理器"""
    
    def __init__(self, user_id: str, api_key: str, secret_key: str, paper_trading: bool = True):
        self.user_id = user_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper_trading = paper_trading
        
        # 连接容器
        self.connections: Dict[ConnectionType, any] = {}
        self.connection_stats: Dict[ConnectionType, ConnectionStats] = {}
        
        # 异步锁
        self._locks: Dict[ConnectionType, asyncio.Lock] = {}
        self._in_use: Dict[ConnectionType, bool] = {}
        
        # 初始化核心连接（每用户必需的连接）
        self._initialize_core_connections()
    
    def _initialize_core_connections(self):
        """初始化核心连接（每用户必需）"""
        try:
            # 1. Trading Client - 用于REST API调用（下单、账户查询等）
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
            
            logger.info(f"初始化Trading Client成功 (用户: {self.user_id})")
            
        except Exception as e:
            logger.error(f"初始化核心连接失败 (用户: {self.user_id}): {e}")
            raise

    def _create_data_connection(self, connection_type: ConnectionType):
        """按需创建数据连接"""
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
                raise ValueError(f"不支持的连接类型: {connection_type}")
            
            self.connections[connection_type] = connection
            self.connection_stats[connection_type] = ConnectionStats(
                connection_type=connection_type,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow()
            )
            self._locks[connection_type] = asyncio.Lock()
            self._in_use[connection_type] = False
            
            logger.info(f"创建{connection_type.value}连接成功 (用户: {self.user_id})")
            return connection
            
        except Exception as e:
            logger.error(f"创建{connection_type.value}连接失败 (用户: {self.user_id}): {e}")
            raise

    async def get_connection(self, connection_type: ConnectionType):
        """获取指定类型的连接"""
        # 如果连接不存在，创建它（除了核心连接）
        if connection_type not in self.connections:
            if connection_type == ConnectionType.TRADING_CLIENT:
                raise ValueError("Trading Client应该在初始化时创建")
            self._create_data_connection(connection_type)
        
        # 确保锁存在
        if connection_type not in self._locks:
            self._locks[connection_type] = asyncio.Lock()
        
        # 获取连接锁
        await self._locks[connection_type].acquire()
        self._in_use[connection_type] = True
        
        # 更新使用统计
        stats = self.connection_stats[connection_type]
        stats.last_used = datetime.utcnow()
        stats.usage_count += 1
        
        return self.connections[connection_type]

    def release_connection(self, connection_type: ConnectionType):
        """释放指定类型的连接"""
        if connection_type in self._locks and self._locks[connection_type].locked():
            self._locks[connection_type].release()
        self._in_use[connection_type] = False

    async def test_connection(self, connection_type: ConnectionType) -> bool:
        """测试指定连接的健康状态"""
        try:
            if connection_type not in self.connections:
                return False
                
            start_time = time.time()
            
            # 根据连接类型进行不同的健康检查
            if connection_type == ConnectionType.TRADING_CLIENT:
                # 测试Trading Client - 获取账户信息
                account = self.connections[connection_type].get_account()
                success = account is not None
            else:
                # 对于数据连接，暂时认为连接存在就是健康的
                success = True
                
            response_time = time.time() - start_time
            
            # 更新统计信息
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
            logger.error(f"{connection_type.value}连接测试失败 (用户: {self.user_id}): {e}")
            return False

    def is_connection_available(self, connection_type: ConnectionType) -> bool:
        """检查连接是否可用"""
        if connection_type not in self.connections:
            return True  # 不存在的连接可以创建
        
        return (not self._in_use.get(connection_type, False) and 
                self.connection_stats[connection_type].is_healthy)

    @property
    def connection_count(self) -> int:
        """当前连接总数"""
        return len(self.connections)

    def get_connection_stats(self) -> Dict:
        """获取连接统计信息"""
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
        """关闭所有连接"""
        logger.info(f"关闭用户{self.user_id}的所有连接...")
        
        # 释放所有锁
        for conn_type in list(self._locks.keys()):
            if self._locks[conn_type].locked():
                self._locks[conn_type].release()
        
        # 清理连接（WebSocket连接需要特殊处理）
        for conn_type, connection in list(self.connections.items()):
            try:
                if conn_type in [ConnectionType.TRADING_STREAM, ConnectionType.STOCK_STREAM, ConnectionType.OPTION_STREAM]:
                    # WebSocket连接需要调用close()方法
                    if hasattr(connection, 'close'):
                        await connection.close()
                # REST客户端不需要特殊清理
            except Exception as e:
                logger.error(f"关闭{conn_type.value}连接时出错: {e}")
        
        # 清理数据结构
        self.connections.clear()
        self.connection_stats.clear()
        self._locks.clear()
        self._in_use.clear()
        
        logger.info(f"用户{self.user_id}的连接清理完成")


class ConnectionPool:
    """优化的连接池管理器 - 基于Alpaca最佳实践"""
    
    def __init__(self, max_idle_time_minutes: int = 30, health_check_interval_seconds: int = 300):
        self.max_idle_time_minutes = max_idle_time_minutes
        self.health_check_interval_seconds = health_check_interval_seconds
        
        # 用户连接管理器 {user_id: AlpacaConnectionManager}
        self.user_managers: Dict[str, AlpacaConnectionManager] = {}
        
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
            for user_id, manager in self.user_managers.items():
                # 检查每个连接管理器中的连接健康状态
                for conn_type in list(manager.connections.keys()):
                    try:
                        await manager.test_connection(conn_type)
                    except Exception as e:
                        logger.error(f"健康检查失败 (用户: {user_id}, 连接: {conn_type.value}): {e}")
    
    async def _cleanup_idle_connections(self):
        """清理空闲连接"""
        await self._ensure_async_components()
        async with self._global_lock:
            for user_id, manager in list(self.user_managers.items()):
                # 检查管理器中的连接是否空闲过久
                idle_connections = []
                
                for conn_type, stats in manager.connection_stats.items():
                    idle_time = (datetime.utcnow() - stats.last_used).total_seconds() / 60
                    
                    if idle_time > self.max_idle_time_minutes and not manager._in_use.get(conn_type, False):
                        # 不清理核心连接（TRADING_CLIENT）
                        if conn_type != ConnectionType.TRADING_CLIENT:
                            idle_connections.append(conn_type)
                
                # 清理空闲连接
                for conn_type in idle_connections:
                    try:
                        if conn_type in manager.connections:
                            connection = manager.connections[conn_type]
                            # WebSocket连接需要关闭
                            if conn_type in [ConnectionType.TRADING_STREAM, ConnectionType.STOCK_STREAM, ConnectionType.OPTION_STREAM]:
                                if hasattr(connection, 'close'):
                                    await connection.close()
                            
                            # 从管理器中移除连接
                            del manager.connections[conn_type]
                            del manager.connection_stats[conn_type]
                            if conn_type in manager._locks:
                                del manager._locks[conn_type]
                            if conn_type in manager._in_use:
                                del manager._in_use[conn_type]
                            
                            logger.info(f"清理空闲连接 (用户: {user_id}, 连接: {conn_type.value}, 空闲时间: {idle_time:.1f}分钟)")
                    except Exception as e:
                        logger.error(f"清理连接失败 (用户: {user_id}, 连接: {conn_type.value}): {e}")
                
                # 如果用户只剩下核心连接且长时间未使用，可以考虑清理整个管理器
                if len(manager.connections) == 1 and ConnectionType.TRADING_CLIENT in manager.connections:
                    trading_stats = manager.connection_stats[ConnectionType.TRADING_CLIENT]
                    idle_time = (datetime.utcnow() - trading_stats.last_used).total_seconds() / 60
                    
                    if idle_time > self.max_idle_time_minutes * 2:  # 核心连接保持更长时间
                        try:
                            await manager.shutdown()
                            del self.user_managers[user_id]
                            logger.info(f"清理用户管理器 (用户: {user_id}, 空闲时间: {idle_time:.1f}分钟)")
                        except Exception as e:
                            logger.error(f"清理用户管理器失败 (用户: {user_id}): {e}")
    
    async def get_user_manager(self, user) -> AlpacaConnectionManager:
        """获取用户连接管理器"""
        user_id = user.id
        
        # 确保异步组件已初始化
        await self._ensure_async_components()
        
        async with self._global_lock:
            # 如果用户管理器不存在，创建它
            if user_id not in self.user_managers:
                try:
                    api_key, secret_key = user.decrypt_alpaca_credentials()
                    manager = AlpacaConnectionManager(
                        user_id=user_id,
                        api_key=api_key,
                        secret_key=secret_key,
                        paper_trading=user.alpaca_paper_trading
                    )
                    self.user_managers[user_id] = manager
                    logger.info(f"创建用户连接管理器 (用户: {user_id})")
                    
                except Exception as e:
                    logger.error(f"创建用户连接管理器失败 (用户: {user_id}): {e}")
                    raise
            
            return self.user_managers[user_id]

    async def get_connection(self, user, connection_type: ConnectionType):
        """获取指定类型的连接"""
        manager = await self.get_user_manager(user)
        return await manager.get_connection(connection_type)

    def release_connection(self, user, connection_type: ConnectionType):
        """释放指定类型的连接"""
        user_id = user.id
        if user_id in self.user_managers:
            self.user_managers[user_id].release_connection(connection_type)

    @asynccontextmanager
    async def get_user_connection(self, user, connection_type: ConnectionType):
        """连接上下文管理器"""
        connection = None
        try:
            connection = await self.get_connection(user, connection_type)
            yield connection
        finally:
            if connection:
                self.release_connection(user, connection_type)

    # 为了保持向后兼容性，提供一些便捷方法
    async def get_trading_client(self, user) -> TradingClient:
        """获取Trading Client连接"""
        return await self.get_connection(user, ConnectionType.TRADING_CLIENT)

    async def get_stock_data_client(self, user) -> StockHistoricalDataClient:
        """获取股票历史数据客户端"""
        return await self.get_connection(user, ConnectionType.STOCK_DATA)

    async def get_option_data_client(self, user) -> OptionHistoricalDataClient:
        """获取期权历史数据客户端"""
        return await self.get_connection(user, ConnectionType.OPTION_DATA)

    async def get_trading_stream(self, user) -> TradingStream:
        """获取交易更新流连接"""
        return await self.get_connection(user, ConnectionType.TRADING_STREAM)

    @asynccontextmanager
    async def get_trading_client_context(self, user):
        """Trading Client上下文管理器"""
        async with self.get_user_connection(user, ConnectionType.TRADING_CLIENT) as client:
            yield client

    @asynccontextmanager  
    async def get_stock_data_context(self, user):
        """股票数据客户端上下文管理器"""
        async with self.get_user_connection(user, ConnectionType.STOCK_DATA) as client:
            yield client

    def get_pool_stats(self) -> Dict:
        """获取连接池统计信息"""
        stats = {
            "total_users": len(self.user_managers),
            "total_connections": sum(manager.connection_count for manager in self.user_managers.values()),
            "user_stats": {}
        }
        
        for user_id, manager in self.user_managers.items():
            stats["user_stats"][user_id] = manager.get_connection_stats()
        
        return stats
    
    async def shutdown(self):
        """关闭连接池"""
        logger.info("关闭连接池...")
        
        # 取消后台任务
        for task in self._background_tasks:
            task.cancel()
            
        # 等待任务完成
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # 关闭所有用户管理器
        if self._global_lock is not None:
            async with self._global_lock:
                for user_id, manager in list(self.user_managers.items()):
                    try:
                        await manager.shutdown()
                    except Exception as e:
                        logger.error(f"关闭用户管理器失败 (用户: {user_id}): {e}")
                
                self.user_managers.clear()
        else:
            # 如果没有锁，直接清理
            for user_id, manager in list(self.user_managers.items()):
                try:
                    await manager.shutdown()
                except Exception as e:
                    logger.error(f"关闭用户管理器失败 (用户: {user_id}): {e}")
            
            self.user_managers.clear()
        
        logger.info("连接池关闭完成")


# 全局连接池实例 - 优化配置
connection_pool = ConnectionPool(
    max_idle_time_minutes=30,              # 空闲连接保持时间
    health_check_interval_seconds=300      # 健康检查间隔
)


# 依赖注入函数
def get_connection_pool() -> ConnectionPool:
    """获取连接池实例"""
    return connection_pool


# 导出连接类型供其他模块使用
__all__ = ['ConnectionPool', 'ConnectionType', 'AlpacaConnectionManager', 'get_connection_pool']