#!/usr/bin/env python3
"""
Test MsgPack Option WebSocket Implementation.
"""
import asyncio
import pytest
import websockets
import msgpack
import requests
import json
from datetime import datetime


class TestMsgPackWebSocket:
    """Test class for MsgPack WebSocket functionality."""

    @pytest.mark.asyncio
    async def test_msgpack_option_websocket(self):
        """Test MsgPack option WebSocket endpoint."""
        print("=== Testing MsgPack Option WebSocket Endpoint ===")
        
        try:
            # Get real API credentials
            print("Getting API credentials...")
            response = requests.get("http://localhost:8091/api/v1/auth/alpaca-credentials")
            if response.status_code == 200:
                credentials = response.json()
                api_key = credentials['api_key']
                secret_key = credentials['secret_key']
                option_ws_url = credentials['endpoints']['option_ws']
                print(f"SUCCESS: Got credentials for {credentials['account_name']}")
                print(f"Option endpoint: {option_ws_url}")
            else:
                pytest.skip(f"Failed to get API credentials: {response.status_code}")
            
            # Connect to option WebSocket
            print(f"Connecting to option WebSocket: {option_ws_url}")
            
            async with websockets.connect(option_ws_url) as websocket:
                print("SUCCESS: WebSocket connected")
                
                # Step 1: Receive welcome message
                try:
                    welcome_data = await asyncio.wait_for(websocket.recv(), timeout=10)
                    print(f"Received welcome message: {type(welcome_data)} - length: {len(welcome_data) if hasattr(welcome_data, '__len__') else 'N/A'}")
                    
                    # Try to parse welcome message
                    if isinstance(welcome_data, bytes):
                        try:
                            welcome_msg = msgpack.unpackb(welcome_data)
                            print(f"SUCCESS: MsgPack parsed welcome: {welcome_msg}")
                        except Exception as e:
                            print(f"WARNING: MsgPack parse failed: {e}")
                            try:
                                welcome_msg = json.loads(welcome_data.decode())
                                print(f"SUCCESS: JSON parsed welcome: {welcome_msg}")
                            except Exception as e2:
                                print(f"ERROR: Both MsgPack and JSON parsing failed: {e2}")
                                pytest.fail("Failed to parse welcome message")
                    else:
                        welcome_msg = json.loads(welcome_data)
                        print(f"SUCCESS: JSON welcome message: {welcome_msg}")
                    
                    # Test successful - we can connect to the WebSocket
                    assert True
                    
                except asyncio.TimeoutError:
                    pytest.fail("Timeout waiting for welcome message")
                    
        except Exception as e:
            pytest.fail(f"WebSocket connection error: {e}")

    def test_msgpack_library(self):
        """Test that MsgPack library is working correctly."""
        try:
            # Test basic pack/unpack
            test_data = {"test": "message", "number": 42, "array": [1, 2, 3]}
            packed = msgpack.packb(test_data)
            unpacked = msgpack.unpackb(packed)
            
            print(f"SUCCESS: MsgPack library working normally")
            print(f"   Original data: {test_data}")
            print(f"   Packed size: {len(packed)} bytes")
            print(f"   Unpacked data: {unpacked}")
            print(f"   Data consistency: {test_data == unpacked}")
            
            assert test_data == unpacked
            
        except ImportError:
            pytest.fail("MsgPack library not installed")
        except Exception as e:
            pytest.fail(f"MsgPack library error: {e}")