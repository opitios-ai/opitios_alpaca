"""
演示JWT Token生成器
为测试目的生成固定的JWT token
"""

import jwt
from datetime import datetime, timedelta
from config import settings

# 固定的演示用户信息
DEMO_USER = {
    "user_id": "demo_user_123",
    "username": "demo_user", 
    "permissions": ["trading", "market_data", "admin"],
    "email": "demo@example.com"
}

def generate_demo_jwt_token(expire_hours: int = 24) -> str:
    """生成固定的演示JWT token"""
    payload = {
        "user_id": DEMO_USER["user_id"],
        "username": DEMO_USER["username"],
        "permissions": DEMO_USER["permissions"],
        "email": DEMO_USER["email"],
        "exp": datetime.utcnow() + timedelta(hours=expire_hours),
        "iat": datetime.utcnow(),
        "demo": True  # 标记为演示token
    }
    
    # 使用固定的secret (在实际应用中应该使用环境变量)
    JWT_SECRET = getattr(settings, 'jwt_secret', 'demo-secret-key-for-testing-only')
    JWT_ALGORITHM = "HS256"
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_demo_user_info() -> dict:
    """获取演示用户信息"""
    return DEMO_USER.copy()

if __name__ == "__main__":
    # 生成演示token
    token = generate_demo_jwt_token(expire_hours=168)  # 7天有效期
    print("Demo JWT Token:")
    print(token)
    print(f"\n用户信息: {DEMO_USER}")
    print(f"Token长度: {len(token)} 字符")
    print(f"有效期: 7天")