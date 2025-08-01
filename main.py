from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.routes import router
from app.middleware import AuthenticationMiddleware, RateLimitMiddleware, LoggingMiddleware
from app.logging_config import logging_config
from app.connection_pool import connection_pool
from config import settings
from loguru import logger
import uvicorn

# Configure enhanced logging
logging_config.setup_logging()

# Create FastAPI application with JWT security scheme
app = FastAPI(
    title=settings.app_name,
    description="Alpaca Trading API Service for stock and options trading",
    version="1.0.0",
    debug=settings.debug,
    # Add JWT security scheme for Swagger UI
    security=[{"BearerAuth": []}],
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
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1", tags=["trading"])

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

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Paper trading mode: {settings.alpaca_paper_trading}")
    logger.info(f"Alpaca base URL: {settings.alpaca_base_url}")
    logger.info(f"Real data only mode: {settings.real_data_only}")
    logger.info(f"Mock data enabled: {settings.enable_mock_data}")
    logger.info(f"Strict error handling: {settings.strict_error_handling}")
    if not settings.real_data_only or settings.enable_mock_data:
        logger.warning("ALERT: Service is NOT configured for real-data-only mode!")
    else:
        logger.info("✓ Service configured for real-data-only mode - no mock or calculated data will be returned")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info(f"Shutting down {settings.app_name}")
    await connection_pool.shutdown()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )