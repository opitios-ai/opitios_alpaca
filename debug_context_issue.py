#!/usr/bin/env python3
"""
调试用户上下文问题
测试JWT token解析和用户上下文查找
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# 服务配置
API_BASE_URL = "http://localhost:8080"

async def debug_authentication_issue():
    """调试认证问题"""
    print("=" * 60)
    print("调试认证上下文问题")
    print("=" * 60)
    
    # 测试数据
    test_user = {
        "username": f"debuguser_{int(datetime.now().timestamp())}",
        "email": f"debug_{int(datetime.now().timestamp())}@example.com", 
        "password": "DebugPassword123!",
        "alpaca_api_key": "debug_api_key_12345",
        "alpaca_secret_key": "debug_secret_key_67890"
    }
    
    print(f"[INFO] 调试用户: {test_user['username']}")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 步骤1: 注册用户
            print(f"\n[STEP 1] 用户注册...")
            async with session.post(
                f"{API_BASE_URL}/api/v1/auth/register",
                json=test_user,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    user_data = await response.json()
                    print(f"[SUCCESS] 用户注册成功: {user_data.get('id')}")
                else:
                    response_text = await response.text()
                    print(f"[FAIL] 注册失败: {response.status} - {response_text}")
                    return False
            
            await asyncio.sleep(1)
            
            # 步骤2: 用户登录 (获取详细响应)
            print(f"\n[STEP 2] 用户登录...")
            login_data = {
                "username": test_user["username"],
                "password": test_user["password"]
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/v1/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    login_result = await response.json()
                    access_token = login_result.get("access_token")
                    
                    print(f"[SUCCESS] 登录成功!")
                    print(f"[DEBUG] 完整登录响应:")
                    print(json.dumps(login_result, indent=2, default=str))
                    
                    if not access_token:
                        print(f"[ERROR] 未获取到access_token")
                        return False
                        
                else:
                    response_text = await response.text()
                    print(f"[FAIL] 登录失败: {response.status} - {response_text}")
                    return False
            
            await asyncio.sleep(1)
            
            # 步骤3: 解析JWT token
            print(f"\n[STEP 3] 解析JWT token...")
            import jwt
            try:
                # 不验证签名，只解析payload
                payload = jwt.decode(access_token, options={"verify_signature": False})
                print(f"[DEBUG] JWT Payload:")
                print(json.dumps(payload, indent=2))
                
                user_id = payload.get("user_id")
                if user_id:
                    print(f"[INFO] JWT中的用户ID: {user_id}")
                else:
                    print(f"[ERROR] JWT中未找到user_id")
                    return False
                    
            except Exception as e:
                print(f"[ERROR] JWT解析失败: {e}")
                return False
            
            # 步骤4: 测试受保护端点 (详细错误信息)
            print(f"\n[STEP 4] 测试受保护端点...")
            async with session.get(
                f"{API_BASE_URL}/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            ) as response:
                response_text = await response.text()
                
                print(f"[DEBUG] 受保护端点响应:")
                print(f"[DEBUG] 状态码: {response.status}")
                print(f"[DEBUG] 响应头: {dict(response.headers)}")
                print(f"[DEBUG] 响应体: {response_text}")
                
                if response.status == 200:
                    print(f"[SUCCESS] 受保护端点访问成功!")
                    return True
                else:
                    print(f"[FAIL] 受保护端点访问失败")
                    return False
                    
        except Exception as e:
            print(f"[ERROR] 调试过程异常: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    """主函数"""
    success = await debug_authentication_issue()
    
    print("\n" + "=" * 60)
    if success:
        print("[SUCCESS] 认证调试成功!")
    else:
        print("[FAIL] 认证调试失败 - 需要进一步检查")
        print("\n[建议检查项目]:")
        print("1. 服务器日志中的用户上下文创建日志")
        print("2. JWT token是否正确生成")
        print("3. 中间件是否正确处理Bearer token")
        print("4. 用户上下文是否在登录后正确创建")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)