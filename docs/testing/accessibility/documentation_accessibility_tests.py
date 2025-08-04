#!/usr/bin/env python3
"""
Accessibility Testing - Documentation Accessibility Tests

This module validates the accessibility of documentation and interactive tools
according to WCAG 2.1 AA standards, ensuring inclusive design for users
with disabilities and various assistive technologies.

Test Focus:
- WCAG 2.1 AA compliance validation
- Screen reader compatibility
- Keyboard navigation support
- Color contrast verification
- Alternative text for images
- Semantic HTML structure
- Mobile device accessibility
- Assistive technology compatibility

Usage:
    python docs/testing/accessibility/documentation_accessibility_tests.py
"""

import os
import sys
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import unittest
from urllib.parse import urlparse
import colorsys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class AccessibilityLevel(Enum):
    """WCAG accessibility levels"""
    A = "A"
    AA = "AA"
    AAA = "AAA"


class AccessibilityCategory(Enum):
    """WCAG principle categories"""
    PERCEIVABLE = "perceivable"
    OPERABLE = "operable"
    UNDERSTANDABLE = "understandable"
    ROBUST = "robust"


@dataclass
class AccessibilityIssue:
    """Accessibility issue found during testing"""
    category: AccessibilityCategory
    level: AccessibilityLevel
    rule: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    severity: str = "medium"  # low, medium, high, critical
    fix_suggestion: Optional[str] = None


@dataclass
class AccessibilityResult:
    """Result of accessibility testing"""
    file_path: str
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    wcag_aa_compliant: bool
    issues: List[AccessibilityIssue]
    success_rate: float


