from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.models import (
    StockQuoteRequest, MultiStockQuoteRequest, StockOrderRequest, 
    OptionOrderRequest, OptionsChainRequest, OptionQuoteRequest, MultiOptionQuoteRequest,
    StockQuoteResponse, OrderResponse, PositionResponse, AccountResponse
)
from app.alpaca_client import AlpacaClient
from loguru import logger

# Create router
router = APIRouter()

# Dependency to get Alpaca client
def get_alpaca_client() -> AlpacaClient:
    return AlpacaClient()

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Opitios Alpaca Trading Service"}

# Connection test endpoint
@router.get("/test-connection")
async def test_connection(client: AlpacaClient = Depends(get_alpaca_client)):
    """Test connection to Alpaca API"""
    result = await client.test_connection()
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

# Account endpoints
@router.get("/account", response_model=AccountResponse)
async def get_account_info(client: AlpacaClient = Depends(get_alpaca_client)):
    """Get account information"""
    try:
        account_data = await client.get_account()
        if "error" in account_data:
            raise HTTPException(status_code=500, detail=account_data["error"])
        return AccountResponse(**account_data)
    except Exception as e:
        logger.error(f"Error in get_account_info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(client: AlpacaClient = Depends(get_alpaca_client)):
    """Get all positions"""
    try:
        positions = await client.get_positions()
        if positions and "error" in positions[0]:
            raise HTTPException(status_code=500, detail=positions[0]["error"])
        return [PositionResponse(**pos) for pos in positions if "error" not in pos]
    except Exception as e:
        logger.error(f"Error in get_positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Stock quote endpoints
@router.post("/stocks/quote", 
    summary="Get Single Stock Quote",
    description="""
    Get the latest quote for a single stock.
    
    **Example Request:**
    ```json
    {
        "symbol": "AAPL"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "symbol": "AAPL",
        "bid_price": 210.1,
        "ask_price": 214.3,
        "bid_size": 100,
        "ask_size": 200,
        "timestamp": "2024-01-15T15:30:00Z"
    }
    ```
    """)
async def get_stock_quote(request: StockQuoteRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get latest quote for a stock"""
    try:
        quote_data = await client.get_stock_quote(request.symbol)
        if "error" in quote_data:
            raise HTTPException(status_code=400, detail=quote_data["error"])
        return quote_data
    except Exception as e:
        logger.error(f"Error in get_stock_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stocks/quotes/batch",
    summary="Get Multiple Stock Quotes",
    description="""
    Get latest quotes for multiple stocks in a single request. Supports up to 20 symbols.
    
    **Example Request:**
    ```json
    {
        "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
    }
    ```
    
    **Example Response:**
    ```json
    {
        "quotes": [
            {
                "symbol": "AAPL",
                "bid_price": 210.1,
                "ask_price": 214.3,
                "timestamp": "2024-01-15T15:30:00Z"
            },
            {
                "symbol": "TSLA", 
                "bid_price": 185.5,
                "ask_price": 187.2,
                "timestamp": "2024-01-15T15:30:00Z"
            }
        ],
        "count": 2,
        "requested_symbols": ["AAPL", "TSLA"]
    }
    ```
    """)
async def get_multiple_stock_quotes(request: MultiStockQuoteRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get latest quotes for multiple stocks"""
    try:
        if not request.symbols or len(request.symbols) == 0:
            raise HTTPException(status_code=400, detail="At least one symbol is required")
            
        if len(request.symbols) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 symbols allowed per request")
        
        quotes_data = await client.get_multiple_stock_quotes(request.symbols)
        if "error" in quotes_data:
            raise HTTPException(status_code=400, detail=quotes_data["error"])
        return quotes_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_multiple_stock_quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stocks/{symbol}/quote")
async def get_stock_quote_by_symbol(symbol: str, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get latest quote for a stock by symbol"""
    try:
        quote_data = await client.get_stock_quote(symbol.upper())
        if "error" in quote_data:
            raise HTTPException(status_code=400, detail=quote_data["error"])
        return quote_data
    except Exception as e:
        logger.error(f"Error in get_stock_quote_by_symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stocks/{symbol}/bars")
async def get_stock_bars(
    symbol: str, 
    timeframe: str = "1Day", 
    limit: int = 100,
    client: AlpacaClient = Depends(get_alpaca_client)
):
    """Get historical price bars for a stock"""
    try:
        bars_data = await client.get_stock_bars(symbol.upper(), timeframe, limit)
        if "error" in bars_data:
            raise HTTPException(status_code=400, detail=bars_data["error"])
        return bars_data
    except Exception as e:
        logger.error(f"Error in get_stock_bars: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Options endpoints
@router.post("/options/chain",
    summary="Get Options Chain",
    description="""
    Get the options chain for an underlying stock. Returns calls and puts with different strike prices and expiration dates.
    
    **Example Request:**
    ```json
    {
        "underlying_symbol": "AAPL",
        "expiration_date": "2024-02-16",
        "option_type": "call"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "underlying_symbol": "AAPL",
        "underlying_price": 212.5,
        "expiration_dates": ["2024-02-16"],
        "options_count": 40,
        "options": [
            {
                "symbol": "AAPL240216C00190000",
                "strike_price": 190.0,
                "option_type": "call",
                "bid_price": 24.5,
                "ask_price": 25.0,
                "delta": 0.85,
                "in_the_money": true
            }
        ]
    }
    ```
    """)
async def get_options_chain(request: OptionsChainRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get options chain for an underlying symbol"""
    try:
        chain_data = await client.get_options_chain(request.underlying_symbol, request.expiration_date)
        if "error" in chain_data:
            raise HTTPException(status_code=400, detail=chain_data["error"])
        return chain_data
    except Exception as e:
        logger.error(f"Error in get_options_chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/options/quote",
    summary="Get Single Option Quote",
    description="""
    Get a quote for a specific option contract.
    
    **Option Symbol Format:** AAPL240216C00190000
    - AAPL: Underlying symbol
    - 240216: Expiration date (YYMMDD)
    - C: Call option (P for Put)
    - 00190000: Strike price ($190.00)
    
    **Example Request:**
    ```json
    {
        "option_symbol": "AAPL240216C00190000"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "symbol": "AAPL240216C00190000",
        "underlying_symbol": "AAPL",
        "underlying_price": 212.5,
        "strike_price": 190.0,
        "expiration_date": "2024-02-16",
        "option_type": "call",
        "bid_price": 24.25,
        "ask_price": 24.75,
        "last_price": 24.50,
        "implied_volatility": 0.25,
        "delta": 0.85,
        "gamma": 0.05,
        "theta": -0.02,
        "vega": 0.1,
        "in_the_money": true,
        "intrinsic_value": 22.5,
        "time_value": 2.0
    }
    ```
    """)
async def get_option_quote(request: OptionQuoteRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get quote for a specific option contract"""
    try:
        quote_data = await client.get_option_quote(request.option_symbol)
        if "error" in quote_data:
            raise HTTPException(status_code=400, detail=quote_data["error"])
        return quote_data
    except Exception as e:
        logger.error(f"Error in get_option_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/options/quotes/batch",
    summary="Get Multiple Option Quotes", 
    description="""
    Get quotes for multiple option contracts in a single request.
    
    **Example Request:**
    ```json
    {
        "option_symbols": [
            "AAPL240216C00190000",
            "AAPL240216P00180000", 
            "TSLA240216C00200000"
        ]
    }
    ```
    
    **Example Response:**
    ```json
    {
        "quotes": [
            {
                "symbol": "AAPL240216C00190000",
                "underlying_symbol": "AAPL",
                "strike_price": 190.0,
                "option_type": "call",
                "bid_price": 24.25,
                "ask_price": 24.75,
                "delta": 0.85
            },
            {
                "symbol": "AAPL240216P00180000",
                "underlying_symbol": "AAPL", 
                "strike_price": 180.0,
                "option_type": "put",
                "bid_price": 2.10,
                "ask_price": 2.35,
                "delta": -0.15
            }
        ],
        "count": 2
    }
    ```
    """)
async def get_multiple_option_quotes(request: MultiOptionQuoteRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get quotes for multiple option contracts"""
    try:
        if len(request.option_symbols) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 option symbols allowed per request")
            
        quotes_data = await client.get_multiple_option_quotes(request.option_symbols)
        if "error" in quotes_data:
            raise HTTPException(status_code=400, detail=quotes_data["error"])
        return quotes_data
    except Exception as e:
        logger.error(f"Error in get_multiple_option_quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options/{underlying_symbol}/chain")
async def get_options_chain_by_symbol(
    underlying_symbol: str,
    expiration_date: Optional[str] = None,
    client: AlpacaClient = Depends(get_alpaca_client)
):
    """Get options chain for an underlying symbol"""
    try:
        chain_data = await client.get_options_chain(underlying_symbol.upper(), expiration_date)
        if "error" in chain_data:
            raise HTTPException(status_code=400, detail=chain_data["error"])
        return chain_data
    except Exception as e:
        logger.error(f"Error in get_options_chain_by_symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Trading endpoints
@router.post("/stocks/order", 
    summary="Place Stock Order",
    description="""
    Place a stock order with various order types and time in force options.
    
    **Order Types:**
    - market: Execute immediately at current market price
    - limit: Execute only at specified price or better
    - stop: Trigger market order when stop price is reached
    - stop_limit: Trigger limit order when stop price is reached
    
    **Time in Force:**
    - day: Order expires at end of trading day
    - gtc: Good Till Cancelled
    - ioc: Immediate or Cancel
    - fok: Fill or Kill
    
    **Example Market Order:**
    ```json
    {
        "symbol": "AAPL",
        "qty": 10,
        "side": "buy", 
        "type": "market",
        "time_in_force": "day"
    }
    ```
    
    **Example Limit Order:**
    ```json
    {
        "symbol": "AAPL",
        "qty": 5,
        "side": "sell",
        "type": "limit",
        "limit_price": 215.50,
        "time_in_force": "gtc"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa",
        "symbol": "AAPL",
        "qty": 10,
        "side": "buy",
        "order_type": "market",
        "status": "pending_new",
        "filled_qty": 0,
        "submitted_at": "2024-01-15T15:30:00Z"
    }
    ```
    """,
    response_model=OrderResponse)
async def place_stock_order(request: StockOrderRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Place a stock order"""
    try:
        order_data = await client.place_stock_order(
            symbol=request.symbol.upper(),
            qty=request.qty,
            side=request.side.value,
            order_type=request.type.value,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            time_in_force=request.time_in_force.value
        )
        if "error" in order_data:
            raise HTTPException(status_code=400, detail=order_data["error"])
        return OrderResponse(**order_data)
    except Exception as e:
        logger.error(f"Error in place_stock_order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/options/order")
async def place_option_order(request: OptionOrderRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Place an options order"""
    try:
        order_data = await client.place_option_order(
            option_symbol=request.option_symbol.upper(),
            qty=request.qty,
            side=request.side.value,
            order_type=request.type.value,
            limit_price=request.limit_price,
            time_in_force=request.time_in_force.value
        )
        if "error" in order_data:
            raise HTTPException(status_code=400, detail=order_data["error"])
        return order_data
    except Exception as e:
        logger.error(f"Error in place_option_order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Order management endpoints
@router.get("/orders", response_model=List[OrderResponse])
async def get_orders(
    status: Optional[str] = None, 
    limit: int = 100,
    client: AlpacaClient = Depends(get_alpaca_client)
):
    """Get orders"""
    try:
        orders = await client.get_orders(status, limit)
        if orders and "error" in orders[0]:
            raise HTTPException(status_code=500, detail=orders[0]["error"])
        return [OrderResponse(**order) for order in orders if "error" not in order]
    except Exception as e:
        logger.error(f"Error in get_orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, client: AlpacaClient = Depends(get_alpaca_client)):
    """Cancel an order"""
    try:
        result = await client.cancel_order(order_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Error in cancel_order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Quick trading endpoints for convenience
@router.post("/stocks/{symbol}/buy")
async def buy_stock(
    symbol: str,
    qty: float,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    client: AlpacaClient = Depends(get_alpaca_client)
):
    """Quick buy stock endpoint"""
    try:
        order_data = await client.place_stock_order(
            symbol=symbol.upper(),
            qty=qty,
            side="buy",
            order_type=order_type,
            limit_price=limit_price
        )
        if "error" in order_data:
            raise HTTPException(status_code=400, detail=order_data["error"])
        return OrderResponse(**order_data)
    except Exception as e:
        logger.error(f"Error in buy_stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stocks/{symbol}/sell")
async def sell_stock(
    symbol: str,
    qty: float,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    client: AlpacaClient = Depends(get_alpaca_client)
):
    """Quick sell stock endpoint"""
    try:
        order_data = await client.place_stock_order(
            symbol=symbol.upper(),
            qty=qty,
            side="sell",
            order_type=order_type,
            limit_price=limit_price
        )
        if "error" in order_data:
            raise HTTPException(status_code=400, detail=order_data["error"])
        return OrderResponse(**order_data)
    except Exception as e:
        logger.error(f"Error in sell_stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))