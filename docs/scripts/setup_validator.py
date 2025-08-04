#!/usr/bin/env python3
"""
Interactive Setup Validation Script for Opitios Alpaca Trading Service

This script provides comprehensive validation of the setup process with
interactive diagnostics and step-by-step verification to achieve >90% setup success rate.

Usage:
    python docs/scripts/setup_validator.py

Features:
- Progressive validation with detailed feedback
- Platform-specific instructions (Windows/macOS/Linux)
- Interactive problem resolution
- Comprehensive environment checking
- API connectivity testing
- Performance diagnostics
"""

import os
import sys
import subprocess
import platform
import json
import requests
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import importlib.util

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_step(step: str, description: str):
    """Print a validation step"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}[STEP] {step}{Colors.END}")
    print(f"{Colors.WHITE}{description}{Colors.END}")

def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def get_user_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default"""
    if default:
        user_input = input(f"{Colors.YELLOW}{prompt} (default: {default}): {Colors.END}")
        return user_input if user_input else default
    else:
        return input(f"{Colors.YELLOW}{prompt}: {Colors.END}")

def check_python_version() -> Tuple[bool, str]:
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    else:
        return False, f"Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)"

def check_virtual_environment() -> Tuple[bool, str]:
    """Check if virtual environment is active"""
    venv_path = os.environ.get('VIRTUAL_ENV')
    if venv_path:
        return True, f"Active virtual environment: {venv_path}"
    else:
        return False, "No virtual environment detected"

def check_required_packages() -> Tuple[bool, List[str]]:
    """Check if required packages are installed"""
    required_packages = [
        'fastapi', 'uvicorn', 'alpaca_trade_api', 'pydantic',
        'python_dotenv', 'requests', 'loguru'
    ]
    
    missing_packages = []
    installed_packages = []
    
    for package in required_packages:
        try:
            spec = importlib.util.find_spec(package.replace('_', '-'))
            if spec is None:
                # Try alternative name
                spec = importlib.util.find_spec(package.replace('-', '_'))
            
            if spec is not None:
                installed_packages.append(package)
            else:
                missing_packages.append(package)
        except ImportError:
            missing_packages.append(package)
    
    success = len(missing_packages) == 0
    return success, missing_packages

def check_project_structure() -> Tuple[bool, List[str]]:
    """Check if project structure is correct"""
    required_files = [
        'main.py',
        'config.py', 
        'requirements.txt',
        'app/__init__.py',
        'app/routes.py',
        'tests/__init__.py'
    ]
    
    missing_files = []
    project_root = Path.cwd()
    
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    success = len(missing_files) == 0
    return success, missing_files

def check_configuration() -> Tuple[bool, Dict[str, str]]:
    """Check configuration and environment variables"""
    env_file = Path('.env')
    config_status = {}
    
    required_vars = [
        'ALPACA_API_KEY',
        'ALPACA_SECRET_KEY', 
        'ALPACA_BASE_URL',
        'ALPACA_PAPER_TRADING'
    ]
    
    # Check .env file exists
    if not env_file.exists():
        return False, {'error': '.env file not found'}
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        return False, {'error': 'python-dotenv not installed'}
    
    # Check required variables
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var in ['ALPACA_API_KEY', 'ALPACA_SECRET_KEY']:
                config_status[var] = f"{'*' * (len(value) - 4)}{value[-4:]}"
            else:
                config_status[var] = value
        else:
            config_status[var] = "NOT SET"
    
    # Validate API key format
    api_key = os.getenv('ALPACA_API_KEY', '')
    secret_key = os.getenv('ALPACA_SECRET_KEY', '')
    
    valid_config = True
    if not api_key.startswith(('PK', 'AK')):
        config_status['api_key_format'] = "Invalid format (should start with PK or AK)"
        valid_config = False
    
    if len(secret_key) < 20:
        config_status['secret_key_format'] = "Invalid format (too short)"
        valid_config = False
    
    return valid_config, config_status

