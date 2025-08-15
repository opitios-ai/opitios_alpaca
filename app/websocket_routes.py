"""
WebSocket路由 - 使用单例管理器，确保架构正确
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import websockets
import msgpack
import ssl
from typing import Dict, List, Set, Optional
from datetime import datetime
from loguru import logger

from config import settings

# WebSocket路由
ws_router = APIRouter(prefix="/ws", tags=["websocket"])

# 全局订阅符号和客户端连接
subscribed_symbols: Set[str] = set()
active_connections: Dict[str, WebSocket] = {}
client_subscriptions: Dict[str, Set[str]] = {}  # 每个客户端订阅的符号

class SingletonWebSocketManager:
    """
    单例WebSocket管理器 - 确保整个应用只有1个股票WS + 1个期权WS连接
    """
    
    _instance = None
    _initialized = False
    
    # Alpaca官方端点
    STOCK_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"
    OPTION_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/indicative"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # WebSocket连接
        self.stock_ws = None
        self.option_ws = None
        self.stock_connected = False
        self.option_connected = False
        
        # 专用账户
        self._stock_account = None
        self._option_account = None
        
        # 监听任务
        self._stock_listener = None
        self._option_listener = None
        
        # 初始化锁
        self._init_lock = asyncio.Lock()
        
        self._initialized = True
        
    async def ensure_initialized(self):
        """确保WebSocket管理器已初始化"""
        async with self._init_lock:
            if not self._stock_account or not self._option_account:
                await self._load_dedicated_accounts()
                
            # 如果连接断开，重新连接
            if not self.stock_connected and subscribed_symbols:
                await self._ensure_stock_connection()
            if not self.option_connected and subscribed_symbols:
                await self._ensure_option_connection()
    
    async def _load_dedicated_accounts(self):
        """加载专用WebSocket账户"""
        try:
            # 获取专用股票WebSocket账户
            stock_account = None
            option_account = None
            
            for username, account in settings.accounts.items():
                if username == "stock_ws":
                    stock_account = {
                        'name': username,
                        'api_key': account.api_key,
                        'secret_key': account.secret_key
                    }
                elif username == "option_ws":
                    option_account = {
                        'name': username,
                        'api_key': account.api_key,
                        'secret_key': account.secret_key
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
        """确保股票WebSocket连接存在"""
        if self.stock_connected:
            return
            
        try:
            logger.info(f"🔌 建立股票WebSocket连接: {self.STOCK_WS_URL}")
            
            ssl_context = ssl.create_default_context()
            self.stock_ws = await websockets.connect(
                self.STOCK_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            # 认证
            auth_message = {
                "action": "auth",
                "key": self._stock_account['api_key'],
                "secret": self._stock_account['secret_key']
            }
            await self.stock_ws.send(json.dumps(auth_message))
            
            # 等待认证响应
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
            
            # 启动监听任务
            if self._stock_listener:
                self._stock_listener.cancel()
            self._stock_listener = asyncio.create_task(self._listen_stock_data())
            
        except Exception as e:
            logger.error(f"❌ 股票WebSocket连接失败: {e}")
            self.stock_connected = False
            raise
    
    async def _ensure_option_connection(self):
        """确保期权WebSocket连接存在"""
        if self.option_connected:
            return
            
        try:
            logger.info(f"🔌 建立期权WebSocket连接: {self.OPTION_WS_URL}")
            
            ssl_context = ssl.create_default_context()
            self.option_ws = await websockets.connect(
                self.OPTION_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            # 认证 (期权使用MessagePack)
            auth_message = {
                "action": "auth",
                "key": self._option_account['api_key'],
                "secret": self._option_account['secret_key']
            }
            packed_auth = msgpack.packb(auth_message)
            await self.option_ws.send(packed_auth)
            
            # 等待认证响应
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
            
            # 启动监听任务
            if self._option_listener:
                self._option_listener.cancel()
            self._option_listener = asyncio.create_task(self._listen_option_data())
            
        except Exception as e:
            logger.error(f"❌ 期权WebSocket连接失败: {e}")
            self.option_connected = False
            raise
    
    async def add_client_subscription(self, client_id: str, symbols: List[str]):
        """添加客户端订阅"""
        await self.ensure_initialized()
        
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
            await self._update_subscriptions()
    
    async def remove_client_subscription(self, client_id: str):
        """移除客户端订阅（客户端断开时调用）"""
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
            await self._update_subscriptions()
    
    async def _update_subscriptions(self):
        """更新Alpaca WebSocket订阅"""
        if not subscribed_symbols:
            return
        
        # 分离股票和期权符号
        stock_symbols = [s for s in subscribed_symbols if not self._is_option_symbol(s)]
        option_symbols = [s for s in subscribed_symbols if self._is_option_symbol(s)]
        
        # 更新股票订阅
        if stock_symbols:
            await self._ensure_stock_connection()
            if self.stock_connected and self.stock_ws:
                subscribe_msg = {
                    "action": "subscribe",
                    "quotes": stock_symbols,
                    "trades": stock_symbols
                }
                await self.stock_ws.send(json.dumps(subscribe_msg))
                logger.info(f"📊 更新股票订阅: {len(stock_symbols)} 个符号")
        
        # 更新期权订阅
        if option_symbols:
            await self._ensure_option_connection()
            if self.option_connected and self.option_ws:
                subscribe_msg = {
                    "action": "subscribe",
                    "quotes": option_symbols,
                    "trades": option_symbols
                }
                packed_msg = msgpack.packb(subscribe_msg)
                await self.option_ws.send(packed_msg)
                logger.info(f"📈 更新期权订阅: {len(option_symbols)} 个符号")
    
    def _is_option_symbol(self, symbol: str) -> bool:
        """判断是否为期权符号"""
        return len(symbol) > 6 and any(c in symbol for c in ['C', 'P']) and any(c.isdigit() for c in symbol)
    
    async def _listen_stock_data(self):
        """监听股票数据并广播给客户端"""
        try:
            while self.stock_connected and self.stock_ws:
                try:
                    message = await self.stock_ws.recv()
                    data = json.loads(message)
                    
                    if isinstance(data, list):
                        for item in data:
                            await self._broadcast_data(item, "stock")
                    else:
                        await self._broadcast_data(data, "stock")
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("📡 股票WebSocket连接断开，尝试重连")
                    self.stock_connected = False
                    await asyncio.sleep(5)
                    await self._ensure_stock_connection()
                    
        except Exception as e:
            logger.error(f"❌ 股票数据监听异常: {e}")
            self.stock_connected = False
    
    async def _listen_option_data(self):
        """监听期权数据并广播给客户端"""
        try:
            while self.option_connected and self.option_ws:
                try:
                    message = await self.option_ws.recv()
                    
                    # 尝试解析JSON或MessagePack
                    try:
                        data = json.loads(message)
                    except:
                        data = msgpack.unpackb(message)
                    
                    if isinstance(data, list):
                        for item in data:
                            await self._broadcast_data(item, "option")
                    else:
                        await self._broadcast_data(data, "option")
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("📡 期权WebSocket连接断开，尝试重连")
                    self.option_connected = False
                    await asyncio.sleep(5)
                    await self._ensure_option_connection()
                    
        except Exception as e:
            logger.error(f"❌ 期权数据监听异常: {e}")
            self.option_connected = False
    
    async def _broadcast_data(self, data: dict, data_type: str):
        """广播数据给所有相关的客户端"""
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
        
        # 广播给所有订阅了该符号的客户端
        message_json = json.dumps(broadcast_msg)
        disconnected_clients = []
        
        for client_id, websocket in active_connections.items():
            if symbol in client_subscriptions.get(client_id, set()):
                try:
                    await websocket.send_text(message_json)
                except:
                    disconnected_clients.append(client_id)
        
        # 清理断开的客户端
        for client_id in disconnected_clients:
            active_connections.pop(client_id, None)
            await self.remove_client_subscription(client_id)
    
    async def shutdown(self):
        """关闭所有连接"""
        logger.info("🔌 关闭WebSocket管理器...")
        
        if self._stock_listener:
            self._stock_listener.cancel()
        if self._option_listener:
            self._option_listener.cancel()
        
        if self.stock_ws:
            await self.stock_ws.close()
            self.stock_connected = False
        
        if self.option_ws:
            await self.option_ws.close()
            self.option_connected = False
        
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
    """WebSocket端点 - 实时市场数据（单例架构）"""
    await websocket.accept()
    client_id = f"client_{datetime.now().timestamp()}"
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
        
        # 自动订阅默认符号（仅在首次连接时）
        if len(client_subscriptions) == 0:  # 第一个客户端
            logger.info(f"🎯 首个客户端，自动订阅默认符号: {client_id}")
            all_symbols = DEFAULT_STOCKS + DEFAULT_OPTIONS
            await ws_manager.add_client_subscription(client_id, all_symbols)
        else:
            logger.info(f"📡 复用现有连接: {client_id}")
            # 为新客户端也订阅默认符号
            all_symbols = DEFAULT_STOCKS + DEFAULT_OPTIONS
            await ws_manager.add_client_subscription(client_id, all_symbols)
        
        # 发送订阅成功消息
        subscription_message = {
            "type": "subscription_success",
            "client_id": client_id,
            "subscribed_symbols": list(client_subscriptions.get(client_id, [])),
            "total_clients": len(active_connections),
            "message": f"成功订阅实时数据流",
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
                        
                        response = {
                            "type": "subscription_update",
                            "client_id": client_id,
                            "added_symbols": new_symbols,
                            "total_subscribed": len(client_subscriptions.get(client_id, []))
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
                    # 心跳检测
                    pong_message = {
                        "type": "pong",
                        "client_id": client_id,
                        "timestamp": datetime.now().isoformat(),
                        "connections_status": {
                            "stock_connected": ws_manager.stock_connected,
                            "option_connected": ws_manager.option_connected,
                            "total_clients": len(active_connections)
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
        # 清理连接和订阅
        active_connections.pop(client_id, None)
        await ws_manager.remove_client_subscription(client_id)
        logger.info(f"🧹 清理客户端连接和订阅: {client_id}")

@ws_router.get("/status")
async def websocket_status():
    """WebSocket状态端点"""
    return {
        "service": "WebSocket Manager",
        "architecture": "singleton",
        "connections": {
            "stock_connected": ws_manager.stock_connected,
            "option_connected": ws_manager.option_connected,
            "total_alpaca_connections": (1 if ws_manager.stock_connected else 0) + (1 if ws_manager.option_connected else 0)
        },
        "clients": {
            "active_connections": len(active_connections),
            "client_subscriptions": len(client_subscriptions)
        },
        "symbols": {
            "total_subscribed": len(subscribed_symbols),
            "subscribed_symbols": list(subscribed_symbols)
        },
        "endpoints": {
            "websocket": "/api/v1/ws/market-data",
            "status": "/api/v1/ws/status"
        },
        "features": {
            "guaranteed_single_connections": True,
            "dynamic_subscription_management": True,
            "broadcast_architecture": True,
            "no_rate_limiting_issues": True
        }
    }