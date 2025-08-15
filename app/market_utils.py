"""
Market Utilities - 市场时间检查和相关工具函数
可配置的市场时间检查功能，支持从配置文件读取开盘和收盘时间
"""

import arrow
from typing import Dict, Optional
from loguru import logger


class MarketTimeChecker:
    """市场时间检查器 - 支持可配置的开盘和收盘时间"""
    
    def __init__(self, market_config: Optional[Dict] = None):
        """
        初始化市场时间检查器
        
        Args:
            market_config: 市场配置字典，包含open_hour, open_minute, close_hour, close_minute
        """
        if market_config:
            self.open_hour = market_config.get('open_hour', 8)
            self.open_minute = market_config.get('open_minute', 50)
            self.close_hour = market_config.get('close_hour', 17)
            self.close_minute = market_config.get('close_minute', 0)
            self.timezone = market_config.get('timezone', 'US/Eastern')
            self.trading_days = market_config.get('trading_days', [0, 1, 2, 3, 4])  # Monday-Friday
        else:
            # 默认配置：美东时间 8:50 AM - 5:00 PM
            self.open_hour = 8
            self.open_minute = 50
            self.close_hour = 17
            self.close_minute = 0
            self.timezone = 'US/Eastern'
            self.trading_days = [0, 1, 2, 3, 4]  # Monday-Friday
    
    def is_market_hours(self) -> bool:
        """
        检查当前是否在市场交易时间内
        
        Returns:
            bool: True if current time is within trading hours, False otherwise
        """
        try:
            # 获取指定时区的当前时间
            now = arrow.now(self.timezone)
            
            # 检查是否为交易日
            if now.weekday() not in self.trading_days:
                logger.debug(f"NON_TRADING_DAY: {now.format('dddd YYYY-MM-DD HH:mm:ss ZZZ')}")
                return False
            
            # 计算开盘和收盘时间
            market_open = now.replace(
                hour=self.open_hour, 
                minute=self.open_minute, 
                second=0, 
                microsecond=0
            )
            market_close = now.replace(
                hour=self.close_hour, 
                minute=self.close_minute, 
                second=0, 
                microsecond=0
            )
            
            is_trading_time = market_open <= now <= market_close
            
            if is_trading_time:
                logger.debug(f"TRADING_HOURS - Current: {now.format('HH:mm:ss ZZZ')}")
            else:
                logger.debug(
                    f"OFF_HOURS - Current: {now.format('HH:mm:ss ZZZ')} | "
                    f"Trading: {self.open_hour:02d}:{self.open_minute:02d}-"
                    f"{self.close_hour:02d}:{self.close_minute:02d} {self.timezone}"
                )
            
            return is_trading_time
            
        except Exception as e:
            logger.warning(f"市场时间检查失败: {e}")
            return True  # 出错时假设市场开放，避免误报
    
    def get_market_status_info(self) -> Dict:
        """
        获取详细的市场状态信息
        
        Returns:
            Dict: 包含市场状态、消息、当前时间等信息的字典
        """
        try:
            now = arrow.now(self.timezone)
            is_trading_day = now.weekday() in self.trading_days
            
            market_open = now.replace(
                hour=self.open_hour, 
                minute=self.open_minute, 
                second=0, 
                microsecond=0
            )
            market_close = now.replace(
                hour=self.close_hour, 
                minute=self.close_minute, 
                second=0, 
                microsecond=0
            )
            
            is_trading_time = market_open <= now <= market_close
            
            if not is_trading_day:
                if now.weekday() >= 5:  # Weekend
                    status = "WEEKEND"
                    message = f"Weekend closed - {now.format('dddd HH:mm:ss ZZZ')}"
                else:
                    status = "HOLIDAY"
                    message = f"Non-trading day - {now.format('dddd HH:mm:ss ZZZ')}"
            elif is_trading_time:
                status = "TRADING"
                message = f"Normal trading hours - {now.format('HH:mm:ss ZZZ')}"
            elif now < market_open:
                status = "PRE_MARKET"
                time_to_open = (market_open - now).total_seconds() / 3600
                message = f"Pre-market - {time_to_open:.1f} hours to open"
            else:  # after market_close
                next_open = market_open.shift(days=1)
                # Skip weekends
                while next_open.weekday() not in self.trading_days:
                    next_open = next_open.shift(days=1)
                status = "AFTER_HOURS"
                message = f"After hours - Next open: {next_open.format('dddd HH:mm ZZZ')}"
            
            market_hours_str = (
                f"{self._get_trading_days_str()} "
                f"{self.open_hour:02d}:{self.open_minute:02d}-"
                f"{self.close_hour:02d}:{self.close_minute:02d} {self.timezone}"
            )
            
            return {
                "status": status,
                "message": message,
                "is_trading_time": is_trading_time and is_trading_day,
                "current_time": now.format('dddd YYYY-MM-DD HH:mm:ss ZZZ'),
                "market_hours": market_hours_str,
                "timezone": self.timezone,
                "next_open": self._get_next_open_time(now).format('dddd YYYY-MM-DD HH:mm:ss ZZZ') if not (is_trading_time and is_trading_day) else None
            }
            
        except Exception as e:
            logger.error(f"获取市场状态信息失败: {e}")
            return {
                "status": "ERROR",
                "message": f"状态检查失败: {e}",
                "is_trading_time": True,  # 安全起见
                "current_time": arrow.now().format('YYYY-MM-DD HH:mm:ss ZZZ'),
                "market_hours": "Unable to determine",
                "timezone": self.timezone
            }
    
    def _get_trading_days_str(self) -> str:
        """获取交易日的字符串表示"""
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        trading_day_names = [day_names[day] for day in sorted(self.trading_days)]
        
        if self.trading_days == [0, 1, 2, 3, 4]:
            return "Monday-Friday"
        elif len(trading_day_names) == 1:
            return trading_day_names[0]
        elif len(trading_day_names) == 2:
            return f"{trading_day_names[0]}, {trading_day_names[1]}"
        else:
            return f"{', '.join(trading_day_names[:-1])}, {trading_day_names[-1]}"
    
    def _get_next_open_time(self, current_time: arrow.Arrow) -> arrow.Arrow:
        """获取下一个开盘时间"""
        next_open = current_time.replace(
            hour=self.open_hour, 
            minute=self.open_minute, 
            second=0, 
            microsecond=0
        )
        
        # 如果当前时间已过今日开盘时间，则查找下一个交易日
        if current_time >= next_open:
            next_open = next_open.shift(days=1)
        
        # 跳过非交易日
        while next_open.weekday() not in self.trading_days:
            next_open = next_open.shift(days=1)
        
        return next_open
    
    def time_until_market_open(self) -> Optional[float]:
        """
        计算距离下一次开盘的时间（小时）
        
        Returns:
            float: 距离开盘的小时数，如果当前正在交易时间内则返回None
        """
        if self.is_market_hours():
            return None
        
        try:
            now = arrow.now(self.timezone)
            next_open = self._get_next_open_time(now)
            return (next_open - now).total_seconds() / 3600
        except Exception as e:
            logger.error(f"计算开盘时间失败: {e}")
            return None
    
    def time_until_market_close(self) -> Optional[float]:
        """
        计算距离市场收盘的时间（小时）
        
        Returns:
            float: 距离收盘的小时数，如果当前不在交易时间内则返回None
        """
        if not self.is_market_hours():
            return None
        
        try:
            now = arrow.now(self.timezone)
            market_close = now.replace(
                hour=self.close_hour, 
                minute=self.close_minute, 
                second=0, 
                microsecond=0
            )
            return (market_close - now).total_seconds() / 3600
        except Exception as e:
            logger.error(f"计算收盘时间失败: {e}")
            return None


