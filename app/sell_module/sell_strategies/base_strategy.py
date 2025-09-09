"""
基础策略类
所有卖出策略的基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from loguru import logger
from ..position_manager import Position
from ..price_tracker import OptionQuote
from ..order_manager import OrderManager


class BaseStrategy(ABC):
    """基础策略抽象类"""
    
    def __init__(self, name: str, order_manager: OrderManager):
        self.name = name
        self.order_manager = order_manager
    
    @abstractmethod
    async def should_execute(self, position: Position, quote: OptionQuote, config: Dict) -> bool:
        """
        判断是否应该执行策略
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
            
        Returns:
            是否应该执行策略
        """
        pass
    
    @abstractmethod
    async def calculate_sell_price(self, position: Position, quote: OptionQuote, config: Dict) -> Optional[float]:
        """
        计算卖出价格
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
            
        Returns:
            卖出价格或None
        """
        pass
    
    @abstractmethod
    async def execute(self, position: Position, quote: OptionQuote, config: Dict) -> Tuple[bool, str, Optional[float]]:
        """
        执行策略
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
            
        Returns:
            (是否执行成功, 执行原因, 卖出价格)
        """
        pass
    
    async def _place_sell_order(self, position: Position, current_price: float, reason: str) -> bool:
        """
        下达卖出订单 - 使用集中式订单管理
        
        Args:
            position: 持仓信息
            current_price: 当前价格
            reason: 卖出原因
            
        Returns:
            是否成功下单
        """
        try:
            # 测试代码 - 限价0.01（已注释，恢复为市价平仓）
            # result = await self.order_manager.place_sell_order(
            #     account_id=position.account_id,
            #     symbol=position.symbol,
            #     qty=position.qty,
            #     order_type='limit',
            #     limit_price=0.01  # 使用测试价格
            # )
            
            # 正常市价平仓
            result = await self.order_manager.place_sell_order(
                account_id=position.account_id,
                symbol=position.symbol,
                qty=position.qty,
                order_type='market'
            )
            
            if "error" not in result:   
                # 正常下单成功
                order_id = result.get('id', 'Unknown')
                logger.warning(
                    f"{self.name}策略执行 账户: {position.account_id}, "
                    f"期权: {position.symbol}, 触发{reason}卖出, "
                    f"成本价: ${position.avg_entry_price:.2f}, "
                    f"卖出价: ${current_price:.2f}, "
                    f"订单ID: {order_id}"
                )
                return True

            logger.error(f"{self.name}策略下单失败: {result.get('error', 'Unknown error')}")
            return False
                
        except Exception as e:
            logger.error(f"{self.name}策略执行失败: {e}")
            return False
    
    def _calculate_profit_percent(self, current_price: float, cost_price: float) -> float:
        """
        计算收益百分比
        
        Args:
            current_price: 当前价格
            cost_price: 成本价格
            
        Returns:
            收益百分比
        """
        if cost_price <= 0:
            return 0
        return (current_price - cost_price) / cost_price
    
    def _meets_profit_target(self, current_price: float, cost_price: float, target_rate: float) -> bool:
        """
        是否达到盈利目标
        
        Args:
            current_price: 当前价格
            cost_price: 成本价格
            target_rate: 目标收益率
            
        Returns:
            是否达到目标
        """
        if cost_price <= 0:
            return False
        return current_price >= (cost_price * target_rate)
    
    def _meets_stop_loss(self, current_price: float, cost_price: float, stop_rate: float) -> bool:
        """
        是否触发止损
        
        Args:
            current_price: 当前价格
            cost_price: 成本价格
            stop_rate: 止损率
            
        Returns:
            是否触发止损
        """
        if cost_price <= 0:
            return False
        return current_price <= (cost_price * stop_rate)
    
    def log_strategy_check(self, position: Position, quote: OptionQuote, config: Dict):
        """
        记录策略检查日志
        
        Args:
            position: 持仓信息
            quote: 期权报价
            config: 策略配置
        """
        profit_percent = self._calculate_profit_percent(quote.current_price, position.avg_entry_price)
        
        logger.debug(
            f"{self.name}策略检查 期权: {position.symbol}, "
            f"当前价格: ${quote.current_price:.2f}, "
            f"成本价: ${position.avg_entry_price:.2f}, "
            f"收益率: {profit_percent:.2%}, "
            f"止盈率: {config.get('profit_rate', 0):.1f}, "
            f"止损率: {config.get('stop_loss_rate', 0):.1f}"
        )