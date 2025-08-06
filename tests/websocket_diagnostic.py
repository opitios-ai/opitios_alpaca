#!/usr/bin/env python3
"""
Alpaca WebSocket 诊断工具
用于测试和诊断WebSocket连接问题
"""

import asyncio
import websockets
import json
import ssl
import time
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
import yaml

# 加载配置
def load_config():
    with open('secrets.yml', 'r') as f:
        config = yaml.safe_load(f)
    return config

# Alpaca WebSocket端点
ENDPOINTS = {
    'test': 'wss://stream.data.alpaca.markets/v2/test',
    'stock_iex': 'wss://stream.data.alpaca.markets/v2/iex',
    'stock_sip': 'wss://stream.data.alpaca.markets/v2/sip',
    'option': 'wss://stream.data.alpaca.markets/v1beta1/indicative',
    'trading': 'wss://paper-api.alpaca.markets/stream'
}

class WebSocketDiagnostic:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.results = {}
        
    async def test_api_permissions(self):
        """测试API密钥权限"""
        print("🔑 测试API密钥权限...")
        
        try:
            # 测试交易API
            trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=True
            )
            account = trading_client.get_account()
            print(f"✅ 交易API权限正常 - 账户: {account.account_number}")
            self.results['trading_api'] = True
            
            # 测试市场数据API
            try:
                data_client = StockHistoricalDataClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
                # 尝试获取简单的股票数据
                from alpaca.data.requests import StockLatestQuoteRequest
                request = StockLatestQuoteRequest(symbol_or_symbols="AAPL")
                quotes = data_client.get_stock_latest_quote(request)
                print(f"✅ 市场数据API权限正常 - AAPL报价可用")
                self.results['market_data_api'] = True
            except Exception as e:
                print(f"❌ 市场数据API权限问题: {e}")
                self.results['market_data_api'] = False
                
        except Exception as e:
            print(f"❌ 交易API权限问题: {e}")
            self.results['trading_api'] = False
            return False
            
        return True
    
    async def test_websocket_endpoint(self, endpoint_name, endpoint_url, test_symbol="FAKEPACA"):
        """测试特定WebSocket端点"""
        print(f"\n🌐 测试WebSocket端点: {endpoint_name}")
        print(f"URL: {endpoint_url}")
        
        try:
            ssl_context = ssl.create_default_context()
            
            # 连接WebSocket
            print("正在连接...")
            ws = await websockets.connect(
                endpoint_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            print("✅ WebSocket连接成功")
            
            # 等待欢迎消息
            try:
                welcome_msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                welcome_data = json.loads(welcome_msg)
                print(f"📨 欢迎消息: {welcome_data}")
                
                if isinstance(welcome_data, list) and len(welcome_data) > 0:
                    if welcome_data[0].get("T") == "success":
                        print("✅ 连接确认成功")
                    else:
                        print(f"⚠️ 意外的欢迎消息: {welcome_data}")
                        
            except asyncio.TimeoutError:
                print("⚠️ 未收到欢迎消息（可能正常）")
            
            # 尝试认证
            print("正在认证...")
            auth_message = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.secret_key
            }
            await ws.send(json.dumps(auth_message))
            
            # 等待认证响应
            try:
                auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                auth_data = json.loads(auth_response)
                print(f"🔐 认证响应: {auth_data}")
                
                if isinstance(auth_data, list):
                    auth_result = auth_data[0] if auth_data else {}
                else:
                    auth_result = auth_data
                
                if auth_result.get("T") == "success":
                    print("✅ 认证成功!")
                    
                    # 尝试订阅测试
                    if endpoint_name == "test":
                        await self.test_subscription(ws, test_symbol)
                    elif "stock" in endpoint_name:
                        await self.test_subscription(ws, "AAPL", channel_type="stock")
                    
                    self.results[endpoint_name] = "success"
                    
                elif auth_result.get("T") == "error":
                    error_code = auth_result.get("code")
                    error_msg = auth_result.get("msg", "Unknown error")
                    print(f"❌ 认证失败: [{error_code}] {error_msg}")
                    self.results[endpoint_name] = f"auth_failed_{error_code}"
                    
                    # 解释常见错误
                    self.explain_error(error_code, error_msg)
                    
                else:
                    print(f"❌ 意外的认证响应: {auth_result}")
                    self.results[endpoint_name] = "unexpected_auth_response"
                    
            except asyncio.TimeoutError:
                print("❌ 认证超时")
                self.results[endpoint_name] = "auth_timeout"
            
            await ws.close()
            
        except websockets.exceptions.InvalidStatusCode as e:
            print(f"❌ WebSocket连接被拒绝: HTTP {e.status_code}")
            self.results[endpoint_name] = f"connection_rejected_{e.status_code}"
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")
            self.results[endpoint_name] = f"connection_failed: {str(e)}"
    
    async def test_subscription(self, ws, symbol, channel_type="test"):
        """测试订阅功能"""
        print(f"📡 测试订阅: {symbol}")
        
        try:
            if channel_type == "test":
                subscribe_msg = {
                    "action": "subscribe",
                    "trades": [symbol],
                    "quotes": [symbol]
                }
            else:
                subscribe_msg = {
                    "action": "subscribe",
                    "quotes": [symbol]
                }
            
            await ws.send(json.dumps(subscribe_msg))
            
            # 等待订阅确认
            sub_response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            sub_data = json.loads(sub_response)
            print(f"📋 订阅响应: {sub_data}")
            
            # 等待一些数据
            print("等待数据...")
            for i in range(3):
                try:
                    data_msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(data_msg)
                    print(f"📊 收到数据 {i+1}: {data}")
                except asyncio.TimeoutError:
                    print(f"⏰ 数据接收超时 {i+1}/3")
                    break
                    
        except Exception as e:
            print(f"❌ 订阅测试失败: {e}")
    
    def explain_error(self, error_code, error_msg):
        """解释常见错误代码"""
        explanations = {
            401: "🔑 API密钥无效或未认证",
            402: "🚫 认证失败 - 检查API密钥和密钥",
            406: "🔗 连接数量超限 - 关闭其他WebSocket连接",
            409: "💰 订阅不足 - 您的账户可能没有市场数据WebSocket权限",
            413: "📊 符号数量超限 - 减少订阅的股票数量"
        }
        
        if error_code in explanations:
            print(f"💡 解决方案: {explanations[error_code]}")
        
        if error_code == 409:
            print("📋 市场数据WebSocket需要额外的订阅:")
            print("   - 访问 https://alpaca.markets/data")
            print("   - 升级到包含实时数据的计划")
            print("   - 或使用免费的延迟数据")
    
    async def run_full_diagnostic(self):
        """运行完整诊断"""
        print("🚀 开始Alpaca WebSocket完整诊断")
        print("=" * 50)
        
        # 1. 测试API权限
        api_ok = await self.test_api_permissions()
        if not api_ok:
            print("❌ API权限测试失败，无法继续WebSocket测试")
            return
        
        # 2. 测试各个WebSocket端点
        print("\n" + "=" * 50)
        print("🌐 开始WebSocket端点测试")
        
        # 首先测试测试端点
        await self.test_websocket_endpoint("test", ENDPOINTS['test'], "FAKEPACA")
        
        # 测试股票数据端点
        await self.test_websocket_endpoint("stock_iex", ENDPOINTS['stock_iex'], "AAPL")
        await self.test_websocket_endpoint("stock_sip", ENDPOINTS['stock_sip'], "AAPL")
        
        # 测试期权端点
        await self.test_websocket_endpoint("option", ENDPOINTS['option'], "AAPL250117C00150000")
        
        # 测试交易更新端点
        await self.test_websocket_endpoint("trading", ENDPOINTS['trading'])
        
        # 3. 生成诊断报告
        self.generate_report()
    
    def generate_report(self):
        """生成诊断报告"""
        print("\n" + "=" * 50)
        print("📋 诊断报告")
        print("=" * 50)
        
        print(f"🔑 交易API权限: {'✅ 正常' if self.results.get('trading_api') else '❌ 异常'}")
        print(f"📊 市场数据API权限: {'✅ 正常' if self.results.get('market_data_api') else '❌ 异常'}")
        
        print("\n🌐 WebSocket端点测试结果:")
        for endpoint, result in self.results.items():
            if endpoint not in ['trading_api', 'market_data_api']:
                status = "✅ 成功" if result == "success" else f"❌ {result}"
                print(f"   {endpoint}: {status}")
        
        # 提供建议
        print("\n💡 建议:")
        
        if not self.results.get('market_data_api'):
            print("   1. 您的API密钥可能没有市场数据权限")
            print("   2. 考虑升级到包含市场数据的Alpaca计划")
            print("   3. 或使用交易WebSocket获取订单更新")
        
        if self.results.get('test') == "success":
            print("   1. ✅ 测试端点工作正常，基本WebSocket功能可用")
        
        working_endpoints = [k for k, v in self.results.items() if v == "success"]
        if working_endpoints:
            print(f"   2. ✅ 可用的端点: {', '.join(working_endpoints)}")
        
        failed_endpoints = [k for k, v in self.results.items() if "auth_failed_409" in str(v)]
        if failed_endpoints:
            print("   3. ⚠️ 需要市场数据订阅的端点:", ', '.join(failed_endpoints))
            print("      解决方案: 访问 https://alpaca.markets/data 升级订阅")

async def main():
    """主函数"""
    try:
        config = load_config()
        
        # 获取第一个启用的账户
        accounts = config.get('accounts', {})
        enabled_account = None
        
        for account_id, account_config in accounts.items():
            if account_config.get('enabled', False):
                enabled_account = account_config
                print(f"使用账户: {account_id} ({account_config.get('name', 'Unknown')})")
                break
        
        if not enabled_account:
            # 回退到传统配置
            alpaca_config = config.get('alpaca', {})
            if alpaca_config.get('api_key') and alpaca_config.get('secret_key'):
                enabled_account = alpaca_config
                print("使用传统配置")
            else:
                print("❌ 未找到启用的账户配置")
                return
        
        # 运行诊断
        diagnostic = WebSocketDiagnostic(
            enabled_account['api_key'],
            enabled_account['secret_key']
        )
        
        await diagnostic.run_full_diagnostic()
        
    except Exception as e:
        print(f"❌ 诊断过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())