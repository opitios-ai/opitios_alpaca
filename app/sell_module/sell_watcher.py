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
from .api_client import AlpacaAPIClient
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
            self.price_tracker = PriceTracker(account_pool)
        else:
            # 原始架构 - 直接连接池访问（需要price_tracker）
            logger.debug("使用原始架构初始化卖出监控器组件")
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
            rates = await self.config_manager.get_strategy_config('GLOBAL')
            strategy_config = {
                'enabled': self.config_manager.is_strategy_enabled(),
                'profit_rate': rates.get('profit_rate'),
                'stop_loss_rate': rates.get('stop_loss_rate')
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
        执行卖出策略 - 使用position数据直接计算，并行处理所有持仓
        
        Args:
            positions: 多头期权持仓列表
        """
        logger.info("***** 开始执行卖出策略 *****")

        # 筛选出期权持仓
        option_positions = [pos for pos in positions if pos.is_option and pos.is_long]
        logger.info(f"发现 {len(option_positions)} 个多头期权持仓需要评估")

        if not option_positions:
            logger.info("没有期权持仓需要处理")
            return

        # 并行评估所有持仓的卖出条件
        logger.info(f"并行评估 {len(option_positions)} 个持仓的卖出条件...")
        evaluation_tasks = [
            self._evaluate_position_sell_condition(position)
            for position in option_positions
        ]

        evaluation_results = await asyncio.gather(*evaluation_tasks, return_exceptions=True)

        # 收集需要卖出的持仓
        positions_to_sell = []
        for i, result in enumerate(evaluation_results):
            position = option_positions[i]
            if isinstance(result, Exception):
                logger.error(f"评估持仓失败 [{position.account_id}] {position.symbol}: {result}")
                continue

            should_sell, reason = result
            if should_sell:
                logger.info(f"SELL DECISION [{position.account_id}] {position.symbol}: {reason} | "
                            f"P&L: {position.unrealized_plpc:.2%} | Current: ${position.current_price} | "
                            f"QtyAvailable: {position.qty_available}")
                positions_to_sell.append(position)
            else:
                logger.debug(f"HOLD [{position.account_id}] {position.symbol}: {reason} | "
                             f"P&L: {position.unrealized_plpc:.2%} | Current: ${position.current_price}")

        logger.info(f"策略评估完成: {len(positions_to_sell)}/{len(option_positions)} 个持仓需要卖出")

        # 并行执行卖出订单
        if positions_to_sell:
            await self._execute_parallel_sell_orders(positions_to_sell)
        else:
            logger.info("无持仓需要卖出")

        logger.info("***** 卖出策略执行结束 *****")

    async def _evaluate_position_sell_condition(self, position: Position) -> tuple[bool, str]:
        """
        评估单个持仓的卖出条件 - 并行执行
        
        Args:
            position: 持仓对象
            
        Returns:
            (should_sell, reason)
        """
        try:
            # 检查必需数据
            if position.unrealized_plpc is None:
                logger.error(f"Position [{position.account_id}] {position.symbol}: Missing unrealized_plpc field")
                return False, "Continue after error: Missing unrealized_plpc data"

            profit_loss_pct = position.unrealized_plpc
            is_zero_day = position.is_zero_day_option

            # 1. 检查持仓时间限制（优先级最高）
            time_config = self.config_manager.get_position_time_limit_config()
            if time_config['enabled']:
                max_hold_minutes = time_config['max_hold_minutes']
                if position.is_time_limit_exceeded(max_hold_minutes):
                    hold_duration = position.hold_duration_minutes
                    return True, f"Time limit exceeded: {hold_duration:.1f}min >= {max_hold_minutes}min"

            # 零日期权：无需利润判断，交由零日处理逻辑统一市价卖出
            if is_zero_day:
                return False, "Zero-day handled by dedicated market-sell handler"

            # 使用 ConfigManager 作为单一配置来源
            underlying_symbol = getattr(position, 'underlying_symbol', position.symbol.split('_')[0])
            rates = await self.config_manager.get_strategy_config(underlying_symbol)
            profit_rate = float(rates.get('profit_rate', 1.1))
            stop_loss_rate = float(rates.get('stop_loss_rate', 0.8))

            min_profit_threshold = profit_rate - 1.0
            stop_loss_threshold = stop_loss_rate - 1.0

            if profit_loss_pct >= min_profit_threshold:
                return True, f"Profit target reached: {profit_loss_pct:.2%} >= {min_profit_threshold:.2%}"
            if profit_loss_pct <= stop_loss_threshold:
                return True, f"Stop loss triggered: {profit_loss_pct:.2%} <= {stop_loss_threshold:.2%}"
            return False, f"Holding: P&L {profit_loss_pct:.2%} within range"

        except Exception as e:
            logger.error(f"Error evaluating sell decision [{position.account_id}] {position.symbol}: {e}")
            return False, f"Continue after error: {str(e)}"

    async def _execute_parallel_sell_orders(self, positions_to_sell: List[Position]):
        """
        并行执行卖出订单 - 使用批次处理避免API过载
        
        Args:
            positions_to_sell: 需要卖出的持仓列表
        """
        logger.info(f"并行执行卖出订单: {len(positions_to_sell)} 个持仓")

        # 批次大小和并发控制
        BATCH_SIZE = 20  # 每批处理20个订单
        MAX_CONCURRENT = 10  # 最大并发数

        # 按账户分组，确保同一账户的订单不会过度并发
        positions_by_account = {}
        for position in positions_to_sell:
            if position.account_id not in positions_by_account:
                positions_by_account[position.account_id] = []
            positions_by_account[position.account_id].append(position)

        logger.info(f"订单分布: {[(account, len(positions)) for account, positions in positions_by_account.items()]}")

        # 统计结果
        successful_sells = 0
        failed_sells = 0

        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def process_position_with_semaphore(position: Position):
            """使用信号量控制单个订单处理"""
            async with semaphore:
                return await self._execute_single_sell_order(position)

        # 分批处理所有订单
        all_positions = positions_to_sell
        for batch_start in range(0, len(all_positions), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(all_positions))
            batch_positions = all_positions[batch_start:batch_end]

            logger.info(
                f"处理批次 {batch_start // BATCH_SIZE + 1}: 订单 {batch_start + 1}-{batch_end} ({len(batch_positions)} 个)")

            # 并行处理当前批次
            sell_tasks = [
                process_position_with_semaphore(position)
                for position in batch_positions
            ]

            batch_results = await asyncio.gather(*sell_tasks, return_exceptions=True)

            # 处理批次结果
            for i, result in enumerate(batch_results):
                position = batch_positions[i]
                if isinstance(result, Exception):
                    failed_sells += 1
                    logger.error(f"❌ Failed to place sell order [{position.account_id}] {position.symbol}: {result}")
                elif isinstance(result, dict) and result.get("error"):
                    failed_sells += 1
                    logger.error(
                        f"❌ Failed to place sell order [{position.account_id}] {position.symbol}: {result['error']}")
                else:
                    successful_sells += 1
                    order_id = result.get('id', 'Unknown') if isinstance(result, dict) else 'Unknown'
                    logger.info(
                        f"✅ Sell order placed successfully [{position.account_id}] {position.symbol} | Order ID: {order_id}")

            # 批次间延迟，避免API过载
            if batch_end < len(all_positions):
                logger.info("批次完成，等待 2 秒后处理下一批次...")
                await asyncio.sleep(2)

        logger.info(f"并行卖出完成: {successful_sells} 成功, {failed_sells} 失败")

    async def _execute_single_sell_order(self, position: Position) -> Dict[str, any]:
        """
        执行单个持仓的卖出订单 - 使用集中式订单管理
        
        Args:
            position: 需要卖出的持仓
            
        Returns:
            卖出结果
        """
        try:
            # 使用qty_available确定正确的卖出数量
            if position.qty_available is None or position.qty_available <= 0:
                # 负数或None为错误
                error_msg = f"Invalid qty_available: {position.qty_available}"
                logger.error(f"Position [{position.account_id}] {position.symbol}: {error_msg}")
                return {"error": error_msg}

            qty_to_sell = abs(int(position.qty_available))

            # 使用集中式订单管理系统
            if not self.order_manager:
                error_msg = "Order manager not available"
                logger.error(f"Position [{position.account_id}] {position.symbol}: {error_msg}")
                return {"error": error_msg}

            # 测试代码 - 限价0.01（已注释，恢复为市价平仓）
            # logger.info(f"Placing sell order [{position.account_id}] {position.symbol} x{qty_to_sell} @ limit 0.01")
            # result = await self.order_manager.place_sell_order(
            #     account_id=position.account_id,
            #     symbol=position.symbol,
            #     qty=qty_to_sell,
            #     order_type='limit',
            #     limit_price=0.01
            # )

            # 正常市价平仓
            logger.info(f"Placing sell order [{position.account_id}] {position.symbol} x{qty_to_sell} @ market")

            result = await self.order_manager.place_sell_order(
                account_id=position.account_id,
                symbol=position.symbol,
                qty=qty_to_sell,
                order_type='market'
            )

            return result

        except Exception as e:
            logger.error(f"Exception executing sell [{position.account_id}] {position.symbol}: {e}")
            return {"error": str(e)}

    async def _handle_zero_day_options(self, positions: List[Position]):
        """
        处理零日期权（当日到期的期权）- 并行执行
        
        Args:
            positions: 持仓列表
        """
        zero_day_positions = self.position_manager.get_zero_day_positions(positions)

        if not zero_day_positions:
            return

        logger.warning(f"发现 {len(zero_day_positions)} 个零日期权，准备强制平仓")

        # 并行执行零日期权平仓
        zero_day_tasks = [
            self._execute_single_sell_order(position)
            for position in zero_day_positions
        ]

        zero_day_results = await asyncio.gather(*zero_day_tasks, return_exceptions=True)

        # 统计结果
        successful_closes = 0
        failed_closes = 0

        for i, result in enumerate(zero_day_results):
            position = zero_day_positions[i]
            if isinstance(result, Exception):
                failed_closes += 1
                logger.error(f"❌ Zero-day close failed [{position.account_id}] {position.symbol}: {result}")
            elif isinstance(result, dict) and result.get("error"):
                failed_closes += 1
                logger.error(f"❌ Zero-day close failed [{position.account_id}] {position.symbol}: {result['error']}")
            elif isinstance(result, dict) and result.get("status") == "skipped":
                # 跳过的情况（如订单待处理）不算失败
                logger.info(
                    f"⏭️ Skipped zero-day close [{position.account_id}] {position.symbol}: {result.get('reason', 'unknown')}")
            else:
                successful_closes += 1
                order_id = result.get('id', 'Unknown') if isinstance(result, dict) else 'Unknown'
                logger.warning(
                    f"⚠️ Zero-day option closed [{position.account_id}] {position.symbol} | Order ID: {order_id}")

        logger.warning(f"零日期权平仓完成: {successful_closes} 成功, {failed_closes} 失败")

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
                logger.info(f"今天是周末（周{current_weekday + 1}），市场未开放")
                return False

            # 检查是否在交易时间内 (9:30 - 16:00 ET)
            is_open = '09:30:00' <= current_time <= '16:00:00'

            # 详细的市场时间日志
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            logger.info(
                f"市场时间检查: 当前美东时间 {current_time} ({weekday_names[current_weekday]}), 市场{'开放' if is_open else '未开放'}")

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
            'architecture': 'parallel_optimized' if self.use_api_client else 'legacy',
            'components': {
                'config_manager': 'ready',
                'position_manager': 'ready (parallel)',
                'order_manager': 'ready (parallel)',
                'price_tracker': 'not_used (position_data_only)',
                'strategy_one': 'ready',
                'parallel_sell_strategy': 'ready' if self.use_api_client else 'not available',
                'parallel_evaluation': 'enabled',
                'parallel_order_placement': 'enabled'
            }
        }

    async def run_once(self):
        """
        执行一次监控周期（用于测试）
        """
        logger.info("执行一次性监控检查")
        await self._monitor_cycle()
