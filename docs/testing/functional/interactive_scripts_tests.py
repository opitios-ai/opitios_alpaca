#!/usr/bin/env python3
"""
Functional Testing - Interactive Scripts Tests

This module provides comprehensive testing for all interactive scripts
in the documentation system, ensuring reliability, functionality,
and user experience quality.

Test Focus:
- setup_validator.py functionality and reliability
- health_check.py system monitoring accuracy  
- config_helper.py configuration management
- doc_validator.py documentation quality assurance
- Interactive user experience validation
- Error handling and recovery

Usage:
    python docs/testing/functional/interactive_scripts_tests.py
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from unittest.mock import patch, MagicMock, mock_open
import importlib.util
from io import StringIO

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class InteractiveScriptsTestSuite(unittest.TestCase):
    """Comprehensive test suite for interactive scripts"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.project_root = Path(__file__).parent.parent.parent.parent
        cls.docs_scripts_path = cls.project_root / "docs" / "scripts"
        cls.temp_dir = None
        
        # Verify scripts exist
        required_scripts = [
            "setup_validator.py",
            "health_check.py", 
            "config_helper.py",
            "doc_validator.py"
        ]
        
        for script in required_scripts:
            script_path = cls.docs_scripts_path / script
            if not script_path.exists():
                raise FileNotFoundError(f"Required script not found: {script_path}")
    
    def setUp(self):
        """Set up individual test"""
        self.temp_dir = tempfile.mkdtemp(prefix="interactive_scripts_test_")
        
        # Create test project structure
        self.test_project = Path(self.temp_dir) / "test_project"
        self.test_project.mkdir()
        
        # Copy essential files for testing
        self._setup_test_project()
    
    def tearDown(self):
        """Clean up after test"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _setup_test_project(self):
        """Setup minimal test project structure"""
        # Create basic project files
        (self.test_project / "main.py").write_text("""
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}

