"""
修复的WebSocket路由 - 智能回退到可用端点
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import asyncio
import websockets
import ssl
import time
from datetime import datetime
from loguru import logger
import yaml

# WebSocket路由
ws_router = APIRouter(prefix="/ws", tags=["websocket"])

# 活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}

# Alpaca WebSocket端点配置
WEBSOCKET_ENDPOINTS = {
    'test': {
        'url': 'wss://stream.data.alpaca.markets/v2/test',
        'symbols': ['FAKEPACA'],
        'description': '测试端点 - 免费可用，提供模拟数据'
    },
    'stock_iex': {
        'url': 'wss://stream.data.alpaca.markets/v2/iex',
        'symbols': ['AAPL', 'TSLA', 'GOOGL', 'MSFT'],
        'description': 'IEX股票数据 - 需要市场数据订阅'
    },
    'trading': {
        'url': 'wss://paper-api.alpaca.markets/stream',
        'symbols': [],
        'description': '交易更新 - 订单和账户变化'
    }
}

class SmartWebSocketManager:
    """智能WebSocket管理器 - 自动选择可用端点"""
    
    def __init__(self):
        self.api_key = None
        self.secret_key = None
        self.connections = {}
        self.subscribers = []
        self.connected = False
        self._shutdown = False
        
    async def initialize(self, api_key: str, secret_key: str):
        """初始化管理器"""
        self.api_key = api_key
        self.secret_key = secret_key
        
        logger.info("🚀 初始化智能WebSocket管理器...")
        
        # 尝试连接可用端点
        success_count = 0
        
        # 1. 首先尝试测试端点（总是可用）
        try:
            await self._connect_test_endpoint()
            success_count += 1
            logger.info("✅ 测试端点连接成功")
        except Exception as e:
            logger.error(f"❌ 测试端点连接失败: {e}")
        
        # 2. 尝试交易端点
        try:
            await self._connect_trading_endpoint()
            success_count += 1
            logger.info("✅ 交易端点连接成功")
        except Exception as e:
            logger.warning(f"⚠️ 交易端点连接失败: {e}")
        
        # 3. 尝试股票端点（可能失败）
        try:
            await self._connect_stock_endpoint()
            success_count += 1
            logger.info("✅ 股票端点连接成功")
        except Exception as e:
            logger.warning(f"⚠️ 股票端点连接失败: {e}")
        
        if success_count > 0:
            self.connected = True
            logger.info(f"🎉 WebSocket管理器初始化成功，{success_count}个端点可用")
        else:
            logger.error("❌ 所有WebSocket端点连接失败")
            raise Exception("无法连接到任何WebSocket端点")
    
    async def _connect_test_endpoint(self):
        """连接测试端点"""
        endpoint_info = WEBSOCKET_ENDPOINTS['test']
        
        ssl_context = ssl.create_default_context()
        ws = await websockets.connect(
            endpoint_info['url'],
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=10
        )
        
        # 等待欢迎消息
        welcome_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        welcome_data = json.loads(welcome_msg)
        
        # 认证
        auth_message = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.secret_key
        }
        await ws.send(json.dumps(auth_message))
        
        # 等待认证响应
        auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
        auth_data = json.loads(auth_response)
        
        auth_result = auth_data[0] if isinstance(auth_data, list) else auth_data
        if auth_result.get("T") != "success":
            raise Exception(f"测试端点认证失败: {auth_result}")
        
        # 订阅测试数据
        subscribe_msg = {
            "action": "subscribe",
            "trades": ["FAKEPACA"],
            "quotes": ["FAKEPACA"],
            "bars": ["FAKEPACA"]
        }
        await ws.send(json.dumps(subscribe_msg))
        
        # 存储连接
        self.connections['test'] = {
            'ws': ws,
            'info': endpoint_info,
            'connected': True
        }
        
        # 启动监听任务
        asyncio.create_task(self._listen_endpoint('test'))
        
        logger.info("✅ 测试端点已连接并订阅FAKEPACA")
    
    async def _connect_trading_endpoint(self):
        """连接交易端点"""
        endpoint_info = WEBSOCKET_ENDPOINTS['trading']
        
        ssl_context = ssl.create_default_context()
        ws = await websockets.connect(
            endpoint_info['url'],
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=10
        )
        
        # 认证（交易端点不发送欢迎消息）
        auth_message = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.secret_key
        }
        await ws.send(json.dumps(auth_message))
        
        # 等待认证响应
        auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
        auth_data = json.loads(auth_response)
        
        if not (auth_data.get('stream') == 'authorization' and 
                auth_data.get('data', {}).get('status') == 'authorized'):
            raise Exception(f"交易端点认证失败: {auth_data}")
        
        # 订阅交易更新
        listen_msg = {
            "action": "listen",
            "data": {
                "streams": ["trade_updates"]
            }
        }
        await ws.send(json.dumps(listen_msg))
        
        # 存储连接
        self.connections['trading'] = {
            'ws': ws,
            'info': endpoint_info,
            'connected': True
        }
        
        # 启动监听任务
        asyncio.create_task(self._listen_endpoint('trading'))
        
        logger.info("✅ 交易端点已连接并订阅交易更新")
    
    async def _connect_stock_endpoint(self):
        """尝试连接股票端点"""
        endpoint_info = WEBSOCKET_ENDPOINTS['stock_iex']
        
        ssl_context = ssl.create_default_context()
        ws = await websockets.connect(
            endpoint_info['url'],
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=10
        )
        
        # 等待欢迎消息
        welcome_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        welcome_data = json.loads(welcome_msg)
        
        # 认证
        auth_message = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.secret_key
        }
        await ws.send(json.dumps(auth_message))
        
        # 等待认证响应
        auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
        auth_data = json.loads(auth_response)
        
        auth_result = auth_data[0] if isinstance(auth_data, list) else auth_data
        if auth_result.get("T") == "error":
            error_code = auth_result.get("code")
            if error_code in [406, 409]:  # 连接超限或订阅不足
                raise Exception(f"股票端点不可用: {auth_result.get('msg')}")
        elif auth_result.get("T") != "success":
            raise Exception(f"股票端点认证失败: {auth_result}")
        
        # 订阅股票数据
        subscribe_msg = {
            "action": "subscribe",
            "quotes": ["AAPL", "TSLA"],  # 限制符号数量
            "trades": ["AAPL", "TSLA"]
        }
        await ws.send(json.dumps(subscribe_msg))
        
        # 存储连接
        self.connections['stock_iex'] = {
            'ws': ws,
            'info': endpoint_info,
            'connected': True
        }
        
        # 启动监听任务
        asyncio.create_task(self._listen_endpoint('stock_iex'))
        
        logger.info("✅ 股票端点已连接并订阅AAPL, TSLA")
    
    async def _listen_endpoint(self, endpoint_name: str):
        """监听端点消息"""
        connection = self.connections[endpoint_name]
        ws = connection['ws']
        
        logger.info(f"👂 开始监听端点: {endpoint_name}")
        
        try:
            while connection['connected'] and not self._shutdown:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    await self._process_message(endpoint_name, message)
                except asyncio.TimeoutError:
                    logger.debug(f"端点 {endpoint_name} 接收超时")
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"端点 {endpoint_name} 连接关闭")
                    break
        except Exception as e:
            logger.error(f"端点 {endpoint_name} 监听错误: {e}")
        finally:
            connection['connected'] = False
            logger.info(f"端点 {endpoint_name} 监听结束")
    
    async def _process_message(self, endpoint_name: str, message):
        """处理消息"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = json.loads(message.decode('utf-8'))
            
            if endpoint_name == 'trading':
                await self._handle_trading_message(data)
            else:
                # 市场数据消息
                if isinstance(data, list):
                    for item in data:
                        await self._handle_market_data_message(endpoint_name, item)
                else:
                    await self._handle_market_data_message(endpoint_name, data)
                    
        except Exception as e:
            logger.error(f"处理消息错误 [{endpoint_name}]: {e}")
    
    async def _handle_trading_message(self, data: dict):
        """处理交易消息"""
        stream = data.get('stream')
        if stream == 'trade_updates':
            trade_data = data.get('data', {})
            event = trade_data.get('event')
            order = trade_data.get('order', {})
            
            message = {
                "type": "trade_update",
                "source": "trading",
                "event": event,
                "symbol": order.get('symbol'),
                "side": order.get('side'),
                "qty": order.get('qty'),
                "status": order.get('status'),
                "timestamp": datetime.now().isoformat()
            }
            
            await self._broadcast_message(message)
            logger.info(f"📈 交易更新: {event} - {order.get('symbol')} {order.get('side')} {order.get('qty')}")
        elif stream == 'listening':
            logger.info(f"✅ 交易监听确认: {data}")
    
    async def _handle_market_data_message(self, endpoint_name: str, data: dict):
        """处理市场数据消息"""
        msg_type = data.get("T")
        
        if msg_type == "q":  # Quote data
            message = {
                "type": "quote",
                "source": endpoint_name,
                "symbol": data.get("S"),
                "bid_price": data.get("bp"),
                "ask_price": data.get("ap"),
                "bid_size": data.get("bs"),
                "ask_size": data.get("as"),
                "timestamp": data.get("t") or datetime.now().isoformat()
            }
            await self._broadcast_message(message)
            
        elif msg_type == "t":  # Trade data
            message = {
                "type": "trade",
                "source": endpoint_name,
                "symbol": data.get("S"),
                "price": data.get("p"),
                "size": data.get("s"),
                "timestamp": data.get("t") or datetime.now().isoformat()
            }
            await self._broadcast_message(message)
            
        elif msg_type == "b":  # Bar data
            message = {
                "type": "bar",
                "source": endpoint_name,
                "symbol": data.get("S"),
                "open": data.get("o"),
                "high": data.get("h"),
                "low": data.get("l"),
                "close": data.get("c"),
                "volume": data.get("v"),
                "timestamp": data.get("t") or datetime.now().isoformat()
            }
            await self._broadcast_message(message)
            
        elif msg_type in ["success", "subscription"]:
            logger.info(f"✅ {endpoint_name} 状态消息: {data}")
        elif msg_type == "error":
            logger.error(f"❌ {endpoint_name} 错误消息: {data}")
    
    async def _broadcast_message(self, message: dict):
        """广播消息给所有订阅者"""
        if active_connections:
            message_json = json.dumps(message)
            disconnected = []
            
            for connection_id, websocket in active_connections.items():
                try:
                    await websocket.send_text(message_json)
                except Exception as e:
                    logger.error(f"发送消息到客户端 {connection_id} 失败: {e}")
                    disconnected.append(connection_id)
            
            # 清理断开的连接
            for connection_id in disconnected:
                active_connections.pop(connection_id, None)
    
    async def get_status(self) -> dict:
        """获取连接状态"""
        status = {
            "connected": self.connected,
            "active_endpoints": len([c for c in self.connections.values() if c['connected']]),
            "subscribers": len(active_connections),
            "endpoints": {}
        }
        
        for name, connection in self.connections.items():
            status["endpoints"][name] = {
                "connected": connection['connected'],
                "description": connection['info']['description']
            }
        
        return status
    
    async def shutdown(self):
        """关闭所有连接"""
        logger.info("🛑 关闭WebSocket管理器...")
        self._shutdown = True
        
        for name, connection in self.connections.items():
            if connection['connected']:
                try:
                    await connection['ws'].close()
                    connection['connected'] = False
                    logger.info(f"✅ 已关闭端点: {name}")
                except Exception as e:
                    logger.error(f"关闭端点 {name} 失败: {e}")
        
        logger.info("✅ WebSocket管理器已关闭")

# 全局WebSocket管理器实例
smart_ws_manager = SmartWebSocketManager()

def load_api_credentials():
    """加载API凭证"""
    try:
        with open('secrets.yml', 'r') as f:
            config = yaml.safe_load(f)
        
        # 获取第一个启用的账户
        accounts = config.get('accounts', {})
        for account_id, account_config in accounts.items():
            if account_config.get('enabled', False):
                return account_config['api_key'], account_config['secret_key']
        
        # 回退到传统配置
        alpaca_config = config.get('alpaca', {})
        if alpaca_config.get('api_key') and alpaca_config.get('secret_key'):
            return alpaca_config['api_key'], alpaca_config['secret_key']
        
        raise Exception("未找到有效的API凭证")
        
    except Exception as e:
        logger.error(f"加载API凭证失败: {e}")
        raise e

@ws_router.websocket("/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket端点 - 智能市场数据流"""
    connection_id = f"ws_{int(time.time() * 1000)}"
    
    try:
        await websocket.accept()
        active_connections[connection_id] = websocket
        logger.info(f"✅ WebSocket连接已建立: {connection_id}")
        
        # 初始化WebSocket管理器
        if not smart_ws_manager.connected:
            try:
                api_key, secret_key = load_api_credentials()
                await smart_ws_manager.initialize(api_key, secret_key)
            except Exception as e:
                logger.error(f"WebSocket管理器初始化失败: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"WebSocket初始化失败: {str(e)}",
                    "suggestion": "请检查API密钥配置或网络连接",
                    "timestamp": datetime.now().isoformat()
                }))
        
        # 发送欢迎消息
        status = await smart_ws_manager.get_status()
        welcome_message = {
            "type": "welcome",
            "message": "已连接到智能Alpaca WebSocket数据流",
            "connection_id": connection_id,
            "status": status,
            "available_data": {
                "test_data": "FAKEPACA - 模拟股票数据（免费）",
                "trading_updates": "订单和账户更新",
                "real_stock_data": "真实股票数据（需要订阅）"
            },
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # 保持连接活跃
        while True:
            try:
                # 等待客户端消息或超时
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    message = json.loads(data)
                    await handle_websocket_message(websocket, message, connection_id)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "无效的JSON格式",
                        "timestamp": datetime.now().isoformat()
                    }))
                    
            except asyncio.TimeoutError:
                # 发送心跳包
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(ping_message))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket连接错误 {connection_id}: {e}")
    finally:
        # 清理连接
        active_connections.pop(connection_id, None)
        logger.info(f"WebSocket连接已清理: {connection_id}")

