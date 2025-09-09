"""
Sell Module API Routes - Consolidated API
Provides streamlined control and monitoring for the sell background service

🔥 SIMPLIFIED API - Only 2 Endpoints:
1. GET /api/v1/sell - Comprehensive status, config, health & service info
2. POST /api/v1/sell/control - Unified control (start/stop/restart)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime
from loguru import logger
from pydantic import BaseModel

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


class SellControlRequest(BaseModel):
    """
    Control request for sell service operations
    
    Actions:
    - "start": Start the sell background service
    - "stop": Stop the sell background service  
    - "restart": Restart the sell background service
    """
    action: str  # "start" | "stop" | "restart"


@sell_router.get("", dependencies=[Depends(internal_or_jwt_auth)])
async def get_sell_comprehensive_status() -> Dict[str, Any]:
    """
    🎯 CONSOLIDATED ENDPOINT - Get comprehensive sell service information
    
    Combines: status + config + health + service-info in one call
    
    Returns:
    - service: Service status, name, uptime, enabled state
    - health: Health status with detailed checks
    - config: Current configuration settings
    - statistics: Service performance metrics
    
    Example Usage:
    ```
    GET /api/v1/sell
    
    Response:
    {
      "service": {"status": "running", "enabled": true, "uptime": "2h 15m"},
      "health": {"status": "healthy", "checks": {...}},
      "config": {"enabled": true, "check_interval": 60},
      "statistics": {"orders_processed": 150, "success_rate": 0.98}
    }
    ```
    """
    try:
        # Get service status
        status = await get_sell_service_status()
        sell_service = get_sell_background_service()
        
        # Get configuration
        from config import settings
        sell_config = settings.sell_module
        
        # Determine health status
        is_healthy = (
            status.get("enabled", False) and 
            status.get("running", False) and 
            status.get("task_status") == "running" and
            status.get("sell_watcher_initialized", False) and
            status.get("account_pool_initialized", False)
        )
        
        # Calculate uptime if available
        uptime_str = "Unknown"
        if status.get("started_at"):
            try:
                started = datetime.fromisoformat(status["started_at"].replace("Z", "+00:00"))
                uptime_delta = datetime.now() - started.replace(tzinfo=None)
                hours = int(uptime_delta.total_seconds() // 3600)
                minutes = int((uptime_delta.total_seconds() % 3600) // 60)
                uptime_str = f"{hours}h {minutes}m"
            except:
                uptime_str = "Unknown"
        
        return {
            "service": {
                "name": "sell_background_service",
                "status": "running" if status.get("running") else "stopped",
                "enabled": status.get("enabled", False),
                "uptime": uptime_str,
                "task_status": status.get("task_status", "unknown"),
                "integration": "fastapi_lifespan",
                "non_blocking": True
            },
            "health": {
                "status": "healthy" if is_healthy else "unhealthy",
                "last_check": datetime.now().isoformat(),
                "checks": {
                    "service_enabled": status.get("enabled", False),
                    "service_running": status.get("running", False),
                    "task_running": status.get("task_status") == "running",
                    "watcher_initialized": status.get("sell_watcher_initialized", False),
                    "account_pool_ready": status.get("account_pool_initialized", False)
                },
                "errors": status.get("errors", [])
            },
            "config": {
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
            "statistics": {
                "orders_processed": status.get("orders_processed", 0),
                "success_rate": status.get("success_rate", 0.0),
                "last_activity": status.get("last_activity", None)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get comprehensive sell service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@sell_router.post("/control", dependencies=[Depends(internal_or_jwt_auth)])
async def control_sell_service(request: SellControlRequest) -> Dict[str, Any]:
    """
    🎯 UNIFIED CONTROL ENDPOINT - Control sell service operations
    
    Combines: start + stop + restart in one endpoint with action parameter
    
    Actions:
    - "start": Start the sell background service
    - "stop": Stop the sell background service
    - "restart": Restart the sell background service (stop + start)
    
    Example Usage:
    ```
    POST /api/v1/sell/control
    Content-Type: application/json
    
    {"action": "start"}     # Start service
    {"action": "stop"}      # Stop service  
    {"action": "restart"}   # Restart service
    
    Response:
    {
      "success": true,
      "action": "start",
      "message": "Sell service started successfully",
      "new_status": "running"
    }
    ```
    
    Requires admin privileges for all operations.
    """
    try:
        action = request.action.lower()
        
        if action not in ["start", "stop", "restart"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid action '{action}'. Must be: start, stop, or restart"
            )
        
        # Execute the requested action
        if action == "start":
            result = await start_sell_service()
            if result:
                message = "Sell service started successfully"
                new_status = "running"
                success = True
            else:
                message = "Sell service was not started (disabled or already running)"
                new_status = "unchanged"
                success = False
                
        elif action == "stop":
            result = await stop_sell_service()
            message = "Sell service stopped successfully"
            new_status = "stopped"
            success = True
            
        elif action == "restart":
            result = await restart_sell_service()
            if result:
                message = "Sell service restarted successfully"
                new_status = "running"
                success = True
            else:
                message = "Failed to restart sell service"
                new_status = "error"
                success = False
        
        return {
            "success": success,
            "action": action,
            "message": message,
            "new_status": new_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute sell service action '{request.action}': {e}")
        raise HTTPException(status_code=500, detail=str(e))