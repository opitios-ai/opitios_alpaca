"""
Dashboard Calculator - Calculate trading history and profit reports from cached order data
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
from loguru import logger
import re


def _parse_option_symbol(symbol: str) -> bool:
    """Check if symbol is an option contract"""
    # Option symbols typically have format: SYMBOL[YY]MMDD[C/P]XXXXXXXX
    # e.g., AAPL240216C00190000
    if len(symbol) < 15:
        return False
    
    # Check if there's a date pattern followed by C/P
    for i, char in enumerate(symbol):
        if char.isdigit():
            # Found start of date, check if followed by 6 digits and C/P
            if i + 7 < len(symbol):
                date_part = symbol[i:i+6]
                option_type = symbol[i+6]
                if date_part.isdigit() and option_type.upper() in ['C', 'P']:
                    return True
            break
    return False


def calculate_trading_history_from_cache(cached_orders: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
    """
    Calculate trading history from cached orders
    
    Args:
        cached_orders: List of order dictionaries from WebSocket cache
        days: Number of days to include in history
        
    Returns:
        Dictionary with overall_profit, overall_commission, daily_summary, has_data
    """
    try:
        from datetime import timezone
        
        # Use timezone-aware datetime for comparison
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Group orders by date and calculate daily summaries
        daily_data = defaultdict(lambda: {
            'net_profit': 0.0,
            'sold_qty': 0,
            'commission': 0.0,
            'total_sold_value_for_avg': 0.0,
            'total_sold_value_usd': 0.0,
            'sell_orders': 0,
            'buy_orders': 0,
            'total_buy_value_usd': 0.0
        })
        
        overall_profit = 0.0
        overall_commission = 0.0
        
        # Track cost basis for each symbol to calculate realized P&L
        cost_basis_tracker = defaultdict(list)  # symbol -> [(qty, price, date), ...]
        
        # Filter and sort orders by filled_at time
        filled_orders = []
        for order in cached_orders:
            if order.get('status') == 'filled' and order.get('filled_at'):
                try:
                    # Parse filled_at date
                    filled_at_str = order.get('filled_at', '')
                    clean_date = re.sub(r'\s+(EDT|EST|PDT|PST|CDT|CST|MDT|MST|UTC|GMT)\s*$', '', filled_at_str.strip())
                    filled_at = datetime.fromisoformat(clean_date.replace(' ', 'T'))
                    
                    # Check if within date range
                    if start_date <= filled_at <= end_date:
                        order['_filled_at_parsed'] = filled_at
                        filled_orders.append(order)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse filled_at for order {order.get('order_id')}: {e}")
                    continue
        
        # Sort by filled time for FIFO processing
        filled_orders.sort(key=lambda x: x['_filled_at_parsed'])
        
        for order in filled_orders:
            filled_at = order['_filled_at_parsed']
            filled_date = filled_at.strftime('%Y-%m-%d')
            
            symbol = order.get('symbol', '')
            qty = float(order.get('filled_qty', 0))
            price = float(order.get('filled_avg_price', 0)) if order.get('filled_avg_price') else 0.0
            
            # Determine if this is an option
            asset_class = order.get('asset_class', '')
            is_option = 'option' in asset_class.lower() if asset_class else _parse_option_symbol(symbol)
            multiplier = 100 if is_option else 1
            
            side = order.get('side', '')
            
            if side == 'buy':
                # Track buy orders for cost basis calculation
                cost_basis_tracker[symbol].append((qty, price, filled_date))
                daily_data[filled_date]['buy_orders'] += 1
                daily_data[filled_date]['total_buy_value_usd'] += qty * price * multiplier
                
            elif side == 'sell' and price > 0:
                # Calculate realized P&L for sell orders
                daily_data[filled_date]['total_sold_value_for_avg'] += qty * price
                daily_data[filled_date]['total_sold_value_usd'] += qty * price * multiplier
                daily_data[filled_date]['sold_qty'] += int(qty)
                daily_data[filled_date]['sell_orders'] += 1
                
                # Calculate realized P&L using FIFO method
                remaining_qty = qty
                realized_pnl = 0.0
                
                # Process cost basis in FIFO order
                while remaining_qty > 0 and cost_basis_tracker[symbol]:
                    cost_qty, cost_price, cost_date = cost_basis_tracker[symbol][0]
                    
                    if cost_qty <= remaining_qty:
                        realized_pnl += cost_qty * (price - cost_price) * multiplier
                        remaining_qty -= cost_qty
                        cost_basis_tracker[symbol].pop(0)
                    else:
                        realized_pnl += remaining_qty * (price - cost_price) * multiplier
                        cost_basis_tracker[symbol][0] = (cost_qty - remaining_qty, cost_price, cost_date)
                        remaining_qty = 0
                
                daily_data[filled_date]['net_profit'] += realized_pnl
                overall_profit += realized_pnl
                
                # Estimate commission (Alpaca typically charges $0)
                estimated_commission = 0.0
                daily_data[filled_date]['commission'] += estimated_commission
                overall_commission += estimated_commission
        
        # Convert to daily summary format
        daily_summaries = []
        for date in sorted(daily_data.keys(), reverse=True):  # Most recent first
            data = daily_data[date]
            # Include days with any trading activity
            if data['sell_orders'] > 0 or data['buy_orders'] > 0:
                avg_sold_price = data['total_sold_value_for_avg'] / data['sold_qty'] if data['sold_qty'] > 0 else 0.0
                daily_summaries.append({
                    'date': date,
                    'net_profit': data['net_profit'],
                    'sold_qty': data['sold_qty'],
                    'commission': data['commission'],
                    'avg_sold_price': avg_sold_price
                })
        
        return {
            'overall_profit': overall_profit,
            'overall_commission': overall_commission,
            'daily_summary': daily_summaries,
            'has_data': len(daily_summaries) > 0
        }
        
    except Exception as e:
        logger.error(f"Error calculating trading history from cache: {e}")
        return {
            'overall_profit': 0.0,
            'overall_commission': 0.0,
            'daily_summary': [],
            'has_data': False,
            'error': str(e)
        }


def calculate_profit_report_from_cache(cached_orders: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
    """
    Calculate profit report from cached orders
    
    Args:
        cached_orders: List of order dictionaries from WebSocket cache
        days: Number of days to include in report
        
    Returns:
        Dictionary with daily, weekly, and total_for_chart profit data
    """
    try:
        # Get trading history data
        trading_history = calculate_trading_history_from_cache(cached_orders, days)
        
        if "error" in trading_history:
            return {
                "daily": {"profit": 0.0, "commission": 0.0, "has_data": False},
                "weekly": {"profit": 0.0, "commission": 0.0, "has_data": False},
                "total_for_chart": {
                    "overall_profit": 0.0,
                    "overall_commission": 0.0,
                    "daily_summary": [],
                    "has_data": False
                }
            }
        
        # Calculate daily profit (today's profit)
        today = datetime.now().strftime("%Y-%m-%d")
        daily_profit = 0.0
        daily_commission = 0.0
        daily_has_data = False
        
        if trading_history.get("daily_summary"):
            for daily in trading_history["daily_summary"]:
                if daily["date"] == today:
                    daily_profit = daily["net_profit"]
                    daily_commission = daily["commission"]
                    daily_has_data = True
                    break
        
        # Calculate weekly profit (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        weekly_profit = 0.0
        weekly_commission = 0.0
        weekly_has_data = False
        
        if trading_history.get("daily_summary"):
            for daily in trading_history["daily_summary"]:
                if daily["date"] >= week_ago:
                    weekly_profit += daily["net_profit"]
                    weekly_commission += daily["commission"]
                    weekly_has_data = True
        
        return {
            "daily": {
                "profit": daily_profit,
                "commission": daily_commission,
                "has_data": daily_has_data
            },
            "weekly": {
                "profit": weekly_profit,
                "commission": weekly_commission,
                "has_data": weekly_has_data
            },
            "total_for_chart": {
                "overall_profit": trading_history.get("overall_profit", 0.0),
                "overall_commission": trading_history.get("overall_commission", 0.0),
                "daily_summary": trading_history.get("daily_summary", []),
                "has_data": trading_history.get("has_data", False)
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating profit report from cache: {e}")
        return {
            "daily": {"profit": 0.0, "commission": 0.0, "has_data": False},
            "weekly": {"profit": 0.0, "commission": 0.0, "has_data": False},
            "total_for_chart": {
                "overall_profit": 0.0,
                "overall_commission": 0.0,
                "daily_summary": [],
                "has_data": False
            }
        }
