from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, OptionLatestQuoteRequest, OptionChainRequest
from alpaca.data.timeframe import TimeFrame
from config import settings
from loguru import logger
from typing import Optional, List, Dict, Any
import pandas as pd
import asyncio
from datetime import datetime, timedelta

class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str, paper_trading: bool = True):
        # Use provided credentials (required in clean architecture)
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper_trading = paper_trading
        self.base_url = "https://paper-api.alpaca.markets" if paper_trading else "https://api.alpaca.markets"
        
        # Validate credentials
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API credentials are required")
        
        # Initialize trading client
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper_trading
        )
        
        # Initialize data clients
        self.stock_data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        
        # Initialize options data client
        self.option_data_client = OptionHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Alpaca API"""
        try:
            account = self.trading_client.get_account()
            return {
                "status": "connected",
                "account_number": account.account_number,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value)
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

    # Stock Price Methods
    async def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """Get latest quote for a stock"""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self.stock_data_client.get_stock_latest_quote(request)
            
            if symbol in quotes:
                quote = quotes[symbol]
                return {
                    "symbol": symbol,
                    "bid_price": float(quote.bid_price) if quote.bid_price else None,
                    "ask_price": float(quote.ask_price) if quote.ask_price else None,
                    "bid_size": quote.bid_size,
                    "ask_size": quote.ask_size,
                    "timestamp": quote.timestamp
                }
            else:
                return {"error": f"No quote data found for {symbol}"}
                
        except Exception as e:
            logger.error(f"Error getting stock quote for {symbol}: {e}")
            return {"error": str(e)}

    async def get_multiple_stock_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get latest quotes for multiple stocks"""
        try:
            if not symbols or len(symbols) == 0:
                return {"error": "No symbols provided"}
            
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.stock_data_client.get_stock_latest_quote(request)
            
            results = []
            for symbol in symbols:
                if symbol in quotes:
                    quote = quotes[symbol]
                    results.append({
                        "symbol": symbol,
                        "bid_price": float(quote.bid_price) if quote.bid_price else None,
                        "ask_price": float(quote.ask_price) if quote.ask_price else None,
                        "bid_size": quote.bid_size,
                        "ask_size": quote.ask_size,
                        "timestamp": quote.timestamp
                    })
                else:
                    results.append({
                        "symbol": symbol,
                        "error": f"No quote data found for {symbol}"
                    })
            
            return {
                "quotes": results,
                "count": len(results),
                "requested_symbols": symbols
            }
                
        except Exception as e:
            logger.error(f"Error getting multiple stock quotes: {e}")
            return {"error": str(e)}

    async def get_stock_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100) -> Dict[str, Any]:
        """Get historical price bars for a stock"""
        try:
            # Convert timeframe string to TimeFrame enum
            tf_map = {
                "1Min": TimeFrame.Minute,
                "5Min": TimeFrame.Minute,  # Simplified for now
                "15Min": TimeFrame.Minute,  # Simplified for now  
                "1Hour": TimeFrame.Hour,
                "1Day": TimeFrame.Day
            }
            
            timeframe_obj = tf_map.get(timeframe, TimeFrame.Day)
            
            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=timeframe_obj,
                limit=limit
            )
            
            bars = self.stock_data_client.get_stock_bars(request)
            
            if symbol in bars:
                bars_data = []
                for bar in bars[symbol]:
                    bars_data.append({
                        "timestamp": bar.timestamp,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": bar.volume
                    })
                
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bars": bars_data
                }
            else:
                return {"error": f"No bar data found for {symbol}"}
                
        except Exception as e:
            logger.error(f"Error getting stock bars for {symbol}: {e}")
            return {"error": str(e)}

    # Options Methods
    async def get_options_chain(self, underlying_symbol: str, expiration_date: Optional[str] = None) -> Dict[str, Any]:
        """Get options chain for an underlying symbol using only real Alpaca market data"""
        try:
            # Use real Alpaca options chain API
            request = OptionChainRequest(underlying_symbol=underlying_symbol)
            chain = self.option_data_client.get_option_chain(request)
            
            if chain and hasattr(chain, 'option_contracts'):
                options_data = []
                exp_dates = set()
                quote_failures = 0
                
                for contract in chain.option_contracts:
                    # Filter by expiration date if specified
                    if expiration_date and str(contract.expiration_date) != expiration_date:
                        continue
                        
                    exp_dates.add(str(contract.expiration_date))
                    
                    option_data = {
                        "symbol": contract.symbol,
                        "underlying_symbol": underlying_symbol,
                        "strike_price": float(contract.strike_price),
                        "expiration_date": str(contract.expiration_date),
                        "option_type": contract.style.value.lower() if hasattr(contract, 'style') else "unknown"
                    }
                    
                    # Try to get real quote data for each contract
                    try:
                        quote_data = await self.get_option_quote(contract.symbol)
                        if "error" not in quote_data:
                            option_data.update({
                                "bid_price": quote_data.get("bid_price"),
                                "ask_price": quote_data.get("ask_price"),
                                "bid_size": quote_data.get("bid_size"),
                                "ask_size": quote_data.get("ask_size"),
                                "last_price": quote_data.get("last_price"),
                                "implied_volatility": quote_data.get("implied_volatility")
                            })
                        else:
                            quote_failures += 1
                            logger.warning(f"No real quote data available for option {contract.symbol}")
                    except Exception as quote_error:
                        quote_failures += 1
                        logger.warning(f"Failed to get quote for option {contract.symbol}: {quote_error}")
                    
                    options_data.append(option_data)
                
                # Get current stock price for reference
                stock_quote = await self.get_stock_quote(underlying_symbol)
                current_price = None
                if "error" not in stock_quote:
                    current_price = stock_quote.get("ask_price") or stock_quote.get("bid_price")
                else:
                    logger.warning(f"Could not get current stock price for {underlying_symbol}")
                
                logger.info(f"Options chain for {underlying_symbol}: {len(options_data)} contracts, {quote_failures} quote failures")
                
                return {
                    "underlying_symbol": underlying_symbol,
                    "underlying_price": current_price,
                    "expiration_dates": sorted(list(exp_dates)),
                    "options_count": len(options_data),
                    "quote_failures": quote_failures,
                    "options": options_data[:100]  # Limit results for performance
                }
            else:
                logger.error(f"No options chain contracts found for {underlying_symbol}")
                return {"error": f"No real options chain data available for {underlying_symbol}"}
            
        except Exception as e:
            logger.error(f"Error getting options chain for {underlying_symbol}: {e}")
            return {"error": f"Failed to retrieve real options chain data for {underlying_symbol}: {str(e)}"}

    async def get_option_quote(self, option_symbol: str) -> Dict[str, Any]:
        """Get quote for a specific option contract using only real Alpaca market data"""
        try:
            # Get real Alpaca options data only
            request = OptionLatestQuoteRequest(symbol_or_symbols=[option_symbol])
            quotes = self.option_data_client.get_option_latest_quote(request)
            
            if quotes and option_symbol in quotes:
                quote = quotes[option_symbol]
                
                # Parse option symbol to get components
                underlying, strike_price, exp_date, option_type = self._parse_option_symbol(option_symbol)
                
                # Validate that we have valid option data
                if not underlying or not strike_price or not option_type:
                    logger.error(f"Failed to parse option symbol: {option_symbol}")
                    return {"error": f"Invalid option symbol format: {option_symbol}"}
                
                return {
                    "symbol": option_symbol,
                    "underlying_symbol": underlying,
                    "strike_price": strike_price,
                    "expiration_date": exp_date,
                    "option_type": option_type,
                    "bid_price": float(quote.bid_price) if quote.bid_price else None,
                    "ask_price": float(quote.ask_price) if quote.ask_price else None,
                    "bid_size": quote.bid_size if hasattr(quote, 'bid_size') else None,
                    "ask_size": quote.ask_size if hasattr(quote, 'ask_size') else None,
                    "last_price": float(quote.last_price) if hasattr(quote, 'last_price') and quote.last_price else None,
                    "implied_volatility": float(quote.implied_volatility) if hasattr(quote, 'implied_volatility') and quote.implied_volatility else None,
                    "timestamp": quote.timestamp
                }
            else:
                logger.warning(f"No real options data available for {option_symbol}")
                return {"error": f"No real market data available for option symbol: {option_symbol}"}
                
        except Exception as e:
            logger.error(f"Error getting option quote for {option_symbol}: {e}")
            return {"error": f"Failed to retrieve real option data for {option_symbol}: {str(e)}"}
    
    def _validate_option_symbol(self, option_symbol: str) -> bool:
        """Validate option symbol format for trading"""
        try:
            # Option symbol format: SYMBOL[YY]MMDD[C/P]XXXXXXXX
            # Example: AAPL240216C00190000
            
            if len(option_symbol) < 15:  # Minimum length check
                return False
            
            # Find where the date starts by looking for the first digit after letters
            underlying = ""
            date_start_idx = 0
            
            for i, char in enumerate(option_symbol):
                if char.isdigit():
                    underlying = option_symbol[:i]
                    date_start_idx = i
                    break
            
            if not underlying or date_start_idx == 0:
                return False
            
            if len(option_symbol) < date_start_idx + 9:  # Need at least YYMMDD + C/P + price
                return False
                
            date_part = option_symbol[date_start_idx:date_start_idx+6]
            option_type_char = option_symbol[date_start_idx+6]
            strike_part = option_symbol[date_start_idx+7:]
            
            # Validate date part (6 digits)
            if not date_part.isdigit() or len(date_part) != 6:
                return False
            
            # Validate option type (C or P)
            if option_type_char.upper() not in ['C', 'P']:
                return False
            
            # Validate strike price part (8 digits)
            if not strike_part.isdigit() or len(strike_part) != 8:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating option symbol {option_symbol}: {e}")
            return False

    def _parse_option_symbol(self, option_symbol: str):
        """Parse option symbol to extract components for real data validation"""
        try:
            # Find where the date starts by looking for the first digit after letters
            underlying = ""
            date_start_idx = 0
            
            for i, char in enumerate(option_symbol):
                if char.isdigit():
                    underlying = option_symbol[:i]
                    date_start_idx = i
                    break
            
            if not underlying or date_start_idx == 0:
                logger.error(f"No underlying symbol found in: {option_symbol}")
                return None, None, None, None
            
            if len(option_symbol) < date_start_idx + 7:
                logger.error(f"Option symbol too short: {option_symbol}")
                return None, None, None, None
                
            date_part = option_symbol[date_start_idx:date_start_idx+6]
            option_type_char = option_symbol[date_start_idx+6]
            strike_part = option_symbol[date_start_idx+7:]
            
            strike_price = float(strike_part) / 1000
            exp_date = f"20{date_part[:2]}-{date_part[2:4]}-{date_part[4:6]}"
            option_type = "call" if option_type_char.upper() == 'C' else "put"
            
            return underlying, strike_price, exp_date, option_type
            
        except Exception as e:
            logger.error(f"Error parsing option symbol {option_symbol}: {e}")
            return None, None, None, None

    async def get_multiple_option_quotes(self, option_symbols: List[str]) -> Dict[str, Any]:
        """Get quotes for multiple option contracts using only real Alpaca market data"""
        try:
            if not option_symbols or len(option_symbols) == 0:
                logger.error("No option symbols provided for batch quote request")
                return {"error": "No option symbols provided"}
            
            results = []
            successful_quotes = 0
            failed_symbols = []
            
            for symbol in option_symbols:
                quote = await self.get_option_quote(symbol)
                if "error" in quote:
                    failed_symbols.append(symbol)
                    logger.warning(f"Failed to get real data for option {symbol}: {quote['error']}")
                else:
                    successful_quotes += 1
                results.append(quote)
            
            # Log summary of results
            logger.info(f"Option quotes batch request: {successful_quotes}/{len(option_symbols)} successful")
            if failed_symbols:
                logger.warning(f"Failed option symbols: {failed_symbols}")
            
            return {
                "quotes": results,
                "count": len(results),  
                "successful_count": successful_quotes,
                "failed_count": len(failed_symbols),
                "requested_symbols": option_symbols,
                "failed_symbols": failed_symbols if failed_symbols else None
            }
            
        except Exception as e:
            logger.error(f"Error getting multiple option quotes: {e}")
            return {"error": f"Failed to process batch option quotes request: {str(e)}"}

    # Trading Methods
    async def place_stock_order(self, symbol: str, qty: float, side: str, order_type: str = "market", 
                              limit_price: Optional[float] = None, stop_price: Optional[float] = None,
                              time_in_force: str = "day") -> Dict[str, Any]:
        """Place a stock order"""
        try:
            # Convert string parameters to Alpaca enums
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif = TimeInForce.DAY if time_in_force.lower() == "day" else TimeInForce.GTC
            
            # Create order request based on type
            if order_type.lower() == "market":
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif
                )
            elif order_type.lower() == "limit" and limit_price:
                order_data = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif,
                    limit_price=limit_price
                )
            elif order_type.lower() == "stop" and stop_price:
                order_data = StopOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif,
                    stop_price=stop_price
                )
            else:
                return {"error": "Invalid order type or missing required price parameters"}
            
            # Submit order
            price_info = f" at ${limit_price}" if limit_price else f" at ${stop_price} (stop)" if stop_price else ""
            logger.info(f"Placing stock order: {symbol} x{qty} {side.upper()} {order_type.upper()}{price_info}")
            order = self.trading_client.submit_order(order_data)
            
            order_result = {
                "id": str(order.id),  # 确保ID是字符串类型
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "status": order.status.value,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at
            }
            
            # 详细的成功日志
            price_str = f" at ${limit_price}" if limit_price else f" at ${stop_price} (stop)" if stop_price else ""
            logger.info(f"✅ Stock order placed successfully: {order_result['symbol']} x{order_result['qty']} {order_result['side'].upper()}{price_str} | Order ID: {order_result['id']} | Status: {order_result['status']}")
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error placing stock order: {e}")
            return {"error": str(e)}

    async def place_option_order(self, option_symbol: str, qty: int, side: str, order_type: str = "market",
                               limit_price: Optional[float] = None, time_in_force: str = "day") -> Dict[str, Any]:
        """Place an options order using Alpaca's options trading API"""
        try:
            # Convert string parameters to Alpaca enums
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            tif = TimeInForce.DAY if time_in_force.lower() == "day" else TimeInForce.GTC
            
            # Validate option symbol format (e.g., AAPL240216C00190000)
            if not self._validate_option_symbol(option_symbol):
                return {"error": f"Invalid option symbol format: {option_symbol}. Expected format: SYMBOL[YY]MMDD[C/P]XXXXXXXX"}
            
            # Create option order request based on type
            # Note: For options, we don't need to specify AssetClass explicitly
            # Alpaca automatically detects options based on the symbol format
            if order_type.lower() == "market":
                order_data = MarketOrderRequest(
                    symbol=option_symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif
                )
            elif order_type.lower() == "limit" and limit_price:
                order_data = LimitOrderRequest(
                    symbol=option_symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif,
                    limit_price=limit_price
                )
            else:
                return {"error": "Invalid order type or missing required price parameters for options"}
            
            # Submit option order
            price_info = f" at ${limit_price}" if limit_price else ""
            logger.info(f"Placing option order: {option_symbol} x{qty} {side.upper()} {order_type.upper()}{price_info}")
            order = self.trading_client.submit_order(order_data)
            
            # 详细的成功日志
            order_result = {
                "id": str(order.id),  # 确保ID是字符串类型
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side.value,
                "order_type": order.order_type.value,
                "status": order.status.value,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at,
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "asset_class": "option"
            }
            
            # 详细的成功日志
            price_str = f" at ${limit_price}" if limit_price else ""
            logger.info(f"✅ Option order placed successfully: {order.symbol} x{order_result['qty']} {order_result['side'].upper()}{price_str} | Order ID: {order_result['id']} | Status: {order_result['status']}")
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error placing option order for {option_symbol}: {e}")
            return {"error": str(e)}

    # Account and Position Methods
    async def get_account(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            account = self.trading_client.get_account()
            return {
                "account_number": account.account_number,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "last_equity": float(account.last_equity),
                "multiplier": account.multiplier,
                "pattern_day_trader": account.pattern_day_trader
            }
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {"error": str(e)}

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions"""
        try:
            positions = self.trading_client.get_all_positions()
            position_list = []
            
            for position in positions:
                position_list.append({
                    "symbol": position.symbol,
                    "qty": float(position.qty),
                    "side": position.side.value,
                    "market_value": float(position.market_value) if position.market_value else None,
                    "cost_basis": float(position.cost_basis) if position.cost_basis else None,
                    "unrealized_pl": float(position.unrealized_pl) if position.unrealized_pl else None,
                    "unrealized_plpc": float(position.unrealized_plpc) if position.unrealized_plpc else None,
                    "avg_entry_price": float(position.avg_entry_price) if position.avg_entry_price else None
                })
            
            return position_list
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return [{"error": str(e)}]

    async def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders"""
        try:
            request = GetOrdersRequest(limit=limit)
            orders = self.trading_client.get_orders(request)
            
            order_list = []
            for order in orders:
                if status is None or order.status.value == status:
                    order_list.append({
                        "id": str(order.id),  # 确保ID是字符串类型
                        "symbol": order.symbol,
                        "qty": float(order.qty),
                        "side": order.side.value,
                        "order_type": order.order_type.value,
                        "status": order.status.value,
                        "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                        "submitted_at": order.submitted_at,
                        "filled_at": order.filled_at,
                        "limit_price": float(order.limit_price) if order.limit_price else None,
                        "stop_price": float(order.stop_price) if order.stop_price else None
                    })
            
            return order_list
            
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return [{"error": str(e)}]

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return {"status": "cancelled", "order_id": order_id}
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return {"error": str(e)}


class PooledAlpacaClient:
    """使用连接池的Alpaca客户端"""
    
    def __init__(self):
        # 延迟加载连接池以避免循环导入
        self._pool = None
    
    @property
    def pool(self):
        """获取连接池实例"""
        if self._pool is None:
            from app.account_pool import get_account_pool
            self._pool = get_account_pool()
        return self._pool
    
    async def _get_client_with_routing(self, account_id: Optional[str] = None, routing_key: Optional[str] = None):
        """获取路由后的客户端连接"""
        connection = await self.pool.get_connection(account_id, routing_key)
        return connection
    
    async def get_stock_quote(self, symbol: str, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取股票报价 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or symbol) as connection:
            return await connection.alpaca_client.get_stock_quote(symbol)
    
    async def get_multiple_stock_quotes(self, symbols: List[str], account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取多个股票报价 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or symbols[0] if symbols else None) as connection:
            return await connection.alpaca_client.get_multiple_stock_quotes(symbols)
    
    async def get_stock_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100, 
                           account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取股票K线数据 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or symbol) as connection:
            return await connection.alpaca_client.get_stock_bars(symbol, timeframe, limit)
    
    async def get_options_chain(self, underlying_symbol: str, expiration_date: Optional[str] = None,
                              account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取期权链 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or underlying_symbol) as connection:
            return await connection.alpaca_client.get_options_chain(underlying_symbol, expiration_date)
    
    async def get_option_quote(self, option_symbol: str, account_id: Optional[str] = None, 
                             routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取期权报价 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or option_symbol) as connection:
            return await connection.alpaca_client.get_option_quote(option_symbol)
    
    async def get_multiple_option_quotes(self, option_symbols: List[str], account_id: Optional[str] = None,
                                       routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取多个期权报价 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or option_symbols[0] if option_symbols else None) as connection:
            return await connection.alpaca_client.get_multiple_option_quotes(option_symbols)
    
    async def place_stock_order(self, symbol: str, qty: float, side: str, order_type: str = "market", 
                              limit_price: Optional[float] = None, stop_price: Optional[float] = None,
                              time_in_force: str = "day", account_id: Optional[str] = None, 
                              routing_key: Optional[str] = None) -> Dict[str, Any]:
        """下股票订单 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or symbol) as connection:
            return await connection.alpaca_client.place_stock_order(
                symbol, qty, side, order_type, limit_price, stop_price, time_in_force
            )
    
    async def place_option_order(self, option_symbol: str, qty: int, side: str, order_type: str = "market",
                               limit_price: Optional[float] = None, time_in_force: str = "day",
                               account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """下期权订单 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key or option_symbol) as connection:
            return await connection.alpaca_client.place_option_order(
                option_symbol, qty, side, order_type, limit_price, time_in_force
            )
    
    async def get_account(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """获取账户信息 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key) as connection:
            return await connection.alpaca_client.get_account()
    
    async def get_positions(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取持仓信息 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key) as connection:
            return await connection.alpaca_client.get_positions()
    
    async def get_orders(self, status: Optional[str] = None, limit: int = 100,
                       account_id: Optional[str] = None, routing_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取订单信息 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key) as connection:
            return await connection.alpaca_client.get_orders(status, limit)
    
    async def cancel_order(self, order_id: str, account_id: Optional[str] = None, 
                         routing_key: Optional[str] = None) -> Dict[str, Any]:
        """取消订单 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key) as connection:
            return await connection.alpaca_client.cancel_order(order_id)
    
    async def bulk_place_stock_order(self, symbol: str, qty: float, side: str, order_type: str = "market", 
                                   limit_price: Optional[float] = None, stop_price: Optional[float] = None,
                                   time_in_force: str = "day") -> Dict[str, Any]:
        """为所有账户批量下股票订单"""
        from app.models import BulkOrderResult
        
        # 获取所有可用账户
        pool_stats = self.pool.get_pool_stats()
        account_stats = pool_stats.get("account_stats", {})
        
        results = []
        successful_orders = 0
        failed_orders = 0
        
        logger.info(f"Starting bulk stock order for {len(account_stats)} accounts: {symbol} {qty} {side}")
        
        # 为每个账户下单
        for account_id, stats in account_stats.items():
            account_name = stats.get("account_name")
            
            try:
                # 使用指定账户下单
                order_result = await self.place_stock_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    time_in_force=time_in_force,
                    account_id=account_id
                )
                
                if "error" in order_result:
                    failed_orders += 1
                    results.append(BulkOrderResult(
                        account_id=account_id,
                        account_name=account_name,
                        success=False,
                        error=order_result["error"]
                    ))
                    logger.warning(f"Failed to place order for account {account_id}: {order_result['error']}")
                else:
                    successful_orders += 1
                    from app.models import OrderResponse
                    
                    # 确保ID是字符串类型（Alpaca可能返回UUID对象）
                    if 'id' in order_result and order_result['id'] is not None:
                        order_result['id'] = str(order_result['id'])
                    
                    results.append(BulkOrderResult(
                        account_id=account_id,
                        account_name=account_name,
                        success=True,
                        order=OrderResponse(**order_result)
                    ))
                    
                    # 详细的成功日志
                    price_str = f" at ${order_result.get('limit_price')}" if order_result.get('limit_price') else f" at ${order_result.get('stop_price')} (stop)" if order_result.get('stop_price') else ""
                    logger.info(f"✅ Stock order placed for {account_name}: {order_result['symbol']} x{order_result['qty']} {order_result['side'].upper()}{price_str} | Order ID: {order_result['id']}")
                    
                    # 发送Discord通知
                    try:
                        from app.discord_notifier import send_trade_notification
                        asyncio.create_task(send_trade_notification(order_result, account_name, is_bulk=True))
                    except Exception as e:
                        logger.warning(f"Failed to send Discord notification: {e}")
                    
            except Exception as e:
                failed_orders += 1
                error_msg = str(e)
                results.append(BulkOrderResult(
                    account_id=account_id,
                    account_name=account_name,
                    success=False,
                    error=error_msg
                ))
                logger.error(f"Exception placing order for account {account_id}: {error_msg}")
        
        logger.info(f"Bulk stock order completed: {successful_orders} successful, {failed_orders} failed")
        
        # 发送批量交易汇总通知
        if successful_orders > 0:
            try:
                from app.discord_notifier import send_bulk_trade_summary
                asyncio.create_task(send_bulk_trade_summary(
                    [r.dict() for r in results], symbol, qty, side, "stock"
                ))
            except Exception as e:
                logger.warning(f"Failed to send Discord bulk summary: {e}")
        
        return {
            "bulk_place": True,
            "total_accounts": len(account_stats),
            "successful_orders": successful_orders,
            "failed_orders": failed_orders,
            "results": results
        }
    
    async def bulk_place_option_order(self, option_symbol: str, qty: int, side: str, order_type: str = "market",
                                    limit_price: Optional[float] = None, time_in_force: str = "day") -> Dict[str, Any]:
        """为所有账户批量下期权订单"""
        from app.models import BulkOrderResult
        
        # 获取所有可用账户
        pool_stats = self.pool.get_pool_stats()
        account_stats = pool_stats.get("account_stats", {})
        
        results = []
        successful_orders = 0
        failed_orders = 0
        
        logger.info(f"Starting bulk option order for {len(account_stats)} accounts: {option_symbol} {qty} {side}")
        
        # 为每个账户下单
        for account_id, stats in account_stats.items():
            account_name = stats.get("account_name")
            
            try:
                # 使用指定账户下单
                order_result = await self.place_option_order(
                    option_symbol=option_symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type,
                    limit_price=limit_price,
                    time_in_force=time_in_force,
                    account_id=account_id
                )
                
                if "error" in order_result:
                    failed_orders += 1
                    results.append(BulkOrderResult(
                        account_id=account_id,
                        account_name=account_name,
                        success=False,
                        error=order_result["error"]
                    ))
                    logger.warning(f"Failed to place option order for account {account_id}: {order_result['error']}")
                else:
                    successful_orders += 1
                    from app.models import OrderResponse
                    
                    # 确保ID是字符串类型（Alpaca可能返回UUID对象）
                    if 'id' in order_result and order_result['id'] is not None:
                        order_result['id'] = str(order_result['id'])
                    
                    results.append(BulkOrderResult(
                        account_id=account_id,
                        account_name=account_name,
                        success=True,
                        order=OrderResponse(**order_result)
                    ))
                    
                    # 详细的成功日志
                    price_str = f" at ${order_result.get('limit_price')}" if order_result.get('limit_price') else ""
                    logger.info(f"✅ Option order placed for {account_name}: {order_result['symbol']} x{order_result['qty']} {order_result['side'].upper()}{price_str} | Order ID: {order_result['id']}")
                    
                    # 发送Discord通知
                    try:
                        from app.discord_notifier import send_trade_notification
                        asyncio.create_task(send_trade_notification(order_result, account_name, is_bulk=True))
                    except Exception as e:
                        logger.warning(f"Failed to send Discord notification: {e}")
                    
            except Exception as e:
                failed_orders += 1
                error_msg = str(e)
                results.append(BulkOrderResult(
                    account_id=account_id,
                    account_name=account_name,
                    success=False,
                    error=error_msg
                ))
                logger.error(f"Exception placing option order for account {account_id}: {error_msg}")
        
        logger.info(f"Bulk option order completed: {successful_orders} successful, {failed_orders} failed")
        
        return {
            "bulk_place": True,
            "total_accounts": len(account_stats),
            "successful_orders": successful_orders,
            "failed_orders": failed_orders,
            "results": results
        }
    
    async def test_connection(self, account_id: Optional[str] = None, routing_key: Optional[str] = None) -> Dict[str, Any]:
        """测试连接 - 使用连接池"""
        async with self.pool.get_account_connection(account_id, routing_key) as connection:
            return await connection.alpaca_client.test_connection()


# 全局连接池客户端实例
pooled_client = PooledAlpacaClient()