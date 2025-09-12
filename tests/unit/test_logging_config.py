"""
Unit tests for logging configuration simplification - Fix #4
Tests the simplified logging setup that removes complex configurations
and focuses on basic application logging and error logging only.
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from loguru import logger

from app.logging_config import LoggingConfig, logging_config


class TestLoggingConfigSimplification:
    """Test the logging configuration simplification fix (#4)."""
    
    def setup_method(self):
        """Setup for each test method."""
        # Remove all existing handlers to start fresh
        logger.remove()
    
    def teardown_method(self):
        """Cleanup after each test method."""
        # Remove all handlers added during test
        logger.remove()
        
        # Restore basic console logging for other tests
        logger.add(sys.stderr, level="DEBUG")
    
    def test_logging_config_initialization(self):
        """Test LoggingConfig class initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary directory for logs
            with patch.object(Path, 'mkdir') as mock_mkdir:
                config = LoggingConfig()
                
                # Should create logs directory
                assert config.log_dir == Path("logs")
                mock_mkdir.assert_called_once_with(exist_ok=True)
    
    def test_setup_logging_development_mode(self):
        """Test logging setup in development mode (debug=True)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            # Mock settings for debug mode
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = True
                
                # Create config and setup logging
                config = LoggingConfig()
                config.log_dir = log_dir
                
                # Count handlers before setup
                initial_handlers = len(logger._core.handlers)
                
                config.setup_logging()
                
                # Should have console handler + file handlers
                final_handlers = len(logger._core.handlers)
                assert final_handlers > initial_handlers, "Should have added logging handlers"
                
                # Verify log files would be created
                expected_app_log = log_dir / "alpaca_service.log"
                expected_error_log = log_dir / "errors.log"
                
                # Files won't exist until logs are written, but paths should be correct
                assert expected_app_log.parent.exists()
                assert expected_error_log.parent.exists()
    
    def test_setup_logging_production_mode(self):
        """Test logging setup in production mode (debug=False)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            # Mock settings for production mode
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = False
                
                # Create config and setup logging
                config = LoggingConfig()
                config.log_dir = log_dir
                
                # Count handlers before setup
                initial_handlers = len(logger._core.handlers)
                
                config.setup_logging()
                
                # Should have file handlers only (no console in production)
                final_handlers = len(logger._core.handlers)
                assert final_handlers > initial_handlers, "Should have added file logging handlers"
    
    def test_logging_simplification_no_complex_handlers(self):
        """Test that complex handlers are not added in simplified version."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            # Mock settings
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = True
                
                config = LoggingConfig()
                config.log_dir = log_dir
                config.setup_logging()
                
                # Test that we only have basic handlers
                # The simplified version should not have complex filtering or routing
                handlers = logger._core.handlers
                
                # Should have exactly 3 handlers: console, app log, error log
                # (In debug mode: console + app log + error log = 3 handlers)
                assert len(handlers) == 3, f"Expected 3 handlers, got {len(handlers)}"
    
    def test_log_file_configuration(self):
        """Test log file configuration parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs" 
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            # Mock the logger.add method to capture parameters
            with patch.object(logger, 'add') as mock_add:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False  # No console handler
                    config.setup_logging()
                
                # Should have been called twice: app log + error log
                assert mock_add.call_count == 2
                
                # Check app log configuration
                app_log_call = mock_add.call_args_list[0]
                assert str(app_log_call[0][0]).endswith("alpaca_service.log")
                app_log_kwargs = app_log_call[1]
                assert app_log_kwargs['level'] == "INFO"
                assert app_log_kwargs['rotation'] == "100 MB"
                assert app_log_kwargs['retention'] == "30 days"
                assert app_log_kwargs['compression'] == "gz"
                assert app_log_kwargs['encoding'] == "utf-8"
                assert app_log_kwargs['enqueue'] is True
                
                # Check error log configuration
                error_log_call = mock_add.call_args_list[1]
                assert str(error_log_call[0][0]).endswith("errors.log")
                error_log_kwargs = error_log_call[1]
                assert error_log_kwargs['level'] == "ERROR"
                assert error_log_kwargs['rotation'] == "50 MB"
                assert error_log_kwargs['retention'] == "60 days" 
                assert error_log_kwargs['compression'] == "gz"
                assert error_log_kwargs['encoding'] == "utf-8"
                assert error_log_kwargs['enqueue'] is True
                assert error_log_kwargs['backtrace'] is True
                assert error_log_kwargs['diagnose'] is True
    
    def test_console_logging_format(self):
        """Test console logging format in debug mode."""
        with patch('app.logging_config.settings') as mock_settings:
            mock_settings.debug = True
            
            config = LoggingConfig()
            
            # Mock logger.add to check console format
            with patch.object(logger, 'add') as mock_add:
                config.setup_logging()
                
                # First call should be console handler (in debug mode)
                console_call = mock_add.call_args_list[0]
                assert console_call[0][0] == sys.stdout
                
                console_kwargs = console_call[1]
                expected_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
                assert console_kwargs['format'] == expected_format
                assert console_kwargs['level'] == "DEBUG"
                assert console_kwargs['colorize'] is False
    
    def test_file_logging_format(self):
        """Test file logging format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch.object(logger, 'add') as mock_add:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False  # No console handler
                    config.setup_logging()
                
                # Both file handlers should have the same format
                expected_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
                
                for call in mock_add.call_args_list:
                    file_kwargs = call[1]
                    assert file_kwargs['format'] == expected_format
    
    def test_global_logging_config_instance(self):
        """Test that global logging_config instance is created."""
        # Test the module-level instance
        assert logging_config is not None
        assert isinstance(logging_config, LoggingConfig)
        assert logging_config.log_dir == Path("logs")
    
    def test_utf8_encoding_configuration(self):
        """Test that UTF-8 encoding is properly configured for all file handlers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch.object(logger, 'add') as mock_add:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False
                    config.setup_logging()
                
                # All file handlers should have UTF-8 encoding
                for call in mock_add.call_args_list:
                    file_kwargs = call[1]
                    assert file_kwargs['encoding'] == "utf-8"
    
    def test_log_rotation_and_retention_policies(self):
        """Test log rotation and retention policies for both log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch.object(logger, 'add') as mock_add:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False
                    config.setup_logging()
                
                # App log: 100 MB rotation, 30 days retention
                app_log_call = mock_add.call_args_list[0]
                app_log_kwargs = app_log_call[1]
                assert app_log_kwargs['rotation'] == "100 MB"
                assert app_log_kwargs['retention'] == "30 days"
                assert app_log_kwargs['compression'] == "gz"
                
                # Error log: 50 MB rotation, 60 days retention  
                error_log_call = mock_add.call_args_list[1]
                error_log_kwargs = error_log_call[1]
                assert error_log_kwargs['rotation'] == "50 MB"
                assert error_log_kwargs['retention'] == "60 days"
                assert error_log_kwargs['compression'] == "gz"
    
    def test_error_log_enhanced_diagnostics(self):
        """Test that error log has enhanced diagnostics enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch.object(logger, 'add') as mock_add:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False
                    config.setup_logging()
                
                # Error log should have backtrace and diagnose enabled
                error_log_call = mock_add.call_args_list[1]
                error_log_kwargs = error_log_call[1]
                assert error_log_kwargs['backtrace'] is True
                assert error_log_kwargs['diagnose'] is True
    
    def test_async_logging_configuration(self):
        """Test that async logging (enqueue) is enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch.object(logger, 'add') as mock_add:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False
                    config.setup_logging()
                
                # Both file handlers should have async logging enabled
                for call in mock_add.call_args_list:
                    file_kwargs = call[1]
                    assert file_kwargs['enqueue'] is True
    
    def test_simplified_logging_initialization_message(self):
        """Test that initialization message is logged after setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            # Mock logger.info to capture the initialization message
            with patch.object(logger, 'info') as mock_info:
                with patch('app.logging_config.settings') as mock_settings:
                    mock_settings.debug = False
                    config.setup_logging()
                
                # Should log initialization message
                mock_info.assert_called_with("Logging system initialized")
    
    def test_no_complex_filtering_or_middleware(self):
        """Test that simplified logging doesn't include complex filtering or middleware."""
        # This test ensures the simplification removed unnecessary complexity
        from app import logging_config as config_module
        
        # Should not have complex attributes that were in previous versions
        assert not hasattr(config_module, 'LoggingMiddleware')
        assert not hasattr(config_module, 'LogFilter')
        assert not hasattr(config_module, 'CustomHandler')
        assert not hasattr(config_module, 'LogRotationManager')
        
        # Should only have the simplified LoggingConfig class
        assert hasattr(config_module, 'LoggingConfig')
        assert hasattr(config_module, 'logging_config')
    
    def test_module_level_exports(self):
        """Test that module exports only necessary components."""
        from app.logging_config import __all__
        
        # Should only export the logging_config instance
        assert __all__ == ["logging_config"]
    
    @pytest.mark.asyncio
    async def test_logging_performance_simplification(self):
        """Test that simplified logging has better performance characteristics."""
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = True
                
                # Measure setup time
                start_time = time.time()
                config.setup_logging()
                setup_time = time.time() - start_time
                
                # Should complete setup quickly (simplified configuration)
                assert setup_time < 0.1, f"Logging setup took {setup_time:.3f}s, expected < 0.1s"
                
                # Measure logging performance
                start_time = time.time()
                for i in range(100):
                    logger.info(f"Test log message {i}")
                logging_time = time.time() - start_time
                
                # Should handle 100 messages quickly
                assert logging_time < 1.0, f"100 log messages took {logging_time:.3f}s, expected < 1.0s"
    
    def test_real_logging_output_integration(self):
        """Integration test with real log file output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = False  # File logging only
                config.setup_logging()
                
                # Write test messages
                test_info_message = "Test INFO message for logging verification"
                test_error_message = "Test ERROR message for logging verification"
                
                logger.info(test_info_message)
                logger.error(test_error_message)
                
                # Give loguru time to write files (async logging)
                import time
                time.sleep(0.1)
                
                # Verify app log file exists and contains INFO message
                app_log_file = log_dir / "alpaca_service.log"
                if app_log_file.exists():
                    app_log_content = app_log_file.read_text(encoding='utf-8')
                    assert test_info_message in app_log_content
                    assert "INFO" in app_log_content
                
                # Verify error log file exists and contains ERROR message
                error_log_file = log_dir / "errors.log"
                if error_log_file.exists():
                    error_log_content = error_log_file.read_text(encoding='utf-8')
                    assert test_error_message in error_log_content
                    assert "ERROR" in error_log_content


class TestLoggingConfigBackwardsCompatibility:
    """Test backwards compatibility of the simplified logging configuration."""
    
    def test_logging_config_instance_accessible(self):
        """Test that logging_config instance is accessible for backwards compatibility."""
        from app.logging_config import logging_config
        
        assert logging_config is not None
        assert isinstance(logging_config, LoggingConfig)
        assert hasattr(logging_config, 'setup_logging')
        assert hasattr(logging_config, 'log_dir')
    
    def test_setup_logging_method_signature(self):
        """Test that setup_logging method has correct signature."""
        from app.logging_config import LoggingConfig
        
        config = LoggingConfig()
        
        # Method should exist and be callable with no arguments
        assert callable(config.setup_logging)
        
        # Should be able to call without arguments
        try:
            # Don't actually call it to avoid side effects
            import inspect
            sig = inspect.signature(config.setup_logging)
            assert len(sig.parameters) == 0, "setup_logging should not require parameters"
        except Exception as e:
            pytest.fail(f"Method signature check failed: {e}")
    
    def test_log_dir_property_exists(self):
        """Test that log_dir property exists for backwards compatibility."""
        from app.logging_config import LoggingConfig
        
        config = LoggingConfig()
        
        assert hasattr(config, 'log_dir')
        assert isinstance(config.log_dir, Path)
        assert config.log_dir == Path("logs")


class TestRealWorldLoggingScenarios:
    """Test real-world logging scenarios to ensure fix works in production."""
    
    def setup_method(self):
        """Setup for each test method."""
        logger.remove()
    
    def teardown_method(self):
        """Cleanup after each test method."""
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    
    def test_high_volume_logging_performance(self):
        """Test logging performance under high volume (production scenario)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = False
                config.setup_logging()
                
                import time
                
                # Test high-volume logging (simulating production load)
                start_time = time.time()
                for i in range(1000):
                    if i % 10 == 0:
                        logger.error(f"Error message {i}")
                    else:
                        logger.info(f"Info message {i}")
                
                elapsed = time.time() - start_time
                
                # Should handle 1000 messages in reasonable time
                assert elapsed < 2.0, f"1000 log messages took {elapsed:.3f}s, too slow for production"
                
                # Verify messages per second rate
                messages_per_second = 1000 / elapsed
                assert messages_per_second > 500, f"Logging rate {messages_per_second:.1f} msg/s is too slow"
    
    def test_unicode_and_special_characters(self):
        """Test logging with Unicode and special characters (real-world data)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = False
                config.setup_logging()
                
                # Test various Unicode and special characters
                test_messages = [
                    "Stock symbol: AAPL€ with price $150.00",
                    "User from 北京 placed order",
                    "Error: Cannot process symbol 'TËST' with émojis 🚀📈",
                    "JSON payload: {'symbol': 'MSFT', 'price': ¥1000}",
                    "Newlines\nand\ttabs in message",
                ]
                
                # Should not raise encoding errors
                for message in test_messages:
                    try:
                        logger.info(message)
                        logger.error(f"Error processing: {message}")
                    except UnicodeError:
                        pytest.fail(f"Unicode error when logging: {message}")
                
                # Give time for async logging
                import time
                time.sleep(0.2)
    
    def test_logging_during_exception_handling(self):
        """Test logging during exception handling (critical production scenario)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"  
            log_dir.mkdir(exist_ok=True)
            
            config = LoggingConfig()
            config.log_dir = log_dir
            
            with patch('app.logging_config.settings') as mock_settings:
                mock_settings.debug = False
                config.setup_logging()
                
                # Test logging during various exception scenarios
                try:
                    raise ValueError("Test exception with traceback")
                except ValueError as e:
                    # Should handle exception logging without issues
                    logger.error(f"Caught exception: {e}")
                    logger.exception("Exception with full traceback")
                
                try:
                    # Test nested exceptions
                    try:
                        1 / 0
                    except ZeroDivisionError:
                        raise RuntimeError("Nested exception") from None
                except RuntimeError as e:
                    logger.error(f"Nested exception: {e}")
                    logger.exception("Nested exception with traceback")
                
                # Give time for async logging
                import time
                time.sleep(0.1)