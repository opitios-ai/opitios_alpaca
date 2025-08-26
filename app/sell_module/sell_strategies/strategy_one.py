"""
策略一实现
基于止盈止损的简单策略，包含收盘前强制平仓
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
import arrow
from loguru import logger
from .base_strategy import BaseStrategy
from ..position_manager import Position
from ..price_tracker import OptionQuote
from ..order_manager import OrderManager


class StrategyOne(BaseStrategy):
    """
    策略一：止盈止损策略
    - 达到止盈率时卖出
    - 触发止损率时卖出  
    - 收盘前10分钟强制平仓
    """
    
    def __init__(self, order_manager: OrderManager):
        super().__init__("策略一", order_manager)
    
    async def should_execute(self, position: Position, quote: OptionQuote, config: Dict) -> bool:
        """
        判断是否应该执行策略一
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
            
        Returns:
            是否应该执行策略
        """
        if not position.is_option or not position.is_long:
            return False
        
        if quote.current_price <= 0 or position.avg_entry_price <= 0:
            logger.warning(f"价格数据异常 {position.symbol}: 当前价={quote.current_price}, 成本价={position.avg_entry_price}")
            return False
        
        # 检查是否达到止盈条件
        if self._meets_profit_target(quote.current_price, position.avg_entry_price, config['profit_rate']):
            return True
        
        # 检查是否触发止损条件
        if self._meets_stop_loss(quote.current_price, position.avg_entry_price, config['stop_loss_rate']):
            return True
        
        # 检查是否接近收盘
        if self._is_close_to_market_close():
            return True
        
        return False
    
    async def calculate_sell_price(self, position: Position, quote: OptionQuote, config: Dict) -> Optional[float]:
        """
        计算卖出价格（策略一使用市价单，返回当前价格用于记录）
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
            
        Returns:
            当前价格
        """
        return quote.current_price
    
    async def execute(self, position: Position, quote: OptionQuote, config: Dict) -> Tuple[bool, str, Optional[float]]:
        """
        执行策略一
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
            
        Returns:
            (是否执行成功, 执行原因, 卖出价格)
        """
        try:
            # 记录策略检查信息
            self.log_strategy_check(position, quote, config)
            
            current_price = quote.current_price
            cost_price = position.avg_entry_price
            profit_rate = config['profit_rate']
            stop_loss_rate = config['stop_loss_rate']
            
            # 计算止盈止损价格
            profit_target_price = cost_price * profit_rate
            stop_loss_price = cost_price * stop_loss_rate
            
            # 计算收益率
            profit_pct = (current_price - cost_price) / cost_price * 100
            
            logger.info(f"[{position.account_id}] 策略一检查 - {position.symbol}")
            logger.info(f"  ├─ 当前价格: ${current_price:.2f}")
            logger.info(f"  ├─ 成本价格: ${cost_price:.2f}")
            logger.info(f"  ├─ 止盈目标: ${profit_target_price:.2f} ({(profit_rate-1)*100:.1f}%)")
            logger.info(f"  ├─ 止损价格: ${stop_loss_price:.2f} ({(stop_loss_rate-1)*100:.1f}%)")
            logger.info(f"  └─ 当前收益: {profit_pct:+.2f}%")
            
            # 判断卖出原因
            reason = None
            
            # 1. 检查止盈
            if current_price >= profit_target_price:
                reason = "止盈"
            
            # 2. 检查止损
            elif current_price <= stop_loss_price:
                reason = "止损"
            
            # 3. 检查收盘强制平仓
            elif self._is_close_to_market_close():
                reason = "收盘"
            
            if reason:
                # 执行卖出
                success = await self._place_sell_order(position, current_price, reason)
                return success, reason, current_price
            else:
                logger.info(f"不满足策略一止盈止损标准，继续监控 {position.symbol}")
                return False, "继续监控", None
                
        except Exception as e:
            logger.error(f"策略一执行异常: {e}")
            return False, f"执行异常: {e}", None
    
    def _is_close_to_market_close(self) -> bool:
        """
        检查是否接近收盘（收盘前10分钟）
        
        Returns:
            是否接近收盘
        """
        try:
            # 获取美东时间
            current_edt = arrow.now('US/Eastern').format('HH:mm:ss')
            
            # 收盘前10分钟（15:50:00 到 16:00:00）
            is_close_time = '15:50:00' <= current_edt <= '16:00:00'
            
            if is_close_time:
                logger.info(f"当前美东时间 {current_edt}，接近收盘，准备强制平仓")
            
            return is_close_time
            
        except Exception as e:
            logger.error(f"检查收盘时间失败: {e}")
            return False
    
    def _is_market_hours(self) -> bool:
        """
        检查是否在交易时间内
        
        Returns:
            是否在交易时间
        """
        try:
            # 获取美东时间
            now_edt = arrow.now('US/Eastern')
            current_time = now_edt.format('HH:mm:ss')
            current_weekday = now_edt.weekday()  # 0=Monday, 6=Sunday
            
            # 检查是否为工作日 (周一到周五)
            if current_weekday >= 5:  # 5=Saturday, 6=Sunday
                return False
            
            # 检查是否在交易时间内 (9:30 - 16:00 ET)
            is_trading_hours = '09:30:00' <= current_time <= '16:00:00'
            
            return is_trading_hours
            
        except Exception as e:
            logger.error(f"检查交易时间失败: {e}")
            return True  # 默认认为在交易时间内
    
    def get_strategy_info(self) -> Dict:
        """
        获取策略信息
        
        Returns:
            策略信息字典
        """
        return {
            'name': self.name,
            'description': '基于止盈止损的简单策略，包含收盘前强制平仓',
            'features': [
                '止盈：达到目标收益率时自动卖出',
                '止损：跌破止损率时自动卖出', 
                '强制平仓：收盘前10分钟自动卖出',
                '市价单：使用市价单确保快速成交'
            ],
            'parameters': [
                'profit_rate: 止盈率（如1.1表示10%盈利）',
                'stop_loss_rate: 止损率（如0.8表示-20%亏损）'
            ]
        }