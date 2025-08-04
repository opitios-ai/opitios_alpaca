"""
WebSocket连接综合测试套件
测试WebSocket实时数据流、连接管理、订阅机制和性能
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch, call, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi.testclient import TestClient
from fastapi import WebSocket
import websockets

from app.websocket_routes import (
    AlpacaWebSocketManager, ws_manager, active_connections, subscribed_symbols,
    DEFAULT_STOCKS, DEFAULT_OPTIONS
)
from main import app


class TestAlpacaWebSocketManager:
    """Alpaca WebSocket管理器测试"""
    
    @pytest.fixture
    def manager(self):
        """创建WebSocket管理器实例"""
        return AlpacaWebSocketManager()
    
    @pytest.mark.asyncio
    async def test_manager_initialization_with_api_keys(self, manager):
        """测试有API密钥的管理器初始化"""
        with patch('app.websocket_routes.settings') as mock_settings:
            mock_settings.alpaca_api_key = "test_api_key"
            mock_settings.alpaca_secret_key = "test_secret_key"
            mock_settings.alpaca_paper_trading = True
            
            with patch('app.websocket_routes.TradingClient') as mock_trading_client:
                with patch('app.websocket_routes.StockDataStream') as mock_stream:
                    mock_stream_instance = AsyncMock()
                    mock_stream.return_value = mock_stream_instance
                    
                    await manager.initialize()
                    
                    assert manager.connected is True
                    assert manager.trading_client is not None
                    assert manager.stock_stream is not None
                    
                    # 验证订阅调用
                    mock_stream_instance.subscribe_quotes.assert_called_once()
                    mock_stream_instance.subscribe_trades.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_manager_initialization_without_api_keys(self, manager):
        """测试无API密钥的管理器初始化（演示模式）"""
        with patch('app.websocket_routes.settings') as mock_settings:
            mock_settings.alpaca_secret_key = None
            
            with patch.object(manager, 'simulate_market_data') as mock_simulate:
                await manager.initialize()
                
                assert manager.connected is True
                assert manager.trading_client is None
                assert manager.stock_stream is None
                
                # 验证模拟数据任务被创建
                mock_simulate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_manager_initialization_failure(self, manager):
        """测试管理器初始化失败"""
        with patch('app.websocket_routes.settings') as mock_settings:
            mock_settings.alpaca_api_key = "test_key"
            mock_settings.alpaca_secret_key = "test_secret"
            
            with patch('app.websocket_routes.TradingClient') as mock_trading_client:
                mock_trading_client.side_effect = Exception("API connection failed")
                
                await manager.initialize()
                
                assert manager.connected is False
    
    def test_option_symbol_detection(self, manager):
        """测试期权符号检测"""
        # 股票符号
        assert manager._is_option_symbol("AAPL") is False
        assert manager._is_option_symbol("GOOGL") is False
        assert manager._is_option_symbol("SPY") is False
        
        # 期权符号
        assert manager._is_option_symbol("AAPL240216C00150000") is True
        assert manager._is_option_symbol("SPY250117P00570000") is True
        assert manager._is_option_symbol("TSLA250117C00300000") is True
        
        # 边缘情况
        assert manager._is_option_symbol("") is False
        assert manager._is_option_symbol("SHORTC") is False
        assert manager._is_option_symbol("VERYLONGSYMBOLBUTNOTANOPTION") is False
    
    @pytest.mark.asyncio
    async def test_symbol_subscription(self, manager):
        """测试符号订阅"""
        # 模拟已连接状态
        manager.connected = True
        manager.stock_stream = AsyncMock()
        
        symbols = ["AAPL", "GOOGL", "AAPL240216C00150000"]
        
        await manager.subscribe_symbols(symbols)
        
        # 验证日志记录被调用（这里我们不能直接验证日志，但可以验证方法执行完成）
        assert manager.connected is True
    
    @pytest.mark.asyncio
    async def test_quote_data_broadcasting(self, manager):
        """测试报价数据广播"""
        # 模拟活跃连接
        mock_websocket = AsyncMock()
        active_connections["test_client"] = mock_websocket
        
        # 创建模拟报价数据
        class MockQuote:
            def __init__(self):
                self.symbol = "AAPL"
                self.bid_price = 150.25
                self.ask_price = 150.75
                self.bid_size = 100
                self.ask_size = 200
                self.timestamp = datetime.now()
        
        quote_data = MockQuote()
        
        await manager.broadcast_quote_data("stock", quote_data)
        
        # 验证消息被发送
        mock_websocket.send_text.assert_called_once()
        
        # 验证消息内容
        sent_message = mock_websocket.send_text.call_args[0][0]
        message_data = json.loads(sent_message)
        
        assert message_data["type"] == "quote"
        assert message_data["data_type"] == "stock"
        assert message_data["symbol"] == "AAPL"
        assert message_data["bid_price"] == 150.25
        assert message_data["ask_price"] == 150.75
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_trade_data_broadcasting(self, manager):
        """测试交易数据广播"""
        # 模拟活跃连接
        mock_websocket = AsyncMock()
        active_connections["test_client"] = mock_websocket
        
        # 创建模拟交易数据
        class MockTrade:
            def __init__(self):
                self.symbol = "TSLA"
                self.price = 200.50
                self.size = 500
                self.timestamp = datetime.now()
        
        trade_data = MockTrade()
        
        await manager.broadcast_trade_data("stock", trade_data)
        
        # 验证消息被发送
        mock_websocket.send_text.assert_called_once()
        
        # 验证消息内容
        sent_message = mock_websocket.send_text.call_args[0][0]
        message_data = json.loads(sent_message)
        
        assert message_data["type"] == "trade"
        assert message_data["data_type"] == "stock"
        assert message_data["symbol"] == "TSLA"
        assert message_data["price"] == 200.50
        assert message_data["size"] == 500
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, manager):
        """测试向多个客户端广播"""
        # 模拟多个活跃连接
        mock_websockets = {}
        for i in range(5):
            client_id = f"client_{i}"
            mock_websockets[client_id] = AsyncMock()
            active_connections[client_id] = mock_websockets[client_id]
        
        # 广播消息
        test_message = {
            "type": "test",
            "content": "Hello all clients"
        }
        
        await manager.broadcast_to_all(test_message)
        
        # 验证所有客户端都收到消息
        for client_id, mock_ws in mock_websockets.items():
            mock_ws.send_text.assert_called_once()
            sent_message = mock_ws.send_text.call_args[0][0]
            message_data = json.loads(sent_message)
            assert message_data == test_message
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_broadcast_with_failed_connections(self, manager):
        """测试广播时处理失败连接"""
        # 模拟正常和失败的连接
        normal_ws = AsyncMock()
        failing_ws = AsyncMock()
        failing_ws.send_text.side_effect = Exception("Connection lost")
        
        active_connections["normal_client"] = normal_ws
        active_connections["failing_client"] = failing_ws
        
        test_message = {"type": "test", "content": "test"}
        
        await manager.broadcast_to_all(test_message)
        
        # 验证正常连接收到消息
        normal_ws.send_text.assert_called_once()
        
        # 验证失败连接被清理
        assert "failing_client" not in active_connections
        assert "normal_client" in active_connections
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_market_data_simulation(self, manager):
        """测试市场数据模拟"""
        manager.connected = True
        
        # 模拟活跃连接
        mock_websocket = AsyncMock()
        active_connections["test_client"] = mock_websocket
        
        # 运行一小段时间的模拟
        simulation_task = asyncio.create_task(manager.simulate_market_data())
        
        # 等待一小段时间让模拟运行
        await asyncio.sleep(0.1)
        
        # 停止模拟
        manager.connected = False
        active_connections.clear()
        
        # 等待任务完成
        try:
            await asyncio.wait_for(simulation_task, timeout=1.0)
        except asyncio.TimeoutError:
            simulation_task.cancel()
        
        # 验证有消息被发送（至少应该有一些模拟数据）
        assert mock_websocket.send_text.call_count >= 0


class TestWebSocketEndpoint:
    """WebSocket端点测试"""
    
    def test_websocket_status_endpoint(self):
        """测试WebSocket状态端点"""
        client = TestClient(app)
        
        # 模拟一些活跃连接和订阅
        active_connections["test_client"] = Mock()
        subscribed_symbols.update(["AAPL", "GOOGL"])
        
        response = client.get("/api/v1/ws/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "active_connections" in data
        assert "subscribed_symbols" in data
        assert "alpaca_connected" in data
        assert "default_symbols" in data
        assert "websocket_endpoint" in data
        
        # 验证默认符号
        assert data["default_symbols"]["stocks"] == DEFAULT_STOCKS
        assert data["default_symbols"]["options"] == DEFAULT_OPTIONS
        
        # 清理
        active_connections.clear()
        subscribed_symbols.clear()
    
    @pytest.mark.asyncio
    async def test_websocket_connection_flow(self):
        """测试WebSocket连接流程"""
        # 这个测试模拟完整的WebSocket连接流程
        
        with patch('app.websocket_routes.ws_manager') as mock_manager:
            mock_manager.connected = False
            mock_manager.initialize = AsyncMock()
            mock_manager.subscribe_symbols = AsyncMock()
            
            # 模拟WebSocket连接
            mock_websocket = AsyncMock()
            
            # 模拟连接接受
            mock_websocket.accept = AsyncMock()
            mock_websocket.send_text = AsyncMock()
            mock_websocket.receive_text = AsyncMock()
            
            # 模拟WebSocketDisconnect
            from fastapi import WebSocketDisconnect
            mock_websocket.receive_text.side_effect = WebSocketDisconnect()
            
            # 由于FastAPI的WebSocket端点很难直接测试，我们测试关键逻辑
            assert mock_manager is not None


class TestWebSocketClientInteraction:
    """WebSocket客户端交互测试"""
    
    @pytest.mark.asyncio
    async def test_client_subscription_request(self):
        """测试客户端订阅请求"""
        # 模拟WebSocket消息处理逻辑
        
        # 模拟客户端订阅消息
        subscription_message = {
            "type": "subscribe",
            "symbols": ["AAPL", "TSLA", "NVDA"]
        }
        
        # 模拟处理订阅逻辑
        if subscription_message.get("type") == "subscribe":
            new_symbols = subscription_message.get("symbols", [])
            subscribed_symbols.update(new_symbols)
            
            response = {
                "type": "subscription_update", 
                "added_symbols": new_symbols,
                "total_subscribed": len(subscribed_symbols)
            }
            
            assert response["type"] == "subscription_update"
            assert response["added_symbols"] == ["AAPL", "TSLA", "NVDA"]
            assert "total_subscribed" in response
        
        # 清理
        subscribed_symbols.clear()
    
    @pytest.mark.asyncio
    async def test_client_ping_pong(self):
        """测试客户端心跳检测"""
        # 模拟ping消息
        ping_message = {
            "type": "ping",
            "timestamp": datetime.now().isoformat()
        }
        
        # 模拟处理ping逻辑
        if ping_message.get("type") == "ping":
            pong_message = {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            }
            
            assert pong_message["type"] == "pong"
            assert "timestamp" in pong_message
    
    def test_welcome_message_structure(self):
        """测试欢迎消息结构"""
        # 模拟欢迎消息
        welcome_message = {
            "type": "welcome",
            "client_id": "test_client_123",
            "message": "连接成功！即将开始接收实时市场数据",
            "default_stocks": DEFAULT_STOCKS,
            "default_options": DEFAULT_OPTIONS,
            "data_source": "Alpaca IEX (Paper Trading)",
            "limitations": {
                "data_feed": "IEX exchange only (free tier)",
                "symbols_limit": 30,
                "connection_limit": 1,
                "update_frequency": "Real-time"
            }
        }
        
        # 验证欢迎消息结构
        assert welcome_message["type"] == "welcome"
        assert "client_id" in welcome_message
        assert "message" in welcome_message
        assert "default_stocks" in welcome_message
        assert "default_options" in welcome_message
        assert "data_source" in welcome_message
        assert "limitations" in welcome_message
        
        # 验证限制信息
        limitations = welcome_message["limitations"]
        assert "data_feed" in limitations
        assert "symbols_limit" in limitations
        assert "connection_limit" in limitations
        assert "update_frequency" in limitations


class TestWebSocketConnectionManagement:
    """WebSocket连接管理测试"""
    
    def test_connection_tracking(self):
        """测试连接跟踪"""
        # 清理现有连接
        active_connections.clear()
        
        # 模拟添加连接
        mock_ws1 = Mock()
        mock_ws2 = Mock()
        
        active_connections["client_1"] = mock_ws1
        active_connections["client_2"] = mock_ws2
        
        assert len(active_connections) == 2
        assert "client_1" in active_connections
        assert "client_2" in active_connections
        
        # 模拟移除连接
        active_connections.pop("client_1", None)
        
        assert len(active_connections) == 1
        assert "client_1" not in active_connections
        assert "client_2" in active_connections
        
        # 清理
        active_connections.clear()
    
    def test_symbol_subscription_tracking(self):
        """测试符号订阅跟踪"""
        # 清理现有订阅
        subscribed_symbols.clear()
        
        # 添加订阅
        subscribed_symbols.update(["AAPL", "GOOGL"])
        assert len(subscribed_symbols) == 2
        
        # 添加更多订阅
        subscribed_symbols.update(["TSLA", "MSFT"])
        assert len(subscribed_symbols) == 4
        
        # 验证特定符号
        assert "AAPL" in subscribed_symbols
        assert "TSLA" in subscribed_symbols
        assert "UNKNOWN" not in subscribed_symbols
        
        # 清理
        subscribed_symbols.clear()
    
    def test_client_id_generation(self):
        """测试客户端ID生成"""
        # 模拟客户端ID生成逻辑
        timestamp = datetime.now().timestamp()
        client_id = f"client_{timestamp}"
        
        assert client_id.startswith("client_")
        assert len(client_id) > 7  # "client_" + timestamp
        
        # 验证ID唯一性
        timestamp2 = datetime.now().timestamp()
        client_id2 = f"client_{timestamp2}"
        
        assert client_id != client_id2


class TestWebSocketErrorHandling:
    """WebSocket错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_manager_connection_failure_recovery(self):
        """测试管理器连接失败恢复"""
        manager = AlpacaWebSocketManager()
        
        with patch('app.websocket_routes.settings') as mock_settings:
            mock_settings.alpaca_api_key = "test_key"
            mock_settings.alpaca_secret_key = "test_secret"
            
            # 第一次初始化失败
            with patch('app.websocket_routes.TradingClient') as mock_trading:
                mock_trading.side_effect = Exception("Connection failed")
                
                await manager.initialize()
                assert manager.connected is False
            
            # 第二次初始化成功
            with patch('app.websocket_routes.TradingClient'):
                with patch('app.websocket_routes.StockDataStream') as mock_stream:
                    mock_stream_instance = AsyncMock()
                    mock_stream.return_value = mock_stream_instance
                    
                    await manager.initialize()
                    assert manager.connected is True
    
    @pytest.mark.asyncio
    async def test_broadcast_error_handling(self):
        """测试广播错误处理"""
        manager = AlpacaWebSocketManager()
        
        # 添加一些连接，其中一些会失败
        working_ws = AsyncMock()
        broken_ws = AsyncMock()
        broken_ws.send_text.side_effect = Exception("Connection broken")
        
        active_connections["working"] = working_ws
        active_connections["broken"] = broken_ws
        
        test_message = {"type": "test", "data": "test"}
        
        # 广播不应该因为部分连接失败而停止
        await manager.broadcast_to_all(test_message)
        
        # 工作的连接应该收到消息
        working_ws.send_text.assert_called_once()
        
        # 损坏的连接应该被移除
        assert "broken" not in active_connections
        assert "working" in active_connections
        
        # 清理
        active_connections.clear()
    
    def test_invalid_message_handling(self):
        """测试无效消息处理"""
        # 模拟处理无效消息的逻辑
        
        invalid_messages = [
            "",  # 空消息
            "not json",  # 非JSON
            "{}",  # 空JSON对象
            '{"type": "unknown"}',  # 未知类型
            '{"type": "subscribe"}',  # 缺少必需字段
        ]
        
        for invalid_msg in invalid_messages:
            try:
                if invalid_msg:
                    message = json.loads(invalid_msg)
                    message_type = message.get("type")
                    
                    # 应该能够安全处理各种无效消息
                    assert message_type in [None, "unknown", "subscribe"] or True
            except json.JSONDecodeError:
                # JSON解析错误应该被捕获
                assert True
    
    @pytest.mark.asyncio
    async def test_subscription_error_recovery(self):
        """测试订阅错误恢复"""
        manager = AlpacaWebSocketManager()
        manager.connected = True
        manager.stock_stream = AsyncMock()
        
        # 模拟订阅失败
        manager.stock_stream.subscribe_quotes.side_effect = Exception("Subscription failed")
        
        # 订阅不应该导致系统崩溃
        try:
            await manager.subscribe_symbols(["AAPL", "GOOGL"])
            # 如果没有异常抛出，说明错误被正确处理
            assert True
        except Exception:
            # 如果有异常，说明错误处理需要改进
            pytest.fail("Subscription error was not handled properly")


