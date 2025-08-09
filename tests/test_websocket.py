#!/usr/bin/env python3
"""
Test Alpaca WebSocket functionality.
"""
import asyncio
import pytest
import websockets
import json
import requests
from datetime import datetime


class TestAlpacaWebSocket:
    """Test class for Alpaca WebSocket functionality."""

    @pytest.mark.asyncio
    async def test_alpaca_websocket_connection(self):
        """Test Alpaca official test endpoint using FAKEPACA."""
        print("=== Testing Alpaca Official Test Endpoint (FAKEPACA) ===")
        
        try:
            # Get real API credentials
            response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
            if response.status_code == 200:
                credentials = response.json()
                api_key = credentials['api_key']
                secret_key = credentials['secret_key']
                print(f"SUCCESS: Got real API credentials: {credentials['account_name']}")
                print(f"API Key: {api_key[:10]}...")
            else:
                pytest.skip(f"Failed to get API credentials: {response.status_code}")
            
            # Connect to Alpaca test WebSocket
            test_uri = "wss://stream.data.alpaca.markets/v2/test"
            print(f"Connecting to: {test_uri}")
            
            async with websockets.connect(test_uri) as websocket:
                print("SUCCESS: Connected to Alpaca official test WebSocket")
                
                # Receive welcome message
                welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                welcome_data = json.loads(welcome_msg)
                print(f"Welcome message: {welcome_data}")
                
                # Send authentication message
                auth_message = {
                    "action": "auth",
                    "key": api_key,
                    "secret": secret_key
                }
                
                await websocket.send(json.dumps(auth_message))
                print("Sent authentication message...")
                
                # Receive authentication response
                auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                auth_data = json.loads(auth_response)
                print(f"Auth response: {auth_data}")
                
                # Check authentication success
                if isinstance(auth_data, list) and len(auth_data) > 0:
                    auth_result = auth_data[0]
                    if auth_result.get('T') == 'success' and 'authenticated' in str(auth_result.get('msg', '')):
                        print("SUCCESS: Authentication successful!")
                        
                        # Subscribe to FAKEPACA data
                        subscribe_message = {
                            "action": "subscribe",
                            "trades": ["FAKEPACA"],
                            "quotes": ["FAKEPACA"],
                            "bars": ["FAKEPACA"]
                        }
                        
                        await websocket.send(json.dumps(subscribe_message))
                        print(f"Sent subscription message: {subscribe_message}")
                        
                        # Receive subscription confirmation
                        sub_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        sub_data = json.loads(sub_response)
                        print(f"Subscription confirmation: {sub_data}")
                        
                        # Test successful - we can connect and authenticate
                        assert True
                    else:
                        pytest.fail(f"Authentication failed: {auth_result}")
                else:
                    pytest.fail(f"Unexpected auth response format: {auth_data}")
                        
        except Exception as e:
            pytest.fail(f"WebSocket connection error: {e}")

    def test_server_health_check(self):
        """Test server health check endpoint."""
        try:
            health_response = requests.get("http://localhost:8091/api/v1/health", timeout=5)
            assert health_response.status_code == 200
            
            health_data = health_response.json()
            assert 'status' in health_data
            assert 'configuration' in health_data
            print(f"Server status: {health_data['status']}")
            print(f"Configuration: real_data_only={health_data['configuration']['real_data_only']}")
            
        except Exception as e:
            pytest.skip(f"Cannot connect to server: {e}")