"""
WebSocket路由 - 实时市场数据流（使用官方Alpaca WebSocket端点）
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Union
import json
import asyncio
import websockets
import msgpack
from datetime import datetime
from alpaca.trading.client import TradingClient
from loguru import logger
import ssl
import time

from config import settings

# WebSocket路由
ws_router = APIRouter(prefix="/ws", tags=["websocket"])

# 活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}
subscribed_symbols: Set[str] = set()

# Alpaca WebSocket客户端
alpaca_ws = None

# 默认的测试股票和期权代码
DEFAULT_STOCKS = [
    "AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NVDA", "META", "SPY",
    "HOOD", "AEO"
]
DEFAULT_OPTIONS = [
    "TSLA250808C00307500",   # TSLA Call $307.50 2025-08-08 (from alert)
    "HOOD250822C00115000",   # HOOD Call $115.00 2025-08-22 (from alert)
    "AEO250808C00015000",    # AEO Call $15.00 2025-08-08 (from alert)
    "AAPL250808C00230000",   # AAPL Call $230 2025-08-08 (current)
    "SPY250808C00580000",    # SPY Call $580 2025-08-08 (current)
    "NVDA250808C00140000"    # NVDA Call $140 2025-08-08 (current)
]

class AlpacaWebSocketManager:
    """Alpaca WebSocket管理器 - 使用官方WebSocket端点"""
    
    # Official Alpaca WebSocket endpoints - Use IEX for fastest pricing
    STOCK_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"
    OPTION_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/indicative"
    TEST_WS_URL = "wss://stream.data.alpaca.markets/v2/test"
    TRADING_WS_URL = "wss://paper-api.alpaca.markets/stream"
    
    # 测试符号
    TEST_SYMBOL = "FAKEPACA"  # 官方测试股票代码
    
    # Alpaca错误代码映射与解决方案
    ERROR_CODES = {
        400: {
            "description": "invalid syntax - 检查消息格式",
            "solution": "检查JSON/MessagePack格式",
            "retry": False
        },
        401: {
            "description": "unauthorized - API密钥无效",
            "solution": "验证API密钥和密钥对",
            "retry": False
        },
        402: {
            "description": "forbidden - 权限不足或订阅不足",
            "solution": "升级账户订阅或使用IEX端点",
            "retry": True,
            "fallback_endpoint": True
        },
        404: {
            "description": "not found - 端点不存在", 
            "solution": "检查端点URL是否正确",
            "retry": False
        },
        406: {
            "description": "connection limit exceeded - 连接数超限",
            "solution": "关闭其他连接或使用连接池",
            "retry": True,
            "wait_seconds": 30
        },
        409: {
            "description": "conflict - 重复订阅或连接冲突",
            "solution": "检查是否已有活跃连接",
            "retry": True,
            "wait_seconds": 5
        },
        412: {
            "description": "option messages are only available in MsgPack format",
            "solution": "期权数据必须使用MessagePack格式",
            "retry": False
        },
        413: {
            "description": "too many symbols - 符号数量超限",
            "solution": "减少单次订阅的符号数量",
            "retry": True,
            "reduce_symbols": True
        },
        500: {
            "description": "internal server error - 服务器内部错误",
            "solution": "等待后重试",
            "retry": True,
            "wait_seconds": 60
        }
    }
    
    def __init__(self):
        self.trading_client = None
        self.stock_ws = None
        self.option_ws = None
        self.connected = False
        self.stock_connected = False
        self.option_connected = False
        self.account_config = None
        self._stock_reconnect_task = None
        self._option_reconnect_task = None
        self._health_check_task = None  # 健康检查任务
        self._shutdown = False
        self.last_message_time = {}  # 连接健康检查
        self.message_counts = {}     # 消息计数
        self.current_stock_endpoint = None  # 当前使用的股票端点
        self.active_connections_count = 0   # 活跃连接计数
        self.connection_limit_reached = False  # 连接限制状态
        
    async def test_websocket_connection(self, api_key: str, secret_key: str) -> bool:
        """在启动正式数据流前测试WebSocket连接"""
        logger.info("🧪 开始WebSocket连接测试...")
        
        try:
            # 1. 验证API凭证
            test_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=True  # 使用paper环境测试
            )
            account = test_client.get_account()
            logger.info(f"✅ API凭证验证成功: {account.account_number}")
            
            # 2. 测试WebSocket连接
            ssl_context = ssl.create_default_context()
            test_ws = await websockets.connect(
                self.TEST_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"✅ WebSocket测试端点连接成功: {self.TEST_WS_URL}")
            
            # 3. 测试认证
            auth_message = {
                "action": "auth",
                "key": api_key,
                "secret": secret_key
            }
            await test_ws.send(json.dumps(auth_message))
            
            # 4. 等待认证响应（10秒超时）
            response = await asyncio.wait_for(test_ws.recv(), timeout=10.0)
            auth_data = json.loads(response)
            
            if isinstance(auth_data, list):
                auth_response = auth_data[0] if auth_data else {}
            else:
                auth_response = auth_data
                
            if auth_response.get("T") == "success":
                logger.info("✅ WebSocket认证测试成功")
                
                # 5. 测试订阅测试符号
                test_subscription = {
                    "action": "subscribe",
                    "trades": [self.TEST_SYMBOL],
                    "quotes": [self.TEST_SYMBOL]
                }
                await test_ws.send(json.dumps(test_subscription))
                logger.info(f"✅ 测试符号订阅成功: {self.TEST_SYMBOL}")
                
                # 6. 等待订阅确认
                sub_response = await asyncio.wait_for(test_ws.recv(), timeout=5.0)
                sub_data = json.loads(sub_response)
                logger.info(f"✅ 订阅确认: {sub_data}")
                
                await test_ws.close()
                logger.info("🎉 WebSocket连接测试完全通过!")
                return True
            else:
                logger.error(f"❌ WebSocket认证失败: {auth_response}")
                await test_ws.close()
                return False
                
        except asyncio.TimeoutError:
            logger.error("❌ WebSocket连接测试超时")
            return False
        except Exception as e:
            logger.error(f"❌ WebSocket连接测试失败: {e}")
            return False
    
    async def handle_websocket_error(self, error_data: dict, endpoint_type: str = "unknown") -> dict:
        """处理WebSocket错误并返回处理策略"""
        error_code = error_data.get("code")
        error_msg = error_data.get("msg", "Unknown error")
        
        error_info = self.ERROR_CODES.get(error_code, {
            "description": "Unknown error code",
            "solution": "检查网络连接或稍后重试",
            "retry": True
        })
        
        logger.error(f"🚨 WebSocket错误 [{endpoint_type}] [{error_code}]: {error_msg}")
        logger.error(f"📋 描述: {error_info['description']}")
        logger.error(f"🔧 解决方案: {error_info['solution']}")
        
        # 构建处理策略
        strategy = {
            "error_code": error_code,
            "error_msg": error_msg,
            "should_retry": error_info.get("retry", False),
            "wait_seconds": error_info.get("wait_seconds", 5),
            "fallback_endpoint": error_info.get("fallback_endpoint", False),
            "reduce_symbols": error_info.get("reduce_symbols", False),
            "action": self._determine_error_action(error_code, endpoint_type)
        }
        
        # 特定错误的额外处理
        if error_code == 406:  # 连接超限
            self.connection_limit_reached = True
            self.active_connections_count = self.account_config.max_connections
            strategy["action"] = "wait_for_connection_slot"
            
        elif error_code == 402 and endpoint_type == "stock":  # 订阅不足，尝试降级端点
            strategy["action"] = "try_fallback_endpoint"
            strategy["fallback_endpoint"] = True
            
        elif error_code == 413:  # 符号过多
            strategy["action"] = "reduce_symbol_count"
            strategy["max_symbols"] = 10  # 减少到10个符号
            
        return strategy
    
    def _determine_error_action(self, error_code: int, endpoint_type: str) -> str:
        """确定错误处理动作"""
        if error_code == 401:
            return "abort_invalid_credentials"
        elif error_code == 402 and endpoint_type == "stock":
            return "try_iex_fallback"
        elif error_code == 406:
            return "wait_for_connection_slot"
        elif error_code == 409:
            return "wait_and_retry"
        elif error_code == 412:
            return "switch_to_msgpack"
        elif error_code == 413:
            return "reduce_symbols"
        elif error_code in [500, 502, 503]:
            return "retry_with_exponential_backoff"
        else:
            return "log_and_continue"
    
    async def validate_connection_health(self, connection_type: str, ws_connection) -> tuple[bool, dict]:
        """验证连接健康状态"""
        checks = {
            "connection_open": ws_connection is not None and not ws_connection.closed,
            "recent_messages": self._check_recent_messages(connection_type),
            "auth_status": self._get_connection_status(connection_type)
        }
        
        # 测试ping响应
        if checks["connection_open"]:
            checks["ping_response"] = await self._test_ping(ws_connection)
        else:
            checks["ping_response"] = False
        
        all_healthy = all(checks.values())
        
        if not all_healthy:
            logger.warning(f"⚠️ 连接健康检查失败 [{connection_type}]: {checks}")
        else:
            logger.debug(f"✅ 连接健康 [{connection_type}]: {checks}")
            
        return all_healthy, checks
    
    def _check_recent_messages(self, connection_type: str) -> bool:
        """检查最近是否收到消息"""
        last_time = self.last_message_time.get(connection_type)
        if not last_time:
            return False
        return (time.time() - last_time) < 60  # 60秒内有消息
    
    def _get_connection_status(self, connection_type: str) -> bool:
        """获取连接状态"""
        if connection_type == "stock":
            return self.stock_connected
        elif connection_type == "option":
            return self.option_connected
        return False
    
    async def _test_ping(self, ws_connection) -> bool:
        """测试WebSocket ping响应"""
        try:
            pong_waiter = await ws_connection.ping()
            await asyncio.wait_for(pong_waiter, timeout=10.0)
            return True
        except Exception:
            return False
    
    async def _periodic_health_check(self):
        """定期健康检查任务"""
        logger.info("🏥 开始定期WebSocket健康检查")
        
        while not self._shutdown:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                if self._shutdown:
                    break
                
                # 检查股票WebSocket健康状态
                if self.stock_connected and self.stock_ws:
                    stock_healthy, stock_checks = await self.validate_connection_health("stock", self.stock_ws)
                    if not stock_healthy:
                        logger.warning(f"🚨 股票WebSocket不健康: {stock_checks}")
                        # 可以在这里触发重连逻辑
                        if not stock_checks.get("connection_open", False):
                            logger.error("股票WebSocket连接已关闭，启动重连...")
                            asyncio.create_task(self._reconnect_stock_websocket())
                    else:
                        logger.debug("✅ 股票WebSocket健康检查通过")
                
                # 检查期权WebSocket健康状态
                if self.option_connected and self.option_ws:
                    option_healthy, option_checks = await self.validate_connection_health("option", self.option_ws)
                    if not option_healthy:
                        logger.warning(f"🚨 期权WebSocket不健康: {option_checks}")
                        # 可以在这里触发重连逻辑
                        if not option_checks.get("connection_open", False):
                            logger.error("期权WebSocket连接已关闭，启动重连...")
                            asyncio.create_task(self._reconnect_option_websocket())
                    else:
                        logger.debug("✅ 期权WebSocket健康检查通过")
                
                # 报告消息统计
                if self.message_counts:
                    total_messages = sum(self.message_counts.values())
                    logger.info(f"📊 消息统计: 总计={total_messages}, 股票={self.message_counts.get('stock', 0)}, 期权={self.message_counts.get('option', 0)}")
                    
                    # 如果连接了但长时间没有消息，发出警告
                    current_time = time.time()
                    for conn_type in ["stock", "option"]:
                        last_time = self.last_message_time.get(conn_type)
                        if last_time and (current_time - last_time) > 300:  # 5分钟没有消息
                            logger.warning(f"⚠️ {conn_type}WebSocket超过5分钟没有收到消息")
                
            except Exception as e:
                logger.error(f"健康检查任务错误: {e}")
                
        logger.info("🏥 定期健康检查任务结束")
        
    async def initialize(self):
        """初始化Alpaca连接 - 智能回退到可用端点"""
        try:
            # 获取第一个启用的账户用于WebSocket连接
            from app.account_pool import get_account_pool
            pool = get_account_pool()
            
            # 确保连接池已初始化
            if not pool._initialized:
                await pool.initialize()
            
            # 获取第一个可用账户
            if not pool.account_configs:
                raise Exception(
                    "No account configurations found. "
                    "Real data only mode requires valid API keys."
                )
            
            # 获取第一个启用的账户
            enabled_accounts = [
                acc for acc in pool.account_configs.values() if acc.enabled
            ]
            if not enabled_accounts:
                raise Exception(
                    "No enabled accounts found. "
                    "Real data only mode requires valid API keys."
                )
            
            self.account_config = enabled_accounts[0]
            logger.info(
                f"Using account {self.account_config.account_id} "
                "for WebSocket data stream"
            )
            
            # 🧪 STEP 1: 执行WebSocket连接测试
            test_passed = await self.test_websocket_connection(
                self.account_config.api_key,
                self.account_config.secret_key
            )
            
            if not test_passed:
                logger.warning("WebSocket连接测试失败，但将尝试使用可用端点")
            
            # 验证API密钥
            test_client = TradingClient(
                api_key=self.account_config.api_key,
                secret_key=self.account_config.secret_key,
                paper=self.account_config.paper_trading
            )
            
            # 测试连接
            account_info = test_client.get_account()
            logger.info(f"✅ API连接验证成功 - 账户: {account_info.account_number}")
            
            # 检测可用端点并连接 - 直接使用IEX端点
            logger.info("🚀 直接使用IEX端点 - 提供最快的交易所价格")
            self.connected = True
            
            logger.info("🚀 Alpaca WebSocket连接初始化成功 - 使用IEX端点")
            logger.info(f"📊 账户层级: {getattr(self.account_config, 'tier', 'unknown')}")
            logger.info(f"🔗 股票端点: IEX - 最快交易所价格")
            logger.info(f"🏷️ Paper Trading: {getattr(self.account_config, 'paper_trading', 'unknown')}")
            logger.info(f"🔢 连接限制: {getattr(self.account_config, 'max_connections', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Alpaca WebSocket初始化失败: {e}")
            logger.warning("将尝试使用测试端点作为回退方案")
            
            # 尝试连接测试端点作为回退
            try:
                await self._connect_test_endpoint_fallback()
                self.connected = True
                logger.info("✅ 已连接到测试端点作为回退方案")
            except Exception as fallback_error:
                logger.error(f"测试端点回退也失败: {fallback_error}")
                self.connected = False
                raise e
    
    async def subscribe_symbols(self, symbols: List[str]):
        """订阅股票和期权代码 - 使用官方WebSocket端点"""
        if not self.connected:
            await self.initialize()
            
        try:
            # 分离股票和期权符号
            stock_symbols = [s for s in symbols if not self._is_option_symbol(s)]
            option_symbols = [s for s in symbols if self._is_option_symbol(s)]
            
            logger.info(f"订阅Alpaca实时数据 - 股票: {stock_symbols}, 期权: {option_symbols}")
            
            # 启动股票WebSocket连接
            if stock_symbols and not self.stock_connected:
                await self._connect_stock_websocket(stock_symbols)
            elif stock_symbols and self.stock_connected:
                await self._subscribe_stock_symbols(stock_symbols)
            
            # 启动期权WebSocket连接
            if option_symbols and not self.option_connected:
                await self._connect_option_websocket(option_symbols)
            elif option_symbols and self.option_connected:
                await self._subscribe_option_symbols(option_symbols)
            
            # 启动健康检查任务
            if not self._health_check_task or self._health_check_task.done():
                self._health_check_task = asyncio.create_task(self._periodic_health_check())
                logger.info("🏥 启动WebSocket连接健康检查任务")
            
        except Exception as e:
            logger.error(f"订阅真实数据失败: {e}")
            raise e
    
    async def _detect_and_connect_stock_endpoints(self):
        """智能检测并连接可用的股票数据端点"""
        logger.info("🔍 开始智能股票端点检测...")
        
        # 根据账户层级确定尝试顺序
        account_tier = getattr(self.account_config, 'tier', 'standard').lower()
        
        # 如果是高级账户，先尝试SIP端点
        if account_tier in ['premium', 'algo_trader_plus']:
            endpoints_to_try = self.STOCK_ENDPOINTS
            logger.info(f"🏆 高级账户 ({account_tier})，优先尝试SIP端点")
        else:
            # 标准账户直接使用IEX端点
            endpoints_to_try = [ep for ep in self.STOCK_ENDPOINTS if ep['name'] == 'IEX']
            logger.info(f"📊 标准账户 ({account_tier})，使用IEX端点")
        
        last_error = None
        
        for endpoint in endpoints_to_try:
            try:
                logger.info(f"🔌 尝试连接 {endpoint['name']} 端点: {endpoint['url']}")
                
                # 测试端点连接
                connection_result = await self._test_stock_endpoint(endpoint)
                
                if connection_result["success"]:
                    self.current_stock_endpoint = endpoint
                    logger.info(f"✅ 成功连接到 {endpoint['name']} 端点")
                    logger.info(f"📝 端点描述: {endpoint['description']}")
                    return True
                else:
                    logger.warning(f"❌ {endpoint['name']} 端点连接失败: {connection_result['error']}")
                    last_error = connection_result["error"]
                    
                    # 如果是权限不足错误，立即尝试下一个端点
                    if connection_result.get("error_code") == 402:
                        logger.info(f"⬇️ 权限不足，尝试降级到下一个端点...")
                        continue
                        
            except Exception as e:
                logger.error(f"❌ {endpoint['name']} 端点测试异常: {e}")
                last_error = str(e)
                continue
        
        # 所有端点都失败
        logger.error("🚨 所有股票数据端点连接失败")
        if last_error:
            logger.error(f"最后错误: {last_error}")
        
        # 作为最后的回退，尝试测试端点
        logger.info("🆘 尝试连接测试端点作为最后回退...")
        try:
            await self._connect_test_endpoint_fallback()
            return True
        except Exception as e:
            logger.error(f"测试端点回退失败: {e}")
            return False
    
    async def _test_stock_endpoint(self, endpoint: dict) -> dict:
        """测试单个股票端点的可用性"""
        try:
            ssl_context = ssl.create_default_context()
            ws = await websockets.connect(
                endpoint["url"],
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            logger.info(f"🔗 {endpoint['name']} WebSocket连接已建立")
            
            # 认证测试
            auth_message = {
                "action": "auth",
                "key": self.account_config.api_key,
                "secret": self.account_config.secret_key
            }
            await ws.send(json.dumps(auth_message))
            
            # 等待认证响应（10秒超时）
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                auth_data = json.loads(response)
                
                # 处理响应格式
                if isinstance(auth_data, list):
                    auth_response = auth_data[0] if auth_data else {}
                else:
                    auth_response = auth_data
                
                # 检查认证结果
                if auth_response.get("T") == "success":
                    logger.info(f"✅ {endpoint['name']} 认证成功")
                    await ws.close()
                    return {"success": True, "endpoint": endpoint}
                    
                elif auth_response.get("T") == "error":
                    error_strategy = await self.handle_websocket_error(auth_response, "stock")
                    await ws.close()
                    return {
                        "success": False, 
                        "error": f"{endpoint['name']} 认证错误: {auth_response.get('msg')}",
                        "error_code": auth_response.get("code"),
                        "strategy": error_strategy
                    }
                else:
                    await ws.close()
                    return {
                        "success": False,
                        "error": f"{endpoint['name']} 认证响应格式未知: {auth_response}"
                    }
                    
            except asyncio.TimeoutError:
                logger.error(f"⏰ {endpoint['name']} 认证超时")
                await ws.close()
                return {
                    "success": False,
                    "error": f"{endpoint['name']} 认证超时 (>10秒)"
                }
                
        except Exception as e:
            logger.error(f"🔌 {endpoint['name']} 连接测试失败: {e}")
            return {
                "success": False,
                "error": f"{endpoint['name']} 连接异常: {str(e)}"
            }

    async def _connect_test_endpoint_fallback(self):
        """连接测试端点作为最后的回退方案"""
        logger.info("🆘 连接测试端点作为回退方案...")
        
        try:
            ssl_context = ssl.create_default_context()
            test_ws = await websockets.connect(
                self.TEST_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            # 认证
            auth_message = {
                "action": "auth",
                "key": self.account_config.api_key,
                "secret": self.account_config.secret_key
            }
            await test_ws.send(json.dumps(auth_message))
            
            # 等待认证响应
            response = await asyncio.wait_for(test_ws.recv(), timeout=10.0)
            auth_data = json.loads(response)
            
            auth_result = auth_data[0] if isinstance(auth_data, list) else auth_data
            if auth_result.get("T") != "success":
                raise Exception(f"测试端点认证失败: {auth_result}")
            
            # 订阅测试符号
            subscribe_msg = {
                "action": "subscribe",
                "trades": [self.TEST_SYMBOL],
                "quotes": [self.TEST_SYMBOL]
            }
            await test_ws.send(json.dumps(subscribe_msg))
            
            # 使用测试端点作为股票连接
            self.stock_ws = test_ws
            self.stock_connected = True
            self.current_stock_endpoint = {
                "name": "TEST",
                "url": self.TEST_WS_URL,
                "description": "测试端点回退 - 提供模拟数据"
            }
            
            logger.info("✅ 测试端点回退连接成功")
            
            # 启动监听任务
            asyncio.create_task(self._listen_stock_websocket())
            
        except Exception as e:
            logger.error(f"测试端点回退失败: {e}")
            raise e

    async def _connect_stock_websocket(self, symbols: List[str]):
        """连接股票WebSocket端点 - 直接使用IEX端点获取最快价格"""
        try:
            logger.info(f"🔌 连接IEX端点获取最快价格: {self.STOCK_WS_URL}")
            
            ssl_context = ssl.create_default_context()
            self.stock_ws = await websockets.connect(
                self.STOCK_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            # 认证
            auth_message = {
                "action": "auth",
                "key": self.account_config.api_key,
                "secret": self.account_config.secret_key
            }
            await self.stock_ws.send(json.dumps(auth_message))
            
            # 等待认证响应
            response = await self.stock_ws.recv()
            auth_data = json.loads(response)
            
            # Alpaca returns messages as arrays
            if isinstance(auth_data, list):
                auth_response = auth_data[0] if auth_data else {}
            else:
                auth_response = auth_data
            
            if auth_response.get("T") != "success":
                raise Exception(f"Stock WebSocket authentication failed: {auth_response}")
            
            logger.info("股票WebSocket认证成功")
            self.stock_connected = True
            
            # 订阅股票符号
            await self._subscribe_stock_symbols(symbols)
            
            # 启动股票数据监听任务
            asyncio.create_task(self._listen_stock_websocket())
            
        except Exception as e:
            logger.error(f"股票WebSocket连接失败: {e}")
            self.stock_connected = False
            raise e
    
    async def _connect_option_websocket(self, symbols: List[str]):
        """连接期权WebSocket端点"""
        try:
            ssl_context = ssl.create_default_context()
            self.option_ws = await websockets.connect(
                self.OPTION_WS_URL,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            # 认证 - 期权WebSocket使用MessagePack格式
            auth_message = {
                "action": "auth",
                "key": self.account_config.api_key,
                "secret": self.account_config.secret_key
            }
            packed_auth = msgpack.packb(auth_message)
            await self.option_ws.send(packed_auth)
            
            # 等待认证响应
            response = await self.option_ws.recv()
            
            # Try to parse as JSON first, then MsgPack
            try:
                if isinstance(response, str):
                    auth_data = json.loads(response)
                else:
                    # Try MsgPack for binary data
                    auth_data = msgpack.unpackb(response, raw=False)
            except (json.JSONDecodeError, msgpack.exceptions.ExtraData):
                # Fallback to string parsing
                try:
                    auth_data = json.loads(response.decode('utf-8'))
                except:
                    auth_data = msgpack.unpackb(response, raw=False)
            
            # Alpaca returns messages as arrays
            if isinstance(auth_data, list):
                auth_response = auth_data[0] if auth_data else {}
            else:
                auth_response = auth_data
            
            if auth_response.get("T") != "success":
                raise Exception(f"Option WebSocket authentication failed: {auth_response}")
            
            logger.info("期权WebSocket认证成功")
            self.option_connected = True
            
            # 订阅期权符号
            await self._subscribe_option_symbols(symbols)
            
            # 启动期权数据监听任务
            asyncio.create_task(self._listen_option_websocket())
            
        except Exception as e:
            logger.error(f"期权WebSocket连接失败: {e}")
            self.option_connected = False
            raise e
    
    async def _subscribe_stock_symbols(self, symbols: List[str]):
        """订阅股票符号"""
        if not self.stock_ws or not self.stock_connected:
            return
            
        # 订阅报价和交易数据
        subscribe_message = {
            "action": "subscribe",
            "quotes": symbols,
            "trades": symbols
        }
        
        await self.stock_ws.send(json.dumps(subscribe_message))
        logger.info(f"已订阅股票符号: {symbols}")
    
    async def _subscribe_option_symbols(self, symbols: List[str]):
        """订阅期权符号 - 使用MessagePack格式"""
        if not self.option_ws or not self.option_connected:
            return
            
        # 订阅报价和交易数据 - 期权必须使用MessagePack格式
        subscribe_message = {
            "action": "subscribe",
            "quotes": symbols,
            "trades": symbols
        }
        
        # 使用MessagePack编码发送消息
        packed_message = msgpack.packb(subscribe_message)
        await self.option_ws.send(packed_message)
        logger.info(f"已订阅期权符号 (MessagePack格式): {symbols}")
    
    async def _listen_stock_websocket(self):
        """监听股票WebSocket数据"""
        try:
            while self.stock_connected and not self._shutdown:
                try:
                    message = await asyncio.wait_for(self.stock_ws.recv(), timeout=30.0)
                    await self._process_stock_message(message)
                except asyncio.TimeoutError:
                    logger.warning("股票WebSocket接收超时")
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("股票WebSocket连接关闭")
                    break
        except Exception as e:
            logger.error(f"股票WebSocket监听错误: {e}")
        finally:
            self.stock_connected = False
            if not self._shutdown:
                logger.info("尝试重连股票WebSocket...")
                asyncio.create_task(self._reconnect_stock_websocket())
    
    async def _listen_option_websocket(self):
        """监听期权WebSocket数据"""
        try:
            while self.option_connected and not self._shutdown:
                try:
                    message = await asyncio.wait_for(self.option_ws.recv(), timeout=30.0)
                    await self._process_option_message(message)
                except asyncio.TimeoutError:
                    logger.warning("期权WebSocket接收超时")
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("期权WebSocket连接关闭")
                    break
        except Exception as e:
            logger.error(f"期权WebSocket监听错误: {e}")
        finally:
            self.option_connected = False
            if not self._shutdown:
                logger.info("尝试重连期权WebSocket...")
                asyncio.create_task(self._reconnect_option_websocket())
    
    async def _process_stock_message(self, message: Union[str, bytes]):
        """处理股票WebSocket消息"""
        try:
            # 尝试解析JSON消息
            if isinstance(message, str):
                data = json.loads(message)
            else:
                # 尝试解析MsgPack消息
                try:
                    data = msgpack.unpackb(message, raw=False)
                except:
                    data = json.loads(message.decode('utf-8'))
            
            # 处理不同类型的消息
            if isinstance(data, list):
                for item in data:
                    await self._handle_stock_data_item(item)
            else:
                await self._handle_stock_data_item(data)
                
        except Exception as e:
            logger.error(f"处理股票消息错误: {e}, 消息: {message[:200] if len(str(message)) > 200 else message}")
    
    async def _process_option_message(self, message: Union[str, bytes]):
        """处理期权WebSocket消息"""
        try:
            # 尝试解析JSON消息
            if isinstance(message, str):
                data = json.loads(message)
            else:
                # 尝试解析MsgPack消息
                try:
                    data = msgpack.unpackb(message, raw=False)
                except:
                    data = json.loads(message.decode('utf-8'))
            
            # 处理不同类型的消息
            if isinstance(data, list):
                for item in data:
                    await self._handle_option_data_item(item)
            else:
                await self._handle_option_data_item(data)
                
        except Exception as e:
            logger.error(f"处理期权消息错误: {e}, 消息: {message[:200] if len(str(message)) > 200 else message}")
    
    async def _handle_stock_data_item(self, item: dict):
        """处理单个股票数据项"""
        try:
            msg_type = item.get("T")
            
            # 更新消息时间戳（用于健康检查）
            self.last_message_time["stock"] = time.time()
            self.message_counts["stock"] = self.message_counts.get("stock", 0) + 1
            
            if msg_type == "q":  # Quote data
                await self._handle_quote_data("stock", item)
            elif msg_type == "t":  # Trade data
                await self._handle_trade_data("stock", item)
            elif msg_type in ["success", "subscription"]:
                logger.info(f"✅ 股票WebSocket状态消息: {item}")
            elif msg_type == "error":
                # 处理错误消息 - 使用改进的错误处理
                error_strategy = await self.handle_websocket_error(item, "stock")
                logger.error(f"股票WebSocket错误处理策略: {error_strategy['action']}")
                
                # 根据策略执行相应动作
                await self._execute_error_strategy(error_strategy, "stock")
                    
            else:
                logger.debug(f"未处理的股票消息类型: {msg_type}, 数据: {item}")
                
        except Exception as e:
            logger.error(f"处理股票数据项错误: {e}, 数据: {item}")
    
    async def _handle_option_data_item(self, item: dict):
        """处理单个期权数据项"""
        try:
            msg_type = item.get("T")
            
            # 更新消息时间戳（用于健康检查）
            self.last_message_time["option"] = time.time()
            self.message_counts["option"] = self.message_counts.get("option", 0) + 1
            
            if msg_type == "q":  # Quote data
                await self._handle_quote_data("option", item)
            elif msg_type == "t":  # Trade data
                await self._handle_trade_data("option", item)
            elif msg_type in ["success", "subscription"]:
                logger.info(f"✅ 期权WebSocket状态消息: {item}")
            elif msg_type == "error":
                # 处理错误消息 - 使用改进的错误处理
                error_strategy = await self.handle_websocket_error(item, "option")
                logger.error(f"期权WebSocket错误处理策略: {error_strategy['action']}")
                
                # 根据策略执行相应动作
                await self._execute_error_strategy(error_strategy, "option")
                    
            else:
                logger.debug(f"未处理的期权消息类型: {msg_type}, 数据: {item}")
                
        except Exception as e:
            logger.error(f"处理期权数据项错误: {e}, 数据: {item}")
    
    async def _execute_error_strategy(self, strategy: dict, endpoint_type: str):
        """根据错误策略执行相应的动作"""
        action = strategy["action"]
        
        if action == "try_iex_fallback" and endpoint_type == "stock":
            logger.info("🔄 尝试降级到IEX端点...")
            # 查找IEX端点
            iex_endpoint = next((ep for ep in self.STOCK_ENDPOINTS if ep['name'] == 'IEX'), None)
            if iex_endpoint and iex_endpoint != self.current_stock_endpoint:
                self.current_stock_endpoint = iex_endpoint
                logger.info("⬇️ 已切换到IEX端点，重新连接...")
                # 触发重连任务
                asyncio.create_task(self._reconnect_stock_websocket())
            else:
                logger.warning("⚠️ 没有可用的IEX端点或已在使用IEX端点")
                
        elif action == "wait_for_connection_slot":
            wait_time = strategy.get("wait_seconds", 30)
            logger.info(f"⏳ 连接数超限，等待 {wait_time} 秒后重试...")
            asyncio.create_task(self._delayed_reconnect(endpoint_type, wait_time))
            
        elif action == "reduce_symbols":
            max_symbols = strategy.get("max_symbols", 10)
            logger.info(f"📉 减少订阅符号数量到 {max_symbols} 个")
            # 这需要在上层处理，这里只记录
            await self._reduce_subscribed_symbols(max_symbols, endpoint_type)
            
        elif action == "wait_and_retry":
            wait_time = strategy.get("wait_seconds", 5)
            logger.info(f"⏳ 等待 {wait_time} 秒后重试连接...")
            asyncio.create_task(self._delayed_reconnect(endpoint_type, wait_time))
            
        elif action == "retry_with_exponential_backoff":
            logger.info("🔄 使用指数退避策略重试...")
            asyncio.create_task(self._exponential_backoff_reconnect(endpoint_type))
            
        elif action == "abort_invalid_credentials":
            logger.error("🚨 API凭证无效，停止尝试连接")
            self.connected = False
            if endpoint_type == "stock":
                self.stock_connected = False
            else:
                self.option_connected = False
                
        else:
            logger.info(f"📝 错误策略: {action} (仅记录)")
    
    async def _delayed_reconnect(self, endpoint_type: str, delay_seconds: int):
        """延迟重连"""
        await asyncio.sleep(delay_seconds)
        if endpoint_type == "stock":
            await self._reconnect_stock_websocket()
        else:
            await self._reconnect_option_websocket()
    
    async def _exponential_backoff_reconnect(self, endpoint_type: str, max_retries: int = 5):
        """指数退避重连"""
        for attempt in range(max_retries):
            wait_time = min(2 ** attempt, 300)  # 最大等待5分钟
            logger.info(f"⏳ 指数退避重连 (尝试 {attempt + 1}/{max_retries})，等待 {wait_time} 秒...")
            await asyncio.sleep(wait_time)
            
            try:
                if endpoint_type == "stock":
                    await self._reconnect_stock_websocket()
                else:
                    await self._reconnect_option_websocket()
                    
                # 检查是否重连成功
                if (endpoint_type == "stock" and self.stock_connected) or \
                   (endpoint_type == "option" and self.option_connected):
                    logger.info(f"✅ {endpoint_type} 重连成功")
                    return
            except Exception as e:
                logger.error(f"❌ {endpoint_type} 重连尝试 {attempt + 1} 失败: {e}")
        
        logger.error(f"🚨 {endpoint_type} 指数退避重连达到最大尝试次数")
    
    async def _reduce_subscribed_symbols(self, max_symbols: int, endpoint_type: str):
        """减少订阅的符号数量"""
        current_symbols = list(subscribed_symbols)
        
        if endpoint_type == "stock":
            stock_symbols = [s for s in current_symbols if not self._is_option_symbol(s)]
            if len(stock_symbols) > max_symbols:
                # 保留最重要的符号（默认股票）
                important_symbols = [s for s in DEFAULT_STOCKS if s in stock_symbols]
                remaining_symbols = [s for s in stock_symbols if s not in important_symbols]
                
                # 计算需要保留的数量
                keep_important = min(len(important_symbols), max_symbols)
                keep_remaining = max(0, max_symbols - keep_important)
                
                new_stock_symbols = important_symbols[:keep_important] + remaining_symbols[:keep_remaining]
                
                logger.info(f"📉 股票符号从 {len(stock_symbols)} 个减少到 {len(new_stock_symbols)} 个")
                logger.info(f"保留的股票符号: {new_stock_symbols}")
                
                # 重新订阅减少后的符号
                if self.stock_connected:
                    await self._subscribe_stock_symbols(new_stock_symbols)
        else:
            # 类似处理期权符号
            option_symbols = [s for s in current_symbols if self._is_option_symbol(s)]
            if len(option_symbols) > max_symbols:
                new_option_symbols = option_symbols[:max_symbols]
                logger.info(f"📉 期权符号从 {len(option_symbols)} 个减少到 {len(new_option_symbols)} 个")
                
                if self.option_connected:
                    await self._subscribe_option_symbols(new_option_symbols)

    async def _handle_quote_data(self, data_type: str, data: dict):
        """处理报价数据"""
        message = {
            "type": "quote",
            "data_type": data_type,
            "symbol": data.get("S"),
            "bid_price": data.get("bp"),
            "ask_price": data.get("ap"),
            "bid_size": data.get("bs"),
            "ask_size": data.get("as"),
            "timestamp": data.get("t") or datetime.now().isoformat()
        }
        
        await self.broadcast_to_all(message)
    
    async def _handle_trade_data(self, data_type: str, data: dict):
        """处理交易数据"""
        message = {
            "type": "trade",
            "data_type": data_type,
            "symbol": data.get("S"),
            "price": data.get("p"),
            "size": data.get("s"),
            "timestamp": data.get("t") or datetime.now().isoformat()
        }
        
        await self.broadcast_to_all(message)
    
    async def _reconnect_stock_websocket(self):
        """重连股票WebSocket"""
        if self._stock_reconnect_task and not self._stock_reconnect_task.done():
            return
            
        self._stock_reconnect_task = asyncio.create_task(self._do_stock_reconnect())
    
    async def _reconnect_option_websocket(self):
        """重连期权WebSocket"""
        if self._option_reconnect_task and not self._option_reconnect_task.done():
            return
            
        self._option_reconnect_task = asyncio.create_task(self._do_option_reconnect())
    
    async def _do_stock_reconnect(self):
        """执行股票WebSocket重连"""
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries and not self._shutdown:
            try:
                await asyncio.sleep(min(2 ** retry_count, 30))  # Exponential backoff
                
                # 重新获取需要订阅的股票符号
                stock_symbols = [s for s in subscribed_symbols if not self._is_option_symbol(s)]
                
                if stock_symbols:
                    await self._connect_stock_websocket(stock_symbols)
                    logger.info("股票WebSocket重连成功")
                    return
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"股票WebSocket重连失败 (尝试 {retry_count}/{max_retries}): {e}")
        
        logger.error("股票WebSocket重连达到最大尝试次数")
    
    async def _do_option_reconnect(self):
        """执行期权WebSocket重连"""
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries and not self._shutdown:
            try:
                await asyncio.sleep(min(2 ** retry_count, 30))  # Exponential backoff
                
                # 重新获取需要订阅的期权符号
                option_symbols = [s for s in subscribed_symbols if self._is_option_symbol(s)]
                
                if option_symbols:
                    await self._connect_option_websocket(option_symbols)
                    logger.info("期权WebSocket重连成功")
                    return
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"期权WebSocket重连失败 (尝试 {retry_count}/{max_retries}): {e}")
        
        logger.error("期权WebSocket重连达到最大尝试次数")
    
    async def shutdown(self):
        """关闭WebSocket连接"""
        logger.info("🛑 开始关闭WebSocket连接...")
        self._shutdown = True
        
        # 停止健康检查任务
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                logger.info("✅ 健康检查任务已停止")
        
        # 关闭WebSocket连接
        if self.stock_ws:
            await self.stock_ws.close()
            self.stock_connected = False
            logger.info("✅ 股票WebSocket连接已关闭")
            
        if self.option_ws:
            await self.option_ws.close()
            self.option_connected = False
            logger.info("✅ 期权WebSocket连接已关闭")
        
        logger.info("🎯 所有WebSocket连接和任务已关闭")
    
    def _is_option_symbol(self, symbol: str) -> bool:
        """判断是否为期权代码"""
        return len(symbol) > 10 and (symbol[-9] in ['C', 'P'])
    
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

# 全局WebSocket管理器
ws_manager = AlpacaWebSocketManager()

@ws_router.websocket("/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket端点 - 实时市场数据"""
    await websocket.accept()
    client_id = f"client_{datetime.now().timestamp()}"
    active_connections[client_id] = websocket
    
    logger.info(f"WebSocket客户端连接: {client_id}")
    
    try:
        # 首先初始化Alpaca连接 - 必须成功才能继续
        if not ws_manager.connected:
            await ws_manager.initialize()
        
        # 发送欢迎消息
        welcome_message = {
            "type": "welcome",
            "client_id": client_id,
            "message": "连接成功！正在建立Alpaca官方WebSocket数据流",
            "default_stocks": DEFAULT_STOCKS,
            "default_options": DEFAULT_OPTIONS,
            "data_source": f"Alpaca {ws_manager.account_config.account_id} - 官方WebSocket端点",
            "account_info": {
                "account_id": ws_manager.account_config.account_id,
                "tier": ws_manager.account_config.tier,
                "paper_trading": ws_manager.account_config.paper_trading
            },
            "capabilities": {
                "stock_data": True,
                "option_data": True,
                "real_time": True,
                "current_stock_endpoint": ws_manager.current_stock_endpoint,
                "option_endpoint": ws_manager.OPTION_WS_URL,
                "native_websocket": True,
                "intelligent_endpoint_selection": True,
                "production_features": {
                    "sip_data_available": ws_manager.current_stock_endpoint and ws_manager.current_stock_endpoint.get("name") == "SIP",
                    "iex_data_fallback": ws_manager.current_stock_endpoint and ws_manager.current_stock_endpoint.get("name") == "IEX",
                    "test_data_fallback": ws_manager.current_stock_endpoint and ws_manager.current_stock_endpoint.get("name") == "TEST",
                    "error_recovery": True,
                    "connection_limit_handling": True
                }
            }
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # 自动订阅默认股票和期权
        all_symbols = DEFAULT_STOCKS + DEFAULT_OPTIONS
        subscribed_symbols.update(all_symbols)
        
        # 启动数据订阅
        try:
            await ws_manager.subscribe_symbols(list(subscribed_symbols))
            logger.info(f"WebSocket订阅成功: {len(subscribed_symbols)} 个符号")
            
            # 发送订阅确认
            subscription_message = {
                "type": "subscription",
                "subscribed_symbols": list(subscribed_symbols),
                "message": f"成功订阅 {len(subscribed_symbols)} 个证券代码的真实数据流",
                "status": "active"
            }
            await websocket.send_text(json.dumps(subscription_message))
            
        except Exception as e:
            logger.error(f"WebSocket订阅失败: {e}")
            # 发送错误消息给客户端
            error_message = {
                "type": "error",
                "message": f"真实数据订阅失败: {str(e)}。系统配置为仅真实数据模式，无法提供服务。"
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
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
        "stock_ws_connected": ws_manager.stock_connected,
        "option_ws_connected": ws_manager.option_connected,
        "default_symbols": {
            "stocks": DEFAULT_STOCKS,
            "options": DEFAULT_OPTIONS
        },
        "websocket_endpoint": "/api/v1/ws/market-data",
        "connection_info": {
            "data_source": "Alpaca Official WebSocket API",
            "current_stock_endpoint": ws_manager.current_stock_endpoint,
            "available_stock_endpoints": ws_manager.STOCK_ENDPOINTS,
            "option_endpoint": ws_manager.OPTION_WS_URL,
            "real_time": True,
            "native_websocket": True,
            "supports_json_msgpack": True,
            "intelligent_fallback": True,
            "connection_limits": {
                "active_connections": ws_manager.active_connections_count,
                "limit_reached": ws_manager.connection_limit_reached,
                "max_allowed": getattr(ws_manager.account_config, 'max_connections', 'unknown') if ws_manager.account_config else 'unknown'
            }
        }
    }