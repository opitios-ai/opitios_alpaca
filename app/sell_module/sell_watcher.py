"""
卖出监控器
主要的卖出监控服务，类似Tiger的sell_watcher_schedule.py
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import arrow
from loguru import logger
from config import settings
from app.account_pool import AccountPool
from .api_client import AlpacaAPIClient, get_api_client
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
    
    def __init__(self, account_pool: AccountPool, api_client: Optional[AlpacaAPIClient] = None):
        self.account_pool = account_pool
        self.settings = settings
        
        # 如果提供了API客户端，则使用API架构，否则使用原始架构
        self.use_api_client = api_client is not None
        
        # 初始化各个组件
        self.config_manager = ConfigManager()
        if self.use_api_client:
            # API 客户端架构 - 避免直接连接池访问
            logger.info("使用 API 客户端架构初始化卖出监控器组件（OptimizedStrategy优先）")
            self.position_manager = PositionManager(account_pool, api_client)
            self.order_manager = OrderManager(account_pool, api_client)
            # 只有在优化策略失败时才需要price_tracker作为回退
            self.price_tracker = PriceTracker(account_pool, api_client)
        else:
            # 原始架构 - 直接连接池访问（需要price_tracker）
            logger.debug("使用原始架构初始化卖出监控器组件")
            self.position_manager = PositionManager(account_pool)
            self.order_manager = OrderManager(account_pool)
            self.price_tracker = PriceTracker(account_pool)
        
        # 初始化策略
        self.strategy_one = StrategyOne(self.order_manager)
        
        # 直接卖出策略配置 (使用position数据，无需单独的策略类)
        self.direct_sell_config = {
            'min_profit_threshold': 0.15,  # 15% profit target
            'stop_loss_threshold': -0.30,  # -30% stop loss
            'zero_day_profit_threshold': 0.05  # 5% for zero-day options
        }
        
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
            # if not self._is_market_open():
            #     logger.info("市场未开放，跳过策略执行")
            #     logger.info("=" * 60)
            #     return
            
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
        执行卖出策略 - 优先使用position数据直接计算，回退到price_tracker
        
        Args:
            positions: 多头期权持仓列表
        """
        logger.info("***** 开始执行卖出策略 *****")
        
        # 如果使用API客户端，优先使用position数据直接计算（无需额外API调用）
        if self.use_api_client:
            logger.info(f"使用position数据直接处理 {len(positions)} 个持仓（无需额外API调用）")
            try:
                await self._execute_direct_sell_strategy(positions)
                logger.info("***** 直接卖出策略执行结束 *****")
                return
                
            except Exception as e:
                logger.error(f"直接卖出策略执行失败: {e}")
                logger.error(f"继续处理错误，回退到传统策略")
        
        # 回退到传统策略（如果直接策略失败或不可用）
        logger.info(f"回退到传统价格追踪策略处理 {len(positions)} 个持仓")
        await self._execute_traditional_sell_strategies(positions)
    
    async def _execute_direct_sell_strategy(self, positions: List[Position]):
        """
        直接卖出策略 - 使用position中的数据直接计算和执行
        
        Args:
            positions: 多头期权持仓列表
        """
        # 筛选出期权持仓
        option_positions = [pos for pos in positions if pos.is_option and pos.is_long]
        logger.info(f"发现 {len(option_positions)} 个多头期权持仓需要评估")
        
        # 评估每个持仓
        positions_to_sell = []
        for position in option_positions:
            should_sell, reason = await self._should_sell_position(position)
            
            if should_sell:
                logger.info(f"SELL DECISION: {position.symbol} - {reason} | "
                           f"P&L: {position.unrealized_plpc:.2%} | Current: ${position.current_price} | "
                           f"QtyAvailable: {position.qty_available}")
                positions_to_sell.append(position)
            else:
                logger.debug(f"HOLD: {position.symbol} - {reason} | "
                            f"P&L: {position.unrealized_plpc:.2%} | Current: ${position.current_price}")
        
        logger.info(f"策略评估完成: {len(positions_to_sell)}/{len(option_positions)} 个持仓需要卖出")
        
        # 执行卖出
        if positions_to_sell:
            await self._execute_direct_sells(positions_to_sell)
        else:
            logger.info("无持仓需要卖出")
    
    async def _should_sell_position(self, position: Position) -> tuple[bool, str]:
        """
        判断持仓是否应该卖出
        
        Args:
            position: 持仓对象
            
        Returns:
            (should_sell, reason)
        """
        try:
            # 检查必需数据
            if position.unrealized_plpc is None:
                logger.error(f"Position {position.symbol}: Missing unrealized_plpc field")
                return False, "Continue after error: Missing unrealized_plpc data"
            
            profit_loss_pct = position.unrealized_plpc
            is_zero_day = position.is_zero_day_option
            
            # 零日期权特殊处理
            if is_zero_day:
                if profit_loss_pct >= self.direct_sell_config['zero_day_profit_threshold']:
                    return True, f"Zero-day option profit target reached: {profit_loss_pct:.2%}"
                elif profit_loss_pct <= self.direct_sell_config['stop_loss_threshold']:
                    return True, f"Zero-day option stop loss triggered: {profit_loss_pct:.2%}"
                else:
                    return False, f"Zero-day option holding: P&L {profit_loss_pct:.2%} within range"
            
            # 普通期权策略
            if profit_loss_pct >= self.direct_sell_config['min_profit_threshold']:
                return True, f"Profit target reached: {profit_loss_pct:.2%}"
            elif profit_loss_pct <= self.direct_sell_config['stop_loss_threshold']:
                return True, f"Stop loss triggered: {profit_loss_pct:.2%}"
            else:
                return False, f"Holding: P&L {profit_loss_pct:.2%} within acceptable range"
                
        except Exception as e:
            logger.error(f"Error evaluating sell decision for {position.symbol}: {e}")
            return False, f"Continue after error: {str(e)}"
    
    async def _execute_direct_sells(self, positions_to_sell: List[Position]):
        """
        执行直接卖出操作
        
        Args:
            positions_to_sell: 需要卖出的持仓列表
        """
        logger.info(f"执行直接卖出策略: {len(positions_to_sell)} 个持仓")
        
        successful_sells = 0
        failed_sells = 0
        
        # 顺序执行卖单，严格避免并发下单
        for position in positions_to_sell:
            try:
                result = await self._execute_single_direct_sell(position)
                if isinstance(result, dict) and result.get("error"):
                    failed_sells += 1
                    logger.error(f"❌ Failed to place sell order for {position.symbol} (account {position.account_id}): {result['error']}")
                else:
                    successful_sells += 1
                    logger.info(f"✅ Sell order placed successfully for {position.symbol} (account {position.account_id})")
            except Exception as e:
                failed_sells += 1
                logger.error(f"Failed to sell {position.symbol} (account {position.account_id}): {e}")
        
        logger.info(f"直接卖出完成: {successful_sells} 成功, {failed_sells} 失败")
    
    async def _execute_single_direct_sell(self, position: Position) -> Dict[str, any]:
        """
        执行单个持仓的直接卖出
        
        Args:
            position: 需要卖出的持仓
            
        Returns:
            卖出结果
        """
        try:
            # 使用qty_available确定正确的卖出数量
            if position.qty_available is None or position.qty_available <= 0:
                error_msg = f"Invalid qty_available: {position.qty_available}"
                logger.error(f"Position {position.symbol}: {error_msg}")
                return {"error": error_msg}
            
            qty_to_sell = abs(int(position.qty_available))
            
            # 通过API客户端下市价卖单（使用实际的 API 客户端实例，而非布尔标志）
            api_client = getattr(self.order_manager, 'api_client', None)
            if api_client is None:
                error_msg = "API client is not configured"
                logger.error(f"Position {position.symbol}: {error_msg}")
                return {"error": error_msg}

            result = await api_client.place_option_order(
                account_id=position.account_id,
                option_symbol=position.symbol,
                qty=qty_to_sell,
                side='sell',
                order_type='market'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Exception executing sell for {position.symbol}: {e}")
            return {"error": str(e)}
    
    async def _execute_traditional_sell_strategies(self, positions: List[Position]):
        """
        传统卖出策略（使用price_tracker）- 作为OptimizedStrategy的回退
        
        Args:
            positions: 多头期权持仓列表
        """
        logger.info("***** 使用传统策略（price_tracker）*****")
        
        # 获取所有持仓的价格
        logger.info(f"获取 {len(positions)} 个持仓的价格数据...")
        quotes = await self.price_tracker.get_position_prices(positions)
        
        if not quotes:
            logger.warning("未能获取期权价格数据，跳过策略执行")
            logger.info("***** 传统策略执行结束 *****")
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
        
        logger.info("***** 传统策略执行结束 *****")
    
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
                'price_tracker': 'ready (fallback only)' if self.use_api_client else 'ready',
                'strategy_one': 'ready',
                'direct_sell_strategy': 'ready' if self.use_api_client else 'not available'
            }
        }
    
    async def run_once(self):
        """
        执行一次监控周期（用于测试）
        """
        logger.info("执行一次性监控检查")
        await self._monitor_cycle()