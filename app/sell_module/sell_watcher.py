"""
卖出监控器
主要的卖出监控服务，类似Tiger的sell_watcher_schedule.py
"""

import asyncio
from typing import Dict, List
from datetime import datetime
import arrow
from loguru import logger
from config import settings
from app.account_pool import AccountPool
from app.utils.discord_notifier import send_sell_module_notification
from .config_manager import ConfigManager
from .position_manager import PositionManager, Position
from .order_manager import OrderManager
from .price_tracker import PriceTracker
from .sell_strategies.strategy_one import StrategyOne


class SellWatcher:
    """
    卖出监控器主类
    负责持续监控持仓并执行卖出策略
    """
    
    def __init__(self, account_pool: AccountPool):
        self.account_pool = account_pool
        self.settings = settings
        
        # 初始化各个组件
        self.config_manager = ConfigManager()
        self.position_manager = PositionManager(account_pool)
        self.order_manager = OrderManager(account_pool)
        self.price_tracker = PriceTracker(account_pool)
        
        # 初始化策略
        self.strategy_one = StrategyOne(self.order_manager)
        
        # 运行状态
        self.is_running = False
        self.monitor_task = None
        
        # 追踪数据（类似Tiger的track_list）
        self.track_list: Dict[str, Dict] = {}
        
        logger.info("卖出监控器初始化完成")
    
    async def start_monitoring(self):
        """
        开始监控（类似Tiger的main函数）
        """
        if self.is_running:
            logger.warning("卖出监控器已在运行")
            return
        
        self.is_running = True
        logger.info("=== 卖出监控器启动 ===")
        
        # 发送Discord启动通知
        try:
            accounts_count = len(self.account_pool.account_configs) if self.account_pool else 0
            strategy_config = {
                'enabled': self.config_manager.is_strategy_enabled(),
                'profit_rate': getattr(settings, 'sell_module', {}).get('strategy_one', {}).get('profit_rate', 1.1),
                'stop_loss_rate': getattr(settings, 'sell_module', {}).get('strategy_one', {}).get('stop_loss_rate', 0.8)
            }
            
            await send_sell_module_notification(
                status="started",
                message="卖出模块已成功启动，开始监控期权持仓并执行自动卖出策略",
                details={
                    'accounts_count': accounts_count,
                    'strategy_config': strategy_config,
                    'check_interval': self.config_manager.get_check_interval(),
                    'cancel_minutes': self.config_manager.get_order_cancel_minutes()
                }
            )
        except Exception as e:
            logger.error(f"发送Discord启动通知失败: {e}")
        
        try:
            while self.is_running:
                # 检查间隔 - 分割为更小的睡眠间隔以便快速响应停止信号
                check_interval = self.config_manager.get_check_interval()
                
                # 分割睡眠时间，每0.5秒检查一次停止信号
                sleep_chunks = max(1, int(check_interval / 0.5))
                chunk_sleep = check_interval / sleep_chunks
                
                for _ in range(sleep_chunks):
                    if not self.is_running:
                        break
                    await asyncio.sleep(chunk_sleep)
                
                if not self.is_running:
                    break
                
                # 执行监控周期
                await self._monitor_cycle()
                
        except Exception as e:
            logger.error(f"监控循环异常: {e}")
        finally:
            logger.info("=== 卖出监控器停止 ===")
            self.is_running = False
            
            # 发送Discord停止通知
            try:
                await send_sell_module_notification(
                    status="stopped",
                    message="卖出模块已停止运行"
                )
            except Exception as e:
                logger.error(f"发送Discord停止通知失败: {e}")
    
    async def stop_monitoring(self):
        """
        停止监控
        """
        if not self.is_running:
            logger.debug("卖出监控器已经停止")
            return
            
        logger.info("正在停止卖出监控器...")
        self.is_running = False
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                logger.debug("监控任务已取消")
                pass
        
        logger.info("卖出监控器已停止")
    
    async def _monitor_cycle(self):
        """
        单次监控周期（类似Tiger的main循环内容）
        """
        try:
            logger.info("=" * 60)
            logger.info("卖出监控周期开始")
            logger.info("=" * 60)
            start_time = datetime.now()
            
            # 1. 获取所有持仓
            all_positions = await self.position_manager.get_all_positions()
            
            if not all_positions:
                logger.info("账户净持仓为0，没有持有期权")
                logger.info("=" * 60)
                return
            
            # 2. 处理空头持仓（自动平仓）
            await self.position_manager.handle_short_positions(all_positions)
            
            # 3. 过滤出多头期权持仓
            long_positions = self.position_manager.filter_long_positions(all_positions)
            
            if not long_positions:
                logger.info("没有多头期权持仓需要处理")
                logger.info("=" * 60)
                return
            
            logger.info(f"发现 {len(long_positions)} 个多头期权持仓需要监控")
            
            # 4. 取消旧订单（无论市场是否开放都执行）
            cancel_minutes = self.config_manager.get_order_cancel_minutes()
            logger.info(f"开始取消超过 {cancel_minutes} 分钟的卖出订单")
            await self.order_manager.cancel_old_orders(minutes=cancel_minutes, side='all')
            logger.info("取消旧订单检查完成")
            
            # 5. 检查是否在交易时间内
            if not self._is_market_open():
                logger.info("市场未开放，跳过策略执行")
                logger.info("=" * 60)
                return
            
            # 6. 执行卖出策略
            await self._execute_sell_strategies(long_positions)
            
            # 7. 处理零日期权
            await self._handle_zero_day_options(long_positions)
            
            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info("=" * 60)
            logger.info(f"卖出监控周期结束 - 用时 {execution_time:.2f}秒")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"监控周期异常: {e}")
    
    async def _execute_sell_strategies(self, positions: List[Position]):
        """
        执行卖出策略
        
        Args:
            positions: 多头期权持仓列表
        """
        logger.info("***** 开始执行卖出策略 *****")
        
        # 获取所有持仓的价格
        logger.info(f"获取 {len(positions)} 个持仓的价格数据...")
        quotes = await self.price_tracker.get_position_prices(positions)
        
        if not quotes:
            logger.warning("未能获取期权价格数据，跳过策略执行")
            logger.info("***** 卖出策略执行结束 *****")
            return
        
        logger.info(f"成功获取 {len(quotes)} 个期权的价格数据")
        
        # 更新追踪列表
        self.track_list = self.price_tracker.add_options_to_track(positions, quotes)
        
        # 遍历每个持仓执行策略
        logger.info(f"开始检查 {len(positions)} 个持仓的卖出条件...")
        for position in positions:
            try:
                await self._execute_position_strategy(position, quotes)
            except Exception as e:
                logger.error(f"执行持仓策略失败 {position.symbol}: {e}")
        
        logger.info("***** 卖出策略执行结束 *****")
    
    async def _execute_position_strategy(self, position: Position, quotes: Dict):
        """
        对单个持仓执行策略
        
        Args:
            position: 持仓信息
            quotes: 价格数据字典
        """
        symbol = position.symbol
        quote = quotes.get(symbol)
        
        if not quote:
            logger.warning(f"未找到期权 {symbol} 的价格数据")
            return
        
        # 获取策略配置
        underlying_symbol = getattr(position, 'underlying_symbol', symbol.split('_')[0])
        strategy_config = await self.config_manager.get_strategy_config(underlying_symbol)
        
        # 检查策略一是否启用
        if not self.config_manager.is_strategy_enabled():
            logger.info(f"策略一未启用，跳过 {symbol}")
            return
        
        logger.info(f"策略一已启用，开始检查 {symbol}")
        
        # 执行策略一
        await self._execute_strategy_one(position, quote, strategy_config)
    
    async def _execute_strategy_one(self, position: Position, quote, strategy_config: Dict):
        """
        执行策略一
        
        Args:
            position: 持仓信息
            quote: 期权报价
            strategy_config: 策略配置
        """
        try:
            # 检查是否应该执行
            should_execute = await self.strategy_one.should_execute(position, quote, strategy_config)
            
            if should_execute:
                # 执行策略
                success, reason, sell_price = await self.strategy_one.execute(position, quote, strategy_config)
                
                if success:
                    logger.info(f"策略一执行成功 {position.symbol}: {reason}, 价格: ${sell_price:.2f}")
                else:
                    logger.warning(f"策略一执行失败 {position.symbol}: {reason}")
            else:
                logger.debug(f"策略一条件不满足 {position.symbol}，继续监控")
                
        except Exception as e:
            logger.error(f"策略一执行异常 {position.symbol}: {e}")
    
    async def _handle_zero_day_options(self, positions: List[Position]):
        """
        处理零日期权（当日到期的期权）
        
        Args:
            positions: 持仓列表
        """
        zero_day_positions = self.position_manager.get_zero_day_positions(positions)
        
        if not zero_day_positions:
            return
        
        logger.warning(f"发现 {len(zero_day_positions)} 个零日期权，准备强制平仓")
        
        for position in zero_day_positions:
            try:
                # 零日期权直接市价卖出
                order_id = await self.order_manager.submit_sell_order(
                    account_id=position.account_id,
                    symbol=position.symbol,
                    qty=position.qty,
                    order_type='market'
                )
                
                if order_id:
                    logger.warning(f"零日期权强制平仓 {position.symbol}, 订单ID: {order_id}")
                
            except Exception as e:
                logger.error(f"零日期权平仓失败 {position.symbol}: {e}")
    
    def _is_market_open(self) -> bool:
        """
        检查市场是否开放（类似Tiger的is_market_open）
        
        Returns:
            市场是否开放
        """
        try:
            # 获取美东时间
            now_edt = arrow.now('US/Eastern')
            current_time = now_edt.format('HH:mm:ss')
            current_weekday = now_edt.weekday()  # 0=Monday, 6=Sunday
            
            # 检查是否为工作日 (周一到周五)
            if current_weekday >= 5:  # 5=Saturday, 6=Sunday
                logger.info(f"今天是周末（周{current_weekday+1}），市场未开放")
                return False
            
            # 检查是否在交易时间内 (9:30 - 16:00 ET)
            is_open = '09:30:00' <= current_time <= '16:00:00'
            
            # 详细的市场时间日志
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            logger.info(f"市场时间检查: 当前美东时间 {current_time} ({weekday_names[current_weekday]}), 市场{'开放' if is_open else '未开放'}")
            
            return is_open
            
        except Exception as e:
            logger.error(f"检查市场开放状态失败: {e}")
            return True  # 默认认为市场开放
    
    def get_status(self) -> Dict:
        """
        获取监控器状态
        
        Returns:
            状态信息字典
        """
        return {
            'is_running': self.is_running,
            'start_time': getattr(self, 'start_time', None),
            'market_open': self._is_market_open(),
            'strategy_one_enabled': self.config_manager.is_strategy_enabled(),
            'check_interval': self.config_manager.get_check_interval(),
            'tracked_options': len(self.track_list),
            'components': {
                'config_manager': 'ready',
                'position_manager': 'ready', 
                'order_manager': 'ready',
                'price_tracker': 'ready',
                'strategy_one': 'ready'
            }
        }
    
    async def run_once(self):
        """
        执行一次监控周期（用于测试）
        """
        logger.info("执行一次性监控检查")
        await self._monitor_cycle()