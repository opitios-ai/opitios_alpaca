"""
多用户交易系统中间件
包含认证、授权、Rate Limiting、用户上下文管理等功能
"""

import time
import json
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
from cryptography.fernet import Fernet

from config import settings


# JWT配置
JWT_SECRET = settings.jwt_secret if hasattr(settings, 'jwt_secret') else "your-secret-key"
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
    except (redis.ConnectionError, redis.TimeoutError, ConnectionRefusedError) as e:
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

# 加密实例
fernet = Fernet(Fernet.generate_key())


class UserContext:
    """用户上下文类"""
    def __init__(self, user_id: str, alpaca_credentials: dict, permissions: list, rate_limits: dict):
        self.user_id = user_id
        self.alpaca_credentials = alpaca_credentials
        self.permissions = permissions
        self.rate_limits = rate_limits
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.request_count = 0
        
    def update_activity(self):
        """更新用户活动时间"""
        self.last_active = datetime.utcnow()
        self.request_count += 1
        
    def has_permission(self, permission: str) -> bool:
        """检查用户权限"""
        return permission in self.permissions
        
    def get_alpaca_credentials(self) -> dict:
        """获取解密后的Alpaca凭据"""
        try:
            return {
                'api_key': fernet.decrypt(self.alpaca_credentials['api_key'].encode()).decode(),
                'secret_key': fernet.decrypt(self.alpaca_credentials['secret_key'].encode()).decode(),
                'paper_trading': self.alpaca_credentials.get('paper_trading', True)
            }
        except Exception as e:
            logger.error(f"解密Alpaca凭据失败: {e}")
            raise HTTPException(status_code=401, detail="Invalid credentials")


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
            return self._redis_rate_limit(identifier, limit, window_seconds, now, redis_client)
        else:
            return self._memory_rate_limit(identifier, limit, window_seconds, now)
            
    def _redis_rate_limit(self, identifier: str, limit: int, window_seconds: int, now: float, redis_client) -> tuple[bool, dict]:
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
            
    def _memory_rate_limit(self, identifier: str, limit: int, window_seconds: int, now: float) -> tuple[bool, dict]:
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
            "remaining": max(0, limit - current_requests - (1 if allowed else 0)),
            "reset_time": int(now + window_seconds),
            "current_requests": current_requests + (1 if allowed else 0)
        }
        
        return allowed, rate_limit_info


class UserContextManager:
    """用户上下文管理器"""
    
    def __init__(self):
        self.active_users: Dict[str, UserContext] = {}
        self.rate_limiter = RateLimiter()
        
    def create_user_context(self, user_data: dict) -> UserContext:
        """创建用户上下文"""
        user_id = user_data['user_id']
        
        logger.info(f"开始创建用户上下文: {user_id}")
        logger.info(f"当前活跃用户数: {len(self.active_users)}")
        
        context = UserContext(
            user_id=user_id,
            alpaca_credentials=user_data['alpaca_credentials'],
            permissions=user_data.get('permissions', ['trading', 'market_data']),
            rate_limits=user_data.get('rate_limits', {
                'requests_per_minute': 120,
                'orders_per_minute': 10,
                'market_data_per_second': 20
            })
        )
        
        self.active_users[user_id] = context
        logger.info(f"用户上下文创建成功: {user_id}, 总数: {len(self.active_users)}")
        return context
        
    def get_user_context(self, user_id: str) -> Optional[UserContext]:
        """获取用户上下文"""
        logger.info(f"查找用户上下文: {user_id}, 当前活跃用户数: {len(self.active_users)}")
        logger.info(f"当前活跃用户列表: {list(self.active_users.keys())}")
        context = self.active_users.get(user_id)
        if context:
            logger.info(f"找到用户上下文: {user_id}")
        else:
            logger.warning(f"未找到用户上下文: {user_id}")
        return context
        
    def remove_user_context(self, user_id: str):
        """移除用户上下文"""
        if user_id in self.active_users:
            del self.active_users[user_id]
            logger.info(f"用户上下文移除: {user_id}")
            
    def cleanup_inactive_users(self, max_inactive_minutes: int = 30):
        """清理非活跃用户"""
        now = datetime.utcnow()
        inactive_users = []
        
        for user_id, context in self.active_users.items():
            if (now - context.last_active).total_seconds() > max_inactive_minutes * 60:
                inactive_users.append(user_id)
                
        for user_id in inactive_users:
            self.remove_user_context(user_id)
            
        if inactive_users:
            logger.info(f"清理非活跃用户: {len(inactive_users)}个")


# 全局实例
user_manager = UserContextManager()
security = HTTPBearer()


def create_jwt_token(user_data: dict) -> str:
    """创建JWT token"""
    payload = {
        "user_id": user_data["user_id"],
        "permissions": user_data.get("permissions", ["trading", "market_data"]),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """验证JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserContext:
    """获取当前用户上下文"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    user_id = payload["user_id"]
    context = user_manager.get_user_context(user_id)
    
    if not context:
        # 如果上下文不存在但JWT有效，从数据库重新创建上下文
        logger.info(f"用户上下文不存在，从数据库重新创建: {user_id}")
        
        try:
            from app.user_manager import UserManager, User
            user_mgr = UserManager()
            user = user_mgr.db.query(User).filter_by(id=user_id).first()
            
            if not user:
                logger.error(f"数据库中未找到用户: {user_id}")
                raise HTTPException(status_code=401, detail="User not found in database")
            
            # 创建用户上下文
            user_context_data = {
                "user_id": user.id,
                "alpaca_credentials": {
                    "api_key": user.alpaca_api_key_encrypted,
                    "secret_key": user.alpaca_secret_key_encrypted,
                    "paper_trading": user.alpaca_paper_trading
                },
                "permissions": list(user.permissions.keys()) if user.permissions else [],
                "rate_limits": user.rate_limits
            }
            
            context = user_manager.create_user_context(user_context_data)
            logger.info(f"用户上下文重新创建成功: {user_id}")
            
        except Exception as e:
            logger.error(f"重新创建用户上下文失败: {user_id}, 错误: {e}")
            raise HTTPException(status_code=401, detail="Failed to create user context")
        
    context.update_activity()
    return context


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """认证中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.public_paths = [
            "/", 
            "/docs", 
            "/openapi.json", 
            "/redoc",
            "/health",
            "/api/v1/health",
            "/api/v1/test-connection",
            "/api/v1/auth/login", 
            "/api/v1/auth/register",
            # Stock quote endpoints - public access  
            "/api/v1/stocks/quote",
            "/api/v1/stocks/quotes/batch",
            # Stock quote by symbol - public access
            "/api/v1/stocks/*/quote",
            # Account and position endpoints - public for demo
            "/api/v1/account",
            "/api/v1/positions"
        ]
        
    async def dispatch(self, request: Request, call_next: Callable):
        # 跳过公共路径 (包括动态路径)
        path = request.url.path
        if path in self.public_paths or any(
            path.startswith("/api/v1/stocks/") and path.endswith("/quote") 
            for _ in [None]  # Single iteration
        ):
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
            request.state.user_id = payload["user_id"]
            request.state.permissions = payload.get("permissions", [])
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
            
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate Limiting中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        
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
        if request.url.path in ["/", "/docs", "/openapi.json", "/health"]:
            return await call_next(request)
            
        # 获取用户ID
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return await call_next(request)
            
        # 获取端点限制配置
        endpoint = request.url.path
        limit, window = self.endpoint_limits.get(endpoint, self.endpoint_limits["default"])
        
        # 检查rate limit
        allowed, rate_info = self.rate_limiter.is_allowed(
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


# 定期清理任务
import asyncio
from threading import Thread

def cleanup_task():
    """定期清理任务"""
    while True:
        try:
            user_manager.cleanup_inactive_users()
            time.sleep(300)  # 每5分钟清理一次
        except Exception as e:
            logger.error(f"清理任务错误: {e}")

# 启动清理线程
cleanup_thread = Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()