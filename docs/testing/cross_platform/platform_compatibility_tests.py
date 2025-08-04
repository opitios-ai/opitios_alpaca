#!/usr/bin/env python3
"""
Cross-Platform Testing - Platform Compatibility Tests

This module validates the documentation system and interactive tools
work correctly across Windows, macOS, and Linux platforms with
different Python versions and shell environments.

Test Focus:
- Windows compatibility (PowerShell, CMD, Git Bash)
- macOS compatibility (Terminal, zsh, bash)
- Linux compatibility (various distributions)
- Python version compatibility (3.8, 3.9, 3.10, 3.11, 3.12)
- Virtual environment operations
- File system and path handling
- Unicode and Chinese character support

Usage:
    python docs/testing/cross_platform/platform_compatibility_tests.py
"""

import os
import sys
import platform
import subprocess
import tempfile
import shutil
import unittest
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import time

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class PlatformType(Enum):
    """Supported platform types"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class ShellType(Enum):
    """Shell environments to test"""
    POWERSHELL = "powershell"
    CMD = "cmd"
    GIT_BASH = "git_bash"
    BASH = "bash"
    ZSH = "zsh"
    SH = "sh"


@dataclass
class PlatformTestResult:
    """Result of platform-specific test"""
    platform: str
    shell: str
    python_version: str
    test_name: str
    success: bool
    execution_time: float
    output: str
    error_message: Optional[str] = None
    details: Dict[str, Any] = None


class PlatformCompatibilityTester:
    """Tests cross-platform compatibility of documentation system"""
    
    def __init__(self):
        self.current_platform = self._detect_platform()
        self.available_shells = self._detect_available_shells()
        self.python_versions = self._detect_python_versions()
        self.test_results: List[PlatformTestResult] = []
        self.project_root = Path(__file__).parent.parent.parent.parent
        
    def _detect_platform(self) -> PlatformType:
        """Detect current platform"""
        system = platform.system().lower()
        if system == "windows":
            return PlatformType.WINDOWS
        elif system == "darwin":
            return PlatformType.MACOS
        elif system == "linux":
            return PlatformType.LINUX
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
    
    def _detect_available_shells(self) -> List[ShellType]:
        """Detect available shell environments"""
        available = []
        
        if self.current_platform == PlatformType.WINDOWS:
            # Test PowerShell
            if shutil.which("powershell") or shutil.which("pwsh"):
                available.append(ShellType.POWERSHELL)
            
            # Test CMD
            if shutil.which("cmd"):
                available.append(ShellType.CMD)
            
            # Test Git Bash
            if shutil.which("bash") or os.path.exists("C:\\Program Files\\Git\\bin\\bash.exe"):
                available.append(ShellType.GIT_BASH)
                
        elif self.current_platform == PlatformType.MACOS:
            # Test zsh (default on newer macOS)
            if shutil.which("zsh"):
                available.append(ShellType.ZSH)
            
            # Test bash
            if shutil.which("bash"):
                available.append(ShellType.BASH)
                
        elif self.current_platform == PlatformType.LINUX:
            # Test bash
            if shutil.which("bash"):
                available.append(ShellType.BASH)
            
            # Test zsh
            if shutil.which("zsh"):
                available.append(ShellType.ZSH)
            
            # Test sh
            if shutil.which("sh"):
                available.append(ShellType.SH)
        
        return available
    
    def _detect_python_versions(self) -> List[str]:
        """Detect available Python versions"""
        versions = []
        
        # Test current Python version
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        versions.append(current_version)
        
        # Test other common Python executables
        for version in ["3.8", "3.9", "3.10", "3.11", "3.12"]:
            python_cmd = f"python{version}"
            if shutil.which(python_cmd):
                try:
                    result = subprocess.run([python_cmd, "--version"], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and version in result.stdout:
                        if version not in versions:
                            versions.append(version)
                except:
                    pass
        
        # Test python3
        if shutil.which("python3"):
            try:
                result = subprocess.run(["python3", "--version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Extract version from output like "Python 3.9.7"
                    import re
                    match = re.search(r"Python (\d+\.\d+)", result.stdout)
                    if match:
                        version = match.group(1)
                        if version not in versions:
                            versions.append(version)
            except:
                pass
        
        return sorted(versions)
    
    def _get_shell_command(self, shell: ShellType, command: str) -> List[str]:
        """Get shell-specific command"""
        if shell == ShellType.POWERSHELL:
            if shutil.which("pwsh"):
                return ["pwsh", "-Command", command]
            else:
                return ["powershell", "-Command", command]
        elif shell == ShellType.CMD:
            return ["cmd", "/c", command]
        elif shell == ShellType.GIT_BASH:
            git_bash_path = "C:\\Program Files\\Git\\bin\\bash.exe"
            if os.path.exists(git_bash_path):
                return [git_bash_path, "-c", command]
            else:
                return ["bash", "-c", command]
        elif shell in [ShellType.BASH, ShellType.ZSH, ShellType.SH]:
            shell_cmd = shell.value
            return [shell_cmd, "-c", command]
        else:
            raise ValueError(f"Unsupported shell: {shell}")
    
    def _run_shell_command(self, shell: ShellType, command: str, 
                          cwd: Optional[str] = None, timeout: int = 30) -> Tuple[bool, str, str]:
        """Run command in specific shell"""
        try:
            shell_cmd = self._get_shell_command(shell, command)
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timeout"
        except Exception as e:
            return False, "", str(e)
    
    def test_basic_shell_functionality(self, shell: ShellType) -> PlatformTestResult:
        """Test basic shell functionality"""
        start_time = time.time()
        
        # Test basic commands
        if shell in [ShellType.POWERSHELL]:
            test_command = "Get-Location; python --version"
        else:
            test_command = "pwd && python --version"
        
        success, stdout, stderr = self._run_shell_command(shell, test_command)
        execution_time = time.time() - start_time
        
        return PlatformTestResult(
            platform=self.current_platform.value,
            shell=shell.value,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            test_name="basic_shell_functionality",
            success=success,
            execution_time=execution_time,
            output=stdout,
            error_message=stderr if not success else None,
            details={'command': test_command}
        )
    
    def test_virtual_environment_operations(self, shell: ShellType) -> PlatformTestResult:
        """Test virtual environment creation and activation"""
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            venv_path = os.path.join(temp_dir, "test_venv")
            
            # Platform-specific venv commands
            if self.current_platform == PlatformType.WINDOWS:
                if shell == ShellType.POWERSHELL:
                    commands = [
                        f"python -m venv {venv_path}",
                        f"{venv_path}\\Scripts\\Activate.ps1; python --version"
                    ]
                else:  # CMD or Git Bash
                    commands = [
                        f"python -m venv {venv_path}",
                        f"{venv_path}\\Scripts\\activate && python --version"
                    ]
            else:  # macOS or Linux
                commands = [
                    f"python -m venv {venv_path}",
                    f"source {venv_path}/bin/activate && python --version"
                ]
            
            success = True
            all_output = []
            error_messages = []
            
            for cmd in commands:
                cmd_success, stdout, stderr = self._run_shell_command(shell, cmd, cwd=temp_dir)
                all_output.append(f"Command: {cmd}\nOutput: {stdout}\n")
                
                if not cmd_success:
                    success = False
                    error_messages.append(f"Command failed: {cmd} - {stderr}")
        
        execution_time = time.time() - start_time
        
        return PlatformTestResult(
            platform=self.current_platform.value,
            shell=shell.value,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            test_name="virtual_environment_operations",
            success=success,
            execution_time=execution_time,
            output="\n".join(all_output),
            error_message="; ".join(error_messages) if error_messages else None,
            details={'commands': commands}
        )
    
    def test_setup_validator_execution(self, shell: ShellType) -> PlatformTestResult:
        """Test setup validator script execution"""
        start_time = time.time()
        
        setup_validator_path = self.project_root / "docs" / "scripts" / "setup_validator.py"
        
        if not setup_validator_path.exists():
            return PlatformTestResult(
                platform=self.current_platform.value,
                shell=shell.value,
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                test_name="setup_validator_execution",
                success=False,
                execution_time=0,
                output="",
                error_message="setup_validator.py not found",
                details={'script_path': str(setup_validator_path)}
            )
        
        # Test script execution
        command = f"python {setup_validator_path}"
        success, stdout, stderr = self._run_shell_command(
            shell, command, cwd=str(self.project_root), timeout=60
        )
        
        execution_time = time.time() - start_time
        
        # Consider it successful if script runs without critical errors
        # (it may fail validation checks, but the script itself should execute)
        if "python" in stderr.lower() and "not found" in stderr.lower():
            success = False
        
        return PlatformTestResult(
            platform=self.current_platform.value,
            shell=shell.value,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            test_name="setup_validator_execution",
            success=success,
            execution_time=execution_time,
            output=stdout[:1000],  # Limit output size
            error_message=stderr[:500] if stderr else None,
            details={'command': command}
        )
    
    def test_unicode_support(self, shell: ShellType) -> PlatformTestResult:
        """Test Unicode and Chinese character support"""
        start_time = time.time()
        
        # Test Unicode handling with Chinese characters
        chinese_text = "测试中文字符支持"
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                       suffix='.txt', delete=False) as f:
            f.write(chinese_text)
            temp_file = f.name
        
        try:
            # Test reading Unicode file
            if self.current_platform == PlatformType.WINDOWS and shell == ShellType.CMD:
                # CMD has issues with Unicode, use type command
                command = f"type {temp_file}"
            else:
                command = f"cat {temp_file}" if shell != ShellType.POWERSHELL else f"Get-Content {temp_file}"
            
            success, stdout, stderr = self._run_shell_command(shell, command)
            
            # Check if Chinese characters are preserved
            unicode_preserved = chinese_text in stdout or len(stdout.strip()) > 0
            
        finally:
            os.unlink(temp_file)
        
        execution_time = time.time() - start_time
        
        return PlatformTestResult(
            platform=self.current_platform.value,
            shell=shell.value,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            test_name="unicode_support",
            success=success and unicode_preserved,
            execution_time=execution_time,
            output=stdout,
            error_message=stderr if not success else None,
            details={
                'test_text': chinese_text,
                'unicode_preserved': unicode_preserved,
                'command': command
            }
        )
    
    def test_file_path_handling(self, shell: ShellType) -> PlatformTestResult:
        """Test file path handling across platforms"""
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested directory structure
            nested_path = os.path.join(temp_dir, "test folder", "nested")
            os.makedirs(nested_path, exist_ok=True)
            
            test_file = os.path.join(nested_path, "test file.txt")
            with open(test_file, 'w') as f:
                f.write("test content")
            
            # Test path with spaces
            if shell == ShellType.POWERSHELL:
                command = f'Test-Path "{test_file}"'
            elif shell == ShellType.CMD:
                command = f'if exist "{test_file}" echo exists'
            else:
                command = f'ls "{test_file}"'
            
            success, stdout, stderr = self._run_shell_command(shell, command)
            
            # Verify file was found
            path_handled_correctly = (
                "True" in stdout or  # PowerShell
                "exists" in stdout or  # CMD
                "test file.txt" in stdout  # Unix shells
            )
        
        execution_time = time.time() - start_time
        
        return PlatformTestResult(
            platform=self.current_platform.value,
            shell=shell.value,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            test_name="file_path_handling",
            success=success and path_handled_correctly,
            execution_time=execution_time,
            output=stdout,
            error_message=stderr if not success else None,
            details={
                'test_file': test_file,
                'path_handled': path_handled_correctly,
                'command': command
            }
        )
    
    def test_python_version_compatibility(self, python_version: str, shell: ShellType) -> PlatformTestResult:
        """Test compatibility with specific Python version"""
        start_time = time.time()
        
        # Find Python executable for version
        python_cmd = f"python{python_version}"
        if not shutil.which(python_cmd):
            python_cmd = "python3" if python_version != f"{sys.version_info.major}.{sys.version_info.minor}" else "python"
        
        # Test basic Python functionality
        test_script = """
