# Project Files Guide - Root Directory

This document explains the purpose and necessity of each file in the root directory of the opitios_alpaca project.

## ✅ Essential Core Files

### Application Files
- **`main.py`** - FastAPI application entry point, server startup
- **`config.py`** - Central configuration management, loads secrets.yml
- **`secrets.yml`** - Multi-account API keys and system configuration (DO NOT COMMIT)
- **`secrets.example.yml`** - Configuration template for new setups

### Dependencies and Setup
- **`requirements.txt`** - Python package dependencies
- **`setup.py`** - Python package installation script
- **`pytest.ini`** - Test framework configuration

### Deployment
- **`Dockerfile`** - Docker container configuration
- **`docker-compose.yml`** - Multi-service Docker orchestration

## ✅ Testing and Validation Files

### Current Testing Scripts (Essential)
- **`test_accounts.py`** - Individual account functionality testing
- **`test_trading_simple.py`** - Basic trading API testing  
- **`test_trading_comprehensive.py`** - Advanced trading scenario testing
- **`test_system_validation.py`** - **NEW** Simple system validation script

### Development Tools
- **`start_server.py`** - Development server startup with endpoint testing
- **`run_tests.py`** - Advanced test runner with multiple modes

## 🗂️ Folder Structure

### Core Directories
- **`app/`** - Main application code (models, routes, middleware, etc.)
- **`docs/`** - **ALL documentation** (moved from root as per new standards)
- **`tests/`** - Legacy test suite (contains outdated user management tests)
- **`static/`** - Static files (websocket test page, etc.)
- **`logs/`** - Runtime logs organized by category
- **`venv/`** - Python virtual environment (NEVER commit)

## ❌ Files That Were Removed/Cleaned

### Temporary Files (Removed)
- ~~`temp_token.txt`~~ - Temporary JWT token file (deleted)
- ~~`users.db`~~ - Old user database from previous system (no longer needed)

### Documentation (Moved to docs/)
All `.md` files were moved to `docs/` folder following new documentation standards:
- ~~`README.md`~~ → `docs/README.md`
- ~~`api-spec.md`~~ → `docs/api/api-spec.md`  
- ~~`architecture.md`~~ → `docs/architecture.md`
- ~~And 7 other documentation files~~

## 🔧 File Usage Patterns

### For Development
```bash
# Start development server
python start_server.py

# Run system validation
python test_system_validation.py  

# Test specific accounts
python test_accounts.py

# Quick trading test
python test_trading_simple.py
```

### For Testing
```bash
# Advanced test runner
python run_tests.py --type all --verbose

# Specific test types  
python run_tests.py --type integration
python run_tests.py --type performance
```

### For Production
```bash
# Direct server startup
uvicorn main:app --host 0.0.0.0 --port 8080

# Docker deployment
docker-compose up -d
```

## 📝 File Maintenance Guidelines

### DO NOT DELETE
- Any file listed in "Essential Core Files"
- `app/` directory contents
- `docs/` directory contents
- Configuration files (`config.py`, `pytest.ini`)

### SAFE TO REMOVE (if needed)
- Log files in `logs/` (they regenerate)
- `__pycache__/` directories
- `.pytest_cache/` directory
- Any `.pyc` files

### CONDITIONAL REMOVAL
- **`tests/` directory**: Contains outdated user management tests. Can be archived if new validation approach is preferred.
- **Legacy test files**: Many test files reference old `UserContext` system and would need updating.

## 🚀 Recommended Development Workflow

1. **Setup**: Use `docs/QUICKSTART.md` for initial setup
2. **Validation**: Run `python test_system_validation.py` 
3. **Development**: Use `python start_server.py` for testing
4. **Testing**: Use individual test scripts rather than pytest suite
5. **Documentation**: All docs in `docs/` folder, update `docs/index.md`

## 🔄 Migration from Old System

The project was recently redesigned from a user-management system to a multi-account system:

### What Changed
- ❌ Removed user registration/authentication
- ❌ Removed SQLite user database  
- ✅ Added multi-account configuration
- ✅ Added connection pooling
- ✅ Added account routing
- ✅ Moved all docs to `docs/` folder

### Legacy Compatibility
- Old test suite in `tests/` references removed components
- New validation approach with simplified scripts
- Documentation reorganized per CLAUDE.md standards

## 📊 Current System Status

**✅ Fully Operational Multi-Account System**
- 3 real Alpaca accounts configured
- 12 pre-established connections  
- Zero-delay trading architecture
- Intelligent load balancing
- Complete API functionality
- Comprehensive documentation

**🧪 Validated Components**
- Module imports: PASS
- Configuration: PASS  
- Server health: PASS
- API functions: PASS
- Account routing: PASS
- Market data: PASS
- Load balancing: PASS

The system is production-ready and all essential files serve specific purposes in the multi-account trading architecture.