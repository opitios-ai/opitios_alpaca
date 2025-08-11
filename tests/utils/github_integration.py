#!/usr/bin/env python3
"""
GitHub Integration system for opitios_alpaca project.

This module provides comprehensive GitHub integration capabilities including:
- Posting coverage reports as PR comments
- Updating GitHub status checks for test results
- Uploading test artifacts
- Managing GitHub workflow integration
"""

import json
import os
import sys
import asyncio
import aiohttp
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import base64
import gzip

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.coverage_manager import CoverageManager, CoverageMetrics, CoverageStatus

logger = logging.getLogger(__name__)


class GitHubCheckStatus(Enum):
    """GitHub check status values."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class GitHubCheckConclusion(Enum):
    """GitHub check conclusion values."""
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"


@dataclass
class GitHubConfig:
    """GitHub configuration for API access."""
    token: str
    repository: str  # format: "owner/repo"
    api_base_url: str = "https://api.github.com"


@dataclass
class PullRequestInfo:
    """Pull request information."""
    number: int
    head_sha: str
    base_sha: str
    branch: str
    base_branch: str


@dataclass
class TestArtifact:
    """Test artifact information."""
    name: str
    path: Path
    content_type: str
    description: Optional[str] = None


@dataclass
class CoverageDiff:
    """Coverage comparison between branches."""
    current_coverage: float
    base_coverage: float
    coverage_diff: float
    trend: str  # "improved", "declined", "unchanged"
    files_changed: Dict[str, Tuple[float, float]]  # file -> (old_cov, new_cov)
    critical_files_affected: List[str]


class GitHubIntegration:
    """Comprehensive GitHub integration for test automation and reporting."""
    
    def __init__(self, config: GitHubConfig, coverage_manager: Optional[CoverageManager] = None):
        """Initialize GitHub integration.
        
        Args:
            config: GitHub configuration with API token and repository info
            coverage_manager: Optional existing coverage manager instance
        """
        self.config = config
        self.coverage_manager = coverage_manager
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Setup paths
        self.project_root = Path(__file__).parent.parent.parent
        self.artifacts_dir = self.project_root / "github-artifacts"
        self.artifacts_dir.mkdir(exist_ok=True)
        
        # GitHub API endpoints
        self.api_base = self.config.api_base_url
        self.repo = self.config.repository
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()
        
    async def _ensure_session(self):
        """Ensure aiohttp session is available."""
        if not self.session:
            headers = {
                "Authorization": f"token {self.config.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "opitios-alpaca-testing"
            }
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
            
    async def _close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def post_coverage_comment(self, pr_number: int, coverage_metrics: CoverageMetrics, 
                                  base_coverage: Optional[CoverageMetrics] = None) -> bool:
        """Post comprehensive coverage report as PR comment.
        
        Args:
            pr_number: Pull request number
            coverage_metrics: Current coverage metrics
            base_coverage: Base branch coverage for comparison
            
        Returns:
            True if comment posted successfully
        """
        try:
            await self._ensure_session()
            
            # Generate coverage diff if base coverage provided
            coverage_diff = None
            if base_coverage:
                coverage_diff = self._calculate_coverage_diff(coverage_metrics, base_coverage)
            
            # Generate comment content
            comment_body = self._generate_coverage_comment(coverage_metrics, coverage_diff)
            
            # Check if existing coverage comment exists
            existing_comment_id = await self._find_existing_coverage_comment(pr_number)
            
            if existing_comment_id:
                # Update existing comment
                success = await self._update_pr_comment(existing_comment_id, comment_body)
                action = "updated"
            else:
                # Create new comment
                success = await self._create_pr_comment(pr_number, comment_body)
                action = "created"
                
            if success:
                logger.info(f"Coverage comment {action} successfully for PR #{pr_number}")
            else:
                logger.error(f"Failed to {action[:-1]} coverage comment for PR #{pr_number}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error posting coverage comment: {e}")
            return False
    
    async def update_status_check(self, commit_sha: str, status: GitHubCheckStatus, 
                                conclusion: Optional[GitHubCheckConclusion] = None,
                                coverage_metrics: Optional[CoverageMetrics] = None) -> bool:
        """Update GitHub status check for test results.
        
        Args:
            commit_sha: Git commit SHA
            status: Check status (queued, in_progress, completed)
            conclusion: Check conclusion (only for completed status)
            coverage_metrics: Optional coverage metrics for detailed reporting
            
        Returns:
            True if status updated successfully
        """
        try:
            await self._ensure_session()
            
            # Prepare check data
            check_data = {
                "name": "Comprehensive Test Suite",
                "head_sha": commit_sha,
                "status": status.value,
                "started_at": datetime.utcnow().isoformat() + "Z"
            }
            
            if status == GitHubCheckStatus.COMPLETED:
                check_data["completed_at"] = datetime.utcnow().isoformat() + "Z"
                check_data["conclusion"] = conclusion.value if conclusion else GitHubCheckConclusion.SUCCESS.value
                
                # Add detailed output
                if coverage_metrics:
                    output = self._generate_status_check_output(coverage_metrics)
                    check_data["output"] = output
            
            # Create or update check run
            url = f"{self.api_base}/repos/{self.repo}/check-runs"
            
            async with self.session.post(url, json=check_data) as response:
                if response.status == 201:
                    check_run = await response.json()
                    logger.info(f"Status check updated: {check_run['name']} - {status.value}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to update status check: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating status check: {e}")
            return False
    
    async def upload_test_artifacts(self, artifacts: List[TestArtifact], 
                                  pr_number: Optional[int] = None) -> bool:
        """Upload test artifacts to GitHub.
        
        Args:
            artifacts: List of test artifacts to upload
            pr_number: Optional PR number for artifact linking
            
        Returns:
            True if artifacts uploaded successfully
        """
        try:
            await self._ensure_session()
            
            uploaded_artifacts = []
            
            for artifact in artifacts:
                # Compress artifact if it's large
                compressed_content, encoding = await self._prepare_artifact_content(artifact.path)
                
                # Create artifact metadata
                artifact_info = {
                    "name": artifact.name,
                    "path": str(artifact.path.relative_to(self.project_root)),
                    "content_type": artifact.content_type,
                    "description": artifact.description or f"Test artifact: {artifact.name}",
                    "size": len(compressed_content),
                    "encoding": encoding,
                    "uploaded_at": datetime.utcnow().isoformat() + "Z"
                }
                
                # Store artifact locally in artifacts directory
                artifact_file = self.artifacts_dir / f"{artifact.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                if encoding == "gzip":
                    artifact_file = artifact_file.with_suffix(artifact_file.suffix + ".gz")
                
                with open(artifact_file, 'wb') as f:
                    f.write(compressed_content)
                
                artifact_info["local_path"] = str(artifact_file)
                uploaded_artifacts.append(artifact_info)
                
                logger.info(f"Artifact stored locally: {artifact_file}")
            
            # Create artifacts index file
            artifacts_index = {
                "created_at": datetime.utcnow().isoformat() + "Z",
                "pr_number": pr_number,
                "artifacts": uploaded_artifacts
            }
            
            index_file = self.artifacts_dir / f"artifacts_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(index_file, 'w') as f:
                json.dump(artifacts_index, f, indent=2)
            
            logger.info(f"Artifacts index created: {index_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading test artifacts: {e}")
            return False
    
    async def get_pull_request_info(self, pr_number: int) -> Optional[PullRequestInfo]:
        """Get pull request information.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            PullRequestInfo object or None if not found
        """
        try:
            await self._ensure_session()
            
            url = f"{self.api_base}/repos/{self.repo}/pulls/{pr_number}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    pr_data = await response.json()
                    return PullRequestInfo(
                        number=pr_data["number"],
                        head_sha=pr_data["head"]["sha"],
                        base_sha=pr_data["base"]["sha"],
                        branch=pr_data["head"]["ref"],
                        base_branch=pr_data["base"]["ref"]
                    )
                else:
                    logger.error(f"Failed to get PR info: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting PR info: {e}")
            return None
    
    async def get_base_branch_coverage(self, base_sha: str) -> Optional[CoverageMetrics]:
        """Get coverage metrics for base branch.
        
        Args:
            base_sha: Base branch commit SHA
            
        Returns:
            CoverageMetrics for base branch or None if not available
        """
        try:
            if not self.coverage_manager:
                return None
                
            # Try to find coverage data for the base SHA in the database
            history = self.coverage_manager.get_coverage_history(days=30)
            
            for record in history:
                if record.get("commit_hash") == base_sha[:7]:  # Match short SHA
                    # Reconstruct CoverageMetrics from database record
                    return CoverageMetrics(
                        timestamp=record["timestamp"],
                        total_lines=record["total_lines"],
                        covered_lines=record["covered_lines"],
                        line_coverage=record["line_coverage"],
                        branch_coverage=record.get("branch_coverage"),
                        function_coverage=record.get("function_coverage"),
                        critical_coverage=record["critical_coverage"],
                        uncovered_lines=json.loads(record.get("uncovered_lines", "[]")),
                        critical_uncovered_lines=[],  # Not stored in DB
                        files_coverage=json.loads(record.get("files_coverage", "{}")),
                        test_duration=record.get("test_duration", 0.0),
                        status=CoverageStatus(record["status"])
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting base branch coverage: {e}")
            return None
    
    def _calculate_coverage_diff(self, current: CoverageMetrics, base: CoverageMetrics) -> CoverageDiff:
        """Calculate coverage difference between current and base."""
        coverage_diff = current.line_coverage - base.line_coverage
        
        if abs(coverage_diff) < 0.1:
            trend = "unchanged"
        elif coverage_diff > 0:
            trend = "improved"
        else:
            trend = "declined"
        
        # Calculate per-file differences
        files_changed = {}
        critical_files_affected = []
        
        for file_path in set(current.files_coverage.keys()) | set(base.files_coverage.keys()):
            current_cov = current.files_coverage.get(file_path, 0.0)
            base_cov = base.files_coverage.get(file_path, 0.0)
            
            if abs(current_cov - base_cov) > 0.1:  # Significant change
                files_changed[file_path] = (base_cov, current_cov)
                
                # Check if this is a critical file (using simple heuristics)
                if any(pattern in file_path.lower() for pattern in 
                      ["auth", "login", "jwt", "trading", "order", "middleware", "security"]):
                    critical_files_affected.append(file_path)
        
        return CoverageDiff(
            current_coverage=current.line_coverage,
            base_coverage=base.line_coverage,
            coverage_diff=coverage_diff,
            trend=trend,
            files_changed=files_changed,
            critical_files_affected=critical_files_affected
        )
    
    def _generate_coverage_comment(self, metrics: CoverageMetrics, 
                                 diff: Optional[CoverageDiff] = None) -> str:
        """Generate comprehensive coverage comment for PR."""
        
        # Status emoji
        if metrics.status == CoverageStatus.PASSED:
            status_emoji = "✅"
        elif metrics.status == CoverageStatus.FAILED_CRITICAL:
            status_emoji = "🚨"
        elif metrics.status == CoverageStatus.FAILED_THRESHOLD:
            status_emoji = "⚠️"
        else:
            status_emoji = "❌"
        
        # Trend emoji
        trend_emoji = ""
        if diff:
            if diff.trend == "improved":
                trend_emoji = "📈"
            elif diff.trend == "declined":
                trend_emoji = "📉"
            else:
                trend_emoji = "➡️"
        
        comment = f"""## {status_emoji} Test Coverage Report {trend_emoji}

