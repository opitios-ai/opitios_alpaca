from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import re

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
class MultiStockQuoteRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock symbols (e.g., ['AAPL', 'TSLA', 'GOOGL'])", example=["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"])

class StockOrderRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    qty: float = Field(..., gt=0, description="Quantity to trade")
    side: OrderSide = Field(..., description="Buy or sell")
    type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="Time in force")
    limit_price: Optional[float] = Field(None, gt=0, description="Limit price for limit orders")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price for stop orders")
    bulk_place: Optional[bool] = Field(default=False, description="If true, place order for all accounts")
    strategy_name: Optional[str] = Field(
        "MODE_STOCK_TRADE",
        description="Trading strategy to validate (default: MODE_STOCK_TRADE)",
        example="MODE_STOCK_TRADE"
    )

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
    limit_price: Optional[float] = Field(None, gt=0, description="Limit price for limit orders")
    bulk_place: Optional[bool] = Field(default=False, description="If true, place order for all accounts")
    auto_sell_enabled: Optional[bool] = Field(
        default=None,
        description="是否允许自动卖出。前端可传入，BUY时默认False（手动下单默认不自动卖出），SELL时忽略"
    )
    strategy_name: Optional[str] = Field(
        None,
        description="Trading strategy to validate. If not provided: BUY uses MODE_DAY_TRADE (day trading), SELL uses MODE_OPTION_TRADE (allows closing positions with option trading permission)",
        example="MODE_DAY_TRADE"
    )

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
    asset_class: Optional[str] = None  # 资产类型 - 用于识别期权 (us_option)
    
    @field_validator('submitted_at', 'filled_at', mode='before')
    @classmethod
    def parse_datetime_with_timezone(cls, v):
        """Parse datetime strings that may contain timezone information like 'EDT'"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        
        # Handle timezone abbreviations like 'EDT', 'EST', etc.
        # Remove timezone abbreviations and parse as naive datetime
        if isinstance(v, str):
            # Remove common timezone abbreviations
            v_clean = re.sub(r'\s+(EDT|EST|PDT|PST|CDT|CST|MDT|MST|UTC|GMT)\s*$', '', v.strip())
            try:
                # Try parsing the cleaned string
                return datetime.fromisoformat(v_clean.replace(' ', 'T'))
            except ValueError:
                # If that fails, try other common formats
                try:
                    return datetime.strptime(v_clean, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Last resort: try ISO format
                    return datetime.fromisoformat(v_clean)
        
        return v

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

# Dashboard Models
class ContractInfo(BaseModel):
    """Contract information for holdings"""
    symbol: str
    currency: str = "USD"
    sec_type: str  # "STK" for stocks, "OPT" for options
    expiry: Optional[str] = None  # For options: "20250919"
    strike: Optional[str] = None  # For options: "170.0"
    right: Optional[str] = None   # For options: "PUT" or "CALL"
    identifier: str  # Full symbol identifier

class HoldingInfo(BaseModel):
    """Individual holding information"""
    quantity: float
    average_cost: float
    market_value: float
    market_price: float
    unrealized_pnl: float
    realized_pnl: float
    contract: ContractInfo

class DailySummary(BaseModel):
    """Daily trading summary"""
    date: str
    net_profit: float
    sold_qty: int
    commission: float
    avg_sold_price: Optional[float] = None

class TradingHistory(BaseModel):
    """Trading history summary"""
    overall_profit: float
    overall_commission: float
    daily_summary: List[DailySummary]
    has_data: bool

class ProfitPeriod(BaseModel):
    """Profit data for a specific period"""
    profit: float
    commission: float
    has_data: bool

class ProfitChartData(BaseModel):
    """Profit data for chart display"""
    overall_profit: float
    overall_commission: float
    daily_summary: List[DailySummary]
    has_data: bool

class ProfitReport(BaseModel):
    """Complete profit report with daily, weekly, and chart data"""
    daily: ProfitPeriod
    weekly: ProfitPeriod
    total_for_chart: ProfitChartData

class DashboardAccountDetails(BaseModel):
    """Account details for dashboard"""
    account_name: str
    real_account: Optional[str] = None
    real_tiger_id: Optional[str] = None
    sandbox_account: Optional[str] = None
    sandbox_tiger_id: Optional[str] = None
    key_path: Optional[str] = None
    permission_group: str = "user"
    paper_trading: int = 1
    currency: str = "USD"
    cash: float
    net_liquidation: float

class DashboardResponse(BaseModel):
    """Complete dashboard response matching Tiger API format"""
    account_details: DashboardAccountDetails
    holdings: List[HoldingInfo]
    trading_history: TradingHistory
    profit_report: ProfitReport
    recent_orders: Optional[List[OrderResponse]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_details": {
                    "account_name": "demo_user",
                    "paper_trading": 1,
                    "currency": "USD",
                    "cash": 10000.0,
                    "net_liquidation": 15000.0
                },
                "holdings": [
                    {
                        "quantity": 10,
                        "average_cost": 150.0,
                        "market_value": 1600.0,
                        "market_price": 160.0,
                        "unrealized_pnl": 100.0,
                        "realized_pnl": 0.0,
                        "contract": {
                            "symbol": "AAPL",
                            "currency": "USD",
                            "sec_type": "STK",
                            "identifier": "AAPL"
                        }
                    }
                ],
                "trading_history": {
                    "overall_profit": 500.0,
                    "overall_commission": 25.0,
                    "daily_summary": [
                        {
                            "date": "2024-01-15",
                            "net_profit": 100.0,
                            "sold_qty": 5,
                            "commission": 5.0,
                            "avg_sold_price": 155.0
                        }
                    ],
                    "has_data": True
                },
                "profit_report": {
                    "daily": {
                        "profit": 100.0,
                        "commission": 5.0,
                        "has_data": True
                    },
                    "weekly": {
                        "profit": 500.0,
                        "commission": 25.0,
                        "has_data": True
                    },
                    "total_for_chart": {
                        "overall_profit": 500.0,
                        "overall_commission": 25.0,
                        "daily_summary": [
                            {
                                "date": "2024-01-15",
                                "net_profit": 100.0,
                                "sold_qty": 5,
                                "commission": 5.0,
                                "avg_sold_price": 155.0
                            }
                        ],
                        "has_data": True
                    }
                }
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