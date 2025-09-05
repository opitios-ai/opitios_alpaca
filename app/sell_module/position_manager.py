"""
持仓管理器
负责获取、过滤和处理所有账户的期权持仓
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, date
from loguru import logger
from app.account_pool import AccountPool
from app.alpaca_client import AlpacaClient
from .api_client import AlpacaAPIClient, get_api_client


class Position:
    """持仓数据类"""
    def __init__(self, data: dict):
        self.account_id = data.get('account_id')
        self.symbol = data.get('symbol')
        self.asset_id = data.get('asset_id')
        
        # Handle invalid numeric data gracefully
        try:
            self.qty = float(data.get('qty', 0))
        except (ValueError, TypeError):
            self.qty = 0.0
            
        try:
            self.avg_entry_price = float(data.get('avg_entry_price', 0))
        except (ValueError, TypeError):
            self.avg_entry_price = 0.0
            
        try:
            self.market_value = float(data.get('market_value', 0))
        except (ValueError, TypeError):
            self.market_value = 0.0
            
        try:
            self.cost_basis = float(data.get('cost_basis', 0))
        except (ValueError, TypeError):
            self.cost_basis = 0.0
            
        try:
            self.unrealized_pl = float(data.get('unrealized_pl', 0))
        except (ValueError, TypeError):
            self.unrealized_pl = 0.0
            
        try:
            self.unrealized_plpc = float(data.get('unrealized_plpc', 0))
        except (ValueError, TypeError):
            self.unrealized_plpc = 0.0
            
        self.side = data.get('side')  # 'long' or 'short'
        
        # Store additional price fields from Alpaca
        try:
            self.current_price = float(data.get('current_price', 0))
        except (ValueError, TypeError):
            self.current_price = 0.0
            
        try:
            self.lastday_price = float(data.get('lastday_price', 0))
        except (ValueError, TypeError):
            self.lastday_price = 0.0
        
        # Store asset class for option identification
        self.asset_class = data.get('asset_class')
        
        # Store qty_available for correct sell quantities
        try:
            self.qty_available = float(data.get('qty_available', 0))
        except (ValueError, TypeError):
            self.qty_available = 0.0
        
        # Log if avg_entry_price is missing
        if self.avg_entry_price == 0 and self.symbol:
            logger.warning(f"Position {self.symbol}: avg_entry_price为0，可能是Alpaca paper账户数据问题")
        
        # 期权特定字段 - 基于symbol解析
        if self.is_option:
            # 从期权symbol解析信息: NVDA250822P00170000
            self.underlying_symbol = self._parse_underlying_symbol()
            self.expiration_date = self._parse_expiration_date()
            self.strike_price = self._parse_strike_price()
            self.option_type = self._parse_option_type()
        else:
            self.underlying_symbol = None
            self.expiration_date = None
            self.strike_price = None
            self.option_type = None
    
    @property
    def is_option(self) -> bool:
        """是否为期权 - 使用asset_class字段准确判断"""
        if not self.symbol:
            return False
        
        # 使用Alpaca API返回的asset_class字段进行准确判断
        if self.asset_class:
            return self.asset_class == 'us_option'
        
        # 如果asset_class不可用，返回False，避免不准确的symbol匹配
        return False
    
    @property
    def is_long(self) -> bool:
        """是否为多头持仓"""
        return self.qty > 0
    
    @property
    def is_short(self) -> bool:
        """是否为空头持仓"""
        return self.qty < 0
    
    @property
    def is_zero_day_option(self) -> bool:
        """是否为零日期权（当日到期）"""
        if not self.is_option or not self.expiration_date:
            return False
        try:
            exp_date = datetime.strptime(self.expiration_date, '%Y-%m-%d').date()
            return exp_date == date.today()
        except:
            return False
    
    def _parse_underlying_symbol(self) -> str:
        """从期权symbol解析标的股票"""
        if not self.is_option:
            return None
        # NVDA250822P00170000 -> NVDA
        # 查找第一个数字的位置
        for i, char in enumerate(self.symbol):
            if char.isdigit():
                return self.symbol[:i]
        return None
    
    def _parse_expiration_date(self) -> str:
        """从期权symbol解析到期日"""
        if not self.is_option:
            return None
        try:
            # NVDA250822P00170000 -> 250822 -> 2025-08-22
            underlying = self._parse_underlying_symbol()
            if not underlying:
                return None
            date_part = self.symbol[len(underlying):len(underlying)+6]  # 6位日期
            if len(date_part) == 6 and date_part.isdigit():
                year = "20" + date_part[:2]
                month = date_part[2:4]
                day = date_part[4:6]
                return f"{year}-{month}-{day}"
        except:
            pass
        return None
    
    def _parse_option_type(self) -> str:
        """从期权symbol解析期权类型"""
        if not self.is_option:
            return None
        try:
            # 需要找到正确的C或P位置（在日期之后）
            underlying = self._parse_underlying_symbol()
            if not underlying:
                return None
                
            # 跳过标的和6位日期，找到C或P
            start_pos = len(underlying) + 6  # 标的 + 6位日期
            for i in range(start_pos, len(self.symbol)):
                if self.symbol[i] == 'C':
                    return 'C'
                elif self.symbol[i] == 'P':
                    return 'P'
        except:
            pass
        return None
    
    def _parse_strike_price(self) -> float:
        """从期权symbol解析行权价格"""
        if not self.is_option:
            return None
        try:
            # AAPL250815P00150000 -> 00150000 -> 150.00
            # 需要找到正确的C或P位置（在日期之后）
            underlying = self._parse_underlying_symbol()
            if not underlying:
                return None
                
            # 跳过标的和6位日期，找到C或P
            start_pos = len(underlying) + 6  # 标的 + 6位日期
            cp_pos = -1
            for i in range(start_pos, len(self.symbol)):
                if self.symbol[i] in ['C', 'P']:
                    cp_pos = i
                    break
            
            if cp_pos > 0 and cp_pos + 1 < len(self.symbol):
                strike_part = self.symbol[cp_pos + 1:]  # C/P之后的部分
                if len(strike_part) == 8 and strike_part.isdigit():
                    # 整个8位数字表示价格，最后3位是小数部分
                    strike_value = int(strike_part)
                    return strike_value / 1000.0
        except:
            pass
        return None


class PositionManager:
    def __init__(self, account_pool: AccountPool, api_client: Optional[AlpacaAPIClient] = None):
        if account_pool is None:
            raise TypeError("account_pool cannot be None")
        self.account_pool = account_pool
        # API客户端用于替代直接连接池访问（可选）
        self.api_client = api_client
        self.use_api_client = api_client is not None
    
    async def get_all_positions(self) -> List[Position]:
        """
        获取所有账户的持仓信息 - 支持API客户端或直接连接池访问
        
        Returns:
            List of all account positions
        """
        if self.use_api_client:
            return await self._get_all_positions_via_api()
        else:
            return await self._get_all_positions_via_pool()
    
    async def _get_all_positions_via_api(self) -> List[Position]:
        """通过 API 客户端获取所有持仓 - 遍历所有账户"""
        try:
            logger.debug("使用 API 客户端获取所有持仓")
            
            # 获取所有账户列表
            accounts = await self.account_pool.get_all_accounts()
            if not accounts:
                logger.debug("未找到任何账户")
                return []
            
            # 为每个账户创建获取持仓的任务
            tasks = []
            for account_id in accounts.keys():
                task = self._get_account_positions_via_api(account_id)
                tasks.append(task)
            
            # 并发获取所有账户的持仓
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 聚合所有持仓
            all_positions = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    account_id = list(accounts.keys())[i]
                    logger.error(f"Failed to get positions for account {account_id}: {result}")
                    continue
                all_positions.extend(result)
            
            # 统计信息
            option_count = sum(1 for pos in all_positions if pos.is_option)
            logger.debug(f"Retrieved {len(all_positions)} positions ({option_count} options) from {len(accounts)} accounts via API")
            
            return all_positions
            
        except Exception as e:
            logger.error(f"Failed to get all positions via API: {e}")
            # 返回空列表而不是抛异常，保持服务稳定性
            return []
    
    async def _get_all_positions_via_pool(self) -> List[Position]:
        """通过连接池获取所有持仓（原始方法）"""
        try:
            # Optimized account retrieval and task creation
            accounts = await self.account_pool.get_all_accounts()
            
            if not accounts:
                return []
            
            # High-concurrency position fetching
            tasks = [
                self._get_account_positions(account_id, connection)
                for account_id, connection in accounts.items()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Optimized result aggregation
            all_positions = []
            for result in results:
                if not isinstance(result, Exception):
                    all_positions.extend(result)
            
            # Fast position counting
            option_count = sum(1 for pos in all_positions if pos.is_option)
            logger.debug(f"Retrieved {len(all_positions)} positions ({option_count} options) from {len(accounts)} accounts")
            
            return all_positions
            
        except Exception as e:
            logger.error(f"Failed to get all positions: {e}")
            # Re-raise the exception instead of masking it with empty list
            # This ensures tests fail when there are real errors
            raise RuntimeError(f"Position retrieval failed: {e}") from e
    
    async def _get_account_positions_via_api(self, account_id: str) -> List[Position]:
        """通过 API 客户端获取单个账户的持仓"""
        try:
            logger.debug(f"通过 API 获取账户 {account_id} 的持仓")
            
            # 通过 HTTP API 获取该账户的持仓数据
            positions_data = await self.api_client.get_all_positions(account_id=account_id)
            
            if not positions_data:
                logger.debug(f"账户 {account_id} 未获取到任何持仓数据")
                return []
            
            # 转换为 Position 对象
            positions = []
            for pos_data in positions_data:
                try:
                    # 确保账户ID包含在数据中
                    pos_data['account_id'] = account_id
                    position = Position(pos_data)
                    positions.append(position)
                    
                    # 重要持仓日志
                    if position.is_option and position.is_zero_day_option:
                        logger.warning(f"Zero-day option detected: {position.symbol} in {account_id}")
                except Exception as e:
                    logger.warning(f"Failed to parse position data for account {account_id}: {e}")
                    continue
            
            logger.debug(f"Account {account_id}: Retrieved {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions for account {account_id} via API: {e}")
            return []
    
    async def _get_account_positions(self, account_id: str, connection) -> List[Position]:
        """
        通过连接池获取单个账户的持仓（原始方法）
        High-performance single account position retrieval
        
        Args:
            account_id: Account ID
            connection: Account connection object
            
        Returns:
            List of positions for the account
        """
        try:
            # Streamlined position retrieval
            positions_data = await connection.alpaca_client.get_positions()
            
            # Optimized position creation
            positions = []
            for pos_data in positions_data:
                pos_data['account_id'] = account_id
                position = Position(pos_data)
                positions.append(position)
                
                # Simplified logging for important positions only
                if position.is_option and position.is_zero_day_option:
                    logger.warning(f"Zero-day option detected: {position.symbol} in {account_id}")
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions for account {account_id}: {e}")
            return []
    
    def filter_long_positions(self, positions: List[Position]) -> List[Position]:
        """
        High-performance filtering for long positions
        
        Args:
            positions: All positions list
            
        Returns:
            Long positions (qty > 0)
        """
        return [pos for pos in positions if pos.is_long]
    
    async def handle_short_positions(self, positions: List[Position]):
        """
        High-performance async handling of short positions (auto-close)
        
        Args:
            positions: All positions list
        """
        short_positions = [pos for pos in positions if pos.is_option and pos.is_short]
        
        if not short_positions:
            return
        
        logger.warning(f"Found {len(short_positions)} short option positions, closing sequentially")
        
        # Sequentially close each short position to avoid concurrent orders
        failed_count = 0
        for position in short_positions:
            try:
                await self._close_short_position(position)
            except Exception:
                failed_count += 1
        if failed_count > 0:
            logger.error(f"{failed_count}/{len(short_positions)} short positions failed to close")
    
    async def _close_short_position(self, position: Position):
        """
        平仓空头持仓 - 支持API客户端或直接连接池访问
        
        Args:
            position: Short position to close
        """
        if self.use_api_client:
            await self._close_short_position_via_api(position)
        else:
            await self._close_short_position_via_pool(position)
    
    async def _close_short_position_via_api(self, position: Position):
        """通过 API 客户端平仓空头持仓"""
        try:
            # 通过 API 下买单平仓空头持仓
            result = await self.api_client.place_option_order(
                account_id=position.account_id,
                option_symbol=position.symbol,
                qty=abs(int(position.qty)),
                side='buy',
                order_type='market'
            )
            
            if "error" not in result:
                logger.info(f"Short position closed via API: {position.symbol} in {position.account_id}")
            else:
                logger.error(f"Failed to close short position {position.symbol} via API: {result['error']}")
                raise Exception(result['error'])
            
        except Exception as e:
            logger.error(f"Failed to close short position {position.symbol} via API: {e}")
            raise
    
    async def _close_short_position_via_pool(self, position: Position):
        """通过连接池平仓空头持仓（原始方法）"""
        try:
            # Streamlined connection and order placement
            connection = await self.account_pool.get_connection(position.account_id)
            
            result = await connection.alpaca_client.submit_order(
                symbol=position.symbol,
                qty=abs(position.qty),
                side='buy',
                type='market',
                time_in_force='day'
            )
            
            logger.info(f"Short position closed: {position.symbol} in {position.account_id}")
            
        except Exception as e:
            logger.error(f"Failed to close short position {position.symbol}: {e}")
            raise
    
    def get_zero_day_positions(self, positions: List[Position]) -> List[Position]:
        """
        High-performance filtering for zero-day option positions
        
        Args:
            positions: Position list
            
        Returns:
            Zero-day option positions
        """
        return [pos for pos in positions if pos.is_option and pos.is_zero_day_option]