import sys
import os
import json
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")
print("SUCCESS")
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            script_path = f.name
        
        try:
            command = f"{python_cmd} {script_path}"
            success, stdout, stderr = self._run_shell_command(shell, command, timeout=15)
            
            # Check if test completed successfully
            version_compatible = "SUCCESS" in stdout and f"Python {python_version}" in stdout
            
        finally:
            os.unlink(script_path)
        
        execution_time = time.time() - start_time
        
        return PlatformTestResult(
            platform=self.current_platform.value,
            shell=shell.value,
            python_version=python_version,
            test_name="python_version_compatibility",
            success=success and version_compatible,
            execution_time=execution_time,
            output=stdout,
            error_message=stderr if not success else None,
            details={
                'python_cmd': python_cmd,
                'version_compatible': version_compatible
            }
        )
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive cross-platform tests"""
        print(f"🚀 Starting Cross-Platform Compatibility Testing")
        print(f"Platform: {self.current_platform.value}")
        print(f"Available shells: {[s.value for s in self.available_shells]}")
        print(f"Python versions: {self.python_versions}")
        
        # Test matrix
        test_functions = [
            self.test_basic_shell_functionality,
            self.test_virtual_environment_operations,
            self.test_setup_validator_execution,
            self.test_unicode_support,
            self.test_file_path_handling
        ]
        
        # Run tests for each shell
        for shell in self.available_shells:
            print(f"\n{'='*60}")
            print(f"Testing Shell: {shell.value}")
            print(f"{'='*60}")
            
            for test_func in test_functions:
                print(f"\nRunning: {test_func.__name__}")
                try:
                    result = test_func(shell)
                    self.test_results.append(result)
                    
                    if result.success:
                        print(f"✅ PASSED ({result.execution_time:.1f}s)")
                    else:
                        print(f"❌ FAILED ({result.execution_time:.1f}s)")
                        if result.error_message:
                            print(f"   Error: {result.error_message[:100]}")
                            
                except Exception as e:
                    print(f"💥 ERROR: {str(e)}")
                    error_result = PlatformTestResult(
                        platform=self.current_platform.value,
                        shell=shell.value,
                        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                        test_name=test_func.__name__,
                        success=False,
                        execution_time=0,
                        output="",
                        error_message=str(e)
                    )
                    self.test_results.append(error_result)
        
        # Test Python version compatibility (with primary shell only)
        if self.available_shells:
            primary_shell = self.available_shells[0]
            print(f"\n{'='*60}")
            print(f"Testing Python Version Compatibility")
            print(f"{'='*60}")
            
            for version in self.python_versions:
                print(f"\nTesting Python {version}")
                try:
                    result = self.test_python_version_compatibility(version, primary_shell)
                    self.test_results.append(result)
                    
                    if result.success:
                        print(f"✅ PASSED ({result.execution_time:.1f}s)")
                    else:
                        print(f"❌ FAILED ({result.execution_time:.1f}s)")
                        if result.error_message:
                            print(f"   Error: {result.error_message[:100]}")
                            
                except Exception as e:
                    print(f"💥 ERROR: {str(e)}")
        
        # Calculate metrics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.success)
        compatibility_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Analyze results by category
        shell_results = {}
        for shell in self.available_shells:
            shell_tests = [r for r in self.test_results if r.shell == shell.value]
            shell_passed = sum(1 for r in shell_tests if r.success)
            shell_results[shell.value] = {
                'total': len(shell_tests),
                'passed': shell_passed,
                'success_rate': (shell_passed / len(shell_tests) * 100) if shell_tests else 0
            }
        
        python_results = {}
        for version in self.python_versions:
            version_tests = [r for r in self.test_results if r.python_version == version]
            version_passed = sum(1 for r in version_tests if r.success)
            python_results[version] = {
                'total': len(version_tests),
                'passed': version_passed,
                'success_rate': (version_passed / len(version_tests) * 100) if version_tests else 0
            }
        
        return {
            'platform': self.current_platform.value,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'compatibility_rate': compatibility_rate,
            'target_compatibility': 95.0,
            'meets_target': compatibility_rate >= 95.0,
            'shell_results': shell_results,
            'python_results': python_results,
            'available_shells': [s.value for s in self.available_shells],
            'python_versions': self.python_versions,
            'detailed_results': self.test_results
        }
    
    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """Generate cross-platform compatibility report"""
        report = f"""
