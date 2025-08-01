"""
用户认证和管理路由
包含注册、登录、用户管理等功能
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List

from app.user_manager import (
    UserManager, UserRegistrationRequest, UserLoginRequest, 
    UserResponse, get_user_manager, UserRole
)
from app.middleware import create_jwt_token, get_current_user, UserContext
from app.logging_config import UserLogger
from app.connection_pool import get_connection_pool, ConnectionPool

# 创建认证路由
auth_router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@auth_router.post("/register", response_model=UserResponse)
async def register_user(
    registration_data: UserRegistrationRequest,
    user_manager: UserManager = Depends(get_user_manager)
):
    """用户注册"""
    try:
        # 创建用户
        user = user_manager.create_user(registration_data)
        
        # 记录注册事件
        UserLogger.log_user_operation(
            user_id=user.id,
            operation="user_registration",
            details={
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        )
        
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            role=UserRole(user.role),
            status=user.status,
            permissions=user.permissions,
            rate_limits=user.rate_limits,
            alpaca_paper_trading=user.alpaca_paper_trading,
            total_requests=user.total_requests,
            total_orders=user.total_orders,
            last_login=user.last_login,
            created_at=user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@auth_router.post("/login")
async def login_user(
    login_data: UserLoginRequest,
    user_manager: UserManager = Depends(get_user_manager)
):
    """用户登录"""
    try:
        # 验证用户
        user = user_manager.authenticate_user(login_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # 生成JWT token
        token = create_jwt_token({
            "user_id": user.id,
            "permissions": list(user.permissions.keys()) if user.permissions else []
        })
        
        # 创建用户上下文 (在middleware的用户管理器中)
        from app.middleware import user_manager as middleware_user_manager
        from loguru import logger
        
        logger.info(f"[CRITICAL] Starting context creation for user {user.id}")
        print(f"[CRITICAL] Starting context creation for user {user.id}")
        
        try:
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
            
            logger.info(f"上下文数据准备完成: {user.id}")
            context = middleware_user_manager.create_user_context(user_context_data)
            logger.info(f"用户上下文创建完成: {user.id}, 实例ID: {id(middleware_user_manager)}")
            
        except Exception as context_error:
            logger.error(f"创建用户上下文失败: {user.id}, 错误: {context_error}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            # 不抛出异常，继续返回token
        
        # 记录登录事件
        UserLogger.log_user_operation(
            user_id=user.id,
            operation="user_login",
            details={"username": user.username}
        )
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": UserResponse(
                id=user.id,
                email=user.email,
                username=user.username,
                role=UserRole(user.role),
                status=user.status,
                permissions=user.permissions,
                rate_limits=user.rate_limits,
                alpaca_paper_trading=user.alpaca_paper_trading,
                total_requests=user.total_requests,
                total_orders=user.total_orders,
                last_login=user.last_login,
                created_at=user.created_at
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserContext = Depends(get_current_user),
    user_manager: UserManager = Depends(get_user_manager)
):
    """获取当前用户信息"""
    user = user_manager.get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=UserRole(user.role),
        status=user.status,
        permissions=user.permissions,
        rate_limits=user.rate_limits,
        alpaca_paper_trading=user.alpaca_paper_trading,
        total_requests=user.total_requests,
        total_orders=user.total_orders,
        last_login=user.last_login,
        created_at=user.created_at
    )


@auth_router.get("/stats")
async def get_user_stats(
    current_user: UserContext = Depends(get_current_user),
    user_manager: UserManager = Depends(get_user_manager)
):
    """获取用户统计信息"""
    stats = user_manager.get_user_stats(current_user.user_id)
    return {
        "user_id": current_user.user_id,
        "stats": stats,
        "current_session": {
            "request_count": current_user.request_count,
            "session_duration_minutes": (
                (current_user.last_active - current_user.created_at).total_seconds() / 60
            ),
            "last_active": current_user.last_active.isoformat()
        }
    }


@auth_router.get("/connection-pool/stats")
async def get_connection_pool_stats(
    current_user: UserContext = Depends(get_current_user),
    pool: ConnectionPool = Depends(get_connection_pool)
):
    """获取连接池统计信息 (需要admin权限)"""
    if not current_user.has_permission("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    
    return pool.get_pool_stats()


@auth_router.delete("/logout")
async def logout_user(
    current_user: UserContext = Depends(get_current_user)
):
    """用户登出"""
    # 记录登出事件
    UserLogger.log_user_operation(
        user_id=current_user.user_id,
        operation="user_logout",
        details={}
    )
    
    return {"message": "Successfully logged out"}


# 管理员路由
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: UserContext = Depends(get_current_user),
    user_manager: UserManager = Depends(get_user_manager),
    skip: int = 0,
    limit: int = 100
):
    """列出所有用户 (管理员功能)"""
    if not current_user.has_permission("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    
    # 这里需要实现数据库查询分页
    # 暂时返回空列表
    return []


@admin_router.get("/system/stats")
async def get_system_stats(
    current_user: UserContext = Depends(get_current_user),
    pool: ConnectionPool = Depends(get_connection_pool)
):
    """获取系统统计信息 (管理员功能)"""
    if not current_user.has_permission("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    
    pool_stats = pool.get_pool_stats()
    
    return {
        "connection_pool": pool_stats,
        "system_info": {
            "timestamp": UserLogger.log_user_operation.__module__,  # 占位符
            "active_users": pool_stats["total_users"],
            "total_connections": pool_stats["total_connections"]
        }
    }