def test_api_connectivity() -> Tuple[bool, str]:
    """Test connection to Alpaca API"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        if not api_key or not secret_key:
            return False, "API credentials not configured"
        
        # Test basic API connectivity
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': secret_key
        }
        
        response = requests.get(f"{base_url}/v2/account", headers=headers, timeout=10)
        
        if response.status_code == 200:
            account_data = response.json()
            buying_power = account_data.get('buying_power', 'Unknown')
            return True, f"Connected successfully. Buying power: ${buying_power}"
        elif response.status_code == 401:
            return False, "Authentication failed - check API credentials"
        else:
            return False, f"API returned status code {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def test_local_server() -> Tuple[bool, str]:
    """Test if local server can start"""
    try:
        print_info("Starting local server test (this may take a few seconds)...")
        
        # Start server in background
        cmd = [sys.executable, 'main.py']
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        
        # Wait for server to start
        time.sleep(3)
        
        # Check if server is responding
        try:
            response = requests.get('http://localhost:8081/api/v1/health', timeout=5)
            if response.status_code == 200:
                success = True
                message = "Local server started successfully"
            else:
                success = False
                message = f"Server responded with status {response.status_code}"
        except requests.exceptions.RequestException:
            success = False
            message = "Server not responding on localhost:8081"
        
        # Stop the server
        process.terminate()
        process.wait(timeout=5)
        
        return success, message
        
    except subprocess.TimeoutExpired:
        return False, "Server failed to start within timeout"
    except Exception as e:
        return False, f"Error starting server: {str(e)}"

def provide_platform_specific_help():
    """Provide platform-specific setup instructions"""
    system = platform.system().lower()
    
    print_header("Platform-Specific Instructions")
    
    if system == "windows":
        print(f"{Colors.CYAN}Windows Setup Instructions:{Colors.END}")
        print("1. Install Python 3.8+ from python.org")
        print("2. Create virtual environment:")
        print("   python -m venv venv")
        print("3. Activate virtual environment:")
        print("   venv\\Scripts\\activate")
        print("4. Install packages:")
        print("   pip install -r requirements.txt")
        
    elif system == "darwin":  # macOS
        print(f"{Colors.CYAN}macOS Setup Instructions:{Colors.END}")
        print("1. Install Python 3.8+ using Homebrew:")
        print("   brew install python@3.8")
        print("2. Create virtual environment:")
        print("   python3 -m venv venv")
        print("3. Activate virtual environment:")
        print("   source venv/bin/activate")
        print("4. Install packages:")
        print("   pip install -r requirements.txt")
        
    elif system == "linux":
        print(f"{Colors.CYAN}Linux Setup Instructions:{Colors.END}")
        print("1. Install Python 3.8+:")
        print("   sudo apt update && sudo apt install python3.8 python3.8-venv")
        print("2. Create virtual environment:")
        print("   python3 -m venv venv")
        print("3. Activate virtual environment:")
        print("   source venv/bin/activate")
        print("4. Install packages:")
        print("   pip install -r requirements.txt")

def interactive_problem_solver(issues: List[str]):
    """Interactive problem solver for common issues"""
    print_header("Interactive Problem Solver")
    
    for issue in issues:
        print(f"\n{Colors.YELLOW}Issue: {issue}{Colors.END}")
        
        if "virtual environment" in issue.lower():
            print("🔧 Solutions for Virtual Environment:")
            print("1. Create new virtual environment")
            print("2. Activate existing virtual environment")
            print("3. Skip virtual environment (not recommended)")
            
            choice = get_user_input("Choose solution (1-3)", "1")
            
            if choice == "1":
                system = platform.system().lower()
                if system == "windows":
                    print("Run: python -m venv venv && venv\\Scripts\\activate")
                else:
                    print("Run: python3 -m venv venv && source venv/bin/activate")
                    
        elif "missing packages" in issue.lower():
            print("🔧 Solutions for Missing Packages:")
            print("1. Install all requirements")
            print("2. Install packages individually")
            
            choice = get_user_input("Choose solution (1-2)", "1")
            
            if choice == "1":
                print("Run: pip install -r requirements.txt")
            else:
                print("Run: pip install fastapi uvicorn alpaca-py pydantic python-dotenv")
                
        elif "configuration" in issue.lower():
            print("🔧 Solutions for Configuration:")
            print("1. Create/update .env file")
            print("2. Check API key format")
            print("3. Verify Alpaca account setup")
            
            choice = get_user_input("Choose solution (1-3)", "1")
            
            if choice == "1":
                print("Create .env file with:")
                print("ALPACA_API_KEY=your_api_key")
                print("ALPACA_SECRET_KEY=your_secret_key")
                print("ALPACA_BASE_URL=https://paper-api.alpaca.markets")
                print("ALPACA_PAPER_TRADING=true")

def generate_diagnostic_report() -> Dict:
    """Generate comprehensive diagnostic report"""
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'platform': {
            'system': platform.system(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python_version': sys.version
        },
        'environment': {
            'cwd': os.getcwd(),
            'virtual_env': os.environ.get('VIRTUAL_ENV'),
            'path': os.environ.get('PATH')
        },
        'validation_results': {}
    }
    
    # Run all validation checks
    python_ok, python_msg = check_python_version()
    report['validation_results']['python'] = {'success': python_ok, 'message': python_msg}
    
    venv_ok, venv_msg = check_virtual_environment()
    report['validation_results']['virtual_env'] = {'success': venv_ok, 'message': venv_msg}
    
    packages_ok, missing_packages = check_required_packages()
    report['validation_results']['packages'] = {
        'success': packages_ok, 
        'missing': missing_packages
    }
    
    structure_ok, missing_files = check_project_structure()
    report['validation_results']['structure'] = {
        'success': structure_ok,
        'missing_files': missing_files
    }
    
    config_ok, config_status = check_configuration()
    report['validation_results']['configuration'] = {
        'success': config_ok,
        'status': config_status
    }
    
    return report

def main():
    """Main validation workflow"""
    print_header("Opitios Alpaca Trading Service - Setup Validator")
    print(f"{Colors.WHITE}This interactive tool will validate your setup and help resolve any issues.{Colors.END}")
    
    # Initialize tracking
    total_checks = 0
    passed_checks = 0
    issues = []
    
    # Step 1: Python Version Check
    print_step("1", "Checking Python version compatibility")
    total_checks += 1
    python_ok, python_msg = check_python_version()
    if python_ok:
        print_success(python_msg)
        passed_checks += 1
    else:
        print_error(python_msg)
        issues.append("Python version incompatible")
    
    # Step 2: Virtual Environment Check
    print_step("2", "Checking virtual environment")
    total_checks += 1
    venv_ok, venv_msg = check_virtual_environment()
    if venv_ok:
        print_success(venv_msg)
        passed_checks += 1
    else:
        print_warning(venv_msg)
        print_error("Virtual environment not activated (CRITICAL per CLAUDE.md requirements)")
        issues.append("Virtual environment not activated")
    
    # Step 3: Package Dependencies
    print_step("3", "Checking required packages")
    total_checks += 1
    packages_ok, missing_packages = check_required_packages()
    if packages_ok:
        print_success("All required packages are installed")
        passed_checks += 1
    else:
        print_error(f"Missing packages: {', '.join(missing_packages)}")
        issues.append("Missing required packages")
    
    # Step 4: Project Structure
    print_step("4", "Validating project structure")
    total_checks += 1
    structure_ok, missing_files = check_project_structure()
    if structure_ok:
        print_success("Project structure is correct")
        passed_checks += 1
    else:
        print_error(f"Missing files: {', '.join(missing_files)}")
        issues.append("Incomplete project structure")
    
    # Step 5: Configuration
    print_step("5", "Checking configuration")
    total_checks += 1
    config_ok, config_status = check_configuration()
    if config_ok:
        print_success("Configuration is valid")
        for key, value in config_status.items():
            print_info(f"{key}: {value}")
        passed_checks += 1
    else:
        print_error("Configuration issues detected")
        for key, value in config_status.items():
            if "NOT SET" in str(value) or "Invalid" in str(value):
                print_error(f"{key}: {value}")
            else:
                print_info(f"{key}: {value}")
        issues.append("Configuration problems")
    
    # Step 6: API Connectivity (only if config is OK)
    if config_ok:
        print_step("6", "Testing Alpaca API connectivity")
        total_checks += 1
        api_ok, api_msg = test_api_connectivity()
        if api_ok:
            print_success(api_msg)
            passed_checks += 1
        else:
            print_error(api_msg)
            issues.append("API connectivity problems")
    
    # Step 7: Local Server Test (only if previous checks pass)
    if passed_checks >= 4:  # Basic requirements met
        print_step("7", "Testing local server startup")
        total_checks += 1
        server_ok, server_msg = test_local_server()
        if server_ok:
            print_success(server_msg)
            passed_checks += 1
        else:
            print_error(server_msg)
            issues.append("Server startup problems")
    
    # Results Summary
    print_header("Validation Results")
    success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
    
    print(f"{Colors.BOLD}Validation Summary:{Colors.END}")
    print(f"Passed: {Colors.GREEN}{passed_checks}{Colors.END}/{total_checks}")
    print(f"Success Rate: {Colors.GREEN if success_rate >= 90 else Colors.YELLOW if success_rate >= 70 else Colors.RED}{success_rate:.1f}%{Colors.END}")
    
    if success_rate >= 90:
        print_success("🎉 Excellent! Your setup is ready for production use.")
    elif success_rate >= 70:
        print_warning("⚠️  Your setup is mostly ready but has some issues to resolve.")
    else:
        print_error("❌ Your setup needs attention before it will work properly.")
    
    # Interactive Problem Solving
    if issues:
        solve_problems = get_user_input("Would you like help solving these issues? (y/n)", "y")
        if solve_problems.lower().startswith('y'):
            interactive_problem_solver(issues)
    
    # Platform-specific help
    if success_rate < 90:
        show_help = get_user_input("Would you like platform-specific setup instructions? (y/n)", "y")
        if show_help.lower().startswith('y'):
            provide_platform_specific_help()
    
    # Generate diagnostic report
    generate_report = get_user_input("Generate diagnostic report for troubleshooting? (y/n)", "n")
    if generate_report.lower().startswith('y'):
        report = generate_diagnostic_report()
        report_file = 'setup_diagnostic_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print_success(f"Diagnostic report saved to: {report_file}")
    
    # Next Steps
    print_header("Next Steps")
    if success_rate >= 90:
        print("🚀 You're ready to go! Try these commands:")
        print("   python main.py                    # Start the server")
        print("   curl http://localhost:8081/docs   # View API documentation")
    else:
        print("🔧 Resolve the issues above, then run this validator again:")
        print("   python docs/scripts/setup_validator.py")
    
    print(f"\n{Colors.BOLD}For more help:{Colors.END}")
    print("📖 Quick Start Guide: docs/en/quickstart.md")
    print("🔍 Troubleshooting: docs/en/troubleshooting.md")
    print("🌐 API Examples: docs/en/api-examples.md")
    
    return success_rate >= 90

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Validation cancelled by user.{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {str(e)}{Colors.END}")
        sys.exit(1)