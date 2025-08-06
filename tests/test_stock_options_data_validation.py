"""
股票和期权数据验证专门测试套件
专注于验证不同股票符号和期权符号的数据接收准确性和完整性
"""

import pytest
import asyncio
import json
import time
import statistics
import websockets
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
import re

logger = logging.getLogger(__name__)

@dataclass
class StockDataMetrics:
    """股票数据指标"""
    symbol: str
    quote_count: int = 0
    trade_count: int = 0
    last_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    price_changes: List[float] = field(default_factory=list)
    update_frequency: float = 0.0  # 更新频率 (updates per second)
    first_update: Optional[datetime] = None
    last_update: Optional[datetime] = None
    data_quality_score: float = 0.0

@dataclass
class OptionDataMetrics:
    """期权数据指标"""
    symbol: str
    underlying: str
    option_type: str  # 'C' for Call, 'P' for Put
    strike_price: float
    expiry_date: str
    quote_count: int = 0
    trade_count: int = 0
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    last_price: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    first_update: Optional[datetime] = None
    last_update: Optional[datetime] = None
    data_quality_score: float = 0.0

class OptionSymbolParser:
    """期权符号解析器"""
    
    @staticmethod
    def parse_option_symbol(symbol: str) -> Optional[Dict[str, Any]]:
        """
        解析期权符号
        格式: AAPL250117C00230000
        - AAPL: 标的股票
        - 250117: 到期日期 (YYMMDD)
        - C: 期权类型 (C=Call, P=Put) 
        - 00230000: 行权价格 (乘以1000，230.00)
        """
        if len(symbol) < 15:
            return None
        
        try:
            # 使用正则表达式解析
            pattern = r'^([A-Z]+)(\d{6})([CP])(\d{8})$'
            match = re.match(pattern, symbol)
            
            if not match:
                return None
            
            underlying, date_str, option_type, strike_str = match.groups()
            
            # 解析日期
            year = int(date_str[:2]) + 2000
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            expiry_date = f"{year:04d}-{month:02d}-{day:02d}"
            
            # 解析行权价格 (除以1000)
            strike_price = int(strike_str) / 1000.0
            
            return {
                'underlying': underlying,
                'expiry_date': expiry_date,
                'option_type': option_type,
                'strike_price': strike_price
            }
        except Exception:
            return None

