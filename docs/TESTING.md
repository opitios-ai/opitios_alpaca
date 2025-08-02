# Alpaca Service Test Suite

Comprehensive testing suite for opitios_alpaca service focused on validating **real market data only** policy.

## Test Structure

### Core Test Files

1. **`test_alpaca_client.py`** - Unit tests for AlpacaClient class
   - Validates real data strategy implementation
   - Tests error handling without mock fallbacks
   - Ensures API integration returns authentic data

2. **`test_api_endpoints.py`** - Integration tests for FastAPI endpoints
   - Tests all REST API endpoints
   - Validates response structures and data integrity
   - Ensures no synthetic data in responses

3. **`test_error_scenarios.py`** - Error handling validation
   - Tests API unavailability scenarios
   - Validates proper error responses without fallbacks
   - Tests market hours and data limitations

4. **`test_data_integrity.py`** - Data integrity and validation
   - Validates response data structures
   - Tests data type consistency
   - Ensures realistic market data constraints

5. **`test_e2e_workflows.py`** - End-to-end workflow tests
   - Tests complete trading workflows
   - Validates data consistency across endpoints
   - Tests real-world usage scenarios

6. **`test_performance.py`** - Performance and load tests
   - Tests API response times
   - Validates concurrent request handling
   - Performance benchmarks for real data calls

## Test Categories

### Unit Tests
```bash
pytest tests/test_alpaca_client.py -v
```
- Test AlpacaClient methods in isolation
- Mock external dependencies
- Validate real data strategy implementation

### Integration Tests
```bash
pytest tests/test_api_endpoints.py -v
```
- Test API endpoints with FastAPI test client
- Validate HTTP responses and status codes
- Test request/response data flow

### Error Scenario Tests
```bash
pytest tests/test_error_scenarios.py -v
```
- Test various error conditions
- Validate error response formats
- Ensure no fallback to mock data

### Data Integrity Tests
```bash
pytest tests/test_data_integrity.py -v
```
- Validate data structure consistency
- Test data type validation
- Ensure realistic market data constraints

### End-to-End Tests
```bash
pytest tests/test_e2e_workflows.py -v
```
- Test complete user workflows
- Validate multi-step operations
- Test real-world scenarios

### Performance Tests
```bash
pytest tests/test_performance.py -v
```
- Test API response times
- Validate concurrent request handling
- Performance benchmarking

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Specific Test Categories
```bash
# Unit tests only
pytest tests/test_alpaca_client.py -v

# Integration tests
pytest tests/test_api_endpoints.py -v

# Error scenarios
pytest tests/test_error_scenarios.py -v

# Performance tests (may be slow)
pytest tests/test_performance.py -v -s
```

### Test Markers
```bash
# Run integration tests
pytest -m integration -v

# Run performance tests
pytest -m performance -v

# Run e2e tests
pytest -m e2e -v
```

## Key Test Validations

### Real Data Only Policy
All tests validate that:
- No mock or synthetic data is returned
- No fallback data when real data unavailable
- Error responses when authentic data missing
- No calculated fields (Greeks, indicators, etc.)

### Data Authenticity Checks
- Validates Alpaca data structure compliance
- Ensures realistic market data constraints
- Tests timestamp and data freshness
- Validates symbol formats and conventions

### Error Handling Validation
- Tests proper error responses without fallbacks
- Validates error message clarity
- Ensures no alternative data sources used
- Tests graceful degradation scenarios

## Configuration

### Test Settings
Tests use mocked settings by default:
```python
real_data_only = True
enable_mock_data = False
strict_error_handling = True
```

### Environment Variables
```bash
# Skip performance tests in CI
export SKIP_PERFORMANCE_TESTS=1

# Run with coverage
pytest --cov=app tests/
```

## Test Data Strategy

### Mocking Strategy
- Mock Alpaca API responses with realistic data structures
- Simulate various error conditions
- Test edge cases and boundary conditions
- Validate response time performance

### Data Validation
- Verify response structures match Alpaca API format
- Validate data types and constraints
- Ensure no synthetic or calculated fields
- Test data consistency across endpoints

## Performance Benchmarks

### Response Time Targets
- Single stock quote: < 500ms
- Batch quotes (20 symbols): < 2s
- Options chain: < 3s
- Account data: < 1s

### Throughput Targets
- Minimum 20 requests/second
- Support 10 concurrent requests
- Handle large data sets efficiently

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run Tests
  run: |
    pytest tests/ -v --cov=app
    pytest tests/test_performance.py -v -x
```

### Test Coverage
Target: 90%+ code coverage for core functionality

## Troubleshooting

### Common Issues
1. **Mock Setup**: Ensure proper mocking of AlpacaClient
2. **Async Tests**: Use `pytest-asyncio` for async test support
3. **Performance Tests**: May be slow, consider skipping in CI

### Debug Mode
```bash
pytest tests/ -v -s --tb=long
```