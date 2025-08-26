#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
卖出模块主启动文件
类似Tiger项目的sell_watcher_schedule.py
"""

import asyncio
import sys
import signal
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.account_pool import AccountPool
from app.sell_module.sell_watcher import SellWatcher
from loguru import logger
from config import settings

class SellModuleMain:
    """
    卖出模块主控制器
    """
    
    def __init__(self):
        self.sell_watcher = None
        self.account_pool = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """初始化组件"""
        logger.info("=" * 60)
        logger.info("初始化卖出模块...")
        logger.info("=" * 60)
        
        # 检查模块是否启用
        if not settings.sell_module.get('enabled', True):
            logger.error("卖出模块已在配置中禁用")
            raise RuntimeError("卖出模块未启用")
        
        # 初始化账户池
        logger.info("初始化账户池...")
        self.account_pool = AccountPool()
        await self.account_pool.initialize()
        logger.info(f"账户池初始化完成，共 {len(self.account_pool.account_configs)} 个账户")
        
        # 初始化卖出监控器
        logger.info("初始化卖出监控器...")
        self.sell_watcher = SellWatcher(self.account_pool)
        logger.info("卖出监控器初始化完成")
        
        logger.info("=" * 60)
        logger.info("卖出模块初始化完成")
        logger.info("=" * 60)
        
    async def start(self):
        """启动卖出模块"""
        try:
            await self.initialize()
            
            # 打印配置信息
            self._print_config_info()
            
            # 启动监控
            logger.info("🚀 启动卖出监控...")
            await self.sell_watcher.start_monitoring()
            
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号，正在关闭...")
        except Exception as e:
            logger.error(f"卖出模块运行异常: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """关闭卖出模块"""
        logger.info("正在关闭卖出模块...")
        
        if self.sell_watcher:
            await self.sell_watcher.stop_monitoring()
            
        if self.account_pool:
            await self.account_pool.shutdown()
            
        logger.info("卖出模块已关闭")
    
    def _print_config_info(self):
        """打印配置信息"""
        config = settings.sell_module
        
        logger.info("=" * 60)
        logger.info("卖出模块配置:")
        logger.info("=" * 60)
        logger.info(f"模块状态: {'启用' if config.get('enabled', True) else '禁用'}")
        logger.info(f"检查间隔: {config.get('check_interval', 5)} 秒")
        logger.info(f"订单取消时间: {config.get('order_cancel_minutes', 3)} 分钟")
        logger.info(f"零日期权处理: {'启用' if config.get('zero_day_handling', True) else '禁用'}")
        
        strategy_one = config.get('strategy_one', {})
        logger.info(f"策略一状态: {'启用' if strategy_one.get('enabled', True) else '禁用'}")
        logger.info(f"止盈比率: {strategy_one.get('profit_rate', 1.1)}")
        logger.info(f"止损比率: {strategy_one.get('stop_loss_rate', 0.8)}")
        logger.info("=" * 60)

def setup_signal_handlers(sell_main):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备关闭...")
        asyncio.create_task(sell_main.shutdown())
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """主函数"""
    logger.info("🎯 启动Alpaca卖出模块")
    logger.info(f"启动时间: {datetime.now()}")
    
    sell_main = SellModuleMain()
    setup_signal_handlers(sell_main)
    
    try:
        await sell_main.start()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    # 设置事件循环策略（Windows兼容性）
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)