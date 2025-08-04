#!/usr/bin/env python3
"""
Documentation Validation Script for Opitios Alpaca Trading Service

This script provides automated validation and quality assurance for documentation,
ensuring consistency, accuracy, and completeness across all documentation files.

Usage:
    python docs/scripts/doc_validator.py

Features:
- Link validation (internal and external)
- Content consistency checking
- Translation validation between English and Chinese
- Markdown format validation
- Cross-reference verification
- Documentation structure validation
- Badge validation
- Code example testing
"""

import os
import re
import sys
import json
import requests
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from urllib.parse import urljoin, urlparse
import concurrent.futures
import time

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
    END = '\033[0m'

class DocumentationValidator:
    def __init__(self):
        self.project_root = Path.cwd()
        self.docs_root = self.project_root / "docs"
        self.results = {
            'total_files': 0,
            'checked_files': 0,
            'errors': [],
            'warnings': [],
            'info': [],
            'external_links': set(),
            'internal_links': set(),
            'broken_links': [],
            'missing_translations': [],
            'inconsistencies': []
        }
        
    def print_header(self, title: str):
        """Print formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{title.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")

    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")
        self.results['warnings'].append(message)

    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.END}")
        self.results['errors'].append(message)

    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")
        self.results['info'].append(message)

    def find_markdown_files(self) -> List[Path]:
        """Find all markdown files in the project"""
        markdown_files = []
        
        # Root level markdown files
        for pattern in ['*.md']:
            markdown_files.extend(self.project_root.glob(pattern))
        
        # Documentation folder markdown files
        if self.docs_root.exists():
            for pattern in ['**/*.md']:
                markdown_files.extend(self.docs_root.glob(pattern))
        
        self.results['total_files'] = len(markdown_files)
        return markdown_files

    def extract_links_from_markdown(self, content: str) -> Tuple[List[str], List[str]]:
        """Extract internal and external links from markdown content"""
        # Regex patterns for different link types
        markdown_link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
        reference_link_pattern = r'\[([^\]]*)\]:\s*([^\s]+)'
        html_link_pattern = r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>'
        
        internal_links = []
        external_links = []
        
        # Find all link patterns
        all_patterns = [markdown_link_pattern, reference_link_pattern, html_link_pattern]
        
        for pattern in all_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    url = match[1] if len(match) > 1 else match[0]
                else:
                    url = match
                
                # Skip empty links and anchors
                if not url or url.startswith('#'):
                    continue
                
                # Classify as internal or external
                if url.startswith(('http://', 'https://')):
                    external_links.append(url)
                else:
                    internal_links.append(url)
        
        return internal_links, external_links

    def validate_internal_links(self, file_path: Path, internal_links: List[str]) -> List[str]:
        """Validate internal links exist"""
        broken_links = []
        
        for link in internal_links:
            # Handle relative links
            if link.startswith('./') or link.startswith('../'):
                target_path = (file_path.parent / link).resolve()
            else:
                # Try multiple possible locations
                possible_paths = [
                    self.project_root / link,
                    self.docs_root / link,
                    file_path.parent / link
                ]
                target_path = None
                for path in possible_paths:
                    if path.exists():
                        target_path = path
                        break
            
            # Check if target exists
            if target_path is None or not target_path.exists():
                broken_links.append(f"{file_path.name}: {link}")
        
        return broken_links

    def validate_external_links(self, external_links: List[str]) -> List[str]:
        """Validate external links are accessible"""
        broken_links = []
        
        def check_link(url: str) -> Optional[str]:
            try:
                # Skip certain URLs that commonly block automated requests
                skip_domains = ['github.com', 'shields.io', 'app.alpaca.markets']
                if any(domain in url for domain in skip_domains):
                    return None
                
                response = requests.head(url, timeout=10, allow_redirects=True)
                if response.status_code >= 400:
                    return f"HTTP {response.status_code}: {url}"
            except requests.exceptions.RequestException as e:
                return f"Connection error: {url} ({str(e)})"
            except Exception as e:
                return f"Error: {url} ({str(e)})"
            
            return None
        
        # Check links concurrently for better performance
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(check_link, url): url for url in external_links}
            
            for future in concurrent.futures.as_completed(future_to_url):
                result = future.result()
                if result:
                    broken_links.append(result)
        
        return broken_links

    def validate_markdown_syntax(self, file_path: Path, content: str) -> List[str]:
        """Validate markdown syntax and structure"""
        issues = []
        lines = content.split('\n')
        
        # Check for common markdown issues
        for i, line in enumerate(lines, 1):
            # Check for malformed headers
            if line.startswith('#'):
                if not re.match(r'^#{1,6}\s+.+', line):
                    issues.append(f"{file_path.name}:{i}: Malformed header - missing space after #")
            
            # Check for malformed links
            if '[' in line and ']' in line:
                # Look for malformed markdown links
                malformed_links = re.findall(r'\[[^\]]*\]\([^)]*$', line)
                if malformed_links:
                    issues.append(f"{file_path.name}:{i}: Unclosed link")
            
            # Check for inconsistent list formatting
            if re.match(r'^[\s]*[-*+]\s*$', line):
                issues.append(f"{file_path.name}:{i}: Empty list item")
        
        # Check for missing title (H1)
        if not re.search(r'^#\s+.+', content, re.MULTILINE):
            issues.append(f"{file_path.name}: Missing main title (H1)")
        
        return issues

    def validate_code_blocks(self, file_path: Path, content: str) -> List[str]:
        """Validate code blocks and examples"""
        issues = []
        
        # Find all code blocks
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', content, re.DOTALL)
        
        for i, (language, code) in enumerate(code_blocks):
            if not language:
                issues.append(f"{file_path.name}: Code block {i+1} missing language specification")
            
            # Check for common issues in bash/shell code
            if language in ['bash', 'shell', 'sh']:
                if 'curl' in code and not any(word in code for word in ['localhost', '127.0.0.1', 'example.com']):
                    # This might be a real API call in documentation
                    issues.append(f"{file_path.name}: Code block {i+1} contains potential real API calls")
        
        return issues

    def validate_badges(self, content: str) -> List[str]:
        """Validate README badges"""
        issues = []
        
        # Find all badge URLs
        badge_pattern = r'!\[([^\]]*)\]\((https://img\.shields\.io/[^)]+)\)'
        badges = re.findall(badge_pattern, content)
        
        for alt_text, badge_url in badges:
            # Check if badge URL is well-formed
            if not re.match(r'https://img\.shields\.io/badge/.+', badge_url):
                issues.append(f"Malformed badge URL: {badge_url}")
            
            # Check if alt text is meaningful
            if not alt_text or len(alt_text) < 3:
                issues.append(f"Badge missing meaningful alt text: {badge_url}")
        
        return issues

    def check_translation_consistency(self) -> List[str]:
        """Check consistency between English and Chinese translations"""
        issues = []
        
        # Map of English to Chinese file pairs
        translation_pairs = [
            ('docs/en/quickstart.md', 'docs/zh/快速开始指南.md'),
            ('docs/en/api-examples.md', 'docs/zh/API使用示例.md'),
            ('docs/en/troubleshooting.md', 'docs/zh/故障排除指南.md'),
            ('docs/en/setup-validation.md', 'docs/zh/安装验证.md'),
            ('README.md', 'README.zh.md')
        ]
        
        for en_file, zh_file in translation_pairs:
            en_path = self.project_root / en_file
            zh_path = self.project_root / zh_file
            
            if en_path.exists() and not zh_path.exists():
                issues.append(f"Missing Chinese translation: {zh_file}")
            elif zh_path.exists() and not en_path.exists():
                issues.append(f"Missing English original: {en_file}")
            elif en_path.exists() and zh_path.exists():
                # Check if both files have similar structure
                try:
                    en_content = en_path.read_text(encoding='utf-8')
                    zh_content = zh_path.read_text(encoding='utf-8')
                    
                    # Count headers in both files
                    en_headers = len(re.findall(r'^#+\s', en_content, re.MULTILINE))
                    zh_headers = len(re.findall(r'^#+\s', zh_content, re.MULTILINE))
                    
                    if abs(en_headers - zh_headers) > 2:  # Allow some flexibility
                        issues.append(f"Header count mismatch between {en_file} ({en_headers}) and {zh_file} ({zh_headers})")
                
                except Exception as e:
                    issues.append(f"Error comparing {en_file} and {zh_file}: {str(e)}")
        
        return issues

    def validate_project_structure(self) -> List[str]:
        """Validate documentation project structure"""
        issues = []
        
        # Required files
        required_files = [
            'README.md',
            'docs/README.md',
            'docs/en/quickstart.md',
            'docs/en/api-examples.md',
            'docs/en/troubleshooting.md',
            'docs/zh/快速开始指南.md',
            'docs/zh/API使用示例.md',
            'docs/zh/故障排除指南.md'
        ]
        
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                issues.append(f"Missing required file: {file_path}")
        
        # Required directories
        required_dirs = [
            'docs',
            'docs/en',
            'docs/zh',
            'docs/scripts'
        ]
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                issues.append(f"Missing required directory: {dir_path}")
        
        return issues

    def generate_report(self) -> Dict:
        """Generate comprehensive validation report"""
        total_issues = len(self.results['errors']) + len(self.results['warnings'])
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_files_checked': self.results['checked_files'],
                'total_issues': total_issues,
                'errors': len(self.results['errors']),
                'warnings': len(self.results['warnings']),
                'info_items': len(self.results['info'])
            },
            'results': self.results,
            'score': max(0, 100 - (len(self.results['errors']) * 10) - (len(self.results['warnings']) * 2))
        }
        
        return report

    def run_validation(self) -> bool:
        """Run complete documentation validation"""
        self.print_header("Documentation Validation")
        print(f"{Colors.WHITE}Comprehensive validation of documentation quality and consistency{Colors.END}")
        
        # Step 1: Project Structure Validation
        print(f"\n{Colors.CYAN}[1/8] Validating project structure...{Colors.END}")
        structure_issues = self.validate_project_structure()
        if structure_issues:
            for issue in structure_issues:
                self.print_error(issue)
        else:
            self.print_success("Project structure is correct")
        
        # Step 2: Find and validate markdown files
        print(f"\n{Colors.CYAN}[2/8] Finding markdown files...{Colors.END}")
        markdown_files = self.find_markdown_files()
        self.print_info(f"Found {len(markdown_files)} markdown files")
        
        # Step 3: Validate individual files
        print(f"\n{Colors.CYAN}[3/8] Validating individual files...{Colors.END}")
        all_internal_links = []
        all_external_links = []
        
        for file_path in markdown_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                self.results['checked_files'] += 1
                
                # Validate markdown syntax
                syntax_issues = self.validate_markdown_syntax(file_path, content)
                for issue in syntax_issues:
                    self.print_warning(issue)
                
                # Validate code blocks
                code_issues = self.validate_code_blocks(file_path, content)
                for issue in code_issues:
                    self.print_warning(issue)
                
                # Extract links
                internal_links, external_links = self.extract_links_from_markdown(content)
                all_internal_links.extend([(file_path, link) for link in internal_links])
                all_external_links.extend(external_links)
                
                # Validate badges (for README files)
                if file_path.name.startswith('README'):
                    badge_issues = self.validate_badges(content)
                    for issue in badge_issues:
                        self.print_warning(f"{file_path.name}: {issue}")
                
                self.print_success(f"Validated {file_path.relative_to(self.project_root)}")
                
            except Exception as e:
                self.print_error(f"Error reading {file_path}: {str(e)}")
        
        # Step 4: Validate internal links
        print(f"\n{Colors.CYAN}[4/8] Validating internal links...{Colors.END}")
        internal_link_issues = []
        for file_path, link in all_internal_links:
            issues = self.validate_internal_links(file_path, [link])
            internal_link_issues.extend(issues)
        
        if internal_link_issues:
            for issue in internal_link_issues:
                self.print_error(f"Broken internal link: {issue}")
        else:
            self.print_success(f"All {len(all_internal_links)} internal links valid")
        
        # Step 5: Validate external links
        print(f"\n{Colors.CYAN}[5/8] Validating external links...{Colors.END}")
        unique_external_links = list(set(all_external_links))
        if unique_external_links:
            self.print_info(f"Checking {len(unique_external_links)} unique external links...")
            external_link_issues = self.validate_external_links(unique_external_links)
            
            if external_link_issues:
                for issue in external_link_issues:
                    self.print_warning(f"External link issue: {issue}")
            else:
                self.print_success("All external links are accessible")
        else:
            self.print_info("No external links found")
        
        # Step 6: Check translation consistency
        print(f"\n{Colors.CYAN}[6/8] Checking translation consistency...{Colors.END}")
        translation_issues = self.check_translation_consistency()
        if translation_issues:
            for issue in translation_issues:
                self.print_warning(issue)
        else:
            self.print_success("Translation consistency validated")
        
        # Step 7: Cross-reference validation
        print(f"\n{Colors.CYAN}[7/8] Validating cross-references...{Colors.END}")
        # Check if all referenced scripts exist
        script_references = [
            'docs/scripts/setup_validator.py',
            'docs/scripts/health_check.py',
            'docs/scripts/config_helper.py'
        ]
        
        for script_path in script_references:
            full_path = self.project_root / script_path
            if not full_path.exists():
                self.print_error(f"Referenced script not found: {script_path}")
            else:
                self.print_success(f"Script exists: {script_path}")
        
        # Step 8: Generate final report
        print(f"\n{Colors.CYAN}[8/8] Generating validation report...{Colors.END}")
        report = self.generate_report()
        
        # Display summary
        self.print_header("Validation Summary")
        print(f"Files checked: {report['summary']['total_files_checked']}")
        print(f"Total issues: {report['summary']['total_issues']}")
        print(f"Errors: {Colors.RED}{report['summary']['errors']}{Colors.END}")
        print(f"Warnings: {Colors.YELLOW}{report['summary']['warnings']}{Colors.END}")
        print(f"Documentation Score: {Colors.GREEN if report['score'] >= 90 else Colors.YELLOW if report['score'] >= 70 else Colors.RED}{report['score']}/100{Colors.END}")
        
        # Save detailed report
        report_file = self.project_root / f"docs_validation_report_{int(time.time())}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.print_success(f"Detailed report saved: {report_file}")
        except Exception as e:
            self.print_warning(f"Could not save report: {str(e)}")
        
        # Final assessment
        if report['score'] >= 90:
            self.print_success("🎉 Excellent! Documentation quality is high.")
        elif report['score'] >= 70:
            self.print_warning("📋 Good documentation with some areas for improvement.")
        else:
            self.print_error("⚠️  Documentation needs significant improvement.")
        
        return report['summary']['errors'] == 0

def main():
    """Main validation workflow"""
    validator = DocumentationValidator()
    
    try:
        success = validator.run_validation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Validation cancelled by user.{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error during validation: {str(e)}{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()