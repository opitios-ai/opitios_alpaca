"""
API 客户端
卖出模块通过 HTTP API 调用获取数据和下单，而不是直接访问连接池
"""

import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from config import settings


class AlpacaAPIClient:
    """
    Alpaca API 客户端 - 通过 HTTP 调用内部 API endpoints
    替代直接连接池访问，符合标准架构流程
    """
    
    def __init__(self, base_url: str = "http://localhost:8090"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Opitios-SellModule/1.0'
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=aiohttp.TCPConnector(limit=20, limit_per_host=10)
            )
        return self.session
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        统一的 HTTP 请求方法
        
        Args:
            method: HTTP 方法 (GET, POST, etc.)
            endpoint: API 端点
            **kwargs: 传递给 aiohttp 的参数
            
        Returns:
            API 响应数据
        """
        url = f"{self.base_url}/api/v1{endpoint}"
        session = await self._get_session()
        
        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed: {method} {url} - {response.status}: {error_text}")
                    return {"error": f"HTTP {response.status}: {error_text}"}
                    
        except asyncio.TimeoutError:
            logger.error(f"API request timeout: {method} {url}")
            return {"error": "Request timeout"}
        except Exception as e:
            logger.error(f"API request exception: {method} {url} - {e}")
            return {"error": str(e)}
    
    async def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        获取所有账户的持仓信息
        
        Returns:
            所有持仓的列表
        """
        logger.debug("通过 API 获取所有账户持仓")
        result = await self._make_request('GET', '/positions')
        
        if "error" in result:
            logger.error(f"获取持仓失败: {result['error']}")
            return []
            
        return result if isinstance(result, list) else []
    
    async def get_all_orders(self, status: str = 'open') -> List[Dict[str, Any]]:
        """
        获取所有账户的订单信息
        
        Args:
            status: 订单状态过滤
            
        Returns:
            订单列表
        """
        logger.debug(f"通过 API 获取所有订单 (status={status})")
        params = {'status': status} if status else {}
        result = await self._make_request('GET', '/orders', params=params)
        
        if "error" in result:
            logger.error(f"获取订单失败: {result['error']}")
            return []
            
        return result if isinstance(result, list) else []
    
    async def cancel_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        取消特定订单
        
        Args:
            account_id: 账户ID
            order_id: 订单ID
            
        Returns:
            取消结果
        """
        logger.debug(f"通过 API 取消订单: {order_id} (account: {account_id})")
        result = await self._make_request(
            'DELETE', 
            f'/orders/{order_id}',
            params={'account_id': account_id}
        )
        
        if "error" in result:
            logger.error(f"取消订单失败: {result['error']}")
            
        return result
    
    async def get_option_quotes(self, symbols: List[str], account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取期权报价
        
        Args:
            symbols: 期权符号列表
            account_id: 可选的账户ID
            
        Returns:
            期权报价数据
        """
        logger.debug(f"通过 API 获取期权报价: {len(symbols)} symbols")
        params = {}
        if account_id:
            params['account_id'] = account_id
            
        result = await self._make_request(
            'POST', 
            '/options/quotes/batch',
            json={'symbols': symbols},
            params=params
        )
        
        if "error" in result:
            logger.error(f"获取期权报价失败: {result['error']}")
            
        return result
    
    async def place_option_order(self, account_id: str, option_symbol: str, qty: int, 
                               side: str, order_type: str = "market", 
                               limit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        下期权订单
        
        Args:
            account_id: 账户ID
            option_symbol: 期权符号
            qty: 数量
            side: 买卖方向 (buy/sell)
            order_type: 订单类型
            limit_price: 限价(限价单)
            
        Returns:
            订单结果
        """
        logger.info(f"通过 API 下期权订单: {option_symbol} x{qty} {side} (account: {account_id})")
        
        order_data = {
            'option_symbol': option_symbol,
            'qty': qty,
            'side': side,
            'order_type': order_type,
            'account_id': account_id
        }
        
        if limit_price:
            order_data['limit_price'] = limit_price
        
        result = await self._make_request('POST', '/options/order', json=order_data)
        
        if "error" in result:
            logger.error(f"下单失败: {result['error']}")
        else:
            logger.success(f"订单提交成功: Order ID {result.get('id', 'Unknown')}")
            
        return result
    
    async def get_account_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取账户信息
        
        Args:
            account_id: 可选的账户ID
            
        Returns:
            账户信息
        """
        logger.debug(f"通过 API 获取账户信息 (account: {account_id or 'auto-route'})")
        params = {}
        if account_id:
            params['account_id'] = account_id
            
        result = await self._make_request('GET', '/account', params=params)
        
        if "error" in result:
            logger.error(f"获取账户信息失败: {result['error']}")
            
        return result
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态
        """
        return await self._make_request('GET', '/health')
    
    async def close(self):
        """关闭 HTTP 会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("API 客户端会话已关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 全局 API 客户端实例
api_client = AlpacaAPIClient()


async def get_api_client() -> AlpacaAPIClient:
    """获取 API 客户端实例"""
    return api_client