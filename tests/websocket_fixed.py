#!/usr/bin/env python3
"""
修复的Alpaca WebSocket实现
基于诊断结果，使用可用的端点提供数据流
"""

import asyncio
import websockets
import json
import ssl
import time
from datetime import datetime
from typing import Dict, List, Set, Optional, Union, Callable
from loguru import logger
import yaml

class FixedAlpacaWebSocketManager:
    """修复的Alpaca WebSocket管理器 - 智能回退到可用端点"""
    
    # WebSocket端点优先级（按可用性排序）
    ENDPOINTS = {
        'test': {
            'url': 'wss://stream.data.alpaca.markets/v2/test',
            'symbols': ['FAKEPACA'],  # 测试端点只支持FAKEPACA
            'available': True,  # 总是可用
            'description': '测试端点 - 免费可用'
        },
        'trading': {
            'url': 'wss://paper-api.alpaca.markets/stream',
            'symbols': [],  # 交易更新，不需要符号
            'available': True,  # 如果有API密钥就可用
            'description': '交易更新端点 - 订单和账户更新'
        },
        'stock_iex': {
            'url': 'wss://stream.data.alpaca.markets/v2/iex',
            'symbols': [],  # 支持真实股票符号
            'available': False,  # 需要检测
            'description': 'IEX股票数据 - 需要市场数据订阅'
        },
        'stock_sip': {
            'url': 'wss://stream.data.alpaca.markets/v2/sip',
            'symbols': [],  # 支持真实股票符号
            'available': False,  # 需要检测
            'description': 'SIP股票数据 - 需要付费订阅'
        }
    }
    
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.connections = {}  # 存储活跃连接
        self.subscribers = []  # WebSocket客户端订阅者
        self.available_endpoints = []  # 可用端点列表
        self.message_handlers = {}  # 消息处理器
        self._shutdown = False
        
    async def initialize(self):
        """初始化并检测可用端点"""
        logger.info("🚀 初始化修复的WebSocket管理器...")
        
        # 检测可用端点
        await self._detect_available_endpoints()
        
        # 连接到可用端点
        await self._connect_to_available_endpoints()
        
        logger.info(f"✅ WebSocket管理器初始化完成，可用端点: {[ep['description'] for ep in self.available_endpoints]}")
    
    async def _detect_available_endpoints(self):
        """检测哪些端点可用"""
        logger.info("🔍 检测可用的WebSocket端点...")
        
        for endpoint_name, endpoint_info in self.ENDPOINTS.items():
            try:
                is_available = await self._test_endpoint(endpoint_name, endpoint_info)
                if is_available:
                    self.available_endpoints.append({
                        'name': endpoint_name,
                        'info': endpoint_info
                    })
                    logger.info(f"✅ {endpoint_name}: {endpoint_info['description']} - 可用")
                else:
                    logger.warning(f"❌ {endpoint_name}: {endpoint_info['description']} - 不可用")
            except Exception as e:
                logger.error(f"❌ {endpoint_name} 检测失败: {e}")
    
    async def _test_endpoint(self, endpoint_name: str, endpoint_info: dict) -> bool:
        """测试单个端点是否可用"""
        try:
            ssl_context = ssl.create_default_context()
            ws = await websockets.connect(
                endpoint_info['url'],
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            # 等待欢迎消息
            try:
                welcome_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                if endpoint_name == 'trading':
                    # 交易端点不发送JSON欢迎消息
                    pass
                else:
                    welcome_data = json.loads(welcome_msg)
                    if not (isinstance(welcome_data, list) and welcome_data[0].get("T") == "success"):
                        await ws.close()
                        return False
            except asyncio.TimeoutError:
                if endpoint_name != 'trading':
                    await ws.close()
                    return False
            
            # 测试认证
            if endpoint_name == 'trading':
                auth_message = {
                    "action": "auth",
                    "key": self.api_key,
                    "secret": self.secret_key
                }
                await ws.send(json.dumps(auth_message))
                
                auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                auth_data = json.loads(auth_response)
                
                if auth_data.get('stream') == 'authorization' and auth_data.get('data', {}).get('status') == 'authorized':
                    await ws.close()
                    return True
                else:
                    await ws.close()
                    return False
            else:
                auth_message = {
                    "action": "auth",
                    "key": self.api_key,
                    "secret": self.secret_key
                }
                await ws.send(json.dumps(auth_message))
                
                auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                auth_data = json.loads(auth_response)
                
                if isinstance(auth_data, list):
                    auth_result = auth_data[0] if auth_data else {}
                else:
                    auth_result = auth_data
                
                await ws.close()
                
                if auth_result.get("T") == "success":
                    return True
                elif auth_result.get("T") == "error":
                    error_code = auth_result.get("code")
                    # 406 = 连接超限，409 = 订阅不足
                    if error_code in [406, 409]:
                        return False
                    else:
                        return False
                        
        except Exception as e:
            logger.debug(f"端点 {endpoint_name} 测试异常: {e}")
            return False
        
        return False
    
    async def _connect_to_available_endpoints(self):
        """连接到所有可用端点"""
        for endpoint in self.available_endpoints:
            try:
                await self._connect_endpoint(endpoint['name'], endpoint['info'])
            except Exception as e:
                logger.error(f"连接端点 {endpoint['name']} 失败: {e}")
    
    async def _connect_endpoint(self, endpoint_name: str, endpoint_info: dict):
        """连接到特定端点"""
        logger.info(f"🔗 连接到端点: {endpoint_name}")
        
        ssl_context = ssl.create_default_context()
        ws = await websockets.connect(
            endpoint_info['url'],
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=10
        )
        
        # 等待欢迎消息
        if endpoint_name != 'trading':
            welcome_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            welcome_data = json.loads(welcome_msg)
            logger.debug(f"欢迎消息 [{endpoint_name}]: {welcome_data}")
        
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
        
        # 验证认证成功
        if endpoint_name == 'trading':
            if not (auth_data.get('stream') == 'authorization' and auth_data.get('data', {}).get('status') == 'authorized'):
                raise Exception(f"认证失败: {auth_data}")
        else:
            auth_result = auth_data[0] if isinstance(auth_data, list) else auth_data
            if auth_result.get("T") != "success":
                raise Exception(f"认证失败: {auth_result}")
        
        logger.info(f"✅ {endpoint_name} 认证成功")
        
        # 存储连接
        self.connections[endpoint_name] = {
            'ws': ws,
            'info': endpoint_info,
            'connected': True
        }
        
        # 启动监听任务
        asyncio.create_task(self._listen_endpoint(endpoint_name))
        
        # 如果是市场数据端点，订阅默认符号
        if endpoint_name == 'test':
            await self._subscribe_test_data(ws)
        elif endpoint_name == 'trading':
            await self._subscribe_trading_updates(ws)
    
    async def _subscribe_test_data(self, ws):
        """订阅测试数据"""
        subscribe_msg = {
            "action": "subscribe",
            "trades": ["FAKEPACA"],
            "quotes": ["FAKEPACA"],
            "bars": ["FAKEPACA"]
        }
        await ws.send(json.dumps(subscribe_msg))
        logger.info("✅ 已订阅测试数据 (FAKEPACA)")
    
    async def _subscribe_trading_updates(self, ws):
        """订阅交易更新"""
        listen_msg = {
            "action": "listen",
            "data": {
                "streams": ["trade_updates"]
            }
        }
        await ws.send(json.dumps(listen_msg))
        logger.info("✅ 已订阅交易更新")
    
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
    
    async def _process_message(self, endpoint_name: str, message: Union[str, bytes]):
        """处理消息"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = json.loads(message.decode('utf-8'))
            
            # 处理不同类型的消息
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
            logger.error(f"处理消息错误 [{endpoint_name}]: {e}, 消息: {str(message)[:200]}")
    
    async def _handle_trading_message(self, data: dict):
        """处理交易消息"""
        stream = data.get('stream')
        if stream == 'trade_updates':
            trade_data = data.get('data', {})
            event = trade_data.get('event')
            order = trade_data.get('order', {})
            
            message = {
                "type": "trade_update",
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
        else:
            logger.debug(f"未处理的交易消息: {data}")
    
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
        else:
            logger.debug(f"未处理的市场数据消息 [{endpoint_name}]: {msg_type} - {data}")
    
    async def _broadcast_message(self, message: dict):
        """广播消息给所有订阅者"""
        if self.subscribers:
            # 创建广播任务
            broadcast_tasks = []
            for subscriber in self.subscribers.copy():  # 复制列表避免并发修改
                try:
                    task = asyncio.create_task(subscriber.send_text(json.dumps(message)))
                    broadcast_tasks.append(task)
                except Exception as e:
                    logger.error(f"广播消息失败: {e}")
                    # 移除失效的订阅者
                    if subscriber in self.subscribers:
                        self.subscribers.remove(subscriber)
            
            # 等待所有广播完成
            if broadcast_tasks:
                await asyncio.gather(*broadcast_tasks, return_exceptions=True)
    
    def add_subscriber(self, websocket):
        """添加WebSocket订阅者"""
        self.subscribers.append(websocket)
        logger.info(f"➕ 新增订阅者，当前订阅者数量: {len(self.subscribers)}")
    
    def remove_subscriber(self, websocket):
        """移除WebSocket订阅者"""
        if websocket in self.subscribers:
            self.subscribers.remove(websocket)
            logger.info(f"➖ 移除订阅者，当前订阅者数量: {len(self.subscribers)}")
    
    async def get_status(self) -> dict:
        """获取连接状态"""
        status = {
            "available_endpoints": len(self.available_endpoints),
            "active_connections": len([c for c in self.connections.values() if c['connected']]),
            "subscribers": len(self.subscribers),
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
        
        self.subscribers.clear()
        logger.info("✅ WebSocket管理器已关闭")

# 全局WebSocket管理器实例
websocket_manager = None

async def get_websocket_manager() -> FixedAlpacaWebSocketManager:
    """获取WebSocket管理器实例"""
    global websocket_manager
    
    if websocket_manager is None:
        # 加载配置
        with open('secrets.yml', 'r') as f:
            config = yaml.safe_load(f)
        
        # 获取第一个启用的账户
        accounts = config.get('accounts', {})
        enabled_account = None
        
        for account_id, account_config in accounts.items():
            if account_config.get('enabled', False):
                enabled_account = account_config
                break
        
        if not enabled_account:
            # 回退到传统配置
            alpaca_config = config.get('alpaca', {})
            if alpaca_config.get('api_key') and alpaca_config.get('secret_key'):
                enabled_account = alpaca_config
            else:
                raise Exception("未找到启用的账户配置")
        
        # 创建并初始化管理器
        websocket_manager = FixedAlpacaWebSocketManager(
            enabled_account['api_key'],
            enabled_account['secret_key']
        )
        
        await websocket_manager.initialize()
    
    return websocket_manager

if __name__ == "__main__":
    async def test_manager():
        """测试WebSocket管理器"""
        manager = await get_websocket_manager()
        
        # 显示状态
        status = await manager.get_status()
        print(f"状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
        
        # 运行一段时间
        await asyncio.sleep(30)
        
        # 关闭
        await manager.shutdown()
    
    asyncio.run(test_manager())