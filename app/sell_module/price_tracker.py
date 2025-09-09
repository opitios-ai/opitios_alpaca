"""
价格追踪器
负责获取和追踪期权的实时价格数据
"""

from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
from app.account_pool import AccountPool
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
    def __init__(self, account_pool: AccountPool):
        if account_pool is None:
            raise TypeError("account_pool cannot be None")
        self.account_pool = account_pool
        self._price_cache: Dict[str, OptionQuote] = {}
        self._price_history: Dict[str, List[OptionQuote]] = {}
        
    
    
    
    
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
    
    
    def clear_cache(self):
        """清除价格缓存"""
        self._price_cache.clear()
        self._price_history.clear()
        logger.debug("价格缓存已清除")