**Overall Status:** `{metrics.status.value.upper()}`  
**Timestamp:** {metrics.timestamp}  
**Test Duration:** {metrics.test_duration:.1f}s

### Coverage Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Line Coverage | {metrics.line_coverage:.2f}% | {'✅' if metrics.line_coverage >= 85 else '❌'} |
| Critical Paths | {metrics.critical_coverage:.2f}% | {'✅' if metrics.critical_coverage >= 95 else '❌'} |
| Total Lines | {metrics.total_lines:,} | - |
| Covered Lines | {metrics.covered_lines:,} | - |
"""

        # Add coverage diff if available
        if diff:
            diff_symbol = "+" if diff.coverage_diff >= 0 else ""
            comment += f"""
### Coverage Changes

| Comparison | Current | Base | Diff |
|------------|---------|------|------|
| Line Coverage | {diff.current_coverage:.2f}% | {diff.base_coverage:.2f}% | {diff_symbol}{diff.coverage_diff:.2f}% |

**Trend:** {diff.trend.title()} {trend_emoji}
"""

            # Add file-level changes if any
            if diff.files_changed:
                comment += "\n### Files with Coverage Changes\n\n"
                for file_path, (old_cov, new_cov) in list(diff.files_changed.items())[:10]:
                    change = new_cov - old_cov
                    change_symbol = "+" if change >= 0 else ""
                    change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    comment += f"- `{file_path}`: {old_cov:.1f}% → {new_cov:.1f}% ({change_symbol}{change:.1f}%) {change_emoji}\n"
                
                if len(diff.files_changed) > 10:
                    comment += f"\n*... and {len(diff.files_changed) - 10} more files*\n"
        
        # Add critical issues if any
        if metrics.critical_uncovered_lines:
            comment += f"""
