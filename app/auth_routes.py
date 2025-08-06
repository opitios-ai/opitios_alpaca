"""
简化的JWT认证路由
仅包含基础的JWT验证功能，支持外部token验证
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from pydantic import BaseModel

from app.middleware import verify_jwt_token
from app.demo_jwt import generate_demo_jwt_token, get_demo_user_info
from config import settings

# 创建认证路由
auth_router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


class TokenVerificationResponse(BaseModel):
    """Token验证响应"""
    valid: bool
    user_id: Optional[str] = None
    permissions: Optional[list] = None
    exp: Optional[int] = None
    message: Optional[str] = None


@auth_router.post("/verify-token", response_model=TokenVerificationResponse)
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证JWT Token"""
    try:
        payload = verify_jwt_token(credentials.credentials)
        return TokenVerificationResponse(
            valid=True,
            user_id=payload.get("user_id"),
            permissions=payload.get("permissions", []),
            exp=payload.get("exp"),
            message="Token is valid"
        )
    except HTTPException as e:
        return TokenVerificationResponse(
            valid=False,
            message=e.detail
        )


# 演示JWT端点
@auth_router.get("/demo-token")
async def get_demo_jwt_token():
    """获取演示JWT Token - 用于Swagger UI快速测试"""
    token = generate_demo_jwt_token(expire_hours=168)  # 7天有效期
    user_info = get_demo_user_info()
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 168 * 3600,  # 7天转换为秒
        "demo_user": user_info,
        "usage_instructions": [
            "1. 复制 access_token 的值",
            "2. 点击 Swagger UI 右上角的 'Authorize' 按钮",
            "3. 输入: Bearer 后面跟上token (例如: Bearer eyJ0eXAiOiJKV1Q...)",
            "4. 点击 'Authorize' 按钮",
            "5. 现在可以测试所有需要JWT认证的端点"
        ],
        "note": "这是一个演示token，仅用于测试目的。实际使用中请通过外部系统获取有效token。"
    }


# 简化的管理员路由
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/account-pool/stats")
async def get_account_pool_stats():
    """获取账户连接池统计信息"""
    from app.account_pool import get_account_pool
    pool = get_account_pool()
    return pool.get_pool_stats()


@admin_router.get("/system/health")
async def get_system_health():
    """获取系统健康状态"""
    from app.account_pool import get_account_pool
    pool = get_account_pool()
    pool_stats = pool.get_pool_stats()
    
    return {
        "status": "healthy",
        "account_pool": pool_stats,
        "system_info": {
            "timestamp": "placeholder",
            "active_accounts": pool_stats.get("active_accounts", 0),
            "total_connections": pool_stats.get("total_connections", 0)
        }
    }


@auth_router.get("/alpaca-credentials")
async def get_alpaca_credentials():
    """获取Alpaca WebSocket测试凭据"""
    # 直接从secrets.yml返回账户凭据
    return {
        "api_key": "PK8T7QYKN7SN9EDDMC09",
        "secret_key": "dhRGqLVvzqGUIYGY87eKw4osEZFbPnCMjuBL2ijV",
        "account_name": "Primary Trading Account",
        "paper_trading": True,
        "endpoints": {
            "stock_ws": "wss://stream.data.alpaca.markets/v2/iex",
            "option_ws": "wss://stream.data.alpaca.markets/v1beta1/indicative", 
            "test_ws": "wss://stream.data.alpaca.markets/v2/test"
        },
        "note": "这些是真实的Alpaca API凭据，用于WebSocket连接测试"
    }