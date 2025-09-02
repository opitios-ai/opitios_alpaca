"""
Simplified Loguru logging configuration
Basic application log + error log only for production
"""

import sys
import os
from pathlib import Path

from loguru import logger
from config import settings


class LoggingConfig:
    """Simplified logging configuration"""
    
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
    
    def setup_logging(self):
        """Setup basic logging configuration"""
        # Remove default handler
        logger.remove()
        
        # Console logging (development only)
        if getattr(settings, 'debug', False):
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
                level="DEBUG",
                colorize=True
            )
        
        # Main application log
        logger.add(
            self.log_dir / "alpaca_service.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="INFO",
            rotation="100 MB",
            retention="30 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True
        )
        
        # Error log (separate file for errors)
        logger.add(
            self.log_dir / "errors.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="ERROR",
            rotation="50 MB",
            retention="60 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )
        
        logger.info("Logging system initialized")


# Global logging configuration instance
logging_config = LoggingConfig()

# Export for backwards compatibility
__all__ = ["logging_config"]