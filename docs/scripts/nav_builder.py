#!/usr/bin/env python3
"""
Navigation Builder Script for Opitios Alpaca Trading Service Documentation

This script builds comprehensive navigation and cross-reference systems
for the documentation, ensuring easy discovery and interconnection of content.

Usage:
    python docs/scripts/nav_builder.py

Features:
- Automatic table of contents generation
- Cross-reference link building
- Documentation index creation
- Language switching navigation
- Breadcrumb generation
- Related content suggestions
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class NavigationBuilder:
    def __init__(self):
        self.project_root = Path.cwd()
        self.docs_root = self.project_root / "docs"
        self.en_docs = self.docs_root / "en"
        self.zh_docs = self.docs_root / "zh"
        
        # Document mappings
        self.doc_mapping = {
            'quickstart': {
                'en': 'docs/en/quickstart.md',
                'zh': 'docs/zh/快速开始指南.md',
                'title_en': 'Quick Start Guide',
                'title_zh': '快速开始指南',
                'category': 'Getting Started'
            },
            'api-examples': {
                'en': 'docs/en/api-examples.md',
                'zh': 'docs/zh/API使用示例.md',
                'title_en': 'API Examples',
                'title_zh': 'API 使用示例',
                'category': 'API Reference'
            },
            'troubleshooting': {
                'en': 'docs/en/troubleshooting.md',
                'zh': 'docs/zh/故障排除指南.md',
                'title_en': 'Troubleshooting Guide',
                'title_zh': '故障排除指南',
                'category': 'Support'
            },
            'setup-validation': {
                'en': 'docs/en/setup-validation.md',
                'zh': 'docs/zh/安装验证.md',
                'title_en': 'Setup Validation',
                'title_zh': '安装验证',
                'category': 'Getting Started'
            }
        }
        
        # Navigation structure
        self.navigation = {
            'Getting Started': ['quickstart', 'setup-validation'],
            'API Reference': ['api-examples'],
            'Support': ['troubleshooting'],
            'Tools': ['scripts']
        }

    def extract_headers(self, content: str) -> List[Tuple[int, str, str]]:
        """Extract headers from markdown content"""
        headers = []
        lines = content.split('\n')
        
        for line in lines:
            match = re.match(r'^(#{1,6})\s+(.+)', line)
            if match:
                level = len(match.group(1))
                title = match.group(2)
                # Create anchor
                anchor = re.sub(r'[^\w\s-]', '', title).strip()
                anchor = re.sub(r'[-\s]+', '-', anchor).lower()
                headers.append((level, title, anchor))
        
        return headers

    def generate_toc(self, headers: List[Tuple[int, str, str]], max_level: int = 3) -> str:
        """Generate table of contents from headers"""
        if not headers:
            return ""
        
        toc_lines = ["## 📋 Table of Contents\n"]
        
        for level, title, anchor in headers:
            if level <= max_level and level > 1:  # Skip H1, include H2-H3
                indent = "  " * (level - 2)
                toc_lines.append(f"{indent}- [{title}](#{anchor})")
        
        return "\n".join(toc_lines) + "\n"

    def generate_breadcrumb(self, doc_key: str, language: str) -> str:
        """Generate breadcrumb navigation"""
        doc_info = self.doc_mapping.get(doc_key)
        if not doc_info:
            return ""
        
        category = doc_info['category']
        title = doc_info[f'title_{language}']
        
        if language == 'en':
            return f"[Documentation](../README.md) > [{category}](#{category.lower().replace(' ', '-')}) > {title}"
        else:
            return f"[文档](../README.md) > [{category}](#{category.lower().replace(' ', '-')}) > {title}"

    def generate_language_switcher(self, doc_key: str, current_lang: str) -> str:
        """Generate language switcher"""
        doc_info = self.doc_mapping.get(doc_key)
        if not doc_info:
            return ""
        
        other_lang = 'zh' if current_lang == 'en' else 'en'
        other_path = doc_info[other_lang]
        
        if current_lang == 'en':
            return f"**🌐 Language**: [English](#) | [中文]({other_path.replace('docs/en/', '../zh/')})"
        else:
            return f"**🌐 语言**: [中文](#) | [English]({other_path.replace('docs/zh/', '../en/')})"

    def generate_related_content(self, doc_key: str, language: str) -> str:
        """Generate related content suggestions"""
        doc_info = self.doc_mapping.get(doc_key)
        if not doc_info:
            return ""
        
        category = doc_info['category']
        
        # Find related documents in same category
        related_docs = []
        for key, info in self.doc_mapping.items():
            if key != doc_key and info['category'] == category:
                related_docs.append(key)
        
        # Add some cross-category suggestions
        if doc_key == 'quickstart':
            related_docs.extend(['api-examples', 'setup-validation'])
        elif doc_key == 'troubleshooting':
            related_docs.extend(['quickstart', 'setup-validation'])
        elif doc_key == 'api-examples':
            related_docs.extend(['quickstart', 'troubleshooting'])
        
        if not related_docs:
            return ""
        
        if language == 'en':
            lines = ["## 📖 Related Documentation\n"]
        else:
            lines = ["## 📖 相关文档\n"]
        
        for related_key in related_docs[:3]:  # Limit to 3 suggestions
            related_info = self.doc_mapping.get(related_key)
            if related_info:
                title = related_info[f'title_{language}']
                path = related_info[language]
                if language == 'en':
                    relative_path = path.replace('docs/en/', '')
                else:
                    relative_path = path.replace('docs/zh/', '')
                lines.append(f"- **[{title}]({relative_path})**")
        
        return "\n".join(lines) + "\n"

    def generate_footer(self, doc_key: str, language: str) -> str:
        """Generate document footer with navigation"""
        doc_info = self.doc_mapping.get(doc_key)
        if not doc_info:
            return ""
        
        if language == 'en':
            footer = [
                "---",
                "",
                f"**📝 Document**: {doc_info['title_en']}  ",
                "**📅 Last Updated**: January 2025  ",
                "**🔗 Links**: [🏠 Home](../../README.md) | [📚 Docs](../README.md) | [🛠️ Tools](../scripts/)",
                "",
                "**Need Help?**",
                "- 🚀 [Quick Start](quickstart.md)",
                "- 📋 [API Examples](api-examples.md)",
                "- 🔧 [Troubleshooting](troubleshooting.md)",
                "- ✅ [Setup Validation](setup-validation.md)"
            ]
        else:
            footer = [
                "---",
                "",
                f"**📝 文档**: {doc_info['title_zh']}  ",
                "**📅 最后更新**: 2025年1月  ",
                "**🔗 链接**: [🏠 首页](../../README.zh.md) | [📚 文档](../README.md) | [🛠️ 工具](../scripts/)",
                "",
                "**需要帮助？**",
                "- 🚀 [快速开始](快速开始指南.md)",
                "- 📋 [API 示例](API使用示例.md)",
                "- 🔧 [故障排除](故障排除指南.md)",
                "- ✅ [安装验证](安装验证.md)"
            ]
        
        return "\n".join(footer)

    def enhance_document(self, file_path: Path, doc_key: str, language: str) -> bool:
        """Enhance a document with navigation elements"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract existing headers
            headers = self.extract_headers(content)
            
            # Generate navigation elements
            toc = self.generate_toc(headers)
            language_switcher = self.generate_language_switcher(doc_key, language)
            related_content = self.generate_related_content(doc_key, language)
            footer = self.generate_footer(doc_key, language)
            
            # Find insertion points
            lines = content.split('\n')
            enhanced_lines = []
            
            # Add language switcher after title
            title_found = False
            toc_inserted = False
            
            for i, line in enumerate(lines):
                enhanced_lines.append(line)
                
                # Add language switcher after main title
                if not title_found and line.startswith('# '):
                    enhanced_lines.append("")
                    enhanced_lines.append(language_switcher)
                    enhanced_lines.append("")
                    title_found = True
                
                # Insert TOC after description/intro paragraph
                if title_found and not toc_inserted and line.strip() == "" and i < len(lines) - 1 and lines[i + 1].startswith('##'):
                    enhanced_lines.append(toc)
                    toc_inserted = True
            
            # Add related content and footer at the end
            if not content.endswith('\n---\n'):
                enhanced_lines.append("")
                enhanced_lines.append(related_content)
                enhanced_lines.append(footer)
            
            # Write enhanced content
            enhanced_content = '\n'.join(enhanced_lines)
            file_path.write_text(enhanced_content, encoding='utf-8')
            
            return True
            
        except Exception as e:
            print(f"Error enhancing {file_path}: {str(e)}")
            return False

    def generate_documentation_index(self) -> str:
        """Generate comprehensive documentation index"""
        index_content = [
            "# 📚 Documentation Index",
            "",
            "Complete index of all documentation for the Opitios Alpaca Trading Service.",
            "",
            "## 🌐 Available Languages",
            "",
            "| Language | Code | Status |",
            "|----------|------|--------|",
            "| English | `en` | ✅ Complete |",
            "| 中文 (Chinese) | `zh` | ✅ Complete |",
            "",
            "## 📋 Document Categories",
            ""
        ]
        
        for category, doc_keys in self.navigation.items():
            index_content.append(f"### {category}")
            index_content.append("")
            
            for doc_key in doc_keys:
                if doc_key == 'scripts':
                    index_content.append("#### Interactive Tools")
                    index_content.append("")
                    index_content.append("| Tool | Description | Command |")
                    index_content.append("|------|-------------|---------|")
                    index_content.append("| Setup Validator | Interactive setup verification | `python docs/scripts/setup_validator.py` |")
                    index_content.append("| Health Check | System health monitoring | `python docs/scripts/health_check.py` |")
                    index_content.append("| Config Helper | Configuration management | `python docs/scripts/config_helper.py` |")
                    index_content.append("| Doc Validator | Documentation validation | `python docs/scripts/doc_validator.py` |")
                    index_content.append("")
                    continue
                
                doc_info = self.doc_mapping.get(doc_key)
                if doc_info:
                    index_content.append(f"#### {doc_info['title_en']}")
                    index_content.append("")
                    index_content.append("| Language | Document | Description |")
                    index_content.append("|----------|----------|-------------|")
                    index_content.append(f"| English | [{doc_info['title_en']}]({doc_info['en']}) | Comprehensive guide |")
                    index_content.append(f"| 中文 | [{doc_info['title_zh']}]({doc_info['zh']}) | 完整指南 |")
                    index_content.append("")
        
        # Add quick links section
        index_content.extend([
            "## 🚀 Quick Links",
            "",
            "### Getting Started",
            "- 🇺🇸 [Quick Start Guide](en/quickstart.md) | 🇨🇳 [快速开始指南](zh/快速开始指南.md)",
            "- 🇺🇸 [Setup Validation](en/setup-validation.md) | 🇨🇳 [安装验证](zh/安装验证.md)",
            "",
            "### API Reference",
            "- 🇺🇸 [API Examples](en/api-examples.md) | 🇨🇳 [API 使用示例](zh/API使用示例.md)",
            "",
            "### Support",
            "- 🇺🇸 [Troubleshooting](en/troubleshooting.md) | 🇨🇳 [故障排除指南](zh/故障排除指南.md)",
            "",
            "### Tools",
            "- [Setup Validator](scripts/setup_validator.py) - Interactive setup verification",
            "- [Health Check](scripts/health_check.py) - System monitoring",
            "- [Config Helper](scripts/config_helper.py) - Configuration management",
            "- [Doc Validator](scripts/doc_validator.py) - Documentation validation",
            "",
            "## 📊 Documentation Statistics",
            "",
            f"- **Total Documents**: {len(self.doc_mapping) * 2} (bilingual)",
            f"- **Categories**: {len(self.navigation)}",
            "- **Interactive Tools**: 4",
            "- **Languages**: 2 (English, Chinese)",
            "- **Completion**: 100%",
            "",
            "---",
            "",
            "**Documentation Index Version**: 1.0.0  ",
            "**Last Updated**: January 2025  ",
            "**Maintained by**: Opitios Team"
        ])
        
        return "\n".join(index_content)

    def build_navigation(self) -> Dict[str, int]:
        """Build comprehensive navigation system"""
        results = {
            'enhanced_files': 0,
            'errors': 0
        }
        
        print("🔧 Building navigation system...")
        
        # Enhance English documents
        for doc_key, doc_info in self.doc_mapping.items():
            en_path = self.project_root / doc_info['en']
            if en_path.exists():
                if self.enhance_document(en_path, doc_key, 'en'):
                    results['enhanced_files'] += 1
                    print(f"✅ Enhanced: {doc_info['en']}")
                else:
                    results['errors'] += 1
                    print(f"❌ Failed: {doc_info['en']}")
        
        # Enhance Chinese documents
        for doc_key, doc_info in self.doc_mapping.items():
            zh_path = self.project_root / doc_info['zh']
            if zh_path.exists():
                if self.enhance_document(zh_path, doc_key, 'zh'):
                    results['enhanced_files'] += 1
                    print(f"✅ Enhanced: {doc_info['zh']}")
                else:
                    results['errors'] += 1
                    print(f"❌ Failed: {doc_info['zh']}")
        
        # Generate documentation index
        try:
            index_content = self.generate_documentation_index()
            index_path = self.docs_root / "INDEX.md"
            index_path.write_text(index_content, encoding='utf-8')
            print(f"✅ Generated: {index_path}")
            results['enhanced_files'] += 1
        except Exception as e:
            print(f"❌ Failed to generate index: {str(e)}")
            results['errors'] += 1
        
        return results

def main():
    """Main navigation builder workflow"""
    print("📚 Opitios Alpaca Trading Service - Navigation Builder")
    print("Building comprehensive navigation and cross-reference systems...")
    
    builder = NavigationBuilder()
    results = builder.build_navigation()
    
    print(f"\n📊 Results:")
    print(f"Enhanced files: {results['enhanced_files']}")
    print(f"Errors: {results['errors']}")
    
    if results['errors'] == 0:
        print("🎉 Navigation system built successfully!")
    else:
        print("⚠️  Some issues occurred during navigation building.")
    
    return results['errors'] == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)