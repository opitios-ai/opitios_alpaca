"""
多用户管理系统
支持用户注册、认证、权限管理、资源隔离
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from cryptography.fernet import Fernet
from loguru import logger

from app.logging_config import UserLogger
from config import settings


# 数据库配置
DATABASE_URL = getattr(settings, 'database_url', 'sqlite:///./users.db')
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 加密密钥 (生产环境应使用环境变量)
ENCRYPTION_KEY = getattr(settings, 'encryption_key', Fernet.generate_key())
fernet = Fernet(ENCRYPTION_KEY)


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    PREMIUM = "premium"
    STANDARD = "standard"
    DEMO = "demo"


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


@dataclass
class RateLimitConfig:
    """Rate Limit配置"""
    requests_per_minute: int = 60
    orders_per_minute: int = 10
    market_data_per_second: int = 10
    batch_size_limit: int = 20


@dataclass
class UserPermissions:
    """用户权限配置"""
    can_trade: bool = True
    can_view_market_data: bool = True
    can_place_orders: bool = True
    can_cancel_orders: bool = True
    can_view_positions: bool = True
    can_view_account: bool = True
    paper_trading_only: bool = True


# 数据库模型
class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default=UserRole.STANDARD.value)
    status = Column(String, nullable=False, default=UserStatus.ACTIVE.value)
    
    # Alpaca凭据 (加密存储)
    alpaca_api_key_encrypted = Column(Text, nullable=True)
    alpaca_secret_key_encrypted = Column(Text, nullable=True)
    alpaca_paper_trading = Column(Boolean, default=True)
    
    # 权限和限制配置
    permissions = Column(JSON, nullable=False)
    rate_limits = Column(JSON, nullable=False)
    
    # 使用统计
    total_requests = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    last_login = Column(DateTime, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def encrypt_alpaca_credentials(self, api_key: str, secret_key: str):
        """加密并存储Alpaca凭据"""
        self.alpaca_api_key_encrypted = fernet.encrypt(api_key.encode()).decode()
        self.alpaca_secret_key_encrypted = fernet.encrypt(secret_key.encode()).decode()
    
    def decrypt_alpaca_credentials(self) -> Tuple[str, str]:
        """解密Alpaca凭据"""
        try:
            api_key = fernet.decrypt(self.alpaca_api_key_encrypted.encode()).decode()
            secret_key = fernet.decrypt(self.alpaca_secret_key_encrypted.encode()).decode()
            return api_key, secret_key
        except Exception as e:
            logger.error(f"解密Alpaca凭据失败: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt credentials")
    
    def has_permission(self, permission: str) -> bool:
        """检查用户权限"""
        return self.permissions.get(permission, False)
    
    def get_rate_limit(self, limit_type: str) -> int:
        """获取rate limit配置"""
        return self.rate_limits.get(limit_type, 0)


class UserSession(Base):
    """用户会话表"""
    __tablename__ = "user_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    session_token = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class UserActivity(Base):
    """用户活动日志表"""
    __tablename__ = "user_activities"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    activity_type = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# 创建表
Base.metadata.create_all(bind=engine)


# Pydantic模型
class UserRegistrationRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_paper_trading: bool = True


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: UserRole
    status: UserStatus
    permissions: Dict
    rate_limits: Dict
    alpaca_paper_trading: bool
    total_requests: int
    total_orders: int
    last_login: Optional[datetime]
    created_at: datetime


class UserManager:
    """用户管理器"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def get_db(self) -> Session:
        """获取数据库会话"""
        try:
            yield self.db
        finally:
            self.db.close()
    
    def hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        return self.hash_password(password) == password_hash
    
    def get_default_permissions(self, role: UserRole) -> Dict:
        """获取默认权限配置"""
        permissions_config = {
            UserRole.ADMIN: UserPermissions(
                can_trade=True,
                can_view_market_data=True,
                can_place_orders=True,
                can_cancel_orders=True,
                can_view_positions=True,
                can_view_account=True,
                paper_trading_only=False
            ),
            UserRole.PREMIUM: UserPermissions(
                can_trade=True,
                can_view_market_data=True,
                can_place_orders=True,
                can_cancel_orders=True,
                can_view_positions=True,
                can_view_account=True,
                paper_trading_only=True
            ),
            UserRole.STANDARD: UserPermissions(
                can_trade=True,
                can_view_market_data=True,
                can_place_orders=True,
                can_cancel_orders=True,
                can_view_positions=True,
                can_view_account=True,
                paper_trading_only=True
            ),
            UserRole.DEMO: UserPermissions(
                can_trade=False,
                can_view_market_data=True,
                can_place_orders=False,
                can_cancel_orders=False,
                can_view_positions=True,
                can_view_account=True,
                paper_trading_only=True
            )
        }
        
        return asdict(permissions_config.get(role, permissions_config[UserRole.STANDARD]))
    
    def get_default_rate_limits(self, role: UserRole) -> Dict:
        """获取默认rate limit配置"""
        rate_limits_config = {
            UserRole.ADMIN: RateLimitConfig(
                requests_per_minute=300,
                orders_per_minute=50,
                market_data_per_second=50,
                batch_size_limit=100
            ),
            UserRole.PREMIUM: RateLimitConfig(
                requests_per_minute=120,
                orders_per_minute=20,
                market_data_per_second=20,
                batch_size_limit=50
            ),
            UserRole.STANDARD: RateLimitConfig(
                requests_per_minute=60,
                orders_per_minute=10,
                market_data_per_second=10,
                batch_size_limit=20
            ),
            UserRole.DEMO: RateLimitConfig(
                requests_per_minute=30,
                orders_per_minute=0,
                market_data_per_second=5,
                batch_size_limit=10
            )
        }
        
        return asdict(rate_limits_config.get(role, rate_limits_config[UserRole.STANDARD]))
    
    def create_user(self, registration_data: UserRegistrationRequest, 
                   role: UserRole = UserRole.STANDARD) -> User:
        """创建新用户"""
        # 检查用户是否已存在
        existing_user = self.db.query(User).filter(
            (User.email == registration_data.email) | 
            (User.username == registration_data.username)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="User with this email or username already exists"
            )
        
        # 创建新用户
        user = User(
            email=registration_data.email,
            username=registration_data.username,
            password_hash=self.hash_password(registration_data.password),
            role=role.value,
            status=UserStatus.ACTIVE.value,
            permissions=self.get_default_permissions(role),
            rate_limits=self.get_default_rate_limits(role),
            alpaca_paper_trading=registration_data.alpaca_paper_trading
        )
        
        # 加密并存储Alpaca凭据
        user.encrypt_alpaca_credentials(
            registration_data.alpaca_api_key,
            registration_data.alpaca_secret_key
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # 记录用户注册
        UserLogger.log_user_operation(
            user_id=user.id,
            operation="user_registration",
            details={
                "email": user.email,
                "username": user.username,
                "role": user.role
            }
        )
        
        logger.info(f"新用户注册: {user.username} ({user.email})")
        return user
    
    def authenticate_user(self, login_data: UserLoginRequest) -> Optional[User]:
        """用户认证"""
        user = self.db.query(User).filter(
            User.username == login_data.username
        ).first()
        
        if not user or not self.verify_password(login_data.password, user.password_hash):
            UserLogger.log_security_event(
                user_id=user.id if user else None,
                event_type="failed_login",
                severity="medium",
                details={
                    "username": login_data.username,
                    "reason": "invalid_credentials"
                }
            )
            return None
        
        if user.status != UserStatus.ACTIVE.value:
            UserLogger.log_security_event(
                user_id=user.id,
                event_type="login_blocked",
                severity="high",
                details={
                    "username": user.username,
                    "status": user.status,
                    "reason": "user_not_active"
                }
            )
            raise HTTPException(status_code=403, detail=f"User account is {user.status}")
        
        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        self.db.commit()
        
        # 记录成功登录
        UserLogger.log_user_operation(
            user_id=user.id,
            operation="user_login",
            details={
                "username": user.username,
                "last_login": user.last_login.isoformat()
            }
        )
        
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def update_user_activity(self, user_id: str, activity_type: str, 
                           details: Optional[Dict] = None):
        """更新用户活动"""
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            details=details or {}
        )
        
        self.db.add(activity)
        self.db.commit()
    
    def increment_user_stats(self, user_id: str, requests: int = 0, orders: int = 0):
        """增加用户统计数据"""
        user = self.get_user_by_id(user_id)
        if user:
            user.total_requests += requests
            user.total_orders += orders
            self.db.commit()
    
    def get_user_stats(self, user_id: str) -> Dict:
        """获取用户统计信息"""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        
        # 获取最近的活动统计
        recent_activities = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        return {
            "total_requests": user.total_requests,
            "total_orders": user.total_orders,
            "recent_activities": recent_activities,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "account_age_days": (datetime.utcnow() - user.created_at).days
        }


# 全局用户管理器实例
user_manager = UserManager()

# 依赖注入函数
def get_user_manager() -> UserManager:
    """获取用户管理器实例"""
    return user_manager