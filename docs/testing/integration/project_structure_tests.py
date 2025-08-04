#!/usr/bin/env python3
"""
Integration Testing - Project Structure and CLAUDE.md Compliance Tests

This module validates that the documentation enhancement implementation
integrates seamlessly with the existing project structure and complies
with all CLAUDE.md requirements and development standards.

Test Focus:
- CLAUDE.md compliance validation
- Project structure integrity
- Documentation organization standards
- Virtual environment requirements
- Configuration file compatibility
- Repository integration seamlessly
- Development workflow compliance

Usage:
    python docs/testing/integration/project_structure_tests.py
"""

import os
import sys
import re
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import yaml

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class ComplianceLevel(Enum):
    """Compliance check severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ComplianceIssue:
    """Issue found during compliance checking"""
    rule: str
    description: str
    file_path: Optional[str]
    severity: ComplianceLevel
    fix_suggestion: str
    line_number: Optional[int] = None


@dataclass
class IntegrationTestResult:
    """Result of integration test"""
    test_name: str
    success: bool
    issues: List[ComplianceIssue]
    compliance_rate: float
    details: Dict[str, Any]


class ProjectStructureIntegrationTester:
    """Tests integration with existing project structure and compliance"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.docs_path = self.project_root / "docs"
        self.results: List[IntegrationTestResult] = []
        
        # CLAUDE.md requirements
        self.claude_requirements = {
            'documentation_location': {
                'rule': 'All documentation MUST be in docs/ folder, NEVER in root',
                'critical': True
            },
            'virtual_environment': {
                'rule': 'ALWAYS use virtual environments - NO EXCEPTIONS',
                'critical': True
            },
            'python_commands': {
                'rule': 'All Python operations must be in virtual environment',
                'critical': True
            },
            'readme_location': {
                'rule': 'Use docs/README.md instead of root README.md',
                'critical': False
            },
            'no_root_docs': {
                'rule': 'NEVER place .md files in root directory (except CLAUDE.md)',
                'critical': True
            }
        }
    
    def _check_claude_md_compliance(self) -> IntegrationTestResult:
        """Check compliance with CLAUDE.md requirements"""
        print("🔍 Checking CLAUDE.md compliance...")
        
        issues = []
        
        # Check 1: All documentation in docs/ folder
        root_md_files = list(self.project_root.glob("*.md"))
        forbidden_files = [f for f in root_md_files if f.name.upper() != "CLAUDE.MD"]
        
        if forbidden_files:
            for file_path in forbidden_files:
                issues.append(ComplianceIssue(
                    rule="no_root_docs",
                    description=f"Documentation file in root directory: {file_path.name}",
                    file_path=str(file_path.relative_to(self.project_root)),
                    severity=ComplianceLevel.CRITICAL,
                    fix_suggestion=f"Move {file_path.name} to docs/ folder"
                ))
        
        # Check 2: docs/README.md exists instead of root README.md
        root_readme = self.project_root / "README.md"
        docs_readme = self.docs_path / "README.md"
        
        if root_readme.exists() and not docs_readme.exists():
            issues.append(ComplianceIssue(
                rule="readme_location",
                description="README.md in root instead of docs/",
                file_path="README.md",
                severity=ComplianceLevel.HIGH,
                fix_suggestion="Move README.md to docs/ folder as per CLAUDE.md requirements"
            ))
        
        # Check 3: Documentation structure follows CLAUDE.md standards
        expected_docs_structure = [
            "README.md",
            "en/quickstart.md",
            "en/api-examples.md", 
            "en/troubleshooting.md",
            "zh/快速开始指南.md",
            "zh/API使用示例.md",
            "zh/故障排除指南.md"
        ]
        
        for expected_file in expected_docs_structure:
            file_path = self.docs_path / expected_file
            if not file_path.exists():
                issues.append(ComplianceIssue(
                    rule="documentation_location",
                    description=f"Missing expected documentation file: {expected_file}",
                    file_path=expected_file,
                    severity=ComplianceLevel.MEDIUM,
                    fix_suggestion=f"Create {expected_file} as per documentation standards"
                ))
        
        # Check 4: Interactive scripts in docs/scripts/
        expected_scripts = [
            "setup_validator.py",
            "health_check.py",
            "config_helper.py",
            "doc_validator.py"
        ]
        
        scripts_path = self.docs_path / "scripts"
        if not scripts_path.exists():
            issues.append(ComplianceIssue(
                rule="documentation_location",
                description="Missing docs/scripts/ directory",
                file_path="docs/scripts/",
                severity=ComplianceLevel.HIGH,
                fix_suggestion="Create docs/scripts/ directory for interactive tools"
            ))
        else:
            for script in expected_scripts:
                script_path = scripts_path / script
                if not script_path.exists() and script in ["setup_validator.py", "health_check.py"]:
                    # Only critical for essential scripts
                    issues.append(ComplianceIssue(
                        rule="documentation_location",
                        description=f"Missing critical script: {script}",
                        file_path=f"docs/scripts/{script}",
                        severity=ComplianceLevel.HIGH,
                        fix_suggestion=f"Implement {script} for documentation system"
                    ))
        
        # Calculate compliance rate
        total_checks = len(self.claude_requirements) + len(expected_docs_structure) + len(expected_scripts)
        failed_checks = len(issues)
        compliance_rate = max(0, (total_checks - failed_checks) / total_checks * 100)
        
        return IntegrationTestResult(
            test_name="claude_md_compliance",
            success=len([i for i in issues if i.severity == ComplianceLevel.CRITICAL]) == 0,
            issues=issues,
            compliance_rate=compliance_rate,
            details={
                'total_checks': total_checks,
                'failed_checks': failed_checks,
                'critical_issues': len([i for i in issues if i.severity == ComplianceLevel.CRITICAL])
            }
        )
    
    def _check_virtual_environment_compliance(self) -> IntegrationTestResult:
        """Check virtual environment usage compliance"""
        print("🔍 Checking virtual environment compliance...")
        
        issues = []
        
        # Check 1: Virtual environment directory exists
        venv_paths = [
            self.project_root / "venv",
            self.project_root / ".venv",
            self.project_root / "env"
        ]
        
        venv_exists = any(path.exists() for path in venv_paths)
        
        if not venv_exists:
            issues.append(ComplianceIssue(
                rule="virtual_environment",
                description="No virtual environment directory found",
                file_path=None,
                severity=ComplianceLevel.CRITICAL,
                fix_suggestion="Create virtual environment: python -m venv venv"
            ))
        
        # Check 2: Documentation scripts use venv activation
        scripts_path = self.docs_path / "scripts"
        if scripts_path.exists():
            for script_file in scripts_path.glob("*.py"):
                try:
                    with open(script_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check if script mentions virtual environment activation
                    if "activate" in content.lower() or "virtual" in content.lower():
                        # Good - script addresses virtual environment
                        continue
                    else:
                        # Script doesn't mention virtual environment usage
                        issues.append(ComplianceIssue(
                            rule="virtual_environment",
                            description=f"Script {script_file.name} doesn't emphasize virtual environment usage",
                            file_path=str(script_file.relative_to(self.project_root)),
                            severity=ComplianceLevel.MEDIUM,
                            fix_suggestion="Add virtual environment check/reminder to script"
                        ))
                except Exception:
                    pass
        
        # Check 3: Documentation mentions virtual environment requirement
        docs_files = list(self.docs_path.rglob("*.md"))
        venv_mentioned = False
        
        for doc_file in docs_files:
            try:
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if re.search(r'(venv|virtual.?environment|activate)', content, re.IGNORECASE):
                    venv_mentioned = True
                    break
            except Exception:
                pass
        
        if not venv_mentioned:
            issues.append(ComplianceIssue(
                rule="virtual_environment",
                description="Documentation doesn't emphasize virtual environment requirement",
                file_path="docs/",
                severity=ComplianceLevel.HIGH,
                fix_suggestion="Add clear virtual environment instructions to documentation"
            ))
        
        # Calculate compliance rate
        total_checks = 3
        failed_checks = len(issues)
        compliance_rate = max(0, (total_checks - failed_checks) / total_checks * 100)
        
        return IntegrationTestResult(
            test_name="virtual_environment_compliance",
            success=len([i for i in issues if i.severity == ComplianceLevel.CRITICAL]) == 0,
            issues=issues,
            compliance_rate=compliance_rate,
            details={
                'venv_exists': venv_exists,
                'venv_mentioned_in_docs': venv_mentioned,
                'scripts_checked': len(list(scripts_path.glob("*.py"))) if scripts_path.exists() else 0
            }
        )
    
    def _check_project_file_integrity(self) -> IntegrationTestResult:
        """Check project file integrity and no conflicts"""
        print("🔍 Checking project file integrity...")
        
        issues = []
        
        # Check 1: Essential project files exist
        essential_files = [
            "main.py",
            "config.py",
            "requirements.txt",
            "app/__init__.py",
            "tests/__init__.py"
        ]
        
        for file_path in essential_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                issues.append(ComplianceIssue(
                    rule="project_structure",
                    description=f"Missing essential project file: {file_path}",
                    file_path=file_path,
                    severity=ComplianceLevel.HIGH,
                    fix_suggestion=f"Create {file_path} as part of project structure"
                ))
        
        # Check 2: No conflicts with existing files
        docs_files = list(self.docs_path.rglob("*"))
        project_files = list(self.project_root.glob("*"))
        
        # Check for naming conflicts (excluding docs folder itself)
        project_names = {f.name for f in project_files if f.name != "docs"}
        
        for docs_file in docs_files:
            if docs_file.is_file() and docs_file.name in project_names:
                # Check if it's a legitimate conflict
                project_equivalent = self.project_root / docs_file.name
                if project_equivalent.exists() and project_equivalent != docs_file:
                    issues.append(ComplianceIssue(
                        rule="project_structure",
                        description=f"Naming conflict: {docs_file.name} exists in both docs/ and root",
                        file_path=str(docs_file.relative_to(self.project_root)),
                        severity=ComplianceLevel.MEDIUM,
                        fix_suggestion=f"Rename or reorganize conflicting file: {docs_file.name}"
                    ))
        
        # Check 3: Configuration file compatibility
        config_files = [
            ".env",
            ".env.example",
            "config.py",
            "requirements.txt"
        ]
        
        for config_file in config_files:
            file_path = self.project_root / config_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Basic validation that file is not corrupted
                    if len(content.strip()) == 0:
                        issues.append(ComplianceIssue(
                            rule="project_structure",
                            description=f"Configuration file is empty: {config_file}",
                            file_path=config_file,
                            severity=ComplianceLevel.MEDIUM,
                            fix_suggestion=f"Add proper configuration to {config_file}"
                        ))
                
                except Exception as e:
                    issues.append(ComplianceIssue(
                        rule="project_structure",
                        description=f"Cannot read configuration file {config_file}: {str(e)}",
                        file_path=config_file,
                        severity=ComplianceLevel.HIGH,
                        fix_suggestion=f"Fix file encoding or permissions for {config_file}"
                    ))
        
        # Check 4: Git integration
        git_dir = self.project_root / ".git"
        gitignore = self.project_root / ".gitignore"
        
        if git_dir.exists():
            # Check if .gitignore includes appropriate entries
            if gitignore.exists():
                try:
                    with open(gitignore, 'r', encoding='utf-8') as f:
                        gitignore_content = f.read()
                    
                    expected_ignores = ["venv/", "__pycache__/", "*.pyc", ".env", "logs/"]
                    missing_ignores = [entry for entry in expected_ignores if entry not in gitignore_content]
                    
                    if missing_ignores:
                        issues.append(ComplianceIssue(
                            rule="project_structure",
                            description=f"Missing .gitignore entries: {', '.join(missing_ignores)}",
                            file_path=".gitignore",
                            severity=ComplianceLevel.LOW,
                            fix_suggestion=f"Add to .gitignore: {', '.join(missing_ignores)}"
                        ))
                
                except Exception:
                    pass
        
        # Calculate compliance rate
        total_checks = len(essential_files) + len(config_files) + 3  # Additional checks
        failed_checks = len(issues)
        compliance_rate = max(0, (total_checks - failed_checks) / total_checks * 100)
        
        return IntegrationTestResult(
            test_name="project_file_integrity",
            success=len([i for i in issues if i.severity in [ComplianceLevel.CRITICAL, ComplianceLevel.HIGH]]) == 0,
            issues=issues,
            compliance_rate=compliance_rate,
            details={
                'essential_files_exist': len(essential_files) - len([i for i in issues if "Missing essential" in i.description]),
                'total_essential_files': len(essential_files),
                'git_integration': git_dir.exists()
            }
        )
    
    def _check_documentation_quality_standards(self) -> IntegrationTestResult:
        """Check documentation meets quality standards"""
        print("🔍 Checking documentation quality standards...")
        
        issues = []
        
        # Check 1: Bilingual documentation completeness
        english_docs = list((self.docs_path / "en").glob("*.md")) if (self.docs_path / "en").exists() else []
        chinese_docs = list((self.docs_path / "zh").glob("*.md")) if (self.docs_path / "zh").exists() else []
        
        if len(english_docs) == 0:
            issues.append(ComplianceIssue(
                rule="documentation_quality",
                description="No English documentation found",
                file_path="docs/en/",
                severity=ComplianceLevel.CRITICAL,
                fix_suggestion="Create English documentation files"
            ))
        
        if len(chinese_docs) == 0:
            issues.append(ComplianceIssue(
                rule="documentation_quality",
                description="No Chinese documentation found",
                file_path="docs/zh/",
                severity=ComplianceLevel.HIGH,
                fix_suggestion="Create Chinese documentation files for bilingual support"
            ))
        
        # Check 2: Documentation file naming consistency
        expected_file_pairs = [
            ("quickstart.md", "快速开始指南.md"),
            ("api-examples.md", "API使用示例.md"),
            ("troubleshooting.md", "故障排除指南.md")
        ]
        
        for en_file, zh_file in expected_file_pairs:
            en_path = self.docs_path / "en" / en_file
            zh_path = self.docs_path / "zh" / zh_file
            
            if en_path.exists() and not zh_path.exists():
                issues.append(ComplianceIssue(
                    rule="documentation_quality",
                    description=f"Missing Chinese equivalent for {en_file}",
                    file_path=f"docs/zh/{zh_file}",
                    severity=ComplianceLevel.MEDIUM,
                    fix_suggestion=f"Create Chinese version: {zh_file}"
                ))
            elif zh_path.exists() and not en_path.exists():
                issues.append(ComplianceIssue(
                    rule="documentation_quality",
                    description=f"Missing English equivalent for {zh_file}",
                    file_path=f"docs/en/{en_file}",
                    severity=ComplianceLevel.MEDIUM,
                    fix_suggestion=f"Create English version: {en_file}"
                ))
        
        # Check 3: Interactive tools directory structure
        scripts_path = self.docs_path / "scripts"
        if scripts_path.exists():
            script_files = list(scripts_path.glob("*.py"))
            if len(script_files) < 2:  # Should have at least setup_validator and health_check
                issues.append(ComplianceIssue(
                    rule="documentation_quality",
                    description="Insufficient interactive tools (should have setup_validator and health_check)",
                    file_path="docs/scripts/",
                    severity=ComplianceLevel.HIGH,
                    fix_suggestion="Implement setup_validator.py and health_check.py"
                ))
        
        # Check 4: Main README.md quality
        main_readme = self.docs_path / "README.md"
        if main_readme.exists():
            try:
                with open(main_readme, 'r', encoding='utf-8') as f:
                    readme_content = f.read()
                
                # Check for essential sections
                essential_sections = [
                    "Quick Links",
                    "Interactive Tools", 
                    "Features Overview",
                    "中文"  # Chinese language support indicator
                ]
                
                missing_sections = [section for section in essential_sections if section not in readme_content]
                
                if missing_sections:
                    issues.append(ComplianceIssue(
                        rule="documentation_quality",
                        description=f"Missing essential README sections: {', '.join(missing_sections)}",
                        file_path="docs/README.md",
                        severity=ComplianceLevel.MEDIUM,
                        fix_suggestion=f"Add sections: {', '.join(missing_sections)}"
                    ))
                
                # Check README length (should be comprehensive)
                if len(readme_content.split('\n')) < 50:
                    issues.append(ComplianceIssue(
                        rule="documentation_quality",
                        description="README.md appears too brief for comprehensive documentation",
                        file_path="docs/README.md",
                        severity=ComplianceLevel.LOW,
                        fix_suggestion="Expand README with more detailed information"
                    ))
                
            except Exception:
                issues.append(ComplianceIssue(
                    rule="documentation_quality",
                    description="Cannot read main README.md",
                    file_path="docs/README.md",
                    severity=ComplianceLevel.HIGH,
                    fix_suggestion="Fix README.md file encoding or permissions"
                ))
        
        # Calculate compliance rate
        total_checks = 4 + len(expected_file_pairs) * 2  # Each pair checked both ways
        failed_checks = len(issues)
        compliance_rate = max(0, (total_checks - failed_checks) / total_checks * 100)
        
        return IntegrationTestResult(
            test_name="documentation_quality_standards",
            success=len([i for i in issues if i.severity == ComplianceLevel.CRITICAL]) == 0,
            issues=issues,
            compliance_rate=compliance_rate,
            details={
                'english_docs_count': len(english_docs),
                'chinese_docs_count': len(chinese_docs),
                'bilingual_support': len(english_docs) > 0 and len(chinese_docs) > 0,
                'interactive_scripts_count': len(list(scripts_path.glob("*.py"))) if scripts_path.exists() else 0
            }
        )
    
    def _check_development_workflow_compliance(self) -> IntegrationTestResult:
        """Check development workflow compliance"""
        print("🔍 Checking development workflow compliance...")
        
        issues = []
        
        # Check 1: Testing infrastructure
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            test_files = list(tests_dir.glob("test_*.py"))
            if len(test_files) == 0:
                issues.append(ComplianceIssue(
                    rule="development_workflow",
                    description="No test files found in tests/ directory",
                    file_path="tests/",
                    severity=ComplianceLevel.MEDIUM,
                    fix_suggestion="Add test files following test_*.py naming convention"
                ))
        else:
            issues.append(ComplianceIssue(
                rule="development_workflow",
                description="No tests/ directory found",
                file_path="tests/",
                severity=ComplianceLevel.HIGH,
                fix_suggestion="Create tests/ directory and add test files"
            ))
        
        # Check 2: Requirements file completeness
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            try:
                with open(requirements_file, 'r') as f:
                    requirements_content = f.read()
                
                # Check for essential dependencies
                essential_deps = ["fastapi", "uvicorn", "pydantic", "python-dotenv"]
                missing_deps = [dep for dep in essential_deps if dep not in requirements_content.lower()]
                
                if missing_deps:
                    issues.append(ComplianceIssue(
                        rule="development_workflow",
                        description=f"Missing essential dependencies: {', '.join(missing_deps)}",
                        file_path="requirements.txt",
                        severity=ComplianceLevel.MEDIUM,
                        fix_suggestion=f"Add to requirements.txt: {', '.join(missing_deps)}"
                    ))
                
            except Exception:
                issues.append(ComplianceIssue(
                    rule="development_workflow",
                    description="Cannot read requirements.txt",
                    file_path="requirements.txt", 
                    severity=ComplianceLevel.HIGH,
                    fix_suggestion="Fix requirements.txt file"
                ))
        
        # Check 3: Environment configuration
        env_example = self.project_root / ".env.example"
        env_file = self.project_root / ".env"
        
        if not env_example.exists() and not env_file.exists():
            issues.append(ComplianceIssue(
                rule="development_workflow",
                description="No environment configuration template found",
                file_path=".env.example",
                severity=ComplianceLevel.MEDIUM,
                fix_suggestion="Create .env.example with required environment variables"
            ))
        
        # Check 4: Code organization
        app_dir = self.project_root / "app"
        if app_dir.exists():
            app_files = list(app_dir.glob("*.py"))
            if len(app_files) == 0:
                issues.append(ComplianceIssue(
                    rule="development_workflow",
                    description="Empty app/ directory",
                    file_path="app/",
                    severity=ComplianceLevel.MEDIUM,
                    fix_suggestion="Add application code files to app/ directory"
                ))
        
        # Calculate compliance rate
        total_checks = 6  # Number of compliance checks
        failed_checks = len(issues)
        compliance_rate = max(0, (total_checks - failed_checks) / total_checks * 100)
        
        return IntegrationTestResult(
            test_name="development_workflow_compliance",
            success=len([i for i in issues if i.severity in [ComplianceLevel.CRITICAL, ComplianceLevel.HIGH]]) == 0,
            issues=issues,
            compliance_rate=compliance_rate,
            details={
                'tests_directory_exists': tests_dir.exists(),
                'requirements_file_exists': requirements_file.exists(),
                'env_config_exists': env_example.exists() or env_file.exists(),
                'app_directory_exists': app_dir.exists()
            }
        )
    
    def run_comprehensive_integration_tests(self) -> Dict[str, Any]:
        """Run comprehensive integration and compliance tests"""
        print("🚀 Starting Integration Testing Suite")
        print("Testing project structure compliance and CLAUDE.md requirements")
        
        # Run all integration tests
        test_functions = [
            self._check_claude_md_compliance,
            self._check_virtual_environment_compliance,
            self._check_project_file_integrity,
            self._check_documentation_quality_standards,
            self._check_development_workflow_compliance
        ]
        
        all_results = []
        
        for test_func in test_functions:
            print(f"\n{'='*60}")
            try:
                result = test_func()
                all_results.append(result)
                self.results.append(result)
                
                if result.success:
                    print(f"✅ {result.test_name}: PASSED ({result.compliance_rate:.1f}% compliance)")
                else:
                    critical_issues = len([i for i in result.issues if i.severity == ComplianceLevel.CRITICAL])
                    high_issues = len([i for i in result.issues if i.severity == ComplianceLevel.HIGH])
                    print(f"❌ {result.test_name}: FAILED ({critical_issues} critical, {high_issues} high priority issues)")
                
            except Exception as e:
                print(f"💥 {test_func.__name__}: ERROR - {str(e)}")
                error_result = IntegrationTestResult(
                    test_name=test_func.__name__,
                    success=False,
                    issues=[ComplianceIssue(
                        rule="test_execution",
                        description=f"Test execution failed: {str(e)}",
                        file_path=None,
                        severity=ComplianceLevel.CRITICAL,
                        fix_suggestion="Fix test execution environment"
                    )],
                    compliance_rate=0.0,
                    details={'error': str(e)}
                )
                all_results.append(error_result)
                self.results.append(error_result)
        
        # Calculate overall metrics
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results if r.success)
        overall_success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Overall compliance rate (weighted by importance)
        test_weights = {
            'claude_md_compliance': 0.3,
            'virtual_environment_compliance': 0.25,
            'project_file_integrity': 0.2,
            'documentation_quality_standards': 0.15,
            'development_workflow_compliance': 0.1
        }
        
        weighted_compliance = 0
        total_weight = 0
        
        for result in all_results:
            weight = test_weights.get(result.test_name, 0.1)
            weighted_compliance += result.compliance_rate * weight
            total_weight += weight
        
        overall_compliance_rate = weighted_compliance / total_weight if total_weight > 0 else 0
        
        # Aggregate all issues
        all_issues = []
        for result in all_results:
            all_issues.extend(result.issues)
        
        critical_issues = [i for i in all_issues if i.severity == ComplianceLevel.CRITICAL]
        high_issues = [i for i in all_issues if i.severity == ComplianceLevel.HIGH]
        
        # Integration success criteria
        integration_success = len(critical_issues) == 0 and overall_compliance_rate >= 85
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'overall_success_rate': overall_success_rate,
            'overall_compliance_rate': overall_compliance_rate,
            'integration_success': integration_success,
            'total_issues': len(all_issues),
            'critical_issues': len(critical_issues),
            'high_issues': len(high_issues),
            'medium_issues': len([i for i in all_issues if i.severity == ComplianceLevel.MEDIUM]),
            'low_issues': len([i for i in all_issues if i.severity == ComplianceLevel.LOW]),
            'claude_md_compliant': len([i for i in critical_issues if "claude" in i.rule.lower()]) == 0,
            'detailed_results': all_results
        }
    
    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """Generate comprehensive integration test report"""
        report = f"""
# Integration Testing Report - Project Structure & CLAUDE.md Compliance

## Executive Summary
- **Total Integration Tests**: {metrics['total_tests']}
- **Passed Tests**: {metrics['passed_tests']}
- **Failed Tests**: {metrics['failed_tests']}
- **Overall Success Rate**: {metrics['overall_success_rate']:.1f}%
- **Overall Compliance Rate**: {metrics['overall_compliance_rate']:.1f}%
- **Integration Success**: {'✅ YES' if metrics['integration_success'] else '❌ NO'}
- **CLAUDE.md Compliant**: {'✅ YES' if metrics['claude_md_compliant'] else '❌ NO'}

## Issue Summary
- **Total Issues**: {metrics['total_issues']}
- **Critical Issues**: {metrics['critical_issues']} 🔴
- **High Priority Issues**: {metrics['high_issues']} 🟠  
- **Medium Priority Issues**: {metrics['medium_issues']} 🟡
- **Low Priority Issues**: {metrics['low_issues']} 🔵

## Compliance Status
"""
        
        if metrics['integration_success']:
            report += "🎉 **EXCELLENT INTEGRATION** - All critical requirements met!\n"
        elif metrics['critical_issues'] == 0:
            report += "✅ **GOOD INTEGRATION** - No critical issues, some improvements needed.\n"
        else:
            report += "⚠️ **INTEGRATION ISSUES** - Critical compliance problems must be resolved.\n"
        
        # Test-by-test results
        report += "\n## Test Results\n"
        
        for result in metrics['detailed_results']:
            status = "✅ PASS" if result.success else "❌ FAIL"
            report += f"\n### {result.test_name.replace('_', ' ').title()} {status}\n"
            report += f"- **Compliance Rate**: {result.compliance_rate:.1f}%\n"
            report += f"- **Issues Found**: {len(result.issues)}\n"
            
            if result.issues:
                # Group issues by severity
                critical = [i for i in result.issues if i.severity == ComplianceLevel.CRITICAL]
                high = [i for i in result.issues if i.severity == ComplianceLevel.HIGH]
                medium = [i for i in result.issues if i.severity == ComplianceLevel.MEDIUM]
                
                if critical:
                    report += f"- **Critical Issues**: {len(critical)}\n"
                    for issue in critical[:2]:  # Show top 2
                        report += f"  - 🔴 {issue.description}\n"
                        report += f"    *Fix: {issue.fix_suggestion}*\n"
                
                if high:
                    report += f"- **High Priority Issues**: {len(high)}\n"
                    for issue in high[:2]:  # Show top 2
                        report += f"  - 🟠 {issue.description}\n"
                        report += f"    *Fix: {issue.fix_suggestion}*\n"
                
                if medium and not critical and not high:
                    report += f"- **Medium Priority Issues**: {len(medium)}\n"
                    for issue in medium[:2]:  # Show top 2
                        report += f"  - 🟡 {issue.description}\n"
        
        # CLAUDE.md specific compliance
        report += "\n## CLAUDE.md Compliance Analysis\n"
        
        claude_issues = []
        for result in metrics['detailed_results']:
            if 'claude' in result.test_name:
                claude_issues.extend(result.issues)
        
        if not claude_issues:
            report += "✅ **Perfect CLAUDE.md Compliance** - All requirements met!\n"
        else:
            report += f"⚠️ **CLAUDE.md Issues Found** ({len(claude_issues)} total)\n"
            
            claude_critical = [i for i in claude_issues if i.severity == ComplianceLevel.CRITICAL]
            if claude_critical:
                report += "\n**Critical CLAUDE.md Violations:**\n"
                for issue in claude_critical:
                    report += f"- 🔴 {issue.description}\n"
                    report += f"  *Fix: {issue.fix_suggestion}*\n"
        
        # Integration recommendations
        report += "\n## Integration Recommendations\n"
        
        if metrics['critical_issues'] > 0:
            report += "\n### 🔴 Critical Priority (Must Fix Immediately)\n"
            critical_issues = []
            for result in metrics['detailed_results']:
                critical_issues.extend([i for i in result.issues if i.severity == ComplianceLevel.CRITICAL])
            
            for issue in critical_issues[:3]:  # Top 3 critical issues
                report += f"- **{issue.rule.replace('_', ' ').title()}**: {issue.description}\n"
                report += f"  *Solution: {issue.fix_suggestion}*\n"
        
        if metrics['high_issues'] > 0:
            report += "\n### 🟠 High Priority (Should Fix Soon)\n"
            high_issues = []
            for result in metrics['detailed_results']:
                high_issues.extend([i for i in result.issues if i.severity == ComplianceLevel.HIGH])
            
            for issue in high_issues[:3]:  # Top 3 high issues
                report += f"- **{issue.rule.replace('_', ' ').title()}**: {issue.description}\n"
                report += f"  *Solution: {issue.fix_suggestion}*\n"
        
        # Best practices
        report += f"""
### Integration Best Practices

#### CLAUDE.md Compliance
- ✅ All documentation MUST be in docs/ folder (never in root)
- ✅ ALWAYS use virtual environments for Python operations
- ✅ Use docs/README.md instead of root README.md
- ✅ Interactive scripts should emphasize virtual environment usage

#### Project Structure
- Maintain clear separation between documentation and code
- Ensure configuration files are properly formatted
- Keep consistent naming conventions across languages
- Implement comprehensive testing infrastructure

#### Documentation Quality
- Provide complete bilingual support (English + Chinese)
- Include interactive tools for user assistance
- Maintain professional README with clear navigation
- Ensure accessibility compliance

#### Development Workflow
- Use proper dependency management
- Implement comprehensive testing
- Maintain environment configuration templates
- Follow consistent code organization patterns

---

**Integration Test Version**: 1.0.0  
**CLAUDE.md Version**: Current  
**Test Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Compliance Target**: >85% overall compliance rate
"""
        
        return report


def main():
    """Main test execution"""
    tester = ProjectStructureIntegrationTester()
    
    # Run comprehensive integration tests
    metrics = tester.run_comprehensive_integration_tests()
    
    # Generate and display report
    report = tester.generate_report(metrics)
    print("\n" + "="*80)
    print(report)
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"integration_test_results_{timestamp}.json"
    
    # Prepare serializable data
    serializable_results = []
    for result in tester.results:
        serializable_issues = []
        for issue in result.issues:
            serializable_issues.append({
                'rule': issue.rule,
                'description': issue.description,
                'file_path': issue.file_path,
                'severity': issue.severity.value,
                'fix_suggestion': issue.fix_suggestion,
                'line_number': issue.line_number
            })
        
        serializable_results.append({
            'test_name': result.test_name,
            'success': result.success,
            'compliance_rate': result.compliance_rate,
            'issues': serializable_issues,
            'details': result.details
        })
    
    save_data = {
        'metrics': metrics,
        'detailed_results': serializable_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Return success if integration criteria are met
    return metrics['integration_success']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)