# 全局市场时间检查器实例（将由config模块初始化）
_global_market_checker: Optional[MarketTimeChecker] = None


def init_market_checker(market_config: Optional[Dict] = None) -> MarketTimeChecker:
    """
    初始化全局市场时间检查器
    
    Args:
        market_config: 市场配置字典
        
    Returns:
        MarketTimeChecker: 市场时间检查器实例
    """
    global _global_market_checker
    _global_market_checker = MarketTimeChecker(market_config)
    return _global_market_checker


def get_market_checker() -> MarketTimeChecker:
    """
    获取全局市场时间检查器实例
    
    Returns:
        MarketTimeChecker: 市场时间检查器实例
        
    Raises:
        RuntimeError: 如果未初始化市场检查器
    """
    if _global_market_checker is None:
        raise RuntimeError("Market checker not initialized. Call init_market_checker() first.")
    return _global_market_checker


# 便捷函数 - 使用全局检查器
def is_market_hours() -> bool:
    """检查当前是否在市场交易时间内（使用全局配置）"""
    return get_market_checker().is_market_hours()


def get_market_status_info() -> Dict:
    """获取详细的市场状态信息（使用全局配置）"""
    return get_market_checker().get_market_status_info()


def time_until_market_open() -> Optional[float]:
    """计算距离下一次开盘的时间（小时）"""
    return get_market_checker().time_until_market_open()


def time_until_market_close() -> Optional[float]:
    """计算距离市场收盘的时间（小时）"""
    return get_market_checker().time_until_market_close()