### 🚨 Critical Uncovered Lines

The following critical code paths are not covered by tests:

"""
            for line in metrics.critical_uncovered_lines[:5]:
                comment += f"- {line}\n"
            
            if len(metrics.critical_uncovered_lines) > 5:
                comment += f"\n*... and {len(metrics.critical_uncovered_lines) - 5} more critical lines*"
        
        # Add links to detailed reports
        comment += f"""

### Detailed Reports

- 📊 [HTML Coverage Report](./htmlcov/index.html)
- 📈 [Coverage Summary](./test-reports/coverage_summary.html)
- 📋 [Uncovered Code Analysis](./test-reports/uncovered_code.txt)

---
*This comment is automatically generated by the comprehensive test suite. Report ID: `{metrics.timestamp}`*
"""
        
        return comment
    
    def _generate_status_check_output(self, metrics: CoverageMetrics) -> Dict[str, Any]:
        """Generate output for GitHub status check."""
        summary = f"Line coverage: {metrics.line_coverage:.2f}%, Critical paths: {metrics.critical_coverage:.2f}%"
        
        if metrics.status == CoverageStatus.PASSED:
            title = "✅ All tests passed with adequate coverage"
        elif metrics.status == CoverageStatus.FAILED_CRITICAL:
            title = "🚨 Critical paths have insufficient coverage"
        elif metrics.status == CoverageStatus.FAILED_THRESHOLD:
            title = "⚠️ Coverage below minimum threshold"
        else:
            title = "❌ Test execution failed"
        
        text = f"""
