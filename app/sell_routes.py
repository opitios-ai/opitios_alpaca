"""
Sell Module API Routes
Provides control and monitoring interfaces for the sell background service
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime
from loguru import logger

from app.middleware import verify_jwt_token, internal_or_jwt_auth
from app.sell_background_service import (
    get_sell_background_service,
    get_sell_service_status,
    restart_sell_service,
    start_sell_service,
    stop_sell_service
)

# Create router
sell_router = APIRouter(prefix="/sell", tags=["sell_module"])


@sell_router.get("/status", dependencies=[Depends(internal_or_jwt_auth)])
async def get_sell_status() -> Dict[str, Any]:
    """
    Get sell background service status
    """
    try:
        status = await get_sell_service_status()
        
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get sell service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.post("/start", dependencies=[Depends(internal_or_jwt_auth)])
async def start_sell_monitoring() -> Dict[str, Any]:
    """
    Start sell background service
    Requires admin privileges
    """
    try:
        result = await start_sell_service()
        
        if result:
            return {
                "status": "success", 
                "message": "Sell background service started successfully"
            }
        else:
            return {
                "status": "warning",
                "message": "Sell background service was not started (disabled or already running)"
            }
        
    except Exception as e:
        logger.error(f"Failed to start sell service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.post("/stop", dependencies=[Depends(internal_or_jwt_auth)])
async def stop_sell_monitoring() -> Dict[str, Any]:
    """
    Stop sell background service
    Requires admin privileges
    """
    try:
        result = await stop_sell_service()
        
        return {
            "status": "success",
            "message": "Sell background service stopped successfully",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Failed to stop sell service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.post("/restart", dependencies=[Depends(internal_or_jwt_auth)])
async def restart_sell_monitoring() -> Dict[str, Any]:
    """
    Restart sell background service
    Requires admin privileges
    """
    try:
        result = await restart_sell_service()
        
        if result:
            return {
                "status": "success",
                "message": "Sell background service restarted successfully"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to restart sell background service"
            }
        
    except Exception as e:
        logger.error(f"Failed to restart sell service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.get("/config", dependencies=[Depends(internal_or_jwt_auth)])
async def get_sell_config() -> Dict[str, Any]:
    """
    Get sell module configuration
    """
    try:
        from config import settings
        sell_config = settings.sell_module
        
        return {
            "status": "success",
            "data": {
                "enabled": sell_config.get('enabled', False),
                "check_interval": sell_config.get('check_interval', 30),
                "order_cancel_minutes": sell_config.get('order_cancel_minutes', 3),
                "zero_day_handling": sell_config.get('zero_day_handling', True),
                "strategy_one": sell_config.get('strategy_one', {
                    "enabled": True,
                    "profit_rate": 1.1,
                    "stop_loss_rate": 0.8
                })
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get sell config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.get("/service-info", dependencies=[Depends(internal_or_jwt_auth)])
async def get_service_info() -> Dict[str, Any]:
    """
    Get detailed sell service information
    """
    try:
        sell_service = get_sell_background_service()
        status = sell_service.get_status()
        
        # Additional service information
        service_info = {
            "service_type": "background_async",
            "integration": "fastapi_lifespan",
            "non_blocking": True,
            "thread_safe": True,
            "status_details": status
        }
        
        return {
            "status": "success",
            "data": service_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get service info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.get("/health", dependencies=[Depends(internal_or_jwt_auth)])
async def get_sell_service_health() -> Dict[str, Any]:
    """
    Health check for sell background service
    """
    try:
        sell_service = get_sell_background_service()
        status = sell_service.get_status()
        
        # Determine health status
        is_healthy = (
            status["enabled"] and 
            status["running"] and 
            status["task_status"] == "running" and
            status["sell_watcher_initialized"] and
            status["account_pool_initialized"]
        )
        
        health_status = "healthy" if is_healthy else "unhealthy"
        
        return {
            "health": health_status,
            "status": "success" if is_healthy else "warning",
            "data": status,
            "checks": {
                "service_enabled": status["enabled"],
                "service_running": status["running"],
                "task_running": status["task_status"] == "running",
                "watcher_initialized": status["sell_watcher_initialized"],
                "account_pool_ready": status["account_pool_initialized"]
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Sell service health check failed: {e}")
        return {
            "health": "unhealthy",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }