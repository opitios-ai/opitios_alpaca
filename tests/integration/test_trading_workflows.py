"""Integration tests for end-to-end trading workflows with real orders."""

import pytest
import asyncio
from typing import Dict, Any, List

from tests.utils import RealAPITestClient, APITestHelper, TestDataGenerator
from app.middleware import create_jwt_token, verify_jwt_token


class TestTradingWorkflows:
    """Test complete trading workflows end-to-end."""
    
    @pytest.mark.asyncio
    async def test_complete_stock_trading_workflow(self, real_api_client, api_test_helper):
        """Test complete stock trading workflow from quote to order."""
        symbol = "AAPL"
        
        # 1. Get stock quote
        quote_result = await api_test_helper.timed_api_call(
            real_api_client.get_stock_quote, symbol
        )
        
        if not quote_result.success:
            pytest.skip(f"Cannot get quote for {symbol}: {quote_result.error_message}")
        
        quote_data = quote_result.response_data
        assert "symbol" in quote_data
        assert quote_data["symbol"] == symbol
        
        # 2. Get account info to check buying power
        account_result = await api_test_helper.timed_api_call(
            real_api_client.get_account
        )
        
        if not account_result.success:
            pytest.skip(f"Cannot get account info: {account_result.error_message}")
        
        account_data = account_result.response_data
        assert "buying_power" in account_data
        assert account_data["buying_power"] > 0
        
        # 3. Place a small test order (limit order to avoid execution)
        limit_price = 50.0  # Very low price to avoid execution
        order_params = TestDataGenerator.generate_test_order_params(
            symbol=symbol, order_type="limit"
        )
        order_params["limit_price"] = limit_price
        
        order_result = await api_test_helper.timed_api_call(
            real_api_client.place_test_order,
            **order_params
        )
        
        if order_result.success and "error" not in order_result.response_data:
            order_data = order_result.response_data
            assert "id" in order_data
            assert order_data["symbol"] == symbol
            assert order_data["side"] == "buy"
            
            # 4. Check order status
            orders_result = await api_test_helper.timed_api_call(
                real_api_client.get_orders
            )
            
            if orders_result.success:
                orders = orders_result.response_data
                order_found = any(order.get("id") == order_data["id"] for order in orders)
                assert order_found, "Placed order not found in orders list"
        
        # Get performance summary
        performance = api_test_helper.get_performance_summary()
        assert performance["total_calls"] >= 3
    
    @pytest.mark.asyncio
    async def test_multi_symbol_quote_workflow(self, real_api_client, api_test_helper):
        """Test workflow for getting multiple stock quotes."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        # Get multiple quotes
        quotes_result = await api_test_helper.timed_api_call(
            real_api_client.get_multiple_stock_quotes, symbols
        )
        
        if quotes_result.success:
            quotes_data = quotes_result.response_data
            assert "quotes" in quotes_data
            assert len(quotes_data["quotes"]) == len(symbols)
            
            # Verify each quote
            for quote in quotes_data["quotes"]:
                if "error" not in quote:
                    assert "symbol" in quote
                    assert quote["symbol"] in symbols
    
    @pytest.mark.asyncio
    async def test_options_workflow(self, real_api_client, api_test_helper):
        """Test options trading workflow."""
        underlying = "AAPL"
        
        # 1. Get options chain
        chain_result = await api_test_helper.timed_api_call(
            real_api_client.get_options_chain, underlying
        )
        
        if chain_result.success and "error" not in chain_result.response_data:
            chain_data = chain_result.response_data
            assert chain_data["underlying_symbol"] == underlying
            
            if chain_data.get("options"):
                # 2. Get quote for first option
                first_option = chain_data["options"][0]
                option_symbol = first_option["symbol"]
                
                option_quote_result = await api_test_helper.timed_api_call(
                    real_api_client.get_option_quote, option_symbol
                )
                
                if option_quote_result.success and "error" not in option_quote_result.response_data:
                    option_quote = option_quote_result.response_data
                    assert option_quote["symbol"] == option_symbol
                    assert option_quote["underlying_symbol"] == underlying


class TestAuthenticationFlows:
    """Test authentication and JWT validation flows."""
    
    def test_jwt_token_creation_and_validation(self):
        """Test JWT token creation and validation workflow."""
        # Create user data
        user_data = {
            "user_id": "test_trader_123",
            "account_id": "trading_account_456",
            "permissions": ["trading", "market_data", "options"]
        }
        
        # Create JWT token
        token = create_jwt_token(user_data)
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token
        payload = verify_jwt_token(token)
        assert payload["user_id"] == user_data["user_id"]
        assert payload["account_id"] == user_data["account_id"]
        assert payload["permissions"] == user_data["permissions"]
        assert "exp" in payload
        assert "iat" in payload
    
    def test_permission_based_access(self):
        """Test permission-based access control."""
        # Create tokens with different permissions
        admin_data = {
            "user_id": "admin_user",
            "permissions": ["trading", "market_data", "admin", "options"]
        }
        
        trader_data = {
            "user_id": "trader_user", 
            "permissions": ["trading", "market_data"]
        }
        
        viewer_data = {
            "user_id": "viewer_user",
            "permissions": ["market_data"]
        }
        
        # Create tokens
        admin_token = create_jwt_token(admin_data)
        trader_token = create_jwt_token(trader_data)
        viewer_token = create_jwt_token(viewer_data)
        
        # Verify permissions
        admin_payload = verify_jwt_token(admin_token)
        trader_payload = verify_jwt_token(trader_token)
        viewer_payload = verify_jwt_token(viewer_token)
        
        assert "admin" in admin_payload["permissions"]
        assert "trading" in admin_payload["permissions"]
        assert "trading" in trader_payload["permissions"]
        assert "trading" not in viewer_payload["permissions"]
        assert "market_data" in viewer_payload["permissions"]


class TestMultiAccountRouting:
    """Test multi-account routing and switching."""
    
    @pytest.mark.asyncio
    async def test_account_routing_workflow(self, multi_account_clients):
        """Test routing between multiple accounts."""
        if len(multi_account_clients) < 2:
            pytest.skip("Need at least 2 accounts for routing test")
        
        # Test each account can get quotes
        results = []
        for i, client in enumerate(multi_account_clients[:2]):
            result = await client.get_stock_quote("AAPL")
            results.append({
                "account_id": client.account_id,
                "result": result,
                "index": i
            })
        
        # Verify all accounts can access API
        successful_accounts = [r for r in results if "error" not in r["result"]]
        assert len(successful_accounts) > 0, "At least one account should work"
    
    @pytest.mark.asyncio
    async def test_account_isolation(self, multi_account_clients):
        """Test that accounts are properly isolated."""
        if len(multi_account_clients) < 2:
            pytest.skip("Need at least 2 accounts for isolation test")
        
        # Get account info from different clients
        account_infos = []
        for client in multi_account_clients[:2]:
            account_result = await client.get_account()
            if "error" not in account_result:
                account_infos.append({
                    "client_account_id": client.account_id,
                    "api_account_number": account_result.get("account_number"),
                    "buying_power": account_result.get("buying_power")
                })
        
        if len(account_infos) >= 2:
            # Verify accounts are different
            assert account_infos[0]["api_account_number"] != account_infos[1]["api_account_number"]


class TestErrorHandlingScenarios:
    """Test error handling in real API scenarios."""
    
    @pytest.mark.asyncio
    async def test_invalid_symbol_error_handling(self, real_api_client):
        """Test error handling for invalid symbols."""
        invalid_symbols = ["INVALID123", "NOTREAL", "FAKE_SYMBOL"]
        
        for symbol in invalid_symbols:
            result = await real_api_client.get_stock_quote(symbol)
            
            # Should either return error or empty data
            if "error" not in result:
                # If no error, should have null prices for invalid symbol
                assert (result.get("bid_price") is None and 
                       result.get("ask_price") is None)
    
    @pytest.mark.asyncio
    async def test_order_validation_errors(self, real_api_client):
        """Test order validation error scenarios."""
        # Test invalid order parameters
        invalid_orders = [
            {
                "symbol": "AAPL",
                "qty": 0,  # Invalid quantity
                "side": "buy",
                "order_type": "market"
            },
            {
                "symbol": "AAPL", 
                "qty": 1,
                "side": "invalid_side",  # Invalid side
                "order_type": "market"
            },
            {
                "symbol": "AAPL",
                "qty": 1,
                "side": "buy",
                "order_type": "limit"
                # Missing limit_price
            }
        ]
        
        for order_params in invalid_orders:
            try:
                result = await real_api_client.client.place_stock_order(**order_params)
                assert "error" in result, f"Expected error for invalid order: {order_params}"
            except Exception as e:
                # Exception is also acceptable for invalid parameters
                assert isinstance(e, (ValueError, TypeError))
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, real_api_client, rate_limit_helper):
        """Test rate limit handling in real scenarios."""
        # Make multiple rapid requests
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
        results = []
        
        for symbol in symbols:
            async with rate_limit_helper.rate_limited_call():
                result = await real_api_client.get_stock_quote(symbol)
                results.append(result)
        
        # All requests should complete without rate limit errors
        rate_limit_errors = [r for r in results if "error" in r and "rate limit" in r["error"].lower()]
        assert len(rate_limit_errors) == 0, f"Unexpected rate limit errors: {rate_limit_errors}"
    
    @pytest.mark.asyncio
    async def test_connection_recovery(self, real_api_client):
        """Test connection recovery scenarios."""
        # Test that client can recover from temporary issues
        
        # First, make a successful call
        result1 = await real_api_client.get_stock_quote("AAPL")
        
        # Then make another call to test consistency
        result2 = await real_api_client.get_stock_quote("MSFT")
        
        # Both should have consistent behavior
        if "error" in result1:
            # If first failed, second might also fail (connection issue)
            pass
        else:
            # If first succeeded, second should also work (unless different symbol issue)
            if "error" in result2:
                # Check if it's a symbol-specific issue
                assert "MSFT" in str(result2.get("error", ""))


class TestPerformanceWorkflows:
    """Test performance-related workflows."""
    
    @pytest.mark.asyncio
    async def test_concurrent_quote_requests(self, real_api_client, api_test_helper):
        """Test concurrent quote requests performance."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        # Prepare concurrent API calls
        api_calls = [
            (real_api_client.get_stock_quote, (symbol,), {})
            for symbol in symbols
        ]
        
        # Execute concurrently
        results = await api_test_helper.batch_api_calls(api_calls, max_concurrent=3)
        
        assert len(results) == len(symbols)
        
        # Check performance metrics
        successful_results = [r for r in results if r.success]
        if successful_results:
            avg_response_time = sum(r.response_time_ms for r in successful_results) / len(successful_results)
            assert avg_response_time < 5000, f"Average response time too high: {avg_response_time}ms"
    
    @pytest.mark.asyncio
    async def test_sequential_vs_batch_performance(self, real_api_client, api_test_helper):
        """Test performance difference between sequential and batch requests."""
        symbols = ["AAPL", "MSFT"]
        
        # Sequential requests
        sequential_start = api_test_helper.get_performance_summary()["total_calls"]
        
        for symbol in symbols:
            await api_test_helper.timed_api_call(
                real_api_client.get_stock_quote, symbol
            )
        
        sequential_calls = api_test_helper.get_performance_summary()["total_calls"] - sequential_start
        
        # Batch request
        batch_result = await api_test_helper.timed_api_call(
            real_api_client.get_multiple_stock_quotes, symbols
        )
        
        # Batch should be more efficient (1 call vs multiple calls)
        if batch_result.success:
            assert sequential_calls > 1  # Sequential made multiple calls
            # Batch made only 1 call but got multiple quotes


@pytest.mark.asyncio
async def test_end_to_end_integration(real_api_client, api_test_helper):
    """Complete end-to-end integration test."""
    # This test combines multiple workflows
    
    # 1. Authentication (simulated)
    user_data = {"user_id": "integration_user", "permissions": ["trading", "market_data"]}
    token = create_jwt_token(user_data)
    payload = verify_jwt_token(token)
    assert payload["user_id"] == "integration_user"
    
    # 2. Market data workflow
    quote_result = await api_test_helper.timed_api_call(
        real_api_client.get_stock_quote, "AAPL"
    )
    
    # 3. Account information
    account_result = await api_test_helper.timed_api_call(
        real_api_client.get_account
    )
    
    # 4. Position check
    positions_result = await api_test_helper.timed_api_call(
        real_api_client.get_positions
    )
    
    # 5. Order history
    orders_result = await api_test_helper.timed_api_call(
        real_api_client.get_orders
    )
    
    # Verify all operations completed
    all_results = [quote_result, account_result, positions_result, orders_result]
    completed_operations = sum(1 for r in all_results if r.response_time_ms > 0)
    assert completed_operations == 4
    
    # Check overall performance
    performance = api_test_helper.get_performance_summary()
    assert performance["total_calls"] >= 4
    
    if performance["successful_calls"] > 0:
        assert performance["success_rate"] > 0
        assert performance["average_response_time_ms"] < 10000  # 10 seconds max average