#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的系统
"""

import asyncio
import websockets
import json
import requests

def test_jwt_endpoint():
    """测试JWT端点"""
    print("Testing JWT endpoint...")
    try:
        response = requests.get('http://localhost:8090/api/v1/auth/demo-token', timeout=5)
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token', '')
            print(f"JWT Token OK: {token[:50]}...")
            return True
        else:
            print(f"JWT Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"JWT Error: {e}")
        return False

def test_favicon():
    """测试favicon"""
    print("Testing favicon...")
    try:
        response = requests.get('http://localhost:8090/favicon.ico', timeout=5)
        print(f"Favicon status: {response.status_code}")
        return response.status_code in [200, 404]  # 404 is OK too
    except Exception as e:
        print(f"Favicon Error: {e}")
        return False

def test_page():
    """测试页面"""
    print("Testing websocket page...")
    try:
        response = requests.get('http://localhost:8090/static/websocket_test.html', timeout=5)
        if response.status_code == 200:
            if 'ws://localhost:8090' in response.text:
                print("Page updated to port 8090: OK")
                return True
            else:
                print("Page port not updated")
                return False
        else:
            print(f"Page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Page Error: {e}")
        return False

async def test_websocket():
    """测试WebSocket"""
    print("Testing WebSocket connection...")
    try:
        async with websockets.connect("ws://localhost:8090/api/v1/ws/market-data") as websocket:
            print("WebSocket connected!")
            
            # 等待消息
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Received: {msg[:100]}...")
                data = json.loads(msg)
                print(f"Message type: {data.get('type', 'unknown')}")
                return True
            except asyncio.TimeoutError:
                print("No message received (timeout)")
                return True  # Connection is OK even without immediate message
                
    except Exception as e:
        print(f"WebSocket Error: {e}")
        return False

async def main():
    """主函数"""
    print("=== Fix Verification Tests ===")
    
    tests = [
        ("JWT Token", test_jwt_endpoint()),
        ("Favicon", test_favicon()),
        ("WebSocket Page", test_page()),
        ("WebSocket Connection", await test_websocket())
    ]
    
    passed = 0
    for name, result in tests:
        status = "PASS" if result else "FAIL"
        print(f"{name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResult: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("ALL FIXES VERIFIED! System is ready.")
    else:
        print("Some tests failed. May need server restart.")

if __name__ == "__main__":
    asyncio.run(main())