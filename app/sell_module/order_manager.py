"""
订单管理器
负责订单的创建、取消和管理
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from app.account_pool import AccountPool
from .api_client import AlpacaAPIClient


class Order:
    """订单数据类"""

    def __init__(self, data: dict):
        self.id = data.get('id')
        self.account_id = data.get('account_id')
        self.client_order_id = data.get('client_order_id')
        self.symbol = data.get('symbol')
        self.asset_id = data.get('asset_id')
        self.asset_class = data.get('asset_class')
        self.qty = float(data.get('qty', 0))
        self.filled_qty = float(data.get('filled_qty', 0))
        self.side = data.get('side')  # 'buy' or 'sell'
        self.order_type = data.get('order_type')
        self.time_in_force = data.get('time_in_force')
        self.limit_price = data.get('limit_price')
        self.stop_price = data.get('stop_price')
        self.status = data.get('status')
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.submitted_at = data.get('submitted_at')

    @property
    def is_sell_order(self) -> bool:
        """是否为卖单"""
        return self.side == 'sell'

    @property
    def is_pending(self) -> bool:
        """是否为待执行订单（包括部分成交的订单）"""
        return self.status in ['new', 'accepted', 'pending_new', 'accepted_for_bidding', 'pending_cancel',
                               'pending_replace', 'partially_filled']

    @property
    def is_option(self) -> bool:
        """是否为期权订单"""
        logger.debug(f"是否为期权订单: {self.asset_class}")
        return self.asset_class == 'us_option'

    @property
    def age_minutes(self) -> float:
        """订单存在时间（分钟）"""
        # Prefer submitted_at (when order was actually submitted), then created_at, then updated_at
        timestamp_str = self.submitted_at or self.created_at or self.updated_at
        if not timestamp_str:
            return 0

        try:
            parsed_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            # Make both sides naive or both aware to avoid subtraction errors
            if parsed_time.tzinfo is None:
                now = datetime.now()
            else:
                now = datetime.now(parsed_time.tzinfo)
            return (now - parsed_time).total_seconds() / 60
        except:
            return 0


class OrderManager:
    def __init__(self, account_pool: AccountPool, api_client: AlpacaAPIClient):
        self.account_pool = account_pool
        # API客户端用于所有订单操作
        self.api_client = api_client

    async def get_all_orders(self, status: str = 'open,accepted,replaced') -> List[Order]:
        """
        获取所有账户的订单信息 - 使用HTTP API客户端
        
        Args:
            status: Order status filter ('open', 'closed', 'all', or comma-separated statuses like 'open,accepted,replaced')
            
        Returns:
            List of orders from all accounts
        """
        return await self._get_all_orders_via_api(status)

    async def _get_all_orders_via_api(self, status: str = 'open') -> List[Order]:
        """通过 API 客户端获取所有订单 - 遍历所有账户"""
        try:
            logger.debug(f"使用 API 客户端获取所有订单 (status={status})")

            # 获取所有账户列表
            accounts = await self.account_pool.get_all_accounts()
            if not accounts:
                logger.debug("未找到任何账户")
                return []

            # 为每个账户创建获取订单的任务
            tasks = []
            for account_id in accounts.keys():
                task = self._get_account_orders_via_api(account_id, status)
                tasks.append(task)

            # 并发获取所有账户的订单
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 聚合所有订单
            all_orders = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    account_id = list(accounts.keys())[i]
                    logger.error(f"Failed to get orders for account {account_id}: {result}")
                    continue
                all_orders.extend(result)

            option_orders = sum(1 for order in all_orders if order.is_option)
            logger.info(f"✅ Retrieved {len(all_orders)} orders ({option_orders} options) from {len(accounts)} accounts via API")
            return all_orders

        except Exception as e:
            logger.error(f"Failed to get all orders via API: {e}")
            return []


    async def _get_account_orders_via_api(self, account_id: str, status: str) -> List[Order]:
        """通过 API 客户端获取单个账户的订单"""
        try:
            logger.debug(f"通过 API 获取账户 [{account_id}] 的订单 (status={status})")

            # 通过 HTTP API 获取该账户的订单数据
            orders_data = await self.api_client.get_all_orders(account_id=account_id, status=status)

            if not orders_data:
                logger.debug(f"账户 [{account_id}] 未获取到任何订单数据")
                return []

            # 转换为 Order 对象
            orders = []
            option_orders = 0
            for order_data in orders_data:
                try:
                    # 确保账户ID包含在数据中
                    order_data['account_id'] = account_id
                    order = Order(order_data)
                    orders.append(order)
                    
                    # 统计期权订单
                    if order.is_option:
                        option_orders += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to parse order data [{account_id}]: {e}")
                    continue

            logger.info(f"✅ Account [{account_id}]: Retrieved {len(orders)} orders ({option_orders} options)")
            return orders

        except Exception as e:
            logger.error(f"❌ Failed to get orders for account [{account_id}] via API: {e}")
            return []


    async def cancel_old_orders(self, minutes: int = 3, side: str = 'sell'):
        """
        High-performance async cancellation of old orders with optimized operations
        
        Args:
            minutes: Order age threshold in minutes
            side: Order side filter ('sell', 'buy', 'all')
        """
        start_time = time.time()

        logger.info(f"Starting batch order cancellation: {side} orders older than {minutes}min")

        try:
            # Optimized concurrent order fetching and filtering
            all_orders = await self.get_all_orders(status='open,accepted,replaced')

            # High-performance filtering using list comprehension
            # When side == 'all', include both buy and sell orders
            orders_to_cancel = [
                order for order in all_orders
                if order.is_pending
                   and ((side == 'all') or (order.side == side))
                   and order.age_minutes >= minutes
            ]

            if not orders_to_cancel:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"No {side} orders to cancel (>{minutes}min) - completed in {elapsed:.1f}ms")
                return

            # Group orders by account to avoid connection conflicts
            orders_by_account = {}
            for order in orders_to_cancel:
                account_id = order.account_id
                if account_id not in orders_by_account:
                    orders_by_account[account_id] = []
                orders_by_account[account_id].append(order)

            logger.info(
                f"🔄 Cancelling {len(orders_to_cancel)} orders from {len(orders_by_account)} accounts (batched by account)")

            # Cancel orders sequentially per account, accounts processed in parallel
            tasks = [
                self._cancel_account_orders_sequential(account_id, orders)
                for account_id, orders in orders_by_account.items()
            ]

            account_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results from all accounts
            results = []
            for account_result in account_results:
                if isinstance(account_result, list):
                    results.extend(account_result)
                elif isinstance(account_result, Exception):
                    results.append(account_result)

            # Optimized result processing
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            failed_count = len(results) - success_count

            elapsed = (time.time() - start_time) * 1000
            logger.info(
                f"✅ Batch cancellation complete: {success_count}/{len(orders_to_cancel)} successful in {elapsed:.1f}ms")

            if failed_count > 0:
                logger.warning(f"{failed_count} orders failed to cancel")

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Batch order cancellation failed in {elapsed:.1f}ms: {e}")

    async def _cancel_account_orders_sequential(self, account_id: str, orders: List[Order]) -> List[bool]:
        """
        Cancel orders sequentially for a single account using HTTP API client
        
        Args:
            account_id: Account ID to cancel orders for
            orders: List of orders to cancel for this account
            
        Returns:
            List of cancellation results (True for success, Exception for failure)
        """
        results = []
        order_count = len(orders)

        logger.info(f"🔄 Cancelling {order_count} orders sequentially for account [{account_id}]")

        if not self.api_client:
            logger.error(f"❌ API client not initialized for account [{account_id}]")
            return [Exception("API client not initialized")] * order_count

        # Cancel each order sequentially using HTTP API client
        for i, order in enumerate(orders, 1):
            try:
                logger.info(f"🔄 Cancelling order {i}/{order_count}: {order.id} [{account_id}] {order.symbol}")
                
                # Use HTTP API client instead of direct Alpaca client
                result = await self.api_client.cancel_order(account_id, order.id)

                if "error" not in result:
                    logger.info(f"✅ Order {order.id} cancelled successfully [{account_id}] {order.symbol} ({i}/{order_count})")
                    results.append(True)
                else:
                    logger.error(f"❌ Failed to cancel order {order.id} [{account_id}] {order.symbol}: {result.get('error')}")
                    results.append(Exception(f"Cancellation failed: {result.get('error')}"))

            except Exception as e:
                logger.error(f"❌ Error cancelling order {order.id} [{account_id}] {order.symbol}: {e}")
                results.append(e)

        logger.debug(
            f"✅ Account [{account_id}] batch complete: {sum(1 for r in results if r is True)}/{order_count} successful")

        return results

    async def _cancel_order(self, order: Order) -> bool:
        """
        High-performance single order cancellation using HTTP API client
        
        Args:
            order: Order to cancel
            
        Returns:
            Success status
        """
        try:
            if not self.api_client:
                logger.error(f"❌ API client not initialized for order {order.id}")
                return False

            # Use HTTP API client instead of direct Alpaca client
            result = await self.api_client.cancel_order(order.account_id, order.id)

            if "error" not in result:
                logger.debug(f"Order {order.id} cancelled successfully for {order.symbol}")
                return True
            else:
                logger.warning(f"Failed to cancel order {order.id} ({order.symbol}): {result.get('error')}")
                return False

        except Exception as e:
            logger.warning(f"Failed to cancel order {order.id} ({order.symbol}): {e}")
            return False

    # ============================================================================
    # CENTRALIZED ORDER MANAGEMENT - SINGLE SOURCE OF TRUTH
    # ============================================================================
    
    async def place_sell_order(self, account_id: str, symbol: str, qty: float,
                              order_type: str = 'market', limit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        🎯 CENTRALIZED SELL ORDER PLACEMENT - Single source of truth for all sell orders
        
        Args:
            account_id: Account ID
            symbol: Option symbol
            qty: Quantity to sell
            order_type: 'market' or 'limit' (default: 'market')
            limit_price: Required for limit orders, ignored for market orders
            
        Returns:
            Order result dictionary with 'id' or 'error'
        """
        try:
            if not self.api_client:
                raise Exception("API client not initialized")
            
            # Validate order type
            if order_type not in ['market', 'limit']:
                error_msg = f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'"
                logger.error(f"❌ {error_msg}")
                return {"error": error_msg}
            
            # Validate limit price for limit orders
            if order_type == 'limit':
                if limit_price is None:
                    error_msg = f"limit_price is required for limit orders"
                    logger.error(f"❌ {error_msg}")
                    return {"error": error_msg}
                if limit_price <= 0:
                    error_msg = f"limit_price must be positive, got {limit_price}"
                    logger.error(f"❌ {error_msg}")
                    return {"error": error_msg}
            
            # Prepare order parameters
            order_params = {
                'account_id': account_id,
                'option_symbol': symbol,
                'qty': abs(qty),
                'side': 'sell',
                'order_type': order_type
            }
            
            # Add limit_price only for limit orders
            if order_type == 'limit':
                order_params['limit_price'] = limit_price
            
            result = await self.api_client.place_option_order(**order_params)
            
            if "error" not in result:
                order_id = result.get('id', 'Unknown')
                price_info = f"@{limit_price}" if order_type == 'limit' else "@market"
                logger.info(f"✅ Sell order placed [{account_id}] {symbol} x{abs(qty)} {price_info} | Order ID: {order_id}")
            else:
                logger.error(f"❌ Sell order failed [{account_id}] {symbol}: {result.get('error', 'Unknown error')}")
            
            return result
                
        except Exception as e:
            error_msg = f"Failed to place sell order [{account_id}] {symbol}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
    
    async def place_buy_order(self, account_id: str, symbol: str, qty: float,
                             order_type: str = 'market', limit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        🎯 CENTRALIZED BUY ORDER PLACEMENT - Single source of truth for all buy orders
        
        Args:
            account_id: Account ID
            symbol: Option symbol
            qty: Quantity to buy
            order_type: 'market' or 'limit' (default: 'market')
            limit_price: Required for limit orders, ignored for market orders
            
        Returns:
            Order result dictionary with 'id' or 'error'
        """
        try:
            if not self.api_client:
                raise Exception("API client not initialized")
            
            # Validate order type
            if order_type not in ['market', 'limit']:
                error_msg = f"Invalid order_type '{order_type}'. Must be 'market' or 'limit'"
                logger.error(f"❌ {error_msg}")
                return {"error": error_msg}
            
            # Validate limit price for limit orders
            if order_type == 'limit':
                if limit_price is None:
                    error_msg = f"limit_price is required for limit orders"
                    logger.error(f"❌ {error_msg}")
                    return {"error": error_msg}
                if limit_price <= 0:
                    error_msg = f"limit_price must be positive, got {limit_price}"
                    logger.error(f"❌ {error_msg}")
                    return {"error": error_msg}
            
            # Prepare order parameters
            order_params = {
                'account_id': account_id,
                'option_symbol': symbol,
                'qty': abs(qty),
                'side': 'buy',
                'order_type': order_type
            }
            
            # Add limit_price only for limit orders
            if order_type == 'limit':
                order_params['limit_price'] = limit_price
            
            result = await self.api_client.place_option_order(**order_params)
            
            if "error" not in result:
                order_id = result.get('id', 'Unknown')
                price_info = f"@{limit_price}" if order_type == 'limit' else "@market"
                logger.info(f"✅ Buy order placed [{account_id}] {symbol} x{abs(qty)} {price_info} | Order ID: {order_id}")
            else:
                logger.error(f"❌ Buy order failed [{account_id}] {symbol}: {result.get('error', 'Unknown error')}")
            
            return result
                
        except Exception as e:
            error_msg = f"Failed to place buy order [{account_id}] {symbol}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}
    
    async def cancel_order_by_id(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        🎯 CENTRALIZED ORDER CANCELLATION - Single source of truth for all order cancellations
        
        Args:
            account_id: Account ID
            order_id: Order ID to cancel
            
        Returns:
            Cancellation result dictionary
        """
        try:
            if not self.api_client:
                raise Exception("API client not initialized")
            
            result = await self.api_client.cancel_order(
                account_id=account_id,
                order_id=order_id
            )
            
            if "error" not in result:
                logger.info(f"✅ Order cancelled [{account_id}] Order ID: {order_id}")
            else:
                logger.error(f"❌ Order cancellation failed [{account_id}] Order ID: {order_id}: {result.get('error', 'Unknown error')}")
            
            return result
                
        except Exception as e:
            error_msg = f"Failed to cancel order [{account_id}] Order ID: {order_id}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"error": error_msg}

    async def get_pending_sell_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        High-performance retrieval of pending sell orders with optimized filtering
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of pending sell orders
        """
        try:
            all_orders = await self.get_all_orders(status='open,accepted,replaced')

            # Optimized filtering with combined conditions
            return [
                order for order in all_orders
                if (order.is_sell_order and order.is_pending and order.is_option
                    and (not symbol or order.symbol == symbol))
            ]

        except Exception as e:
            logger.error(f"Failed to get pending sell orders: {e}")
            return []
