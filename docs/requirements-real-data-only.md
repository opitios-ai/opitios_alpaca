# Requirements: Real Market Data Only Implementation

## Executive Summary

This document defines the requirements for removing all mock, calculated, and fallback data from the opitios_alpaca service to ensure 100% real market data usage from Alpaca APIs. The primary focus is eliminating the Black-Scholes fallback calculations in options pricing and ensuring all API responses contain only authentic market data.

## Current State Analysis

### Identified Mock/Calculated Data Sources

#### 1. Options Pricing Fallback Logic (Primary Issue)
**Location**: `app/alpaca_client.py` lines 259-324  
**Method**: `get_option_quote()`  
**Issue**: When real Alpaca options data is unavailable, the system falls back to Black-Scholes approximation calculations

**Current Fallback Data Generated**:
- Theoretical option prices using Black-Scholes formula
- Calculated bid/ask spreads (±2% from theoretical price)
- Estimated Greeks (delta, gamma, theta, vega)
- Implied volatility assumptions (fixed at 0.25)
- Time value calculations
- Intrinsic value calculations

#### 2. Options Chain Fallback
**Location**: `app/alpaca_client.py` lines 165-227  
**Method**: `get_options_chain()`  
**Issue**: Limited error handling when real options chain data is unavailable

#### 3. Data Source Indicators
**Current Implementation**: Responses include `data_source` field indicating whether data is real or calculated
- Real data: `"Real Alpaca options market data"`
- Calculated data: `"Calculated pricing based on real {underlying} stock price: ${current_price}"`

## Stakeholders

### Primary Users
- **Traders**: Require accurate, real-time market data for trading decisions
- **Portfolio Managers**: Need authentic pricing for risk assessment
- **Algorithmic Trading Systems**: Depend on real market data for automated strategies

### Secondary Users  
- **Compliance Teams**: Must ensure trading data authenticity for regulatory requirements
- **Risk Management**: Require real market data for accurate risk calculations
- **Auditors**: Need verification that all pricing data is from legitimate market sources

### System Administrators
- **DevOps Teams**: Responsible for monitoring data source health and API connectivity
- **Support Teams**: Handle escalations when real data is unavailable

## Functional Requirements

### FR-001: Eliminate Options Pricing Fallback Calculations
**Description**: Remove all Black-Scholes and calculated pricing logic from options quote endpoints  
**Priority**: High  
**Acceptance Criteria**:
- [ ] Remove lines 259-324 in `alpaca_client.py` (Black-Scholes fallback logic)
- [ ] Remove calculated pricing variables: `theoretical_price`, `bid_price`, `ask_price` calculations
- [ ] Remove calculated Greeks: `delta`, `gamma`, `theta`, `vega` approximations
- [ ] Remove intrinsic and time value calculations
- [ ] Return error response when real Alpaca options data is unavailable

### FR-002: Real-Only Options Quote API
**Description**: `get_option_quote()` method must return only real Alpaca market data or explicit error  
**Priority**: High  
**Acceptance Criteria**:
- [ ] API attempts to fetch real options data from Alpaca first
- [ ] If real data unavailable, return structured error response instead of calculated data
- [ ] Remove `data_source` field from successful responses (all data will be real)
- [ ] Maintain all real data fields: symbol, bid_price, ask_price, bid_size, ask_size, timestamp
- [ ] Return HTTP 404 with specific error message when option quote not available

### FR-003: Real-Only Options Chain API  
**Description**: `get_options_chain()` method must return only real Alpaca options chain data  
**Priority**: High  
**Acceptance Criteria**:
- [ ] Remove any fallback or approximation logic from options chain retrieval
- [ ] Return only contracts with real market data from Alpaca API
- [ ] Filter out contracts without real quote data
- [ ] Return error response when no real options chain data available
- [ ] Maintain expiration date filtering functionality using real data only

### FR-004: Multiple Options Quote Batch Processing
**Description**: `get_multiple_option_quotes()` must handle real-data-only responses  
**Priority**: High  
**Acceptance Criteria**:
- [ ] Process each option symbol individually for real data
- [ ] Include error objects in response array for symbols without real data
- [ ] Maintain response structure with successful quotes and error indicators
- [ ] Remove any calculated data from batch responses
- [ ] Provide count of successful vs. failed quote retrievals

### FR-005: Stock Data Validation (Baseline)
**Description**: Verify all stock-related endpoints use only real Alpaca data  
**Priority**: Medium  
**Acceptance Criteria**:
- [ ] Audit `get_stock_quote()` method for any mock data patterns
- [ ] Audit `get_multiple_stock_quotes()` method for fallback logic
- [ ] Audit `get_stock_bars()` method for calculated data
- [ ] Confirm all stock endpoints return only real market data or errors

## Non-Functional Requirements

### NFR-001: Error Handling Performance
**Description**: System response time requirements when real data is unavailable  
**Priority**: High  
**Metrics**:
- API error response time < 500ms when real data unavailable
- Batch quote processing maintains < 2 second response time
- No more than 3 retry attempts per API call to Alpaca

### NFR-002: Data Authenticity Validation
**Description**: Verification that all returned data originates from Alpaca APIs  
**Priority**: High  
**Standards**:
- All pricing data must have Alpaca API timestamps
- No internally generated price calculations allowed
- Response validation ensures data source traceability
- Audit logs must track all API calls to Alpaca services

### NFR-003: Availability and Reliability
**Description**: Service behavior when Alpaca APIs are unavailable  
**Priority**: Medium  
**Requirements**:
- Graceful degradation with clear error messages
- No cached or stale calculated data served
- Health check endpoints reflect real data source status
- Circuit breaker pattern for Alpaca API failures

### NFR-004: API Response Consistency
**Description**: Standardized error responses for unavailable real data  
**Priority**: Medium  
**Standards**:
- Consistent error response format across all endpoints
- Clear distinction between API errors vs. data unavailability
- HTTP status codes aligned with error types (404 for no data, 500 for API errors)

## User Stories

### Epic: Real Options Data Implementation

#### Story: REAL-001 - Remove Options Pricing Fallback
**As a** trader  
**I want** option quotes to return only real market data  
**So that** my trading decisions are based on authentic market pricing

**Acceptance Criteria** (EARS format):
- **WHEN** requesting option quote **THEN** system attempts real Alpaca API call only
- **IF** real options data unavailable **THEN** return HTTP 404 with "Real market data not available" error
- **FOR** any option quote response **VERIFY** no calculated pricing fields present

**Technical Notes**:
- Remove Black-Scholes calculation logic entirely
- Update error handling to return structured error responses
- Modify unit tests to expect errors when real data unavailable

**Story Points**: 8  
**Priority**: High

#### Story: REAL-002 - Options Chain Real Data Only
**As a** portfolio manager  
**I want** options chain data to include only contracts with real market pricing  
**So that** my risk assessments are based on actual market conditions

**Acceptance Criteria** (EARS format):
- **WHEN** requesting options chain **THEN** return only contracts with real Alpaca quote data
- **IF** no real options chain data exists **THEN** return error with specific message
- **FOR** each option contract **VERIFY** bid/ask prices are from real market data

**Technical Notes**:
- Filter options chain results to real data only
- Remove any synthetic contract generation
- Update response model to reflect real-data-only structure

**Story Points**: 5  
**Priority**: High

#### Story: REAL-003 - Batch Quote Real Data Processing  
**As a** algorithmic trading system  
**I want** batch option quote requests to clearly identify which quotes have real data  
**So that** my automated strategies only execute on authentic market pricing

**Acceptance Criteria** (EARS format):
- **WHEN** requesting multiple option quotes **THEN** each quote contains only real data or error object
- **IF** subset of quotes have real data **THEN** return mixed response with success/error indicators
- **FOR** batch response **VERIFY** count fields accurately reflect real vs. error results

**Technical Notes**:
- Modify batch processing to handle real-data-only responses
- Update response structure for mixed success/error scenarios
- Ensure error objects are clearly distinguishable from quote objects

**Story Points**: 3  
**Priority**: Medium

### Epic: Error Handling Enhancement

#### Story: REAL-004 - Standardized Error Responses
**As a** system administrator  
**I want** consistent error messages when real market data is unavailable  
**So that** I can effectively monitor and troubleshoot data source issues

**Acceptance Criteria** (EARS format):
- **WHEN** real data unavailable **THEN** return standardized error response format
- **IF** Alpaca API returns error **THEN** log original error and return user-friendly message  
- **FOR** all error responses **VERIFY** HTTP status codes are appropriate

**Technical Notes**:
- Define standard error response schema
- Implement consistent error handling across all endpoints
- Add comprehensive logging for debugging

**Story Points**: 3  
**Priority**: Medium

## API Behavior Specifications

### Options Quote Endpoint Changes

#### Current Behavior (To Be Removed)
```json
{
  "symbol": "AAPL240216C00190000",
  "bid_price": 24.01,
  "ask_price": 24.49,
  "data_source": "Calculated pricing based on real AAPL stock price: $212.50",
  "implied_volatility": 0.25,
  "delta": 0.85
}
```

#### New Real-Data-Only Behavior
**Success Response** (Real Data Available):
```json
{
  "symbol": "AAPL240216C00190000",
  "underlying_symbol": "AAPL",
  "strike_price": 190.0,
  "expiration_date": "2024-02-16",
  "option_type": "call",
  "bid_price": 24.25,
  "ask_price": 24.75,
  "bid_size": 10,
  "ask_size": 8,
  "timestamp": "2024-01-15T15:30:00Z"
}
```

**Error Response** (Real Data Unavailable):
```json
{
  "error": "Real market data not available for option AAPL240216C00190000",
  "error_code": "NO_REAL_DATA",
  "message": "Option quote data is not available from Alpaca market data service",
  "symbol": "AAPL240216C00190000",
  "timestamp": "2024-01-15T15:30:00Z"
}
```

### Options Chain Endpoint Changes

#### New Real-Data-Only Response
```json
{
  "underlying_symbol": "AAPL",
  "underlying_price": 212.50,
  "expiration_dates": ["2024-02-16"],
  "options_count": 15,
  "options": [
    {
      "symbol": "AAPL240216C00190000",
      "strike_price": 190.0,
      "option_type": "call",
      "bid_price": 24.25,
      "ask_price": 24.75,
      "bid_size": 10,
      "ask_size": 8
    }
  ],
  "note": "Filtered to show only options with real market data"
}
```

## Data Source Requirements

### Alpaca API Integration Standards

#### Primary Data Sources (Required)
- **Options Market Data API**: Real-time and historical options quotes
- **Stock Market Data API**: Real-time stock quotes and historical bars  
- **Options Chain API**: Complete options chain with contract details
- **Trading API**: Account data, positions, and order management

#### Data Validation Requirements
- All returned timestamps must be from Alpaca API responses
- Bid/ask prices must be directly from market data feeds
- No interpolation or calculation of missing price points
- Greeks must be provided by Alpaca or omitted entirely

#### Fallback Strategy (Real Data Only)
- **Primary**: Attempt real-time data from Alpaca market data API
- **Secondary**: Return structured error when real data unavailable
- **Prohibited**: Any calculated, approximated, or synthetic data generation

## Error Handling Specifications

### Error Response Schema
```json
{
  "error": "string",           // Human-readable error message  
  "error_code": "string",      // Machine-readable error code
  "message": "string",         // Detailed error description
  "symbol": "string",          // Symbol that failed (if applicable)
  "timestamp": "datetime",     // Error occurrence timestamp
  "retry_after": "number"      // Suggested retry delay in seconds (optional)
}
```

### Standard Error Codes
- `NO_REAL_DATA`: Real market data not available for requested instrument
- `API_UNAVAILABLE`: Alpaca API service temporarily unavailable  
- `INVALID_SYMBOL`: Requested symbol not recognized by Alpaca
- `RATE_LIMITED`: API rate limit exceeded
- `INSUFFICIENT_PERMISSIONS`: Account lacks permissions for requested data

### HTTP Status Code Mapping
- `404 Not Found`: Real data not available for requested symbol/contract
- `429 Too Many Requests`: API rate limiting in effect
- `500 Internal Server Error`: Alpaca API service error
- `503 Service Unavailable`: Alpaca API temporarily unavailable

## Implementation Timeline

### Phase 1: Options Fallback Removal (Week 1-2)
- Remove Black-Scholes calculation logic
- Implement real-data-only option quote endpoint
- Update error handling for missing real data
- Modify unit tests for new behavior

### Phase 2: Options Chain Enhancement (Week 2-3)  
- Filter options chain to real data only
- Update response models
- Implement comprehensive error responses
- Add integration tests

### Phase 3: Validation and Testing (Week 3-4)
- End-to-end testing with real Alpaca API
- Performance testing under various market conditions
- Error scenario validation
- Documentation updates

### Phase 4: Monitoring and Deployment (Week 4)
- Add monitoring for real data availability
- Implement alerting for API connectivity issues
- Production deployment with feature flags
- Post-deployment validation

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Alpaca options data limited availability | High | Medium | Implement comprehensive error handling and user communication |
| Increased API errors impact user experience | Medium | High | Add caching strategy for frequently accessed symbols |
| Performance degradation from additional validation | Low | Medium | Optimize API calls and implement connection pooling |
| Breaking changes affect existing integrations | High | Low | Maintain API compatibility with deprecation warnings |

## Success Criteria

### Functional Success Metrics
- [ ] 0% of API responses contain calculated/synthetic data
- [ ] 100% of successful responses contain real Alpaca market data
- [ ] All fallback calculation logic removed from codebase
- [ ] Error responses clearly indicate when real data unavailable

### Technical Success Metrics  
- [ ] API response time < 500ms for error cases
- [ ] API response time < 2 seconds for successful real data
- [ ] 100% unit test coverage for real-data-only logic
- [ ] Zero calculated data fields in response schemas

### Business Success Metrics
- [ ] Trader confidence in data authenticity increases
- [ ] Compliance audit requirements met
- [ ] Risk management accuracy improves with real data
- [ ] System transparency enhanced through clear error messaging

## Dependencies

### External Dependencies
- **Alpaca Market Data API**: Reliable access to real-time options and stock data
- **Alpaca Trading API**: Account and position data access
- **Network Connectivity**: Stable connection to Alpaca services

### Internal Dependencies  
- **Configuration Management**: API keys and service endpoints properly configured
- **Logging Infrastructure**: Comprehensive logging for debugging and monitoring
- **Error Handling Framework**: Consistent error response patterns across service

### Development Dependencies
- **Testing Environment**: Access to Alpaca paper trading environment
- **CI/CD Pipeline**: Automated testing and deployment capabilities
- **Monitoring Tools**: Real-time service health and API performance monitoring

## Assumptions

- Alpaca provides sufficient options market data coverage for target trading instruments
- Real-time options data from Alpaca has acceptable latency for trading operations  
- Error rates from missing real data will be acceptable to end users
- Existing API clients can handle error responses for unavailable data
- Network connectivity to Alpaca services maintains high availability

## Out of Scope

- Implementation of alternative market data providers as fallback
- Development of new calculated pricing models
- Historical data backfilling for periods when real data unavailable
- Real-time streaming WebSocket implementation (separate project)
- Integration with additional options exchanges beyond Alpaca's coverage
- Development of proprietary market data aggregation logic

---

*This requirements document ensures the opitios_alpaca service delivers only authentic market data from Alpaca APIs, eliminating all calculated and synthetic data to maintain the highest standards of data integrity for trading operations.*