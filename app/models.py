from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill

class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"

# Stock Models
class StockQuoteRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL, TSLA)")

class MultiStockQuoteRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock symbols (e.g., ['AAPL', 'TSLA', 'GOOGL'])", example=["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"])

class StockOrderRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    qty: float = Field(..., gt=0, description="Quantity to trade")
    side: OrderSide = Field(..., description="Buy or sell")
    type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="Time in force")
    limit_price: Optional[float] = Field(None, description="Limit price for limit orders")
    stop_price: Optional[float] = Field(None, description="Stop price for stop orders")
    bulk_place: Optional[bool] = Field(default=False, description="If true, place order for all accounts")

# Options Models
class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"

class OptionsChainRequest(BaseModel):
    underlying_symbol: str = Field(..., description="Underlying stock symbol", example="AAPL")
    expiration_date: Optional[str] = Field(None, description="Expiration date (YYYY-MM-DD)", example="2024-02-16")
    option_type: Optional[OptionType] = Field(None, description="Call or Put", example="call")

class OptionQuoteRequest(BaseModel):
    option_symbol: str = Field(..., description="Option contract symbol", example="AAPL240216C00190000")

class MultiOptionQuoteRequest(BaseModel):
    option_symbols: List[str] = Field(..., description="List of option contract symbols", example=["AAPL240216C00190000", "AAPL240216P00180000", "TSLA240216C00200000"])

class OptionOrderRequest(BaseModel):
    option_symbol: str = Field(..., description="Option contract symbol")
    qty: int = Field(..., gt=0, description="Number of contracts")
    side: OrderSide = Field(..., description="Buy or sell")
    type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="Time in force")
    limit_price: Optional[float] = Field(None, description="Limit price for limit orders")
    bulk_place: Optional[bool] = Field(default=False, description="If true, place order for all accounts")

# Response Models
class StockQuoteResponse(BaseModel):
    symbol: str
    bid_price: Optional[float]
    ask_price: Optional[float]
    last_price: Optional[float]
    timestamp: datetime

class OptionQuoteResponse(BaseModel):
    """Response model for option quotes using only real market data from Alpaca"""
    symbol: str
    underlying_symbol: str
    strike_price: float
    expiration_date: str
    option_type: str
    bid_price: Optional[float]
    ask_price: Optional[float]
    last_price: Optional[float]
    implied_volatility: Optional[float]
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL240216C00190000",
                "underlying_symbol": "AAPL",
                "strike_price": 190.0,
                "expiration_date": "2024-02-16",
                "option_type": "call",
                "bid_price": 24.25,
                "ask_price": 24.75,
                "last_price": 24.50,
                "implied_volatility": 0.25,
                "bid_size": 10,
                "ask_size": 15,
                "timestamp": "2024-01-15T15:30:00Z"
            }
        }

class OrderResponse(BaseModel):
    id: str
    symbol: str
    qty: float
    side: str
    order_type: str
    status: str
    filled_qty: Optional[float]
    filled_avg_price: Optional[float]
    submitted_at: datetime
    filled_at: Optional[datetime]

class PositionResponse(BaseModel):
    asset_id: Optional[str]
    symbol: str
    qty: float
    side: str
    market_value: Optional[float]
    cost_basis: Optional[float]
    unrealized_pl: Optional[float]
    unrealized_plpc: Optional[float]
    avg_entry_price: Optional[float]  # 平均成本价 - 直接来自Alpaca API
    current_price: Optional[float]  # 当前价格
    lastday_price: Optional[float]  # 昨日收盘价
    asset_class: Optional[str]  # 资产类型 - 用于识别期权 (us_option)
    qty_available: Optional[float]  # 可用数量 - 用于正确的卖出数量

class AccountResponse(BaseModel):
    account_number: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    last_equity: float
    multiplier: int
    pattern_day_trader: bool

class BulkOrderResult(BaseModel):
    """Single account result in bulk order"""
    account_id: str
    account_name: Optional[str] = None
    success: bool
    order: Optional[OrderResponse] = None
    error: Optional[str] = None

class BulkOrderResponse(BaseModel):
    """Response for bulk order operations"""
    bulk_place: bool = True
    total_accounts: int
    successful_orders: int
    failed_orders: int
    results: List[BulkOrderResult]
    
    class Config:
        json_schema_extra = {
            "example": {
                "bulk_place": True,
                "total_accounts": 3,
                "successful_orders": 2,
                "failed_orders": 1,
                "results": [
                    {
                        "account_id": "account_1",
                        "account_name": "Trading Account 1",
                        "success": True,
                        "order": {
                            "id": "order_123",
                            "symbol": "AAPL",
                            "qty": 10,
                            "side": "buy",
                            "order_type": "market",
                            "status": "pending_new"
                        }
                    },
                    {
                        "account_id": "account_2", 
                        "success": False,
                        "error": "Insufficient buying power"
                    }
                ]
            }
        }

class ErrorResponse(BaseModel):
    """Structured error response for API failures"""
    error: str
    error_code: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "No real market data available for option symbol: AAPL240216C00190000",
                "error_code": "REAL_DATA_UNAVAILABLE",
                "message": "This service provides only authentic market data from Alpaca. No calculated or mock data is returned.",
                "details": {
                    "option_symbol": "AAPL240216C00190000",
                    "service": "opitios_alpaca"
                }
            }
        }