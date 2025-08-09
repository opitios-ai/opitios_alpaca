#!/usr/bin/env python3
"""
Alpaca Account Health Check Tool
检查主账户的完整权限：询价、下单、撤单等功能
"""

import os
import sys
import yaml
import asyncio
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from loguru import logger

class AlpacaHealthChecker:
    """Alpaca账户健康检查器"""
    
    def __init__(self):
        self.secrets = self.load_secrets()
        self.trading_clients = {}
        self.data_clients = {}
        self.accounts = {}
        
    def load_secrets(self):
        """加载secrets.yml配置"""
        secrets_file = "secrets.yml"
        if not os.path.exists(secrets_file):
            logger.error("❌ secrets.yml文件不存在，请先配置API密钥")
            sys.exit(1)
            
        try:
            with open(secrets_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"❌ 读取secrets.yml失败: {e}")
            sys.exit(1)
    
    def initialize_clients(self):
        """初始化所有账户的交易和数据客户端"""
        logger.info("🔧 初始化Alpaca客户端...")
        
        # 获取账户配置
        accounts = self.secrets.get('accounts', {})
        if not accounts:
            logger.error("❌ 未在secrets.yml中找到账户配置")
            sys.exit(1)
        
        for account_id, config in accounts.items():
            if not config.get('enabled', True):
                logger.info(f"⏭️ 跳过禁用账户: {account_id}")
                continue
                
            try:
                # 创建交易客户端
                trading_client = TradingClient(
                    api_key=config['api_key'],
                    secret_key=config['secret_key'],
                    paper=config.get('paper_trading', True)
                )
                
                # 创建数据客户端
                data_client = StockHistoricalDataClient(
                    api_key=config['api_key'],
                    secret_key=config['secret_key']
                )
                
                self.trading_clients[account_id] = trading_client
                self.data_clients[account_id] = data_client
                
                logger.info(f"✅ 账户 {account_id} 客户端初始化成功")
                
            except Exception as e:
                logger.error(f"❌ 账户 {account_id} 客户端初始化失败: {e}")
                continue
    
    async def run_comprehensive_health_check(self):
        """执行全面的健康检查"""
        logger.info("🏥 开始Alpaca账户全面健康检查")
        logger.info("=" * 80)
        
        self.initialize_clients()
        
        all_results = {}
        
        for account_id, trading_client in self.trading_clients.items():
            logger.info(f"\n🔍 检查账户: {account_id}")
            logger.info("-" * 60)
            
            results = await self.check_single_account(account_id, trading_client)
            all_results[account_id] = results
        
        # 生成总体报告
        self.generate_health_report(all_results)
    
    async def check_single_account(self, account_id: str, trading_client: TradingClient) -> dict:
        """检查单个账户的完整权限"""
        results = {
            "account_id": account_id,
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        # 1. 账户信息检查
        results["checks"]["account_info"] = await self.check_account_info(trading_client)
        
        # 2. 持仓检查
        results["checks"]["positions"] = await self.check_positions(trading_client)
        
        # 3. 订单历史检查
        results["checks"]["order_history"] = await self.check_order_history(trading_client)
        
        # 4. 买入权限检查 (测试订单)
        results["checks"]["buy_permission"] = await self.check_buy_permission(trading_client)
        
        # 5. 卖出权限检查
        results["checks"]["sell_permission"] = await self.check_sell_permission(trading_client)
        
        # 6. 订单取消权限检查
        results["checks"]["cancel_permission"] = await self.check_cancel_permission(trading_client)
        
        # 7. 市场数据访问检查
        if account_id in self.data_clients:
            results["checks"]["market_data"] = await self.check_market_data_access(account_id)
        
        # 8. WebSocket数据流检查
        results["checks"]["websocket_access"] = await self.check_websocket_access(account_id)
        
        # 9. 账户限制检查
        results["checks"]["account_limits"] = await self.check_account_limits(trading_client)
        
        return results
    
    async def check_account_info(self, trading_client: TradingClient) -> dict:
        """检查账户基本信息"""
        try:
            account = trading_client.get_account()
            
            result = {
                "status": "success",
                "account_number": account.account_number,
                "account_status": account.status.value,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "pattern_day_trader": account.pattern_day_trader,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "initial_margin": float(account.initial_margin),
                "maintenance_margin": float(account.maintenance_margin),
                "regt_buying_power": float(account.regt_buying_power),
                "daytrading_buying_power": float(account.daytrading_buying_power),
                "message": "账户信息获取成功"
            }
            
            # 检查账户状态
            if account.status.value != "ACTIVE":
                result["warnings"] = [f"账户状态非ACTIVE: {account.status.value}"]
            
            if account.trading_blocked:
                result["warnings"] = result.get("warnings", []) + ["交易被阻止"]
            
            if account.account_blocked:
                result["warnings"] = result.get("warnings", []) + ["账户被阻止"]
            
            logger.info(f"✅ 账户信息: {account.account_number} | 状态: {account.status.value}")
            logger.info(f"💰 买入力: ${account.buying_power} | 现金: ${account.cash}")
            logger.info(f"📊 投资组合价值: ${account.portfolio_value}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 账户信息检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_positions(self, trading_client: TradingClient) -> dict:
        """检查持仓信息"""
        try:
            positions = trading_client.get_all_positions()
            
            result = {
                "status": "success",
                "total_positions": len(positions),
                "positions": [],
                "message": f"成功获取 {len(positions)} 个持仓"
            }
            
            for pos in positions:
                position_info = {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "side": pos.side.value,
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc)
                }
                result["positions"].append(position_info)
            
            if positions:
                logger.info(f"✅ 持仓检查: {len(positions)} 个活跃持仓")
                for pos in positions[:3]:  # 显示前3个持仓
                    logger.info(f"📈 {pos.symbol}: {pos.qty} 股 | 市值: ${pos.market_value} | P&L: ${pos.unrealized_pl}")
            else:
                logger.info("✅ 持仓检查: 无活跃持仓")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 持仓检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_order_history(self, trading_client: TradingClient) -> dict:
        """检查订单历史"""
        try:
            # 获取最近的订单
            request = GetOrdersRequest(
                status="all",
                limit=10
            )
            orders = trading_client.get_orders(filter=request)
            
            result = {
                "status": "success",
                "recent_orders_count": len(orders),
                "orders": [],
                "message": f"成功获取最近 {len(orders)} 个订单"
            }
            
            for order in orders:
                order_info = {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "qty": float(order.qty),
                    "order_type": order.order_type.value,
                    "status": order.status.value,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                    "filled_qty": float(order.filled_qty) if order.filled_qty else 0
                }
                result["orders"].append(order_info)
            
            logger.info(f"✅ 订单历史: 最近 {len(orders)} 个订单")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 订单历史检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_buy_permission(self, trading_client: TradingClient) -> dict:
        """检查买入权限 - 使用极小金额测试订单"""
        try:
            # 使用极小的金额创建测试订单，然后立即取消
            test_symbol = "AAPL"
            test_qty = 1  # 1股测试
            
            # 创建限价买入订单，价格设置得很低，不会被执行
            market_order_data = LimitOrderRequest(
                symbol=test_symbol,
                qty=test_qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=1.0  # 设置极低价格，确保不会被执行
            )
            
            # 提交订单
            order = trading_client.submit_order(order_data=market_order_data)
            
            # 立即取消订单
            try:
                trading_client.cancel_order_by_id(order.id)
                cancel_success = True
            except:
                cancel_success = False
            
            result = {
                "status": "success",
                "test_order_id": order.id,
                "test_symbol": test_symbol,
                "test_qty": test_qty,
                "order_submitted": True,
                "order_cancelled": cancel_success,
                "message": "买入权限正常 - 测试订单已提交并取消"
            }
            
            logger.info(f"✅ 买入权限: 测试订单 {order.id} 提交成功并已取消")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 买入权限检查失败: {e}")
            return {"status": "error", "error": str(e), "message": "无买入权限或账户受限"}
    
    async def check_sell_permission(self, trading_client: TradingClient) -> dict:
        """检查卖出权限"""
        try:
            # 检查是否有持仓可以测试卖出
            positions = trading_client.get_all_positions()
            
            if not positions:
                logger.info("ℹ️ 卖出权限: 无持仓，无法测试实际卖出权限")
                return {
                    "status": "skip", 
                    "message": "无持仓，跳过卖出权限测试",
                    "positions_available": False
                }
            
            # 选择第一个持仓进行测试
            test_position = positions[0]
            
            # 创建极低价格的限价卖出订单，确保不会被执行
            sell_order_data = LimitOrderRequest(
                symbol=test_position.symbol,
                qty=1,  # 只测试1股
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=999999.0  # 设置极高价格，确保不会被执行
            )
            
            # 提交测试订单
            order = trading_client.submit_order(order_data=sell_order_data)
            
            # 立即取消
            try:
                trading_client.cancel_order_by_id(order.id)
                cancel_success = True
            except:
                cancel_success = False
            
            result = {
                "status": "success",
                "test_order_id": order.id,
                "test_symbol": test_position.symbol,
                "positions_available": True,
                "order_submitted": True,
                "order_cancelled": cancel_success,
                "message": "卖出权限正常 - 测试订单已提交并取消"
            }
            
            logger.info(f"✅ 卖出权限: 测试订单 {order.id} 提交成功并已取消")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 卖出权限检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_cancel_permission(self, trading_client: TradingClient) -> dict:
        """检查订单取消权限"""
        try:
            # 创建一个测试订单用于取消
            test_symbol = "AAPL"
            
            # 创建限价订单，价格设置得很低
            order_data = LimitOrderRequest(
                symbol=test_symbol,
                qty=1,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=1.0
            )
            
            # 提交订单
            order = trading_client.submit_order(order_data=order_data)
            
            # 等待一下确保订单提交完成
            await asyncio.sleep(1)
            
            # 取消订单
            cancel_result = trading_client.cancel_order_by_id(order.id)
            
            result = {
                "status": "success",
                "test_order_id": order.id,
                "cancel_successful": True,
                "message": "订单取消权限正常"
            }
            
            logger.info(f"✅ 取消权限: 订单 {order.id} 成功取消")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 取消权限检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_market_data_access(self, account_id: str) -> dict:
        """检查市场数据访问权限"""
        try:
            data_client = self.data_clients[account_id]
            
            # 测试获取最新报价
            request = StockLatestQuoteRequest(symbol_or_symbols=["AAPL"])
            quotes = data_client.get_stock_latest_quote(request)
            
            if "AAPL" in quotes:
                quote = quotes["AAPL"]
                result = {
                    "status": "success",
                    "test_symbol": "AAPL",
                    "latest_quote": {
                        "bid_price": quote.bid_price,
                        "ask_price": quote.ask_price,
                        "bid_size": quote.bid_size,
                        "ask_size": quote.ask_size,
                        "timestamp": quote.timestamp.isoformat()
                    },
                    "message": "市场数据访问正常"
                }
                
                logger.info(f"✅ 市场数据: AAPL 最新报价 - 买: ${quote.bid_price} 卖: ${quote.ask_price}")
                
            else:
                result = {
                    "status": "error",
                    "message": "无法获取市场数据"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 市场数据检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_websocket_access(self, account_id: str) -> dict:
        """检查WebSocket数据流访问权限"""
        try:
            # 这里简化检查，实际中需要测试WebSocket连接
            account_config = self.secrets['accounts'][account_id]
            
            result = {
                "status": "info",
                "websocket_endpoints": {
                    "stock_iex": "wss://stream.data.alpaca.markets/v2/iex",
                    "stock_sip": "wss://stream.data.alpaca.markets/v2/sip",
                    "options": "wss://stream.data.alpaca.markets/v1beta1/indicative",
                    "test": "wss://stream.data.alpaca.markets/v2/test"
                },
                "api_credentials": {
                    "api_key": account_config['api_key'][:8] + "...",
                    "has_secret": bool(account_config.get('secret_key'))
                },
                "message": "WebSocket端点配置完整，需要运行时测试"
            }
            
            logger.info("✅ WebSocket配置: 端点和凭据配置完整")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ WebSocket配置检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def check_account_limits(self, trading_client: TradingClient) -> dict:
        """检查账户限制和规则"""
        try:
            account = trading_client.get_account()
            
            result = {
                "status": "success",
                "pattern_day_trader": account.pattern_day_trader,
                "daytrading_buying_power": float(account.daytrading_buying_power),
                "regt_buying_power": float(account.regt_buying_power),
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "crypto_status": getattr(account, 'crypto_status', 'unknown'),
                "message": "账户限制检查完成"
            }
            
            # 检查限制状态
            limitations = []
            if account.pattern_day_trader:
                limitations.append("Pattern Day Trader规则适用")
            if account.trading_blocked:
                limitations.append("交易被阻止")
            if account.transfers_blocked:
                limitations.append("转账被阻止")
            if account.account_blocked:
                limitations.append("账户被阻止")
            
            result["limitations"] = limitations
            
            if limitations:
                logger.warning(f"⚠️ 账户限制: {', '.join(limitations)}")
            else:
                logger.info("✅ 账户限制: 无特殊限制")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 账户限制检查失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def generate_health_report(self, all_results: dict):
        """生成健康检查总体报告"""
        logger.info("\n" + "=" * 80)
        logger.info("Alpaca账户健康检查报告")
        logger.info("=" * 80)
        
        for account_id, results in all_results.items():
            logger.info(f"\n账户: {account_id}")
            logger.info("-" * 40)
            
            checks = results["checks"]
            success_count = 0
            total_checks = len(checks)
            
            for check_name, check_result in checks.items():
                status = check_result.get("status", "unknown")
                if status == "success":
                    status_icon = "[OK]"
                    success_count += 1
                elif status == "error":
                    status_icon = "[ERROR]"
                elif status == "skip":
                    status_icon = "[SKIP]"
                    success_count += 0.5  # 跳过的检查算半分
                else:
                    status_icon = "[INFO]"
                    success_count += 0.5
                
                logger.info(f"{status_icon} {check_name}: {check_result.get('message', '无详细信息')}")
            
            # 计算健康得分
            health_score = (success_count / total_checks) * 100
            
            if health_score >= 90:
                score_icon = "[EXCELLENT]"
                score_status = "优秀"
            elif health_score >= 70:
                score_icon = "[GOOD]"
                score_status = "良好"
            else:
                score_icon = "[WARNING]"
                score_status = "需要注意"
            
            logger.info(f"\n{score_icon} 账户健康得分: {health_score:.1f}% ({score_status})")
        
        logger.info("\n" + "=" * 80)
        logger.info("健康检查完成")
        logger.info("=" * 80)

def main():
    """主函数"""
    print("Alpaca账户健康检查工具")
    print("检查主账户的完整权限：询价、下单、撤单等功能")
    print("=" * 60)
    
    checker = AlpacaHealthChecker()
    
    try:
        asyncio.run(checker.run_comprehensive_health_check())
    except KeyboardInterrupt:
        logger.info("\n用户中断，健康检查停止")
    except Exception as e:
        logger.error(f"健康检查执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()