async def handle_websocket_message(websocket: WebSocket, message: dict, connection_id: str):
    """处理WebSocket消息"""
    message_type = message.get("type")
    
    if message_type == "ping":
        # 响应心跳包
        pong_message = {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(pong_message))
        
    elif message_type == "status":
        # 返回连接状态
        status = await smart_ws_manager.get_status()
        status_message = {
            "type": "status_response",
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(status_message))
        
    else:
        # 未知消息类型
        error_response = {
            "type": "error",
            "message": f"未知消息类型: {message_type}",
            "supported_types": ["ping", "status"],
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(error_response))

@ws_router.get("/status")
async def websocket_status():
    """获取WebSocket连接状态"""
    if smart_ws_manager.connected:
        status = await smart_ws_manager.get_status()
    else:
        status = {"connected": False, "message": "WebSocket管理器未初始化"}
    
    return {
        "websocket_manager": status,
        "active_client_connections": len(active_connections),
        "websocket_endpoint": "/api/v1/ws/market-data",
        "available_endpoints": WEBSOCKET_ENDPOINTS,
        "connection_info": {
            "data_source": "Alpaca Official WebSocket API",
            "intelligent_fallback": True,
            "supports_test_data": True,
            "supports_trading_updates": True,
            "supports_real_market_data": "需要市场数据订阅"
        }
    }