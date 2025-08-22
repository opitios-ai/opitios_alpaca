"""
简化的认证和限流中间件
支持外部JWT验证、内网判断和基础限流功能
"""

import time
import hashlib
import ipaddress
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
JWT_ALGORITHM = "HS512"
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


def get_allowed_external_ips():
    """获取允许的外部IP列表"""
    try:
        from config import secrets
        return secrets.get('allowed_external_ips', [])
    except Exception as e:
        logger.warning(f"Failed to load allowed external IPs: {e}")
        return []

def is_internal_ip(ip: str) -> bool:
    """判断是否为内网IP"""
    try:
        # 检查白名单IP
        allowed_external_ips = get_allowed_external_ips()
        if ip in allowed_external_ips:
            return True
            
        # 检查私有IP地址
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback:
            return True
            
        # 检查特殊网段 (如果需要)
        # if ip_obj in ipaddress.ip_network("100.64.0.0/10"):
        #     return True
            
        return False
    except ValueError:
        logger.warning(f"Invalid IP address format: {ip}")
        return False

def verify_jwt_token(token: str) -> dict:
    """验证JWT token - 支持外部token"""
    try:
        logger.info(f"Verifying JWT token with secret: {JWT_SECRET[:10]}... algorithm: {JWT_ALGORITHM}")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        logger.info(f"JWT verification successful for user: {payload.get('username', 'unknown')}")
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.error(f"JWT token expired: {e}")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.DecodeError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT invalid token error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"JWT verification unexpected error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def internal_or_jwt_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
):
    """内网或JWT认证 - 参考 Opitios_Service 的实现"""
    client_ip = request.client.host if request.client else "unknown"
    is_internal = is_internal_ip(client_ip)
    
    logger.debug(f"Client IP: {client_ip}, Is Internal: {is_internal}")
    
    if is_internal:
        # 内部访问：尝试解析token获取用户信息，如果没有token则仅标记为内部访问
        user_data = None
        if credentials and credentials.credentials:
            try:
                payload = verify_jwt_token(credentials.credentials)
                user_data = payload
                logger.debug(f"Internal access with valid token: {user_data.get('user_id', 'unknown')}")
            except HTTPException:
                logger.debug("Internal access with invalid token, proceeding without user data")
                pass
        else:
            logger.debug("Internal access without token")
        
        return {
            "ip": client_ip, 
            "internal": True,
            "user": user_data  # 如果有有效token则包含用户信息，否则为None
        }
    
    # 外网IP，必须有JWT
    token = credentials.credentials if credentials else None
    payload = verify_jwt_token(token) if token else None
    
    if not payload:
        logger.warning(f"External IP {client_ip} attempted access without valid JWT")
        raise HTTPException(status_code=401, detail="Invalid or missing JWT token")
        
    logger.debug(f"External access with valid token: {payload.get('user_id', 'unknown')}")
    return {"ip": client_ip, "internal": False, "user": payload}

async def get_current_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
) -> RequestContext:
    """获取当前请求上下文 - 支持内网免JWT"""
    auth_result = await internal_or_jwt_auth(request, credentials)
    
    # 如果是内网访问且没有用户信息，创建默认上下文
    if auth_result["internal"] and not auth_result["user"]:
        default_payload = {
            "user_id": "internal_user",
            "account_id": None,
            "permissions": ["trading", "market_data", "admin"]  # 内网默认给予所有权限
        }
        context = RequestContext(default_payload)
    else:
        # 使用JWT中的用户信息
        user_data = auth_result["user"]
        context = RequestContext(user_data)
    
    context.update_activity()
    return context


# 向后兼容的别名
get_current_user = get_current_context


def role_required(roles: list[str]):
    """角色权限检查装饰器"""
    def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
    ):
        # 使用内网或JWT认证
        import asyncio
        auth_result = asyncio.create_task(internal_or_jwt_auth(request, credentials))
        auth_data = asyncio.get_event_loop().run_until_complete(auth_result)
        
        # 内网/白名单IP直接放行
        if auth_data.get('internal'):
            logger.debug(f"Internal IP {auth_data.get('ip')} bypassing role check")
            return
            
        payload = auth_data.get('user')
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid user account")
            
        user_role = payload.get('permission_group') or payload.get('role', 'user')
        
        if user_role not in roles:
            raise HTTPException(
                status_code=403, 
                detail=f"You need one of roles: {roles}. Current role: {user_role}"
            )
    return dependency

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """支持内网免JWT的认证中间件"""
    
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
            "/api/v1/auth/admin-token",  # 新增管理员token端点
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
        
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"
        is_internal = is_internal_ip(client_ip)
        
        # 内网访问：可选JWT
        if is_internal:
            logger.debug(f"Internal IP {client_ip} accessing {path}")
            
            # 尝试获取JWT信息（如果有的话）
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                    payload = verify_jwt_token(token)
                    request.state.user_id = payload.get("user_id", "internal_user")
                    request.state.account_id = payload.get("account_id")
                    request.state.permissions = payload.get("permissions", ["trading", "market_data", "admin"])
                    request.state.internal = True
                    logger.debug(f"Internal access with JWT: {request.state.user_id}")
                except HTTPException:
                    # JWT无效，但内网访问仍然允许
                    request.state.user_id = "internal_user"
                    request.state.account_id = None
                    request.state.permissions = ["trading", "market_data", "admin"]
                    request.state.internal = True
                    logger.debug("Internal access with invalid JWT, using default permissions")
            else:
                # 内网访问，无JWT
                request.state.user_id = "internal_user"
                request.state.account_id = None
                request.state.permissions = ["trading", "market_data", "admin"]
                request.state.internal = True
                logger.debug("Internal access without JWT, using default permissions")
                
            return await call_next(request)
        
        # 外网访问：必须有JWT
        logger.debug(f"External IP {client_ip} accessing {path}")
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"External IP {client_ip} missing authorization header")
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
            request.state.internal = False
            logger.debug(f"External access with valid JWT: {request.state.user_id}")
        except HTTPException as e:
            logger.warning(f"External IP {client_ip} invalid JWT: {e.detail}")
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