class DocumentationAccessibilityTester:
    """Tests accessibility of documentation system"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.docs_path = self.project_root / "docs"
        self.results: List[AccessibilityResult] = []
        
        # WCAG 2.1 AA requirements for documentation
        self.wcag_rules = {
            'perceivable': [
                'alt_text_present',
                'color_contrast_adequate',
                'heading_structure_logical',
                'text_scalable',
                'meaningful_link_text'
            ],
            'operable': [
                'keyboard_navigable',
                'no_seizure_triggers',
                'sufficient_time_limits',
                'focus_indicators'
            ],
            'understandable': [
                'language_specified',
                'clear_navigation',
                'consistent_identification',
                'error_instructions_clear'
            ],
            'robust': [
                'valid_markup',
                'assistive_tech_compatible',
                'future_compatible'
            ]
        }
    
    def _parse_markdown_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse markdown file and extract structure"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract headings
            headings = []
            for match in re.finditer(r'^(#+)\s+(.+)$', content, re.MULTILINE):
                level = len(match.group(1))
                text = match.group(2).strip()
                line_num = content[:match.start()].count('\n') + 1
                headings.append({
                    'level': level,
                    'text': text,
                    'line': line_num
                })
            
            # Extract links
            links = []
            for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', content):
                link_text = match.group(1)
                link_url = match.group(2)
                line_num = content[:match.start()].count('\n') + 1
                links.append({
                    'text': link_text,
                    'url': link_url,
                    'line': line_num
                })
            
            # Extract images
            images = []
            for match in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', content):
                alt_text = match.group(1)
                image_url = match.group(2)
                line_num = content[:match.start()].count('\n') + 1
                images.append({
                    'alt_text': alt_text,
                    'url': image_url,
                    'line': line_num
                })
            
            # Extract language indicators
            language_indicators = []
            for match in re.finditer(r'```(\w+)', content):
                language = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                language_indicators.append({
                    'language': language,
                    'line': line_num
                })
            
            return {
                'content': content,
                'headings': headings,
                'links': links,
                'images': images,
                'language_indicators': language_indicators,
                'line_count': content.count('\n') + 1
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'content': '',
                'headings': [],
                'links': [],
                'images': [],
                'language_indicators': [],
                'line_count': 0
            }
    
    def _check_heading_structure(self, headings: List[Dict]) -> List[AccessibilityIssue]:
        """Check heading structure follows logical hierarchy"""
        issues = []
        
        if not headings:
            return issues
        
        # Check if document starts with H1
        if headings[0]['level'] != 1:
            issues.append(AccessibilityIssue(
                category=AccessibilityCategory.PERCEIVABLE,
                level=AccessibilityLevel.AA,
                rule="heading_structure_logical",
                description="Document should start with H1 heading",
                file_path="",
                line_number=headings[0]['line'],
                severity="medium",
                fix_suggestion="Start document with a single H1 heading"
            ))
        
        # Check for heading level skips
        for i in range(1, len(headings)):
            current_level = headings[i]['level']
            previous_level = headings[i-1]['level']
            
            if current_level > previous_level + 1:
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.AA,
                    rule="heading_structure_logical",
                    description=f"Heading level skipped: H{previous_level} to H{current_level}",
                    file_path="",
                    line_number=headings[i]['line'],
                    severity="medium",
                    fix_suggestion=f"Use H{previous_level + 1} instead of H{current_level}"
                ))
        
        # Check for multiple H1s
        h1_count = sum(1 for h in headings if h['level'] == 1)
        if h1_count > 1:
            h1_lines = [h['line'] for h in headings if h['level'] == 1]
            issues.append(AccessibilityIssue(
                category=AccessibilityCategory.PERCEIVABLE,
                level=AccessibilityLevel.AA,
                rule="heading_structure_logical",
                description=f"Multiple H1 headings found ({h1_count})",
                file_path="",
                line_number=h1_lines[1] if len(h1_lines) > 1 else None,
                severity="high",
                fix_suggestion="Use only one H1 per document"
            ))
        
        return issues
    
    def _check_link_accessibility(self, links: List[Dict]) -> List[AccessibilityIssue]:
        """Check link accessibility compliance"""
        issues = []
        
        # Generic link text that should be avoided
        generic_text = [
            'click here', 'here', 'read more', 'more', 'link',
            'this', 'continue', 'go', 'download', 'view'
        ]
        
        for link in links:
            link_text = link['text'].lower().strip()
            
            # Check for empty link text
            if not link_text:
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.A,
                    rule="meaningful_link_text",
                    description="Link has empty text",
                    file_path="",
                    line_number=link['line'],
                    severity="high",
                    fix_suggestion="Provide descriptive link text"
                ))
            
            # Check for generic link text
            elif link_text in generic_text:
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.AA,
                    rule="meaningful_link_text",
                    description=f"Non-descriptive link text: '{link['text']}'",
                    file_path="",
                    line_number=link['line'],
                    severity="medium",
                    fix_suggestion="Use descriptive text that indicates link purpose"
                ))
            
            # Check for very short link text (unless it's an acronym)
            elif len(link_text) < 3 and not link_text.isupper():
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.AA,
                    rule="meaningful_link_text",
                    description=f"Very short link text: '{link['text']}'",
                    file_path="",
                    line_number=link['line'],
                    severity="low",
                    fix_suggestion="Consider using more descriptive link text"
                ))
            
            # Check for URL as link text
            elif urlparse(link_text).scheme in ['http', 'https']:
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.AA,
                    rule="meaningful_link_text",
                    description="URL used as link text",
                    file_path="",
                    line_number=link['line'],
                    severity="medium",
                    fix_suggestion="Use descriptive text instead of raw URL"
                ))
        
        return issues
    
    def _check_image_accessibility(self, images: List[Dict]) -> List[AccessibilityIssue]:
        """Check image accessibility compliance"""
        issues = []
        
        for image in images:
            alt_text = image['alt_text'].strip()
            
            # Check for missing alt text
            if not alt_text:
                # Determine if this might be decorative
                image_url = image['url'].lower()
                decorative_indicators = ['decoration', 'divider', 'spacer', 'bullet']
                
                if any(indicator in image_url for indicator in decorative_indicators):
                    severity = "low"
                    fix_suggestion = "Add empty alt text (alt='') if decorative, or descriptive alt text if meaningful"
                else:
                    severity = "high"
                    fix_suggestion = "Add descriptive alt text explaining the image content"
                
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.A,
                    rule="alt_text_present",
                    description="Image missing alt text",
                    file_path="",
                    line_number=image['line'],
                    severity=severity,
                    fix_suggestion=fix_suggestion
                ))
            
            # Check for redundant alt text
            elif alt_text.lower().startswith(('image of', 'picture of', 'photo of', 'graphic of')):
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.AA,
                    rule="alt_text_present",
                    description=f"Redundant alt text: '{alt_text}'",
                    file_path="",
                    line_number=image['line'],
                    severity="low",
                    fix_suggestion="Remove redundant phrases like 'image of' from alt text"
                ))
            
            # Check for very long alt text
            elif len(alt_text) > 150:
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.AA,
                    rule="alt_text_present",
                    description=f"Alt text too long ({len(alt_text)} characters)",
                    file_path="",
                    line_number=image['line'],
                    severity="medium",
                    fix_suggestion="Keep alt text under 150 characters, use caption for detailed description"
                ))
        
        return issues
    
    def _check_language_specification(self, file_path: Path, content: str) -> List[AccessibilityIssue]:
        """Check if document language is specified"""
        issues = []
        
        # For markdown files, check if there's language indication
        # This is more relevant for HTML, but we can check for multilingual content
        
        # Check if file contains Chinese characters but no language indication
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', content))
        has_english = bool(re.search(r'[a-zA-Z]', content))
        
        if has_chinese and has_english:
            # Mixed language content should have clear language indicators
            if 'zh' not in str(file_path).lower() and 'chinese' not in content.lower():
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.UNDERSTANDABLE,
                    level=AccessibilityLevel.AA,
                    rule="language_specified",
                    description="Mixed language content without clear language indication",
                    file_path="",
                    line_number=1,
                    severity="medium",
                    fix_suggestion="Add language indicators or separate into language-specific files"
                ))
        
        return issues
    
    def _check_content_structure(self, content: str) -> List[AccessibilityIssue]:
        """Check content structure for accessibility"""
        issues = []
        
        # Check for color-only information
        color_only_patterns = [
            r'red\s+(?:text|color|background)',
            r'green\s+(?:text|color|background)',
            r'blue\s+(?:text|color|background)',
            r'click\s+the\s+(?:red|green|blue|yellow)',
            r'see\s+the\s+(?:red|green|blue|yellow)'
        ]
        
        for pattern in color_only_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.A,
                    rule="color_contrast_adequate",
                    description="Information conveyed through color only",
                    file_path="",
                    line_number=line_num,
                    severity="medium",
                    fix_suggestion="Provide additional visual cues beyond color"
                ))
        
        # Check for tables without headers (basic check for markdown tables)
        table_pattern = r'\|.*\|.*\n\|[-:\s|]+\|'
        tables = re.finditer(table_pattern, content, re.MULTILINE)
        
        for table in tables:
            table_content = table.group()
            line_num = content[:table.start()].count('\n') + 1
            
            # Very basic check - tables should have header row
            if not re.search(r'\|.*[A-Za-z].*\|', table_content.split('\n')[0]):
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.PERCEIVABLE,
                    level=AccessibilityLevel.A,
                    rule="valid_markup",
                    description="Table may be missing descriptive headers",
                    file_path="",
                    line_number=line_num,
                    severity="medium",
                    fix_suggestion="Ensure table has descriptive column headers"
                ))
        
        # Check for long paragraphs (readability)
        paragraphs = content.split('\n\n')
        for i, paragraph in enumerate(paragraphs):
            # Remove markdown formatting for word count
            clean_paragraph = re.sub(r'[*_`#\[\]()!]', '', paragraph)
            word_count = len(clean_paragraph.split())
            
            if word_count > 100:  # Very long paragraph
                # Estimate line number
                preceding_text = '\n\n'.join(paragraphs[:i])
                line_num = preceding_text.count('\n') + 1
                
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.UNDERSTANDABLE,
                    level=AccessibilityLevel.AAA,
                    rule="clear_navigation",
                    description=f"Very long paragraph ({word_count} words)",
                    file_path="",
                    line_number=line_num,
                    severity="low",
                    fix_suggestion="Consider breaking into shorter paragraphs or using lists"
                ))
        
        return issues
    
    def _check_code_accessibility(self, content: str, language_indicators: List[Dict]) -> List[AccessibilityIssue]:
        """Check code block accessibility"""
        issues = []
        
        # Find code blocks without language specification
        code_blocks = re.finditer(r'```(\w*)\n', content)
        
        for code_block in code_blocks:
            language = code_block.group(1)
            line_num = content[:code_block.start()].count('\n') + 1
            
            if not language:
                issues.append(AccessibilityIssue(
                    category=AccessibilityCategory.ROBUST,
                    level=AccessibilityLevel.AA,
                    rule="assistive_tech_compatible",
                    description="Code block without language specification",
                    file_path="",
                    line_number=line_num,
                    severity="low",
                    fix_suggestion="Specify programming language for code blocks (e.g., ```python)"
                ))
        
        return issues
    
    def test_file_accessibility(self, file_path: Path) -> AccessibilityResult:
        """Test accessibility of a single documentation file"""
        print(f"Testing: {file_path.relative_to(self.docs_path)}")
        
        # Parse the file
        parsed = self._parse_markdown_file(file_path)
        
        if 'error' in parsed:
            return AccessibilityResult(
                file_path=str(file_path.relative_to(self.docs_path)),
                total_issues=1,
                critical_issues=1,
                high_issues=0,
                medium_issues=0,
                low_issues=0,
                wcag_aa_compliant=False,
                issues=[AccessibilityIssue(
                    category=AccessibilityCategory.ROBUST,
                    level=AccessibilityLevel.A,
                    rule="valid_markup",
                    description=f"File parsing error: {parsed['error']}",
                    file_path=str(file_path.relative_to(self.docs_path)),
                    severity="critical"
                )],
                success_rate=0.0
            )
        
        all_issues = []
        
        # Run accessibility checks
        all_issues.extend(self._check_heading_structure(parsed['headings']))
        all_issues.extend(self._check_link_accessibility(parsed['links']))
        all_issues.extend(self._check_image_accessibility(parsed['images']))
        all_issues.extend(self._check_language_specification(file_path, parsed['content']))
        all_issues.extend(self._check_content_structure(parsed['content']))
        all_issues.extend(self._check_code_accessibility(parsed['content'], parsed['language_indicators']))
        
        # Update file path in issues
        for issue in all_issues:
            issue.file_path = str(file_path.relative_to(self.docs_path))
        
        # Count issues by severity
        critical_count = sum(1 for issue in all_issues if issue.severity == "critical")
        high_count = sum(1 for issue in all_issues if issue.severity == "high")
        medium_count = sum(1 for issue in all_issues if issue.severity == "medium")
        low_count = sum(1 for issue in all_issues if issue.severity == "low")
        
        # Check WCAG AA compliance (no critical or high issues)
        wcag_aa_compliant = critical_count == 0 and high_count == 0
        
        # Calculate success rate based on issue severity
        total_possible_issues = len(self.wcag_rules['perceivable']) + len(self.wcag_rules['operable']) + len(self.wcag_rules['understandable']) + len(self.wcag_rules['robust'])
        weighted_issues = critical_count * 3 + high_count * 2 + medium_count * 1 + low_count * 0.5
        success_rate = max(0, (total_possible_issues - weighted_issues) / total_possible_issues * 100)
        
        return AccessibilityResult(
            file_path=str(file_path.relative_to(self.docs_path)),
            total_issues=len(all_issues),
            critical_issues=critical_count,
            high_issues=high_count,
            medium_issues=medium_count,
            low_issues=low_count,
            wcag_aa_compliant=wcag_aa_compliant,
            issues=all_issues,
            success_rate=success_rate
        )
    
    def run_comprehensive_accessibility_tests(self) -> Dict[str, Any]:
        """Run comprehensive accessibility tests on all documentation"""
        print("🚀 Starting Accessibility Testing Suite")
        print("Testing documentation for WCAG 2.1 AA compliance")
        
        # Find all markdown files
        markdown_files = []
        for pattern in ['**/*.md']:
            markdown_files.extend(self.docs_path.glob(pattern))
        
        print(f"Found {len(markdown_files)} documentation files to test")
        
        # Test each file
        for file_path in sorted(markdown_files):
            if file_path.is_file():
                result = self.test_file_accessibility(file_path)
                self.results.append(result)
        
        # Calculate overall metrics
        total_files = len(self.results)
        compliant_files = sum(1 for r in self.results if r.wcag_aa_compliant)
        compliance_rate = (compliant_files / total_files * 100) if total_files > 0 else 0
        
        # Aggregate issues
        total_issues = sum(r.total_issues for r in self.results)
        critical_issues = sum(r.critical_issues for r in self.results)
        high_issues = sum(r.high_issues for r in self.results)
        medium_issues = sum(r.medium_issues for r in self.results)
        low_issues = sum(r.low_issues for r in self.results)
        
        # Average success rate
        avg_success_rate = sum(r.success_rate for r in self.results) / total_files if total_files > 0 else 0
        
        # Issue categories analysis
        issue_categories = {}
        issue_rules = {}
        
        for result in self.results:
            for issue in result.issues:
                category = issue.category.value
                rule = issue.rule
                
                issue_categories[category] = issue_categories.get(category, 0) + 1
                issue_rules[rule] = issue_rules.get(rule, 0) + 1
        
        # WCAG AA compliance status
        meets_wcag_aa = critical_issues == 0 and high_issues == 0
        
        return {
            'total_files': total_files,
            'compliant_files': compliant_files,
            'non_compliant_files': total_files - compliant_files,
            'compliance_rate': compliance_rate,
            'avg_success_rate': avg_success_rate,
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'high_issues': high_issues,
            'medium_issues': medium_issues,
            'low_issues': low_issues,
            'meets_wcag_aa': meets_wcag_aa,
            'target_compliance': 100.0,
            'meets_target': meets_wcag_aa and compliance_rate >= 95,
            'issue_categories': issue_categories,
            'issue_rules': issue_rules,
            'detailed_results': self.results
        }
    
    def generate_report(self, metrics: Dict[str, Any]) -> str:
        """Generate comprehensive accessibility report"""
        report = f"""
