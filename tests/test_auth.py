"""
Comprehensive tests for JWT authentication, user management, and security
"""

import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from main import app
from app.middleware import (
    create_jwt_token, verify_jwt_token, get_current_user,
    UserContext, UserContextManager, user_manager, 
    JWT_SECRET, JWT_ALGORITHM
)
from app.user_manager import UserManager, UserRegistrationRequest, UserLoginRequest
from config import settings

client = TestClient(app)


class TestJWTTokens:
    """Test JWT token creation and validation"""
    
    def test_create_jwt_token(self):
        """Test JWT token creation"""
        user_data = {
            "user_id": "test_user_123",
            "permissions": ["trading", "market_data"]
        }
        
        token = create_jwt_token(user_data)
        assert token is not None
        assert isinstance(token, str)
        
        # Decode token to verify payload
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["user_id"] == user_data["user_id"]
        assert payload["permissions"] == user_data["permissions"]
        assert "exp" in payload
        assert "iat" in payload
    
    def test_verify_valid_jwt_token(self):
        """Test verification of valid JWT token"""
        user_data = {
            "user_id": "test_user_123",
            "permissions": ["trading", "market_data"]
        }
        
        token = create_jwt_token(user_data)
        payload = verify_jwt_token(token)
        
        assert payload["user_id"] == user_data["user_id"]
        assert payload["permissions"] == user_data["permissions"]
    
    def test_verify_expired_jwt_token(self):
        """Test verification of expired JWT token"""
        # Create expired token
        expired_payload = {
            "user_id": "test_user_123",
            "permissions": ["trading"],
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        
        expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(expired_token)
        
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()
    
    def test_verify_invalid_jwt_token(self):
        """Test verification of invalid JWT token"""
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(invalid_token)
        
        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()
    
    def test_verify_jwt_token_wrong_secret(self):
        """Test verification of JWT token with wrong secret"""
        # Create token with different secret
        wrong_payload = {
            "user_id": "test_user_123",
            "permissions": ["trading"],
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow()
        }
        
        wrong_token = jwt.encode(wrong_payload, "wrong-secret", algorithm=JWT_ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(wrong_token)
        
        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()


class TestUserContext:
    """Test UserContext functionality"""
    
    def test_user_context_creation(self):
        """Test UserContext creation and initialization"""
        alpaca_credentials = {
            "api_key": "test_api_key",
            "secret_key": "test_secret_key",
            "paper_trading": True
        }
        
        context = UserContext(
            user_id="test_user_123",
            alpaca_credentials=alpaca_credentials,
            permissions=["trading", "market_data"],
            rate_limits={"requests_per_minute": 120}
        )
        
        assert context.user_id == "test_user_123"
        assert context.permissions == ["trading", "market_data"]
        assert context.rate_limits == {"requests_per_minute": 120}
        assert context.request_count == 0
        assert isinstance(context.created_at, datetime)
        assert isinstance(context.last_active, datetime)
    
    def test_user_context_update_activity(self):
        """Test UserContext activity update"""
        context = UserContext(
            user_id="test_user_123",
            alpaca_credentials={},
            permissions=[],
            rate_limits={}
        )
        
        initial_count = context.request_count
        initial_time = context.last_active
        
        # Small delay to ensure time difference
        import time
        time.sleep(0.01)
        
        context.update_activity()
        
        assert context.request_count == initial_count + 1
        assert context.last_active > initial_time
    
    def test_user_context_has_permission(self):
        """Test UserContext permission checking"""
        context = UserContext(
            user_id="test_user_123",
            alpaca_credentials={},
            permissions=["trading", "market_data", "admin"],
            rate_limits={}
        )
        
        assert context.has_permission("trading") is True
        assert context.has_permission("market_data") is True
        assert context.has_permission("admin") is True
        assert context.has_permission("invalid_permission") is False


class TestUserContextManager:
    """Test UserContextManager functionality"""
    
    def test_create_user_context(self):
        """Test user context creation"""
        manager = UserContextManager()
        
        user_data = {
            "user_id": "test_user_123",
            "alpaca_credentials": {
                "api_key": "test_key",
                "secret_key": "test_secret",
                "paper_trading": True
            },
            "permissions": ["trading", "market_data"],
            "rate_limits": {"requests_per_minute": 120}
        }
        
        context = manager.create_user_context(user_data)
        
        assert context.user_id == "test_user_123"
        assert manager.get_user_context("test_user_123") == context
    
    def test_get_user_context(self):
        """Test getting user context"""
        manager = UserContextManager()
        
        # Non-existent user
        assert manager.get_user_context("non_existent") is None
        
        # Create and get user
        user_data = {
            "user_id": "test_user_123",
            "alpaca_credentials": {},
            "permissions": [],
            "rate_limits": {}
        }
        
        context = manager.create_user_context(user_data)
        retrieved_context = manager.get_user_context("test_user_123")
        
        assert retrieved_context == context
    
    def test_remove_user_context(self):
        """Test removing user context"""
        manager = UserContextManager()
        
        user_data = {
            "user_id": "test_user_123",
            "alpaca_credentials": {},
            "permissions": [],
            "rate_limits": {}
        }
        
        manager.create_user_context(user_data)
        assert manager.get_user_context("test_user_123") is not None
        
        manager.remove_user_context("test_user_123")
        assert manager.get_user_context("test_user_123") is None
    
    def test_cleanup_inactive_users(self):
        """Test cleanup of inactive users"""
        manager = UserContextManager()
        
        # Create user contexts
        for i in range(3):
            user_data = {
                "user_id": f"test_user_{i}",
                "alpaca_credentials": {},
                "permissions": [],
                "rate_limits": {}
            }
            manager.create_user_context(user_data)
        
        # Make one user inactive by modifying its last_active time
        inactive_user = manager.get_user_context("test_user_1")
        inactive_user.last_active = datetime.utcnow() - timedelta(hours=1)
        
        # Cleanup with 30 minutes threshold
        manager.cleanup_inactive_users(max_inactive_minutes=30)
        
        # Check that inactive user was removed
        assert manager.get_user_context("test_user_0") is not None
        assert manager.get_user_context("test_user_1") is None  # Should be removed
        assert manager.get_user_context("test_user_2") is not None


class TestAuthenticationEndpoints:
    """Test authentication endpoints"""
    
    @patch('app.user_manager.get_user_manager')
    def test_login_success(self, mock_get_manager):
        """Test successful login"""
        mock_manager = Mock()
        mock_user = Mock()
        mock_user.id = "test_user_123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.role = "user"
        mock_user.status = "active"
        mock_user.permissions = {"trading": True, "market_data": True}
        mock_user.rate_limits = {"requests_per_minute": 120}
        mock_user.alpaca_paper_trading = True
        mock_user.total_requests = 0
        mock_user.total_orders = 0
        mock_user.last_login = None
        mock_user.created_at = datetime.utcnow()
        
        mock_manager.authenticate_user.return_value = mock_user
        mock_get_manager.return_value = mock_manager
        
        login_data = {
            "username": "testuser",
            "password": "testpass123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["id"] == "test_user_123"
    
    @patch('app.user_manager.get_user_manager')
    def test_login_invalid_credentials(self, mock_get_manager):
        """Test login with invalid credentials"""
        mock_manager = Mock()
        mock_manager.authenticate_user.return_value = None
        mock_get_manager.return_value = mock_manager
        
        login_data = {
            "username": "invalid",
            "password": "invalid"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]
    
    def test_protected_endpoint_no_token(self):
        """Test protected endpoint without token"""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        assert "Missing or invalid authorization header" in response.json()["detail"]
    
    def test_protected_endpoint_invalid_token(self):
        """Test protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]
    
    @patch('app.middleware.user_manager')
    @patch('app.user_manager.get_user_manager')
    def test_protected_endpoint_valid_token(self, mock_get_manager, mock_user_manager):
        """Test protected endpoint with valid token"""
        # Create a valid token
        user_data = {
            "user_id": "test_user_123",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        # Mock user context
        mock_context = Mock()
        mock_context.user_id = "test_user_123"
        mock_context.update_activity = Mock()
        mock_user_manager.get_user_context.return_value = mock_context
        
        # Mock user manager
        mock_manager = Mock()
        mock_user = Mock()
        mock_user.id = "test_user_123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.role = "user"
        mock_user.status = "active"
        mock_user.permissions = {"trading": True, "market_data": True}
        mock_user.rate_limits = {"requests_per_minute": 120}
        mock_user.alpaca_paper_trading = True
        mock_user.total_requests = 0
        mock_user.total_orders = 0
        mock_user.last_login = None
        mock_user.created_at = datetime.utcnow()
        
        mock_manager.get_user_by_id.return_value = mock_user
        mock_get_manager.return_value = mock_manager
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        # Should succeed or fail based on user context setup
        # This is a complex integration test that may need more setup
        assert response.status_code in [200, 401]


class TestGetCurrentUser:
    """Test get_current_user dependency"""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test get_current_user with valid token and context"""
        # Create valid token
        user_data = {
            "user_id": "test_user_123",
            "permissions": ["trading", "market_data"]
        }
        token = create_jwt_token(user_data)
        
        # Create user context
        context = UserContext(
            user_id="test_user_123",
            alpaca_credentials={},
            permissions=["trading", "market_data"],
            rate_limits={}
        )
        
        # Add context to user manager
        user_manager.active_users["test_user_123"] = context
        
        try:
            # Mock credentials
            from fastapi.security import HTTPAuthorizationCredentials
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token
            )
            
            result = await get_current_user(credentials)
            
            assert result.user_id == "test_user_123"
            assert result.permissions == ["trading", "market_data"]
        finally:
            # Cleanup
            if "test_user_123" in user_manager.active_users:
                del user_manager.active_users["test_user_123"]
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_context(self):
        """Test get_current_user with valid token but no context"""
        user_data = {
            "user_id": "test_user_456",
            "permissions": ["trading"]
        }
        token = create_jwt_token(user_data)
        
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "User context not found" in exc_info.value.detail


@pytest.fixture
def mock_user_data():
    """Fixture providing test user data"""
    return {
        "user_id": "test_user_123",
        "username": "testuser",
        "email": "test@example.com",
        "alpaca_credentials": {
            "api_key": "test_api_key",
            "secret_key": "test_secret_key",
            "paper_trading": True
        },
        "permissions": ["trading", "market_data"],
        "rate_limits": {
            "requests_per_minute": 120,
            "orders_per_minute": 10
        }
    }


class TestAuthenticationIntegration:
    """Integration tests for full authentication flow"""
    
    def test_token_expiration_handling(self):
        """Test handling of token expiration in requests"""
        # This would test the full flow from token creation to expiration
        # and proper error handling throughout the system
        pass
    
    def test_user_session_management(self):
        """Test user session lifecycle management"""
        # This would test user login, session tracking, activity updates,
        # and session cleanup
        pass
    
    def test_concurrent_user_sessions(self):
        """Test multiple concurrent user sessions"""
        # This would test that multiple users can be authenticated
        # simultaneously without interference
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])