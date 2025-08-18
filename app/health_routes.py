"""
健康检查路由 - Web端点版本
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, List, Optional
import asyncio
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from loguru import logger

from config import settings

# 健康检查路由
health_router = APIRouter(prefix="/health", tags=["health"])

# 全局健康检查结果缓存
health_cache = {}
health_check_running = False

class WebHealthChecker:
    """Web版本的健康检查器"""
    
    def __init__(self):
        self.accounts = settings.accounts
    
    async def run_comprehensive_check(self, account_id: Optional[str] = None) -> Dict:
        """执行全面健康检查"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "accounts": {}
        }
        
        accounts_to_check = [account_id] if account_id else list(self.accounts.keys())
        
        for acc_id in accounts_to_check:
            if acc_id not in self.accounts:
                continue
                
            account_config = self.accounts[acc_id]
            if not account_config.get('enabled', True):
                results["accounts"][acc_id] = {
                    "status": "disabled",
                    "message": "账户已禁用"
                }
                continue
            
            try:
                account_result = await self.check_single_account(acc_id, account_config)
                results["accounts"][acc_id] = account_result
            except Exception as e:
                results["accounts"][acc_id] = {
                    "status": "error",
                    "error": str(e),
                    "message": "账户检查失败"
                }
        
        return results
    
    async def check_single_account(self, account_id: str, config: Dict) -> Dict:
        """检查单个账户"""
        result = {
            "account_id": account_id,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "unknown"
        }
        
        try:
            # 初始化客户端
            trading_client = TradingClient(
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                paper=config.get('paper_trading', True)
            )
            
            data_client = StockHistoricalDataClient(
                api_key=config['api_key'],
                secret_key=config['secret_key']
            )
            
            # 执行各项检查
            result["checks"]["account_info"] = await self.check_account_info(trading_client)
            result["checks"]["positions"] = await self.check_positions(trading_client)
            result["checks"]["order_history"] = await self.check_order_history(trading_client)
            result["checks"]["buy_permission"] = await self.check_trading_permission(trading_client, "buy")
            result["checks"]["sell_permission"] = await self.check_trading_permission(trading_client, "sell")
            result["checks"]["cancel_permission"] = await self.check_cancel_permission(trading_client)
            result["checks"]["market_data"] = await self.check_market_data(data_client)
            result["checks"]["websocket_config"] = self.check_websocket_config(config)
            
            # 计算总体状态
            result["overall_status"] = self.calculate_overall_status(result["checks"])
            
        except Exception as e:
            result["checks"]["initialization"] = {
                "status": "error",
                "error": str(e),
                "message": "客户端初始化失败"
            }
            result["overall_status"] = "error"
        
        return result
    
    async def check_account_info(self, trading_client: TradingClient) -> Dict:
        """检查账户基本信息"""
        try:
            account = trading_client.get_account()
            
            warnings = []
            if account.status.value != "ACTIVE":
                warnings.append(f"账户状态: {account.status.value}")
            if account.trading_blocked:
                warnings.append("交易被阻止")
            if account.account_blocked:
                warnings.append("账户被阻止")
            
            return {
                "status": "success",
                "data": {
                    "account_number": account.account_number,
                    "status": account.status.value,
                    "buying_power": float(account.buying_power),
                    "cash": float(account.cash),
                    "portfolio_value": float(account.portfolio_value),
                    "pattern_day_trader": account.pattern_day_trader
                },
                "warnings": warnings,
                "message": "账户信息获取成功"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def check_positions(self, trading_client: TradingClient) -> Dict:
        """检查持仓"""
        try:
            positions = trading_client.get_all_positions()
            
            return {
                "status": "success",
                "data": {
                    "total_positions": len(positions),
                    "positions": [
                        {
                            "symbol": pos.symbol,
                            "qty": float(pos.qty),
                            "side": pos.side.value,
                            "market_value": float(pos.market_value),
                            "unrealized_pl": float(pos.unrealized_pl)
                        }
                        for pos in positions[:5]  # 只返回前5个持仓
                    ]
                },
                "message": f"获取到 {len(positions)} 个持仓"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def check_order_history(self, trading_client: TradingClient) -> Dict:
        """检查订单历史"""
        try:
            from alpaca.trading.requests import GetOrdersRequest
            
            request = GetOrdersRequest(status="all", limit=5)
            orders = trading_client.get_orders(filter=request)
            
            return {
                "status": "success",
                "data": {
                    "recent_orders_count": len(orders),
                    "orders": [
                        {
                            "id": str(order.id),  # 确保ID是字符串类型
                            "symbol": order.symbol,
                            "side": order.side.value,
                            "qty": float(order.qty),
                            "status": order.status.value,
                            "created_at": order.created_at.isoformat() if order.created_at else None
                        }
                        for order in orders
                    ]
                },
                "message": f"获取到最近 {len(orders)} 个订单"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def check_trading_permission(self, trading_client: TradingClient, side: str) -> Dict:
        """检查交易权限"""
        try:
            test_symbol = "AAPL"
            
            if side == "buy":
                # 创建极低价格的限价买入订单
                order_data = LimitOrderRequest(
                    symbol=test_symbol,
                    qty=1,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                    limit_price=1.0  # 极低价格
                )
            else:  # sell
                # 检查是否有持仓
                positions = trading_client.get_all_positions()
                if not positions:
                    return {
                        "status": "skip",
                        "message": "无持仓，跳过卖出测试",
                        "data": {"positions_available": False}
                    }
                
                # 创建极高价格的限价卖出订单
                order_data = LimitOrderRequest(
                    symbol=positions[0].symbol,
                    qty=1,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                    limit_price=999999.0  # 极高价格
                )
            
            # 提交测试订单
            order = trading_client.submit_order(order_data=order_data)
            
            # 立即取消
            cancel_success = False
            try:
                trading_client.cancel_order_by_id(order.id)
                cancel_success = True
            except Exception:
                pass
            
            return {
                "status": "success",
                "data": {
                    "test_order_id": str(order.id),  # 确保ID是字符串类型
                    "order_submitted": True,
                    "order_cancelled": cancel_success
                },
                "message": f"{side}权限正常 - 测试订单已提交并取消"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"{side}权限检查失败"
            }
    
    async def check_cancel_permission(self, trading_client: TradingClient) -> Dict:
        """检查取消权限"""
        try:
            # 创建测试订单
            order_data = LimitOrderRequest(
                symbol="AAPL",
                qty=1,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=1.0
            )
            
            order = trading_client.submit_order(order_data=order_data)
            
            # 等待一下
            await asyncio.sleep(1)
            
            # 取消订单
            trading_client.cancel_order_by_id(order.id)
            
            return {
                "status": "success",
                "data": {"test_order_id": str(order.id)},  # 确保ID是字符串类型
                "message": "订单取消权限正常"
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def check_market_data(self, data_client: StockHistoricalDataClient) -> Dict:
        """检查市场数据访问"""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=["AAPL"])
            quotes = data_client.get_stock_latest_quote(request)
            
            if "AAPL" in quotes:
                quote = quotes["AAPL"]
                return {
                    "status": "success",
                    "data": {
                        "test_symbol": "AAPL",
                        "bid_price": quote.bid_price,
                        "ask_price": quote.ask_price,
                        "timestamp": quote.timestamp.isoformat()
                    },
                    "message": "市场数据访问正常"
                }
            else:
                return {"status": "error", "message": "无法获取市场数据"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def check_websocket_config(self, config: Dict) -> Dict:
        """检查WebSocket配置"""
        try:
            return {
                "status": "success",
                "data": {
                    "websocket_endpoints": {
                        "stock_iex": "wss://stream.data.alpaca.markets/v2/iex",
                        "options": "wss://stream.data.alpaca.markets/v1beta1/indicative",
                        "test": "wss://stream.data.alpaca.markets/v2/test"
                    },
                    "api_key_configured": bool(config.get('api_key')),
                    "secret_key_configured": bool(config.get('secret_key'))
                },
                "message": "WebSocket配置检查完成"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def calculate_overall_status(self, checks: Dict) -> str:
        """计算总体状态"""
        success_count = 0
        total_count = len(checks)
        
        for check_result in checks.values():
            if check_result.get("status") == "success":
                success_count += 1
            elif check_result.get("status") == "skip":
                success_count += 0.5
        
        success_rate = success_count / total_count if total_count > 0 else 0
        
        if success_rate >= 0.9:
            return "excellent"
        elif success_rate >= 0.7:
            return "good"
        elif success_rate >= 0.5:
            return "warning"
        else:
            return "error"

# 初始化检查器
web_checker = WebHealthChecker()

@health_router.get("/")
async def health_overview():
    """简单的健康检查概览 - 无需认证"""
    return {
        "service": "Opitios Alpaca Trading Service",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "components": {
            "websocket": "operational",
            "trading_api": "operational", 
            "market_data": "operational"
        },
        "endpoints": {
            "comprehensive_check": "/api/v1/health/comprehensive",
            "account_check": "/api/v1/health/account/{account_id}",
            "trading_permissions": "/api/v1/health/trading-permissions"
        }
    }

@health_router.get("/comprehensive")
async def comprehensive_health_check():
    """全面健康检查"""
    global health_check_running
    global health_cache
    
    if health_check_running:
        return {
            "status": "running",
            "message": "健康检查正在进行中，请稍后再试"
        }
    
    try:
        health_check_running = True
        results = await web_checker.run_comprehensive_check()
        
        # 缓存结果
        health_cache = results
        
        return {
            "status": "completed",
            "results": results,
            "message": "全面健康检查完成"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "健康检查执行失败"
        }
    finally:
        health_check_running = False

@health_router.get("/account/{account_id}")
async def single_account_check(account_id: str):
    """单个账户健康检查"""
    try:
        results = await web_checker.run_comprehensive_check(account_id)
        
        if account_id not in results["accounts"]:
            raise HTTPException(status_code=404, detail="账户不存在或未配置")
        
        return {
            "status": "completed",
            "account_id": account_id,
            "result": results["accounts"][account_id],
            "message": f"账户 {account_id} 健康检查完成"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": f"账户 {account_id} 检查失败"
        }

@health_router.get("/trading-permissions")
async def trading_permissions_check():
    """专门的交易权限检查"""
    results = {}
    
    for account_id, config in settings.accounts.items():
        if not config.get('enabled', True):
            continue
        
        try:
            trading_client = TradingClient(
                api_key=config['api_key'],
                secret_key=config['secret_key'],
                paper=config.get('paper_trading', True)
            )
            
            # 检查账户状态
            account = trading_client.get_account()
            
            permissions = {
                "account_active": account.status.value == "ACTIVE",
                "trading_allowed": not account.trading_blocked,
                "account_unblocked": not account.account_blocked,
                "transfers_allowed": not account.transfers_blocked,
                "buying_power": float(account.buying_power),
                "pattern_day_trader": account.pattern_day_trader
            }
            
            results[account_id] = {
                "status": "success",
                "permissions": permissions,
                "overall_trading_enabled": all([
                    permissions["account_active"],
                    permissions["trading_allowed"],
                    permissions["account_unblocked"]
                ])
            }
            
        except Exception as e:
            results[account_id] = {
                "status": "error",
                "error": str(e)
            }
    
    return {
        "status": "completed",
        "accounts": results,
        "message": "交易权限检查完成"
    }

@health_router.get("/websocket-status")
async def websocket_status_check():
    """WebSocket状态检查"""
    # 导入WebSocket管理器
    try:
        from app.websocket_routes import ws_manager, active_connections
        
        return {
            "status": "success",
            "websocket_manager": {
                "connected": ws_manager.connected,
                "stock_connected": ws_manager.stock_connected,
                "option_connected": ws_manager.option_connected
            },
            "active_connections": len(active_connections),
            "endpoints": {
                "stock": "wss://stream.data.alpaca.markets/v2/iex",
                "options": "wss://stream.data.alpaca.markets/v1beta1/indicative",
                "test": "wss://stream.data.alpaca.markets/v2/test"
            },
            "message": "WebSocket状态检查完成"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "WebSocket状态检查失败"
        }

@health_router.get("/last-check")
async def get_last_health_check():
    """获取最后一次健康检查结果"""
    if not health_cache:
        return {
            "status": "no_data",
            "message": "尚未执行健康检查，请先调用 /health/comprehensive"
        }
    
    return {
        "status": "success",
        "cached_results": health_cache,
        "message": "返回最后一次健康检查结果"
    }

@health_router.post("/background-check")
async def start_background_health_check(background_tasks: BackgroundTasks):
    """启动后台健康检查"""
    
    async def background_check():
        global health_cache
        global health_check_running
        try:
            health_check_running = True
            results = await web_checker.run_comprehensive_check()
            health_cache = results
            logger.info("✅ 后台健康检查完成")
        except Exception as e:
            logger.error(f"❌ 后台健康检查失败: {e}")
        finally:
            health_check_running = False
    
    background_tasks.add_task(background_check)
    
    return {
        "status": "started",
        "message": "后台健康检查已启动，结果将在完成后通过 /health/last-check 获取"
    }