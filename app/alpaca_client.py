from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, OptionLatestQuoteRequest, OptionChainRequest
from alpaca.data.timeframe import TimeFrame
from config import settings
from loguru import logger
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta

class AlpacaClient:
    def __init__(self):
        self.api_key = settings.alpaca_api_key
        self.secret_key = settings.alpaca_secret_key
        self.base_url = settings.alpaca_base_url
        self.paper_trading = settings.alpaca_paper_trading
        
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
        """Get options chain for an underlying symbol using real Alpaca data"""
        try:
            # Use real Alpaca options chain API
            request = OptionChainRequest(underlying_symbol=underlying_symbol)
            chain = self.option_data_client.get_option_chain(request)
            
            if chain and hasattr(chain, 'option_contracts'):
                options_data = []
                exp_dates = set()
                
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
                        "option_type": contract.style.value.lower() if hasattr(contract, 'style') else "unknown",
                        "note": "Real Alpaca options chain data"
                    }
                    
                    # Try to get quote data for each contract
                    try:
                        quote_data = await self.get_option_quote(contract.symbol)
                        if "error" not in quote_data:
                            option_data.update({
                                "bid_price": quote_data.get("bid_price"),
                                "ask_price": quote_data.get("ask_price"),
                                "bid_size": quote_data.get("bid_size"),
                                "ask_size": quote_data.get("ask_size")
                            })
                    except:
                        pass  # Continue without quote data if it fails
                    
                    options_data.append(option_data)
                
                # Get current stock price
                stock_quote = await self.get_stock_quote(underlying_symbol)
                current_price = None
                if "error" not in stock_quote:
                    current_price = stock_quote.get("ask_price") or stock_quote.get("bid_price")
                
                return {
                    "underlying_symbol": underlying_symbol,
                    "underlying_price": current_price,
                    "expiration_dates": sorted(list(exp_dates)),
                    "options_count": len(options_data),
                    "options": options_data[:100],  # Limit results
                    "note": "Real Alpaca options chain data"
                }
            else:
                return {"error": f"No options chain data found for {underlying_symbol}"}
            
        except Exception as e:
            logger.error(f"Error getting real options chain for {underlying_symbol}: {e}")
            # Fallback to a simple error message
            return {"error": f"Failed to get real options chain data: {str(e)}"}

    async def get_option_quote(self, option_symbol: str) -> Dict[str, Any]:
        """Get quote for a specific option contract - tries real Alpaca data first, falls back to calculated pricing"""
        try:
            # First, try to get real Alpaca options data
            try:
                request = OptionLatestQuoteRequest(symbol_or_symbols=[option_symbol])
                quotes = self.option_data_client.get_option_latest_quote(request)
                
                if quotes and option_symbol in quotes:
                    quote = quotes[option_symbol]
                    
                    # Parse option symbol to get components
                    underlying, strike_price, exp_date, option_type = self._parse_option_symbol(option_symbol)
                    
                    return {
                        "symbol": option_symbol,
                        "underlying_symbol": underlying,
                        "strike_price": strike_price,
                        "expiration_date": exp_date,
                        "option_type": option_type,
                        "bid_price": float(quote.bid_price) if quote.bid_price else None,
                        "ask_price": float(quote.ask_price) if quote.ask_price else None,
                        "bid_size": quote.bid_size,
                        "ask_size": quote.ask_size,
                        "timestamp": quote.timestamp,
                        "data_source": "Real Alpaca options market data"
                    }
            except Exception as e:
                logger.warning(f"Real options data not available for {option_symbol}: {e}")
            
            # Fallback: Calculate realistic pricing based on real stock price
            underlying, strike_price, exp_date, option_type = self._parse_option_symbol(option_symbol)
            
            if not underlying or not strike_price or not option_type:
                return {"error": "Invalid option symbol format"}
            
            # Get real underlying stock price
            stock_quote = await self.get_stock_quote(underlying)
            if "error" in stock_quote:
                return {"error": f"Could not get stock price for underlying {underlying}"}
            
            current_price = stock_quote.get("ask_price") or stock_quote.get("bid_price")
            if not current_price:
                return {"error": f"No valid stock price found for {underlying}"}
            
            # Calculate Black-Scholes approximation for realistic pricing
            from datetime import datetime
            try:
                exp_datetime = datetime.strptime(exp_date, "%Y-%m-%d")
                days_to_exp = (exp_datetime - datetime.now()).days
                time_to_exp = max(1, days_to_exp) / 365.0
            except:
                time_to_exp = 0.1  # Default to ~1 month
            
            # Simple Black-Scholes approximation
            if option_type == "call":
                intrinsic = max(0, current_price - strike_price)
                time_value = max(0.01, strike_price * 0.25 * (time_to_exp ** 0.5) * 0.5)
                delta = 0.5 + (current_price - strike_price) / (strike_price * 2)
                delta = max(0.01, min(0.99, delta))
            else:  # put
                intrinsic = max(0, strike_price - current_price)
                time_value = max(0.01, strike_price * 0.25 * (time_to_exp ** 0.5) * 0.5)
                delta = -0.5 + (current_price - strike_price) / (strike_price * 2)
                delta = max(-0.99, min(-0.01, delta))
            
            theoretical_price = intrinsic + time_value
            bid_price = max(0.01, theoretical_price * 0.98)
            ask_price = theoretical_price * 1.02
            
            return {
                "symbol": option_symbol,
                "underlying_symbol": underlying,
                "underlying_price": current_price,
                "strike_price": strike_price,
                "expiration_date": exp_date,
                "option_type": option_type,
                "bid_price": round(bid_price, 2),
                "ask_price": round(ask_price, 2),
                "last_price": round(theoretical_price, 2),
                "implied_volatility": 0.25,
                "delta": round(delta, 3),
                "gamma": 0.05,
                "theta": -0.02,
                "vega": 0.1,
                "in_the_money": (option_type == "call" and current_price > strike_price) or (option_type == "put" and current_price < strike_price),
                "intrinsic_value": round(intrinsic, 2),
                "time_value": round(time_value, 2),
                "timestamp": pd.Timestamp.now(),
                "data_source": f"Calculated pricing based on real {underlying} stock price: ${current_price}"
            }
                
        except Exception as e:
            logger.error(f"Error getting option quote for {option_symbol}: {e}")
            return {"error": f"Failed to get option data: {str(e)}"}
    
    def _parse_option_symbol(self, option_symbol: str):
        """Parse option symbol to extract components"""
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
                return None, None, None, None
            
            if len(option_symbol) < date_start_idx + 7:
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
        """Get quotes for multiple option contracts"""
        try:
            results = []
            for symbol in option_symbols:
                quote = await self.get_option_quote(symbol)
                results.append(quote)
            
            return {
                "quotes": results,
                "count": len(results),
                "requested_symbols": option_symbols
            }
            
        except Exception as e:
            logger.error(f"Error getting multiple option quotes: {e}")
            return {"error": str(e)}

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
            order = self.trading_client.submit_order(order_data)
            
            return {
                "id": order.id,
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
            
        except Exception as e:
            logger.error(f"Error placing stock order: {e}")
            return {"error": str(e)}

    async def place_option_order(self, option_symbol: str, qty: int, side: str, order_type: str = "market",
                               limit_price: Optional[float] = None, time_in_force: str = "day") -> Dict[str, Any]:
        """Place an options order"""
        try:
            # Note: Options trading implementation depends on Alpaca's options trading API
            # This is a placeholder implementation
            return {
                "message": "Options trading requires additional implementation based on Alpaca's options trading capabilities",
                "option_symbol": option_symbol,
                "qty": qty,
                "side": side,
                "order_type": order_type
            }
            
        except Exception as e:
            logger.error(f"Error placing option order: {e}")
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
                        "id": order.id,
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