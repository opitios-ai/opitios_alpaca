#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Comprehensive Health Check for Alpaca Trading Service
Tests all accounts with real trading operations to ensure everything works.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.account_pool import AccountPool
from app.alpaca_client import pooled_client
from loguru import logger

class HealthChecker:
    """Comprehensive health checker for all trading accounts"""
    
    def __init__(self):
        self.pool = None
        self.results = {}
        
    async def initialize(self):
        """Initialize account pool"""
        self.pool = AccountPool()
        await self.pool.initialize()
        logger.info(f"Health checker initialized with {len(self.pool.account_configs)} accounts")
    
    async def check_account_basics(self, account_id: str) -> Dict[str, Any]:
        """Check basic account info and assets"""
        try:
            account_data = await pooled_client.get_account(account_id=account_id)
            positions = await pooled_client.get_positions(account_id=account_id)
            
            return {
                "status": "HEALTHY",
                "account_number": account_data.get("account_number", "N/A"),
                "equity": float(account_data.get("equity", 0)),
                "buying_power": float(account_data.get("buying_power", 0)),
                "cash": float(account_data.get("cash", 0)),
                "positions_count": len(positions) if positions else 0,
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
    
    async def check_market_data(self, account_id: str) -> Dict[str, Any]:
        """Check market data access"""
        try:
            # Test stock quote
            quote = await pooled_client.get_stock_quote("AAPL", account_id=account_id)
            
            # Test batch quotes
            batch_quotes = await pooled_client.get_multiple_stock_quotes(
                ["AAPL", "TSLA"], account_id=account_id
            )
            
            return {
                "status": "HEALTHY",
                "stock_quote_working": bool(quote),
                "batch_quotes_working": bool(batch_quotes),
                "aapl_price": quote.get("bid", "N/A") if quote else "N/A",
                "error": None
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "stock_quote_working": False,
                "batch_quotes_working": False,
                "aapl_price": "N/A"
            }
    
    async def check_order_operations(self, account_id: str) -> Dict[str, Any]:
        """Check order placement and cancellation (paper trading only)"""
        try:
            # Test order placement (small amount for paper trading)
            order_result = await pooled_client.place_stock_order(
                symbol="AAPL",
                qty=1,
                side="buy",
                order_type="market",
                account_id=account_id
            )
            
            if order_result and "id" in order_result:
                order_id = order_result["id"]
                
                # Test order cancellation
                cancel_result = await pooled_client.cancel_order(
                    order_id=order_id,
                    account_id=account_id
                )
                
                return {
                    "status": "HEALTHY", 
                    "order_placement_working": True,
                    "order_cancellation_working": bool(cancel_result),
                    "test_order_id": order_id,
                    "error": None
                }
            else:
                return {
                    "status": "WARNING",
                    "order_placement_working": False,
                    "order_cancellation_working": False,
                    "test_order_id": "N/A",
                    "error": "Order placement failed"
                }
                
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "order_placement_working": False,
                "order_cancellation_working": False,
                "test_order_id": "N/A"
            }
    
    async def check_single_account(self, account_id: str) -> Dict[str, Any]:
        """Comprehensive check for a single account"""
        logger.info(f"🔍 Checking account: {account_id}")
        
        # Run all checks
        basics = await self.check_account_basics(account_id)
        market_data = await self.check_market_data(account_id)
        orders = await self.check_order_operations(account_id)
        
        # Determine overall status
        if basics["status"] == "ERROR":
            overall_status = "CRITICAL"
        elif market_data["status"] == "ERROR" or orders["status"] == "ERROR":
            overall_status = "DEGRADED"
        elif orders["status"] == "WARNING":
            overall_status = "PARTIAL"
        else:
            overall_status = "HEALTHY"
        
        result = {
            "account_id": account_id,
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "basics": basics,
            "market_data": market_data,
            "orders": orders
        }
        
        # Log one-line summary as requested
        self._log_account_summary(account_id, result)
        
        return result
    
    def _log_account_summary(self, account_id: str, result: Dict[str, Any]):
        """Log condensed one-line account summary"""
        basics = result["basics"]
        market_data = result["market_data"]
        orders = result["orders"]
        
        status_emoji = {
            "HEALTHY": "✅",
            "PARTIAL": "⚠️", 
            "DEGRADED": "🔶",
            "CRITICAL": "❌"
        }
        
        emoji = status_emoji.get(result["overall_status"], "❓")
        
        summary = (
            f"{emoji} {account_id}: {result['overall_status']} | "
            f"Account#{basics['account_number']} | "
            f"Equity=${basics['equity']:,.2f} | "
            f"Cash=${basics['cash']:,.2f} | "
            f"Positions={basics['positions_count']} | "
            f"AAPL=${market_data['aapl_price']} | "
            f"Orders={'OK' if orders['order_placement_working'] else 'FAIL'}"
        )
        
        if result["overall_status"] == "HEALTHY":
            logger.info(summary)
        elif result["overall_status"] in ["PARTIAL", "DEGRADED"]:
            logger.warning(summary)
        else:
            logger.error(summary)
    
    async def check_all_accounts(self) -> Dict[str, Any]:
        """Check all configured accounts"""
        logger.info("🚀 Starting comprehensive health check for all accounts")
        
        self.results = {}
        healthy_count = 0
        
        for account_id in self.pool.account_configs.keys():
            if self.pool.account_configs[account_id].enabled:
                result = await self.check_single_account(account_id)
                self.results[account_id] = result
                
                if result["overall_status"] == "HEALTHY":
                    healthy_count += 1
        
        # Overall summary
        total_accounts = len(self.results)
        logger.info(f"📊 Health Check Complete: {healthy_count}/{total_accounts} accounts healthy")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_accounts": total_accounts,
            "healthy_accounts": healthy_count,
            "success_rate": f"{(healthy_count/total_accounts)*100:.1f}%" if total_accounts > 0 else "0%",
            "accounts": self.results
        }
    
    async def check_specific_account(self, account_id: str) -> Dict[str, Any]:
        """Check a specific account"""
        if account_id not in self.pool.account_configs:
            logger.error(f"Account {account_id} not found in configuration")
            return {"error": f"Account {account_id} not configured"}
        
        if not self.pool.account_configs[account_id].enabled:
            logger.warning(f"Account {account_id} is disabled")
            return {"error": f"Account {account_id} is disabled"}
        
        return await self.check_single_account(account_id)

async def main():
    """Main health check function"""
    checker = HealthChecker()
    
    try:
        await checker.initialize()
        
        # Check if specific account was requested
        if len(sys.argv) > 1:
            account_id = sys.argv[1]
            logger.info(f"🎯 Running health check for specific account: {account_id}")
            result = await checker.check_specific_account(account_id)
            print(f"\nResult: {result}")
        else:
            # Check all accounts
            result = await checker.check_all_accounts()
            
            # Print summary (ASCII safe for Windows encoding)
            print(f"\n** Health Check Summary:")
            print(f"   Total Accounts: {result['total_accounts']}")
            print(f"   Healthy: {result['healthy_accounts']}")
            print(f"   Success Rate: {result['success_rate']}")
            
            # Print any issues
            for account_id, account_result in result["accounts"].items():
                if account_result["overall_status"] != "HEALTHY":
                    print(f"   WARNING: {account_id}: {account_result['overall_status']}")
                    if account_result["basics"].get("error"):
                        print(f"      Basic Error: {account_result['basics']['error']}")
                    if account_result["market_data"].get("error"):
                        print(f"      Market Data Error: {account_result['market_data']['error']}")
                    if account_result["orders"].get("error"):
                        print(f"      Orders Error: {account_result['orders']['error']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)