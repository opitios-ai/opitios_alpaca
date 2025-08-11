#!/usr/bin/env python3
"""
Comprehensive coverage reporting and analysis system for opitios_alpaca.

This module provides advanced coverage analysis, trend tracking, threshold enforcement,
and detailed reporting capabilities for the test suite.
"""

import json
import os
import sqlite3
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class CoverageStatus(Enum):
    """Coverage status indicators."""
    PASSED = "passed"
    FAILED_THRESHOLD = "failed_threshold"
    FAILED_CRITICAL = "failed_critical"
    ERROR = "error"


@dataclass
class CoverageThreshold:
    """Coverage threshold configuration."""
    line_coverage_minimum: float = 85.0
    critical_paths_minimum: float = 95.0
    branch_coverage_minimum: float = 80.0
    function_coverage_minimum: float = 90.0
    
    # Critical paths patterns (regex patterns)
    critical_patterns: List[str] = None
    
    def __post_init__(self):
        """Initialize critical patterns if not provided."""
        if self.critical_patterns is None:
            self.critical_patterns = [
                r".*auth.*",  # Authentication flows
                r".*login.*",  # Login mechanisms
                r".*jwt.*",  # JWT handling
                r".*trading.*",  # Trading operations
                r".*order.*",  # Order management
                r".*middleware.*",  # Security middleware
                r".*security.*",  # Security modules
            ]


@dataclass
class CoverageMetrics:
    """Coverage metrics for a test run."""
    timestamp: str
    total_lines: int
    covered_lines: int
    line_coverage: float
    branch_coverage: Optional[float]
    function_coverage: Optional[float]
    critical_coverage: float
    uncovered_lines: List[str]
    critical_uncovered_lines: List[str]
    files_coverage: Dict[str, float]
    test_duration: float
    status: CoverageStatus


@dataclass
class CoverageTrend:
    """Coverage trend analysis."""
    current_coverage: float
    previous_coverage: float
    trend_direction: str  # "up", "down", "stable"
    coverage_diff: float
    days_since_last: int


