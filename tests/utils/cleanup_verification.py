"""Cleanup verification system for ensuring all test data is properly cleaned up."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from .real_api_client import RealAPITestClient
from .test_data_manager import TestDataManager, CleanupStatus, TestSession


logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """Status of verification checks."""
    VERIFIED = "verified"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class VerificationType(Enum):
    """Types of verification checks."""
    ORDERS_CLEANUP = "orders_cleanup"
    POSITIONS_CLEANUP = "positions_cleanup"
    CONNECTIONS_CLOSED = "connections_closed"
    DATA_ISOLATION = "data_isolation"
    ACCOUNT_STATE = "account_state"
    RATE_LIMITS = "rate_limits"
    CUSTOM = "custom"


@dataclass
class VerificationCheck:
    """Represents a single verification check."""
    check_id: str
    verification_type: VerificationType
    account_id: str
    description: str
    check_function: callable
    priority: int = 0
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class VerificationResult:
    """Result of a verification check."""
    check_id: str
    verification_type: VerificationType
    account_id: str
    status: VerificationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[Exception] = None


@dataclass
class VerificationReport:
    """Comprehensive verification report."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_checks: int
    verified_checks: int
    failed_checks: int
    warning_checks: int
    skipped_checks: int
    success_rate: float
    results: List[VerificationResult]
    summary: Dict[str, Any] = field(default_factory=dict)


