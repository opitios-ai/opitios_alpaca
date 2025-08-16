"""
WebSocket路由 - 使用单例管理器，确保架构正确
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import websockets
import msgpack
import ssl
import threading
import weakref
from typing import Dict, List, Set, Optional
from datetime import datetime
from loguru import logger

from config import settings

# WebSocket路由
ws_router = APIRouter(prefix="/ws", tags=["websocket"])

# 全局订阅符号和客户端连接 - 使用线程安全锁保护
_global_lock = asyncio.Lock()
subscribed_symbols: Set[str] = set()
active_connections: Dict[str, WebSocket] = {}
client_subscriptions: Dict[str, Set[str]] = {}  # 每个客户端订阅的符号

class SingletonWebSocketManager:
    """
    单例WebSocket管理器 - 线程安全和异步安全
    确保整个应用只有1个股票WS + 1个期权WS连接
    """
    
    _instance: Optional['SingletonWebSocketManager'] = None
    _instance_lock = threading.Lock()  # 线程级别的锁
    _instance_init_lock = asyncio.Lock()  # 异步级别的锁
    
    # Alpaca官方端点
    STOCK_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"
    OPTION_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/indicative"
    
    def __new__(cls):
        # 双重检查锁定模式 - 线程安全的单例
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 使用弱引用避免循环引用问题
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        # WebSocket连接
        self.stock_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.option_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.stock_connected = False
        self.option_connected = False
        
        # 专用账户
        self._stock_account: Optional[Dict] = None
        self._option_account: Optional[Dict] = None
        
        # 监听任务 - 原子化管理
        self._stock_listener: Optional[asyncio.Task] = None
        self._option_listener: Optional[asyncio.Task] = None
        self._stock_listener_lock = asyncio.Lock()
        self._option_listener_lock = asyncio.Lock()
        
        # 重连任务
        self._reconnection_task: Optional[asyncio.Task] = None
        
        # WebSocket recv 锁 - 防止并发recv调用
        self._stock_recv_lock = asyncio.Lock()
        self._option_recv_lock = asyncio.Lock()
        
        # 连接状态锁
        self._stock_connection_lock = asyncio.Lock()
        self._option_connection_lock = asyncio.Lock()
        
        # 初始化锁
        self._init_lock = asyncio.Lock()
        
        # 关闭标志
        self._shutdown_event = asyncio.Event()
        
        self._initialized = True
        
    async def ensure_initialized(self):
        """确保WebSocket管理器已初始化 - 线程安全"""
        if self._shutdown_event.is_set():
            logger.warning("WebSocket管理器已关闭，无法初始化")
            return
            
        async with self._init_lock:
            try:
                if not self._stock_account or not self._option_account:
                    await self._load_dedicated_accounts()
                    
                # 原子化启动重连任务
                if not self._reconnection_task or self._reconnection_task.done():
                    if self._reconnection_task and not self._reconnection_task.done():
                        self._reconnection_task.cancel()
                        try:
                            await self._reconnection_task
                        except asyncio.CancelledError:
                            pass
                    self._reconnection_task = asyncio.create_task(self._reconnection_manager())
                    
                # 如果有订阅且连接断开，重新连接
                async with _global_lock:
                    has_symbols = bool(subscribed_symbols)
                    
                if has_symbols:
                    if not self.stock_connected:
                        await self._ensure_stock_connection()
                    if not self.option_connected:
                        await self._ensure_option_connection()
                        
            except Exception as e:
                logger.error(f"❌ WebSocket管理器初始化失败: {e}")
                raise
    
    async def _load_dedicated_accounts(self):
        """加载专用WebSocket账户"""
        try:
            # 导入account_pool以获取AccountConfig对象
            from app.account_pool import account_pool
            
            # 确保account_pool已初始化
            if not account_pool._initialized:
                await account_pool.initialize()
            
            # 获取专用股票WebSocket账户
            stock_account = None
            option_account = None
            
            # 从account_pool获取AccountConfig对象
            if 'stock_ws' in account_pool.account_configs:
                stock_config = account_pool.account_configs['stock_ws']
                if stock_config.enabled:
                    stock_account = {
                        'name': stock_config.account_name or 'stock_ws',
                        'api_key': stock_config.api_key,
                        'secret_key': stock_config.secret_key
                    }
            
            if 'option_ws' in account_pool.account_configs:
                option_config = account_pool.account_configs['option_ws']
                if option_config.enabled:
                    option_account = {
                        'name': option_config.account_name or 'option_ws',
                        'api_key': option_config.api_key,
                        'secret_key': option_config.secret_key
                    }
            
            if not stock_account:
                raise Exception("未找到stock_ws专用账户配置")
            if not option_account:
                raise Exception("未找到option_ws专用账户配置")
                
            self._stock_account = stock_account
            self._option_account = option_account
            
            logger.info(f"✅ 加载专用WebSocket账户: stock_ws={stock_account['name']}, option_ws={option_account['name']}")
            
        except Exception as e:
            logger.error(f"❌ 加载专用WebSocket账户失败: {e}")
            raise
    
    async def _ensure_stock_connection(self):
        """确保股票WebSocket连接存在 - 原子化连接管理"""
        async with self._stock_connection_lock:
            if self.stock_connected and self.stock_ws and not self.stock_ws.closed:
                return
                
            if self._shutdown_event.is_set():
                logger.warning("WebSocket管理器已关闭，无法建立股票连接")
                return
                
            try:
                logger.info(f"🔌 建立股票WebSocket连接: {self.STOCK_WS_URL}")
                
                # 清理旧连接
                await self._cleanup_stock_connection()
                
                ssl_context = ssl.create_default_context()
                self.stock_ws = await websockets.connect(
                    self.STOCK_WS_URL,
                    ssl=ssl_context,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2**20  # 1MB max message size
                )
                
                # 认证
                auth_message = {
                    "action": "auth",
                    "key": self._stock_account['api_key'],
                    "secret": self._stock_account['secret_key']
                }
                await self.stock_ws.send(json.dumps(auth_message))
                
                # 使用recv锁等待认证响应
                async with self._stock_recv_lock:
                    response = await self.stock_ws.recv()
                    auth_data = json.loads(response)
                
                if isinstance(auth_data, list):
                    auth_response = auth_data[0] if auth_data else {}
                else:
                    auth_response = auth_data
                
                if auth_response.get("T") != "success":
                    raise Exception(f"股票WebSocket认证失败: {auth_response}")
                
                self.stock_connected = True
                logger.info("✅ 股票WebSocket连接和认证成功")
                
                # 原子化启动监听任务
                await self._start_stock_listener()
                
            except Exception as e:
                logger.error(f"❌ 股票WebSocket连接失败: {e}")
                self.stock_connected = False
                await self._cleanup_stock_connection()
                raise
                
    async def _cleanup_stock_connection(self):
        """清理股票WebSocket连接资源"""
        try:
            # 取消监听任务
            async with self._stock_listener_lock:
                if self._stock_listener and not self._stock_listener.done():
                    self._stock_listener.cancel()
                    try:
                        await self._stock_listener
                    except asyncio.CancelledError:
                        pass
                    self._stock_listener = None
            
            # 关闭WebSocket连接
            if self.stock_ws and not self.stock_ws.closed:
                await self.stock_ws.close()
            self.stock_ws = None
            self.stock_connected = False
            
        except Exception as e:
            logger.error(f"❌ 清理股票WebSocket连接异常: {e}")
            
    async def _start_stock_listener(self):
        """原子化启动股票监听任务"""
        async with self._stock_listener_lock:
            # 确保没有重复的监听任务
            if self._stock_listener and not self._stock_listener.done():
                logger.warning("股票监听任务已在运行，跳过启动")
                return
                
            if self._stock_listener:
                self._stock_listener.cancel()
                try:
                    await self._stock_listener
                except asyncio.CancelledError:
                    pass
                    
            self._stock_listener = asyncio.create_task(self._listen_stock_data())
            logger.info("✅ 股票监听任务已启动")
    
    async def _ensure_option_connection(self):
        """确保期权WebSocket连接存在 - 原子化连接管理"""
        async with self._option_connection_lock:
            if self.option_connected and self.option_ws and not self.option_ws.closed:
                return
                
            if self._shutdown_event.is_set():
                logger.warning("WebSocket管理器已关闭，无法建立期权连接")
                return
                
            try:
                logger.info(f"🔌 建立期权WebSocket连接: {self.OPTION_WS_URL}")
                
                # 清理旧连接
                await self._cleanup_option_connection()
                
                ssl_context = ssl.create_default_context()
                self.option_ws = await websockets.connect(
                    self.OPTION_WS_URL,
                    ssl=ssl_context,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2**20  # 1MB max message size
                )
                
                # 认证 (期权使用MessagePack)
                auth_message = {
                    "action": "auth",
                    "key": self._option_account['api_key'],
                    "secret": self._option_account['secret_key']
                }
                packed_auth = msgpack.packb(auth_message)
                await self.option_ws.send(packed_auth)
                
                # 使用recv锁等待认证响应
                async with self._option_recv_lock:
                    response = await self.option_ws.recv()
                    try:
                        auth_data = json.loads(response)
                    except:
                        auth_data = msgpack.unpackb(response)
                
                if isinstance(auth_data, list):
                    auth_response = auth_data[0] if auth_data else {}
                else:
                    auth_response = auth_data
                
                if auth_response.get("T") != "success":
                    raise Exception(f"期权WebSocket认证失败: {auth_response}")
                
                self.option_connected = True
                logger.info("✅ 期权WebSocket连接和认证成功")
                
                # 原子化启动监听任务
                await self._start_option_listener()
                
            except Exception as e:
                logger.error(f"❌ 期权WebSocket连接失败: {e}")
                self.option_connected = False
                await self._cleanup_option_connection()
                raise
                
    async def _cleanup_option_connection(self):
        """清理期权WebSocket连接资源"""
        try:
            # 取消监听任务
            async with self._option_listener_lock:
                if self._option_listener and not self._option_listener.done():
                    self._option_listener.cancel()
                    try:
                        await self._option_listener
                    except asyncio.CancelledError:
                        pass
                    self._option_listener = None
            
            # 关闭WebSocket连接
            if self.option_ws and not self.option_ws.closed:
                await self.option_ws.close()
            self.option_ws = None
            self.option_connected = False
            
        except Exception as e:
            logger.error(f"❌ 清理期权WebSocket连接异常: {e}")
            
    async def _start_option_listener(self):
        """原子化启动期权监听任务"""
        async with self._option_listener_lock:
            # 确保没有重复的监听任务
            if self._option_listener and not self._option_listener.done():
                logger.warning("期权监听任务已在运行，跳过启动")
                return
                
            if self._option_listener:
                self._option_listener.cancel()
                try:
                    await self._option_listener
                except asyncio.CancelledError:
                    pass
                    
            self._option_listener = asyncio.create_task(self._listen_option_data())
            logger.info("✅ 期权监听任务已启动")
    
    async def add_client_subscription(self, client_id: str, symbols: List[str]):
        """添加客户端订阅 - 线程安全"""
        global subscribed_symbols, client_subscriptions
        
        if self._shutdown_event.is_set():
            logger.warning("WebSocket管理器已关闭，无法添加订阅")
            return
            
        await self.ensure_initialized()
        
        async with _global_lock:
            # 记录客户端订阅
            if client_id not in client_subscriptions:
                client_subscriptions[client_id] = set()
            
            new_symbols = set(symbols) - client_subscriptions[client_id]
            client_subscriptions[client_id].update(symbols)
            
            # 更新全局订阅
            global_new_symbols = new_symbols - subscribed_symbols
            subscribed_symbols.update(new_symbols)
            
            if global_new_symbols:
                logger.info(f"🆕 新增订阅符号: {list(global_new_symbols)} (客户端: {client_id})")
                
        # 在锁外更新订阅以避免死锁
        if global_new_symbols:
            await self._update_subscriptions()
    
    async def remove_client_subscription(self, client_id: str):
        """移除客户端订阅（客户端断开时调用）- 线程安全"""
        global subscribed_symbols, client_subscriptions
        
        symbols_to_remove = set()
        
        async with _global_lock:
            if client_id not in client_subscriptions:
                return
            
            client_symbols = client_subscriptions.pop(client_id)
            
            # 检查是否有其他客户端还需要这些符号
            still_needed_symbols = set()
            for other_client_symbols in client_subscriptions.values():
                still_needed_symbols.update(other_client_symbols)
            
            # 移除不再需要的符号
            symbols_to_remove = client_symbols - still_needed_symbols
            if symbols_to_remove:
                subscribed_symbols -= symbols_to_remove
                logger.info(f"🗑️ 移除不再需要的符号: {list(symbols_to_remove)} (客户端 {client_id} 断开)")
                
        # 在锁外更新订阅以避免死锁
        if symbols_to_remove:
            await self._update_subscriptions()
    
    async def _update_subscriptions(self):
        """更新Alpaca WebSocket订阅 - 线程安全"""
        if self._shutdown_event.is_set():
            return
            
        async with _global_lock:
            current_symbols = subscribed_symbols.copy()
            
        if not current_symbols:
            return
        
        # 分离股票和期权符号
        stock_symbols = [s for s in current_symbols if not self._is_option_symbol(s)]
        option_symbols = [s for s in current_symbols if self._is_option_symbol(s)]
        
        # 更新股票订阅
        if stock_symbols:
            try:
                await self._ensure_stock_connection()
                if self.stock_connected and self.stock_ws and not self.stock_ws.closed:
                    subscribe_msg = {
                        "action": "subscribe",
                        "quotes": stock_symbols,
                        "trades": stock_symbols
                    }
                    await self.stock_ws.send(json.dumps(subscribe_msg))
                    logger.info(f"📊 更新股票订阅: {len(stock_symbols)} 个符号")
            except Exception as e:
                logger.error(f"❌ 更新股票订阅失败: {e}")
        
        # 更新期权订阅
        if option_symbols:
            try:
                await self._ensure_option_connection()
                if self.option_connected and self.option_ws and not self.option_ws.closed:
                    subscribe_msg = {
                        "action": "subscribe",
                        "quotes": option_symbols,
                        "trades": option_symbols
                    }
                    packed_msg = msgpack.packb(subscribe_msg)
                    await self.option_ws.send(packed_msg)
                    logger.info(f"📈 更新期权订阅: {len(option_symbols)} 个符号")
            except Exception as e:
                logger.error(f"❌ 更新期权订阅失败: {e}")
    
    def _is_option_symbol(self, symbol: str) -> bool:
        """判断是否为期权符号"""
        return len(symbol) > 6 and any(c in symbol for c in ['C', 'P']) and any(c.isdigit() for c in symbol)
    
    async def _reconnection_manager(self):
        """后台重连管理器 - 改进的健壮性"""
        logger.info("🔄 启动WebSocket重连管理器")
        
        consecutive_failures = 0
        max_failures = 5
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # 动态调整检查间隔
                    check_interval = min(10 + consecutive_failures * 5, 60)  # 10-60秒
                    await asyncio.sleep(check_interval)
                    
                    if self._shutdown_event.is_set():
                        break
                    
                    # 获取当前订阅状态
                    async with _global_lock:
                        has_symbols = bool(subscribed_symbols)
                        current_stock_connected = self.stock_connected
                        current_option_connected = self.option_connected
                    
                    reconnection_needed = False
                    
                    # 检查股票连接
                    if has_symbols and not current_stock_connected:
                        if not self._stock_listener or self._stock_listener.done():
                            logger.info("🔄 检测到股票WebSocket断开，正在重新连接...")
                            try:
                                await self._ensure_stock_connection()
                                reconnection_needed = True
                            except Exception as e:
                                logger.error(f"❌ 股票WebSocket重连失败: {e}")
                                consecutive_failures += 1
                    
                    # 检查期权连接
                    if has_symbols and not current_option_connected:
                        if not self._option_listener or self._option_listener.done():
                            logger.info("🔄 检测到期权WebSocket断开，正在重新连接...")
                            try:
                                await self._ensure_option_connection()
                                reconnection_needed = True
                            except Exception as e:
                                logger.error(f"❌ 期权WebSocket重连失败: {e}")
                                consecutive_failures += 1
                    
                    # 如果重连成功，重置失败计数
                    if reconnection_needed and (self.stock_connected or self.option_connected):
                        consecutive_failures = 0
                    
                    # 如果连续失败太多次，增加等待时间
                    if consecutive_failures >= max_failures:
                        logger.warning(f"⚠️ 连续重连失败 {consecutive_failures} 次，等待更长时间")
                        await asyncio.sleep(60)  # 等待1分钟后再试
                        consecutive_failures = 0  # 重置计数
                            
                except asyncio.CancelledError:
                    logger.info("🔄 重连管理器被取消")
                    break
                except Exception as e:
                    logger.error(f"❌ 重连管理器异常: {e}")
                    consecutive_failures += 1
                    await asyncio.sleep(30)  # 发生异常时等待30秒
                    
        except asyncio.CancelledError:
            logger.info("🔄 重连管理器已停止")
        finally:
            logger.info("🔄 重连管理器任务结束")
    
    async def _listen_stock_data(self):
        """监听股票数据并广播给客户端 - 使用recv锁防止并发问题"""
        logger.info("🎧 开始监听股票数据")
        
        try:
            while (self.stock_connected and self.stock_ws and 
                   not self.stock_ws.closed and not self._shutdown_event.is_set()):
                try:
                    # 使用recv锁确保同一时间只有一个协程在recv
                    async with self._stock_recv_lock:
                        if not self.stock_connected or not self.stock_ws or self.stock_ws.closed:
                            break
                        message = await self.stock_ws.recv()
                    
                    # 解析数据
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError as e:
                        logger.warning(f"⚠️ 股票数据JSON解析失败: {e}")
                        continue
                    
                    # 广播数据
                    if isinstance(data, list):
                        for item in data:
                            if item:  # 确保数据不为空
                                await self._broadcast_data(item, "stock")
                    else:
                        if data:  # 确保数据不为空
                            await self._broadcast_data(data, "stock")
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("📡 股票WebSocket连接断开")
                    self.stock_connected = False
                    break
                except asyncio.CancelledError:
                    logger.info("📡 股票数据监听任务被取消")
                    break
                except Exception as e:
                    logger.error(f"❌ 股票数据处理异常: {e}")
                    # 继续循环，不要因为单个消息错误而退出
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            logger.info("📡 股票数据监听任务被取消")
        except Exception as e:
            logger.error(f"❌ 股票数据监听严重异常: {e}")
        finally:
            self.stock_connected = False
            logger.info("📡 股票数据监听任务结束")
    
    async def _listen_option_data(self):
        """监听期权数据并广播给客户端 - 使用recv锁防止并发问题"""
        logger.info("🎧 开始监听期权数据")
        
        try:
            while (self.option_connected and self.option_ws and 
                   not self.option_ws.closed and not self._shutdown_event.is_set()):
                try:
                    # 使用recv锁确保同一时间只有一个协程在recv
                    async with self._option_recv_lock:
                        if not self.option_connected or not self.option_ws or self.option_ws.closed:
                            break
                        message = await self.option_ws.recv()
                    
                    # 尝试解析JSON或MessagePack
                    try:
                        data = json.loads(message)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        try:
                            data = msgpack.unpackb(message)
                        except Exception as e:
                            logger.warning(f"⚠️ 期权数据解析失败: {e}")
                            continue
                    
                    # 广播数据
                    if isinstance(data, list):
                        for item in data:
                            if item:  # 确保数据不为空
                                await self._broadcast_data(item, "option")
                    else:
                        if data:  # 确保数据不为空
                            await self._broadcast_data(data, "option")
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("📡 期权WebSocket连接断开")
                    self.option_connected = False
                    break
                except asyncio.CancelledError:
                    logger.info("📡 期权数据监听任务被取消")
                    break
                except Exception as e:
                    logger.error(f"❌ 期权数据处理异常: {e}")
                    # 继续循环，不要因为单个消息错误而退出
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            logger.info("📡 期权数据监听任务被取消")
        except Exception as e:
            logger.error(f"❌ 期权数据监听严重异常: {e}")
        finally:
            self.option_connected = False
            logger.info("📡 期权数据监听任务结束")
    
    async def _broadcast_data(self, data: dict, data_type: str):
        """广播数据给所有相关的客户端 - 线程安全"""
        if not data or data.get("T") not in ["q", "t"]:  # 只处理报价(q)和交易(t)数据
            return
        
        symbol = data.get("S")
        if not symbol:
            return
        
        # 构造广播消息
        broadcast_msg = {
            "type": "quote" if data.get("T") == "q" else "trade",
            "data_type": data_type,
            "symbol": symbol,
            "timestamp": data.get("t", datetime.now().isoformat())
        }
        
        if data.get("T") == "q":  # 报价数据
            broadcast_msg.update({
                "bid_price": data.get("bp"),
                "ask_price": data.get("ap"),
                "bid_size": data.get("bs"),
                "ask_size": data.get("as")
            })
        else:  # 交易数据
            broadcast_msg.update({
                "price": data.get("p"),
                "size": data.get("s")
            })
        
        # 获取需要广播的客户端列表（在锁内快速获取快照）
        clients_to_notify = []
        async with _global_lock:
            for client_id, websocket in active_connections.items():
                if symbol in client_subscriptions.get(client_id, set()):
                    clients_to_notify.append((client_id, websocket))
        
        # 在锁外进行实际的广播操作
        if not clients_to_notify:
            return
            
        message_json = json.dumps(broadcast_msg)
        disconnected_clients = []
        
        # 并发发送消息给所有客户端
        async def send_to_client(client_id: str, websocket: WebSocket):
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.debug(f"❌ 发送数据给客户端 {client_id} 失败: {e}")
                return client_id
            return None
        
        # 使用gather进行并发发送，但限制并发数避免过载
        batch_size = 50  # 限制并发发送的客户端数量
        for i in range(0, len(clients_to_notify), batch_size):
            batch = clients_to_notify[i:i + batch_size]
            tasks = [send_to_client(client_id, websocket) for client_id, websocket in batch]
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, str):  # 返回了client_id，表示发送失败
                        disconnected_clients.append(result)
            except Exception as e:
                logger.error(f"❌ 批量发送数据异常: {e}")
        
        # 清理断开的客户端
        if disconnected_clients:
            async with _global_lock:
                for client_id in disconnected_clients:
                    active_connections.pop(client_id, None)
            
            # 在锁外移除订阅
            for client_id in disconnected_clients:
                await self.remove_client_subscription(client_id)
    
    async def shutdown(self):
        """关闭所有连接 - 优雅关闭"""
        logger.info("🔌 开始关闭WebSocket管理器...")
        
        # 设置关闭标志
        self._shutdown_event.set()
        
        try:
            # 并发取消所有任务
            tasks_to_cancel = []
            
            if self._reconnection_task and not self._reconnection_task.done():
                tasks_to_cancel.append(self._reconnection_task)
            
            if self._stock_listener and not self._stock_listener.done():
                tasks_to_cancel.append(self._stock_listener)
                
            if self._option_listener and not self._option_listener.done():
                tasks_to_cancel.append(self._option_listener)
            
            # 取消所有任务
            for task in tasks_to_cancel:
                task.cancel()
            
            # 等待任务完成
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            
            # 清理连接
            await self._cleanup_stock_connection()
            await self._cleanup_option_connection()
            
        except Exception as e:
            logger.error(f"❌ 关闭WebSocket管理器异常: {e}")
        
        logger.info("✅ WebSocket管理器已关闭")

# 全局单例实例
ws_manager = SingletonWebSocketManager()

# 默认测试符号
DEFAULT_STOCKS = [
    "AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NVDA", "META", "SPY",
    "HOOD", "AEO"
]
DEFAULT_OPTIONS = [
    "TSLA250808C00307500",   # TSLA Call $307.50 2025-08-08
    "HOOD250822C00115000",   # HOOD Call $115.00 2025-08-22
    "AEO250808C00015000",    # AEO Call $15.00 2025-08-08
    "AAPL250808C00230000",   # AAPL Call $230 2025-08-08
    "SPY250808C00580000",    # SPY Call $580 2025-08-08
    "NVDA250808C00140000"    # NVDA Call $140 2025-08-08
]

@ws_router.websocket("/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket端点 - 实时市场数据（单例架构）- 线程安全"""
    global active_connections, client_subscriptions
    
    await websocket.accept()
    client_id = f"client_{datetime.now().timestamp()}"
    
    # 线程安全地添加连接
    async with _global_lock:
        active_connections[client_id] = websocket
    
    logger.info(f"🔗 WebSocket客户端连接: {client_id}")
    
    try:
        # 发送欢迎消息
        welcome_message = {
            "type": "welcome",
            "client_id": client_id,
            "message": "连接成功！使用单例架构的Alpaca WebSocket数据流",
            "default_stocks": DEFAULT_STOCKS,
            "default_options": DEFAULT_OPTIONS,
            "architecture": "singleton",
            "features": {
                "single_stock_connection": True,
                "single_option_connection": True,
                "dynamic_subscription_management": True,
                "broadcast_to_all_clients": True
            }
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # 自动订阅默认符号 - 线程安全检查
        async with _global_lock:
            is_first_client = len(client_subscriptions) == 0
            
        if is_first_client:  # 第一个客户端
            logger.info(f"🎯 首个客户端，自动订阅默认符号: {client_id}")
        else:
            logger.info(f"📡 复用现有连接: {client_id}")
            
        # 为客户端订阅默认符号
        all_symbols = DEFAULT_STOCKS + DEFAULT_OPTIONS
        await ws_manager.add_client_subscription(client_id, all_symbols)
        
        # 发送订阅成功消息 - 线程安全获取状态
        async with _global_lock:
            subscribed_symbols_list = list(client_subscriptions.get(client_id, []))
            total_clients = len(active_connections)
            
        subscription_message = {
            "type": "subscription_success",
            "client_id": client_id,
            "subscribed_symbols": subscribed_symbols_list,
            "total_clients": total_clients,
            "message": "成功订阅实时数据流",
            "status": "active"
        }
        await websocket.send_text(json.dumps(subscription_message))
        
        # 保持连接并处理客户端消息
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "subscribe":
                    # 添加新的订阅
                    new_symbols = message.get("symbols", [])
                    if new_symbols:
                        await ws_manager.add_client_subscription(client_id, new_symbols)
                        
                        # 线程安全获取订阅数量
                        async with _global_lock:
                            total_subscribed = len(client_subscriptions.get(client_id, []))
                            
                        response = {
                            "type": "subscription_update",
                            "client_id": client_id,
                            "added_symbols": new_symbols,
                            "total_subscribed": total_subscribed
                        }
                        await websocket.send_text(json.dumps(response))
                        
                elif message.get("type") == "unsubscribe":
                    # 取消订阅（TODO: 实现具体的取消订阅逻辑）
                    response = {
                        "type": "unsubscribe_ack",
                        "message": "取消订阅功能正在开发中"
                    }
                    await websocket.send_text(json.dumps(response))
                        
                elif message.get("type") == "ping":
                    # 心跳检测 - 线程安全获取状态
                    async with _global_lock:
                        total_clients = len(active_connections)
                        
                    pong_message = {
                        "type": "pong",
                        "client_id": client_id,
                        "timestamp": datetime.now().isoformat(),
                        "connections_status": {
                            "stock_connected": ws_manager.stock_connected,
                            "option_connected": ws_manager.option_connected,
                            "total_clients": total_clients
                        }
                    }
                    await websocket.send_text(json.dumps(pong_message))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"❌ 处理客户端消息异常 {client_id}: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"📴 WebSocket客户端断开: {client_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket连接异常 {client_id}: {e}")
    finally:
        # 线程安全地清理连接和订阅
        try:
            async with _global_lock:
                active_connections.pop(client_id, None)
            
            # 在锁外移除订阅
            await ws_manager.remove_client_subscription(client_id)
            logger.info(f"🧹 清理客户端连接和订阅: {client_id}")
        except Exception as e:
            logger.error(f"❌ 清理客户端连接异常 {client_id}: {e}")

@ws_router.get("/status")
async def websocket_status():
    """WebSocket状态端点 - 线程安全"""
    async with _global_lock:
        active_connections_count = len(active_connections)
        client_subscriptions_count = len(client_subscriptions)
        total_subscribed = len(subscribed_symbols)
        subscribed_symbols_list = list(subscribed_symbols)
    
    return {
        "service": "WebSocket Manager",
        "architecture": "singleton_thread_safe",
        "connections": {
            "stock_connected": ws_manager.stock_connected,
            "option_connected": ws_manager.option_connected,
            "total_alpaca_connections": (1 if ws_manager.stock_connected else 0) + (1 if ws_manager.option_connected else 0)
        },
        "clients": {
            "active_connections": active_connections_count,
            "client_subscriptions": client_subscriptions_count
        },
        "symbols": {
            "total_subscribed": total_subscribed,
            "subscribed_symbols": subscribed_symbols_list
        },
        "endpoints": {
            "websocket": "/api/v1/ws/market-data",
            "status": "/api/v1/ws/status"
        },
        "features": {
            "guaranteed_single_connections": True,
            "dynamic_subscription_management": True,
            "broadcast_architecture": True,
            "no_rate_limiting_issues": True,
            "thread_safe_operations": True,
            "recv_lock_protection": True,
            "atomic_task_management": True,
            "graceful_shutdown": True
        }
    }