#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Comprehensive Health Check for Alpaca Trading Service
Tests all API endpoints with correct accounts to ensure everything works.
"""

import asyncio
import sys
import os
import time
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.account_pool import get_account_pool
from app.alpaca_client import AlpacaClient
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich import box

class HealthChecker:
    """Comprehensive health checker for all API endpoints and accounts"""
    
    def __init__(self):
        self.pool = None
        self.results = {}
        self.console = Console()
        self.secrets_config = None
        
    async def initialize(self):
        """Initialize account pool and load secrets configuration"""
        self.pool = get_account_pool()
        await self.pool.initialize()
        
        # Load secrets configuration
        try:
            with open('secrets.yml', 'r', encoding='utf-8') as f:
                self.secrets_config = yaml.safe_load(f)
            logger.info("✅ Secrets configuration loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load secrets.yml: {e}")
            self.secrets_config = None
            
        logger.info(f"Health checker initialized with {len(self.pool.account_configs)} accounts")
    
    def check_secrets_configuration(self) -> Dict[str, Any]:
        """Check secrets.yml configuration completeness"""
        logger.debug("🔐 Checking secrets configuration")
        
        if not self.secrets_config:
            return {
                "status": "ERROR",
                "error": "secrets.yml not loaded",
                "database_configured": False,
                "accounts_configured": False,
                "jwt_configured": False,
                "trading_configured": False
            }
        
        try:
            # Check database configuration
            database_ok = bool(self.secrets_config.get('database', {}).get('url'))
            
            # Check accounts configuration
            accounts = self.secrets_config.get('accounts', {})
            accounts_ok = len(accounts) >= 2 and all(
                'api_key' in acc and 'secret_key' in acc 
                for acc in accounts.values()
            )
            
            # Check JWT configuration
            jwt = self.secrets_config.get('jwt', {})
            jwt_ok = bool(jwt.get('secret_key') and jwt.get('algorithm'))
            
            # Check trading configuration
            trading = self.secrets_config.get('trading', {})
            trading_ok = 'real_data_only' in trading and 'max_option_symbols_per_request' in trading
            
            overall_status = "HEALTHY" if all([database_ok, accounts_ok, jwt_ok, trading_ok]) else "DEGRADED"
            
            return {
                "status": overall_status,
                "error": None,
                "database_configured": database_ok,
                "accounts_configured": accounts_ok,
                "jwt_configured": jwt_ok,
                "trading_configured": trading_ok,
                "total_accounts": len(accounts),
                "enabled_accounts": sum(1 for acc in accounts.values() if acc.get('enabled', True))
            }
            
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "database_configured": False,
                "accounts_configured": False,
                "jwt_configured": False,
                "trading_configured": False
            }
    
    async def check_stock_endpoints(self, account_id: str) -> Dict[str, Any]:
        """Check all stock-related endpoints - optimized for parallel execution"""
        logger.debug(f"📈 Checking stock endpoints for: {account_id}")
        try:
            # Get account config for direct HTTP client creation (no locks)
            config = self.pool.get_account_config(account_id)
            if not config:
                return {"status": "ERROR", "error": f"Account config not found for {account_id}", "endpoints": {}}
            
            # Create direct HTTP client (no connection pool locks)
            from app.alpaca_client import AlpacaClient
            client = AlpacaClient(
                api_key=config.api_key,
                secret_key=config.secret_key,
                paper_trading=config.paper_trading
            )
            
            results = {}
            
            # Test single stock quote
            quote = await client.get_stock_quote("AAPL")
            results["single_quote"] = {"status": "OK" if quote and "error" not in quote else "FAIL", "data": quote}
            
            # Test multiple stock quotes
            batch_quotes = await client.get_multiple_stock_quotes(["AAPL", "TSLA"])
            results["batch_quotes"] = {"status": "OK" if batch_quotes and "error" not in batch_quotes else "FAIL", "data": batch_quotes}
            
            # Test stock bars (may fail due to subscription limits)
            try:
                bars = await client.get_stock_bars("AAPL", limit=5)
                results["stock_bars"] = {"status": "OK" if bars and "error" not in bars else "FAIL", "data": bars}
            except Exception as e:
                results["stock_bars"] = {"status": "LIMITED", "error": str(e)}
            
            # Determine overall status
            if results["single_quote"]["status"] == "OK" and results["batch_quotes"]["status"] == "OK":
                overall_status = "HEALTHY"
            elif results["single_quote"]["status"] == "OK" or results["batch_quotes"]["status"] == "OK":
                overall_status = "PARTIAL"
            else:
                overall_status = "ERROR"
            
            return {
                "status": overall_status,
                "error": None,
                "endpoints": results
            }
            
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "endpoints": {}
            }
    
    async def check_options_endpoints(self, account_id: str) -> Dict[str, Any]:
        """Check all options-related endpoints - optimized for parallel execution"""
        logger.debug(f"📊 Checking options endpoints for: {account_id}")
        try:
            # Get account config for direct HTTP client creation (no locks)
            config = self.pool.get_account_config(account_id)
            if not config:
                return {"status": "ERROR", "error": f"Account config not found for {account_id}", "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
            
            # Create direct HTTP client (no connection pool locks)
            from app.alpaca_client import AlpacaClient
            client = AlpacaClient(
                api_key=config.api_key,
                secret_key=config.secret_key,
                paper_trading=config.paper_trading
            )
            
            results = {}
            
            # Test options chain (using 2026-09-18 date as specified)
            try:
                chain = await client.get_options_chain("AAPL", expiration_date="2026-09-18")
                results["options_chain"] = {"status": "OK" if chain and "error" not in chain else "FAIL", "data": chain}
            except Exception as e:
                results["options_chain"] = {"status": "FAIL", "error": str(e)}
            
            # Test single option quote (using AAPL260918P00130000 as specified)
            try:
                option_quote = await client.get_option_quote("AAPL260918P00130000")
                results["option_quote"] = {"status": "OK" if option_quote and "error" not in option_quote else "FAIL", "data": option_quote}
            except Exception as e:
                results["option_quote"] = {"status": "FAIL", "error": str(e)}
            
            # Test batch option quotes (using AAPL260918P00130000 as specified)
            try:
                batch_options = await client.get_multiple_option_quotes(["AAPL260918P00130000"])
                results["batch_option_quotes"] = {"status": "OK" if batch_options and "error" not in batch_options else "FAIL", "data": batch_options}
            except Exception as e:
                results["batch_option_quotes"] = {"status": "FAIL", "error": str(e)}
            
            # Determine overall status
            working_endpoints = sum(1 for ep in results.values() if ep["status"] == "OK")
            total_endpoints = len(results)
            
            if working_endpoints == total_endpoints:
                overall_status = "HEALTHY"
            elif working_endpoints > 0:
                overall_status = "PARTIAL"
            else:
                overall_status = "ERROR"
            
            return {
                "status": overall_status,
                "error": None,
                "endpoints": results,
                "working_endpoints": working_endpoints,
                "total_endpoints": total_endpoints
            }
            
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "endpoints": {},
                "working_endpoints": 0,
                "total_endpoints": 0
            }
    
    async def check_trading_endpoints(self, account_id: str) -> Dict[str, Any]:
        """Check trading-related endpoints following the specified flow - optimized for parallel execution:
        1. Get all pending orders
        2. Cancel all existing orders if any exist
        3. Place stock order at limit price 0.01
        4. Place option order at limit price 0.01 (AAPL260918P00130000)
        5. Cancel all orders (cleanup)"""
        logger.debug(f"💰 Checking trading endpoints for: {account_id}")
        try:
            # Get account config for direct HTTP client creation (no locks)
            config = self.pool.get_account_config(account_id)
            if not config:
                return {"status": "ERROR", "error": f"Account config not found for {account_id}", "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
            
            # Create direct HTTP client (no connection pool locks)
            from app.alpaca_client import AlpacaClient
            client = AlpacaClient(
                api_key=config.api_key,
                secret_key=config.secret_key,
                paper_trading=config.paper_trading
            )
            
            results = {}
            
            # Step 1: Test get orders (get all pending orders)
            try:
                orders = await client.get_orders(limit=100)
                results["get_orders"] = {"status": "OK" if orders is not None else "FAIL", "data": orders}
            except Exception as e:
                results["get_orders"] = {"status": "FAIL", "error": str(e)}
            
            # Step 2: Cancel all existing orders if any exist
            try:
                if results.get("get_orders", {}).get("status") == "OK" and results["get_orders"]["data"]:
                    orders_data = results["get_orders"]["data"]
                    cancelled_orders = []
                    for order in orders_data:
                        if order.get("id") and order.get("status") in ["pending_new", "accepted", "pending_cancel"]:
                            try:
                                cancel_result = await client.cancel_order(order["id"])
                                cancelled_orders.append({"order_id": order["id"], "result": cancel_result})
                            except Exception as cancel_error:
                                cancelled_orders.append({"order_id": order["id"], "error": str(cancel_error)})
                    results["cancel_existing_orders"] = {"status": "OK", "cancelled_count": len(cancelled_orders), "data": cancelled_orders}
                else:
                    results["cancel_existing_orders"] = {"status": "SKIP", "message": "No existing orders to cancel"}
            except Exception as e:
                results["cancel_existing_orders"] = {"status": "FAIL", "error": str(e)}
            
            # Step 3: Place stock order at limit price 0.01 (as specified)
            try:
                order = await client.place_stock_order(
                    symbol="AAPL", qty=1, side="buy", order_type="limit", 
                    limit_price=0.01, time_in_force="day"
                )
                results["place_stock_order"] = {"status": "OK" if order and "error" not in order else "FAIL", "data": order}
            except Exception as e:
                results["place_stock_order"] = {"status": "FAIL", "error": str(e)}
            
            # Step 4: Place option order at limit price 0.01 (as specified)
            try:
                option_order = await client.place_option_order(
                    option_symbol="AAPL260918P00130000", qty=1, side="buy", order_type="limit",
                    limit_price=0.01, time_in_force="day"
                )
                results["place_option_order"] = {"status": "OK" if option_order and "error" not in option_order else "FAIL", "data": option_order}
            except Exception as e:
                results["place_option_order"] = {"status": "FAIL", "error": str(e)}
            
            # Step 5: Cancel all orders (cleanup)
            try:
                # Get current orders again
                current_orders = await client.get_orders(limit=100)
                cancelled_orders = []
                if current_orders:
                    for order in current_orders:
                        if order.get("id") and order.get("status") in ["pending_new", "accepted", "pending_cancel"]:
                            try:
                                cancel_result = await client.cancel_order(order["id"])
                                cancelled_orders.append({"order_id": order["id"], "result": cancel_result})
                            except Exception as cancel_error:
                                cancelled_orders.append({"order_id": order["id"], "error": str(cancel_error)})
                results["cancel_all_orders"] = {"status": "OK", "cancelled_count": len(cancelled_orders), "data": cancelled_orders}
            except Exception as e:
                results["cancel_all_orders"] = {"status": "FAIL", "error": str(e)}
            
            # Determine overall status
            working_endpoints = sum(1 for ep in results.values() if ep["status"] == "OK")
            total_endpoints = len([ep for ep in results.values() if ep["status"] != "SKIP"])
            
            if working_endpoints == total_endpoints:
                overall_status = "HEALTHY"
            elif working_endpoints > 0:
                overall_status = "PARTIAL"
            else:
                overall_status = "ERROR"
            
            return {
                "status": overall_status,
                "error": None,
                "endpoints": results,
                "working_endpoints": working_endpoints,
                "total_endpoints": total_endpoints
            }
            
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "endpoints": {},
                "working_endpoints": 0,
                "total_endpoints": 0
            }
    
    async def check_trading_endpoints_parallel(self, account_ids: List[str]) -> Dict[str, Any]:
        """Check trading endpoints for multiple accounts in parallel - MUCH FASTER"""
        logger.info(f"🚀 Running parallel trading checks for {len(account_ids)} accounts")
        
        async def check_single_account_trading(account_id: str) -> Dict[str, Any]:
            """Check trading for a single account"""
            try:
                config = self.pool.get_account_config(account_id)
                if not config:
                    return {"account_id": account_id, "status": "ERROR", "error": f"Account config not found"}
                
                client = AlpacaClient(
                    api_key=config.api_key,
                    secret_key=config.secret_key,
                    paper_trading=config.paper_trading
                )
                
                # Run all trading operations in parallel for this account
                get_orders_task = client.get_orders(limit=100)
                place_stock_task = client.place_stock_order(
                    symbol="AAPL", qty=1, side="buy", order_type="limit", 
                    limit_price=0.01, time_in_force="day"
                )
                place_option_task = client.place_option_order(
                    option_symbol="AAPL260918P00130000", qty=1, side="buy", order_type="limit",
                    limit_price=0.01, time_in_force="day"
                )
                
                # Execute all operations in parallel
                orders, stock_order, option_order = await asyncio.gather(
                    get_orders_task, place_stock_task, place_option_task,
                    return_exceptions=True
                )
                
                # Cancel all orders (cleanup)
                cancelled_orders = []
                if isinstance(orders, list) and not isinstance(orders, Exception):
                    for order in orders:
                        if order.get("id") and order.get("status") in ["pending_new", "accepted", "pending_cancel"]:
                            try:
                                cancel_result = await client.cancel_order(order["id"])
                                cancelled_orders.append({"order_id": order["id"], "result": cancel_result})
                            except Exception as cancel_error:
                                cancelled_orders.append({"order_id": order["id"], "error": str(cancel_error)})
                
                # Determine status
                success_count = 0
                if not isinstance(orders, Exception):
                    success_count += 1
                if not isinstance(stock_order, Exception) and stock_order and "error" not in stock_order:
                    success_count += 1
                if not isinstance(option_order, Exception) and option_order and "error" not in option_order:
                    success_count += 1
                
                status = "HEALTHY" if success_count == 3 else "PARTIAL" if success_count > 0 else "ERROR"
                
                return {
                    "account_id": account_id,
                    "status": status,
                    "success_count": success_count,
                    "total_operations": 3,
                    "orders": orders if not isinstance(orders, Exception) else str(orders),
                    "stock_order": stock_order if not isinstance(stock_order, Exception) else str(stock_order),
                    "option_order": option_order if not isinstance(option_order, Exception) else str(option_order),
                    "cancelled_orders": len(cancelled_orders)
                }
                
            except Exception as e:
                return {"account_id": account_id, "status": "ERROR", "error": str(e)}
        
        # Run all accounts in parallel
        start_time = time.time()
        results = await asyncio.gather(
            *[check_single_account_trading(account_id) for account_id in account_ids],
            return_exceptions=True
        )
        parallel_time = time.time() - start_time
        
        # Process results
        account_results = {}
        healthy_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Trading check failed: {result}")
                continue
                
            account_id = result["account_id"]
            account_results[account_id] = result
            
            if result["status"] == "HEALTHY":
                healthy_count += 1
        
        logger.info(f"⚡ Parallel trading check completed in {parallel_time:.2f}s: {healthy_count}/{len(account_ids)} accounts healthy")
        
        return {
            "status": "COMPLETED",
            "execution_time": parallel_time,
            "healthy_accounts": healthy_count,
            "total_accounts": len(account_ids),
            "success_rate": f"{(healthy_count/len(account_ids))*100:.1f}%" if account_ids else "0%",
            "accounts": account_results
        }
    
    async def _get_disabled_options_result(self) -> Dict[str, Any]:
        """Return a placeholder result when options chain processing is disabled"""
        return {
            "status": "SKIP",
            "error": None,
            "endpoints": {},
            "working_endpoints": 0,
            "total_endpoints": 0,
            "message": "Options chain processing disabled (use --include-options-chain to enable)"
        }
    
    async def check_account_basics(self, account_id: str) -> Dict[str, Any]:
        """Check basic account info and assets - optimized for parallel execution"""
        logger.debug(f"📊 Checking account basics for: {account_id}")
        try:
            # Get account config for direct HTTP client creation (no locks)
            config = self.pool.get_account_config(account_id)
            if not config:
                return {"status": "ERROR", "error": f"Account config not found for {account_id}", "account_number": "N/A", "equity": 0, "buying_power": 0, "cash": 0, "positions_count": 0}
            
            # Create direct HTTP client (no connection pool locks)
            from app.alpaca_client import AlpacaClient
            client = AlpacaClient(
                api_key=config.api_key,
                secret_key=config.secret_key,
                paper_trading=config.paper_trading
            )
            
            account_data = await client.get_account()
            positions = await client.get_positions()
            
            # Get this week's orders to match with current positions for time tracking
            entry_times = await self._get_weekly_entry_times(client)
            
            # Process positions with time tracking
            processed_positions = []
            if positions:
                for pos in positions:
                    symbol = pos.get('symbol', 'Unknown')
                    
                    # Find real entry time from this week's orders
                    real_entry_time = entry_times.get(symbol)
                    if real_entry_time:
                        entry_time_str = datetime.fromtimestamp(real_entry_time).strftime('%m-%d %H:%M')
                        hold_duration_minutes = (datetime.now().timestamp() - real_entry_time) / 60
                    else:
                        entry_time_str = 'Unknown (24h+)'
                        hold_duration_minutes = 24 * 60 + 1  # Default to 24+ hours for risk management
                    
                    processed_positions.append({
                        'symbol': symbol,
                        'asset_class': pos.get('asset_class', 'unknown'),
                        'qty': pos.get('qty', 0),
                        'side': pos.get('side', 'unknown'),
                        'current_price': pos.get('current_price', 0),
                        'market_value': pos.get('market_value', 0),
                        'unrealized_plpc': pos.get('unrealized_plpc', 0),
                        'hold_duration_minutes': round(hold_duration_minutes, 1),
                        'entry_time': entry_time_str,
                        'is_option': pos.get('asset_class') == 'us_option',
                        'is_zero_day': self._is_zero_day_option(symbol)
                    })
            
            return {
                "status": "HEALTHY",
                "account_number": account_data.get("account_number", "N/A"),
                "equity": float(account_data.get("equity", 0)),
                "buying_power": float(account_data.get("buying_power", 0)),
                "cash": float(account_data.get("cash", 0)),
                "positions_count": len(processed_positions),
                "positions": processed_positions,
                "error": None
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "account_number": "N/A",
                "equity": 0,
                "buying_power": 0,
                "cash": 0,
                "positions_count": 0
            }
    
    def _is_zero_day_option(self, symbol: str) -> bool:
        """Check if option symbol is zero-day (expires today)"""
        if not symbol or len(symbol) < 15:
            return False
        
        try:
            # Parse option symbol: AAPL250912C00150000 -> 250912
            # Find first digit position
            first_digit_pos = -1
            for i, char in enumerate(symbol):
                if char.isdigit():
                    first_digit_pos = i
                    break
            
            if first_digit_pos == -1 or first_digit_pos + 6 > len(symbol):
                return False
            
            # Extract date part (6 digits after first digit)
            date_part = symbol[first_digit_pos:first_digit_pos + 6]
            if len(date_part) != 6 or not date_part.isdigit():
                return False
            
            # Convert to date: 250912 -> 2025-09-12
            year = int("20" + date_part[:2])
            month = int(date_part[2:4])
            day = int(date_part[4:6])
            
            option_date = datetime(year, month, day).date()
            today = datetime.now().date()
            
            return option_date == today
            
        except Exception:
            return False
    
    async def _get_weekly_entry_times(self, client) -> Dict[str, float]:
        """Get entry times from this week's orders for position time tracking"""
        entry_times = {}
        
        try:
            # Calculate start of week (Monday) and format for API
            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            
            # Format dates for Alpaca API (ISO format)
            after_date = start_of_week.strftime('%Y-%m-%dT00:00:00Z')
            before_date = today.strftime('%Y-%m-%dT23:59:59Z')
            
            logger.debug(f"Querying orders from {after_date} to {before_date}")
            
            # Query orders with date range
            weekly_orders = await client.get_orders(limit=1000, after=after_date, before=before_date)
            if not weekly_orders:
                logger.debug("No orders found for this week")
                return entry_times
            
            logger.debug(f"Retrieved {len(weekly_orders)} orders from this week")
            
            for order in weekly_orders:
                symbol = order.get('symbol')
                side = order.get('side')
                status = order.get('status')
                
                # Only process buy orders with valid status
                if not (symbol and side == 'buy' and status in ['filled', 'done_for_day', 'accepted', 'new']):
                    continue
                
                # Get the most relevant timestamp
                timestamp_str = order.get('filled_at') or order.get('submitted_at') or order.get('created_at')
                if not timestamp_str:
                    continue
                
                try:
                    # Parse timestamp
                    if 'T' in timestamp_str:
                        if timestamp_str.endswith('Z'):
                            order_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            order_time = datetime.fromisoformat(timestamp_str)
                    else:
                        order_time = datetime.fromisoformat(timestamp_str)
                    
                    timestamp = order_time.timestamp()
                    # Keep the most recent entry time for each symbol
                    if symbol not in entry_times or timestamp > entry_times[symbol]:
                        entry_times[symbol] = timestamp
                        
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp '{timestamp_str}' for order {order.get('id')}: {e}")
                    continue
            
            logger.debug(f"Found entry times for {len(entry_times)} symbols from {len(weekly_orders)} this week's orders")
            
        except Exception as e:
            logger.debug(f"Failed to get weekly orders: {e}")
        
        return entry_times
    
    async def check_single_account(self, account_id: str, include_options_chain: bool = False) -> Dict[str, Any]:
        """Comprehensive check for a single account with all endpoints
        
        Args:
            account_id: Account ID to check
            include_options_chain: If True, includes options chain processing (slow operation)
        """
        logger.info(f"🔍 Starting comprehensive health check for account: {account_id}")
        
        # Run all checks in parallel for better performance
        try:
            # Prepare tasks based on options chain setting
            tasks = [
                self.check_account_basics(account_id),
                self.check_stock_endpoints(account_id),
                self.check_trading_endpoints(account_id)
            ]
            
            if include_options_chain:
                tasks.append(self.check_options_endpoints(account_id))
            else:
                # Add a placeholder for options endpoints when disabled
                tasks.append(asyncio.create_task(self._get_disabled_options_result()))
            
            basics, stock_endpoints, trading_endpoints, options_endpoints = await asyncio.gather(
                *tasks,
                return_exceptions=True
            )
            
            # Handle exceptions from parallel execution
            if isinstance(basics, Exception):
                basics = {"status": "ERROR", "error": str(basics), "account_number": "N/A", 
                         "equity": 0, "buying_power": 0, "cash": 0, "positions_count": 0}
            if isinstance(stock_endpoints, Exception):
                stock_endpoints = {"status": "ERROR", "error": str(stock_endpoints), "endpoints": {}}
            if isinstance(options_endpoints, Exception):
                options_endpoints = {"status": "ERROR", "error": str(options_endpoints), 
                                   "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
            if isinstance(trading_endpoints, Exception):
                trading_endpoints = {"status": "ERROR", "error": str(trading_endpoints), 
                                   "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
                
        except Exception as e:
            logger.error(f"Unexpected error in parallel check for {account_id}: {e}")
            basics = {"status": "ERROR", "error": f"Parallel execution failed: {e}", "account_number": "N/A", 
                     "equity": 0, "buying_power": 0, "cash": 0, "positions_count": 0}
            stock_endpoints = {"status": "ERROR", "error": f"Parallel execution failed: {e}", "endpoints": {}}
            options_endpoints = {"status": "ERROR", "error": f"Parallel execution failed: {e}", 
                               "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
            trading_endpoints = {"status": "ERROR", "error": f"Parallel execution failed: {e}", 
                               "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
        
        # Determine overall status
        if basics["status"] == "ERROR":
            overall_status = "CRITICAL"
        elif any(ep["status"] == "ERROR" for ep in [stock_endpoints, options_endpoints, trading_endpoints]):
            overall_status = "DEGRADED"
        elif any(ep["status"] == "PARTIAL" for ep in [stock_endpoints, options_endpoints, trading_endpoints]):
            overall_status = "PARTIAL"
        else:
            overall_status = "HEALTHY"
        
        result = {
            "account_id": account_id,
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "basics": basics,
            "stock_endpoints": stock_endpoints,
            "options_endpoints": options_endpoints,
            "trading_endpoints": trading_endpoints
        }
        
        # Log one-line summary as requested
        self._log_account_summary(account_id, result)
        
        return result
    
    def _log_account_summary(self, account_id: str, result: Dict[str, Any]):
        """Log condensed one-line account summary"""
        basics = result["basics"]
        stock_ep = result["stock_endpoints"]
        options_ep = result["options_endpoints"]
        trading_ep = result["trading_endpoints"]
        
        status_emoji = {
            "HEALTHY": "✅",
            "PARTIAL": "⚠️", 
            "DEGRADED": "🔶",
            "CRITICAL": "❌"
        }
        
        emoji = status_emoji.get(result["overall_status"], "❓")
        
        # Get endpoint statuses
        stock_status = "OK" if stock_ep["status"] == "HEALTHY" else "FAIL"
        options_status = f"{options_ep.get('working_endpoints', 0)}/{options_ep.get('total_endpoints', 0)}"
        trading_status = f"{trading_ep.get('working_endpoints', 0)}/{trading_ep.get('total_endpoints', 0)}"
        
        summary = (
            f"{emoji} {account_id}: {result['overall_status']} | "
            f"Account#{basics['account_number']} | "
            f"Equity=${basics['equity']:,.2f} | "
            f"Cash=${basics['cash']:,.2f} | "
            f"Positions={basics['positions_count']} | "
            f"Stock:{stock_status} | "
            f"Options:{options_status} | "
            f"Trading:{trading_status}"
        )
        
        if result["overall_status"] == "HEALTHY":
            logger.info(summary)
        elif result["overall_status"] in ["PARTIAL", "DEGRADED"]:
            logger.warning(summary)
        else:
            logger.error(summary)
        
        # Display position time table
        self._display_position_time_table(result["basics"]["positions"])
    
    def _display_position_time_table(self, positions: List[Dict[str, Any]]):
        """Display a table showing position hold times"""
        if not positions:
            return
        
        # Filter for options only (since stocks don't have time-sensitive expiry)
        option_positions = [pos for pos in positions if pos.get('is_option', False)]
        
        if not option_positions:
            return
        
        # Create table
        table = Table(
            title="⏰ 期权持仓时间表",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            title_style="bold blue"
        )
        
        # Add columns
        table.add_column("期权代码", style="cyan", no_wrap=True)
        table.add_column("数量", justify="right", style="green")
        table.add_column("当前价格", justify="right", style="yellow")
        table.add_column("市值", justify="right", style="green")
        table.add_column("盈亏%", justify="right", style="red")
        table.add_column("持仓时间", justify="right", style="blue")
        table.add_column("入场时间", style="magenta")
        table.add_column("零日期权", justify="center", style="red")
        
        # Add rows
        for pos in option_positions[:20]:  # Limit to first 20 for readability
            symbol = pos.get('symbol', 'Unknown')
            qty = pos.get('qty', 0)
            current_price = pos.get('current_price', 0)
            market_value = pos.get('market_value', 0)
            unrealized_plpc = pos.get('unrealized_plpc', 0)
            hold_duration_minutes = pos.get('hold_duration_minutes', 0)
            entry_time = pos.get('entry_time', 'Unknown')
            is_zero_day = pos.get('is_zero_day', False)
            
            # Format hold duration
            if hold_duration_minutes >= 1440:  # 24+ hours
                hold_duration_str = f"{hold_duration_minutes/1440:.1f}天"
            else:
                hold_duration_str = f"{hold_duration_minutes:.0f}分钟"
            
            # Format P&L with color
            pl_str = f"{unrealized_plpc*100:+.1f}%"
            pl_style = "green" if unrealized_plpc >= 0 else "red"
            
            # Zero day indicator
            zero_day_str = "⚠️" if is_zero_day else ""
            
            table.add_row(
                symbol,
                f"{qty:.0f}",
                f"${current_price:.2f}",
                f"${market_value:,.0f}",
                pl_str,
                hold_duration_str,
                entry_time,
                zero_day_str
            )
        
        # Display table
        console = Console()
        console.print(table)
        
        if len(option_positions) > 20:
            console.print(f"[dim]显示前20个期权持仓，共{len(option_positions)}个[/dim]")
    
    def _create_health_table(self, results: Dict[str, Any]) -> Table:
        """Create a beautiful Rich table for health check results"""
        table = Table(
            title="🏥 Alpaca Trading Service - Comprehensive Health Check",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            title_style="bold blue"
        )
        
        # Define columns
        table.add_column("Account ID", style="cyan", width=12)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Account #", style="dim", width=10)
        table.add_column("Equity", justify="right", style="green", width=12)
        table.add_column("Cash", justify="right", style="blue", width=10)
        table.add_column("Positions", justify="center", width=8)
        table.add_column("Stock APIs", justify="center", width=10)
        table.add_column("Options APIs", justify="center", width=12)
        table.add_column("Trading APIs", justify="center", width=12)
        
        # Status color mapping
        status_colors = {
            "HEALTHY": "green",
            "PARTIAL": "yellow", 
            "DEGRADED": "orange3",
            "CRITICAL": "red"
        }
        
        status_emojis = {
            "HEALTHY": "✅",
            "PARTIAL": "⚠️", 
            "DEGRADED": "🔶",
            "CRITICAL": "❌"
        }
        
        # Add rows
        for account_id, result in results.items():
            basics = result["basics"]
            stock_ep = result["stock_endpoints"]
            options_ep = result["options_endpoints"]
            trading_ep = result["trading_endpoints"]
            
            # Status with emoji and color
            status_text = f"{status_emojis.get(result['overall_status'], '❓')} {result['overall_status']}"
            status_style = status_colors.get(result['overall_status'], 'white')
            
            # Format currency values
            equity = f"${basics['equity']:,.2f}" if basics['equity'] > 0 else "N/A"
            cash = f"${basics['cash']:,.2f}" if basics['cash'] > 0 else "N/A"
            
            # API endpoint statuses
            stock_status = "✅ OK" if stock_ep["status"] == "HEALTHY" else "❌ FAIL"
            options_status = f"{options_ep.get('working_endpoints', 0)}/{options_ep.get('total_endpoints', 0)}"
            trading_status = f"{trading_ep.get('working_endpoints', 0)}/{trading_ep.get('total_endpoints', 0)}"
            
            table.add_row(
                account_id,
                Text(status_text, style=status_style),
                basics['account_number'],
                equity,
                cash,
                str(basics['positions_count']),
                stock_status,
                options_status,
                trading_status
            )
        
        return table
    
    def _create_secrets_panel(self, secrets_config: Dict[str, Any]) -> Panel:
        """Create a panel showing secrets configuration status"""
        status = secrets_config.get("status", "UNKNOWN")
        
        # Color based on status
        if status == "HEALTHY":
            border_color = "green"
            status_emoji = "✅"
        elif status == "DEGRADED":
            border_color = "yellow"
            status_emoji = "⚠️"
        else:
            border_color = "red"
            status_emoji = "❌"
        
        # Build configuration details
        config_details = []
        config_details.append(f"{status_emoji} [bold]Overall Status:[/bold] {status}")
        config_details.append("")
        config_details.append("📊 [bold]Configuration Checks:[/bold]")
        
        # Database
        db_status = "✅" if secrets_config.get("database_configured") else "❌"
        config_details.append(f"   {db_status} Database: {'Configured' if secrets_config.get('database_configured') else 'Missing'}")
        
        # Accounts
        accounts_status = "✅" if secrets_config.get("accounts_configured") else "❌"
        total_accounts = secrets_config.get("total_accounts", 0)
        enabled_accounts = secrets_config.get("enabled_accounts", 0)
        config_details.append(f"   {accounts_status} Accounts: {enabled_accounts}/{total_accounts} enabled")
        
        # JWT
        jwt_status = "✅" if secrets_config.get("jwt_configured") else "❌"
        config_details.append(f"   {jwt_status} JWT: {'Configured' if secrets_config.get('jwt_configured') else 'Missing'}")
        
        # Trading
        trading_status = "✅" if secrets_config.get("trading_configured") else "❌"
        config_details.append(f"   {trading_status} Trading: {'Configured' if secrets_config.get('trading_configured') else 'Missing'}")
        
        if secrets_config.get("error"):
            config_details.append("")
            config_details.append(f"❌ [bold red]Error:[/bold red] {secrets_config['error']}")
        
        return Panel(
            "\n".join(config_details),
            title="🔐 Secrets Configuration Status",
            border_style=border_color,
            padding=(1, 2)
        )
    
    def _create_summary_panel(self, result: Dict[str, Any]) -> Panel:
        """Create a summary panel with key statistics"""
        total_accounts = result['total_accounts']
        healthy_accounts = result['healthy_accounts']
        success_rate = result['success_rate']
        execution_time = result.get('execution_time', 0)
        avg_time = result.get('avg_time_per_account', 0)
        performance_mode = result.get('performance_mode', 'unknown')
        
        # Calculate health percentage
        health_percentage = (healthy_accounts / total_accounts * 100) if total_accounts > 0 else 0
        
        # Color based on health percentage
        if health_percentage >= 90:
            health_color = "green"
            health_emoji = "🟢"
        elif health_percentage >= 70:
            health_color = "yellow"
            health_emoji = "🟡"
        else:
            health_color = "red"
            health_emoji = "🔴"
        
        summary_text = f"""
{health_emoji} [bold {health_color}]Overall Health: {health_percentage:.1f}%[/bold {health_color}]

📊 [bold]Statistics:[/bold]
   • Total Accounts: [bold cyan]{total_accounts}[/bold cyan]
   • Healthy Accounts: [bold green]{healthy_accounts}[/bold green]
   • Success Rate: [bold blue]{success_rate}[/bold blue]

⏱️  [bold]Performance:[/bold]
   • Total Time: [bold yellow]{execution_time:.2f}s[/bold yellow]
   • Avg per Account: [bold yellow]{avg_time:.2f}s[/bold yellow]
   • Mode: [bold magenta]{performance_mode}[/bold magenta]
        """
        
        return Panel(
            summary_text.strip(),
            title="📈 Health Check Summary",
            border_style=health_color,
            padding=(1, 2)
        )
    
    async def check_all_accounts(self, include_options_chain: bool = False) -> Dict[str, Any]:
        """Check all configured accounts and endpoints in parallel
        
        Args:
            include_options_chain: If True, includes options chain processing (slow operation)
        """
        start_time = time.time()
        logger.info("🚀 Starting comprehensive health check for all accounts and endpoints")
        if not include_options_chain:
            logger.info("⚡ Options chain processing DISABLED (use --include-options-chain to enable)")
        
        # First check secrets configuration
        secrets_check = self.check_secrets_configuration()
        logger.info(f"🔐 Secrets configuration: {secrets_check['status']}")
        
        # Get all enabled accounts
        enabled_accounts = [
            account_id for account_id in self.pool.account_configs.keys()
            if self.pool.account_configs[account_id].enabled
        ]
        
        if not enabled_accounts:
            logger.warning("No enabled accounts found")
            return {
                "timestamp": datetime.now().isoformat(),
                "total_accounts": 0,
                "healthy_accounts": 0,
                "success_rate": "0%",
                "execution_time": time.time() - start_time,
                "accounts": {}
            }
        
        logger.info(f"Checking {len(enabled_accounts)} accounts in parallel...")
        parallel_start = time.time()
        
        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True
        ) as progress:
            task = progress.add_task("Running health checks...", total=len(enabled_accounts))
            
            # Run all account checks in parallel
            try:
                results = await asyncio.gather(
                    *[self.check_single_account(account_id, include_options_chain) for account_id in enabled_accounts],
                    return_exceptions=True
                )
                progress.update(task, completed=len(enabled_accounts))
                
                parallel_time = time.time() - parallel_start
                logger.info(f"⚡ Parallel execution completed in {parallel_time:.2f} seconds")
                
                # Process results
                self.results = {}
                healthy_count = 0
                
                for i, result in enumerate(results):
                    account_id = enabled_accounts[i]
                    
                    if isinstance(result, Exception):
                        logger.error(f"Failed to check account {account_id}: {result}")
                        self.results[account_id] = {
                            "account_id": account_id,
                            "overall_status": "CRITICAL",
                            "timestamp": datetime.now().isoformat(),
                            "error": f"Account check failed: {result}",
                            "basics": {"status": "ERROR", "error": str(result)},
                            "market_data": {"status": "ERROR", "error": str(result)},
                            "orders": {"status": "ERROR", "error": str(result)}
                        }
                    else:
                        self.results[account_id] = result
                        if result["overall_status"] == "HEALTHY":
                            healthy_count += 1
                            
            except Exception as e:
                logger.error(f"Critical error during parallel account checks: {e}")
                # Fallback to sequential processing
                return await self._fallback_sequential_check(enabled_accounts)
        
        # Overall summary
        total_accounts = len(self.results)
        total_time = time.time() - start_time
        
        logger.info(f"📊 Health Check Complete: {healthy_count}/{total_accounts} accounts healthy")
        logger.info(f"⏱️  Total execution time: {total_time:.2f} seconds ({total_time/total_accounts:.2f}s per account)")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_accounts": total_accounts,
            "healthy_accounts": healthy_count,
            "success_rate": f"{(healthy_count/total_accounts)*100:.1f}%" if total_accounts > 0 else "0%",
            "execution_time": total_time,
            "parallel_execution_time": parallel_time,
            "avg_time_per_account": total_time / total_accounts if total_accounts > 0 else 0,
            "performance_mode": "parallel",
            "secrets_configuration": secrets_check,
            "accounts": self.results
        }
    
    async def check_all_accounts_parallel(self, include_options_chain: bool = False) -> Dict[str, Any]:
        """Check all accounts using parallel trading approach for maximum speed"""
        start_time = time.time()
        logger.info("🚀 Starting PARALLEL health check for all accounts (maximum speed mode)")
        if not include_options_chain:
            logger.info("⚡ Options chain processing DISABLED (use --include-options-chain to enable)")
        
        # First check secrets configuration
        secrets_check = self.check_secrets_configuration()
        logger.info(f"🔐 Secrets configuration: {secrets_check['status']}")
        
        # Get all enabled accounts
        enabled_accounts = [
            account_id for account_id in self.pool.account_configs.keys()
            if self.pool.account_configs[account_id].enabled
        ]
        
        if not enabled_accounts:
            logger.warning("No enabled accounts found")
            return {
                "timestamp": datetime.now().isoformat(),
                "total_accounts": 0,
                "healthy_accounts": 0,
                "success_rate": "0%",
                "execution_time": time.time() - start_time,
                "accounts": {}
            }
        
        logger.info(f"Checking {len(enabled_accounts)} accounts with parallel trading...")
        
        # Run parallel trading check first (this is the bottleneck)
        trading_start = time.time()
        trading_results = await self.check_trading_endpoints_parallel(enabled_accounts)
        trading_time = time.time() - trading_start
        
        # Now run other checks in parallel (basics, stock endpoints, options if enabled)
        other_checks_start = time.time()
        
        async def check_account_other_endpoints(account_id: str) -> Dict[str, Any]:
            """Check non-trading endpoints for a single account"""
            try:
                tasks = [
                    self.check_account_basics(account_id),
                    self.check_stock_endpoints(account_id)
                ]
                
                if include_options_chain:
                    tasks.append(self.check_options_endpoints(account_id))
                else:
                    tasks.append(asyncio.create_task(self._get_disabled_options_result()))
                
                basics, stock_endpoints, options_endpoints = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Handle exceptions
                if isinstance(basics, Exception):
                    basics = {"status": "ERROR", "error": str(basics), "account_number": "N/A", 
                             "equity": 0, "buying_power": 0, "cash": 0, "positions_count": 0}
                if isinstance(stock_endpoints, Exception):
                    stock_endpoints = {"status": "ERROR", "error": str(stock_endpoints), "endpoints": {}}
                if isinstance(options_endpoints, Exception):
                    options_endpoints = {"status": "ERROR", "error": str(options_endpoints), 
                                       "endpoints": {}, "working_endpoints": 0, "total_endpoints": 0}
                
                # Get trading results for this account
                trading_result = trading_results["accounts"].get(account_id, {"status": "ERROR", "error": "No trading data"})
                
                # Determine overall status
                if basics["status"] == "ERROR":
                    overall_status = "CRITICAL"
                elif any(ep["status"] == "ERROR" for ep in [stock_endpoints, options_endpoints]) or trading_result["status"] == "ERROR":
                    overall_status = "DEGRADED"
                elif any(ep["status"] == "PARTIAL" for ep in [stock_endpoints, options_endpoints]) or trading_result["status"] == "PARTIAL":
                    overall_status = "PARTIAL"
                else:
                    overall_status = "HEALTHY"
                
                return {
                    "account_id": account_id,
                    "overall_status": overall_status,
                    "timestamp": datetime.now().isoformat(),
                    "basics": basics,
                    "stock_endpoints": stock_endpoints,
                    "options_endpoints": options_endpoints,
                    "trading_endpoints": {
                        "status": trading_result["status"],
                        "success_count": trading_result.get("success_count", 0),
                        "total_operations": trading_result.get("total_operations", 0),
                        "cancelled_orders": trading_result.get("cancelled_orders", 0)
                    }
                }
                
            except Exception as e:
                return {
                    "account_id": account_id,
                    "overall_status": "CRITICAL",
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Account check failed: {e}",
                    "basics": {"status": "ERROR", "error": str(e)},
                    "stock_endpoints": {"status": "ERROR", "error": str(e)},
                    "options_endpoints": {"status": "ERROR", "error": str(e)},
                    "trading_endpoints": {"status": "ERROR", "error": str(e)}
                }
        
        # Run other checks in parallel
        other_results = await asyncio.gather(
            *[check_account_other_endpoints(account_id) for account_id in enabled_accounts],
            return_exceptions=True
        )
        other_checks_time = time.time() - other_checks_start
        
        # Process results
        self.results = {}
        healthy_count = 0
        
        for result in other_results:
            if isinstance(result, Exception):
                logger.error(f"Account check failed: {result}")
                continue
                
            account_id = result["account_id"]
            self.results[account_id] = result
            
            if result["overall_status"] == "HEALTHY":
                healthy_count += 1
        
        # Overall summary
        total_accounts = len(self.results)
        total_time = time.time() - start_time
        
        logger.info(f"📊 PARALLEL Health Check Complete: {healthy_count}/{total_accounts} accounts healthy")
        logger.info(f"⏱️  Total execution time: {total_time:.2f} seconds")
        logger.info(f"   - Trading checks: {trading_time:.2f}s")
        logger.info(f"   - Other checks: {other_checks_time:.2f}s")
        logger.info(f"   - Speed improvement: ~{((12 * total_accounts) / total_time):.1f}x faster than sequential")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_accounts": total_accounts,
            "healthy_accounts": healthy_count,
            "success_rate": f"{(healthy_count/total_accounts)*100:.1f}%" if total_accounts > 0 else "0%",
            "execution_time": total_time,
            "trading_checks_time": trading_time,
            "other_checks_time": other_checks_time,
            "avg_time_per_account": total_time / total_accounts if total_accounts > 0 else 0,
            "performance_mode": "parallel_trading",
            "secrets_configuration": secrets_check,
            "accounts": self.results
        }
    
    async def _fallback_sequential_check(self, enabled_accounts: List[str]) -> Dict[str, Any]:
        """Fallback to sequential checking if parallel fails"""
        sequential_start = time.time()
        logger.warning("Falling back to sequential account checking")
        
        self.results = {}
        healthy_count = 0
        
        for account_id in enabled_accounts:
            try:
                result = await self.check_single_account(account_id)
                self.results[account_id] = result
                
                if result["overall_status"] == "HEALTHY":
                    healthy_count += 1
                    
            except Exception as e:
                logger.error(f"Sequential check failed for account {account_id}: {e}")
                self.results[account_id] = {
                    "account_id": account_id,
                    "overall_status": "CRITICAL",
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Sequential check failed: {e}",
                    "basics": {"status": "ERROR", "error": str(e)},
                    "market_data": {"status": "ERROR", "error": str(e)},
                    "orders": {"status": "ERROR", "error": str(e)}
                }
        
        total_accounts = len(self.results)
        sequential_time = time.time() - sequential_start
        
        logger.info(f"📊 Sequential Health Check Complete: {healthy_count}/{total_accounts} accounts healthy")
        logger.info(f"⏱️  Sequential execution time: {sequential_time:.2f} seconds ({sequential_time/total_accounts:.2f}s per account)")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_accounts": total_accounts,
            "healthy_accounts": healthy_count,
            "success_rate": f"{(healthy_count/total_accounts)*100:.1f}%" if total_accounts > 0 else "0%",
            "execution_time": sequential_time,
            "avg_time_per_account": sequential_time / total_accounts if total_accounts > 0 else 0,
            "performance_mode": "sequential_fallback",
            "accounts": self.results
        }
    
    async def check_specific_account(self, account_id: str, include_options_chain: bool = False) -> Dict[str, Any]:
        """Check a specific account"""
        if account_id not in self.pool.account_configs:
            logger.error(f"Account {account_id} not found in configuration")
            return {"error": f"Account {account_id} not configured"}
        
        if not self.pool.account_configs[account_id].enabled:
            logger.warning(f"Account {account_id} is disabled")
            return {"error": f"Account {account_id} is disabled"}
        
        return await self.check_single_account(account_id, include_options_chain)