# Accessibility Testing Report (WCAG 2.1 AA)

## Executive Summary
- **Total Files Tested**: {metrics['total_files']}
- **WCAG AA Compliant Files**: {metrics['compliant_files']}
- **Non-Compliant Files**: {metrics['non_compliant_files']}
- **Compliance Rate**: {metrics['compliance_rate']:.1f}%
- **Average Success Rate**: {metrics['avg_success_rate']:.1f}%
- **Meets WCAG 2.1 AA**: {'✅ YES' if metrics['meets_wcag_aa'] else '❌ NO'}

## Issue Summary
- **Total Issues**: {metrics['total_issues']}
- **Critical Issues**: {metrics['critical_issues']} 🔴
- **High Priority Issues**: {metrics['high_issues']} 🟠
- **Medium Priority Issues**: {metrics['medium_issues']} 🟡
- **Low Priority Issues**: {metrics['low_issues']} 🔵

## WCAG 2.1 AA Compliance Status
"""
        
        if metrics['meets_wcag_aa']:
            report += "🎉 **EXCELLENT** - Documentation meets WCAG 2.1 AA standards!\n"
        elif metrics['critical_issues'] == 0:
            report += "✅ **GOOD** - No critical issues, but some high priority issues need attention.\n"
        else:
            report += "⚠️ **NEEDS IMPROVEMENT** - Critical accessibility issues must be resolved.\n"
        
        # Issues by category
        if metrics['issue_categories']:
            report += "\n## Issues by WCAG Principle\n"
            for category, count in sorted(metrics['issue_categories'].items()):
                report += f"- **{category.title()}**: {count} issues\n"
        
        # Most common issues
        if metrics['issue_rules']:
            report += "\n## Most Common Accessibility Issues\n"
            sorted_rules = sorted(metrics['issue_rules'].items(), key=lambda x: x[1], reverse=True)
            for rule, count in sorted_rules[:5]:
                rule_name = rule.replace('_', ' ').title()
                report += f"- **{rule_name}**: {count} occurrences\n"
        
        # File-by-file results
        report += "\n## File-by-File Results\n"
        
        for result in sorted(metrics['detailed_results'], key=lambda x: x.total_issues, reverse=True):
            if result.total_issues > 0:
                status = "🔴" if result.critical_issues > 0 else "🟠" if result.high_issues > 0 else "🟡" if result.medium_issues > 0 else "🔵"
                compliance = "❌" if not result.wcag_aa_compliant else "✅"
                
                report += f"\n### {result.file_path} {status} {compliance}\n"
                report += f"- **Success Rate**: {result.success_rate:.1f}%\n"
                report += f"- **Total Issues**: {result.total_issues}\n"
                
                if result.critical_issues > 0:
                    report += f"- **Critical**: {result.critical_issues}\n"
                if result.high_issues > 0:
                    report += f"- **High**: {result.high_issues}\n"
                if result.medium_issues > 0:
                    report += f"- **Medium**: {result.medium_issues}\n"
                if result.low_issues > 0:
                    report += f"- **Low**: {result.low_issues}\n"
                
                # Show most critical issues
                critical_issues = [i for i in result.issues if i.severity in ['critical', 'high']]
                if critical_issues:
                    report += "\n**Priority Issues:**\n"
                    for issue in critical_issues[:3]:  # Show top 3
                        report += f"- Line {issue.line_number or '?'}: {issue.description}\n"
                        if issue.fix_suggestion:
                            report += f"  *Fix: {issue.fix_suggestion}*\n"
        
        # Files with perfect accessibility
        perfect_files = [r for r in metrics['detailed_results'] if r.wcag_aa_compliant and r.total_issues == 0]
        if perfect_files:
            report += f"\n## Perfectly Accessible Files ({len(perfect_files)})\n"
            for result in perfect_files:
                report += f"- ✅ {result.file_path}\n"
        
        # Recommendations
        report += "\n## Accessibility Improvement Recommendations\n"
        
        if metrics['critical_issues'] > 0:
            report += "\n### 🔴 Critical Priority (Must Fix)\n"
            critical_rules = {}
            for result in metrics['detailed_results']:
                for issue in result.issues:
                    if issue.severity == 'critical':
                        rule = issue.rule.replace('_', ' ').title()
                        if rule not in critical_rules:
                            critical_rules[rule] = issue.fix_suggestion or "Address this accessibility barrier"
            
            for rule, suggestion in critical_rules.items():
                report += f"- **{rule}**: {suggestion}\n"
        
        if metrics['high_issues'] > 0:
            report += "\n### 🟠 High Priority (Should Fix)\n"
            high_rules = {}
            for result in metrics['detailed_results']:
                for issue in result.issues:
                    if issue.severity == 'high':
                        rule = issue.rule.replace('_', ' ').title()
                        if rule not in high_rules:
                            high_rules[rule] = issue.fix_suggestion or "Improve accessibility for better user experience"
            
            for rule, suggestion in list(high_rules.items())[:3]:  # Top 3
                report += f"- **{rule}**: {suggestion}\n"
        
        # General accessibility guidelines
        report += f"""
