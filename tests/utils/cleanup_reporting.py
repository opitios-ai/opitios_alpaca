"""Comprehensive cleanup reporting system with detailed logs, metrics, and failure analysis."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import plotly.graph_objs as go
from plotly.offline import plot
import pandas as pd

from .test_data_manager import TestDataManager, CleanupStatus
from .cleanup_verification import CleanupVerificationSystem, VerificationReport
from .real_api_client import RealAPITestClient


logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of cleanup reports."""
    SUMMARY = "summary"
    DETAILED = "detailed"
    ANALYTICS = "analytics"
    TRENDS = "trends"
    COMPARISON = "comparison"


class ReportFormat(Enum):
    """Report output formats."""
    JSON = "json"
    HTML = "html"
    CSV = "csv"
    PDF = "pdf"


@dataclass
class CleanupSummaryMetrics:
    """Summary metrics for cleanup operations."""
    total_sessions: int = 0
    successful_sessions: int = 0
    failed_sessions: int = 0
    total_accounts: int = 0
    total_orders_processed: int = 0
    total_orders_cancelled: int = 0
    total_positions_processed: int = 0
    total_positions_closed: int = 0
    total_api_calls: int = 0
    total_cleanup_time: float = 0.0
    average_cleanup_time: float = 0.0
    success_rate: float = 0.0
    error_count: int = 0


@dataclass
class AccountCleanupReport:
    """Cleanup report for a specific account."""
    account_id: str
    cleanup_results: Dict[str, Any]
    verification_results: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    error_analysis: Optional[Dict[str, Any]] = None
    performance_stats: Optional[Dict[str, Any]] = None
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SessionCleanupReport:
    """Comprehensive cleanup report for a test session."""
    session_id: str
    start_time: datetime
    end_time: datetime
    duration: float
    status: str
    account_reports: List[AccountCleanupReport]
    verification_report: Optional[VerificationReport] = None
    summary_metrics: Optional[CleanupSummaryMetrics] = None
    overall_recommendations: List[str] = field(default_factory=list)


