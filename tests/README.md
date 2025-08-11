# Opitios Alpaca Test Infrastructure

This document describes the enhanced test infrastructure for the Opitios Alpaca project, which provides comprehensive real API testing, coverage reporting, and GitHub integration.

## Overview

The test infrastructure is designed to:
- Test against real Alpaca API endpoints (no mocking)
- Provide detailed WebSocket testing capabilities
- Generate comprehensive coverage reports
- Support parallel test execution
- Integrate with GitHub for automated testing

## Directory Structure

```
tests/
├── conftest.py                 # Global fixtures and configuration
├── config.py                   # Enhanced test configuration system
├── test_config.py              # Tests for the configuration system
├── unit/                       # Unit tests with real API calls
├── integration/                # Integration tests
├── websocket/                  # WebSocket-specific tests
├── performance/                # Performance and load tests
├── security/                   # Security tests
├── utils/                      # Test utilities and helpers
└── data/                       # Test data files
```

## Configuration System

The test infrastructure uses a sophisticated configuration system (`tests/config.py`) that:

### Features
- **Real API Credentials Management**: Loads credentials from `secrets.yml`
- **Multiple Test Environments**: Unit, Integration, WebSocket, Performance, Security
- **Test Data Isolation**: Automatic cleanup of test orders and positions
- **Resource Tracking**: Tracks test resources for cleanup
- **Environment-Specific Settings**: Different configurations for different test types

### Test Environments

1. **Unit Tests**: Single account, minimal setup, parallel execution
2. **Integration Tests**: Multiple accounts, full setup, parallel execution
3. **WebSocket Tests**: Limited accounts, sequential execution for stability
4. **Performance Tests**: All accounts, load testing setup, parallel execution
5. **Security Tests**: Single account, security-focused, sequential execution

## Running Tests

### Using the Enhanced Test Runner

The enhanced test runner (`run_tests.py`) provides comprehensive testing capabilities:

```bash
# Validate test environment
python run_tests.py --validate-only

# Run all tests
python run_tests.py

# Run specific test types
python run_tests.py --type unit
python run_tests.py --type integration
python run_tests.py --type websocket
python run_tests.py --type performance
python run_tests.py --type security

# Run test suites
python run_tests.py --suite quick      # Unit tests only
python run_tests.py --suite all        # All test types

# Control reporting
python run_tests.py --no-coverage      # Disable coverage
python run_tests.py --no-html          # Disable HTML reports
python run_tests.py --no-parallel      # Disable parallel execution

# Advanced options
python run_tests.py --markers "not slow"  # Skip slow tests
python run_tests.py --fail-fast           # Stop on first failure
python run_tests.py --collect-only        # Only collect tests
python run_tests.py --cleanup             # Clean up after tests
```

### Using pytest Directly

You can also run tests directly with pytest:

```bash
# Run all tests with coverage
pytest --cov=app --cov-report=html:htmlcov

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m websocket

# Run tests in specific directories
pytest tests/unit/
pytest tests/integration/

# Run with parallel execution
pytest -n auto

# Generate reports
pytest --html=test-reports/report.html --self-contained-html
```

## Test Fixtures

The test infrastructure provides comprehensive fixtures:

### Configuration Fixtures
- `test_config`: Main test configuration instance
- `real_api_credentials`: Real Alpaca API credentials
- `primary_test_account`: Primary test account
- `all_test_accounts`: All available test accounts

### Environment Fixtures
- `unit_test_environment`: Unit test environment configuration
- `integration_test_environment`: Integration test environment
- `websocket_test_environment`: WebSocket test environment
- `performance_test_environment`: Performance test environment
- `security_test_environment`: Security test environment

### Utility Fixtures
- `test_symbols`: Standard test symbols (AAPL, MSFT, etc.)
- `test_option_symbols`: Test option symbols
- `test_cleanup_handler`: Cleanup handler for individual tests
- `project_root_path`: Project root directory path
- `test_data_path`: Test data directory path
- `reports_path`: Test reports directory path

## Writing Tests

### Basic Test Structure

```python
import pytest
from tests.config import TestCredentials, TestAccount

class TestMyFeature:
    """Test my feature with real API calls."""
    
    def test_basic_functionality(self, real_api_credentials):
        """Test basic functionality."""
        # Use real_api_credentials to make actual API calls
        assert real_api_credentials.api_key
        assert real_api_credentials.paper_trading is True
    
    @pytest.mark.asyncio
    async def test_async_functionality(self, test_cleanup_handler):
        """Test async functionality with cleanup."""
        # Register cleanup tasks
        test_cleanup_handler(lambda: print("Cleaning up"))
        
        # Your test code here
        pass
    
    @pytest.mark.integration
    def test_integration_scenario(self, integration_test_environment):
        """Test integration scenario."""
        # Use integration environment settings
        accounts = integration_test_environment.accounts
        symbols = integration_test_environment.test_symbols
        
        # Your integration test code here
        pass
```

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit          # Unit tests
@pytest.mark.integration   # Integration tests
@pytest.mark.websocket     # WebSocket tests
@pytest.mark.performance   # Performance tests
@pytest.mark.security      # Security tests
@pytest.mark.real_api      # Tests using real API calls
@pytest.mark.slow          # Slow tests (can be skipped)
```

### Resource Cleanup

The test infrastructure provides automatic cleanup:

```python
def test_with_cleanup(self, test_config, test_cleanup_handler):
    """Test with automatic cleanup."""
    # Register test resources
    test_config.register_test_order("order_123")
    test_config.register_test_position("AAPL")
    
    # Register custom cleanup
    test_cleanup_handler(lambda: print("Custom cleanup"))
    
    # Test code here - cleanup happens automatically
```

## Coverage Reporting

The test infrastructure generates comprehensive coverage reports:

### Report Types
- **Terminal**: Real-time coverage display
- **HTML**: Interactive coverage report (`htmlcov/index.html`)
- **XML**: Machine-readable coverage data (`test-reports/coverage.xml`)
- **JSON**: Structured coverage data (`test-reports/coverage.json`)

### Coverage Configuration
- **Minimum Coverage**: 85% required
- **Source**: `app/` directory
- **Exclusions**: Tests, virtual environments, cache directories
- **Line Exclusions**: Pragma comments, debug code, abstract methods

## GitHub Integration

The test infrastructure is designed to integrate with GitHub Actions:

### Automated Testing
- Tests run on every push and pull request
- Coverage reports posted as PR comments
- Test failures block PR merging
- Artifacts uploaded for analysis

### Status Checks
- Test results displayed in PR status
- Coverage changes highlighted
- Performance regression detection
- Security vulnerability scanning

## Best Practices

### Test Organization
1. **Group by Functionality**: Organize tests by feature/module
2. **Use Descriptive Names**: Clear test and class names
3. **Follow Conventions**: Consistent naming patterns
4. **Add Documentation**: Document complex test scenarios

### Real API Testing
1. **Use Paper Trading**: Always use paper trading accounts
2. **Clean Up Resources**: Register all test resources for cleanup
3. **Handle Rate Limits**: Implement appropriate delays
4. **Test Error Scenarios**: Include error handling tests

### Performance
1. **Use Parallel Execution**: Enable for unit and integration tests
2. **Skip Slow Tests**: Use markers for optional slow tests
3. **Optimize Setup**: Minimize test setup overhead
4. **Monitor Resources**: Track memory and connection usage

### Security
1. **Protect Credentials**: Never log or expose API keys
2. **Validate Inputs**: Test input validation thoroughly
3. **Test Authorization**: Verify permission enforcement
4. **Check Rate Limiting**: Ensure rate limits are enforced

## Troubleshooting

### Common Issues

1. **Missing Dependencies**
   ```bash
   pip install pytest-cov pytest-xdist pytest-html pytest-json-report
   ```

2. **Configuration Errors**
   ```bash
   python run_tests.py --validate-only
   ```

3. **Coverage Issues**
   - Check `.coveragerc` configuration
   - Ensure source paths are correct
   - Verify exclusion patterns

4. **Parallel Execution Problems**
   - Disable parallel execution for debugging
   - Check for shared resource conflicts
   - Use sequential execution for WebSocket tests

### Debug Mode

Run tests with detailed output:

```bash
python run_tests.py --type unit --no-parallel -v
```

### Environment Validation

Validate your test environment:

```bash
python run_tests.py --validate-only
```

This will check:
- Configuration file exists
- Test accounts are available
- Required directories exist
- Dependencies are installed

## Next Steps

After setting up the test infrastructure:

1. **Write Unit Tests**: Create tests in `tests/unit/`
2. **Add Integration Tests**: Create workflow tests in `tests/integration/`
3. **Implement WebSocket Tests**: Add real-time data tests in `tests/websocket/`
4. **Create Performance Tests**: Add load tests in `tests/performance/`
5. **Add Security Tests**: Create security tests in `tests/security/`
6. **Setup GitHub Actions**: Configure automated testing workflows
7. **Monitor Coverage**: Track and improve test coverage over time