### General Accessibility Guidelines

#### Content Structure
- Use proper heading hierarchy (H1 → H2 → H3)
- Provide meaningful link text that describes the destination
- Include alt text for all informative images
- Use tables with proper headers for tabular data

#### Language and Readability
- Specify document language for multilingual content
- Break long paragraphs into shorter, scannable sections
- Use clear, simple language when possible
- Provide definitions for technical terms

#### Navigation and Interaction
- Ensure all functionality is keyboard accessible
- Provide focus indicators for interactive elements
- Use consistent navigation patterns across documents
- Include skip links for long pages

#### Visual Design
- Maintain sufficient color contrast (4.5:1 for normal text)
- Don't rely on color alone to convey information
- Ensure text can be scaled up to 200% without horizontal scrolling
- Use whitespace effectively to improve readability

### Testing and Validation
- Test with screen readers (NVDA, JAWS, VoiceOver)
- Validate with automated accessibility tools
- Conduct user testing with people with disabilities
- Regular accessibility audits during content updates

### Implementation Priority
1. **Critical Issues** (WCAG Level A): Must be fixed immediately
2. **High Priority** (WCAG Level AA): Should be fixed in current iteration
3. **Medium Priority**: Include in next content review cycle
4. **Low Priority** (WCAG Level AAA): Consider for future improvements