class CleanupVerificationSystem:
    """
    Verification system that ensures all test data is properly cleaned up.
    
    This system provides:
    - Comprehensive verification of cleanup operations
    - Account state validation
    - Data isolation verification
    - Detailed reporting with metrics
    - Graceful handling of verification failures
    """
    
    def __init__(self):
        """Initialize CleanupVerificationSystem."""
        self.verification_checks: List[VerificationCheck] = []
        self.verification_results: List[VerificationResult] = []
        self.custom_validators: Dict[str, callable] = {}
        
        logger.info("Initialized CleanupVerificationSystem")
    
    def register_verification_check(self, check: VerificationCheck) -> None:
        """
        Register a verification check.
        
        Args:
            check: VerificationCheck to register
        """
        self.verification_checks.append(check)
        logger.debug(f"Registered verification check: {check.check_id}")
    
    def register_custom_validator(self, validator_name: str, validator_function: callable) -> None:
        """
        Register a custom validator function.
        
        Args:
            validator_name: Name of the validator
            validator_function: Callable that performs validation
        """
        self.custom_validators[validator_name] = validator_function
        logger.debug(f"Registered custom validator: {validator_name}")
    
    async def _execute_verification_check(self, check: VerificationCheck, 
                                        client: RealAPITestClient) -> VerificationResult:
        """
        Execute a single verification check.
        
        Args:
            check: Verification check to execute
            client: RealAPITestClient instance
            
        Returns:
            VerificationResult
        """
        start_time = datetime.now()
        result = VerificationResult(
            check_id=check.check_id,
            verification_type=check.verification_type,
            account_id=check.account_id,
            status=VerificationStatus.SKIPPED,
            message=f"Executing verification: {check.description}"
        )
        
        for attempt in range(check.retry_count + 1):
            try:
                # Execute verification with timeout
                verification_result = await asyncio.wait_for(
                    self._run_check_function(check, client),
                    timeout=check.timeout
                )
                
                if verification_result is True:
                    result.status = VerificationStatus.VERIFIED
                    result.message = f"Verification passed: {check.description}"
                elif verification_result is False:
                    result.status = VerificationStatus.FAILED
                    result.message = f"Verification failed: {check.description}"
                elif isinstance(verification_result, dict):
                    result.details = verification_result
                    result.status = verification_result.get("status", VerificationStatus.FAILED)
                    result.message = verification_result.get("message", result.message)
                else:
                    result.status = VerificationStatus.WARNING
                    result.message = f"Unexpected verification result: {verification_result}"
                
                break  # Success, exit retry loop
                
            except asyncio.TimeoutError:
                result.error = TimeoutError(f"Verification timed out after {check.timeout}s")
                if attempt < check.retry_count:
                    logger.warning(f"Verification {check.check_id} timed out, retrying ({attempt + 1}/{check.retry_count})")
                    await asyncio.sleep(check.retry_delay * (attempt + 1))
                else:
                    result.status = VerificationStatus.FAILED
                    result.message = f"Verification timed out after {check.retry_count} retries"
                    
            except Exception as e:
                result.error = e
                result.retry_count = attempt
                
                if attempt < check.retry_count:
                    logger.warning(f"Verification {check.check_id} failed, retrying ({attempt + 1}/{check.retry_count}): {e}")
                    await asyncio.sleep(check.retry_delay * (attempt + 1))
                else:
                    result.status = VerificationStatus.FAILED
                    result.message = f"Verification failed after {check.retry_count} retries: {str(e)}"
        
        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result
    
    async def _run_check_function(self, check: VerificationCheck, client: RealAPITestClient) -> Any:
        """Run the check function with proper error handling."""
        if asyncio.iscoroutinefunction(check.check_function):
            return await check.check_function(client)
        else:
            return check.check_function(client)
    
    async def verify_orders_cleanup(self, client: RealAPITestClient) -> Dict[str, Any]:
        """
        Verify that all test orders have been properly cleaned up.
        
        Args:
            client: RealAPITestClient instance
            
        Returns:
            Verification result dictionary
        """
        try:
            # Get current orders
            orders = await client.get_orders(status="open")
            
            # Filter for test orders (orders with our test prefix)
            test_orders = [
                order for order in orders
                if order.get("client_order_id", "").startswith(client.test_prefix)
            ]
            
            if not test_orders:
                return {
                    "status": VerificationStatus.VERIFIED,
                    "message": "No test orders found - cleanup successful",
                    "order_count": 0,
                    "orders": []
                }
            else:
                return {
                    "status": VerificationStatus.FAILED,
                    "message": f"Found {len(test_orders)} uncleaned test orders",
                    "order_count": len(test_orders),
                    "orders": [order.get("id") for order in test_orders]
                }
                
        except Exception as e:
            return {
                "status": VerificationStatus.FAILED,
                "message": f"Error verifying orders cleanup: {str(e)}",
                "error": str(e)
            }
    
    async def verify_positions_cleanup(self, client: RealAPITestClient) -> Dict[str, Any]:
        """
        Verify that test positions have been properly cleaned up.
        
        Args:
            client: RealAPITestClient instance
            
        Returns:
            Verification result dictionary
        """
        try:
            # Get current positions
            positions = await client.get_positions()
            
            # Check if any positions are for symbols we used in tests
            test_positions = [
                pos for pos in positions
                if pos.get("symbol") in client.test_symbols
            ]
            
            if not test_positions:
                return {
                    "status": VerificationStatus.VERIFIED,
                    "message": "No test positions found - cleanup successful",
                    "position_count": 0,
                    "positions": []
                }
            else:
                return {
                    "status": VerificationStatus.WARNING,
                    "message": f"Found {len(test_positions)} positions in test symbols",
                    "position_count": len(test_positions),
                    "positions": [pos.get("symbol") for pos in test_positions]
                }
                
        except Exception as e:
            return {
                "status": VerificationStatus.FAILED,
                "message": f"Error verifying positions cleanup: {str(e)}",
                "error": str(e)
            }
    
    async def verify_account_state(self, client: RealAPITestClient) -> Dict[str, Any]:
        """
        Verify account state is consistent after cleanup.
        
        Args:
            client: RealAPITestClient instance
            
        Returns:
            Verification result dictionary
        """
        try:
            # Get account information
            account_info = await client.get_account()
            
            if "error" in account_info:
                return {
                    "status": VerificationStatus.FAILED,
                    "message": f"Error getting account info: {account_info['error']}",
                    "account_info": account_info
                }
            
            # Check account status
            account_status = account_info.get("status", "unknown")
            if account_status != "ACTIVE":
                return {
                    "status": VerificationStatus.WARNING,
                    "message": f"Account status is {account_status}, expected ACTIVE",
                    "account_status": account_status
                }
            
            return {
                "status": VerificationStatus.VERIFIED,
                "message": "Account state is consistent",
                "account_status": account_status,
                "account_id": account_info.get("id")
            }
            
        except Exception as e:
            return {
                "status": VerificationStatus.FAILED,
                "message": f"Error verifying account state: {str(e)}",
                "error": str(e)
            }
    
    async def verify_data_isolation(self, account_id: str, test_session: TestSession) -> Dict[str, Any]:
        """
        Verify that test data was properly isolated and didn't affect other tests.
        
        Args:
            account_id: Account ID to verify
            test_session: Test session information
            
        Returns:
            Verification result dictionary
        """
        try:
            # Check if test session data is properly isolated
            session_data = test_session.test_data
            
            isolation_issues = []
            
            # Verify each type of test data
            for data_key, data_list in session_data.items():
                if account_id not in data_key:
                    continue
                    
                # Check for potential data leakage
                for item in data_list:
                    if not str(item.get("data", "")).startswith(test_session.test_prefix):
                        isolation_issues.append({
                            "data_key": data_key,
                            "issue": "Data item doesn't have test prefix",
                            "item": item
                        })
            
            if not isolation_issues:
                return {
                    "status": VerificationStatus.VERIFIED,
                    "message": "Test data isolation verified",
                    "data_items_checked": sum(len(data) for data in session_data.values())
                }
            else:
                return {
                    "status": VerificationStatus.WARNING,
                    "message": f"Found {len(isolation_issues)} data isolation issues",
                    "isolation_issues": isolation_issues
                }
                
        except Exception as e:
            return {
                "status": VerificationStatus.FAILED,
                "message": f"Error verifying data isolation: {str(e)}",
                "error": str(e)
            }
    
    def create_standard_verification_checks(self, account_id: str) -> List[VerificationCheck]:
        """
        Create standard verification checks for an account.
        
        Args:
            account_id: Account ID to create checks for
            
        Returns:
            List of verification checks
        """
        checks = []
        
        # Orders cleanup verification
        checks.append(VerificationCheck(
            check_id=f"orders_cleanup_{account_id}",
            verification_type=VerificationType.ORDERS_CLEANUP,
            account_id=account_id,
            description="Verify all test orders are cleaned up",
            check_function=self.verify_orders_cleanup,
            priority=10,
            timeout=30.0
        ))
        
        # Positions cleanup verification
        checks.append(VerificationCheck(
            check_id=f"positions_cleanup_{account_id}",
            verification_type=VerificationType.POSITIONS_CLEANUP,
            account_id=account_id,
            description="Verify test positions are cleaned up",
            check_function=self.verify_positions_cleanup,
            priority=8,
            timeout=30.0
        ))
        
        # Account state verification
        checks.append(VerificationCheck(
            check_id=f"account_state_{account_id}",
            verification_type=VerificationType.ACCOUNT_STATE,
            account_id=account_id,
            description="Verify account state consistency",
            check_function=self.verify_account_state,
            priority=5,
            timeout=20.0
        ))
        
        return checks
    
    async def verify_cleanup(self, test_data_manager: TestDataManager) -> VerificationReport:
        """
        Perform comprehensive cleanup verification.
        
        Args:
            test_data_manager: TestDataManager instance
            
        Returns:
            VerificationReport
        """
        start_time = datetime.now()
        
        if not test_data_manager.current_session:
            raise RuntimeError("No active test session in TestDataManager")
        
        session_id = test_data_manager.current_session.session_id
        logger.info(f"Starting cleanup verification for session: {session_id}")
        
        # Create standard checks for all accounts
        all_checks = []
        for account_id in test_data_manager.active_clients:
            standard_checks = self.create_standard_verification_checks(account_id)
            all_checks.extend(standard_checks)
        
        # Add registered custom checks
        all_checks.extend(self.verification_checks)
        
        # Sort checks by priority
        all_checks.sort(key=lambda x: x.priority, reverse=True)
        
        # Execute verification checks
        results = []
        
        for check in all_checks:
            client = test_data_manager.active_clients.get(check.account_id)
            if not client:
                result = VerificationResult(
                    check_id=check.check_id,
                    verification_type=check.verification_type,
                    account_id=check.account_id,
                    status=VerificationStatus.SKIPPED,
                    message=f"No client available for account {check.account_id}"
                )
            else:
                # Special handling for data isolation check
                if check.verification_type == VerificationType.DATA_ISOLATION:
                    result = await self._execute_data_isolation_check(
                        check, test_data_manager.current_session
                    )
                else:
                    result = await self._execute_verification_check(check, client)
            
            results.append(result)
            self.verification_results.append(result)
            
            logger.debug(f"Verification check {check.check_id}: {result.status.value}")
        
        # Create verification report
        end_time = datetime.now()
        total_checks = len(results)
        verified_checks = len([r for r in results if r.status == VerificationStatus.VERIFIED])
        failed_checks = len([r for r in results if r.status == VerificationStatus.FAILED])
        warning_checks = len([r for r in results if r.status == VerificationStatus.WARNING])
        skipped_checks = len([r for r in results if r.status == VerificationStatus.SKIPPED])
        
        success_rate = (verified_checks / total_checks * 100) if total_checks > 0 else 0.0
        
        report = VerificationReport(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            total_checks=total_checks,
            verified_checks=verified_checks,
            failed_checks=failed_checks,
            warning_checks=warning_checks,
            skipped_checks=skipped_checks,
            success_rate=success_rate,
            results=results
        )
        
        # Generate summary
        report.summary = {
            "duration_seconds": (end_time - start_time).total_seconds(),
            "verification_by_type": self._summarize_by_type(results),
            "verification_by_account": self._summarize_by_account(results),
            "critical_failures": [
                r for r in results 
                if r.status == VerificationStatus.FAILED and r.verification_type in [
                    VerificationType.ORDERS_CLEANUP, VerificationType.POSITIONS_CLEANUP
                ]
            ],
            "recommendations": self._generate_recommendations(results)
        }
        
        logger.info(f"Cleanup verification completed: {success_rate:.1f}% success rate "
                   f"({verified_checks}/{total_checks} checks passed)")
        
        return report
    
    async def _execute_data_isolation_check(self, check: VerificationCheck, 
                                          test_session: TestSession) -> VerificationResult:
        """Execute data isolation check."""
        start_time = datetime.now()
        
        try:
            isolation_result = await self.verify_data_isolation(check.account_id, test_session)
            
            result = VerificationResult(
                check_id=check.check_id,
                verification_type=check.verification_type,
                account_id=check.account_id,
                status=isolation_result["status"],
                message=isolation_result["message"],
                details=isolation_result,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            result = VerificationResult(
                check_id=check.check_id,
                verification_type=check.verification_type,
                account_id=check.account_id,
                status=VerificationStatus.FAILED,
                message=f"Data isolation check failed: {str(e)}",
                execution_time=(datetime.now() - start_time).total_seconds(),
                error=e
            )
        
        return result
    
    def _summarize_by_type(self, results: List[VerificationResult]) -> Dict[str, Dict[str, int]]:
        """Summarize verification results by type."""
        summary = {}
        
        for result in results:
            type_name = result.verification_type.value
            if type_name not in summary:
                summary[type_name] = {
                    "total": 0, "verified": 0, "failed": 0, "warning": 0, "skipped": 0
                }
            
            summary[type_name]["total"] += 1
            summary[type_name][result.status.value] += 1
        
        return summary
    
    def _summarize_by_account(self, results: List[VerificationResult]) -> Dict[str, Dict[str, int]]:
        """Summarize verification results by account."""
        summary = {}
        
        for result in results:
            account_id = result.account_id
            if account_id not in summary:
                summary[account_id] = {
                    "total": 0, "verified": 0, "failed": 0, "warning": 0, "skipped": 0
                }
            
            summary[account_id]["total"] += 1
            summary[account_id][result.status.value] += 1
        
        return summary
    
    def _generate_recommendations(self, results: List[VerificationResult]) -> List[str]:
        """Generate recommendations based on verification results."""
        recommendations = []
        
        # Check for critical failures
        critical_failures = [
            r for r in results 
            if r.status == VerificationStatus.FAILED and r.verification_type in [
                VerificationType.ORDERS_CLEANUP, VerificationType.POSITIONS_CLEANUP
            ]
        ]
        
        if critical_failures:
            recommendations.append(
                "Critical failures detected in orders or positions cleanup. "
                "Manual intervention may be required to clean up remaining test data."
            )
        
        # Check for timeout issues
        timeout_failures = [r for r in results if r.error and isinstance(r.error, TimeoutError)]
        if timeout_failures:
            recommendations.append(
                "Some verification checks timed out. Consider increasing timeout values "
                "or checking API response times."
            )
        
        # Check for high warning rate
        warning_rate = len([r for r in results if r.status == VerificationStatus.WARNING]) / len(results)
        if warning_rate > 0.3:
            recommendations.append(
                "High warning rate detected. Review warning messages to identify "
                "potential cleanup improvements."
            )
        
        # Check success rate
        success_rate = len([r for r in results if r.status == VerificationStatus.VERIFIED]) / len(results)
        if success_rate < 0.8:
            recommendations.append(
                "Low verification success rate. Review failed checks and improve "
                "cleanup procedures."
            )
        
        if not recommendations:
            recommendations.append("All verifications completed successfully. No issues detected.")
        
        return recommendations
    
    def export_verification_report(self, report: VerificationReport, 
                                 file_path: Optional[str] = None) -> str:
        """
        Export verification report to JSON file.
        
        Args:
            report: VerificationReport to export
            file_path: Optional file path
            
        Returns:
            File path where report was saved
        """
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"cleanup_verification_{report.session_id}_{timestamp}.json"
        
        report_data = {
            "session_id": report.session_id,
            "start_time": report.start_time.isoformat(),
            "end_time": report.end_time.isoformat() if report.end_time else None,
            "total_checks": report.total_checks,
            "verified_checks": report.verified_checks,
            "failed_checks": report.failed_checks,
            "warning_checks": report.warning_checks,
            "skipped_checks": report.skipped_checks,
            "success_rate": report.success_rate,
            "summary": report.summary,
            "results": [
                {
                    "check_id": r.check_id,
                    "verification_type": r.verification_type.value,
                    "account_id": r.account_id,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "execution_time": r.execution_time,
                    "retry_count": r.retry_count,
                    "timestamp": r.timestamp.isoformat(),
                    "error": str(r.error) if r.error else None
                }
                for r in report.results
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"Exported verification report to: {file_path}")
        return file_path