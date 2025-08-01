#!/usr/bin/env python3
"""
调试用户数据和凭据
"""

import sys  
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import aiohttp
from app.user_manager import UserManager, get_user_manager
from app.middleware import user_manager as middleware_user_manager
from loguru import logger

API_BASE_URL = "http://localhost:8080"

async def debug_user_and_credentials():
    """调试用户数据和凭据"""
    print("=" * 60)
    print("调试用户数据和凭据")
    print("=" * 60)
    
    # 登录获取用户信息
    login_data = {
        "username": "middleware_test_user",
        "password": "TestPassword123!"
    }
    
    async with aiohttp.ClientSession() as session:
        # 登录
        async with session.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                login_result = await response.json()
                user_id = login_result.get("user", {}).get("id")
                print(f"[INFO] 登录成功，用户ID: {user_id}")
            else:
                print(f"[FAIL] 登录失败")
                return False
    
    # 直接从数据库获取用户信息
    print(f"\n[STEP 1] 从数据库获取用户信息...")
    try:
        user_mgr = UserManager()
        
        # 查询用户
        from app.user_manager import User
        user = user_mgr.db.query(User).filter_by(id=user_id).first()
        
        if not user:
            print(f"[FAIL] 数据库中未找到用户: {user_id}")
            return False
        
        print(f"[SUCCESS] 找到用户: {user.username}")
        print(f"[INFO] 邮箱: {user.email}")
        print(f"[INFO] 角色: {user.role}")
        print(f"[INFO] 状态: {user.status}")
        print(f"[INFO] 权限: {user.permissions}")
        print(f"[INFO] 速率限制: {user.rate_limits}")
        print(f"[INFO] Paper Trading: {user.alpaca_paper_trading}")
        
        # 检查加密凭据
        print(f"\n[STEP 2] 检查Alpaca凭据...")
        if user.alpaca_api_key_encrypted and user.alpaca_secret_key_encrypted:
            print(f"[SUCCESS] 找到加密的Alpaca凭据")
            print(f"[INFO] API Key (加密): {user.alpaca_api_key_encrypted[:50]}...")
            print(f"[INFO] Secret Key (加密): {user.alpaca_secret_key_encrypted[:50]}...")
            
            # 尝试解密（仅用于测试）
            try:
                api_key, secret_key = user.decrypt_alpaca_credentials()
                print(f"[SUCCESS] 凭据解密成功")
                print(f"[INFO] API Key (解密): {api_key}")
                print(f"[INFO] Secret Key (解密): {secret_key}")
            except Exception as decrypt_error:
                print(f"[WARNING] 凭据解密失败: {decrypt_error}")
                
        else:
            print(f"[FAIL] 未找到Alpaca凭据")
            return False
        
        # 测试手动创建上下文
        print(f"\n[STEP 3] 手动创建用户上下文...")
        
        context_data = {
            "user_id": user.id,
            "alpaca_credentials": {
                "api_key": user.alpaca_api_key_encrypted,
                "secret_key": user.alpaca_secret_key_encrypted,
                "paper_trading": user.alpaca_paper_trading
            },
            "permissions": list(user.permissions.keys()) if user.permissions else [],
            "rate_limits": user.rate_limits
        }
        
        print(f"[INFO] 上下文数据准备完成")
        print(f"[INFO] 用户ID: {context_data['user_id']}")
        print(f"[INFO] 权限: {context_data['permissions']}")
        print(f"[INFO] 中间件实例ID: {id(middleware_user_manager)}")
        
        # 创建上下文
        context = middleware_user_manager.create_user_context(context_data)
        print(f"[SUCCESS] 上下文创建成功: {context.user_id}")
        
        # 验证上下文
        retrieved_context = middleware_user_manager.get_user_context(user.id)
        if retrieved_context:
            print(f"[SUCCESS] 上下文验证成功")
            return True
        else:
            print(f"[FAIL] 上下文验证失败")
            return False
            
    except Exception as e:
        print(f"[ERROR] 调试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    success = await debug_user_and_credentials()
    
    print("\n" + "=" * 60)
    if success:
        print("[SUCCESS] 用户数据和凭据调试成功!")
        print("\n[结论] 如果手动创建上下文成功，但登录时不成功，说明:")
        print("1. 用户数据和凭据没有问题")
        print("2. 问题在于登录路由中的上下文创建代码执行")
        print("3. 可能是服务器未重新加载代码更改")
    else:
        print("[FAIL] 用户数据或凭据存在问题")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)