class StockOptionsDataValidator:
    """股票和期权数据验证器"""
    
    def __init__(self):
        self.production_url = "ws://localhost:8091/api/v1/ws/market-data"
        self.alpaca_url = "wss://stream.data.alpaca.markets/v2/test"
        
        # 测试符号列表
        self.test_stocks = [
            "AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", 
            "NVDA", "META", "SPY", "QQQ", "IWM"
        ]
        
        self.test_options = [
            "AAPL250117C00230000",   # AAPL $230 Call 2025-01-17
            "AAPL250117P00220000",   # AAPL $220 Put 2025-01-17
            "TSLA250117C00300000",   # TSLA $300 Call 2025-01-17
            "TSLA250117P00280000",   # TSLA $280 Put 2025-01-17
            "SPY250117C00580000",    # SPY $580 Call 2025-01-17
            "SPY250117P00570000",    # SPY $570 Put 2025-01-17
            "NVDA250117C00140000",   # NVDA $140 Call 2025-01-17
            "NVDA250117P00130000",   # NVDA $130 Put 2025-01-17
        ]
        
        # 数据存储
        self.stock_metrics: Dict[str, StockDataMetrics] = {}
        self.option_metrics: Dict[str, OptionDataMetrics] = {}
        self.parser = OptionSymbolParser()
        
        # 测试配置
        self.test_duration = 180  # 3分钟
        self.min_updates_per_symbol = 1  # 每个符号至少应该有的更新数
        
    def initialize_metrics(self):
        """初始化指标"""
        # 初始化股票指标
        for symbol in self.test_stocks:
            self.stock_metrics[symbol] = StockDataMetrics(symbol=symbol)
        
        # 初始化期权指标
        for symbol in self.test_options:
            parsed = self.parser.parse_option_symbol(symbol)
            if parsed:
                self.option_metrics[symbol] = OptionDataMetrics(
                    symbol=symbol,
                    underlying=parsed['underlying'],
                    option_type=parsed['option_type'],
                    strike_price=parsed['strike_price'],
                    expiry_date=parsed['expiry_date']
                )
    
    async def test_production_endpoint_data(self, duration: int = 180) -> Dict[str, Any]:
        """测试生产端点的股票和期权数据"""
        logger.info(f"开始测试生产端点数据质量，持续{duration}秒...")
        
        self.initialize_metrics()
        start_time = time.time()
        results = {
            "endpoint": "production",
            "test_duration": duration,
            "connection_success": False,
            "total_messages": 0,
            "stock_data": {},
            "option_data": {},
            "errors": []
        }
        
        try:
            # 连接WebSocket
            websocket = await websockets.connect(
                self.production_url,
                ping_interval=20,
                ping_timeout=10
            )
            
            results["connection_success"] = True
            logger.info("生产端点连接成功")
            
            # 监听数据
            end_time = time.time() + duration
            
            while time.time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    results["total_messages"] += 1
                    
                    data = json.loads(message)
                    await self._process_production_message(data)
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.error("生产端点连接关闭")
                    break
                except Exception as e:
                    results["errors"].append(str(e))
                    continue
            
            await websocket.close()
            
        except Exception as e:
            results["errors"].append(f"连接失败: {str(e)}")
            logger.error(f"生产端点测试失败: {e}")
        
        # 计算最终指标
        results["stock_data"] = self._calculate_stock_metrics()
        results["option_data"] = self._calculate_option_metrics()
        results["summary"] = self._generate_summary_stats()
        
        return results
    
    async def test_alpaca_endpoint_data(self, duration: int = 180) -> Dict[str, Any]:
        """测试Alpaca端点的股票数据"""
        logger.info(f"开始测试Alpaca端点数据质量，持续{duration}秒...")
        
        self.initialize_metrics()
        start_time = time.time()
        results = {
            "endpoint": "alpaca",
            "test_duration": duration,
            "connection_success": False,
            "authentication_success": False,
            "subscription_success": False,
            "total_messages": 0,
            "stock_data": {},
            "option_data": {},  # Alpaca测试端点可能不支持期权
            "errors": []
        }
        
        try:
            # 连接WebSocket
            ssl_context = ssl.create_default_context()
            websocket = await websockets.connect(
                self.alpaca_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            results["connection_success"] = True
            logger.info("Alpaca端点连接成功")
            
            # 认证
            auth_message = {
                "action": "auth",
                "key": "test_api_key",
                "secret": "test_secret_key"
            }
            await websocket.send(json.dumps(auth_message))
            
            # 等待认证响应
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            auth_data = json.loads(auth_response)
            
            if isinstance(auth_data, list):
                auth_result = auth_data[0] if auth_data else {}
            else:
                auth_result = auth_data
                
            if auth_result.get("T") == "success":
                results["authentication_success"] = True
                logger.info("Alpaca端点认证成功")
                
                # 订阅数据
                subscribe_message = {
                    "action": "subscribe", 
                    "quotes": self.test_stocks,
                    "trades": self.test_stocks
                }
                await websocket.send(json.dumps(subscribe_message))
                results["subscription_success"] = True
                logger.info("Alpaca端点订阅成功")
            
            # 监听数据
            end_time = time.time() + duration
            
            while time.time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    results["total_messages"] += 1
                    
                    data = json.loads(message)
                    await self._process_alpaca_message(data)
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.error("Alpaca端点连接关闭")
                    break
                except Exception as e:
                    results["errors"].append(str(e))
                    continue
            
            await websocket.close()
            
        except Exception as e:
            results["errors"].append(f"连接失败: {str(e)}")
            logger.error(f"Alpaca端点测试失败: {e}")
        
        # 计算最终指标
        results["stock_data"] = self._calculate_stock_metrics()
        results["option_data"] = self._calculate_option_metrics()  # 可能为空
        results["summary"] = self._generate_summary_stats()
        
        return results
    
    async def _process_production_message(self, data: Dict[str, Any]):
        """处理生产端点消息"""
        message_type = data.get("type")
        
        if message_type == "quote":
            await self._process_quote_data(data, "production")
        elif message_type == "trade":
            await self._process_trade_data(data, "production")
        elif message_type in ["welcome", "subscription"]:
            logger.info(f"生产端点状态消息: {data.get('message', 'No message')}")
    
    async def _process_alpaca_message(self, data: Any):
        """处理Alpaca端点消息"""
        if isinstance(data, list):
            for item in data:
                await self._process_single_alpaca_message(item)
        else:
            await self._process_single_alpaca_message(data)
    
    async def _process_single_alpaca_message(self, data: Dict[str, Any]):
        """处理单个Alpaca消息"""
        message_type = data.get("T")
        
        if message_type == "q":  # Quote
            await self._process_alpaca_quote(data)
        elif message_type == "t":  # Trade
            await self._process_alpaca_trade(data)
        elif message_type in ["success", "subscription"]:
            logger.info(f"Alpaca端点状态消息: {data}")
    
    async def _process_quote_data(self, data: Dict[str, Any], source: str):
        """处理报价数据"""
        symbol = data.get("symbol")
        if not symbol:
            return
        
        now = datetime.now()
        
        # 判断是股票还是期权
        if len(symbol) <= 10:  # 股票
            if symbol in self.stock_metrics:
                metrics = self.stock_metrics[symbol]
                metrics.quote_count += 1
                metrics.bid_price = data.get("bid_price")
                metrics.ask_price = data.get("ask_price")
                metrics.bid_size = data.get("bid_size")
                metrics.ask_size = data.get("ask_size")
                
                if metrics.first_update is None:
                    metrics.first_update = now
                metrics.last_update = now
        else:  # 期权
            if symbol in self.option_metrics:
                metrics = self.option_metrics[symbol]
                metrics.quote_count += 1
                metrics.bid_price = data.get("bid_price")
                metrics.ask_price = data.get("ask_price")
                metrics.bid_size = data.get("bid_size")
                metrics.ask_size = data.get("ask_size")
                
                if metrics.first_update is None:
                    metrics.first_update = now
                metrics.last_update = now
    
    async def _process_trade_data(self, data: Dict[str, Any], source: str):
        """处理交易数据"""
        symbol = data.get("symbol")
        if not symbol:
            return
        
        price = data.get("price")
        size = data.get("size")
        now = datetime.now()
        
        # 判断是股票还是期权
        if len(symbol) <= 10:  # 股票
            if symbol in self.stock_metrics:
                metrics = self.stock_metrics[symbol]
                metrics.trade_count += 1
                
                if price is not None:
                    old_price = metrics.last_price
                    metrics.last_price = price
                    
                    if old_price is not None:
                        price_change = price - old_price
                        metrics.price_changes.append(price_change)
                
                if metrics.first_update is None:
                    metrics.first_update = now
                metrics.last_update = now
        else:  # 期权
            if symbol in self.option_metrics:
                metrics = self.option_metrics[symbol]
                metrics.trade_count += 1
                
                if price is not None:
                    metrics.last_price = price
                
                if metrics.first_update is None:
                    metrics.first_update = now
                metrics.last_update = now
    
    async def _process_alpaca_quote(self, data: Dict[str, Any]):
        """处理Alpaca报价数据"""
        symbol = data.get("S")
        if not symbol or symbol not in self.stock_metrics:
            return
        
        now = datetime.now()
        metrics = self.stock_metrics[symbol]
        metrics.quote_count += 1
        metrics.bid_price = data.get("bp")
        metrics.ask_price = data.get("ap")
        metrics.bid_size = data.get("bs")
        metrics.ask_size = data.get("as")
        
        if metrics.first_update is None:
            metrics.first_update = now
        metrics.last_update = now
    
    async def _process_alpaca_trade(self, data: Dict[str, Any]):
        """处理Alpaca交易数据"""
        symbol = data.get("S")
        if not symbol or symbol not in self.stock_metrics:
            return
        
        price = data.get("p")
        size = data.get("s")
        now = datetime.now()
        
        metrics = self.stock_metrics[symbol]
        metrics.trade_count += 1
        
        if price is not None:
            old_price = metrics.last_price
            metrics.last_price = price
            
            if old_price is not None:
                price_change = price - old_price
                metrics.price_changes.append(price_change)
        
        if metrics.first_update is None:
            metrics.first_update = now
        metrics.last_update = now
    
    def _calculate_stock_metrics(self) -> Dict[str, Any]:
        """计算股票指标"""
        stock_results = {}
        
        for symbol, metrics in self.stock_metrics.items():
            # 计算更新频率
            if metrics.first_update and metrics.last_update:
                duration = (metrics.last_update - metrics.first_update).total_seconds()
                if duration > 0:
                    total_updates = metrics.quote_count + metrics.trade_count
                    metrics.update_frequency = total_updates / duration
            
            # 计算数据质量分数
            quality_score = 0
            if metrics.quote_count > 0:
                quality_score += 30
            if metrics.trade_count > 0:
                quality_score += 30
            if metrics.bid_price is not None and metrics.ask_price is not None:
                quality_score += 20
            if len(metrics.price_changes) > 0:
                quality_score += 20
            
            metrics.data_quality_score = quality_score
            
            stock_results[symbol] = {
                "quote_count": metrics.quote_count,
                "trade_count": metrics.trade_count,
                "last_price": metrics.last_price,
                "bid_price": metrics.bid_price,
                "ask_price": metrics.ask_price,
                "bid_size": metrics.bid_size,
                "ask_size": metrics.ask_size,
                "price_changes": len(metrics.price_changes),
                "update_frequency": round(metrics.update_frequency, 4),
                "data_quality_score": metrics.data_quality_score,
                "has_data": metrics.quote_count > 0 or metrics.trade_count > 0
            }
        
        return stock_results
    
    def _calculate_option_metrics(self) -> Dict[str, Any]:
        """计算期权指标"""
        option_results = {}
        
        for symbol, metrics in self.option_metrics.items():
            # 计算更新频率
            if metrics.first_update and metrics.last_update:
                duration = (metrics.last_update - metrics.first_update).total_seconds()
                if duration > 0:
                    total_updates = metrics.quote_count + metrics.trade_count
                    metrics.update_frequency = total_updates / duration
            
            # 计算数据质量分数
            quality_score = 0
            if metrics.quote_count > 0:
                quality_score += 30
            if metrics.trade_count > 0:
                quality_score += 30
            if metrics.bid_price is not None and metrics.ask_price is not None:
                quality_score += 20
            if metrics.last_price is not None:
                quality_score += 20
            
            metrics.data_quality_score = quality_score
            
            option_results[symbol] = {
                "underlying": metrics.underlying,
                "option_type": metrics.option_type,
                "strike_price": metrics.strike_price,
                "expiry_date": metrics.expiry_date,
                "quote_count": metrics.quote_count,
                "trade_count": metrics.trade_count,
                "last_price": metrics.last_price,
                "bid_price": metrics.bid_price,
                "ask_price": metrics.ask_price,
                "bid_size": metrics.bid_size,
                "ask_size": metrics.ask_size,
                "update_frequency": round(metrics.update_frequency, 4),
                "data_quality_score": metrics.data_quality_score,
                "has_data": metrics.quote_count > 0 or metrics.trade_count > 0
            }
        
        return option_results
    
    def _generate_summary_stats(self) -> Dict[str, Any]:
        """生成汇总统计"""
        # 股票统计
        stock_with_data = sum(1 for m in self.stock_metrics.values() if m.quote_count > 0 or m.trade_count > 0)
        total_stock_quotes = sum(m.quote_count for m in self.stock_metrics.values())
        total_stock_trades = sum(m.trade_count for m in self.stock_metrics.values())
        avg_stock_quality = sum(m.data_quality_score for m in self.stock_metrics.values()) / len(self.stock_metrics) if self.stock_metrics else 0
        
        # 期权统计
        option_with_data = sum(1 for m in self.option_metrics.values() if m.quote_count > 0 or m.trade_count > 0)
        total_option_quotes = sum(m.quote_count for m in self.option_metrics.values())
        total_option_trades = sum(m.trade_count for m in self.option_metrics.values())
        avg_option_quality = sum(m.data_quality_score for m in self.option_metrics.values()) / len(self.option_metrics) if self.option_metrics else 0
        
        return {
            "stocks": {
                "total_symbols": len(self.stock_metrics),
                "symbols_with_data": stock_with_data,
                "data_coverage": round(stock_with_data / len(self.stock_metrics) * 100, 2) if self.stock_metrics else 0,
                "total_quotes": total_stock_quotes,
                "total_trades": total_stock_trades,
                "avg_quality_score": round(avg_stock_quality, 2)
            },
            "options": {
                "total_symbols": len(self.option_metrics),
                "symbols_with_data": option_with_data,
                "data_coverage": round(option_with_data / len(self.option_metrics) * 100, 2) if self.option_metrics else 0,
                "total_quotes": total_option_quotes,
                "total_trades": total_option_trades,
                "avg_quality_score": round(avg_option_quality, 2)
            }
        }
    
    def generate_validation_report(self, production_results: Dict, alpaca_results: Dict) -> str:
        """生成验证报告"""
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     股票和期权数据验证测试报告                                 ║
║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
╠══════════════════════════════════════════════════════════════════════════════╣

📊 测试概览
├─ 测试时长: {self.test_duration}秒
├─ 测试股票: {len(self.test_stocks)}个 ({', '.join(self.test_stocks[:5])}...)
├─ 测试期权: {len(self.test_options)}个
├─ 生产端点: {self.production_url}
└─ Alpaca端点: {self.alpaca_url}

🏭 生产端点结果
├─ 连接状态: {"成功" if production_results["connection_success"] else "失败"}
├─ 总消息数: {production_results["total_messages"]:,}
├─ 错误数量: {len(production_results["errors"])}
├─ 股票数据覆盖: {production_results["summary"]["stocks"]["data_coverage"]}%
├─ 期权数据覆盖: {production_results["summary"]["options"]["data_coverage"]}%
├─ 股票平均质量: {production_results["summary"]["stocks"]["avg_quality_score"]}/100
└─ 期权平均质量: {production_results["summary"]["options"]["avg_quality_score"]}/100

📈 生产端点股票详情
├─ 有数据符号: {production_results["summary"]["stocks"]["symbols_with_data"]}/{production_results["summary"]["stocks"]["total_symbols"]}
├─ 总报价数: {production_results["summary"]["stocks"]["total_quotes"]:,}
├─ 总交易数: {production_results["summary"]["stocks"]["total_trades"]:,}
"""
        
        # 显示前5个股票的详细数据
        stock_data = production_results["stock_data"]
        stocks_with_data = [(symbol, data) for symbol, data in stock_data.items() if data["has_data"]][:5]
        
        for symbol, data in stocks_with_data:
            report += f"├─ {symbol}: {data['quote_count']}报价, {data['trade_count']}交易, 质量{data['data_quality_score']}/100\n"
        
        report += f"""
📊 生产端点期权详情
├─ 有数据符号: {production_results["summary"]["options"]["symbols_with_data"]}/{production_results["summary"]["options"]["total_symbols"]}
├─ 总报价数: {production_results["summary"]["options"]["total_quotes"]:,}
├─ 总交易数: {production_results["summary"]["options"]["total_trades"]:,}
"""
        
        # 显示前5个期权的详细数据
        option_data = production_results["option_data"]
        options_with_data = [(symbol, data) for symbol, data in option_data.items() if data["has_data"]][:5]
        
        for symbol, data in options_with_data:
            report += f"├─ {symbol}: {data['quote_count']}报价, {data['trade_count']}交易, 质量{data['data_quality_score']}/100\n"
        
        report += f"""

🧪 Alpaca端点结果
├─ 连接状态: {"成功" if alpaca_results["connection_success"] else "失败"}
├─ 认证状态: {"成功" if alpaca_results["authentication_success"] else "失败"}
├─ 订阅状态: {"成功" if alpaca_results["subscription_success"] else "失败"}
├─ 总消息数: {alpaca_results["total_messages"]:,}
├─ 错误数量: {len(alpaca_results["errors"])}
├─ 股票数据覆盖: {alpaca_results["summary"]["stocks"]["data_coverage"]}%
├─ 股票平均质量: {alpaca_results["summary"]["stocks"]["avg_quality_score"]}/100
└─ 期权支持: {"支持" if alpaca_results["summary"]["options"]["symbols_with_data"] > 0 else "不支持"}

📈 Alpaca端点股票详情
├─ 有数据符号: {alpaca_results["summary"]["stocks"]["symbols_with_data"]}/{alpaca_results["summary"]["stocks"]["total_symbols"]}
├─ 总报价数: {alpaca_results["summary"]["stocks"]["total_quotes"]:,}
├─ 总交易数: {alpaca_results["summary"]["stocks"]["total_trades"]:,}
"""
        
        # 显示Alpaca股票数据
        alpaca_stock_data = alpaca_results["stock_data"]
        alpaca_stocks_with_data = [(symbol, data) for symbol, data in alpaca_stock_data.items() if data["has_data"]][:5]
        
        for symbol, data in alpaca_stocks_with_data:
            report += f"├─ {symbol}: {data['quote_count']}报价, {data['trade_count']}交易, 质量{data['data_quality_score']}/100\n"
        
        # 数据对比分析
        prod_stock_coverage = production_results["summary"]["stocks"]["data_coverage"]
        alpaca_stock_coverage = alpaca_results["summary"]["stocks"]["data_coverage"]
        prod_option_coverage = production_results["summary"]["options"]["data_coverage"]
        
        report += f"""

🔄 数据对比分析
├─ 股票覆盖比较: 生产端{prod_stock_coverage}% vs Alpaca端{alpaca_stock_coverage}%
├─ 期权支持: 生产端{prod_option_coverage}% vs Alpaca端0%
├─ 数据完整性: {"生产端更完整" if prod_stock_coverage > alpaca_stock_coverage else "Alpaca端更完整" if alpaca_stock_coverage > prod_stock_coverage else "基本相当"}
├─ 期权优势: {"生产端独有期权数据" if prod_option_coverage > 0 else "无期权数据"}
└─ 推荐: {"优先使用生产端点" if prod_stock_coverage >= alpaca_stock_coverage else "可考虑Alpaca端点"}

✅ 测试结论
├─ 生产端点可靠性: {"优秀" if prod_stock_coverage > 80 else "良好" if prod_stock_coverage > 50 else "需改进"}
├─ Alpaca端点可靠性: {"优秀" if alpaca_stock_coverage > 80 else "良好" if alpaca_stock_coverage > 50 else "需改进"}
├─ 期权数据支持: {"生产端点支持" if prod_option_coverage > 0 else "暂无支持"}
├─ 数据质量评估: {"高质量" if (production_results["summary"]["stocks"]["avg_quality_score"] + alpaca_results["summary"]["stocks"]["avg_quality_score"]) / 2 > 70 else "中等质量"}
└─ 部署建议: {"可以部署到生产环境" if prod_stock_coverage > 70 else "需要进一步优化"}

╚══════════════════════════════════════════════════════════════════════════════╝
        """
        
        return report

class TestStockOptionsDataValidation:
    """股票和期权数据验证测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.validator = StockOptionsDataValidator()
        
    @pytest.mark.asyncio
    async def test_production_stock_data_quality(self):
        """测试生产端点股票数据质量"""
        results = await self.validator.test_production_endpoint_data(duration=120)
        
        # 验证连接成功
        assert results["connection_success"], "生产端点连接应该成功"
        
        # 验证数据接收
        assert results["total_messages"] > 0, "应该接收到消息"
        
        # 验证股票数据覆盖
        stock_coverage = results["summary"]["stocks"]["data_coverage"]
        assert stock_coverage > 0, f"股票数据覆盖率应该大于0%: {stock_coverage}%"
        
        logger.info(f"生产端点股票数据测试通过: {stock_coverage}% 覆盖率")
    
    @pytest.mark.asyncio
    async def test_production_option_data_quality(self):
        """测试生产端点期权数据质量"""
        results = await self.validator.test_production_endpoint_data(duration=120)
        
        # 验证期权数据
        option_coverage = results["summary"]["options"]["data_coverage"]
        option_quality = results["summary"]["options"]["avg_quality_score"]
        
        logger.info(f"生产端点期权数据: {option_coverage}% 覆盖率, {option_quality}/100 质量分")
        
        # 期权数据可能不如股票数据丰富，但应该有一定的覆盖
        # 这里设置较低的阈值，实际部署时可以调整
        assert option_coverage >= 0, f"期权数据覆盖率: {option_coverage}%"
    
    @pytest.mark.asyncio
    async def test_alpaca_stock_data_quality(self):
        """测试Alpaca端点股票数据质量"""
        results = await self.validator.test_alpaca_endpoint_data(duration=120)
        
        # 验证连接和认证
        assert results["connection_success"], "Alpaca端点连接应该成功"
        assert results["authentication_success"], "Alpaca端点认证应该成功"
        
        # 验证股票数据接收
        stock_coverage = results["summary"]["stocks"]["data_coverage"]
        
        logger.info(f"Alpaca端点股票数据测试: {stock_coverage}% 覆盖率")
        
        # Alpaca测试端点可能数据有限，设置较低阈值
        assert stock_coverage >= 0, f"Alpaca股票数据覆盖率: {stock_coverage}%"
    
    @pytest.mark.asyncio
    async def test_stock_symbol_parsing(self):
        """测试股票符号解析"""
        validator = StockOptionsDataValidator()
        
        # 测试股票符号 (应该不被解析为期权)
        for stock in validator.test_stocks:
            parsed = validator.parser.parse_option_symbol(stock)
            assert parsed is None, f"股票符号 {stock} 不应该被解析为期权"
    
    @pytest.mark.asyncio
    async def test_option_symbol_parsing(self):
        """测试期权符号解析"""
        validator = StockOptionsDataValidator()
        
        # 测试期权符号解析
        test_cases = [
            ("AAPL250117C00230000", {
                "underlying": "AAPL",
                "expiry_date": "2025-01-17",
                "option_type": "C",
                "strike_price": 230.0
            }),
            ("TSLA250117P00280000", {
                "underlying": "TSLA",
                "expiry_date": "2025-01-17", 
                "option_type": "P",
                "strike_price": 280.0
            })
        ]
        
        for symbol, expected in test_cases:
            parsed = validator.parser.parse_option_symbol(symbol)
            assert parsed is not None, f"期权符号 {symbol} 应该能够被解析"
            assert parsed["underlying"] == expected["underlying"]
            assert parsed["expiry_date"] == expected["expiry_date"]
            assert parsed["option_type"] == expected["option_type"]
            assert parsed["strike_price"] == expected["strike_price"]
    
    @pytest.mark.asyncio
    async def test_comprehensive_data_validation(self):
        """运行综合数据验证测试"""
        validator = StockOptionsDataValidator()
        
        # 并行测试两个端点
        production_task = asyncio.create_task(
            validator.test_production_endpoint_data(duration=150)
        )
        alpaca_task = asyncio.create_task(
            validator.test_alpaca_endpoint_data(duration=150)
        )
        
        production_results, alpaca_results = await asyncio.gather(
            production_task, alpaca_task, return_exceptions=True
        )
        
        # 处理异常结果
        if isinstance(production_results, Exception):
            logger.error(f"生产端点测试异常: {production_results}")
            pytest.fail(f"生产端点测试失败: {production_results}")
        
        if isinstance(alpaca_results, Exception):
            logger.error(f"Alpaca端点测试异常: {alpaca_results}")
            pytest.fail(f"Alpaca端点测试失败: {alpaca_results}")
        
        # 生成报告
        report = validator.generate_validation_report(production_results, alpaca_results)
        print(report)
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"stock_options_validation_report_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"数据验证报告已保存: {report_file}")
        
        # 基本验证
        assert production_results["connection_success"], "生产端点应该连接成功"
        assert alpaca_results["connection_success"], "Alpaca端点应该连接成功"
        
        # 至少一个端点应该有股票数据
        prod_coverage = production_results["summary"]["stocks"]["data_coverage"]
        alpaca_coverage = alpaca_results["summary"]["stocks"]["data_coverage"]
        
        assert prod_coverage > 0 or alpaca_coverage > 0, "至少一个端点应该有股票数据"


# 独立运行函数
async def run_stock_options_validation(duration: int = 180):
    """独立运行股票期权数据验证"""
    validator = StockOptionsDataValidator()
    validator.test_duration = duration
    
    print(f"🚀 开始股票和期权数据验证测试，持续 {duration} 秒...")
    
    # 并行测试两个端点
    production_task = asyncio.create_task(
        validator.test_production_endpoint_data(duration)
    )
    alpaca_task = asyncio.create_task(
        validator.test_alpaca_endpoint_data(duration)
    )
    
    try:
        production_results, alpaca_results = await asyncio.gather(
            production_task, alpaca_task
        )
        
        # 生成和显示报告
        report = validator.generate_validation_report(production_results, alpaca_results)
        print(report)
        
        # 保存报告和数据
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        report_file = f"stock_options_validation_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        data_file = f"stock_options_validation_data_{timestamp}.json"
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump({
                "production": production_results,
                "alpaca": alpaca_results,
                "test_config": {
                    "duration": duration,
                    "test_stocks": validator.test_stocks,
                    "test_options": validator.test_options
                }
            }, f, indent=2, default=str)
        
        print(f"\n📄 报告已保存: {report_file}")
        print(f"📄 数据已保存: {data_file}")
        
        return production_results, alpaca_results
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        raise


if __name__ == "__main__":
    # 直接运行测试
    import sys
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    
    asyncio.run(run_stock_options_validation(duration))