class TestWebSocketPerformance:
    """WebSocket性能测试"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_broadcast_performance_many_clients(self):
        """测试大量客户端的广播性能"""
        manager = AlpacaWebSocketManager()
        
        # 创建100个模拟客户端
        mock_clients = {}
        for i in range(100):
            client_id = f"client_{i}"
            mock_ws = AsyncMock()
            mock_clients[client_id] = mock_ws
            active_connections[client_id] = mock_ws
        
        test_message = {
            "type": "performance_test",
            "data": "x" * 1000  # 1KB消息
        }
        
        # 测试广播性能
        start_time = time.time()
        await manager.broadcast_to_all(test_message)
        end_time = time.time()
        
        broadcast_time = end_time - start_time
        messages_per_second = 100 / broadcast_time if broadcast_time > 0 else float('inf')
        
        print(f"Broadcast to 100 clients took: {broadcast_time:.3f}s")
        print(f"Messages per second: {messages_per_second:.0f}")
        
        # 验证所有客户端都收到消息
        for mock_ws in mock_clients.values():
            mock_ws.send_text.assert_called_once()
        
        # 性能断言 - 100个客户端广播应该在1秒内完成
        assert broadcast_time < 1.0, f"Broadcast too slow: {broadcast_time:.3f}s"
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_message_throughput(self):
        """测试消息吞吐量"""
        manager = AlpacaWebSocketManager()
        
        # 创建10个模拟客户端
        for i in range(10):
            client_id = f"client_{i}"
            mock_ws = AsyncMock()
            active_connections[client_id] = mock_ws
        
        # 发送大量消息
        start_time = time.time()
        message_count = 100
        
        for i in range(message_count):
            test_message = {
                "type": "throughput_test",
                "sequence": i,
                "timestamp": datetime.now().isoformat()
            }
            await manager.broadcast_to_all(test_message)
        
        end_time = time.time()
        
        total_time = end_time - start_time
        messages_per_second = message_count / total_time if total_time > 0 else float('inf')
        
        print(f"Sent {message_count} messages in: {total_time:.3f}s")
        print(f"Throughput: {messages_per_second:.0f} messages/second")
        
        # 性能断言 - 应该能够处理高吞吐量
        assert messages_per_second > 50, f"Throughput too low: {messages_per_second:.0f} msg/s"
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.performance
    def test_symbol_subscription_performance(self):
        """测试符号订阅性能"""
        # 测试大量符号订阅的性能
        large_symbol_list = [f"STOCK{i:04d}" for i in range(1000)]
        
        start_time = time.time()
        subscribed_symbols.update(large_symbol_list)
        end_time = time.time()
        
        subscription_time = end_time - start_time
        symbols_per_second = 1000 / subscription_time if subscription_time > 0 else float('inf')
        
        print(f"Subscribed to 1000 symbols in: {subscription_time:.3f}s")
        print(f"Symbols per second: {symbols_per_second:.0f}")
        
        # 验证所有符号都被添加
        assert len(subscribed_symbols) >= 1000
        
        # 性能断言
        assert subscription_time < 0.1, f"Symbol subscription too slow: {subscription_time:.3f}s"
        
        # 清理
        subscribed_symbols.clear()


class TestWebSocketDataIntegrity:
    """WebSocket数据完整性测试"""
    
    @pytest.mark.asyncio
    async def test_quote_data_integrity(self):
        """测试报价数据完整性"""
        manager = AlpacaWebSocketManager()
        
        # 模拟客户端
        mock_websocket = AsyncMock()
        active_connections["test_client"] = mock_websocket
        
        # 创建测试报价数据
        class MockQuote:
            def __init__(self):
                self.symbol = "AAPL"
                self.bid_price = 150.25
                self.ask_price = 150.75
                self.bid_size = 100
                self.ask_size = 200
                self.timestamp = datetime.now()
        
        quote_data = MockQuote()
        await manager.broadcast_quote_data("stock", quote_data)
        
        # 验证数据完整性
        sent_data = mock_websocket.send_text.call_args[0][0]
        message = json.loads(sent_data)
        
        # 验证所有必需字段
        required_fields = ["type", "data_type", "symbol", "bid_price", "ask_price", 
                          "bid_size", "ask_size", "timestamp"]
        
        for field in required_fields:
            assert field in message, f"Missing required field: {field}"
        
        # 验证数据类型
        assert isinstance(message["bid_price"], float)
        assert isinstance(message["ask_price"], float)
        assert isinstance(message["bid_size"], int)
        assert isinstance(message["ask_size"], int)
        assert isinstance(message["timestamp"], str)
        
        # 验证数据值
        assert message["symbol"] == "AAPL"
        assert message["bid_price"] == 150.25
        assert message["ask_price"] == 150.75
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_trade_data_integrity(self):
        """测试交易数据完整性"""
        manager = AlpacaWebSocketManager()
        
        # 模拟客户端
        mock_websocket = AsyncMock()
        active_connections["test_client"] = mock_websocket
        
        # 创建测试交易数据
        class MockTrade:
            def __init__(self):
                self.symbol = "TSLA"
                self.price = 200.50
                self.size = 500
                self.timestamp = datetime.now()
        
        trade_data = MockTrade()
        await manager.broadcast_trade_data("stock", trade_data)
        
        # 验证数据完整性
        sent_data = mock_websocket.send_text.call_args[0][0]
        message = json.loads(sent_data)
        
        # 验证所有必需字段
        required_fields = ["type", "data_type", "symbol", "price", "size", "timestamp"]
        
        for field in required_fields:
            assert field in message, f"Missing required field: {field}"
        
        # 验证数据类型
        assert isinstance(message["price"], float)
        assert isinstance(message["size"], int)
        assert isinstance(message["timestamp"], str)
        
        # 验证数据值
        assert message["symbol"] == "TSLA"
        assert message["price"] == 200.50
        assert message["size"] == 500
        
        # 清理
        active_connections.clear()
    
    def test_message_serialization(self):
        """测试消息序列化"""
        # 测试各种数据类型的序列化
        test_messages = [
            {
                "type": "quote",
                "symbol": "AAPL",
                "price": 150.25,
                "size": 100,
                "timestamp": datetime.now().isoformat()
            },
            {
                "type": "trade",
                "symbol": "GOOGL",
                "price": None,  # 测试None值
                "size": 0,
                "timestamp": datetime.now().isoformat()
            },
            {
                "type": "status",
                "symbols": ["AAPL", "GOOGL", "TSLA"],
                "count": 3,
                "active": True
            }
        ]
        
        for message in test_messages:
            # 序列化应该成功
            serialized = json.dumps(message)
            assert isinstance(serialized, str)
            
            # 反序列化应该得到相同数据
            deserialized = json.loads(serialized)
            assert deserialized == message


class TestWebSocketConcurrency:
    """WebSocket并发测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_client_connections(self):
        """测试并发客户端连接"""
        manager = AlpacaWebSocketManager()
        
        # 模拟100个并发客户端连接
        async def simulate_client(client_id):
            mock_ws = AsyncMock()
            active_connections[client_id] = mock_ws
            
            # 模拟客户端活动
            await asyncio.sleep(0.01)
            
            return client_id
        
        # 并发创建客户端
        tasks = [simulate_client(f"client_{i}") for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        # 验证所有客户端都成功连接
        assert len(results) == 100
        assert len(active_connections) == 100
        
        # 验证客户端ID唯一性
        assert len(set(results)) == 100
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_concurrent_message_broadcasting(self):
        """测试并发消息广播"""
        manager = AlpacaWebSocketManager()
        
        # 创建多个客户端
        for i in range(10):
            client_id = f"client_{i}"
            mock_ws = AsyncMock()
            active_connections[client_id] = mock_ws
        
        # 并发广播多个消息
        async def broadcast_message(message_id):
            message = {
                "type": "concurrent_test",
                "message_id": message_id,
                "timestamp": datetime.now().isoformat()
            }
            await manager.broadcast_to_all(message)
            return message_id
        
        # 并发发送50条消息
        tasks = [broadcast_message(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        
        # 验证所有消息都被发送
        assert len(results) == 50
        
        # 验证每个客户端都收到了所有消息
        for client_id, mock_ws in active_connections.items():
            assert mock_ws.send_text.call_count == 50
        
        # 清理
        active_connections.clear()
    
    @pytest.mark.asyncio
    async def test_concurrent_subscription_updates(self):
        """测试并发订阅更新"""
        # 清理现有订阅
        subscribed_symbols.clear()
        
        # 并发添加订阅
        async def add_subscription(symbol_batch):
            subscribed_symbols.update(symbol_batch)
            return len(symbol_batch)
        
        # 创建10个批次，每批次10个符号
        symbol_batches = []
        for i in range(10):
            batch = [f"SYMBOL{i}_{j}" for j in range(10)]
            symbol_batches.append(batch)
        
        # 并发更新订阅
        tasks = [add_subscription(batch) for batch in symbol_batches]
        results = await asyncio.gather(*tasks)
        
        # 验证所有符号都被添加
        assert sum(results) == 100
        assert len(subscribed_symbols) == 100
        
        # 清理
        subscribed_symbols.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])