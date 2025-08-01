#!/usr/bin/env python3
"""
检查中间件和上下文管理器状态
"""

import requests
import json

API_BASE_URL = "http://localhost:8080"

def test_middleware_state():
    """测试中间件状态"""
    print("=" * 60)
    print("检查中间件状态")
    print("=" * 60)
    
    # 先创建并登录一个用户
    test_user = {
        "username": f"middleware_test_user",
        "email": f"middleware_test@example.com", 
        "password": "TestPassword123!",
        "alpaca_api_key": "test_api_key_12345",
        "alpaca_secret_key": "test_secret_key_67890"
    }
    
    try:
        # 注册
        print("[STEP 1] 注册用户...")
        reg_response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/register",
            json=test_user,
            headers={"Content-Type": "application/json"}
        )
        
        if reg_response.status_code == 200:
            user_data = reg_response.json()
            print(f"[SUCCESS] 用户注册成功: {user_data.get('id')}")
        else:
            print(f"[INFO] 注册响应: {reg_response.status_code} (可能用户已存在)")
        
        # 登录
        print("[STEP 2] 用户登录...")
        login_data = {
            "username": test_user["username"],
            "password": test_user["password"]
        }
        
        login_response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if login_response.status_code == 200:
            login_result = login_response.json()
            access_token = login_result.get("access_token")
            user_id = login_result.get("user", {}).get("id")
            print(f"[SUCCESS] 登录成功, 用户ID: {user_id}")
            print(f"[INFO] Token (前30字符): {access_token[:30]}...")
            
            # 测试受保护端点
            print("[STEP 3] 测试受保护端点...")
            me_response = requests.get(
                f"{API_BASE_URL}/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            print(f"[DEBUG] /auth/me 响应状态: {me_response.status_code}")
            print(f"[DEBUG] /auth/me 响应内容: {me_response.text}")
            
            if me_response.status_code == 200:
                print("[SUCCESS] 认证系统工作正常!")
                return True
            else:
                print("[FAIL] 用户上下文未找到")
                
                # 让我们检查是否可以直接访问中间件状态
                print("[STEP 4] 尝试检查服务器内部状态...")
                
                # 这个请求可能会失败，但能帮助我们了解服务器状态
                try:
                    health_response = requests.get(f"{API_BASE_URL}/api/v1/health")
                    print(f"[INFO] 健康检查: {health_response.status_code}")
                    if health_response.status_code == 200:
                        health_data = health_response.json()
                        print(f"[INFO] 服务状态: {health_data}")
                except Exception as e:
                    print(f"[INFO] 健康检查异常: {e}")
                
                return False
        else:
            print(f"[FAIL] 登录失败: {login_response.status_code} - {login_response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_middleware_state()
    print("\n" + "=" * 60)
    
    if not success:
        print("[分析] 可能的问题:")
        print("1. 用户上下文在登录时未正确创建")
        print("2. 中间件使用了不同的UserContextManager实例") 
        print("3. 服务重启后上下文丢失")
        print("4. 导入顺序或模块实例化问题")
        
        print("\n[建议] 检查服务器日志以确认:")
        print("- 是否有'用户上下文创建'日志消息")
        print("- 登录过程中是否有异常")
        print("- 中间件是否正确解析JWT token")
    
    exit(0 if success else 1)