**Coverage Status:** {metrics.status.value.upper()}
**Line Coverage:** {metrics.line_coverage:.2f}%
**Critical Coverage:** {metrics.critical_coverage:.2f}%
**Test Duration:** {metrics.test_duration:.1f}s

**Coverage Details:**
- Total lines: {metrics.total_lines:,}
- Covered lines: {metrics.covered_lines:,}
"""

        if metrics.critical_uncovered_lines:
            text += f"\n**Critical Issues:** {len(metrics.critical_uncovered_lines)} critical lines uncovered"

        return {
            "title": title,
            "summary": summary,
            "text": text
        }
    
    async def _find_existing_coverage_comment(self, pr_number: int) -> Optional[int]:
        """Find existing coverage comment on PR."""
        try:
            url = f"{self.api_base}/repos/{self.repo}/issues/{pr_number}/comments"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    comments = await response.json()
                    
                    for comment in comments:
                        body = comment.get("body", "")
                        if "Test Coverage Report" in body and "automatically generated" in body:
                            return comment["id"]
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding existing coverage comment: {e}")
            return None
    
    async def _create_pr_comment(self, pr_number: int, body: str) -> bool:
        """Create new PR comment."""
        try:
            url = f"{self.api_base}/repos/{self.repo}/issues/{pr_number}/comments"
            data = {"body": body}
            
            async with self.session.post(url, json=data) as response:
                return response.status == 201
                
        except Exception as e:
            logger.error(f"Error creating PR comment: {e}")
            return False
    
    async def _update_pr_comment(self, comment_id: int, body: str) -> bool:
        """Update existing PR comment."""
        try:
            url = f"{self.api_base}/repos/{self.repo}/issues/comments/{comment_id}"
            data = {"body": body}
            
            async with self.session.patch(url, json=data) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Error updating PR comment: {e}")
            return False
    
    async def _prepare_artifact_content(self, file_path: Path) -> Tuple[bytes, str]:
        """Prepare artifact content for upload (with compression if needed)."""
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Compress if file is larger than 1MB
        if len(content) > 1024 * 1024:
            compressed = gzip.compress(content)
            return compressed, "gzip"
        
        return content, "raw"


async def create_github_integration(github_token: str, repository: str, 
                                  coverage_manager: Optional[CoverageManager] = None) -> GitHubIntegration:
    """Create and initialize GitHub integration.
    
    Args:
        github_token: GitHub API token
        repository: Repository in format "owner/repo"  
        coverage_manager: Optional existing coverage manager
        
    Returns:
        Initialized GitHubIntegration instance
    """
    config = GitHubConfig(token=github_token, repository=repository)
    integration = GitHubIntegration(config, coverage_manager)
    await integration._ensure_session()
    return integration


# CLI interface for testing
async def main():
    """Main function for testing GitHub integration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test GitHub Integration")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--pr", type=int, help="PR number to test")
    parser.add_argument("--sha", help="Commit SHA for status check")
    parser.add_argument("--test-comment", action="store_true", help="Test coverage comment")
    parser.add_argument("--test-status", action="store_true", help="Test status check")
    
    args = parser.parse_args()
    
    async with create_github_integration(args.token, args.repo) as github:
        if args.test_comment and args.pr:
            # Create mock coverage metrics for testing
            from tests.utils.coverage_manager import CoverageMetrics, CoverageStatus
            
            test_metrics = CoverageMetrics(
                timestamp=datetime.now().isoformat(),
                total_lines=1000,
                covered_lines=850,
                line_coverage=85.0,
                branch_coverage=80.0,
                function_coverage=90.0,
                critical_coverage=95.0,
                uncovered_lines=["app/main.py: lines 25, 30", "app/auth.py: lines 45"],
                critical_uncovered_lines=["CRITICAL - app/auth.py: lines 45"],
                files_coverage={"app/main.py": 85.0, "app/auth.py": 90.0},
                test_duration=45.5,
                status=CoverageStatus.PASSED
            )
            
            success = await github.post_coverage_comment(args.pr, test_metrics)
            print(f"Coverage comment test: {'SUCCESS' if success else 'FAILED'}")
        
        if args.test_status and args.sha:
            success = await github.update_status_check(
                args.sha, 
                GitHubCheckStatus.COMPLETED, 
                GitHubCheckConclusion.SUCCESS
            )
            print(f"Status check test: {'SUCCESS' if success else 'FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())