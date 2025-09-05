"""
价格追踪器
负责获取和追踪期权的实时价格数据
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
from app.account_pool import AccountPool
from app.alpaca_client import AlpacaClient
from .api_client import AlpacaAPIClient
from .position_manager import Position


class OptionQuote:
    """期权报价数据类"""
    def __init__(self, data: dict):
        self.symbol = data.get('symbol')
        self.bid_price = float(data.get('bid_price') or 0)
        self.ask_price = float(data.get('ask_price') or 0)
        self.last_price = float(data.get('last_price') or 0)
        self.mark_price = float(data.get('mark_price') or 0)
        self.bid_size = int(data.get('bid_size') or 0)
        self.ask_size = int(data.get('ask_size') or 0)
        self.timestamp = data.get('timestamp', datetime.now().isoformat())
        
    @property
    def mid_price(self) -> float:
        """中间价"""
        if self.bid_price > 0 and self.ask_price > 0:
            return (self.bid_price + self.ask_price) / 2
        return self.last_price or self.mark_price
    
    @property
    def current_price(self) -> float:
        """当前价格（用于策略计算）"""
        # 优先使用买一价（类似Tiger的逻辑）
        if self.bid_price > 0:
            return self.bid_price
        # 其次使用最后成交价
        if self.last_price > 0:
            return self.last_price
        # 最后使用中间价
        return self.mid_price


class PriceTracker:
    def __init__(self, account_pool: AccountPool, api_client: Optional[AlpacaAPIClient] = None):
        if account_pool is None:
            raise TypeError("account_pool cannot be None")
        self.account_pool = account_pool
        # API客户端用于替代直接连接池访问（可选）
        self.api_client = api_client
        self.use_api_client = api_client is not None
        self._price_cache: Dict[str, OptionQuote] = {}
        self._price_history: Dict[str, List[OptionQuote]] = {}
        
    async def get_option_quotes(self, symbols: List[str]) -> Dict[str, OptionQuote]:
        """
        获取期权报价 - 支持API客户端或直接连接池访问
        
        Args:
            symbols: 期权符号列表
            
        Returns:
            期权符号到报价的映射字典
        """
        if self.use_api_client:
            return await self._get_option_quotes_via_api(symbols)
        else:
            return await self._get_option_quotes_via_pool(symbols)
    
    async def _get_option_quotes_via_api(self, symbols: List[str]) -> Dict[str, OptionQuote]:
        """通过 API 客户端获取期权报价"""
        if not symbols:
            return {}
        
        quotes = {}
        
        try:
            logger.debug(f"使用 API 客户端获取 {len(symbols)} 个期权报价")
            
            # 分批获取报价（API限制每次最多20个符号）
            batch_size = 20  # API限制每次最多20个符号
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                batch_quotes_data = await self.api_client.get_option_quotes(batch_symbols)
                
                if batch_quotes_data and 'quotes' in batch_quotes_data:
                    for quote_data in batch_quotes_data['quotes']:
                        symbol = quote_data.get('symbol')
                        if symbol and "error" not in quote_data:
                            quotes[symbol] = OptionQuote(quote_data)
            
            # 更新缓存
            self._price_cache.update(quotes)
            
            # 更新价格历史
            for symbol, quote in quotes.items():
                if symbol not in self._price_history:
                    self._price_history[symbol] = []
                self._price_history[symbol].append(quote)
                # 只保留最近的10个价格记录
                self._price_history[symbol] = self._price_history[symbol][-10:]
            
            logger.debug(f"通过 API 成功获取 {len(quotes)}/{len(symbols)} 个期权报价")
            return quotes
            
        except Exception as e:
            logger.error(f"通过 API 获取期权报价失败: {e}")
            return quotes
    
    async def _get_option_quotes_via_pool(self, symbols: List[str]) -> Dict[str, OptionQuote]:
        """通过连接池获取期权报价（原始方法）"""
        if not symbols:
            return {}
        
        quotes = {}
        
        try:
            # 优先使用stock_ws账户获取报价（避免冲突）
            accounts = await self.account_pool.get_all_accounts()
            if not accounts:
                logger.error("没有可用的账户连接")
                return quotes
            
            # 查找stock_ws账户
            stock_ws_connection = None
            for account_id, connection in accounts.items():
                if account_id == 'stock_ws':
                    stock_ws_connection = connection
                    logger.debug(f"使用stock_ws账户进行期权询价")
                    break
            
            # 如果没有stock_ws账户，使用第一个可用账户
            if stock_ws_connection is None:
                stock_ws_connection = list(accounts.values())[0]
                first_account_id = list(accounts.keys())[0]
                logger.warning(f"未找到stock_ws账户，使用 {first_account_id} 进行询价")
            
            first_client = stock_ws_connection.alpaca_client
            
            # 分批获取报价（API限制每次最多20个符号）
            batch_size = 20  # API限制每次最多20个符号
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                batch_quotes = await self._get_quotes_batch(first_client, batch_symbols)
                quotes.update(batch_quotes)
            
            # 更新缓存
            self._price_cache.update(quotes)
            
            # 更新价格历史
            for symbol, quote in quotes.items():
                if symbol not in self._price_history:
                    self._price_history[symbol] = []
                self._price_history[symbol].append(quote)
                # 只保留最近的10个价格记录
                self._price_history[symbol] = self._price_history[symbol][-10:]
            
            logger.debug(f"通过连接池成功获取 {len(quotes)}/{len(symbols)} 个期权报价")
            return quotes
            
        except Exception as e:
            logger.error(f"通过连接池获取期权报价失败: {e}")
            return quotes
    
    async def _get_quotes_batch(self, client, symbols: List[str]) -> Dict[str, OptionQuote]:
        """
        批量获取期权报价
        
        Args:
            client: Alpaca客户端对象
            symbols: 期权符号列表
            
        Returns:
            期权报价字典
        """
        quotes = {}
        
        try:
            # 获取期权报价数据
            quotes_response = await client.get_multiple_option_quotes(symbols)
            
            # 检查是否有错误
            if "error" in quotes_response:
                logger.error(f"获取期权报价失败: {quotes_response['error']}")
                return quotes
            
            # 提取报价数据
            quotes_data = quotes_response.get('quotes', [])
            for quote_data in quotes_data:
                symbol = quote_data.get('symbol')
                if symbol and "error" not in quote_data:
                    quotes[symbol] = OptionQuote(quote_data)
            
            return quotes
            
        except Exception as e:
            logger.error(f"批量获取报价失败: {e}")
            return quotes
    
    async def get_position_prices(self, positions: List[Position]) -> Dict[str, OptionQuote]:
        """
        获取持仓的当前价格
        
        Args:
            positions: 持仓列表
            
        Returns:
            期权符号到报价的映射字典
        """
        # 提取所有期权符号
        symbols = [pos.symbol for pos in positions if pos.is_option]
        
        if not symbols:
            return {}
        
        # 去重
        unique_symbols = list(set(symbols))
        
        # 记录去重效果
        if len(symbols) != len(unique_symbols):
            logger.info(f"期权符号去重: {len(symbols)} -> {len(unique_symbols)} (去除 {len(symbols) - len(unique_symbols)} 个重复)")
        else:
            logger.debug(f"期权符号无重复: {len(unique_symbols)} 个唯一符号")
        
        # 获取报价
        quotes = await self.get_option_quotes(unique_symbols)
        
        # 记录价格信息
        for position in positions:
            if position.symbol in quotes:
                quote = quotes[position.symbol]
                logger.debug(
                    f"期权 {position.symbol} 当前价格: "
                    f"买一={quote.bid_price}, 卖一={quote.ask_price}, "
                    f"最后={quote.last_price}, 当前={quote.current_price}"
                )
        
        return quotes
    
    def get_cached_quote(self, symbol: str) -> Optional[OptionQuote]:
        """
        获取缓存的报价
        
        Args:
            symbol: 期权符号
            
        Returns:
            缓存的报价或None
        """
        return self._price_cache.get(symbol)
    
    def get_price_change(self, symbol: str) -> Optional[float]:
        """
        获取价格变化百分比
        
        Args:
            symbol: 期权符号
            
        Returns:
            价格变化百分比或None
        """
        history = self._price_history.get(symbol)
        if not history or len(history) < 2:
            return None
        
        current_price = history[-1].current_price
        previous_price = history[-2].current_price
        
        if previous_price <= 0:
            return None
        
        return (current_price - previous_price) / previous_price
    
    def add_options_to_track(self, positions: List[Position], quotes: Dict[str, OptionQuote]) -> Dict[str, Dict]:
        """
        将期权加入追踪列表（类似Tiger的add_options_in_dict）
        
        Args:
            positions: 持仓列表
            quotes: 期权报价字典
            
        Returns:
            追踪数据字典
        """
        track_list = {}
        
        for position in positions:
            if not position.is_option:
                continue
                
            symbol = position.symbol
            quote = quotes.get(symbol)
            
            if not quote:
                logger.warning(f"未找到期权 {symbol} 的报价数据")
                continue
            
            # 构建追踪数据
            current_price_key = f"{symbol}_current_price"
            previous_price_key = f"{symbol}_previous_price"
            
            if current_price_key not in track_list:
                # 首次加入
                track_list[current_price_key] = [quote.current_price]
                track_list[previous_price_key] = [0]  # 初始化为0
            else:
                # 更新价格
                track_list[previous_price_key] = track_list[current_price_key]  # 保存之前的价格
                track_list[current_price_key] = [quote.current_price]  # 更新当前价格
            
            logger.debug(f"期权 {symbol} 加入追踪: 当前价格={quote.current_price}")
        
        return track_list
    
    async def refresh_quotes(self, symbols: List[str]) -> Dict[str, OptionQuote]:
        """
        刷新期权报价
        
        Args:
            symbols: 需要刷新的期权符号列表
            
        Returns:
            更新后的报价字典
        """
        logger.debug(f"刷新 {len(symbols)} 个期权报价")
        return await self.get_option_quotes(symbols)
    
    def clear_cache(self):
        """清除价格缓存"""
        self._price_cache.clear()
        self._price_history.clear()
        logger.debug("价格缓存已清除")