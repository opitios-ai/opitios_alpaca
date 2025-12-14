# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from app.routes import router
from app.middleware import (
    AuthenticationMiddleware, RateLimitMiddleware, LoggingMiddleware, is_internal_ip
)
from app.logging_config import logging_config
from app.account_pool import account_pool
from app.market_utils import init_market_checker
from config import settings
from loguru import logger
from contextlib import asynccontextmanager
import uvicorn
import subprocess
import sys
import time
import os

# Configure enhanced logging
logging_config.setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(
        f"Environment: {'Production' if not settings.debug else 'Development'}"
    )
    logger.info(f"Real data only mode: {settings.real_data_only}")
    logger.info(f"Mock data enabled: {settings.enable_mock_data}")
    logger.info(f"Strict error handling: {settings.strict_error_handling}")
    logger.info(f"Multi-account trading mode: {len(settings.accounts)} accounts configured")
    
    # Initialize market time checker
    try:
        market_checker = init_market_checker(settings.market_config)
        market_status = market_checker.get_market_status_info()
        logger.info(f"Market time checker initialized: {market_status['market_hours']}")
        logger.info(f"Current market status: {market_status['status']} - {market_status['message']}")
    except Exception as e:
        logger.error(f"Failed to initialize market checker: {e}")
        raise
    
    # Initialize account connection pool
    try:
        await account_pool.initialize()
        pool_stats = account_pool.get_pool_stats()
        logger.info(
            f"Account pool initialized: {pool_stats['total_accounts']} "
            f"accounts, {pool_stats['total_connections']} connections"
        )
    except Exception as e:
        logger.error(f"Failed to initialize account pool: {e}")
        raise
    
    if not settings.real_data_only or settings.enable_mock_data:
        logger.warning(
            "ALERT: Service is NOT configured for real-data-only mode!"
        )
    else:
        logger.info(
            "✓ Service configured for real-data-only mode - "
            "no mock or calculated data will be returned"
        )
    
    # Initialize and start sell background service
    try:
        from app.sell_background_service import get_sell_background_service
        
        sell_service = get_sell_background_service()
        service_started = await sell_service.start()
        
        if service_started:
            logger.info("✓ Sell background service started successfully")
        else:
            logger.info("Sell background service not started (disabled or failed)")
            
    except Exception as e:
        logger.error(f"Failed to initialize sell background service: {e}")
        # Don't raise - let the main service continue running
    
    # Start WebSocket manager for real-time updates
    try:
        from app.websocket_manager import ws_manager
        import asyncio
        asyncio.create_task(ws_manager.start())
        logger.info("✓ WebSocket manager started - real-time updates enabled")
    except Exception as e:
        logger.warning(f"WebSocket manager failed to start: {e}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")
    
    # Stop WebSocket manager
    try:
        from app.websocket_manager import ws_manager
        await ws_manager.stop()
        logger.info("✓ WebSocket manager stopped")
    except Exception as e:
        logger.error(f"Error stopping WebSocket manager: {e}")
    
    # Shutdown sell background service
    try:
        from app.sell_background_service import get_sell_background_service
        
        sell_service = get_sell_background_service()
        if sell_service.is_running:
            logger.info("Stopping sell background service...")
            await sell_service.stop()
            logger.info("✓ Sell background service stopped")
    except Exception as e:
        logger.error(f"Error stopping sell background service: {e}")
    
    await account_pool.shutdown()

# Create FastAPI application with JWT security scheme
app = FastAPI(
    title=settings.app_name,
    description="Alpaca Trading API Service for stock and options trading",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
    docs_url=None,  # Disable default docs to use custom one
    # Don't apply global security - we'll apply it per endpoint
    # Define security schemes
    openapi_tags=[
        {
            "name": "authentication",
            "description": "User authentication and management"
        },
        {
            "name": "trading", 
            "description": "Stock and options trading operations"
        }
    ]
)

# Add JWT security scheme to OpenAPI schema
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token obtained from /api/v1/auth/login"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request: Request):
    """Custom Swagger UI with opitios_alpaca branding"""
    client_ip = request.client.host if request.client else "unknown"
    is_internal = is_internal_ip(client_ip)
    
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - {'Internal' if is_internal else 'External'}",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    ).body.decode("utf-8")
    
    if is_internal:
        # Internal access - add colored header and WebSocket test link
        header_html = '''
        <style>
        #opitios-alpaca-header { 
            background: linear-gradient(90deg, #4a90a4 0%, #357a8a 100%); 
            color: white; 
            padding: 15px 20px; 
            margin: 0; 
            font-family: Arial, sans-serif;
            border-bottom: 3px solid #2d5f6f;
        }
        .ws-test-link {
            background: #28a745;
            color: white;
            padding: 8px 16px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            margin-left: 15px;
            display: inline-block;
        }
        .ws-test-link:hover {
            background: #218838;
            color: white;
            text-decoration: none;
        }
        </style>
        <div id="opitios-alpaca-header">
            <h3 style="margin: 0; display: inline-block;">🚀 Opitios Alpaca Trading Service - Internal Access</h3>
            <a href="/static/websocket_test.html" target="_blank" class="ws-test-link">📡 WebSocket Testing</a>
        </div>
        '''
    else:
        # External access - gray header
        header_html = '''
        <style>
        #opitios-alpaca-header { 
            background: linear-gradient(90deg, #6c757d 0%, #495057 100%); 
            color: white; 
            padding: 15px 20px; 
            margin: 0; 
            font-family: Arial, sans-serif;
            border-bottom: 3px solid #495057;
        }
        </style>
        <div id="opitios-alpaca-header">
            <h3 style="margin: 0;">🚀 Opitios Alpaca Trading Service - External Access</h3>
        </div>
        '''
    
    html = html.replace("<body>", "<body>" + header_html)
    return HTMLResponse(html)

# Add middleware in order (last added = first executed)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthenticationMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, 'allowed_origins', ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.auth_routes import auth_router, admin_router
from app.websocket_routes import ws_router
from app.health_routes import health_router
from app.sell_routes import sell_router
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1", tags=["trading"])
app.include_router(ws_router, prefix="/api/v1", tags=["websocket"])
app.include_router(sell_router, prefix="/api/v1", tags=["sell_module"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.app_name,
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

@app.get("/health")
async def basic_health_check():
    """Basic health check endpoint - fast response < 100ms"""
    import time
    from datetime import datetime
    start_time = time.time()
    
    # Quick configuration check only
    config_status = {
        "real_data_only": settings.real_data_only,
        "accounts_configured": len(settings.accounts),
        "multi_account_mode": len(settings.accounts) > 1
    }
    
    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    return {
        "status": "healthy", 
        "service": "Opitios Alpaca Trading Service",
        "response_time_ms": round(response_time, 2),
        "configuration": config_status,
        "timestamp": datetime.now().isoformat()
    }

# Event handlers moved to lifespan context manager above

if __name__ == "__main__":
    # Clear port 8090 before starting server
    logger.info(f"Starting {settings.app_name} on port {settings.port}")    
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )