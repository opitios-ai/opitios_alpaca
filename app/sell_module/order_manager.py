"""
订单管理器
负责订单的创建、取消和管理
"""

import asyncio
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
from app.account_pool import AccountPool
from app.alpaca_client import AlpacaClient
from .api_client import AlpacaAPIClient, get_api_client


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
        """是否为待执行订单"""
        return self.status in ['new', 'accepted', 'pending_new', 'accepted_for_bidding', 'pending_cancel', 'pending_replace']
    
    @property
    def is_option(self) -> bool:
        """是否为期权订单"""
        return self.asset_class == 'option'
    
    @property
    def age_minutes(self) -> float:
        """订单存在时间（分钟）"""
        if not self.created_at:
            return 0
        
        try:
            created_time = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            return (datetime.now().astimezone() - created_time).total_seconds() / 60
        except:
            return 0


class OrderManager:
    def __init__(self, account_pool: AccountPool, api_client: Optional[AlpacaAPIClient] = None):
        self.account_pool = account_pool
        # API客户端用于替代直接连接池访问（可选）
        self.api_client = api_client
        self.use_api_client = api_client is not None
    
    async def get_all_orders(self, status: str = 'open') -> List[Order]:
        """
        获取所有账户的订单信息 - 支持API客户端或直接连接池访问
        
        Args:
            status: Order status filter ('open', 'closed', 'all')
            
        Returns:
            List of orders from all accounts
        """
        if self.use_api_client:
            return await self._get_all_orders_via_api(status)
        else:
            return await self._get_all_orders_via_pool(status)
    
    async def _get_all_orders_via_api(self, status: str = 'open') -> List[Order]:
        """通过 API 客户端获取所有订单"""
        try:
            logger.debug(f"使用 API 客户端获取所有订单 (status={status})")
            # 通过 HTTP API 获取所有订单数据
            orders_data = await self.api_client.get_all_orders(status=status)
            
            if not orders_data:
                logger.debug("未获取到任何订单数据")
                return []
            
            # 转换为 Order 对象
            all_orders = []
            for order_data in orders_data:
                try:
                    order = Order(order_data)
                    all_orders.append(order)
                except Exception as e:
                    logger.warning(f"Failed to parse order data: {e}")
                    continue
            
            logger.debug(f"Retrieved {len(all_orders)} orders via API")
            return all_orders
            
        except Exception as e:
            logger.error(f"Failed to get all orders via API: {e}")
            return []
    
    async def _get_all_orders_via_pool(self, status: str = 'open') -> List[Order]:
        """通过连接池获取所有订单（原始方法）"""
        try:
            # Optimized account retrieval and task creation
            accounts = await self.account_pool.get_all_accounts()
            
            if not accounts:
                return []
            
            # High-concurrency order fetching
            tasks = [
                self._get_account_orders(account_id, connection, status)
                for account_id, connection in accounts.items()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Optimized result aggregation
            all_orders = []
            for result in results:
                if not isinstance(result, Exception):
                    all_orders.extend(result)
            
            logger.debug(f"Retrieved {len(all_orders)} orders from {len(accounts)} accounts")
            return all_orders
            
        except Exception as e:
            logger.error(f"Failed to get all orders: {e}")
            return []
    
    async def _get_account_orders(self, account_id: str, connection, status: str) -> List[Order]:
        """
        获取单个账户的订单
        
        Args:
            account_id: 账户ID
            connection: 账户连接对象
            status: 订单状态
            
        Returns:
            该账户的订单列表
        """
        try:
            alpaca_client = connection.alpaca_client
            orders_data = await alpaca_client.get_orders(status=status)
            orders = []
            
            for order_data in orders_data:
                # 添加账户ID到订单数据
                order_data['account_id'] = account_id
                order = Order(order_data)
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"获取账户 {account_id} 订单失败: {e}")
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
            all_orders = await self.get_all_orders(status='open')
            
            # High-performance filtering using list comprehension
            orders_to_cancel = [
                order for order in all_orders
                if order.is_pending 
                and (side == 'all' or order.side == side)
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
            
            logger.info(f"Cancelling {len(orders_to_cancel)} orders from {len(orders_by_account)} accounts (batched by account)")
            
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
            logger.success(f"Batch cancellation complete: {success_count}/{len(orders_to_cancel)} successful in {elapsed:.1f}ms")
            
            if failed_count > 0:
                logger.warning(f"{failed_count} orders failed to cancel")
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Batch order cancellation failed in {elapsed:.1f}ms: {e}")
    
    async def _cancel_account_orders_sequential(self, account_id: str, orders: List[Order]) -> List[bool]:
        """
        Cancel orders sequentially for a single account to avoid connection conflicts
        
        Args:
            account_id: Account ID to cancel orders for
            orders: List of orders to cancel for this account
            
        Returns:
            List of cancellation results (True for success, Exception for failure)
        """
        results = []
        order_count = len(orders)
        
        logger.debug(f"Cancelling {order_count} orders sequentially for account {account_id}")
        
        try:
            # Get connection once for all orders in this account
            connection = await self.account_pool.get_connection(account_id)
            
            # Cancel each order sequentially using the same connection
            for i, order in enumerate(orders, 1):
                try:
                    result = await connection.alpaca_client.cancel_order(order.id)
                    
                    if "error" not in result:
                        logger.debug(f"Order {order.id} cancelled successfully for {order.symbol} ({i}/{order_count})")
                        results.append(True)
                    else:
                        logger.error(f"Failed to cancel order {order.id} for {order.symbol}: {result.get('error')}")
                        results.append(Exception(f"Cancellation failed: {result.get('error')}"))
                        
                except Exception as e:
                    logger.error(f"Error cancelling order {order.id} for {order.symbol}: {e}")
                    results.append(e)
                    
            logger.debug(f"Account {account_id} batch complete: {sum(1 for r in results if r is True)}/{order_count} successful")
            
        except Exception as e:
            logger.error(f"Failed to get connection for account {account_id}: {e}")
            # Return failure for all orders if connection fails
            results = [e] * order_count
            
        return results
    
    async def _cancel_order(self, order: Order) -> bool:
        """
        High-performance single order cancellation with optimized operations
        
        Args:
            order: Order to cancel
            
        Returns:
            Success status
        """
        try:
            # Optimized connection retrieval and API call
            connection = await self.account_pool.get_connection(order.account_id)
            result = await connection.alpaca_client.cancel_order(order.id)
            
            logger.debug(f"Order {order.id} cancelled successfully for {order.symbol}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to cancel order {order.id} ({order.symbol}): {e}")
            return False
    
    async def submit_sell_order(self, account_id: str, symbol: str, qty: float, 
                               order_type: str = 'market', limit_price: Optional[float] = None) -> Optional[str]:
        """
        High-performance sell order submission with optimized operations
        
        Args:
            account_id: Account ID
            symbol: Option symbol
            qty: Quantity
            order_type: Order type ('market', 'limit')
            limit_price: Limit price (for limit orders only)
            
        Returns:
            Order ID or None
        """
        try:
            # Optimized connection and order submission
            connection = await self.account_pool.get_connection(account_id)
            client = connection.alpaca_client
            
            # Streamlined order placement
            if order_type == 'limit' and limit_price:
                result = await client.place_option_order(
                    option_symbol=symbol,
                    qty=abs(qty),
                    side='sell',
                    order_type='limit',
                    limit_price=limit_price
                )
            else:
                result = await client.place_option_order(
                    option_symbol=symbol,
                    qty=abs(qty),
                    side='sell',
                    order_type='market'
                )
            
            order_id = result.get('id')
            logger.info(f"Sell order submitted: {order_id} for {symbol} qty={qty}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Failed to submit sell order for {symbol}: {e}")
            return None
    
    async def get_pending_sell_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        High-performance retrieval of pending sell orders with optimized filtering
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of pending sell orders
        """
        try:
            all_orders = await self.get_all_orders(status='open')
            
            # Optimized filtering with combined conditions
            return [
                order for order in all_orders
                if (order.is_sell_order and order.is_pending and order.is_option
                    and (not symbol or order.symbol == symbol))
            ]
            
        except Exception as e:
            logger.error(f"Failed to get pending sell orders: {e}")
            return []