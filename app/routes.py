from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from app.models import (
    MultiStockQuoteRequest, StockOrderRequest, 
    OptionOrderRequest, OptionsChainRequest, OptionQuoteRequest, MultiOptionQuoteRequest,
    OrderResponse, PositionResponse, AccountResponse,
    BulkOrderResponse, DashboardResponse, DashboardAccountDetails, 
    HoldingInfo, ContractInfo, TradingHistory, DailySummary
)
from app.alpaca_client import AlpacaClient, pooled_client
from app.middleware import internal_or_jwt_auth
from config import settings
from loguru import logger

# Create router
router = APIRouter()

# Dependency to get account routing info
def get_routing_info(
    account_id: Optional[str] = Query(None, description="指定账户ID进行路由"),
    routing_key: Optional[str] = Query(None, description="路由键（如符号）用于负载均衡")
):
    """获取账户路由信息"""
    return {"account_id": account_id, "routing_key": routing_key}

# Dependency to get Alpaca client (for compatibility with non-authenticated endpoints)
def get_alpaca_client() -> AlpacaClient:
    # This is only used for non-authenticated endpoints, so we use default credentials
    from config import settings
    if not settings.accounts:
        raise HTTPException(status_code=500, detail="No account configuration available")
    
    # Use the first available account
    first_account = list(settings.accounts.values())[0]
    return AlpacaClient(
        api_key=first_account.api_key,
        secret_key=first_account.secret_key,
        paper_trading=first_account.paper_trading
    )

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
            "multi_account_mode": len(settings.accounts) > 0,
            "max_option_symbols_per_request": settings.max_option_symbols_per_request
        },
        "data_policy": "Real Alpaca market data only - no calculated or mock data"
    }

