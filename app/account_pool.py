"""
预配置账户连接池管理器
支持1000个预配置账户的连接池，支持账户路由和负载均衡
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
from app.alpaca_client import AlpacaClient


@dataclass
class AccountConfig:
    """账户配置"""
    account_id: str
    api_key: str
    secret_key: str
    paper_trading: bool = True
    account_name: Optional[str] = None
    region: str = "us"
    tier: str = "standard"  # standard, premium, vip
    max_connections: int = 3
    enabled: bool = True


@dataclass
class ConnectionStats:
    """连接统计信息"""
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None


class AlpacaAccountConnection:
    """单个账户连接封装"""
    
    def __init__(self, account_config: AccountConfig):
        self.account_config = account_config
        self.connection_id = f"{account_config.account_id}_{int(time.time())}"
        
        # 初始化Alpaca客户端
        self.alpaca_client = AlpacaClient(
            api_key=account_config.api_key,
            secret_key=account_config.secret_key,
            paper_trading=account_config.paper_trading
        )
        
        # 连接统计
        self.stats = ConnectionStats(
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow()
        )
        
        # 异步锁
        self._lock = asyncio.Lock()
        self._in_use = False
        
    async def test_connection(self) -> bool:
        """测试连接健康状态"""
        try:
            async with self._lock:
                start_time = time.time()
                
                # 测试连接
                result = await self.alpaca_client.test_connection()
                
                response_time = time.time() - start_time
                
                # 更新统计信息
                self.stats.last_used = datetime.utcnow()
                self.stats.last_health_check = datetime.utcnow()
                self.stats.usage_count += 1
                self.stats.avg_response_time = (
                    (self.stats.avg_response_time * (self.stats.usage_count - 1) + response_time) 
                    / self.stats.usage_count
                )
                
                is_healthy = result.get("status") == "connected"
                self.stats.is_healthy = is_healthy
                
                if not is_healthy:
                    self.stats.error_count += 1
                    logger.warning(f"账户连接不健康: {self.account_config.account_id}")
                
                return is_healthy
                
        except Exception as e:
            self.stats.error_count += 1
            self.stats.is_healthy = False
            logger.error(f"连接测试失败 (账户: {self.account_config.account_id}): {e}")
            return False
    
    async def acquire(self):
        """获取连接"""
        await self._lock.acquire()
        self._in_use = True
        self.stats.last_used = datetime.utcnow()
        
    def release(self):
        """释放连接"""
        self._in_use = False
        if self._lock.locked():
            self._lock.release()
    
    @property
    def is_available(self) -> bool:
        """检查连接是否可用"""
        return not self._in_use and self.stats.is_healthy and self.account_config.enabled
    
    @property
    def age_minutes(self) -> float:
        """连接年龄(分钟)"""
        return (datetime.utcnow() - self.stats.created_at).total_seconds() / 60


class AccountConnectionPool:
    """账户连接池管理器"""
    
    def __init__(self, max_connections_per_account: int = 3, health_check_interval_seconds: int = 300):
        self.max_connections_per_account = max_connections_per_account
        self.health_check_interval_seconds = health_check_interval_seconds
        
        # 账户配置 {account_id: AccountConfig}
        self.account_configs: Dict[str, AccountConfig] = {}
        
        # 账户连接池 {account_id: [AlpacaAccountConnection]}
        self.account_pools: Dict[str, List[AlpacaAccountConnection]] = {}
        
        # 连接使用队列 {account_id: deque[AlpacaAccountConnection]}
        self.usage_queues: Dict[str, deque[AlpacaAccountConnection]] = {}
        
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
        logger.info(f"账户连接池初始化完成: {len(self.account_configs)} 个账户, {sum(len(conns) for conns in self.account_pools.values())} 个连接")
    
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
                max_connections=config.get('max_connections', 3),
                enabled=config.get('enabled', True)
            )
            
            self.account_configs[account_id] = account_config
        
        self.account_id_list = list(self.account_configs.keys())
        logger.info(f"加载了 {len(self.account_configs)} 个账户配置")
    
    async def _prebuild_connections(self):
        """预建立所有账户连接"""
        logger.info("开始预建立账户连接...")
        
        for account_id, account_config in self.account_configs.items():
            if not account_config.enabled:
                continue
                
            logger.info(f"为账户 {account_id} 预建立 {account_config.max_connections} 个连接")
            
            self.account_pools[account_id] = []
            self.usage_queues[account_id] = deque()
            
            # 为每个账户创建指定数量的连接
            for i in range(account_config.max_connections):
                try:
                    connection = AlpacaAccountConnection(account_config)
                    
                    # 测试连接
                    if await connection.test_connection():
                        self.account_pools[account_id].append(connection)
                        logger.debug(f"账户 {account_id} 连接 {i+1} 创建成功")
                    else:
                        logger.error(f"账户 {account_id} 连接 {i+1} 测试失败")
                        
                except Exception as e:
                    logger.error(f"创建账户 {account_id} 连接 {i+1} 失败: {e}")
        
        total_connections = sum(len(conns) for conns in self.account_pools.values())
        logger.info(f"预建立连接完成: {total_connections} 个连接")
    
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
            for account_id, connections in self.account_pools.items():
                healthy_connections = []
                
                for conn in connections:
                    if conn._in_use:
                        healthy_connections.append(conn)
                        continue
                        
                    # 测试连接健康状态
                    is_healthy = await conn.test_connection()
                    
                    if is_healthy:
                        healthy_connections.append(conn)
                    else:
                        logger.warning(f"移除不健康连接 (账户: {account_id})")
                
                self.account_pools[account_id] = healthy_connections
    
    async def _cleanup_idle_connections(self):
        """清理空闲连接（暂时不清理，保持预配置连接）"""
        # 对于预配置连接池，我们不清理空闲连接，而是保持它们活跃
        pass
    
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
                connections = self.account_pools.get(account_id, [])
                if not connections:
                    continue
                    
                # 计算平均使用次数作为负载指标
                avg_usage = sum(conn.stats.usage_count for conn in connections) / len(connections)
                if avg_usage < min_load:
                    min_load = avg_usage
                    selected_account = account_id
            
            return selected_account or self.account_id_list[0]
        
        # 默认返回第一个账户
        return self.account_id_list[0]
    
    async def get_connection(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> AlpacaAccountConnection:
        """获取账户连接"""
        if not self._initialized:
            await self.initialize()
        
        # 如果没有指定账户ID，使用路由策略选择
        if not account_id:
            account_id = self.get_account_by_routing(routing_key, strategy="round_robin")
        
        if not account_id or account_id not in self.account_pools:
            raise Exception(f"账户不存在或无可用连接: {account_id}")
        
        async with self._global_lock:
            connections = self.account_pools[account_id]
            usage_queue = self.usage_queues[account_id]
            
            # 寻找可用连接
            available_conn = None
            for conn in connections:
                if conn.is_available:
                    available_conn = conn
                    break
            
            # 如果没有可用连接，使用最少使用的连接
            if not available_conn and connections:
                available_conn = min(connections, key=lambda c: c.stats.usage_count)
                logger.warning(f"复用繁忙连接 (账户: {account_id})")
            
            if not available_conn:
                raise Exception(f"无法获取连接 (账户: {account_id})")
            
            # 获取连接
            await available_conn.acquire()
            
            # 更新使用队列
            if available_conn in usage_queue:
                usage_queue.remove(available_conn)
            usage_queue.append(available_conn)
            
            return available_conn
    
    def release_connection(self, connection: AlpacaAccountConnection):
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
        """获取连接池统计信息"""
        stats = {
            "total_accounts": len(self.account_configs),
            "active_accounts": len([acc for acc in self.account_configs.values() if acc.enabled]),
            "total_connections": sum(len(conns) for conns in self.account_pools.values()),
            "account_stats": {}
        }
        
        for account_id, connections in self.account_pools.items():
            if not connections:
                continue
                
            account_config = self.account_configs.get(account_id)
            account_stats = {
                "account_name": account_config.account_name if account_config else account_id,
                "tier": account_config.tier if account_config else "unknown",
                "connection_count": len(connections),
                "available_connections": sum(1 for c in connections if c.is_available),
                "healthy_connections": sum(1 for c in connections if c.stats.is_healthy),
                "total_usage": sum(c.stats.usage_count for c in connections),
                "total_errors": sum(c.stats.error_count for c in connections),
                "avg_response_time": sum(c.stats.avg_response_time for c in connections) / len(connections) if connections else 0,
                "last_health_check": max((c.stats.last_health_check for c in connections if c.stats.last_health_check), default=None)
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
        
        # 清理所有连接
        if self._global_lock:
            async with self._global_lock:
                for account_id, connections in self.account_pools.items():
                    for conn in connections:
                        if conn._in_use:
                            conn.release()
                
                self.account_pools.clear()
                self.usage_queues.clear()
        
        logger.info("账户连接池关闭完成")


# 全局账户连接池实例
account_pool = AccountConnectionPool(
    max_connections_per_account=3,
    health_check_interval_seconds=300
)


# 依赖注入函数
def get_account_pool() -> AccountConnectionPool:
    """获取账户连接池实例"""
    return account_pool


# 向后兼容的别名（替代原来的connection_pool）
connection_pool = account_pool
get_connection_pool = get_account_pool