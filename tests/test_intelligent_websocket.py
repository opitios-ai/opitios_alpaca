#!/usr/bin/env python3
"""
Test intelligent WebSocket functionality.
"""
import asyncio
import pytest
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger


class TestIntelligentWebSocket:
    """Test class for intelligent WebSocket functionality."""

    @pytest.mark.asyncio
    async def test_endpoint_detection(self):
        """Test intelligent endpoint detection."""
        logger.info("🧪 Testing intelligent endpoint detection...")
        
        try:
            from app.websocket_routes_fixed import SmartWebSocketManager
            
            ws_manager = SmartWebSocketManager()
            
            # Test that the manager has the expected endpoints
            assert hasattr(ws_manager, 'STOCK_ENDPOINTS')
            assert len(ws_manager.STOCK_ENDPOINTS) > 0
            
            logger.info("✅ Endpoint detection test passed")
            
        except ImportError as e:
            pytest.skip(f"WebSocket manager not available: {e}")
        except Exception as e:
            pytest.fail(f"Endpoint detection test failed: {e}")

    @pytest.mark.asyncio
    async def test_error_handling_strategies(self):
        """Test WebSocket error handling strategies."""
        logger.info("🧪 Testing error handling strategies...")
        
        try:
            from app.websocket_routes_fixed import SmartWebSocketManager
            
            ws_manager = SmartWebSocketManager()
            
            # Test error 402 (insufficient subscription)
            test_error_402 = {"T": "error", "code": 402, "msg": "subscription insufficient"}
            strategy_402 = await ws_manager.handle_websocket_error(test_error_402, "stock")
            
            assert 'action' in strategy_402
            logger.info(f"Error 402 strategy: {strategy_402['action']}")
            
            # Test error 406 (connection limit)
            test_error_406 = {"T": "error", "code": 406, "msg": "connection limit exceeded"}
            strategy_406 = await ws_manager.handle_websocket_error(test_error_406, "stock")
            
            assert 'action' in strategy_406
            logger.info(f"Error 406 strategy: {strategy_406['action']}")
            
            logger.info("✅ Error handling strategies test passed")
            
        except ImportError as e:
            pytest.skip(f"WebSocket manager not available: {e}")
        except Exception as e:
            pytest.fail(f"Error handling test failed: {e}")

    def test_websocket_manager_initialization(self):
        """Test that WebSocket manager can be initialized."""
        try:
            from app.websocket_routes_fixed import SmartWebSocketManager
            
            ws_manager = SmartWebSocketManager()
            assert ws_manager is not None
            
            logger.info("✅ WebSocket manager initialization test passed")
            
        except ImportError as e:
            pytest.skip(f"WebSocket manager not available: {e}")
        except Exception as e:
            pytest.fail(f"WebSocket manager initialization failed: {e}")