class CleanupReportingSystem:
    """
    Comprehensive cleanup reporting system.
    
    This system provides:
    - Detailed cleanup reports with metrics and analysis
    - Trend analysis across multiple test sessions
    - Performance analytics and recommendations
    - Multiple report formats (JSON, HTML, CSV)
    - Visual dashboards for cleanup performance
    """
    
    def __init__(self, reports_dir: Optional[Path] = None):
        """
        Initialize CleanupReportingSystem.
        
        Args:
            reports_dir: Directory to store reports (defaults to test-reports)
        """
        self.reports_dir = reports_dir or Path("test-reports")
        self.reports_dir.mkdir(exist_ok=True)
        
        # Historical data storage
        self.session_history: List[SessionCleanupReport] = []
        self.account_history: Dict[str, List[AccountCleanupReport]] = {}
        
        logger.info(f"Initialized CleanupReportingSystem with reports directory: {self.reports_dir}")
    
    def generate_session_report(self, test_data_manager: TestDataManager,
                              verification_system: Optional[CleanupVerificationSystem] = None) -> SessionCleanupReport:
        """
        Generate comprehensive cleanup report for a test session.
        
        Args:
            test_data_manager: TestDataManager instance
            verification_system: Optional CleanupVerificationSystem instance
            
        Returns:
            SessionCleanupReport
        """
        if not test_data_manager.current_session:
            raise RuntimeError("No active test session in TestDataManager")
        
        session = test_data_manager.current_session
        logger.info(f"Generating cleanup report for session: {session.session_id}")
        
        # Collect account reports
        account_reports = []
        for account_id, client in test_data_manager.active_clients.items():
            account_report = self._generate_account_report(account_id, client)
            account_reports.append(account_report)
            
            # Add to account history
            if account_id not in self.account_history:
                self.account_history[account_id] = []
            self.account_history[account_id].append(account_report)
        
        # Generate summary metrics
        summary_metrics = self._calculate_summary_metrics(account_reports)
        
        # Get verification report if available
        verification_report = None
        if verification_system and hasattr(verification_system, 'verification_results'):
            verification_report = verification_system.verify_cleanup(test_data_manager)
        
        # Create session report
        session_report = SessionCleanupReport(
            session_id=session.session_id,
            start_time=session.start_time,
            end_time=session.end_time or datetime.now(),
            duration=(session.end_time or datetime.now() - session.start_time).total_seconds(),
            status="completed" if session.success else "failed",
            account_reports=account_reports,
            verification_report=verification_report,
            summary_metrics=summary_metrics,
            overall_recommendations=self._generate_session_recommendations(account_reports, summary_metrics)
        )
        
        # Add to session history
        self.session_history.append(session_report)
        
        logger.info(f"Generated cleanup report for session: {session.session_id}")
        return session_report
    
    def _generate_account_report(self, account_id: str, client: RealAPITestClient) -> AccountCleanupReport:
        """Generate cleanup report for a specific account."""
        logger.debug(f"Generating account report for: {account_id}")
        
        # Get cleanup results from client
        cleanup_results = {}
        if hasattr(client, 'cleanup_all_test_data'):
            # This would contain the results from the last cleanup operation
            cleanup_results = {
                "orders_cleanup": {
                    "total_orders": len(client.test_orders),
                    "tracking_enabled": True
                },
                "positions_cleanup": {
                    "total_positions": len(client.test_positions),
                    "tracking_enabled": True
                }
            }
        
        # Get metrics if available
        metrics = None
        if hasattr(client, 'get_cleanup_metrics'):
            try:
                metrics = client.get_cleanup_metrics()
            except Exception as e:
                logger.warning(f"Could not get cleanup metrics for {account_id}: {e}")
        
        # Get error analysis if available
        error_analysis = None
        if hasattr(client, 'get_error_analysis'):
            try:
                error_analysis = client.get_error_analysis()
            except Exception as e:
                logger.warning(f"Could not get error analysis for {account_id}: {e}")
        
        # Get performance stats if available
        performance_stats = None
        if hasattr(client, 'get_api_performance_stats'):
            try:
                performance_stats = client.get_api_performance_stats()
            except Exception as e:
                logger.warning(f"Could not get performance stats for {account_id}: {e}")
        
        # Generate recommendations
        recommendations = self._generate_account_recommendations(metrics, error_analysis, performance_stats)
        
        return AccountCleanupReport(
            account_id=account_id,
            cleanup_results=cleanup_results,
            metrics=metrics,
            error_analysis=error_analysis,
            performance_stats=performance_stats,
            recommendations=recommendations
        )
    
    def _calculate_summary_metrics(self, account_reports: List[AccountCleanupReport]) -> CleanupSummaryMetrics:
        """Calculate summary metrics from account reports."""
        metrics = CleanupSummaryMetrics()
        metrics.total_sessions = 1  # Current session
        metrics.total_accounts = len(account_reports)
        
        for report in account_reports:
            if report.metrics:
                metrics.total_orders_processed += report.metrics.get('total_orders', 0)
                metrics.total_orders_cancelled += report.metrics.get('cancelled_orders', 0)
                metrics.total_positions_processed += report.metrics.get('total_positions', 0)
                metrics.total_positions_closed += report.metrics.get('closed_positions', 0)
                metrics.total_api_calls += report.metrics.get('api_calls_made', 0)
                metrics.total_cleanup_time += report.metrics.get('total_cleanup_time', 0.0)
                metrics.error_count += report.metrics.get('error_count', 0)
        
        # Calculate derived metrics
        if metrics.total_accounts > 0:
            metrics.average_cleanup_time = metrics.total_cleanup_time / metrics.total_accounts
        
        total_operations = metrics.total_orders_processed + metrics.total_positions_processed
        successful_operations = metrics.total_orders_cancelled + metrics.total_positions_closed
        
        if total_operations > 0:
            metrics.success_rate = successful_operations / total_operations * 100
        
        # Determine session success
        if metrics.error_count == 0 and metrics.success_rate > 90:
            metrics.successful_sessions = 1
        else:
            metrics.failed_sessions = 1
        
        return metrics
    
    def _generate_account_recommendations(self, metrics: Optional[Dict[str, Any]],
                                        error_analysis: Optional[Dict[str, Any]],
                                        performance_stats: Optional[Dict[str, Any]]) -> List[str]:
        """Generate recommendations for account cleanup improvements."""
        recommendations = []
        
        if metrics:
            # Order cleanup recommendations
            order_success_rate = metrics.get('order_cleanup_success_rate', 100)
            if order_success_rate < 95:
                recommendations.append(
                    f"Order cleanup success rate is {order_success_rate:.1f}%. "
                    "Consider investigating failed order cancellations."
                )
            
            # Position cleanup recommendations
            position_success_rate = metrics.get('position_cleanup_success_rate', 100)
            if position_success_rate < 90:
                recommendations.append(
                    f"Position cleanup success rate is {position_success_rate:.1f}%. "
                    "Review position closing logic and market hours."
                )
            
            # Rate limiting recommendations
            rate_limit_delays = metrics.get('rate_limit_delays', 0)
            api_calls = metrics.get('api_calls_made', 1)
            if rate_limit_delays / api_calls > 0.1:
                recommendations.append(
                    "High rate limiting detected. Consider increasing delays between API calls."
                )
            
            # Performance recommendations
            cleanup_time = metrics.get('total_cleanup_time', 0)
            if cleanup_time > 60:  # More than 1 minute
                recommendations.append(
                    f"Cleanup took {cleanup_time:.1f} seconds. Consider optimizing cleanup procedures."
                )
        
        if error_analysis:
            total_errors = error_analysis.get('total_errors', 0)
            if total_errors > 0:
                most_common_error = error_analysis.get('most_common_error')
                if most_common_error:
                    recommendations.append(
                        f"Most common error: {most_common_error}. "
                        "Consider implementing specific handling for this error type."
                    )
                
                recent_errors = error_analysis.get('recent_errors_count', 0)
                if recent_errors > 3:
                    recommendations.append(
                        "High number of recent errors detected. Check system stability and API connectivity."
                    )
        
        if performance_stats:
            for method, success_rate in performance_stats.get('success_rates', {}).items():
                if success_rate < 95:
                    recommendations.append(
                        f"Low success rate ({success_rate:.1f}%) for {method} API calls. "
                        "Review error handling and retry logic."
                    )
        
        if not recommendations:
            recommendations.append("Account cleanup performed successfully with no issues detected.")
        
        return recommendations
    
    def _generate_session_recommendations(self, account_reports: List[AccountCleanupReport],
                                        summary_metrics: CleanupSummaryMetrics) -> List[str]:
        """Generate overall recommendations for the session."""
        recommendations = []
        
        # Overall success rate
        if summary_metrics.success_rate < 95:
            recommendations.append(
                f"Overall cleanup success rate is {summary_metrics.success_rate:.1f}%. "
                "Review individual account reports for specific issues."
            )
        
        # Error analysis
        if summary_metrics.error_count > 0:
            recommendations.append(
                f"Session encountered {summary_metrics.error_count} errors. "
                "Check error details in individual account reports."
            )
        
        # Performance analysis
        if summary_metrics.average_cleanup_time > 30:
            recommendations.append(
                f"Average cleanup time is {summary_metrics.average_cleanup_time:.1f} seconds per account. "
                "Consider optimizing cleanup procedures for better performance."
            )
        
        # Account-specific issues
        failed_accounts = [report for report in account_reports if report.metrics and report.metrics.get('error_count', 0) > 0]
        if failed_accounts:
            account_ids = [report.account_id for report in failed_accounts]
            recommendations.append(
                f"Accounts with cleanup issues: {', '.join(account_ids)}. "
                "Review individual account reports for details."
            )
        
        if not recommendations:
            recommendations.append("Session completed successfully with excellent cleanup performance.")
        
        return recommendations
    
    def export_report(self, session_report: SessionCleanupReport, 
                     report_format: ReportFormat = ReportFormat.JSON,
                     file_name: Optional[str] = None) -> str:
        """
        Export session report to specified format.
        
        Args:
            session_report: SessionCleanupReport to export
            report_format: Output format
            file_name: Optional custom file name
            
        Returns:
            Path to exported report file
        """
        if not file_name:
            timestamp = session_report.start_time.strftime("%Y%m%d_%H%M%S")
            file_name = f"cleanup_report_{session_report.session_id}_{timestamp}"
        
        file_path = self.reports_dir / f"{file_name}.{report_format.value}"
        
        if report_format == ReportFormat.JSON:
            self._export_json_report(session_report, file_path)
        elif report_format == ReportFormat.HTML:
            self._export_html_report(session_report, file_path)
        elif report_format == ReportFormat.CSV:
            self._export_csv_report(session_report, file_path)
        else:
            raise ValueError(f"Unsupported report format: {report_format}")
        
        logger.info(f"Exported {report_format.value.upper()} report to: {file_path}")
        return str(file_path)
    
    def _export_json_report(self, session_report: SessionCleanupReport, file_path: Path):
        """Export report as JSON."""
        report_data = {
            "session_id": session_report.session_id,
            "start_time": session_report.start_time.isoformat(),
            "end_time": session_report.end_time.isoformat(),
            "duration_seconds": session_report.duration,
            "status": session_report.status,
            "summary_metrics": {
                "total_accounts": session_report.summary_metrics.total_accounts,
                "total_orders_processed": session_report.summary_metrics.total_orders_processed,
                "total_orders_cancelled": session_report.summary_metrics.total_orders_cancelled,
                "total_positions_processed": session_report.summary_metrics.total_positions_processed,
                "total_positions_closed": session_report.summary_metrics.total_positions_closed,
                "success_rate": session_report.summary_metrics.success_rate,
                "total_cleanup_time": session_report.summary_metrics.total_cleanup_time,
                "average_cleanup_time": session_report.summary_metrics.average_cleanup_time,
                "error_count": session_report.summary_metrics.error_count
            } if session_report.summary_metrics else {},
            "account_reports": [
                {
                    "account_id": report.account_id,
                    "cleanup_results": report.cleanup_results,
                    "metrics": report.metrics,
                    "error_analysis": report.error_analysis,
                    "performance_stats": report.performance_stats,
                    "recommendations": report.recommendations
                }
                for report in session_report.account_reports
            ],
            "verification_report": {
                "total_checks": session_report.verification_report.total_checks,
                "verified_checks": session_report.verification_report.verified_checks,
                "failed_checks": session_report.verification_report.failed_checks,
                "success_rate": session_report.verification_report.success_rate
            } if session_report.verification_report else None,
            "overall_recommendations": session_report.overall_recommendations
        }
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
    
    def _export_html_report(self, session_report: SessionCleanupReport, file_path: Path):
        """Export report as HTML with charts and styling."""
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cleanup Report - {session_report.session_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .metric-card {{ background-color: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; text-align: center; }}
                .success {{ color: #28a745; }}
                .warning {{ color: #ffc107; }}
                .danger {{ color: #dc3545; }}
                .recommendations {{ background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .account-section {{ margin: 30px 0; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Cleanup Report</h1>
                <p><strong>Session ID:</strong> {session_report.session_id}</p>
                <p><strong>Duration:</strong> {session_report.duration:.2f} seconds</p>
                <p><strong>Status:</strong> <span class="{'success' if session_report.status == 'completed' else 'danger'}">{session_report.status}</span></p>
            </div>
        """
        
        if session_report.summary_metrics:
            metrics = session_report.summary_metrics
            html_content += f"""
            <h2>Summary Metrics</h2>
            <div class="metrics">
                <div class="metric-card">
                    <h3>Success Rate</h3>
                    <p class="{'success' if metrics.success_rate > 95 else 'warning' if metrics.success_rate > 80 else 'danger'}">{metrics.success_rate:.1f}%</p>
                </div>
                <div class="metric-card">
                    <h3>Orders Processed</h3>
                    <p>{metrics.total_orders_processed}</p>
                </div>
                <div class="metric-card">
                    <h3>Orders Cancelled</h3>
                    <p>{metrics.total_orders_cancelled}</p>
                </div>
                <div class="metric-card">
                    <h3>Positions Processed</h3>
                    <p>{metrics.total_positions_processed}</p>
                </div>
                <div class="metric-card">
                    <h3>Cleanup Time</h3>
                    <p>{metrics.total_cleanup_time:.2f}s</p>
                </div>
                <div class="metric-card">
                    <h3>Errors</h3>
                    <p class="{'success' if metrics.error_count == 0 else 'danger'}">{metrics.error_count}</p>
                </div>
            </div>
            """
        
        # Add account details
        html_content += "<h2>Account Details</h2>"
        for report in session_report.account_reports:
            html_content += f"""
            <div class="account-section">
                <h3>Account: {report.account_id}</h3>
            """
            
            if report.metrics:
                html_content += f"""
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Order Success Rate</td><td>{report.metrics.get('order_cleanup_success_rate', 0):.1f}%</td></tr>
                    <tr><td>Position Success Rate</td><td>{report.metrics.get('position_cleanup_success_rate', 0):.1f}%</td></tr>
                    <tr><td>API Calls</td><td>{report.metrics.get('api_calls_made', 0)}</td></tr>
                    <tr><td>Rate Limit Delays</td><td>{report.metrics.get('rate_limit_delays', 0)}</td></tr>
                </table>
                """
            
            if report.recommendations:
                html_content += """
                <div class="recommendations">
                    <h4>Recommendations</h4>
                    <ul>
                """
                for rec in report.recommendations:
                    html_content += f"<li>{rec}</li>"
                html_content += "</ul></div>"
            
            html_content += "</div>"
        
        # Add overall recommendations
        if session_report.overall_recommendations:
            html_content += """
            <div class="recommendations">
                <h2>Overall Recommendations</h2>
                <ul>
            """
            for rec in session_report.overall_recommendations:
                html_content += f"<li>{rec}</li>"
            html_content += "</ul></div>"
        
        html_content += "</body></html>"
        
        with open(file_path, 'w') as f:
            f.write(html_content)
    
    def _export_csv_report(self, session_report: SessionCleanupReport, file_path: Path):
        """Export report as CSV for data analysis."""
        data = []
        
        for report in session_report.account_reports:
            row = {
                'session_id': session_report.session_id,
                'account_id': report.account_id,
                'duration': session_report.duration,
                'status': session_report.status,
            }
            
            if report.metrics:
                row.update(report.metrics)
            
            if report.error_analysis:
                row.update({
                    f"error_{k}": v for k, v in report.error_analysis.items()
                    if isinstance(v, (int, float, str))
                })
            
            data.append(row)
        
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)
    
    def generate_trend_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate trend analysis for cleanup performance over time.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Trend analysis data
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_sessions = [
            session for session in self.session_history
            if session.start_time >= cutoff_date
        ]
        
        if not recent_sessions:
            return {"error": "No recent session data available for trend analysis"}
        
        # Calculate trends
        success_rates = [s.summary_metrics.success_rate for s in recent_sessions if s.summary_metrics]
        cleanup_times = [s.summary_metrics.average_cleanup_time for s in recent_sessions if s.summary_metrics]
        error_counts = [s.summary_metrics.error_count for s in recent_sessions if s.summary_metrics]
        
        trends = {
            "period_days": days,
            "total_sessions": len(recent_sessions),
            "success_rate_trend": {
                "average": sum(success_rates) / len(success_rates) if success_rates else 0,
                "min": min(success_rates) if success_rates else 0,
                "max": max(success_rates) if success_rates else 0,
                "improving": len(success_rates) > 1 and success_rates[-1] > success_rates[0]
            },
            "cleanup_time_trend": {
                "average": sum(cleanup_times) / len(cleanup_times) if cleanup_times else 0,
                "min": min(cleanup_times) if cleanup_times else 0,
                "max": max(cleanup_times) if cleanup_times else 0,
                "improving": len(cleanup_times) > 1 and cleanup_times[-1] < cleanup_times[0]
            },
            "error_trend": {
                "average": sum(error_counts) / len(error_counts) if error_counts else 0,
                "total_errors": sum(error_counts),
                "improving": len(error_counts) > 1 and error_counts[-1] < error_counts[0]
            }
        }
        
        return trends
    
    def export_dashboard(self, file_name: Optional[str] = None) -> str:
        """
        Export an interactive dashboard with cleanup performance metrics.
        
        Args:
            file_name: Optional custom file name
            
        Returns:
            Path to dashboard file
        """
        if not file_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"cleanup_dashboard_{timestamp}.html"
        
        file_path = self.reports_dir / file_name
        
        # Create charts using plotly
        figures = []
        
        if self.session_history:
            # Success rate over time
            dates = [s.start_time for s in self.session_history]
            success_rates = [s.summary_metrics.success_rate if s.summary_metrics else 0 for s in self.session_history]
            
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=dates, y=success_rates, mode='lines+markers', name='Success Rate'))
            fig1.update_layout(title='Cleanup Success Rate Over Time', xaxis_title='Date', yaxis_title='Success Rate (%)')
            figures.append(fig1)
            
            # Cleanup time trend
            cleanup_times = [s.summary_metrics.average_cleanup_time if s.summary_metrics else 0 for s in self.session_history]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=dates, y=cleanup_times, mode='lines+markers', name='Cleanup Time'))
            fig2.update_layout(title='Average Cleanup Time Trend', xaxis_title='Date', yaxis_title='Time (seconds)')
            figures.append(fig2)
        
        # Generate HTML dashboard
        dashboard_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cleanup Performance Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .chart-container { margin: 30px 0; }
                .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 30px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Cleanup Performance Dashboard</h1>
                <p>Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            </div>
        """
        
        for i, fig in enumerate(figures):
            dashboard_html += f'<div id="chart{i}" class="chart-container"></div>'
        
        dashboard_html += """
            <script>
        """
        
        for i, fig in enumerate(figures):
            dashboard_html += f"Plotly.newPlot('chart{i}', {fig.to_json()});"
        
        dashboard_html += """
            </script>
        </body>
        </html>
        """
        
        with open(file_path, 'w') as f:
            f.write(dashboard_html)
        
        logger.info(f"Exported cleanup dashboard to: {file_path}")
        return str(file_path)