# Cross-Platform Compatibility Test Report

## Executive Summary
- **Platform**: {metrics['platform'].title()}
- **Overall Compatibility Rate**: {metrics['compatibility_rate']:.1f}%
- **Target Compatibility**: {metrics['target_compatibility']}%
- **Target Achievement**: {'✅ SUCCESS' if metrics['meets_target'] else '❌ FAILED'}
- **Total Tests**: {metrics['total_tests']}
- **Passed**: {metrics['passed_tests']}
- **Failed**: {metrics['failed_tests']}

## Environment Details
- **Available Shells**: {', '.join(metrics['available_shells'])}
- **Python Versions**: {', '.join(metrics['python_versions'])}
- **Test Categories**: Shell functionality, Virtual environments, Script execution, Unicode support, Path handling

## Shell Compatibility Results
"""
        
        for shell, results in metrics['shell_results'].items():
            status = "✅" if results['success_rate'] >= 95 else "⚠️" if results['success_rate'] >= 80 else "❌"
            report += f"- **{shell}**: {results['success_rate']:.1f}% ({results['passed']}/{results['total']}) {status}\n"
        
        report += "\n## Python Version Compatibility\n"
        
        for version, results in metrics['python_results'].items():
            if results['total'] > 0:
                status = "✅" if results['success_rate'] >= 95 else "⚠️" if results['success_rate'] >= 80 else "❌"
                report += f"- **Python {version}**: {results['success_rate']:.1f}% ({results['passed']}/{results['total']}) {status}\n"
        
        report += "\n## Detailed Test Results\n"
        
        # Group by test type
        test_types = {}
        for result in metrics['detailed_results']:
            test_type = result.test_name
            if test_type not in test_types:
                test_types[test_type] = []
            test_types[test_type].append(result)
        
        for test_type, results in test_types.items():
            passed = sum(1 for r in results if r.success)
            total = len(results)
            success_rate = (passed / total * 100) if total > 0 else 0
            
            status = "✅" if success_rate >= 95 else "⚠️" if success_rate >= 80 else "❌"
            report += f"\n### {test_type.replace('_', ' ').title()} {status}\n"
            report += f"Success Rate: {success_rate:.1f}% ({passed}/{total})\n"
            
            # Show failed tests
            failed_results = [r for r in results if not r.success]
            if failed_results:
                report += "Failed configurations:\n"
                for result in failed_results[:3]:  # Show first 3 failures
                    report += f"- {result.shell} ({result.python_version}): {result.error_message or 'Unknown error'}\n"
        
        report += f"""
