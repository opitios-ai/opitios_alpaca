"""
配置管理器
处理卖出策略的配置，支持数据库优先，配置文件兜底的双层配置
"""

import asyncio
from typing import Dict, Optional
from loguru import logger
from config import settings


class ConfigManager:
    def __init__(self):
        self.settings = settings
        self._config_cache = {}
        self._cache_ttl = 300  # 缓存5分钟
        
    async def get_strategy_config(self, symbol: str) -> Dict[str, float]:
        """
        获取特定symbol的策略配置
        目前只使用配置文件，数据库功能暂时禁用以确保独立运行
        
        Args:
            symbol: 股票代码，如 "AAPL"
            
        Returns:
            包含profit_rate和stop_loss_rate的配置字典
        """
        try:
            # 检查缓存
            cache_key = f"strategy_config_{symbol}"
            if cache_key in self._config_cache:
                cached_data = self._config_cache[cache_key]
                if asyncio.get_event_loop().time() - cached_data['timestamp'] < self._cache_ttl:
                    logger.debug(f"使用缓存配置 {symbol}: {cached_data['config']}")
                    return cached_data['config']
            
            # 使用默认配置（独立运行模式）
            config = {
                'profit_rate': float(self.settings.sell_module['strategy_one']['profit_rate']),
                'stop_loss_rate': float(self.settings.sell_module['strategy_one']['stop_loss_rate'])
            }
            logger.info(f"使用默认配置 {symbol}: 止盈率={config['profit_rate']}, 止损率={config['stop_loss_rate']}")
            
            # 更新缓存
            self._config_cache[cache_key] = {
                'config': config,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            return config
            
        except Exception as e:
            logger.error(f"获取策略配置失败 {symbol}: {e}")
            # 返回默认配置作为兜底
            return {
                'profit_rate': 1.1,
                'stop_loss_rate': 0.8
            }
    
    
    def clear_cache(self):
        """清除配置缓存"""
        self._config_cache.clear()
        logger.info("配置缓存已清除")
    
    def is_strategy_enabled(self) -> bool:
        """检查策略一是否启用"""
        return self.settings.sell_module['strategy_one']['enabled']
    
    def get_check_interval(self) -> int:
        """获取检查间隔（秒）"""
        return self.settings.sell_module['check_interval']
    
    def get_order_cancel_minutes(self) -> int:
        """获取订单取消时间（分钟）"""
        return self.settings.sell_module['order_cancel_minutes']