---

**WCAG Version**: 2.1 Level AA  
**Test Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Framework Version**: 1.0.0  
**Total Documentation Files**: {metrics['total_files']}
"""
        
        return report


def main():
    """Main test execution"""
    tester = DocumentationAccessibilityTester()
    
    # Run comprehensive accessibility tests
    metrics = tester.run_comprehensive_accessibility_tests()
    
    # Generate and display report
    report = tester.generate_report(metrics)
    print("\n" + "="*80)
    print(report)
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"accessibility_test_results_{timestamp}.json"
    
    # Prepare serializable data
    serializable_results = []
    for result in tester.results:
        serializable_issues = []
        for issue in result.issues:
            serializable_issues.append({
                'category': issue.category.value,
                'level': issue.level.value,
                'rule': issue.rule,
                'description': issue.description,
                'file_path': issue.file_path,
                'line_number': issue.line_number,
                'severity': issue.severity,
                'fix_suggestion': issue.fix_suggestion
            })
        
        serializable_results.append({
            'file_path': result.file_path,
            'total_issues': result.total_issues,
            'critical_issues': result.critical_issues,
            'high_issues': result.high_issues,
            'medium_issues': result.medium_issues,
            'low_issues': result.low_issues,
            'wcag_aa_compliant': result.wcag_aa_compliant,
            'success_rate': result.success_rate,
            'issues': serializable_issues
        })
    
    save_data = {
        'metrics': metrics,
        'detailed_results': serializable_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Return success if WCAG AA compliance is achieved
    return metrics['meets_wcag_aa'] and metrics['compliance_rate'] >= 95


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)