#!/usr/bin/env python3
"""
Comprehensive Test Runner
Runs all tests with proper error handling and timeout management.
"""

import subprocess
import sys
import time
from pathlib import Path

def run_command_with_timeout(cmd, timeout=300, cwd=None):
    """Run command with timeout to avoid hanging."""
    try:
        print(f"🚀 Running: {' '.join(cmd)}")
        start_time = time.time()
        
        result = subprocess.run(
            cmd, 
            cwd=cwd,
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"✅ Command completed successfully in {duration:.1f}s")
            return True, result.stdout, result.stderr
        else:
            print(f"❌ Command failed with return code {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False, result.stdout, result.stderr
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Command timed out after {timeout}s")
        return False, "", "Command timed out"
    except Exception as e:
        print(f"💥 Command failed with exception: {e}")
        return False, "", str(e)

def main():
    """Run comprehensive test suite."""
    print("🧪 Starting Comprehensive Test Suite")
    print("=" * 50)
    
    # Change to project directory
    project_dir = Path(__file__).parent
    
    # Test categories to run
    test_categories = [
        {
            "name": "Linting",
            "cmd": ["python", "-m", "flake8", "app/", "tests/", "--select=E9,F63,F7,F82", "--count"],
            "timeout": 60
        },
        {
            "name": "Unit Tests",
            "cmd": ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short", "-x"],
            "timeout": 180
        },
        {
            "name": "Security Tests", 
            "cmd": ["python", "-m", "pytest", "tests/security/", "-v", "--tb=short", "-x"],
            "timeout": 120
        },
        {
            "name": "Performance Tests",
            "cmd": ["python", "-m", "pytest", "tests/performance/", "-v", "--tb=short", "-x"],
            "timeout": 120
        },
        {
            "name": "Coverage Report",
            "cmd": ["python", "-m", "pytest", "tests/unit/", "--cov=app", "--cov-report=term-missing", "--cov-report=xml"],
            "timeout": 180
        }
    ]
    
    results = []
    
    for test_category in test_categories:
        print(f"\n📋 Running {test_category['name']}...")
        print("-" * 30)
        
        success, stdout, stderr = run_command_with_timeout(
            test_category["cmd"],
            timeout=test_category["timeout"],
            cwd=project_dir
        )
        
        results.append({
            "name": test_category["name"],
            "success": success,
            "stdout": stdout,
            "stderr": stderr
        })
        
        if not success:
            print(f"⚠️  {test_category['name']} failed, but continuing...")
    
    # Print final summary
    print("\n" + "=" * 50)
    print("📊 FINAL TEST RESULTS")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for result in results:
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{result['name']:<20} {status}")
        
        if result["success"]:
            passed += 1
        else:
            failed += 1
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")
        return 0
    else:
        print(f"\n⚠️  {failed} test categories failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())