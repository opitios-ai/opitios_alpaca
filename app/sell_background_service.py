"""
Sell Module Background Service
Non-blocking async background service for sell operations
Integrates with FastAPI application lifecycle
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from loguru import logger

from config import settings
from app.account_pool import AccountPool, get_account_pool
from app.sell_module.sell_watcher import SellWatcher


class SellBackgroundService:
    """Non-blocking background service for sell operations"""
    
    def __init__(self):
        self.sell_watcher: Optional[SellWatcher] = None
        self.account_pool: Optional[AccountPool] = None
        self.background_task: Optional[asyncio.Task] = None
        self.is_enabled = settings.sell_module.get('enabled', False)
        self.is_running = False
    
    async def start(self) -> bool:
        """Start the sell module background service"""
        if not self.is_enabled:
            logger.info("Sell module is disabled in configuration - skipping background service")
            return False
        
        if self.is_running:
            logger.warning("Sell background service is already running")
            return False
        
        try:
            logger.info("Starting sell module background service...")
            
            # Initialize account pool if not already done
            self.account_pool = get_account_pool()
            if not self.account_pool._initialized:
                await self.account_pool.initialize()
            
            # Initialize sell watcher
            self.sell_watcher = SellWatcher(self.account_pool)
            
            # Start background monitoring task
            self.background_task = asyncio.create_task(
                self._background_monitoring(),
                name="sell_module_monitoring"
            )
            
            self.is_running = True
            logger.info("✅ Sell module background service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start sell module background service: {e}")
            await self.stop()
            return False
    
    async def stop(self):
        """Stop the sell module background service"""
        if not self.is_running:
            return
        
        logger.info("Stopping sell module background service...")
        
        self.is_running = False
        
        # Stop sell watcher
        if self.sell_watcher:
            try:
                await self.sell_watcher.stop_monitoring()
            except Exception as e:
                logger.error(f"Error stopping sell watcher: {e}")
        
        # Cancel background task
        if self.background_task and not self.background_task.done():
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                logger.debug("Sell module background task cancelled")
            except Exception as e:
                logger.error(f"Error cancelling sell module background task: {e}")
        
        logger.info("✅ Sell module background service stopped")
    
    async def _background_monitoring(self):
        """Background monitoring task that runs the sell watcher"""
        try:
            logger.info("Starting sell module background monitoring...")
            await self.sell_watcher.start_monitoring()
        except asyncio.CancelledError:
            logger.info("Sell module background monitoring cancelled")
            raise
        except Exception as e:
            logger.error(f"Sell module background monitoring failed: {e}")
            self.is_running = False
            raise
    
    def get_status(self) -> dict:
        """Get status of the sell background service"""
        return {
            "enabled": self.is_enabled,
            "running": self.is_running,
            "task_status": "running" if self.background_task and not self.background_task.done() else "stopped",
            "sell_watcher_initialized": self.sell_watcher is not None,
            "account_pool_initialized": self.account_pool is not None and self.account_pool._initialized
        }
    
    async def restart(self) -> bool:
        """Restart the sell background service"""
        logger.info("Restarting sell module background service...")
        await self.stop()
        await asyncio.sleep(1)  # Give some time for cleanup
        return await self.start()


# Global instance
sell_background_service = SellBackgroundService()


@asynccontextmanager
async def sell_service_lifespan():
    """Context manager for sell service lifecycle management"""
    service_started = False
    try:
        # Start sell service
        service_started = await sell_background_service.start()
        yield sell_background_service
    except Exception as e:
        logger.error(f"Error in sell service lifespan: {e}")
    finally:
        # Stop sell service
        if service_started:
            await sell_background_service.stop()


def get_sell_background_service() -> SellBackgroundService:
    """Get the sell background service instance"""
    return sell_background_service


# API endpoints for sell service management
async def get_sell_service_status():
    """Get sell service status for API"""
    return sell_background_service.get_status()


async def restart_sell_service():
    """Restart sell service via API"""
    return await sell_background_service.restart()


async def start_sell_service():
    """Start sell service via API"""
    return await sell_background_service.start()


async def stop_sell_service():
    """Stop sell service via API"""
    await sell_background_service.stop()
    return {"status": "stopped"}