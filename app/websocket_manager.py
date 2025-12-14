"""
WebSocket Manager - In-Memory Real-Time Data
Connects to Alpaca WebSocket and maintains in-memory cache
"""

import asyncio
import json
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
import websockets
import random

from config import settings
from alpaca.trading.client import TradingClient


class WebSocketManager:
    """Manages Alpaca WebSocket connections and in-memory data"""
    
    def __init__(self):
        self.accounts_data: Dict[str, dict] = {}
        self.positions_data: Dict[str, list] = {}
        self.orders_data: Dict[str, list] = {}
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.running = False
        
        # Track reconnection attempts per account (for exponential backoff)
        self.reconnect_attempts: Dict[str, int] = {}
        self.last_error_time: Dict[str, datetime] = {}
        
        logger.info("✅ WebSocket Manager initialized")
    
    async def _load_account_data(self, account_id: str, config: dict, delay: float = 0):
        """Load initial data for a single account"""
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            
            client = TradingClient(
                api_key=config["api_key"],
                secret_key=config["secret_key"],
                paper=config["paper_trading"]
            )
            
            account = client.get_account()
            self.accounts_data[account_id] = {
                "account_id": account_id,
                "account_number": account.account_number,
                "status": account.status.value,
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "pattern_day_trader": account.pattern_day_trader,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            await asyncio.sleep(0.2)
            
            positions = client.get_all_positions()
            self.positions_data[account_id] = [
                {
                    "asset_id": str(pos.asset_id),
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "side": pos.side.value,
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "current_price": float(pos.current_price),
                    "lastday_price": float(pos.lastday_price),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "asset_class": pos.asset_class.value,
                    "qty_available": float(pos.qty_available),
                }
                for pos in positions
            ]
            
            await asyncio.sleep(0.2)
            
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            order_request = GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                limit=50
            )
            orders = client.get_orders(filter=order_request)
            self.orders_data[account_id] = [
                {
                    "order_id": order.id,
                    "symbol": order.symbol,
                    "qty": float(order.qty) if order.qty else None,
                    "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                    "side": order.side.value,
                    "order_type": order.order_type.value,
                    "status": order.status.value,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                    "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                }
                for order in orders
            ]
            
            logger.info(f"✅ Loaded data for {account_id}: {len(self.positions_data[account_id])} positions, {len(self.orders_data[account_id])} orders")
            
        except Exception as e:
            logger.error(f"❌ Failed to load data for {account_id}: {e}")
            if account_id not in self.accounts_data:
                self.accounts_data[account_id] = {}
            if account_id not in self.positions_data:
                self.positions_data[account_id] = []
            if account_id not in self.orders_data:
                self.orders_data[account_id] = []
    
    async def load_initial_data(self):
        """Load initial data for all accounts concurrently with staggered start"""
        logger.info(f"📥 Loading initial data for {len(settings.accounts)} accounts (concurrent)...")
        
        tasks = []
        for i, (account_id, config) in enumerate(settings.accounts.items()):
            delay = i * 0.5
            task = asyncio.create_task(self._load_account_data(account_id, config, delay))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        loaded_count = sum(1 for acc_id in settings.accounts.keys() if self.accounts_data.get(acc_id))
        logger.info(f"✅ Initial data loaded: {loaded_count}/{len(settings.accounts)} accounts ready")
    
    async def refresh_account_data(self, account_id: str):
        """Refresh account and positions after trade update"""
        try:
            config = settings.accounts.get(account_id)
            if not config:
                return
            
            client = TradingClient(
                api_key=config["api_key"],
                secret_key=config["secret_key"],
                paper=config["paper_trading"]
            )
            
            # Update account
            account = client.get_account()
            self.accounts_data[account_id].update({
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "last_updated": datetime.utcnow().isoformat()
            })
            
            # Update positions
            positions = client.get_all_positions()
            self.positions_data[account_id] = [
                {
                    "asset_id": str(pos.asset_id),
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "side": pos.side.value,
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "current_price": float(pos.current_price),
                    "lastday_price": float(pos.lastday_price),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "asset_class": pos.asset_class.value,
                    "qty_available": float(pos.qty_available),
                }
                for pos in positions
            ]
            
            logger.info(f"🔄 Refreshed {account_id}: {len(self.positions_data[account_id])} positions")
            
        except Exception as e:
            logger.error(f"Failed to refresh {account_id}: {e}")
    
    async def handle_trade_update(self, account_id: str, event_data: dict):
        """Handle WebSocket trade update"""
        try:
            event = event_data.get("event")
            order_data = event_data.get("data", {}).get("order", {})
            
            symbol = order_data.get("symbol", "")
            status = order_data.get("status", "")
            
            logger.info(f"📊 {account_id} | {event} | {symbol} | {status}")
            
            # Update order in memory
            order_id = order_data.get("id")
            if order_id:
                # Find and update existing order or add new
                orders = self.orders_data.get(account_id, [])
                existing_order = next((o for o in orders if o["order_id"] == order_id), None)
                
                order_update = {
                    "order_id": order_id,
                    "symbol": symbol,
                    "qty": float(order_data.get("qty", 0)) if order_data.get("qty") else None,
                    "filled_qty": float(order_data.get("filled_qty", 0)) if order_data.get("filled_qty") else 0,
                    "side": order_data.get("side", ""),
                    "order_type": order_data.get("order_type", ""),
                    "status": status,
                    "submitted_at": order_data.get("submitted_at"),
                    "filled_at": order_data.get("filled_at"),
                }
                
                if existing_order:
                    existing_order.update(order_update)
                else:
                    orders.append(order_update)
                    self.orders_data[account_id] = orders
            
            # If filled/partial_fill, refresh account and positions
            if event in ["fill", "partial_fill"]:
                logger.info(f"🔄 Order filled, refreshing {account_id}")
                await self.refresh_account_data(account_id)
            
        except Exception as e:
            logger.error(f"Failed to handle trade update: {e}")
    
    def _calculate_backoff_delay(self, account_id: str) -> float:
        """Calculate exponential backoff delay with jitter"""
        attempts = self.reconnect_attempts.get(account_id, 0)
        
        # Base delay: 5s, max delay: 300s (5 minutes)
        base_delay = 5
        max_delay = 300
        
        # Exponential backoff: 5s, 10s, 20s, 40s, 80s, 160s, 300s
        delay = min(base_delay * (2 ** attempts), max_delay)
        
        # Add jitter (±20%) to avoid thundering herd
        jitter = delay * 0.2 * (random.random() * 2 - 1)
        final_delay = delay + jitter
        
        return max(final_delay, base_delay)
    
    async def connect_websocket(self, account_id: str):
        """Connect to Alpaca WebSocket for an account with error handling and exponential backoff"""
        config = settings.accounts.get(account_id)
        if not config:
            logger.error(f"❌ No config found for {account_id}")
            return
        
        ws_url = "wss://paper-api.alpaca.markets/stream" if config["paper_trading"] else "wss://api.alpaca.markets/stream"
        
        while self.running:
            try:
                logger.info(f"🔌 Connecting WebSocket for {account_id}...")
                
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    # Authenticate
                    auth_msg = {
                        "action": "auth",
                        "key": config["api_key"],
                        "secret": config["secret_key"]
                    }
                    await ws.send(json.dumps(auth_msg))
                    
                    auth_response = await ws.recv()
                    auth_data = json.loads(auth_response)
                    
                    if auth_data.get("data", {}).get("status") != "authorized":
                        logger.error(f"❌ Auth failed for {account_id}: {auth_data}")
                        # Auth failure is not recoverable, don't retry
                        return
                    
                    # Subscribe to trade updates
                    listen_msg = {
                        "action": "listen",
                        "data": {"streams": ["trade_updates"]}
                    }
                    await ws.send(json.dumps(listen_msg))
                    
                    # Wait for acknowledgement
                    await ws.recv()
                    
                    logger.info(f"✅ WebSocket connected for {account_id}")
                    self.connections[account_id] = ws
                    
                    # Reset reconnect attempts on successful connection
                    self.reconnect_attempts[account_id] = 0
                    
                    # Listen for messages
                    while self.running:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=30)
                            data = json.loads(message)
                            
                            if data.get("stream") == "trade_updates":
                                await self.handle_trade_update(account_id, data)
                            
                        except asyncio.TimeoutError:
                            # Send ping to keep connection alive
                            try:
                                await ws.ping()
                            except Exception as ping_error:
                                logger.warning(f"Ping failed for {account_id}: {ping_error}")
                                break
                        except websockets.exceptions.ConnectionClosed as e:
                            logger.warning(f"⚠️ WebSocket closed for {account_id}: {e}")
                            break
                        
            except websockets.exceptions.WebSocketException as e:
                error_msg = str(e)
                
                # Check for 429 rate limit error
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    self.reconnect_attempts[account_id] = self.reconnect_attempts.get(account_id, 0) + 1
                    delay = self._calculate_backoff_delay(account_id)
                    logger.error(
                        f"🚫 Rate limit (429) for {account_id} - "
                        f"attempt {self.reconnect_attempts[account_id]}, "
                        f"retrying in {delay:.1f}s"
                    )
                    self.last_error_time[account_id] = datetime.utcnow()
                    
                    if self.running:
                        await asyncio.sleep(delay)
                        continue
                    else:
                        break
                else:
                    logger.error(f"❌ WebSocket error for {account_id}: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error for {account_id}: {e}")
            
            # Reconnect with exponential backoff
            if self.running:
                self.reconnect_attempts[account_id] = self.reconnect_attempts.get(account_id, 0) + 1
                delay = self._calculate_backoff_delay(account_id)
                logger.info(
                    f"🔄 Will retry WebSocket for {account_id} in {delay:.1f}s "
                    f"(attempt {self.reconnect_attempts[account_id]})"
                )
                await asyncio.sleep(delay)
            else:
                break
        
        # Cleanup
        if account_id in self.connections:
            del self.connections[account_id]
        logger.info(f"🛑 WebSocket task stopped for {account_id}")
    
    async def start(self):
        """Start WebSocket manager with independent account connections"""
        self.running = True
        logger.info("🚀 Starting WebSocket Manager")
        
        # Load initial data with rate limiting
        await self.load_initial_data()
        
        # Connect WebSockets for all accounts with staggered delays
        # Each account runs independently - errors in one won't affect others
        tasks = []
        for i, account_id in enumerate(settings.accounts.keys()):
            # Add 2-second delay between connection attempts to avoid rate limits
            if i > 0:
                logger.info(f"⏳ Waiting 2s before connecting {account_id}...")
                await asyncio.sleep(2)
            
            # Create independent task for each account
            task = asyncio.create_task(self.connect_websocket(account_id))
            tasks.append(task)
            logger.info(f"📡 Started WebSocket task for {account_id}")
        
        # Wait for all tasks (they run independently and handle their own errors)
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("🏁 All WebSocket tasks completed")
    
    async def stop(self):
        """Stop WebSocket manager"""
        self.running = False
        logger.info("🛑 Stopping WebSocket Manager")
        
        for ws in self.connections.values():
            await ws.close()
    
    def get_account(self, account_id: str) -> Optional[dict]:
        """Get account data from memory"""
        return self.accounts_data.get(account_id)
    
    def get_positions(self, account_id: str) -> list:
        """Get positions from memory"""
        return self.positions_data.get(account_id, [])
    
    def get_orders(self, account_id: str) -> list:
        """Get orders from memory"""
        return self.orders_data.get(account_id, [])
    
    def get_dashboard(self, account_id: str) -> dict:
        """Get complete dashboard data from memory"""
        account = self.get_account(account_id)
        positions = self.get_positions(account_id)
        orders = self.get_orders(account_id)
        
        if not account:
            return None
        
        # Calculate totals
        total_position_value = sum(p["market_value"] for p in positions)
        total_unrealized_pl = sum(p["unrealized_pl"] for p in positions)
        
        return {
            "account": account,
            "positions": positions,
            "orders": orders,
            "summary": {
                "total_positions": len(positions),
                "total_position_value": total_position_value,
                "total_unrealized_pl": total_unrealized_pl,
                "cash": account["cash"],
                "portfolio_value": account["portfolio_value"],
                "buying_power": account["buying_power"]
            }
        }
    
    def get_connection_status(self) -> dict:
        """Get WebSocket connection status for all accounts"""
        status = {
            "total_accounts": len(settings.accounts),
            "connected_accounts": len(self.connections),
            "accounts": {}
        }
        
        for account_id in settings.accounts.keys():
            is_connected = account_id in self.connections
            reconnect_attempts = self.reconnect_attempts.get(account_id, 0)
            last_error = self.last_error_time.get(account_id)
            
            status["accounts"][account_id] = {
                "connected": is_connected,
                "reconnect_attempts": reconnect_attempts,
                "last_error": last_error.isoformat() if last_error else None,
                "has_data": account_id in self.accounts_data and bool(self.accounts_data[account_id])
            }
        
        return status


# Global instance
ws_manager = WebSocketManager()
