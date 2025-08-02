"""
WebSocket路由 - 实时市场数据流
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, List, Set
import json
import asyncio
import random
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from loguru import logger

from config import settings

# WebSocket路由
ws_router = APIRouter(prefix="/ws", tags=["websocket"])

# 活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}
subscribed_symbols: Set[str] = set()

# Alpaca WebSocket客户端
alpaca_ws = None

# 默认的测试股票和期权代码
DEFAULT_STOCKS = ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NVDA", "META", "SPY"]
DEFAULT_OPTIONS = [
    "AAPL250117C00230000",   # AAPL Call $230 2025-01-17
    "AAPL250117P00220000",   # AAPL Put $220 2025-01-17  
    "TSLA250117C00300000",   # TSLA Call $300 2025-01-17
    "TSLA250117P00280000",   # TSLA Put $280 2025-01-17
    "SPY250117C00580000",    # SPY Call $580 2025-01-17
    "SPY250117P00570000"     # SPY Put $570 2025-01-17
]

class AlpacaWebSocketManager:
    """Alpaca WebSocket管理器"""
    
    def __init__(self):
        self.trading_client = None
        self.stock_stream = None
        self.connected = False
        
    async def initialize(self):
        """初始化Alpaca连接"""
        try:
            # 检查API密钥是否配置
            if not settings.alpaca_secret_key:
                logger.warning("Alpaca secret key not configured, using demo mode with simulated data")
                self.connected = True
                # 启动模拟数据生成器
                asyncio.create_task(self.simulate_market_data())
                return
            
            # 使用配置的API密钥初始化
            self.trading_client = TradingClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                paper=settings.alpaca_paper_trading
            )
            
            # 创建数据流连接
            self.stock_stream = StockDataStream(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                feed='iex'  # 免费账户使用IEX数据
            )
            
            # 设置数据处理回调
            async def quote_handler(data):
                await self.broadcast_quote_data('stock', data)
            
            async def trade_handler(data):
                await self.broadcast_trade_data('stock', data)
                
            self.stock_stream.subscribe_quotes(quote_handler, *DEFAULT_STOCKS)
            self.stock_stream.subscribe_trades(trade_handler, *DEFAULT_STOCKS)
            
            self.connected = True
            logger.info("Alpaca WebSocket连接初始化成功")
            
        except Exception as e:
            logger.error(f"Alpaca WebSocket初始化失败: {e}")
            self.connected = False
    
    async def subscribe_symbols(self, symbols: List[str]):
        """订阅股票代码"""
        if not self.connected or not self.stock_stream:
            await self.initialize()
            
        try:
            # 订阅股票报价和交易数据
            stock_symbols = [s for s in symbols if not self._is_option_symbol(s)]
            option_symbols = [s for s in symbols if self._is_option_symbol(s)]
            
            if stock_symbols:
                logger.info(f"订阅股票数据: {stock_symbols}")
                # 注意：实际的订阅在initialize方法中已完成
                # 这里可以添加动态订阅逻辑（如果需要）
            
            if option_symbols:
                logger.info(f"期权数据订阅请求: {option_symbols} (注意：需要检查Alpaca是否支持期权实时数据)")
            
            # 启动数据流（在后台任务中运行）
            if not hasattr(self, '_stream_task'):
                self._stream_task = asyncio.create_task(self.stock_stream.run())
            
        except Exception as e:
            logger.error(f"订阅数据失败: {e}")
    
    def _is_option_symbol(self, symbol: str) -> bool:
        """判断是否为期权代码"""
        return len(symbol) > 10 and (symbol[-9] in ['C', 'P'])
    
    async def broadcast_quote_data(self, data_type: str, data):
        """广播报价数据到所有连接的客户端"""
        message = {
            "type": "quote",
            "data_type": data_type,
            "symbol": data.symbol,
            "bid_price": float(data.bid_price) if data.bid_price else None,
            "ask_price": float(data.ask_price) if data.ask_price else None,
            "bid_size": int(data.bid_size) if data.bid_size else None,
            "ask_size": int(data.ask_size) if data.ask_size else None,
            "timestamp": data.timestamp.isoformat() if hasattr(data, 'timestamp') else datetime.now().isoformat()
        }
        
        await self.broadcast_to_all(message)
    
    async def broadcast_trade_data(self, data_type: str, data):
        """广播交易数据到所有连接的客户端"""
        message = {
            "type": "trade",
            "data_type": data_type,
            "symbol": data.symbol,
            "price": float(data.price) if data.price else None,
            "size": int(data.size) if data.size else None,
            "timestamp": data.timestamp.isoformat() if hasattr(data, 'timestamp') else datetime.now().isoformat()
        }
        
        await self.broadcast_to_all(message)
    
    async def broadcast_to_all(self, message: dict):
        """向所有连接的客户端广播消息"""
        if active_connections:
            message_str = json.dumps(message)
            disconnected = []
            
            for client_id, websocket in active_connections.items():
                try:
                    await websocket.send_text(message_str)
                except Exception as e:
                    logger.warning(f"发送消息给客户端 {client_id} 失败: {e}")
                    disconnected.append(client_id)
            
            # 清理断开的连接
            for client_id in disconnected:
                active_connections.pop(client_id, None)

    async def simulate_market_data(self):
        """模拟市场数据生成器"""
        logger.info("启动模拟市场数据生成器")
        
        # 基础价格
        base_prices = {
            "AAPL": 225.0,
            "TSLA": 290.0,
            "GOOGL": 172.0,
            "MSFT": 420.0,
            "AMZN": 185.0,
            "NVDA": 875.0,
            "META": 520.0,
            "SPY": 575.0
        }
        
        current_prices = base_prices.copy()
        
        while self.connected and active_connections:
            try:
                # 随机选择一个股票
                symbol = random.choice(DEFAULT_STOCKS)
                
                # 生成报价数据
                current_price = current_prices[symbol]
                spread = current_price * 0.001  # 0.1% spread
                bid_price = current_price - spread/2
                ask_price = current_price + spread/2
                
                # 创建模拟报价数据
                class MockQuote:
                    def __init__(self, symbol, bid_price, ask_price):
                        self.symbol = symbol
                        self.bid_price = bid_price
                        self.ask_price = ask_price
                        self.bid_size = random.randint(100, 1000)
                        self.ask_size = random.randint(100, 1000)
                        self.timestamp = datetime.now()
                
                quote_data = MockQuote(symbol, bid_price, ask_price)
                await self.broadcast_quote_data('stock', quote_data)
                
                # 随机生成交易数据
                if random.random() < 0.3:  # 30% 概率生成交易
                    trade_price = random.uniform(bid_price, ask_price)
                    
                    class MockTrade:
                        def __init__(self, symbol, price):
                            self.symbol = symbol
                            self.price = price
                            self.size = random.randint(50, 500)
                            self.timestamp = datetime.now()
                    
                    trade_data = MockTrade(symbol, trade_price)
                    await self.broadcast_trade_data('stock', trade_data)
                    
                    # 更新当前价格（随机游走）
                    price_change = (random.random() - 0.5) * current_price * 0.01  # ±0.5% 随机变化
                    current_prices[symbol] = max(0.01, current_price + price_change)
                
                # 等待2-5秒
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"模拟数据生成错误: {e}")
                await asyncio.sleep(5)

# 全局WebSocket管理器
ws_manager = AlpacaWebSocketManager()

@ws_router.websocket("/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket端点 - 实时市场数据"""
    await websocket.accept()
    client_id = f"client_{datetime.now().timestamp()}"
    active_connections[client_id] = websocket
    
    logger.info(f"WebSocket客户端连接: {client_id}")
    
    # 发送欢迎消息
    welcome_message = {
        "type": "welcome",
        "client_id": client_id,
        "message": "连接成功！即将开始接收实时市场数据",
        "default_stocks": DEFAULT_STOCKS,
        "default_options": DEFAULT_OPTIONS,
        "data_source": "Alpaca IEX (Paper Trading)",
        "limitations": {
            "data_feed": "IEX exchange only (free tier)",
            "symbols_limit": 30,
            "connection_limit": 1,
            "update_frequency": "Real-time"
        }
    }
    
    try:
        await websocket.send_text(json.dumps(welcome_message))
        
        # 如果还没有连接到Alpaca，则初始化连接
        if not ws_manager.connected:
            await ws_manager.initialize()
        
        # 自动订阅默认股票和期权
        all_symbols = DEFAULT_STOCKS + DEFAULT_OPTIONS
        subscribed_symbols.update(all_symbols)
        
        # 发送订阅确认
        subscription_message = {
            "type": "subscription",
            "subscribed_symbols": list(subscribed_symbols),
            "message": f"已订阅 {len(subscribed_symbols)} 个证券代码"
        }
        await websocket.send_text(json.dumps(subscription_message))
        
        # 启动数据订阅 (在后台运行)
        if subscribed_symbols:
            asyncio.create_task(ws_manager.subscribe_symbols(list(subscribed_symbols)))
        
        # 保持连接并处理客户端消息
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "subscribe":
                    # 客户端请求订阅新股票
                    new_symbols = message.get("symbols", [])
                    subscribed_symbols.update(new_symbols)
                    
                    response = {
                        "type": "subscription_update", 
                        "added_symbols": new_symbols,
                        "total_subscribed": len(subscribed_symbols)
                    }
                    await websocket.send_text(json.dumps(response))
                    
                elif message.get("type") == "ping":
                    # 心跳检测
                    pong_message = {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send_text(json.dumps(pong_message))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"处理WebSocket消息错误: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开连接: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket连接错误: {e}")
    finally:
        # 清理连接
        active_connections.pop(client_id, None)
        logger.info(f"WebSocket客户端 {client_id} 连接已清理")

@ws_router.get("/status")
async def websocket_status():
    """获取WebSocket连接状态"""
    return {
        "active_connections": len(active_connections),
        "subscribed_symbols": list(subscribed_symbols),
        "alpaca_connected": ws_manager.connected,
        "default_symbols": {
            "stocks": DEFAULT_STOCKS,
            "options": DEFAULT_OPTIONS
        },
        "websocket_endpoint": "/api/v1/ws/market-data",
        "connection_info": {
            "data_source": "Alpaca Paper Trading API",
            "data_feed": "IEX Exchange",
            "real_time": True,
            "limitations": "Free tier: 30 symbols, 1 connection"
        }
    }