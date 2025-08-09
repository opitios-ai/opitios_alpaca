"""
简化的认证和限流中间件
支持外部JWT验证和基础限流功能
"""

import time
import hashlib
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque

from fastapi import Request, Response, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger
import jwt
import redis

from config import settings


# JWT配置
JWT_SECRET = (
    settings.jwt_secret if hasattr(settings, 'jwt_secret')
    else "your-secret-key"
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Redis连接 (用于分布式rate limiting)
redis_client = None
redis_available = False

def initialize_redis():
    """初始化Redis连接"""
    global redis_client, redis_available
    try:
        redis_client = redis.Redis(
            host=getattr(settings, 'redis_host', 'localhost'),
            port=getattr(settings, 'redis_port', 6379),
            db=getattr(settings, 'redis_db', 0),
            password=getattr(settings, 'redis_password', None),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        # 测试连接
        redis_client.ping()
        redis_available = True
        logger.info("Redis连接成功，启用分布式rate limiting")
    except (
        redis.ConnectionError,
        redis.TimeoutError,
        ConnectionRefusedError
    ) as e:
        logger.warning(f"Redis连接失败，使用内存rate limiting: {e}")
        redis_client = None
        redis_available = False
    except Exception as e:
        logger.error(f"Redis初始化出现未预期错误: {e}")
        redis_client = None
        redis_available = False

# 初始化Redis连接
initialize_redis()

def get_redis_client():
    """获取Redis客户端，如果不可用则返回None"""
    global redis_available
    if not redis_available:
        return None
    
    try:
        # 检查连接健康状态
        if redis_client:
            redis_client.ping()
        return redis_client
    except Exception as e:
        logger.warning(f"Redis连接检查失败，切换到内存模式: {e}")
        redis_available = False
        return None

class RequestContext:
    """简化的请求上下文类"""
    def __init__(self, token_payload: dict):
        self.user_id = token_payload.get("user_id", "external_user")
        self.account_id = token_payload.get("account_id")  # 可选的账户ID
        self.permissions = token_payload.get("permissions", [])
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.request_count = 0
        
    def update_activity(self):
        """更新活动时间"""
        self.last_active = datetime.utcnow()
        self.request_count += 1
        
    def has_permission(self, permission: str) -> bool:
        """检查权限"""
        return permission in self.permissions


class RateLimiter:
    """Rate Limiting类"""
    
    def __init__(self):
        # 内存存储 (如果Redis不可用)
        self.memory_store = defaultdict(lambda: defaultdict(deque))
        
    def _get_key(self, identifier: str, window: str) -> str:
        """生成Redis key"""
        return f"rate_limit:{identifier}:{window}"
        
    def _clean_old_requests(self, requests: deque, window_seconds: int):
        """清理过期的请求记录"""
        now = time.time()
        while requests and requests[0] < now - window_seconds:
            requests.popleft()
            
    def is_allowed(self, identifier: str, limit: int, window_seconds: int) -> tuple[bool, dict]:
        """
        检查是否允许请求
        返回: (是否允许, 限制信息)
        """
        now = time.time()
        
        redis_client = get_redis_client()
        if redis_client:
            return self._redis_rate_limit(
                identifier, limit, window_seconds, now, redis_client
            )
        else:
            return self._memory_rate_limit(
                identifier, limit, window_seconds, now
            )
            
    def _redis_rate_limit(
        self, identifier: str, limit: int, window_seconds: int,
        now: float, redis_client
    ) -> tuple[bool, dict]:
        """使用Redis的rate limiting"""
        try:
            key = self._get_key(identifier, str(window_seconds))
            
            # 使用Redis的sliding window算法
            with redis_client.pipeline() as pipe:
                pipe.multi()
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window_seconds)
                results = pipe.execute()
                
            current_requests = results[1]
            
            rate_limit_info = {
                "limit": limit,
                "remaining": max(0, limit - current_requests - 1),
                "reset_time": int(now + window_seconds),
                "current_requests": current_requests + 1
            }
            
            return current_requests < limit, rate_limit_info
            
        except Exception as e:
            logger.error(f"Redis rate limiting错误: {e}")
            # 标记Redis为不可用，下次直接使用内存模式
            global redis_available
            redis_available = False
            return self._memory_rate_limit(identifier, limit, window_seconds, now)
            
    def _memory_rate_limit(
        self, identifier: str, limit: int, window_seconds: int, now: float
    ) -> tuple[bool, dict]:
        """使用内存的rate limiting"""
        requests = self.memory_store[identifier][window_seconds]
        
        # 清理过期请求
        self._clean_old_requests(requests, window_seconds)
        
        # 检查限制
        current_requests = len(requests)
        allowed = current_requests < limit
        
        if allowed:
            requests.append(now)
            
        rate_limit_info = {
            "limit": limit,
            "remaining": max(
                0, limit - current_requests - (1 if allowed else 0)
            ),
            "reset_time": int(now + window_seconds),
            "current_requests": current_requests + (1 if allowed else 0)
        }
        
        return allowed, rate_limit_info


# 全局实例
security = HTTPBearer()
rate_limiter = RateLimiter()


def create_jwt_token(user_data: dict) -> str:
    """创建JWT token - 主要用于演示"""
    payload = {
        "user_id": user_data.get("user_id", "demo_user"),
        "account_id": user_data.get("account_id"),
        "permissions": user_data.get("permissions", ["trading", "market_data"]),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """验证JWT token - 支持外部token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_context(credentials: HTTPAuthorizationCredentials = Depends(security)) -> RequestContext:
    """获取当前请求上下文"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    # 创建简化的请求上下文
    context = RequestContext(payload)
    context.update_activity()
    return context


# 向后兼容的别名
get_current_user = get_current_context


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """简化的认证中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.public_paths = [
            "/", 
            "/docs", 
            "/openapi.json", 
            "/redoc",
            "/health",
            "/api/v1/health",
            "/api/v1/health/",
            "/api/v1/health/comprehensive",
            "/api/v1/health/trading-permissions",
            "/api/v1/health/websocket-status",
            "/api/v1/health/last-check",
            "/api/v1/health/background-check",
            "/api/v1/test-connection",
            "/api/v1/auth/demo-token",
            "/api/v1/auth/verify-token",
            "/api/v1/auth/alpaca-credentials",
            # 静态文件路径
            "/static",
            "/favicon.ico",
            # 演示模式 - 部分端点公开访问
            "/api/v1/stocks/quote",
            "/api/v1/stocks/quotes/batch",
            "/api/v1/account",
            "/api/v1/positions"
        ]
        
    async def dispatch(self, request: Request, call_next: Callable):
        # 跳过公共路径
        path = request.url.path
        
        # Debug logging
        from loguru import logger
        logger.debug(f"AuthMiddleware checking path: {path}")
        
        # Check for health endpoints first
        if path.startswith("/api/v1/health"):
            logger.debug(f"Skipping auth for health endpoint: {path}")
            return await call_next(request)
            
        if (path in self.public_paths or 
            path.startswith("/static/") or
            any(path.startswith("/api/v1/stocks/") and path.endswith("/quote") for _ in [None])):
            logger.debug(f"Skipping auth for public path: {path}")
            return await call_next(request)
            
        # 检查Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid authorization header"}
            )
            
        try:
            token = auth_header.split(" ")[1]
            payload = verify_jwt_token(token)
            request.state.user_id = payload.get("user_id", "external_user")
            request.state.account_id = payload.get("account_id")
            request.state.permissions = payload.get("permissions", [])
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
            
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简化的Rate Limiting中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # 不同端点的限制配置
        self.endpoint_limits = {
            "/api/v1/stocks/quote": (60, 60),  # 60 requests per minute
            "/api/v1/stocks/quotes/batch": (30, 60),  # 30 requests per minute
            "/api/v1/options/quote": (60, 60),
            "/api/v1/options/quotes/batch": (20, 60),
            "/api/v1/stocks/order": (10, 60),  # 10 orders per minute
            "/api/v1/options/order": (10, 60),
            "default": (120, 60)  # 默认限制
        }
        
    async def dispatch(self, request: Request, call_next: Callable):
        # 跳过公共路径
        if request.url.path in ["/", "/docs", "/openapi.json", "/health"] or \
           request.url.path.startswith("/api/v1/health/"):
            return await call_next(request)
            
        # 获取用户/账户ID
        user_id = getattr(request.state, "user_id", None) or getattr(request.state, "account_id", "anonymous")
        if not user_id or user_id == "anonymous":
            return await call_next(request)
            
        # 获取端点限制配置
        endpoint = request.url.path
        limit, window = self.endpoint_limits.get(endpoint, self.endpoint_limits["default"])
        
        # 检查rate limit
        allowed, rate_info = rate_limiter.is_allowed(
            f"user:{user_id}:{endpoint}", limit, window
        )
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": rate_info["limit"],
                    "remaining": rate_info["remaining"],
                    "reset_time": rate_info["reset_time"]
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset_time"])
                }
            )
            
        # 执行请求
        response = await call_next(request)
        
        # 添加rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset_time"])
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()
        
        # 获取用户信息
        user_id = getattr(request.state, "user_id", "anonymous")
        
        # 记录请求
        logger.info(
            "Request started",
            extra={
                "user_id": user_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        )
        
        # 执行请求
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 记录响应
        logger.info(
            "Request completed",
            extra={
                "user_id": user_id,
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "process_time": round(process_time, 4)
            }
        )
        
        # 添加处理时间header
        response.headers["X-Process-Time"] = str(round(process_time, 4))
        
        return response


# Middleware completed - no background cleanup needed for stateless authentication