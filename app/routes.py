from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.models import (
    StockQuoteRequest, MultiStockQuoteRequest, StockOrderRequest, 
    OptionOrderRequest, OptionsChainRequest, OptionQuoteRequest, MultiOptionQuoteRequest,
    StockQuoteResponse, OrderResponse, PositionResponse, AccountResponse
)
from app.alpaca_client import AlpacaClient
from config import settings
from loguru import logger

# Create router
router = APIRouter()

# Dependency to get Alpaca client
def get_alpaca_client() -> AlpacaClient:
    return AlpacaClient()

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint with configuration status"""
    return {
        "status": "healthy", 
        "service": "Opitios Alpaca Trading Service",
        "configuration": {
            "real_data_only": settings.real_data_only,
            "mock_data_enabled": settings.enable_mock_data,
            "strict_error_handling": settings.strict_error_handling,
            "paper_trading": settings.alpaca_paper_trading,
            "max_option_symbols_per_request": settings.max_option_symbols_per_request
        },
        "data_policy": "Real Alpaca market data only - no calculated or mock data"
    }

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
    Get the options chain for an underlying stock using only real Alpaca market data.
    Returns calls and puts with different strike prices and expiration dates.
    
    **Note:** This endpoint returns only real market data from Alpaca. Options without real quote data
    will be included in the chain but may have missing bid/ask prices.
    
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
        "quote_failures": 5,
        "options": [
            {
                "symbol": "AAPL240216C00190000",
                "strike_price": 190.0,
                "option_type": "call",
                "bid_price": 24.5,
                "ask_price": 25.0,
                "last_price": 24.75,
                "implied_volatility": 0.25
            }
        ]
    }
    ```
    """)
async def get_options_chain(request: OptionsChainRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get options chain for an underlying symbol using only real market data"""
    try:
        chain_data = await client.get_options_chain(request.underlying_symbol, request.expiration_date)
        if "error" in chain_data:
            logger.warning(f"Options chain unavailable for {request.underlying_symbol}: {chain_data['error']}")
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": chain_data["error"],
                    "error_code": "OPTIONS_CHAIN_UNAVAILABLE",
                    "underlying_symbol": request.underlying_symbol,
                    "expiration_date": request.expiration_date,
                    "message": "No real options chain data available from Alpaca for this symbol"
                }
            )
        return chain_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_options_chain for {request.underlying_symbol}: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"Internal server error while retrieving options chain: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "underlying_symbol": request.underlying_symbol,
                "expiration_date": request.expiration_date
            }
        )

@router.post("/options/quote",
    summary="Get Single Option Quote",
    description="""
    Get a quote for a specific option contract using only real Alpaca market data.
    
    **Option Symbol Format:** AAPL240216C00190000
    - AAPL: Underlying symbol
    - 240216: Expiration date (YYMMDD)
    - C: Call option (P for Put)
    - 00190000: Strike price ($190.00)
    
    **Note:** This endpoint returns only real market data from Alpaca. If real data is not available,
    the request will fail with an appropriate error message.
    
    **Example Request:**
    ```json
    {
        "option_symbol": "AAPL240216C00190000"
    }
    ```
    
    **Example Success Response:**
    ```json
    {
        "symbol": "AAPL240216C00190000",
        "underlying_symbol": "AAPL",
        "strike_price": 190.0,
        "expiration_date": "2024-02-16",
        "option_type": "call",
        "bid_price": 24.25,
        "ask_price": 24.75,
        "last_price": 24.50,
        "implied_volatility": 0.25,
        "timestamp": "2024-01-15T15:30:00Z"
    }
    ```
    
    **Example Error Response:**
    ```json
    {
        "detail": {
            "error": "No real market data available for option symbol: AAPL240216C00190000",
            "error_code": "REAL_DATA_UNAVAILABLE",
            "option_symbol": "AAPL240216C00190000",
            "message": "This service provides only authentic market data from Alpaca. No calculated or mock data is returned."
        }
    }
    ```
    """)
async def get_option_quote(request: OptionQuoteRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get quote for a specific option contract using only real market data"""
    try:
        quote_data = await client.get_option_quote(request.option_symbol)
        if "error" in quote_data:
            logger.warning(f"Real data unavailable for option {request.option_symbol}: {quote_data['error']}")
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": quote_data["error"],
                    "error_code": "REAL_DATA_UNAVAILABLE",
                    "option_symbol": request.option_symbol,
                    "message": "This service provides only authentic market data from Alpaca. No calculated or mock data is returned."
                }
            )
        return quote_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_option_quote for {request.option_symbol}: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"Internal server error while retrieving option data: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "option_symbol": request.option_symbol
            }
        )

@router.post("/options/quotes/batch",
    summary="Get Multiple Option Quotes", 
    description="""
    Get quotes for multiple option contracts in a single request using only real Alpaca market data.
    
    **Note:** This endpoint returns only real market data from Alpaca. Individual options that don't have
    real data available will be marked with errors in the response.
    
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
                "timestamp": "2024-01-15T15:30:00Z"
            },
            {
                "error": "No real market data available for option symbol: AAPL240216P00180000"
            }
        ],
        "count": 2,
        "successful_count": 1,
        "failed_count": 1,
        "failed_symbols": ["AAPL240216P00180000"]
    }
    ```
    """)
async def get_multiple_option_quotes(request: MultiOptionQuoteRequest, client: AlpacaClient = Depends(get_alpaca_client)):
    """Get quotes for multiple option contracts using only real market data"""
    try:
        if len(request.option_symbols) > settings.max_option_symbols_per_request:
            logger.warning(f"Batch request exceeded limit: {len(request.option_symbols)} symbols (max {settings.max_option_symbols_per_request})")
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": f"Maximum {settings.max_option_symbols_per_request} option symbols allowed per request",
                    "error_code": "REQUEST_LIMIT_EXCEEDED",
                    "requested_count": len(request.option_symbols),
                    "max_allowed": settings.max_option_symbols_per_request
                }
            )
            
        quotes_data = await client.get_multiple_option_quotes(request.option_symbols)
        if "error" in quotes_data:
            logger.error(f"Batch option quotes request failed: {quotes_data['error']}")
            raise HTTPException(
                status_code=500, 
                detail={
                    "error": quotes_data["error"],
                    "error_code": "BATCH_REQUEST_FAILED",
                    "requested_symbols": request.option_symbols
                }
            )
        
        # Log summary of batch request
        success_rate = quotes_data.get('successful_count', 0) / len(request.option_symbols) * 100
        logger.info(f"Batch option quotes: {success_rate:.1f}% success rate ({quotes_data.get('successful_count', 0)}/{len(request.option_symbols)})")
        
        return quotes_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_multiple_option_quotes: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"Internal server error during batch option quotes request: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "requested_symbols": request.option_symbols
            }
        )

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