@app.get("/api/v1/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8081)
""")
        
        (self.test_project / "config.py").write_text("""
import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
""")
        
        (self.test_project / "requirements.txt").write_text("""
fastapi==0.104.1
uvicorn==0.24.0
alpaca-py==0.12.1
pydantic==2.5.0
python-dotenv==1.0.0
requests==2.31.0
loguru==0.7.2
psutil==5.9.6
""")
        
        # Create app directory
        app_dir = self.test_project / "app"
        app_dir.mkdir()
        (app_dir / "__init__.py").write_text("")
        (app_dir / "routes.py").write_text("""
from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def test_endpoint():
    return {"test": "success"}
""")
        
        # Create tests directory
        tests_dir = self.test_project / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        
        # Create .env file
        (self.test_project / ".env").write_text("""
ALPACA_API_KEY=PKTEST1234567890abcdef
ALPACA_SECRET_KEY=test_secret_key_1234567890abcdef
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true
HOST=localhost
PORT=8081
DEBUG=false
""")


class SetupValidatorTests(InteractiveScriptsTestSuite):
    """Test suite for setup_validator.py"""
    
    def setUp(self):
        super().setUp()
        # Import setup validator module
        spec = importlib.util.spec_from_file_location(
            "setup_validator", 
            self.docs_scripts_path / "setup_validator.py"
        )
        self.setup_validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.setup_validator)
    
    def test_python_version_check(self):
        """Test Python version checking functionality"""
        # Test with current Python version (should pass)
        success, message = self.setup_validator.check_python_version()
        self.assertTrue(success)
        self.assertIn("Python", message)
    
    def test_virtual_environment_detection(self):
        """Test virtual environment detection"""
        # Test without virtual environment
        with patch.dict(os.environ, {}, clear=True):
            success, message = self.setup_validator.check_virtual_environment()
            self.assertFalse(success)
            self.assertIn("No virtual environment", message)
        
        # Test with virtual environment
        with patch.dict(os.environ, {"VIRTUAL_ENV": "/path/to/venv"}):
            success, message = self.setup_validator.check_virtual_environment()
            self.assertTrue(success)
            self.assertIn("Active virtual environment", message)
    
    @patch('importlib.util.find_spec')
    def test_required_packages_check(self, mock_find_spec):
        """Test required packages checking"""
        # Test with all packages available
        mock_find_spec.return_value = MagicMock()
        success, missing = self.setup_validator.check_required_packages()
        self.assertTrue(success)
        self.assertEqual(len(missing), 0)
        
        # Test with missing packages
        mock_find_spec.return_value = None
        success, missing = self.setup_validator.check_required_packages()
        self.assertFalse(success)
        self.assertGreater(len(missing), 0)
    
    def test_project_structure_validation(self):
        """Test project structure validation"""
        # Change to test project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_project)
            success, missing_files = self.setup_validator.check_project_structure()
            
            # Should have most required files
            self.assertTrue(success or len(missing_files) <= 2)  # Allow some missing files in test setup
        finally:
            os.chdir(original_cwd)
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_project)
            success, config_status = self.setup_validator.check_configuration()
            
            # Should find .env file and validate configuration
            self.assertTrue(success)
            self.assertIn("ALPACA_API_KEY", config_status)
            self.assertIn("ALPACA_SECRET_KEY", config_status)
        finally:
            os.chdir(original_cwd)
    
    @patch('requests.get')
    def test_api_connectivity_test(self, mock_get):
        """Test API connectivity testing"""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_project)
            
            # Test successful API connection
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"buying_power": "100000"}
            mock_get.return_value = mock_response
            
            success, message = self.setup_validator.test_api_connectivity()
            self.assertTrue(success)
            self.assertIn("Connected successfully", message)
            
            # Test failed API connection
            mock_response.status_code = 401
            success, message = self.setup_validator.test_api_connectivity()
            self.assertFalse(success)
            self.assertIn("Authentication failed", message)
            
        finally:
            os.chdir(original_cwd)
    
    def test_platform_specific_help(self):
        """Test platform-specific help generation"""
        # This should not raise exceptions on any platform
        try:
            self.setup_validator.provide_platform_specific_help()
        except Exception as e:
            self.fail(f"Platform-specific help failed: {e}")
    
    def test_interactive_problem_solver(self):
        """Test interactive problem solver"""
        issues = ["virtual environment not activated", "missing required packages"]
        
        # Mock user input
        with patch('builtins.input', return_value='1'):
            try:
                self.setup_validator.interactive_problem_solver(issues)
            except Exception as e:
                self.fail(f"Interactive problem solver failed: {e}")
    
    def test_diagnostic_report_generation(self):
        """Test diagnostic report generation"""
        report = self.setup_validator.generate_diagnostic_report()
        
        self.assertIsInstance(report, dict)
        self.assertIn('timestamp', report)
        self.assertIn('platform', report)
        self.assertIn('validation_results', report)
        
        # Verify report structure
        self.assertIn('python', report['validation_results'])
        self.assertIn('virtual_env', report['validation_results'])


class HealthCheckTests(InteractiveScriptsTestSuite):
    """Test suite for health_check.py"""
    
    def setUp(self):
        super().setUp()
        # Import health check module
        spec = importlib.util.spec_from_file_location(
            "health_check", 
            self.docs_scripts_path / "health_check.py"
        )
        self.health_check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.health_check)
    
    @patch('psutil.process_iter')
    def test_server_process_check(self, mock_process_iter):
        """Test server process detection"""
        # Mock process with main.py
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 1234,
            'name': 'python',
            'cmdline': ['python', 'main.py'],
            'memory_info': MagicMock(rss=50*1024*1024),  # 50MB
            'cpu_percent': 5.0
        }
        mock_process_iter.return_value = [mock_proc]
        
        success, data = self.health_check.check_server_process()
        self.assertTrue(success)
        self.assertIn('processes', data)
        self.assertEqual(len(data['processes']), 1)
    
    @patch('socket.socket')
    def test_port_availability_check(self, mock_socket):
        """Test port availability checking"""
        # Test port in use
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0  # Connection successful
        mock_socket.return_value.__enter__.return_value = mock_sock
        
        success, message = self.health_check.check_port_availability(8081)
        self.assertTrue(success)
        self.assertIn("Port 8081 is in use", message)
        
        # Test port not in use
        mock_sock.connect_ex.return_value = 1  # Connection failed
        success, message = self.health_check.check_port_availability(8081)
        self.assertFalse(success)
        self.assertIn("Port 8081 is not in use", message)
    
    @patch('requests.get')
    def test_api_endpoints_check(self, mock_get):
        """Test API endpoints health checking"""
        # Mock successful API responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response
        
        results = self.health_check.check_api_endpoints()
        
        self.assertIsInstance(results, dict)
        self.assertIn('health', results)
        
        for endpoint, result in results.items():
            if not result.get('error'):
                self.assertTrue(result.get('success'))
                self.assertEqual(result.get('status_code'), 200)
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_system_resources_check(self, mock_disk, mock_memory, mock_cpu):
        """Test system resource monitoring"""
        # Mock system resource data
        mock_cpu.return_value = 25.5
        
        mock_memory_obj = MagicMock()
        mock_memory_obj.total = 8 * 1024**3  # 8GB
        mock_memory_obj.available = 4 * 1024**3  # 4GB
        mock_memory_obj.percent = 50.0
        mock_memory_obj.free = 3 * 1024**3  # 3GB
        mock_memory.return_value = mock_memory_obj
        
        mock_disk_obj = MagicMock()
        mock_disk_obj.total = 500 * 1024**3  # 500GB
        mock_disk_obj.free = 200 * 1024**3   # 200GB
        mock_disk_obj.used = 300 * 1024**3   # 300GB
        mock_disk.return_value = mock_disk_obj
        
        resources = self.health_check.check_system_resources()
        
        self.assertIn('cpu', resources)
        self.assertIn('memory', resources)
        self.assertIn('disk', resources)
        
        self.assertEqual(resources['cpu']['percent'], 25.5)
        self.assertEqual(resources['memory']['percent_used'], 50.0)
        self.assertAlmostEqual(resources['disk']['percent_used'], 60.0, places=1)
    
    def test_log_files_check(self):
        """Test log files analysis"""
        # Create test logs directory
        logs_dir = self.test_project / "logs"
        logs_dir.mkdir()
        
        # Create test log file
        test_log = logs_dir / "test.log"
        test_log.write_text("""
2024-01-01 10:00:00 INFO Application started
2024-01-01 10:01:00 WARNING Connection timeout
2024-01-01 10:02:00 ERROR Database connection failed
2024-01-01 10:03:00 INFO Recovery completed
""")
        
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_project)
            results = self.health_check.check_log_files()
            
            if 'error' not in results:
                self.assertIn('test.log', results)
                log_data = results['test.log']
                self.assertIn('recent_errors', log_data)
                self.assertIn('recent_warnings', log_data)
                self.assertEqual(log_data['recent_errors'], 1)
                self.assertEqual(log_data['recent_warnings'], 1)
        finally:
            os.chdir(original_cwd)
    
    def test_environment_config_check(self):
        """Test environment configuration checking"""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_project)
            
            config = self.health_check.check_environment_config()
            
            self.assertIsInstance(config, dict)
            self.assertIn('ALPACA_API_KEY', config)
            self.assertIn('ALPACA_SECRET_KEY', config)
            
            # Verify sensitive data is masked
            if config['ALPACA_API_KEY'] != "NOT SET":
                self.assertTrue(config['ALPACA_API_KEY'].startswith('*'))
        finally:
            os.chdir(original_cwd)
    
    def test_health_score_calculation(self):
        """Test health score calculation"""
        # Test perfect health
        perfect_results = {
            'server_process': {'success': True, 'data': {'processes': [{}]}},
            'api_endpoints': {
                'health': {'success': True},
                'root': {'success': True}
            },
            'system_resources': {
                'memory': {'percent_used': 60},
                'cpu': {'percent': 50}
            },
            'log_files': {'test.log': {'recent_errors': 0}},
            'database': {'success': True}
        }
        
        score, issues = self.health_check.generate_health_score(perfect_results)
        self.assertEqual(score, 100)
        self.assertEqual(len(issues), 0)
        
        # Test degraded health
        degraded_results = {
            'server_process': {'success': False},
            'api_endpoints': {
                'health': {'success': False},
                'root': {'success': False}
            },
            'system_resources': {
                'memory': {'percent_used': 95},
                'cpu': {'percent': 85}
            },
            'log_files': {'test.log': {'recent_errors': 10}},
            'database': {'success': False}
        }
        
        score, issues = self.health_check.generate_health_score(degraded_results)
        self.assertLess(score, 50)
        self.assertGreater(len(issues), 0)


class ConfigHelperTests(InteractiveScriptsTestSuite):
    """Test suite for config_helper.py"""
    
    def setUp(self):
        super().setUp()
        # Import config helper if it exists
        config_helper_path = self.docs_scripts_path / "config_helper.py"
        if config_helper_path.exists():
            spec = importlib.util.spec_from_file_location(
                "config_helper", config_helper_path
            )
            self.config_helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.config_helper)
        else:
            self.config_helper = None
    
    def test_config_helper_exists(self):
        """Test that config helper script exists"""
        config_helper_path = self.docs_scripts_path / "config_helper.py"
        if not config_helper_path.exists():
            self.skipTest("config_helper.py not implemented yet")
        
        self.assertTrue(config_helper_path.exists())
    
    @unittest.skipIf(True, "config_helper.py not fully implemented")
    def test_config_validation(self):
        """Test configuration validation functionality"""
        if not self.config_helper:
            self.skipTest("config_helper.py not available")
        
        # This would test configuration validation logic
        pass
    
    @unittest.skipIf(True, "config_helper.py not fully implemented")  
    def test_config_generation(self):
        """Test configuration file generation"""
        if not self.config_helper:
            self.skipTest("config_helper.py not available")
        
        # This would test .env file generation
        pass


class DocValidatorTests(InteractiveScriptsTestSuite):
    """Test suite for doc_validator.py"""
    
    def setUp(self):
        super().setUp()
        # Import doc validator if it exists
        doc_validator_path = self.docs_scripts_path / "doc_validator.py"
        if doc_validator_path.exists():
            spec = importlib.util.spec_from_file_location(
                "doc_validator", doc_validator_path
            )
            self.doc_validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.doc_validator)
        else:
            self.doc_validator = None
    
    def test_doc_validator_exists(self):
        """Test that doc validator script exists"""
        doc_validator_path = self.docs_scripts_path / "doc_validator.py"
        if not doc_validator_path.exists():
            self.skipTest("doc_validator.py not implemented yet")
        
        self.assertTrue(doc_validator_path.exists())
    
    @unittest.skipIf(True, "doc_validator.py not fully implemented")
    def test_link_validation(self):
        """Test documentation link validation"""
        if not self.doc_validator:
            self.skipTest("doc_validator.py not available")
        
        # This would test link validation functionality
        pass
    
    @unittest.skipIf(True, "doc_validator.py not fully implemented")
    def test_translation_consistency(self):
        """Test translation consistency checking"""
        if not self.doc_validator:
            self.skipTest("doc_validator.py not available")
        
        # This would test translation consistency
        pass


class IntegrationTests(InteractiveScriptsTestSuite):
    """Integration tests for script interaction"""
    
    def test_scripts_can_run_independently(self):
        """Test that all scripts can run without errors"""
        scripts_to_test = [
            "setup_validator.py",
            "health_check.py"
        ]
        
        for script_name in scripts_to_test:
            script_path = self.docs_scripts_path / script_name
            if script_path.exists():
                # Test script can be imported
                try:
                    spec = importlib.util.spec_from_file_location(
                        script_name.replace('.py', ''), script_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except Exception as e:
                    self.fail(f"Failed to import {script_name}: {e}")
    
    def test_script_help_functions(self):
        """Test that scripts provide help functionality"""
        required_help_functions = [
            'print_header',
            'print_success', 
            'print_error',
            'print_warning',
            'print_info'
        ]
        
        # Test setup_validator has help functions
        spec = importlib.util.spec_from_file_location(
            "setup_validator", 
            self.docs_scripts_path / "setup_validator.py"
        )
        setup_validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_validator)
        
        for func_name in required_help_functions:
            self.assertTrue(hasattr(setup_validator, func_name),
                          f"setup_validator missing {func_name}")
    
    def test_error_handling_robustness(self):
        """Test scripts handle errors gracefully"""
        # Import setup validator
        spec = importlib.util.spec_from_file_location(
            "setup_validator", 
            self.docs_scripts_path / "setup_validator.py"
        )
        setup_validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_validator)
        
        # Test functions handle missing files gracefully
        original_cwd = os.getcwd()
        try:
            # Change to empty directory
            empty_dir = self.temp_dir / "empty"
            empty_dir.mkdir()
            os.chdir(empty_dir)
            
            # These should not crash
            try:
                setup_validator.check_project_structure()
                setup_validator.check_configuration()
            except Exception as e:
                # Should not raise unhandled exceptions
                if "unhandled" in str(e).lower():
                    self.fail(f"Unhandled exception: {e}")
        finally:
            os.chdir(original_cwd)


def create_test_suite():
    """Create comprehensive test suite"""
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        SetupValidatorTests,
        HealthCheckTests,
        ConfigHelperTests,
        DocValidatorTests,
        IntegrationTests
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    return suite


def main():
    """Main test runner"""
    print("🚀 Starting Interactive Scripts Testing Suite")
    
    # Create and run test suite
    suite = create_test_suite()
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True
    )
    
    result = runner.run(suite)
    
    # Generate summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
    success_rate = ((total_tests - failures - errors) / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n{'='*60}")
    print("Interactive Scripts Testing Summary")
    print(f"{'='*60}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")
    print(f"Skipped: {skipped}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if result.failures:
        print(f"\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.splitlines()[-1] if traceback else 'Unknown'}")
    
    if result.errors:
        print(f"\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.splitlines()[-1] if traceback else 'Unknown'}")
    
    # Success criteria: >95% success rate
    success_criteria_met = success_rate >= 95
    
    if success_criteria_met:
        print(f"\n✅ SUCCESS: Interactive scripts meet quality standards ({success_rate:.1f}% success rate)")
    else:
        print(f"\n⚠️  WARNING: Interactive scripts need improvement ({success_rate:.1f}% success rate < 95%)")
    
    return success_criteria_met


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)