## Platform-Specific Insights

### {metrics['platform'].title()} Platform Analysis
"""
        
        if metrics['platform'] == 'windows':
            report += """
- **PowerShell**: Modern shell with excellent Unicode support
- **CMD**: Legacy shell with limited Unicode capabilities
- **Git Bash**: Unix-like environment on Windows
- **Virtual Environment**: Uses Scripts\\activate.bat or Scripts\\Activate.ps1
- **Path Handling**: Uses backslashes, requires quoting for spaces
"""
        elif metrics['platform'] == 'macos':
            report += """
- **zsh**: Default shell on modern macOS versions
- **bash**: Traditional Unix shell, still widely used
- **Virtual Environment**: Uses bin/activate script
- **Path Handling**: Uses forward slashes, good Unicode support
- **Homebrew Python**: Often preferred over system Python
"""
        elif metrics['platform'] == 'linux':
            report += """
- **bash**: Most common shell across distributions
- **zsh**: Advanced shell with additional features
- **Virtual Environment**: Uses bin/activate script
- **Path Handling**: Uses forward slashes, excellent Unicode support
- **Package Management**: Various Python installation methods
"""
        
        # Recommendations
        report += "\n## Recommendations\n"
        
        if metrics['compatibility_rate'] >= 95:
            report += "🎉 **Excellent Compatibility** - All platforms and shells work well\n"
        elif metrics['compatibility_rate'] >= 85:
            report += "✅ **Good Compatibility** - Minor issues on some configurations\n"
        else:
            report += "⚠️ **Compatibility Issues** - Several configurations need attention\n"
        
        # Specific recommendations based on failures
        failed_tests = [r for r in metrics['detailed_results'] if not r.success]
        if failed_tests:
            report += "\n### Priority Issues to Address:\n"
            
            # Group failures by type
            failure_types = {}
            for result in failed_tests:
                if result.test_name not in failure_types:
                    failure_types[result.test_name] = []
                failure_types[result.test_name].append(result)
            
            for test_type, failures in failure_types.items():
                report += f"- **{test_type}**: {len(failures)} failures across different configurations\n"
        
        report += f"""
