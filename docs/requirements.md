# Opitios Alpaca Trading Service - Critical Issues Requirements

## Executive Summary

This document outlines 6 critical issues that need to be addressed in the opitios_alpaca trading system to ensure production readiness, security, and operational reliability. These issues range from account type detection and balance validation to threading optimization and code cleanup.

**Project**: Opitios Alpaca Trading Service (Port 8090)
**Architecture**: FastAPI backend with multi-account Alpaca trading support
**Priority**: High - Production system requiring immediate fixes
**Timeline**: 2-3 weeks for complete implementation

## Stakeholders

### Primary Users
- **Trading Operations Team**: Need reliable automated trading with proper balance validation and account type detection
- **System Administrators**: Require simplified logging, clean codebase, and non-blocking operations
- **Development Team**: Need maintainable code without demo/test files in production

### Secondary Users
- **Compliance Team**: Need proper account type detection for regulatory reporting
- **Support Team**: Need clear logging and order timing data for troubleshooting

## Functional Requirements

### FR-001: Account Type Detection
**Description**: Implement automatic detection of paper trading vs live trading accounts based on account ID patterns
**Priority**: High
**Business Context**: Critical for compliance reporting and risk management

**Acceptance Criteria**:
- [ ] System automatically identifies paper trading accounts when account ID starts with "PA"
- [ ] System identifies live trading accounts for all other account ID patterns
- [ ] Account type detection is logged and available via API endpoints
- [ ] Account type is validated during connection pool initialization
- [ ] Account type information is included in all trading operation logs
- [ ] Configuration allows override of default detection logic if needed

**Technical Specifications**:
```python
def detect_account_type(account_id: str) -> str:
    """
    Detect if account is paper trading or live trading
    Returns: 'paper' or 'live'
    """
    return 'paper' if account_id.startswith('PA') else 'live'
```

**Implementation Location**: `app/account_pool.py` - AccountConfig class

### FR-002: Balance Validation System
**Description**: Prevent trading operations when account cash balance falls below configurable minimum threshold
**Priority**: High
**Business Context**: Risk management to prevent over-trading and account depletion

**Acceptance Criteria**:
- [ ] System checks cash balance before executing any trading operations
- [ ] Default minimum balance threshold of $5000 stored in secrets.yml
- [ ] Balance validation applies to all trading operations (buy/sell stocks and options)
- [ ] System logs balance validation failures with account details
- [ ] API returns clear error message when balance is insufficient
- [ ] Balance threshold is configurable per account if needed
- [ ] System handles API failures gracefully when balance cannot be retrieved

**Configuration in secrets.yml**:
```yaml
trading:
  minimum_balance: 5000  # USD
  balance_check_enabled: true
```

**Implementation Location**: 
- `app/alpaca_client.py` - Add balance validation methods
- `app/routes.py` - Integrate balance checks into trading endpoints
- `config.py` - Add balance configuration settings

### FR-003: Demo JWT File Assessment and Cleanup
**Description**: Evaluate necessity of demo JWT file and remove if not required for production
**Priority**: Medium
**Business Context**: Security and code cleanliness - demo files should not exist in production

**Acceptance Criteria**:
- [ ] Analyze app/demo_jwt.py to determine if it's used by any production code
- [ ] Search codebase for any imports or references to demo_jwt
- [ ] If unused, remove app/demo_jwt.py completely
- [ ] If used, document the specific use case and justify retention
- [ ] Update any documentation referencing demo JWT functionality
- [ ] Ensure no test code depends on demo JWT file

**Implementation Actions**:
1. Code analysis to find references
2. Remove file if unused
3. Update any dependent code if removal breaks functionality

**Implementation Location**: 
- Remove: `app/demo_jwt.py`
- Check: All files in `app/` directory for imports

### FR-004: Logging Configuration Simplification  
**Description**: Simplify logging configuration to include only basic log and error functionality, removing performance monitoring and complex features
**Priority**: Medium
**Business Context**: Reduce system complexity and improve maintainability

**Current Complex Features to Remove**:
- Performance monitoring decorators
- User-specific logging
- Security audit logging (keep basic security logs only)
- Trading operation structured logs (keep basic trading logs only)
- JSON formatters for complex log types

**Acceptance Criteria**:
- [ ] Keep only basic application logging and error logging
- [ ] Remove PerformanceMonitor class and all decorators
- [ ] Remove UserLogger specialized logging methods
- [ ] Simplify log directory structure to just app/ and errors/
- [ ] Keep console logging for development environment
- [ ] Maintain log rotation and compression for basic logs
- [ ] Ensure all existing logger.info/error calls continue to work

**Simplified Configuration**:
```python
class SimpleLoggingConfig:
    def setup_logging(self):
        # Console logging (development)
        # Basic application log
        # Error log only
        # No performance monitoring
        # No structured JSON logs
```

**Implementation Location**: `app/logging_config.py`

### FR-005: Order Placement Time Logging
**Description**: Ensure all trading operations log precise timing measurements for performance analysis and regulatory compliance
**Priority**: High
**Business Context**: Regulatory compliance and performance monitoring for trading operations

**Acceptance Criteria**:
- [ ] All order placement operations log start and completion timestamps
- [ ] Log format includes order ID, symbol, operation type, and duration in milliseconds
- [ ] Timing data is logged regardless of order success or failure
- [ ] Performance timing is available in trading operation logs
- [ ] Timing includes network latency to Alpaca API
- [ ] Failed orders log timing information with error details

**Log Format Example**:
```
2025-01-15 14:30:25.123 | INFO | Order placed: BUY AAPL qty=100 | order_id=abc123 | duration=245ms | success=true
2025-01-15 14:30:25.456 | ERROR | Order failed: SELL TSLA qty=50 | duration=1200ms | error=insufficient_balance
```

**Implementation Location**:
- `app/alpaca_client.py` - Add timing to all order methods
- `app/sell_module/order_manager.py` - Add timing to sell operations
- `app/routes.py` - Add timing to API endpoints

### FR-006: Sell Module Threading Optimization
**Description**: Fix sell_main.py blocking issue by implementing proper threading/async processing that doesn't block the main API
**Priority**: Critical
**Business Context**: System performance - selling operations currently block the main API causing delays

**Current Problems**:
- `sell_main.py` runs synchronously and blocks API operations
- Sell monitoring should run in background without affecting API performance
- Current implementation may have bugs in price retrieval and order cancellation

**Acceptance Criteria**:
- [ ] Sell module runs in completely separate thread/process from main API
- [ ] Sell module uses existing account pool without interfering with API operations
- [ ] Sell module has proper error handling and doesn't crash main application
- [ ] Current price retrieval works correctly for all option symbols
- [ ] Order cancellation after X minutes (configurable) works reliably
- [ ] Sell operations are properly logged with timing information
- [ ] Main API performance is not affected by sell module operations
- [ ] Sell module can be started/stopped independently via API endpoints

**Threading Implementation**:
```python
class SellModuleManager:
    def __init__(self, account_pool):
        self.account_pool = account_pool
        self.executor = ThreadPoolExecutor(max_workers=1)
        
    async def start_sell_module(self):
        # Run in separate thread without blocking
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(self.executor, self._run_sell_module)
        return future
```

**Implementation Location**:
- Modify: `sell_main.py` - Convert to proper async/threading
- Modify: `app/sell_module/sell_watcher.py` - Ensure thread safety
- Update: `main.py` - Integration with main API without blocking

## Non-Functional Requirements

### NFR-001: Performance
**Description**: System response time requirements
**Metrics**: 
- API response time < 500ms for 95th percentile (excluding Alpaca API latency)
- Order placement timing logged with millisecond precision
- Sell module operations don't impact main API performance

### NFR-002: Security
**Description**: Security and authentication requirements
**Standards**: 
- Remove all demo/test code from production
- Validate account balances before trading operations
- Proper account type detection for compliance

### NFR-003: Reliability
**Description**: System reliability requirements
**Standards**:
- Balance validation prevents over-trading
- Sell module runs independently without crashing main API
- Proper error handling for all account operations

### NFR-004: Maintainability
**Description**: Code maintainability requirements
**Standards**:
- Simplified logging configuration
- Clean codebase without demo files
- Proper separation of concerns between API and background processes

## Constraints

### Technical Constraints
- Must maintain all existing functionality while implementing fixes
- Cannot change core Alpaca API integration patterns
- Must use existing account pool architecture
- Cannot modify secrets.yml structure significantly
- Must maintain backward compatibility with existing API endpoints

### Business Constraints
- Production system - no downtime during implementation
- Real money trading system - extensive testing required
- Regulatory compliance requirements for account type detection and logging

### Development Constraints
- Cannot run/execute code during development - validation through code review only
- Must work with existing FastAPI framework and async patterns
- Must integrate with existing configuration system (secrets.yml)

## Success Criteria

### Primary Success Metrics
1. **Account Type Detection**: 100% accurate identification of paper vs live accounts
2. **Balance Validation**: Zero instances of trading below minimum balance threshold
3. **Demo Code Removal**: No demo/test files in production codebase
4. **Logging Simplification**: Reduced complexity while maintaining essential functionality
5. **Order Timing**: All trading operations logged with precise timing data
6. **Sell Module Performance**: Sell operations don't impact main API response times

### Validation Approach
1. **Code Review**: Thorough review of all changes before implementation
2. **Configuration Testing**: Verify all settings load correctly from secrets.yml
3. **Integration Testing**: Test with existing account pool and API endpoints
4. **Performance Testing**: Verify sell module doesn't block main API
5. **Logging Verification**: Confirm all required timing and account data is logged
6. **Security Testing**: Ensure no demo code exists and balance validation works

## Assumptions

### Key Assumptions Made
- Existing account pool architecture is stable and should be maintained
- Balance validation should be configurable but default to $5000 minimum
- Order cancellation timing (X minutes) is configurable in secrets.yml
- Current logging destinations (files/directories) should be maintained
- Alpaca API patterns and error handling should remain consistent

## Out of Scope

### Explicitly NOT Included
- Changes to core Alpaca API integration methods
- Modifications to authentication system or JWT handling
- Database schema changes or new data models
- UI/frontend changes for account management
- New trading strategies or algorithm modifications
- Websocket connection handling changes
- Rate limiting or CORS configuration changes

## Risk Assessment

### High Risk Items
1. **Threading Implementation**: Risk of introducing race conditions in sell module
2. **Balance Validation**: Risk of blocking valid trades due to API latency
3. **Production Changes**: Risk of disrupting live trading operations

### Medium Risk Items
1. **Logging Changes**: Risk of breaking existing log parsing tools
2. **Demo File Removal**: Risk of breaking hidden dependencies
3. **Account Type Detection**: Risk of misclassifying account types

### Low Risk Items
1. **Order Timing Logging**: Low risk addition to existing logging
2. **Configuration Changes**: Low risk additions to secrets.yml

### Risk Mitigation Strategies
- Comprehensive code review before any production deployment
- Gradual rollout with extensive monitoring
- Rollback plan for each component
- Test with paper trading accounts before live accounts
- Monitor system performance during and after implementation

## Dependencies

### Implementation Dependencies
1. **Account Type Detection** → Must be implemented before Balance Validation
2. **Logging Simplification** → Must be completed before Order Timing implementation  
3. **Demo JWT Assessment** → Independent, can be done first
4. **Sell Module Threading** → Depends on Account Type Detection and Balance Validation
5. **Order Timing** → Can be implemented independently but should come after Logging Simplification

### External Dependencies
- Alpaca API availability for balance checking
- Database connectivity for account configuration
- Redis connectivity for caching (if used)
- Existing secrets.yml configuration structure

## Implementation Roadmap

### Phase 1: Assessment and Cleanup (Week 1)
1. Demo JWT file assessment and removal
2. Logging configuration simplification
3. Account type detection implementation

### Phase 2: Core Functionality (Week 2)
1. Balance validation system
2. Order placement timing logging
3. Configuration updates in secrets.yml

### Phase 3: Threading Optimization (Week 2-3)
1. Sell module threading implementation
2. Integration testing and performance validation
3. Production deployment preparation

This comprehensive requirements document provides the foundation for implementing all 6 critical issues while maintaining system stability and production readiness.