async def main():
    """Main health check function
    
    Usage:
        python healthcheck.py                                    # Check all accounts (options chain disabled)
        python healthcheck.py --include-options-chain            # Check all accounts with options chain
        python healthcheck.py --parallel-trading                 # Check all accounts with parallel trading (FASTEST)
        python healthcheck.py --parallel-trading --include-options-chain  # Full parallel check with options
        python healthcheck.py account_id                         # Check specific account (options chain disabled)
        python healthcheck.py account_id --include-options-chain # Check specific account with options chain
        
    Performance Modes:
        Default: ~12 seconds per account (sequential trading operations)
        --parallel-trading: ~3-5 seconds per account (parallel trading operations)
        --include-options-chain: Adds ~3-4 seconds per account (options chain processing)
    """
    checker = HealthChecker()
    
    try:
        await checker.initialize()
        
        # Parse command line arguments
        include_options_chain = "--include-options-chain" in sys.argv
        use_parallel_trading = "--parallel-trading" in sys.argv
        
        # Check if specific account was requested
        if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
            account_id = sys.argv[1]
            logger.info(f"🎯 Running health check for specific account: {account_id}")
            result = await checker.check_specific_account(account_id, include_options_chain)
            print(f"\nResult: {result}")
        else:
            # Check all accounts
            if use_parallel_trading:
                logger.info("🚀 Using parallel trading approach for maximum speed")
                result = await checker.check_all_accounts_parallel(include_options_chain=include_options_chain)
            else:
                result = await checker.check_all_accounts(include_options_chain=include_options_chain)
            
            # Display secrets configuration panel
            secrets_config = result.get("secrets_configuration", {})
            if secrets_config:
                secrets_panel = checker._create_secrets_panel(secrets_config)
                checker.console.print(secrets_panel)
                checker.console.print()
            
            # Display Rich summary panel
            summary_panel = checker._create_summary_panel(result)
            checker.console.print(summary_panel)
            checker.console.print()
            
            # Display Rich health table
            health_table = checker._create_health_table(result["accounts"])
            checker.console.print(health_table)
            checker.console.print()
            
            # Display any issues in a separate panel
            issues = []
            for account_id, account_result in result["accounts"].items():
                if account_result["overall_status"] != "HEALTHY":
                    issue_text = f"[bold red]{account_id}:[/bold red] {account_result['overall_status']}"
                    
                    # Add specific endpoint errors
                    if account_result["basics"].get("error"):
                        issue_text += f"\n   Account Error: {account_result['basics']['error']}"
                    if account_result["stock_endpoints"].get("error"):
                        issue_text += f"\n   Stock APIs Error: {account_result['stock_endpoints']['error']}"
                    if account_result["options_endpoints"].get("error"):
                        issue_text += f"\n   Options APIs Error: {account_result['options_endpoints']['error']}"
                    if account_result["trading_endpoints"].get("error"):
                        issue_text += f"\n   Trading APIs Error: {account_result['trading_endpoints']['error']}"
                    
                    issues.append(issue_text)
            
            if issues:
                issues_panel = Panel(
                    "\n\n".join(issues),
                    title="⚠️ Issues Found",
                    border_style="red",
                    padding=(1, 2)
                )
                checker.console.print(issues_panel)
            else:
                success_panel = Panel(
                    "🎉 All accounts are healthy! No issues found.",
                    title="✅ Perfect Health",
                    border_style="green",
                    padding=(1, 2)
                )
                checker.console.print(success_panel)
        
        return 0
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)