# Connection test endpoint
@router.get("/test-connection")
async def test_connection(routing_info: dict = Depends(get_routing_info)):
    """Test connection to Alpaca API - uses connection pool with option_ws account"""
    try:
        # Use option_ws account for options-related testing
        account_data = await pooled_client.get_account(
            account_id="option_ws",
            routing_key="test_connection"
        )
        if "error" in account_data:
            raise HTTPException(status_code=500, detail=account_data["error"])
        return {"status": "success", "message": "Connection to Alpaca API successful", "account_tested": "option_ws"}
    except Exception as e:
        logger.error(f"Error in test_connection: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

# Account endpoints
@router.get("/account", response_model=AccountResponse)
async def get_account_info(
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Get account information - uses connection pool with routing"""
    try:
        # Security: Require explicit account_id to prevent unauthorized access
        if not routing_info["account_id"]:
            raise HTTPException(
                status_code=400, 
                detail="account_id parameter is required"
            )
        
        account_data = await pooled_client.get_account(
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        if "error" in account_data:
            raise HTTPException(status_code=500, detail=account_data["error"])
        return AccountResponse(**account_data)
    except Exception as e:
        logger.error(f"Error in get_account_info: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Get all positions - uses connection pool with routing"""
    try:
        # Security: Require explicit account_id to prevent unauthorized access
        if not routing_info["account_id"]:
            raise HTTPException(
                status_code=400, 
                detail="account_id parameter is required"
            )
        
        positions = await pooled_client.get_positions(
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        if positions and "error" in positions[0]:
            raise HTTPException(status_code=500, detail=positions[0]["error"])
        return [PositionResponse(**pos) for pos in positions if "error" not in pos]
    except Exception as e:
        logger.error(f"Error in get_positions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/stocks/quotes",
    summary="Get Multiple Stock Quotes - Uses Connection Pool",
    description="""
    Get the latest quotes for multiple stocks in a single request.
    Uses connection pool with intelligent account routing.
    
    **Query Parameters:**
    - `account_id`: (Optional) Specify account ID for routing
    - `routing_key`: (Optional) Routing key for load balancing
    
    **Request Body:**
    ```json
    {
        "symbols": ["AAPL", "NVDA", "TSLA"]
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
                "bid_size": 100,
                "ask_size": 200,
                "timestamp": "2024-01-15T15:30:00Z"
            },
            {
                "symbol": "NVDA",
                "bid_price": 850.5,
                "ask_price": 852.0,
                "bid_size": 50,
                "ask_size": 75,
                "timestamp": "2024-01-15T15:30:00Z"
            }
        ],
        "count": 2,
        "successful_count": 2,
        "failed_count": 0,
        "failed_symbols": []
    }
    ```
    """)
async def get_multiple_stock_quotes(
    request: MultiStockQuoteRequest, 
    routing_info: dict = Depends(get_routing_info)
):
    """Get latest quotes for multiple stocks - uses connection pool"""
    try:
        if not request.symbols or len(request.symbols) == 0:
            raise HTTPException(status_code=400, detail="At least one symbol is required")
            
        if len(request.symbols) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 symbols allowed per request")
        
        quotes_data = await pooled_client.get_multiple_stock_quotes(
            symbols=request.symbols,
            account_id=routing_info["account_id"] or "stock_ws",
            routing_key=routing_info["routing_key"] or request.symbols[0]
        )
        if "error" in quotes_data:
            raise HTTPException(status_code=400, detail=quotes_data["error"])
        return quotes_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_multiple_stock_quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/stocks/{symbol}/quote", 
    summary="Get Stock Quote - Uses Connection Pool",
    description="""
    Get the latest quote for a single stock by symbol.
    Uses connection pool with intelligent account routing.
    
    **Query Parameters:**
    - `account_id`: (Optional) Specify account ID for routing
    - `routing_key`: (Optional) Routing key for load balancing
    
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
async def get_stock_quote(symbol: str, routing_info: dict = Depends(get_routing_info)):
    """Get latest quote for a stock by symbol - uses connection pool"""
    try:
        quote_data = await pooled_client.get_stock_quote(
            symbol=symbol.upper(),
            account_id=routing_info["account_id"] or "stock_ws",
            routing_key=routing_info["routing_key"] or symbol
        )
        if "error" in quote_data:
            raise HTTPException(status_code=400, detail=quote_data["error"])
        return quote_data
    except Exception as e:
        logger.error(f"Error in get_stock_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/stocks/{symbol}/bars")
async def get_stock_bars(
    symbol: str, 
    timeframe: str = "1Day", 
    limit: int = 100,
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    routing_info: dict = Depends(get_routing_info)
):
    """Get historical price bars for a stock - uses connection pool"""
    try:
        bars_data = await pooled_client.get_stock_bars(
            symbol=symbol.upper(), 
            timeframe=timeframe, 
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            account_id=routing_info["account_id"] or "stock_ws",
            routing_key=routing_info["routing_key"] or symbol
        )
        if "error" in bars_data:
            error_msg = bars_data.get("error", "Unknown error")
            
            # Check if it's a subscription/permission error (handle JSON string format)
            error_str = str(error_msg).lower()
            if "subscription does not permit" in error_str or "subscription" in error_str:
                logger.warning(f"Paper trading subscription limit for {symbol}: {error_msg}")
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Paper trading accounts have limited data access",
                        "error_code": "SUBSCRIPTION_LIMIT",
                        "symbol": symbol.upper(),
                        "timeframe": timeframe,
                        "message": "Historical bar data requires live trading subscription. Paper trading accounts have limited market data access.",
                        "alpaca_error": str(error_msg)
                    }
                )
            else:
                logger.warning(f"Stock bars unavailable for {symbol}: {error_msg}")
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "error": error_msg,
                        "error_code": "STOCK_BARS_UNAVAILABLE", 
                        "symbol": symbol.upper(),
                        "timeframe": timeframe,
                        "message": "No historical bar data available from Alpaca for this symbol and timeframe"
                    }
                )
        return bars_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_stock_bars for {symbol}: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"Internal server error while retrieving stock bars: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "symbol": symbol.upper(),
                "timeframe": timeframe
            }
        ) from e

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
async def get_options_chain(request: OptionsChainRequest, routing_info: dict = Depends(get_routing_info)):
    """Get options chain for an underlying symbol using only real market data - uses option_ws account"""
    try:
        chain_data = await pooled_client.get_options_chain(
            underlying_symbol=request.underlying_symbol,
            expiration_date=request.expiration_date,
            account_id=routing_info["account_id"] or "option_ws",
            routing_key=request.underlying_symbol
        )
        if "error" in chain_data:
            error_msg = chain_data.get("error", "Unknown error")
            logger.warning(f"Options chain unavailable for {request.underlying_symbol}: {error_msg}")
            
            # Provide helpful error message
            if "no real options chain data" in str(error_msg).lower():
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "error": error_msg,
                        "error_code": "OPTIONS_CHAIN_UNAVAILABLE",
                        "underlying_symbol": request.underlying_symbol,
                        "expiration_date": request.expiration_date,
                        "message": "Options chain data may be temporarily unavailable. Try again in a few moments.",
                        "suggestion": "Options data availability varies by market hours and symbol liquidity"
                    }
                )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "error": error_msg,
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
        ) from e

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
async def get_option_quote(request: OptionQuoteRequest, routing_info: dict = Depends(get_routing_info)):
    """Get quote for a specific option contract using only real market data - uses option_ws account"""
    try:
        quote_data = await pooled_client.get_option_quote(
            option_symbol=request.option_symbol,
            account_id=routing_info["account_id"] or "option_ws",
            routing_key=request.option_symbol
        )
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
        ) from e

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
async def get_multiple_option_quotes(request: MultiOptionQuoteRequest, routing_info: dict = Depends(get_routing_info)):
    """Get quotes for multiple option contracts using only real market data - uses option_ws account"""
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
            
        quotes_data = await pooled_client.get_multiple_option_quotes(
            option_symbols=request.option_symbols,
            account_id=routing_info["account_id"] or "option_ws",
            routing_key=request.option_symbols[0] if request.option_symbols else "batch_options"
        )
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
        ) from e

@router.get("/options/{underlying_symbol}/chain")
async def get_options_chain_by_symbol(
    underlying_symbol: str,
    expiration_date: Optional[str] = None,
    routing_info: dict = Depends(get_routing_info)
):
    """Get options chain for an underlying symbol - uses option_ws account"""
    try:
        chain_data = await pooled_client.get_options_chain(
            underlying_symbol=underlying_symbol.upper(),
            expiration_date=expiration_date,
            account_id=routing_info["account_id"] or "option_ws",
            routing_key=underlying_symbol
        )
        if "error" in chain_data:
            error_msg = chain_data.get("error", "Unknown error")
            logger.warning(f"Options chain unavailable for {underlying_symbol}: {error_msg}")
            
            # Provide helpful error message
            if "no real options chain data" in str(error_msg).lower():
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "error": error_msg,
                        "error_code": "OPTIONS_CHAIN_UNAVAILABLE", 
                        "underlying_symbol": underlying_symbol,
                        "expiration_date": expiration_date,
                        "message": "Options chain data may be temporarily unavailable. Try again in a few moments.",
                        "suggestion": "Options data availability varies by market hours and symbol liquidity"
                    }
                )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "error": error_msg,
                        "error_code": "OPTIONS_CHAIN_UNAVAILABLE",
                        "underlying_symbol": underlying_symbol,
                        "expiration_date": expiration_date,
                        "message": "No real options chain data available from Alpaca for this symbol"
                    }
                )
        return chain_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_options_chain_by_symbol for {underlying_symbol}: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"Internal server error while retrieving options chain: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "underlying_symbol": underlying_symbol,
                "expiration_date": expiration_date
            }
        ) from e

# Trading endpoints
@router.post("/stocks/order", 
    summary="Place Stock Order",
    description="""
    🔐 **AUTHENTICATION REQUIRED** - Protected endpoint (Internal network or JWT)
    
    Place a stock order with various order types and time in force options.
    
    **Bulk Place Feature:**
    Set `bulk_place: true` to place the same order for all configured accounts.
    
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
    
    **Example Single Account Order:**
    ```json
    {
        "symbol": "AAPL",
        "qty": 10,
        "side": "buy", 
        "type": "market",
        "time_in_force": "day",
        "bulk_place": false
    }
    ```
    
    **Example Bulk Order (All Accounts):**
    ```json
    {
        "symbol": "AAPL",
        "qty": 10,
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "bulk_place": true
    }
    ```
    
    **Single Account Response:**
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
    
    **Bulk Order Response:**
    ```json
    {
        "bulk_place": true,
        "total_accounts": 3,
        "successful_orders": 2,
        "failed_orders": 1,
        "results": [
            {
                "account_id": "account_1",
                "account_name": "Trading Account 1",
                "success": true,
                "order": { "id": "order_123", "symbol": "AAPL", "qty": 10, "side": "buy" }
            },
            {
                "account_id": "account_2",
                "success": false,
                "error": "Insufficient buying power"
            }
        ]
    }
    ```
    """)
async def place_stock_order(
    request: StockOrderRequest, 
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Place a stock order - supports both single account and bulk placement"""
    try:
        # Extract user information from auth_data - REQUIRED for security
        if routing_info["account_id"] is None:
            logger.error("Stock order attempt without account ID")
            raise HTTPException(status_code=400, detail="Account ID is required for order placement")
        user_id = None
        if auth_data and auth_data.get("user"):
            user_id = auth_data["user"].get("user_id")
        elif auth_data and auth_data.get("internal"):
            user_id = "internal_user"
        
        # Security check: Require user identification for all orders
        if not user_id:
            logger.error("Stock order attempt without user identification - SECURITY RISK")
            raise HTTPException(status_code=401, detail="User identification required for order placement")
        
        # 检查是否为批量下单
        if request.bulk_place:
            logger.info(f"Processing bulk stock order: {request.symbol} {request.qty} {request.side.value}")
            
            bulk_result = await pooled_client.bulk_place_stock_order(
                symbol=request.symbol.upper(),
                qty=request.qty,
                side=request.side.value,
                order_type=request.type.value,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
                time_in_force=request.time_in_force.value,
                user_id=user_id
            )
            
            return BulkOrderResponse(**bulk_result)
        
        # 单账户下单
        else:
            order_data = await pooled_client.place_stock_order(
                symbol=request.symbol.upper(),
                qty=request.qty,
                side=request.side.value,
                order_type=request.type.value,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
                time_in_force=request.time_in_force.value,
                account_id=routing_info["account_id"],
                routing_key=routing_info["routing_key"],
                user_id=user_id
            )
            if "error" in order_data:
                raise HTTPException(status_code=400, detail=order_data["error"])
            return OrderResponse(**order_data)
            
    except Exception as e:
        logger.error(f"Error in place_stock_order: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/options/order",
    summary="Place Options Order",
    description="""
    🔐 **AUTHENTICATION REQUIRED** - Place an options order (Internal network or JWT)
    
    **Bulk Place Feature:**
    Set `bulk_place: true` to place the same order for all configured accounts.
    
    **Example Single Account Order:**
    ```json
    {
        "option_symbol": "AAPL240216C00190000",
        "qty": 1,
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "bulk_place": false
    }
    ```
    
    **Example Bulk Order (All Accounts):**
    ```json
    {
        "option_symbol": "AAPL240216C00190000",
        "qty": 1,
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "bulk_place": true
    }
    ```
    """)
async def place_option_order(
    request: OptionOrderRequest, 
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Place an options order - supports both single account and bulk placement"""
    try:
        # Extract user information from auth_data - REQUIRED for security
        if routing_info["account_id"] is None:
            logger.error("Option order attempt without account ID - SECURITY RISK")
            raise HTTPException(status_code=400, detail="Account ID is required for order placement")
        user_id = None
        if auth_data and auth_data.get("user"):
            user_id = auth_data["user"].get("user_id")
        elif auth_data and auth_data.get("internal"):
            user_id = "internal_user"
        
        # Security check: Require user identification for all orders
        if not user_id:
            logger.error("Option order attempt without user identification - SECURITY RISK")
            raise HTTPException(status_code=401, detail="User identification required for order placement")
        
        # 检查是否为批量下单
        if request.bulk_place:
            logger.info(f"Processing bulk option order: {request.option_symbol} {request.qty} {request.side.value}")
            
            bulk_result = await pooled_client.bulk_place_option_order(
                option_symbol=request.option_symbol.upper(),
                qty=request.qty,
                side=request.side.value,
                order_type=request.type.value,
                limit_price=request.limit_price,
                time_in_force=request.time_in_force.value,
                user_id=user_id
            )
            
            return BulkOrderResponse(**bulk_result)
        
        # 单账户下单
        else:
            order_data = await pooled_client.place_option_order(
                option_symbol=request.option_symbol.upper(),
                qty=request.qty,
                side=request.side.value,
                order_type=request.type.value,
                limit_price=request.limit_price,
                time_in_force=request.time_in_force.value,
                account_id=routing_info["account_id"],
                routing_key=routing_info["routing_key"],
                user_id=user_id
            )
            if "error" in order_data:
                raise HTTPException(status_code=400, detail=order_data["error"])
            return order_data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in place_option_order: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

# Order management endpoints
@router.get("/orders", 
    summary="Get Orders",
    description="🔐 **AUTHENTICATION REQUIRED** - Get user's orders (Internal network or JWT)",
    response_model=List[OrderResponse])
async def get_orders(
    status: Optional[str] = None, 
    limit: int = 100,
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Get orders - uses connection pool"""
    try:
        if routing_info["account_id"] is None:
            logger.error("Account ID is required to get orders.")
            raise HTTPException(status_code=400, detail="Account ID is required for order retrieval")
        logger.info(f"getting orders for account {routing_info['account_id']} with status {status} and limit {limit}")
        orders = await pooled_client.get_orders(
            status=status, 
            limit=limit,
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        if orders and "error" in orders[0]:
            raise HTTPException(status_code=500, detail=orders[0]["error"])
        return [OrderResponse(**order) for order in orders if "error" not in order]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_orders: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.delete("/orders/{order_id}",
    summary="Cancel Order", 
    description="🔐 **AUTHENTICATION REQUIRED** - Cancel an order (Internal network or JWT)")
async def cancel_order(
    order_id: str, 
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Cancel an order - uses connection pool"""
    try:
        if routing_info["account_id"] is None:
            logger.error(f"Account ID is required to cancel order {order_id}.")
            raise HTTPException(status_code=400, detail="Account ID is required for order cancellation")
        logger.info(f"Cancelling order {order_id} for account {routing_info['account_id']}")
        if not order_id:
            logger.error("Order ID is required to cancel order.")
            raise HTTPException(status_code=400, detail="Order ID is required for cancellation")
        # Cancel the order using the pooled client
        result = await pooled_client.cancel_order(
            order_id=order_id,
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cancel_order: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

# Dashboard endpoint
@router.get("/dashboard/{account_name}", 
    summary="Get Trading Dashboard",
    description="""
    🔐 **AUTHENTICATION REQUIRED** - Get comprehensive trading dashboard (Internal network or JWT)
    
    Returns a complete dashboard view similar to Tiger API format, including:
    - Account details (cash, portfolio value, etc.)
    - Current holdings (stocks and options with P&L)
    - Trading history with daily summaries
    
    **Parameters:**
    - `account_name`: Account identifier for routing
    - `all_holdings`: Include all holdings (default: true)
    - `days`: Number of days for trading history and recent orders (default: 30)
    - `include_recent_orders`: Include recent orders in response (default: false)
    
    **Example Response:**
    ```json
    {
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
            "has_data": true
        }
    }
    ```
    """,
    response_model=DashboardResponse)
async def get_dashboard(
    account_name: str,
    all_holdings: bool = Query(True, description="Include all holdings"),
    days: int = Query(30, description="Number of days for trading history and recent orders"),
    include_recent_orders: bool = Query(False, description="Include recent orders in response"),
    routing_info: dict = Depends(get_routing_info),
    auth_data: dict = Depends(internal_or_jwt_auth)
):
    """Get comprehensive trading dashboard matching Tiger API format"""
    try:
        # Security: Require explicit account_id to prevent unauthorized access
        if not routing_info["account_id"]:
            raise HTTPException(
                status_code=400, 
                detail="account_id parameter is required"
            )
        
        logger.info(f"Getting dashboard for account {account_name} (ID: {routing_info['account_id']})")
        
        # Get account information
        account_data = await pooled_client.get_account(
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        if "error" in account_data:
            raise HTTPException(status_code=500, detail=account_data["error"])
        
        # Get positions
        positions = await pooled_client.get_positions(
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        if positions and "error" in positions[0]:
            raise HTTPException(status_code=500, detail=positions[0]["error"])
        
        # Get trading history
        trading_history = await pooled_client.get_trading_history(
            days=days,
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        
        # Get profit report
        profit_report_data = await pooled_client.get_profit_report(
            days=days,
            account_id=routing_info["account_id"],
            routing_key=routing_info["routing_key"]
        )
        
        # Get recent orders if requested
        recent_orders = []
        if include_recent_orders:
            try:
                # Use days parameter to determine how many orders to fetch
                # Estimate: assume max 10 orders per day, so days * 10 should be sufficient
                estimated_limit = max(days * 10, 50)  # At least 50 orders
                orders_data = await pooled_client.get_orders(
                    status="all",
                    limit=estimated_limit,
                    account_id=routing_info["account_id"],
                    routing_key=routing_info["routing_key"]
                )
                if orders_data and "error" not in orders_data[0]:
                    # Filter orders to only include those within the specified days
                    from datetime import datetime, timedelta
                    cutoff_date = datetime.now() - timedelta(days=days)
                    
                    filtered_orders = []
                    for order in orders_data:
                        try:
                            # Parse the submitted_at date to check if it's within the range
                            submitted_at_str = order.get('submitted_at', '')
                            if submitted_at_str:
                                # Use the same parsing logic as OrderResponse
                                import re
                                clean_date = re.sub(r'\s+(EDT|EST|PDT|PST|CDT|CST|MDT|MST|UTC|GMT)\s*$', '', submitted_at_str.strip())
                                order_date = datetime.fromisoformat(clean_date.replace(' ', 'T'))
                                if order_date >= cutoff_date:
                                    filtered_orders.append(order)
                        except (ValueError, TypeError):
                            # If we can't parse the date, include the order to be safe
                            filtered_orders.append(order)
                    
                    recent_orders = filtered_orders
                    logger.info(f"Retrieved {len(recent_orders)} recent orders for dashboard")
            except Exception as e:
                logger.warning(f"Failed to retrieve recent orders for dashboard: {e}")
                recent_orders = []
        
        # Transform account data to dashboard format
        account_details = DashboardAccountDetails(
            account_name=account_name,
            paper_trading=1 if account_data.get("pattern_day_trader") else 0,
            currency="USD",
            cash=account_data.get("cash", 0.0),
            net_liquidation=account_data.get("portfolio_value", 0.0)
        )
        
        # Transform positions to holdings format
        holdings = []
        for position in positions:
            if "error" not in position:
                # Apply all_holdings filter if needed
                if not all_holdings and position.get("qty", 0) == 0:
                    continue  # Skip zero quantity positions if all_holdings is False
                # Determine security type
                sec_type = "OPT" if position.get("asset_class") == "us_option" else "STK"
                
                # Parse option details if it's an option
                expiry = None
                strike = None
                right = None
                identifier = position.get("symbol", "")
                
                if sec_type == "OPT":
                    # Parse option symbol to extract details
                    # Format: SYMBOL[YY]MMDD[C/P]XXXXXXXX
                    symbol = position.get("symbol", "")
                    if len(symbol) >= 15:
                        try:
                            # Extract underlying symbol
                            date_start_idx = 0
                            for i, char in enumerate(symbol):
                                if char.isdigit():
                                    date_start_idx = i
                                    break
                            
                            if date_start_idx > 0 and len(symbol) >= date_start_idx + 7:
                                date_part = symbol[date_start_idx:date_start_idx + 6]
                                option_type_char = symbol[date_start_idx + 6]
                                strike_part = symbol[date_start_idx + 7:]
                                
                                expiry = f"20{date_part[:2]}-{date_part[2:4]}-{date_part[4:6]}"
                                strike = str(float(strike_part) / 1000)
                                right = "CALL" if option_type_char.upper() == 'C' else "PUT"
                                identifier = symbol
                        except Exception as e:
                            logger.warning(f"Failed to parse option symbol {symbol}: {e}")
                
                contract = ContractInfo(
                    symbol=position.get("symbol", ""),
                    currency="USD",
                    sec_type=sec_type,
                    expiry=expiry,
                    strike=strike,
                    right=right,
                    identifier=identifier
                )
                
                holding = HoldingInfo(
                    quantity=position.get("qty", 0.0),
                    average_cost=position.get("avg_entry_price", 0.0),
                    market_value=position.get("market_value", 0.0),
                    market_price=position.get("current_price", 0.0),
                    unrealized_pnl=position.get("unrealized_pl", 0.0),
                    realized_pnl=0.0,  # This would need to be calculated from trade history
                    contract=contract
                )
                holdings.append(holding)
        
        # Transform trading history
        daily_summaries = []
        if "daily_summary" in trading_history:
            for daily in trading_history["daily_summary"]:
                daily_summaries.append(DailySummary(
                    date=daily["date"],
                    net_profit=daily["net_profit"],
                    sold_qty=daily["sold_qty"],
                    commission=daily["commission"],
                    avg_sold_price=daily.get("avg_sold_price")
                ))
        
        trading_history_obj = TradingHistory(
            overall_profit=trading_history.get("overall_profit", 0.0),
            overall_commission=trading_history.get("overall_commission", 0.0),
            daily_summary=daily_summaries,
            has_data=trading_history.get("has_data", False)
        )
        
        # Build profit report
        from app.models import ProfitPeriod, ProfitChartData, ProfitReport
        
        # Daily profit period
        daily_period = ProfitPeriod(
            profit=profit_report_data.get("daily", {}).get("profit", 0.0),
            commission=profit_report_data.get("daily", {}).get("commission", 0.0),
            has_data=profit_report_data.get("daily", {}).get("has_data", False)
        )
        
        # Weekly profit period
        weekly_period = ProfitPeriod(
            profit=profit_report_data.get("weekly", {}).get("profit", 0.0),
            commission=profit_report_data.get("weekly", {}).get("commission", 0.0),
            has_data=profit_report_data.get("weekly", {}).get("has_data", False)
        )
        
        # Chart data
        chart_daily_summaries = []
        chart_data = profit_report_data.get("total_for_chart", {})
        if "daily_summary" in chart_data:
            for daily in chart_data["daily_summary"]:
                chart_daily_summaries.append(DailySummary(
                    date=daily["date"],
                    net_profit=daily["net_profit"],
                    sold_qty=daily["sold_qty"],
                    commission=daily["commission"],
                    avg_sold_price=daily.get("avg_sold_price")
                ))
        
        chart_data_obj = ProfitChartData(
            overall_profit=chart_data.get("overall_profit", 0.0),
            overall_commission=chart_data.get("overall_commission", 0.0),
            daily_summary=chart_daily_summaries,
            has_data=chart_data.get("has_data", False)
        )
        
        # Complete profit report
        profit_report = ProfitReport(
            daily=daily_period,
            weekly=weekly_period,
            total_for_chart=chart_data_obj
        )
        
        # Create dashboard response
        dashboard = DashboardResponse(
            account_details=account_details,
            holdings=holdings,
            trading_history=trading_history_obj,
            profit_report=profit_report,
            recent_orders=[OrderResponse(**order) for order in recent_orders] if recent_orders else None
        )
        
        logger.info(f"Dashboard generated for {account_name}: {len(holdings)} holdings, {len(daily_summaries)} trading days, {len(recent_orders) if recent_orders else 0} recent orders")
        return dashboard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_dashboard for {account_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