class CoverageManager:
    """Comprehensive coverage reporting and analysis system."""
    
    def __init__(self, project_root: Path, config: Optional[Dict] = None):
        """Initialize coverage manager.
        
        Args:
            project_root: Path to project root directory
            config: Optional configuration dictionary
        """
        self.project_root = project_root
        self.config = config or {}
        
        # Setup directories
        self.coverage_dir = self.project_root / "htmlcov"
        self.reports_dir = self.project_root / "test-reports"
        self.trends_dir = self.project_root / "coverage-trends"
        self.db_path = self.trends_dir / "coverage_history.db"
        
        # Ensure directories exist
        for directory in [self.coverage_dir, self.reports_dir, self.trends_dir]:
            directory.mkdir(exist_ok=True)
        
        # Setup coverage thresholds
        self.thresholds = CoverageThreshold(**self.config.get("thresholds", {}))
        
        # Initialize database
        self._init_database()
        
    def _init_database(self) -> None:
        """Initialize SQLite database for coverage history tracking."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coverage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    branch TEXT,
                    commit_hash TEXT,
                    total_lines INTEGER,
                    covered_lines INTEGER,
                    line_coverage REAL,
                    branch_coverage REAL,
                    function_coverage REAL,
                    critical_coverage REAL,
                    test_duration REAL,
                    status TEXT,
                    uncovered_lines TEXT,
                    files_coverage TEXT,
                    UNIQUE(timestamp, branch, commit_hash)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON coverage_history(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_branch 
                ON coverage_history(branch)
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to initialize coverage database: {e}")
            
    def generate_coverage_report(self, test_command: List[str], 
                               fail_under: bool = True) -> CoverageMetrics:
        """Generate comprehensive coverage report.
        
        Args:
            test_command: Command to run tests with coverage
            fail_under: Whether to fail if coverage is below thresholds
            
        Returns:
            CoverageMetrics object with detailed coverage information
        """
        logger.info("Starting comprehensive coverage analysis...")
        start_time = datetime.now()
        
        try:
            # Run tests with coverage
            result = self._run_coverage_tests(test_command)
            
            # Parse coverage results
            coverage_data = self._parse_coverage_results()
            
            # Analyze critical paths
            critical_coverage = self._analyze_critical_paths(coverage_data)
            
            # Create metrics object
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            metrics = CoverageMetrics(
                timestamp=start_time.isoformat(),
                total_lines=coverage_data.get("totals", {}).get("num_statements", 0),
                covered_lines=coverage_data.get("totals", {}).get("covered_lines", 0),
                line_coverage=coverage_data.get("totals", {}).get("percent_covered", 0.0),
                branch_coverage=coverage_data.get("totals", {}).get("percent_covered_branches"),
                function_coverage=coverage_data.get("totals", {}).get("percent_covered_functions"),
                critical_coverage=critical_coverage,
                uncovered_lines=self._extract_uncovered_lines(coverage_data),
                critical_uncovered_lines=self._extract_critical_uncovered_lines(coverage_data),
                files_coverage=self._extract_file_coverage(coverage_data),
                test_duration=duration,
                status=self._determine_status(coverage_data.get("totals", {}).get("percent_covered", 0.0), 
                                            critical_coverage)
            )
            
            # Store in database
            self._store_coverage_metrics(metrics)
            
            # Generate reports
            self._generate_detailed_reports(metrics, coverage_data)
            
            # Check thresholds
            if fail_under and metrics.status != CoverageStatus.PASSED:
                self._handle_threshold_failure(metrics)
            
            logger.info(f"Coverage analysis completed: {metrics.line_coverage:.2f}% line coverage")
            return metrics
            
        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            error_metrics = CoverageMetrics(
                timestamp=start_time.isoformat(),
                total_lines=0,
                covered_lines=0,
                line_coverage=0.0,
                branch_coverage=None,
                function_coverage=None,
                critical_coverage=0.0,
                uncovered_lines=[],
                critical_uncovered_lines=[],
                files_coverage={},
                test_duration=(datetime.now() - start_time).total_seconds(),
                status=CoverageStatus.ERROR
            )
            
            if fail_under:
                raise
                
            return error_metrics
    
    def _run_coverage_tests(self, test_command: List[str]) -> subprocess.CompletedProcess:
        """Run tests with coverage collection."""
        logger.info(f"Running test command: {' '.join(test_command)}")
        
        # Check if this is a collect-only command
        is_collect_only = "--collect-only" in test_command
        
        # Ensure coverage reports are generated in all formats (but not for collect-only)
        enhanced_command = test_command.copy()
        
        if not is_collect_only:
            # Add coverage reporting options if not already present
            coverage_options = [
                f"--cov-report=html:{self.coverage_dir}",
                f"--cov-report=xml:{self.reports_dir}/coverage.xml",
                f"--cov-report=json:{self.reports_dir}/coverage.json",
                "--cov-report=term-missing"
            ]
            
            for option in coverage_options:
                if option not in enhanced_command:
                    enhanced_command.append(option)
        
        result = subprocess.run(
            enhanced_command,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Test command failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
        
        return result
    
    def _parse_coverage_results(self) -> Dict[str, Any]:
        """Parse coverage results from JSON report."""
        json_path = self.reports_dir / "coverage.json"
        
        if not json_path.exists():
            # Return empty coverage data for collect-only runs
            return {
                "totals": {
                    "num_statements": 0,
                    "covered_lines": 0,
                    "percent_covered": 0.0
                },
                "files": {}
            }
        
        with open(json_path, 'r') as f:
            return json.load(f)
    
    def _analyze_critical_paths(self, coverage_data: Dict[str, Any]) -> float:
        """Analyze coverage of critical paths."""
        import re
        
        files = coverage_data.get("files", {})
        critical_files = []
        
        for file_path, file_data in files.items():
            for pattern in self.thresholds.critical_patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    critical_files.append(file_data)
                    break
        
        if not critical_files:
            return 100.0  # No critical files found
        
        total_lines = sum(f.get("summary", {}).get("num_statements", 0) for f in critical_files)
        covered_lines = sum(f.get("summary", {}).get("covered_lines", 0) for f in critical_files)
        
        if total_lines == 0:
            return 100.0
            
        return (covered_lines / total_lines) * 100.0
    
    def _extract_uncovered_lines(self, coverage_data: Dict[str, Any]) -> List[str]:
        """Extract uncovered line information."""
        uncovered = []
        files = coverage_data.get("files", {})
        
        for file_path, file_data in files.items():
            missing_lines = file_data.get("missing_lines", [])
            if missing_lines:
                uncovered.append(f"{file_path}: lines {', '.join(map(str, missing_lines))}")
        
        return uncovered
    
    def _extract_critical_uncovered_lines(self, coverage_data: Dict[str, Any]) -> List[str]:
        """Extract uncovered lines in critical paths."""
        import re
        
        uncovered = []
        files = coverage_data.get("files", {})
        
        for file_path, file_data in files.items():
            # Check if file is critical
            is_critical = any(
                re.search(pattern, file_path, re.IGNORECASE) 
                for pattern in self.thresholds.critical_patterns
            )
            
            if is_critical:
                missing_lines = file_data.get("missing_lines", [])
                if missing_lines:
                    uncovered.append(f"CRITICAL - {file_path}: lines {', '.join(map(str, missing_lines))}")
        
        return uncovered
    
    def _extract_file_coverage(self, coverage_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract per-file coverage percentages."""
        file_coverage = {}
        files = coverage_data.get("files", {})
        
        for file_path, file_data in files.items():
            summary = file_data.get("summary", {})
            total = summary.get("num_statements", 0)
            covered = summary.get("covered_lines", 0)
            
            if total > 0:
                coverage_pct = (covered / total) * 100.0
            else:
                coverage_pct = 100.0
                
            file_coverage[file_path] = coverage_pct
        
        return file_coverage
    
    def _determine_status(self, line_coverage: float, critical_coverage: float) -> CoverageStatus:
        """Determine overall coverage status."""
        if critical_coverage < self.thresholds.critical_paths_minimum:
            return CoverageStatus.FAILED_CRITICAL
        elif line_coverage < self.thresholds.line_coverage_minimum:
            return CoverageStatus.FAILED_THRESHOLD
        else:
            return CoverageStatus.PASSED
    
    def _store_coverage_metrics(self, metrics: CoverageMetrics) -> None:
        """Store coverage metrics in database."""
        try:
            # Get git information
            branch = self._get_git_branch()
            commit_hash = self._get_git_commit_hash()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO coverage_history (
                    timestamp, branch, commit_hash, total_lines, covered_lines,
                    line_coverage, branch_coverage, function_coverage, 
                    critical_coverage, test_duration, status,
                    uncovered_lines, files_coverage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.timestamp,
                branch,
                commit_hash,
                metrics.total_lines,
                metrics.covered_lines,
                metrics.line_coverage,
                metrics.branch_coverage,
                metrics.function_coverage,
                metrics.critical_coverage,
                metrics.test_duration,
                metrics.status.value,
                json.dumps(metrics.uncovered_lines),
                json.dumps(metrics.files_coverage)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info("Coverage metrics stored in database")
            
        except Exception as e:
            logger.error(f"Failed to store coverage metrics: {e}")
    
    def _generate_detailed_reports(self, metrics: CoverageMetrics, coverage_data: Dict[str, Any]) -> None:
        """Generate detailed coverage reports."""
        try:
            # Generate summary report
            self._generate_summary_report(metrics)
            
            # Generate trend analysis
            trend = self._analyze_coverage_trends()
            if trend:
                self._generate_trend_report(trend)
            
            # Generate uncovered code report
            self._generate_uncovered_report(metrics)
            
            # Generate file-by-file analysis
            self._generate_file_analysis_report(metrics)
            
        except Exception as e:
            logger.error(f"Failed to generate detailed reports: {e}")
    
    def _generate_summary_report(self, metrics: CoverageMetrics) -> None:
        """Generate coverage summary report."""
        report_path = self.reports_dir / "coverage_summary.html"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Coverage Summary Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: white; border: 1px solid #ddd; padding: 15px; border-radius: 5px; text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .warning {{ color: #ffc107; }}
        .critical {{ background-color: #f8d7da; border-color: #f5c6cb; }}
        .uncovered {{ margin: 20px 0; }}
        .uncovered ul {{ max-height: 300px; overflow-y: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Coverage Summary Report</h1>
        <p>Generated: {metrics.timestamp}</p>
        <p>Status: <span class="{'passed' if metrics.status == CoverageStatus.PASSED else 'failed'}">{metrics.status.value.upper()}</span></p>
    </div>
    
    <div class="metrics">
        <div class="metric">
            <div class="metric-title">Line Coverage</div>
            <div class="metric-value {'passed' if metrics.line_coverage >= self.thresholds.line_coverage_minimum else 'failed'}">
                {metrics.line_coverage:.1f}%
            </div>
            <div>Minimum: {self.thresholds.line_coverage_minimum}%</div>
        </div>
        
        <div class="metric">
            <div class="metric-title">Critical Paths</div>
            <div class="metric-value {'passed' if metrics.critical_coverage >= self.thresholds.critical_paths_minimum else 'failed'}">
                {metrics.critical_coverage:.1f}%
            </div>
            <div>Minimum: {self.thresholds.critical_paths_minimum}%</div>
        </div>
        
        <div class="metric">
            <div class="metric-title">Total Lines</div>
            <div class="metric-value">{metrics.total_lines:,}</div>
            <div>Covered: {metrics.covered_lines:,}</div>
        </div>
        
        <div class="metric">
            <div class="metric-title">Test Duration</div>
            <div class="metric-value">{metrics.test_duration:.1f}s</div>
        </div>
    </div>
    
    {self._generate_uncovered_section(metrics)}
    
    <div class="footer">
        <p><a href="index.html">View Detailed HTML Report</a></p>
    </div>
</body>
</html>
        """
        
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Summary report generated: {report_path}")
    
    def _generate_uncovered_section(self, metrics: CoverageMetrics) -> str:
        """Generate uncovered code section for HTML report."""
        if not metrics.uncovered_lines and not metrics.critical_uncovered_lines:
            return '<div class="uncovered"><h3>All code is covered! 🎉</h3></div>'
        
        html = '<div class="uncovered">'
        
        if metrics.critical_uncovered_lines:
            html += '''
            <div class="critical">
                <h3>Critical Uncovered Lines (Requires Immediate Attention)</h3>
                <ul>
            '''
            for line in metrics.critical_uncovered_lines[:20]:  # Limit to first 20
                html += f'<li>{line}</li>'
            html += '</ul></div>'
        
        if metrics.uncovered_lines:
            html += '''
            <h3>All Uncovered Lines</h3>
            <ul>
            '''
            for line in metrics.uncovered_lines[:50]:  # Limit to first 50
                html += f'<li>{line}</li>'
            html += '</ul>'
        
        html += '</div>'
        return html
    
    def _analyze_coverage_trends(self) -> Optional[CoverageTrend]:
        """Analyze coverage trends over time."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get last two coverage runs
            cursor.execute("""
                SELECT line_coverage, timestamp 
                FROM coverage_history 
                ORDER BY timestamp DESC 
                LIMIT 2
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            if len(results) < 2:
                return None
            
            current_coverage, current_time = results[0]
            previous_coverage, previous_time = results[1]
            
            current_dt = datetime.fromisoformat(current_time)
            previous_dt = datetime.fromisoformat(previous_time)
            
            days_diff = (current_dt - previous_dt).days
            coverage_diff = current_coverage - previous_coverage
            
            if abs(coverage_diff) < 0.1:
                trend_direction = "stable"
            elif coverage_diff > 0:
                trend_direction = "up"
            else:
                trend_direction = "down"
            
            return CoverageTrend(
                current_coverage=current_coverage,
                previous_coverage=previous_coverage,
                trend_direction=trend_direction,
                coverage_diff=coverage_diff,
                days_since_last=days_diff
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze coverage trends: {e}")
            return None
    
    def _generate_trend_report(self, trend: CoverageTrend) -> None:
        """Generate coverage trend report."""
        report_path = self.reports_dir / "coverage_trends.json"
        
        trend_data = {
            "timestamp": datetime.now().isoformat(),
            "current_coverage": trend.current_coverage,
            "previous_coverage": trend.previous_coverage,
            "trend_direction": trend.trend_direction,
            "coverage_diff": trend.coverage_diff,
            "days_since_last": trend.days_since_last
        }
        
        with open(report_path, 'w') as f:
            json.dump(trend_data, f, indent=2)
        
        logger.info(f"Trend report generated: {report_path}")
    
    def _generate_uncovered_report(self, metrics: CoverageMetrics) -> None:
        """Generate detailed uncovered code report."""
        report_path = self.reports_dir / "uncovered_code.txt"
        
        with open(report_path, 'w') as f:
            f.write("UNCOVERED CODE ANALYSIS\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generated: {metrics.timestamp}\n")
            f.write(f"Overall Coverage: {metrics.line_coverage:.2f}%\n")
            f.write(f"Critical Coverage: {metrics.critical_coverage:.2f}%\n\n")
            
            if metrics.critical_uncovered_lines:
                f.write("CRITICAL UNCOVERED LINES (HIGH PRIORITY)\n")
                f.write("-" * 40 + "\n")
                for line in metrics.critical_uncovered_lines:
                    f.write(f"  {line}\n")
                f.write("\n")
            
            if metrics.uncovered_lines:
                f.write("ALL UNCOVERED LINES\n")
                f.write("-" * 20 + "\n")
                for line in metrics.uncovered_lines:
                    f.write(f"  {line}\n")
        
        logger.info(f"Uncovered code report generated: {report_path}")
    
    def _generate_file_analysis_report(self, metrics: CoverageMetrics) -> None:
        """Generate per-file coverage analysis."""
        report_path = self.reports_dir / "file_coverage_analysis.json"
        
        # Sort files by coverage percentage
        sorted_files = sorted(
            metrics.files_coverage.items(),
            key=lambda x: x[1]
        )
        
        analysis = {
            "timestamp": metrics.timestamp,
            "files_by_coverage": {
                "lowest_coverage": sorted_files[:10],  # Bottom 10
                "highest_coverage": sorted_files[-10:][::-1],  # Top 10
                "needs_attention": [(f, c) for f, c in sorted_files if c < 50.0],
                "well_covered": [(f, c) for f, c in sorted_files if c >= 90.0]
            },
            "summary": {
                "total_files": len(sorted_files),
                "average_coverage": sum(c for _, c in sorted_files) / len(sorted_files) if sorted_files else 0,
                "files_below_threshold": len([c for _, c in sorted_files if c < self.thresholds.line_coverage_minimum]),
                "files_well_covered": len([c for _, c in sorted_files if c >= 90.0])
            }
        }
        
        with open(report_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        logger.info(f"File analysis report generated: {report_path}")
    
    def _handle_threshold_failure(self, metrics: CoverageMetrics) -> None:
        """Handle coverage threshold failures."""
        error_message = f"Coverage threshold failure: {metrics.status.value}\n"
        error_message += f"Line coverage: {metrics.line_coverage:.2f}% (minimum: {self.thresholds.line_coverage_minimum}%)\n"
        error_message += f"Critical coverage: {metrics.critical_coverage:.2f}% (minimum: {self.thresholds.critical_paths_minimum}%)\n"
        
        if metrics.critical_uncovered_lines:
            error_message += f"\nCritical uncovered lines ({len(metrics.critical_uncovered_lines)}):\n"
            for line in metrics.critical_uncovered_lines[:10]:
                error_message += f"  - {line}\n"
        
        logger.error(error_message)
        raise ValueError(error_message)
    
    def get_coverage_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get coverage history for specified number of days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute("""
                SELECT * FROM coverage_history 
                WHERE timestamp >= ? 
                ORDER BY timestamp DESC
            """, (cutoff_date,))
            
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON fields
                result['uncovered_lines'] = json.loads(result['uncovered_lines'] or '[]')
                result['files_coverage'] = json.loads(result['files_coverage'] or '{}')
                results.append(result)
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get coverage history: {e}")
            return []
    
    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_git_commit_hash(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def cleanup_old_reports(self, days: int = 30) -> None:
        """Clean up old coverage reports."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Clean database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM coverage_history 
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old coverage records")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old reports: {e}")