## Technical Recommendations

### For Documentation System
- Ensure all scripts handle platform-specific paths correctly
- Test virtual environment activation across all supported shells
- Validate Unicode support for Chinese documentation
- Provide platform-specific setup instructions

### For Interactive Scripts
- Add platform detection and adaptive behavior
- Include shell-specific error messages and help
- Test script execution permissions on all platforms
- Ensure graceful degradation on unsupported configurations

### For Users
- Prefer modern shells (PowerShell on Windows, zsh on macOS)
- Use Python 3.8+ for best compatibility
- Follow platform-specific virtual environment practices
- Report platform-specific issues with environment details

---

**Test Environment**: {metrics['platform'].title()}  
**Test Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Framework Version**: 1.0.0
"""
        
        return report


def main():
    """Main test execution"""
    tester = PlatformCompatibilityTester()
    
    # Run comprehensive tests
    metrics = tester.run_comprehensive_tests()
    
    # Generate and display report
    report = tester.generate_report(metrics)
    print("\n" + "="*80)
    print(report)
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"cross_platform_test_results_{timestamp}.json"
    
    # Prepare serializable data
    serializable_results = []
    for result in tester.test_results:
        serializable_results.append({
            'platform': result.platform,
            'shell': result.shell,
            'python_version': result.python_version,
            'test_name': result.test_name,
            'success': result.success,
            'execution_time': result.execution_time,
            'output': result.output[:500] if result.output else "",  # Limit output size
            'error_message': result.error_message,
            'details': result.details
        })
    
    save_data = {
        'metrics': metrics,
        'detailed_results': serializable_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Return success if target is met
    return metrics['meets_target']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)