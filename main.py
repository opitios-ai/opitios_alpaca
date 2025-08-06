from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from app.routes import router
from app.middleware import AuthenticationMiddleware, RateLimitMiddleware, LoggingMiddleware
from app.logging_config import logging_config
from app.account_pool import account_pool
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

def clear_port_8090():
    """Clear any processes using port 8090"""
    logger.info("Checking for processes using port 8090...")
    
    try:
        if os.name == 'nt':  # Windows
            # Find processes using port 8090
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'TCP'], 
                capture_output=True, text=True, check=False
            )
            
            lines = result.stdout.split('\n')
            pids_to_kill = []
            
            for line in lines:
                if ':8090' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids_to_kill.append(pid)
                            logger.warning(f"Found process PID {pid} using port 8090")
            
            # Kill the processes
            for pid in pids_to_kill:
                try:
                    subprocess.run(['taskkill', '/F', '/PID', pid], check=True)
                    logger.success(f"Killed process PID {pid}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to kill PID {pid}: {e}")
                    
        else:  # Linux/Mac
            try:
                result = subprocess.run(
                    ['lsof', '-ti:8090'], 
                    capture_output=True, text=True, check=False
                )
                
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid.strip():
                            try:
                                subprocess.run(['kill', '-9', pid.strip()], check=True)
                                logger.success(f"Killed process PID {pid.strip()}")
                            except subprocess.CalledProcessError as e:
                                logger.error(f"Failed to kill PID {pid.strip()}: {e}")
                else:
                    logger.info("No processes found using port 8090")
                    
            except FileNotFoundError:
                logger.info("lsof command not found, trying alternative method...")
                try:
                    subprocess.run(['fuser', '-k', '8090/tcp'], check=True)
                    logger.success("Killed processes using port 8090 with fuser")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    logger.warning("Could not kill processes automatically")
        
        # Wait for processes to close
        time.sleep(2)
        logger.info("Port 8090 cleanup completed")
        
    except Exception as e:
        logger.error(f"Error while cleaning port 8090: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {'Production' if not settings.debug else 'Development'}")
    logger.info(f"Paper trading mode: {settings.alpaca_paper_trading}")
    logger.info(f"Alpaca base URL: {settings.alpaca_base_url}")
    logger.info(f"Real data only mode: {settings.real_data_only}")
    logger.info(f"Mock data enabled: {settings.enable_mock_data}")
    logger.info(f"Strict error handling: {settings.strict_error_handling}")
    
    # Initialize account connection pool
    try:
        await account_pool.initialize()
        pool_stats = account_pool.get_pool_stats()
        logger.info(f"Account pool initialized: {pool_stats['total_accounts']} accounts, {pool_stats['total_connections']} connections")
    except Exception as e:
        logger.error(f"Failed to initialize account pool: {e}")
        raise
    
    if not settings.real_data_only or settings.enable_mock_data:
        logger.warning("ALERT: Service is NOT configured for real-data-only mode!")
    else:
        logger.info("✓ Service configured for real-data-only mode - no mock or calculated data will be returned")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")
    await account_pool.shutdown()

# Create FastAPI application with JWT security scheme
app = FastAPI(
    title=settings.app_name,
    description="Alpaca Trading API Service for stock and options trading",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
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
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1", tags=["trading"])
app.include_router(ws_router, prefix="/api/v1", tags=["websocket"])

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

# Event handlers moved to lifespan context manager above

if __name__ == "__main__":
    # Clear port 8090 before starting server
    logger.info(f"Starting {settings.app_name} on port {settings.port}")
    clear_port_8090()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )