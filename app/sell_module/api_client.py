"""
API 客户端
卖出模块通过 HTTP API 调用获取数据和下单，而不是直接访问连接池
"""

import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
import time
import json
from loguru import logger


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
        
        # Rate limiting management
        self.rate_limit_reset_time = 0
        self.rate_limit_remaining = 10  # Default assumption
        self.rate_limit_total = 10
        self.last_rate_limit_check = 0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self.session is None or self.session.closed:
            # 优化超时设置：总超时60秒，连接超时10秒，读取超时30秒
            timeout = aiohttp.ClientTimeout(
                total=180,       # 总超时时间 - 增加到180秒
                connect=30,      # 连接超时 - 增加到30秒
                sock_read=120    # 读取超时 - 增加到120秒
            )
            # 增加连接池大小以支持更多并发
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=aiohttp.TCPConnector(
                    limit=100,          # 总连接池大小 - 增加到100
                    limit_per_host=50,  # 每个主机的连接数 - 增加到50
                    ttl_dns_cache=300,  # DNS缓存时间
                    use_dns_cache=True
                )
            )
        return self.session
    
    def _update_rate_limit_info(self, response_data: dict):
        """更新速率限制信息"""
        if isinstance(response_data, dict):
            # 检查是否有速率限制信息
            if "limit" in response_data:
                self.rate_limit_total = response_data.get("limit", 10)
                self.rate_limit_remaining = response_data.get("remaining", 0)
                self.rate_limit_reset_time = response_data.get("reset_time", 0)
                self.last_rate_limit_check = time.time()
                
                logger.warning(f"Rate limit info updated: {self.rate_limit_remaining}/{self.rate_limit_total}, "
                             f"reset at {self.rate_limit_reset_time}")
    
    async def _check_rate_limit(self):
        """检查并处理速率限制"""
        current_time = time.time()
        
        # 如果还在速率限制期内
        if current_time < self.rate_limit_reset_time:
            wait_time = self.rate_limit_reset_time - current_time
            logger.warning(f"Rate limit active. Waiting {wait_time:.1f} seconds until reset...")
            await asyncio.sleep(wait_time + 1)  # 额外等待1秒确保重置
            logger.info("Rate limit should be reset now, continuing...")
        
        # 如果剩余请求数很低，主动延迟
        elif self.rate_limit_remaining <= 3 and self.rate_limit_remaining > 0:
            wait_time = 10  # 增加到10秒延迟
            logger.warning(f"Rate limit approaching: only {self.rate_limit_remaining} requests remaining. "
                         f"Adding {wait_time}s delay to prevent limit...")
            await asyncio.sleep(wait_time)
    
    def _is_rate_limit_error(self, response_data: dict) -> bool:
        """检查是否为速率限制错误"""
        if isinstance(response_data, dict):
            return (
                response_data.get("detail") == "Rate limit exceeded" or
                "rate limit" in str(response_data.get("error", "")).lower() or
                "limit" in response_data
            )
        return False
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        统一的 HTTP 请求方法 - 支持速率限制管理
        
        Args:
            method: HTTP 方法 (GET, POST, etc.)
            endpoint: API 端点
            **kwargs: 传递给 aiohttp 的参数
            
        Returns:
            API 响应数据
        """
        # 检查速率限制
        await self._check_rate_limit()
        
        url = f"{self.base_url}/api/v1{endpoint}"
        session = await self._get_session()
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 检查响应中是否包含速率限制信息
                        if isinstance(result, dict):
                            self._update_rate_limit_info(result)
                            
                            # 如果是速率限制错误，等待并重试
                            if self._is_rate_limit_error(result):
                                retry_count += 1
                                if retry_count < max_retries:
                                    logger.warning(f"Rate limit hit, retrying {retry_count}/{max_retries}...")
                                    await asyncio.sleep(10 * retry_count)  # 递增延迟
                                    continue
                                else:
                                    logger.error("Max retries reached for rate limit, giving up")
                                    return result
                        
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"API request failed: {method} {url} - {response.status}: {error_text}")
                        
                        # 检查是否为429速率限制
                        if response.status == 429:
                            # 尝试从JSON或响应头中解析重置时间
                            reset_time = None
                            limit = None
                            remaining = None
                            try:
                                data = json.loads(error_text)
                                if isinstance(data, dict):
                                    reset_time = data.get("reset_time")
                                    limit = data.get("limit")
                                    remaining = data.get("remaining")
                            except Exception:
                                pass
                            # 备用：从响应头读取
                            if reset_time is None:
                                header_reset = response.headers.get("X-RateLimit-Reset")
                                try:
                                    reset_time = int(header_reset) if header_reset else None
                                except Exception:
                                    reset_time = None
                            if limit is None:
                                header_limit = response.headers.get("X-RateLimit-Limit")
                                try:
                                    limit = int(header_limit) if header_limit else None
                                except Exception:
                                    limit = None
                            if remaining is None:
                                header_remaining = response.headers.get("X-RateLimit-Remaining")
                                try:
                                    remaining = int(header_remaining) if header_remaining else None
                                except Exception:
                                    remaining = None

                            # 更新本地速率限制信息
                            if reset_time is not None:
                                self.rate_limit_reset_time = reset_time
                            if limit is not None:
                                self.rate_limit_total = limit
                            if remaining is not None:
                                self.rate_limit_remaining = remaining

                            retry_count += 1
                            if retry_count < max_retries:
                                # 精确等待到reset_time，再重试
                                now = time.time()
                                if reset_time and now < reset_time:
                                    wait_time = max(0, reset_time - now) + 1  # 多等1s保证重置
                                else:
                                    # 回退：如果没有reset_time，则使用递增延迟
                                    wait_time = 10 * retry_count
                                logger.warning(
                                    f"HTTP 429 rate limit. Waiting {wait_time:.1f}s (limit={limit}, remaining={remaining}, reset={reset_time}) before retry {retry_count}/{max_retries}"
                                )
                                await asyncio.sleep(wait_time)
                                continue
                        
                        return {"error": f"HTTP {response.status}: {error_text}"}
                        
            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Request timeout, retrying {retry_count}/{max_retries}...")
                    await asyncio.sleep(5 * retry_count)
                    continue
                else:
                    logger.error(f"API request timeout after {max_retries} retries: {method} {url}")
                    return {"error": "Request timeout"}
            except Exception as e:
                logger.error(f"API request exception: {method} {url} - {e}")
                return {"error": str(e)}
        
        # 如果循环结束了，说明达到了最大重试次数
        return {"error": f"Max retries ({max_retries}) exceeded"}
    
    async def get_all_positions(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取账户的持仓信息
        
        Args:
            account_id: 账户ID，必须提供用于多账户路由
            
        Returns:
            持仓列表
        """
        logger.debug(f"通过 API 获取持仓 (account: {account_id or 'not specified'})")
        
        params = {}
        if account_id:
            params['account_id'] = account_id
        else:
            logger.warning("No account_id provided to get_all_positions - this will likely fail")
            
        result = await self._make_request('GET', '/positions', params=params)
        
        if "error" in result:
            logger.error(f"获取持仓失败: {result['error']}")
            return []
            
        return result if isinstance(result, list) else []
    
    async def get_all_orders(self, account_id: Optional[str] = None, status: str = 'open') -> List[Dict[str, Any]]:
        """
        获取账户的订单信息
        
        Args:
            account_id: 账户ID，必须提供用于多账户路由
            status: 订单状态过滤，支持单个状态或逗号分隔的多个状态 (如 'open,accepted,replaced')
            
        Returns:
            订单列表
        """
        logger.debug(f"通过 API 获取订单 (account: {account_id or 'not specified'}, status={status})")
        
        params = {}
        if account_id:
            params['account_id'] = account_id
        else:
            logger.warning("No account_id provided to get_all_orders - this will likely fail")
            
        if status:
            params['status'] = status
            
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
    
    async def get_option_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        获取期权报价 - 市场数据，不需要账户ID
        
        ⚠️ DEPRECATED: OptimizedStrategy uses position.current_price directly.
        This method is only used for fallback/traditional strategy.
        
        Args:
            symbols: 期权符号列表
            
        Returns:
            期权报价数据
        """
        logger.warning(f"使用已弃用的 get_option_quotes 方法获取 {len(symbols)} 个期权报价 - 考虑使用 OptimizedStrategy")
            
        result = await self._make_request(
            'POST', 
            '/options/quotes/batch',
            json={'option_symbols': symbols}
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
        logger.info(f"通过API下期权订单: {option_symbol} x{qty} {side} (account: {account_id})")

        order_data = {
            'option_symbol': option_symbol,
            'qty': qty,
            'side': side,
            'type': 'limit',        # 使用正确的字段名
            'limit_price': 0.01     # 使用正确的数据类型
        }

        # Server expects account_id as query param via routing dependency
        result = await self._make_request('POST', '/options/order', params={'account_id': account_id}, json=order_data)
        
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
            try:
                await self.session.close()
                logger.debug("API 客户端会话已关闭")
            except Exception as e:
                logger.warning(f"关闭 API 客户端会话时出错: {e}")
        self.session = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 全局 API 客户端实例
api_client = AlpacaAPIClient()


def get_api_client() -> AlpacaAPIClient:
    """获取 API 客户端实例"""
    return api_client