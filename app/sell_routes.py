"""
卖出模块API路由
提供卖出模块的控制和监控接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime
from loguru import logger

from app.middleware import jwt_required, RoleRequired
from app.sell_module.sell_watcher import SellWatcher
from app.account_pool import get_account_pool

# 全局卖出监控器实例
_sell_watcher: SellWatcher = None

def get_sell_watcher():
    """获取卖出监控器实例"""
    global _sell_watcher
    if _sell_watcher is None:
        account_pool = get_account_pool()
        _sell_watcher = SellWatcher(account_pool)
    return _sell_watcher

# 创建路由器
sell_router = APIRouter(prefix="/sell", tags=["sell_module"])

@sell_router.get("/status", dependencies=[Depends(jwt_required)])
async def get_sell_status() -> Dict[str, Any]:
    """
    获取卖出模块状态
    """
    try:
        sell_watcher = get_sell_watcher()
        status = sell_watcher.get_status()
        
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取卖出模块状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sell_router.post("/start", dependencies=[Depends(RoleRequired(min_role="admin"))])
async def start_sell_monitoring() -> Dict[str, str]:
    """
    启动卖出监控
    需要管理员权限
    """
    try:
        sell_watcher = get_sell_watcher()
        
        if sell_watcher.is_running:
            return {
                "status": "warning",
                "message": "卖出监控器已经在运行中"
            }
        
        # 在后台启动监控
        import asyncio
        asyncio.create_task(sell_watcher.start_monitoring())
        
        return {
            "status": "success", 
            "message": "卖出监控器已启动"
        }
        
    except Exception as e:
        logger.error(f"启动卖出监控失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sell_router.post("/stop", dependencies=[Depends(RoleRequired(min_role="admin"))])
async def stop_sell_monitoring() -> Dict[str, str]:
    """
    停止卖出监控
    需要管理员权限
    """
    try:
        sell_watcher = get_sell_watcher()
        
        if not sell_watcher.is_running:
            return {
                "status": "warning", 
                "message": "卖出监控器未在运行"
            }
        
        await sell_watcher.stop_monitoring()
        
        return {
            "status": "success",
            "message": "卖出监控器已停止"
        }
        
    except Exception as e:
        logger.error(f"停止卖出监控失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sell_router.post("/run-once", dependencies=[Depends(RoleRequired(min_role="admin"))])
async def run_sell_check_once() -> Dict[str, str]:
    """
    执行一次卖出检查
    需要管理员权限
    """
    try:
        sell_watcher = get_sell_watcher()
        await sell_watcher.run_once()
        
        return {
            "status": "success",
            "message": "卖出检查执行完成"
        }
        
    except Exception as e:
        logger.error(f"执行卖出检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sell_router.get("/config", dependencies=[Depends(jwt_required)])
async def get_sell_config() -> Dict[str, Any]:
    """
    获取卖出模块配置
    """
    try:
        from config import settings
        sell_config = settings.sell_module
        
        return {
            "status": "success",
            "data": {
                "enabled": sell_config.get('enabled', True),
                "check_interval": sell_config.get('check_interval', 5),
                "order_cancel_minutes": sell_config.get('order_cancel_minutes', 3),
                "zero_day_handling": sell_config.get('zero_day_handling', True),
                "strategy_one": sell_config.get('strategy_one', {})
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取卖出配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@sell_router.get("/positions", dependencies=[Depends(jwt_required)])
async def get_monitored_positions() -> Dict[str, Any]:
    """
    获取正在监控的持仓
    """
    try:
        sell_watcher = get_sell_watcher()
        
        # 获取监控的持仓信息
        track_list = getattr(sell_watcher, 'track_list', {})
        
        positions_info = []
        for symbol, data in track_list.items():
            positions_info.append({
                "symbol": symbol,
                "current_price": data.get('current_price', 0),
                "entry_price": data.get('entry_price', 0),
                "quantity": data.get('quantity', 0),
                "unrealized_pnl": data.get('unrealized_pnl', 0),
                "last_updated": data.get('last_updated', 'N/A')
            })
        
        return {
            "status": "success",
            "data": {
                "total_positions": len(positions_info),
                "positions": positions_info
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取监控持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))