"""
简化的JWT认证路由
仅包含基础的JWT验证功能，支持外部token验证
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from pydantic import BaseModel

from app.middleware import verify_jwt_token, create_jwt_token, is_internal_ip, internal_or_jwt_auth
# Demo JWT imports only for development - not used in production
# from app.demo_jwt import generate_demo_jwt_token, get_demo_user_info
from config import settings
from fastapi import Request

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
async def verify_token(
        credentials: HTTPAuthorizationCredentials = Depends(security)
):
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
        # Re-raise HTTPException to return proper status codes
        raise e
    except Exception as e:
        # For unexpected errors, return 400 Bad Request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token validation failed: {str(e)}"
        )


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


@auth_router.get("/admin-token")
async def get_admin_token(request: Request):
    """生成管理员JWT Token - 仅限内网访问"""
    client_ip = request.client.host if request.client else "unknown"

    # 检查是否为内网IP
    if not is_internal_ip(client_ip):
        raise HTTPException(
            status_code=403,
            detail="Admin token generation is only allowed from internal network"
        )

    # 创建管理员token
    admin_user_data = {
        "user_id": "admin_user",
        "account_id": "admin_account",
        "permissions": ["trading", "market_data", "admin", "bulk_place"],
        "role": "admin",
        "permission_group": "admin"
    }

    token = create_jwt_token(admin_user_data)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 24 * 3600,  # 24小时
        "user_info": admin_user_data,
        "client_ip": client_ip,
        "usage_instructions": [
            "1. 复制 access_token 的值",
            "2. 在API请求中添加 Authorization header: Bearer <token>",
            "3. 或在 Swagger UI 中点击 'Authorize' 按钮输入token",
            "4. 现在可以访问所有管理员端点，包括批量下单功能"
        ],
        "permissions": admin_user_data["permissions"],
        "note": "这是管理员token，拥有所有权限，包括批量下单功能。仅限内网生成。"
    }
