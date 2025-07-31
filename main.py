from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router
from config import settings
from loguru import logger
import uvicorn

# Configure logging
logger.add("logs/alpaca_service.log", rotation="100 MB", retention="7 days", encoding='utf-8', enqueue=True)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Alpaca Trading API Service for stock and options trading",
    version="1.0.0",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )