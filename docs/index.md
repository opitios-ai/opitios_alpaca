# Opitios Alpaca Trading System Documentation

## 📚 Documentation Index

Welcome to the complete documentation for the Opitios Alpaca Multi-Account Trading System. This documentation is organized following the standardized `docs/` folder structure as specified in the main CLAUDE.md guidelines.

## 🏗️ Architecture and System Design

### Core Documentation
- **[README.md](README.md)** - Project overview, features, and quick start guide
- **[architecture.md](architecture.md)** - System architecture and technical design
- **[multi-account-system.md](multi-account-system.md)** - **⭐ NEW**: Comprehensive multi-account architecture guide
- **[data-flow.md](data-flow.md)** - Data flow and processing pipelines
- **[tech-stack.md](tech-stack.md)** - Technology stack and dependencies

### Requirements and Constraints
- **[requirements.md](requirements.md)** - System requirements and dependencies
- **[technical-constraints.md](technical-constraints.md)** - Technical limitations and constraints
- **[user-stories.md](user-stories.md)** - User stories and use cases

## 🔧 Setup and Configuration

### Getting Started
- **[SETUP.md](SETUP.md)** - Installation and setup instructions
- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide for developers

### Configuration
- **[examples/secrets.example.yml](../secrets.example.yml)** - Configuration template
- **Multi-Account Setup** - See [multi-account-system.md](multi-account-system.md#configuration)

## 🧪 Testing and Quality Assurance

### Testing Documentation
- **[TESTING.md](TESTING.md)** - Testing guidelines and procedures
- **[test-results.md](test-results.md)** - **⭐ NEW**: Comprehensive test execution results
- **[requirements-real-data-only.md](requirements-real-data-only.md)** - Real data testing requirements

### Performance and Security
- **[security-performance.md](security-performance.md)** - Security and performance guidelines
- **[success-metrics.md](success-metrics.md)** - Success metrics and KPIs

## 🔌 API Documentation

### API References
- **[api/api-spec.md](api/api-spec.md)** - Complete API specification
- **[API_TEST_COMMANDS.md](API_TEST_COMMANDS.md)** - API testing commands and examples

### Interactive Documentation
- **FastAPI Docs**: http://localhost:8080/docs (when server is running)
- **ReDoc**: http://localhost:8080/redoc (alternative API docs)

## 🚀 Deployment and Operations

### Deployment
- **Production Deployment** - See [README.md](README.md#deployment)
- **Docker Support** - See [../Dockerfile](../Dockerfile) and [../docker-compose.yml](../docker-compose.yml)

### Monitoring and Logging
- **Logging Configuration** - See [multi-account-system.md](multi-account-system.md#monitoring)
- **Health Checks** - See [multi-account-system.md](multi-account-system.md#deployment)

## 📋 Documentation Standards

This documentation follows the **CRITICAL DOCUMENTATION RULE** from CLAUDE.md:

> **All documentation files MUST be placed in the `docs/` folder - NEVER in the root directory.**

### Documentation Organization
```
docs/
├── index.md                    # This documentation index
├── README.md                   # Project overview (moved from root)
├── architecture.md             # System architecture
├── multi-account-system.md     # Multi-account implementation guide
├── test-results.md            # Comprehensive test results
├── api/                       # API documentation
│   └── api-spec.md           # API specifications
├── examples/                  # Configuration examples
└── diagrams/                  # Architecture diagrams (future)
```

## 🔄 Recent Updates

### August 3, 2025 - Multi-Account System Implementation
- ✅ **Redesigned system architecture** - Removed user management, implemented multi-account support
- ✅ **Added comprehensive testing** - All test scenarios completed successfully
- ✅ **Updated documentation structure** - Moved all docs to `docs/` folder
- ✅ **Created new documentation**:
  - [multi-account-system.md](multi-account-system.md) - Complete architecture guide
  - [test-results.md](test-results.md) - Detailed test execution results
  - [index.md](index.md) - This documentation index

## 🎯 Key Features Documented

### Multi-Account Trading System
- **Zero-Delay Architecture**: Pre-established connections to 100-1000 accounts
- **Intelligent Routing**: Account selection via `account_id` and `routing_key`
- **Load Balancing**: Multiple routing strategies (round-robin, hash-based, random, least-loaded)
- **External JWT Authentication**: No user management, external token validation
- **High Performance**: 50+ requests/second, <200ms average latency

### Comprehensive Testing
- **3 Real Alpaca Accounts**: Fully tested with live API connections
- **12 Pre-established Connections**: All connection pool functionality verified
- **100% Test Success Rate**: All scenarios passed as required
- **Performance Validated**: Zero-delay trading architecture confirmed

## 📞 Support and Troubleshooting

### Common Issues
- **Setup Problems** - See [SETUP.md](SETUP.md) and [QUICKSTART.md](QUICKSTART.md)
- **API Issues** - See [API_TEST_COMMANDS.md](API_TEST_COMMANDS.md)
- **Multi-Account Issues** - See [multi-account-system.md](multi-account-system.md#troubleshooting)

### Getting Help
1. Check the relevant documentation in this `docs/` folder
2. Review test results in [test-results.md](test-results.md)
3. Examine system logs in `/logs` directory
4. Verify configuration against [multi-account-system.md](multi-account-system.md#configuration)

---

**Note**: This documentation structure complies with the standardized documentation guidelines specified in the main CLAUDE.md file, ensuring all documentation files are properly organized within the `docs/` folder structure.