#!/usr/bin/env python3
"""
Setup script for Opitios Alpaca Trading Service
Handles environment initialization, dependency installation, and database setup
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Colors for console output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_status(message: str, status: str = "INFO"):
    """Print colored status message"""
    color = Colors.BLUE
    if status == "SUCCESS":
        color = Colors.GREEN
    elif status == "WARNING":
        color = Colors.YELLOW
    elif status == "ERROR":
        color = Colors.RED
    
    print(f"{color}[{status}]{Colors.END} {message}")

def run_command(command: str, cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result"""
    print_status(f"Running: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print_status(f"Command failed: {e}", "ERROR")
        if e.stderr:
            print(e.stderr)
        if check:
            raise
        return e

def check_python_version():
    """Check if Python version is compatible"""
    print_status("Checking Python version...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_status(f"Python {version.major}.{version.minor} detected. Python 3.8+ required.", "ERROR")
        sys.exit(1)
    
    print_status(f"Python {version.major}.{version.minor}.{version.micro} - OK", "SUCCESS")

def check_virtual_environment():
    """Check if running in virtual environment"""
    print_status("Checking virtual environment...")
    
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_status("Virtual environment detected", "SUCCESS")
        return True
    else:
        print_status("No virtual environment detected", "WARNING")
        print_status("It's recommended to use a virtual environment")
        
        response = input("Continue without virtual environment? (y/N): ").lower()
        if response != 'y':
            print_status("Please create and activate a virtual environment first:", "INFO")
            print("  python -m venv venv")
            print("  source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
            sys.exit(1)
        return False

def install_dependencies():
    """Install Python dependencies"""
    print_status("Installing Python dependencies...")
    
    requirements_file = "requirements.txt"
    if not os.path.exists(requirements_file):
        print_status(f"{requirements_file} not found", "ERROR")
        sys.exit(1)
    
    # Upgrade pip first
    run_command(f"{sys.executable} -m pip install --upgrade pip")
    
    # Install requirements
    run_command(f"{sys.executable} -m pip install -r {requirements_file}")
    
    print_status("Dependencies installed successfully", "SUCCESS")

def create_env_file():
    """Create .env file from template"""
    print_status("Setting up environment configuration...")
    
    env_file = ".env"
    env_example = ".env.example"
    
    if os.path.exists(env_file):
        print_status(f"{env_file} already exists", "WARNING")
        response = input("Overwrite existing .env file? (y/N): ").lower()
        if response != 'y':
            return
    
    # Create .env file with default values
    env_content = f"""# Opitios Alpaca Trading Service Configuration

# Alpaca API Configuration
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true

# FastAPI Configuration
APP_NAME=Opitios Alpaca Trading Service
DEBUG=true
HOST=0.0.0.0
PORT=8081

# JWT Configuration
JWT_SECRET=your-jwt-secret-key-change-in-production-{os.urandom(16).hex()}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Rate Limiting Configuration
DEFAULT_RATE_LIMIT=120
RATE_LIMIT_WINDOW=60

# Data Service Configuration
REAL_DATA_ONLY=true
ENABLE_MOCK_DATA=false
STRICT_ERROR_HANDLING=true
MAX_OPTION_SYMBOLS_PER_REQUEST=20

# Logging Configuration
LOG_DATA_FAILURES=true
LOG_LEVEL=INFO

# CORS Configuration
ALLOWED_ORIGINS=["*"]
"""
    
    with open(env_file, 'w') as f:
        f.write(env_content.strip())
    
    print_status(f"Created {env_file} with default configuration", "SUCCESS")
    print_status("Please update the configuration with your actual values", "WARNING")

def check_redis_connection():
    """Check if Redis is available"""
    print_status("Checking Redis connection...")
    
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        client.ping()
        print_status("Redis connection successful", "SUCCESS")
        return True
    except ImportError:
        print_status("Redis library not installed", "WARNING")
        return False
    except Exception as e:
        print_status(f"Redis connection failed: {e}", "WARNING")
        print_status("Redis is optional but recommended for distributed rate limiting", "INFO")
        return False

def setup_database():
    """Setup database if needed"""
    print_status("Setting up database...")
    
    # For now, this is a placeholder since the current system doesn't use a database
    # But this is where you would initialize SQLAlchemy, run migrations, etc.
    
    print_status("Database setup completed", "SUCCESS")

def run_tests():
    """Run test suite to verify installation"""
    print_status("Running test suite...")
    
    try:
        # Run pytest
        result = run_command(f"{sys.executable} -m pytest tests/ -v --tb=short", check=False)
        
        if result.returncode == 0:
            print_status("All tests passed", "SUCCESS")
            return True
        else:
            print_status("Some tests failed", "WARNING")
            return False
            
    except FileNotFoundError:
        print_status("pytest not found. Installing...", "WARNING")
        run_command(f"{sys.executable} -m pip install pytest")
        return run_tests()

def verify_installation():
    """Verify that the installation is working"""
    print_status("Verifying installation...")
    
    try:
        # Try to import main modules
        from app.alpaca_client import AlpacaClient
        from app.middleware import UserContextManager
        from app.models import StockQuoteRequest
        from config import settings
        
        print_status("All modules import successfully", "SUCCESS")
        
        # Check configuration
        if hasattr(settings, 'alpaca_api_key') and settings.alpaca_api_key:
            if settings.alpaca_api_key == "your_alpaca_api_key_here":
                print_status("Please update your Alpaca API credentials in .env", "WARNING")
            else:
                print_status("Alpaca API key configured", "SUCCESS")
        
        return True
        
    except ImportError as e:
        print_status(f"Import error: {e}", "ERROR")
        return False

def create_systemd_service():
    """Create systemd service file for production deployment"""
    print_status("Creating systemd service file...")
    
    service_content = f"""[Unit]
Description=Opitios Alpaca Trading Service
After=network.target

[Service]
Type=simple
User=alpaca
WorkingDirectory={os.getcwd()}
Environment=PATH={os.environ.get('PATH', '')}
ExecStart={sys.executable} -m uvicorn main:app --host 0.0.0.0 --port 8081
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    
    service_file = "opitios-alpaca.service"
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print_status(f"Created {service_file}", "SUCCESS")
    print_status("To install as system service:", "INFO")
    print(f"  sudo cp {service_file} /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable opitios-alpaca")
    print("  sudo systemctl start opitios-alpaca")

def print_post_install_instructions():
    """Print post-installation instructions"""
    print_status("Setup completed!", "SUCCESS")
    print()
    print(f"{Colors.BOLD}Next Steps:{Colors.END}")
    print("1. Update .env file with your Alpaca API credentials")
    print("2. (Optional) Install and configure Redis for distributed rate limiting")
    print("3. Start the development server:")
    print("   uvicorn main:app --host 0.0.0.0 --port 8081 --reload")
    print()
    print(f"{Colors.BOLD}API Documentation:{Colors.END}")
    print("   http://localhost:8081/docs")
    print()
    print(f"{Colors.BOLD}Testing:{Colors.END}")
    print("   python -m pytest tests/ -v")
    print()
    print(f"{Colors.BOLD}Production Deployment:{Colors.END}")
    print("   Use the generated systemd service file for production deployment")

def main():
    """Main setup function"""
    print(f"{Colors.BOLD}Opitios Alpaca Trading Service Setup{Colors.END}")
    print("=" * 50)
    
    try:
        # Check prerequisites
        check_python_version()
        check_virtual_environment()
        
        # Install dependencies
        install_dependencies()
        
        # Setup configuration
        create_env_file()
        
        # Optional components
        check_redis_connection()
        setup_database()
        
        # Verify installation
        if verify_installation():
            print_status("Installation verification successful", "SUCCESS")
        else:
            print_status("Installation verification failed", "ERROR")
            sys.exit(1)
        
        # Run tests
        response = input("Run tests to verify installation? (Y/n): ").lower()
        if response != 'n':
            run_tests()
        
        # Optional production setup
        response = input("Create systemd service file for production? (y/N): ").lower()
        if response == 'y':
            create_systemd_service()
        
        # Print final instructions
        print_post_install_instructions()
        
    except KeyboardInterrupt:
        print_status("Setup cancelled by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        print_status(f"Setup failed: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()