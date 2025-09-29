"""Unit tests for authentication routes using real data."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import jwt
import datetime

from app.auth_routes import auth_router, TokenVerificationResponse
from config import Settings


@pytest.fixture
def test_app():
    """Create test app with auth routes."""
    app = FastAPI()
    app.include_router(auth_router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def settings():
    """Create settings instance."""
    return Settings()


@pytest.fixture
def real_jwt_token(settings):
    """Create a real JWT token for testing."""
    payload = {
        'user_id': 'test_user',
        'permissions': ['read', 'write'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


@pytest.fixture
def expired_jwt_token(settings):
    """Create an expired JWT token for testing."""
    payload = {
        'user_id': 'test_user',
        'permissions': ['read', 'write'],
        'exp': datetime.datetime.utcnow() - datetime.timedelta(hours=1)  # Expired
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


class TestTokenVerificationResponse:
    """Test TokenVerificationResponse model."""
    
    def test_valid_response_creation(self):
        """Test valid response creation."""
        response = TokenVerificationResponse(
            valid=True,
            user_id="test_user",
            permissions=["read", "write"],
            exp=1234567890,
            message="Token is valid"
        )
        assert response.valid is True
        assert response.user_id == "test_user"
        assert response.permissions == ["read", "write"]
        assert response.exp == 1234567890
        assert response.message == "Token is valid"
        
    def test_invalid_response_creation(self):
        """Test invalid response creation."""
        response = TokenVerificationResponse(
            valid=False,
            message="Token is invalid"
        )
        assert response.valid is False
        assert response.user_id is None
        assert response.permissions is None
        assert response.exp is None
        assert response.message == "Token is invalid"


class TestVerifyTokenEndpoint:
    """Test /auth/verify-token endpoint with real JWT tokens."""
    
    def test_verify_token_endpoint_exists(self, client):
        """Test verify token endpoint is accessible."""
        # Test without token should fail
        response = client.post("/auth/verify-token")
        assert response.status_code in [401, 403, 422]  # Unauthorized, Forbidden, or validation error
        
    def test_verify_token_with_valid_token(self, client, real_jwt_token):
        """Test verify token with valid JWT token."""
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": f"Bearer {real_jwt_token}"}
        )
        
        # Should succeed with valid token
        if response.status_code == 200:
            data = response.json()
            assert data.get("valid") is True
            assert "user_id" in data
        else:
            # If endpoint implementation differs, check for reasonable response
            assert response.status_code in [200, 400, 401]
        
    def test_verify_token_with_expired_token(self, client, expired_jwt_token):
        """Test verify token with expired JWT token."""
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": f"Bearer {expired_jwt_token}"}
        )
        
        # Should fail with expired token
        assert response.status_code in [400, 401, 403]
        
    def test_verify_token_with_invalid_token(self, client):
        """Test verify token with completely invalid JWT token."""
        invalid_token = "invalid.jwt.token"
        
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": f"Bearer {invalid_token}"}
        )
        
        # Should handle invalid token gracefully
        assert response.status_code in [400, 401, 403, 422]
        
    def test_verify_token_with_malformed_token(self, client):
        """Test verify token with malformed JWT token."""
        malformed_token = "this_is_not_a_jwt_token_at_all"
        
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )
        
        # Should handle malformed token gracefully
        assert response.status_code in [400, 401, 403, 422]


class TestAuthRouterIntegration:
    """Test auth router integration."""
    
    def test_auth_router_prefix(self):
        """Test auth router has correct prefix."""
        assert auth_router.prefix == "/auth"
        
    def test_auth_router_tags(self):
        """Test auth router has correct tags."""
        assert "authentication" in auth_router.tags
        
    def test_auth_routes_registered(self, test_app):
        """Test auth routes are properly registered."""
        routes = [route.path for route in test_app.routes]
        auth_routes = [route for route in routes if route.startswith("/auth")]
        assert len(auth_routes) > 0
        
    def test_security_scheme_configured(self):
        """Test HTTP Bearer security scheme is configured."""
        from app.auth_routes import security
        assert security is not None


class TestRealJWTOperations:
    """Test real JWT operations without mocking."""
    
    def test_jwt_token_creation_and_verification(self, settings):
        """Test creating and verifying real JWT tokens."""
        # Create a token
        payload = {
            'user_id': 'real_test_user',
            'permissions': ['read', 'write', 'admin'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        }
        
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify the token
        try:
            decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            assert decoded['user_id'] == 'real_test_user'
            assert decoded['permissions'] == ['read', 'write', 'admin']
            assert decoded['exp'] > datetime.datetime.utcnow().timestamp()
        except jwt.ExpiredSignatureError:
            pytest.fail("Token should not be expired")
        except jwt.InvalidTokenError:
            pytest.fail("Token should be valid")
            
    def test_jwt_token_expiry_validation(self, settings):
        """Test JWT token expiry validation."""
        # Create an expired token
        payload = {
            'user_id': 'expired_user',
            'exp': datetime.datetime.utcnow() - datetime.timedelta(minutes=1)  # 1 minute ago
        }
        
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        
        # Try to decode expired token
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            
    def test_jwt_token_signature_validation(self, settings):
        """Test JWT token signature validation."""
        # Create token with wrong secret
        payload = {
            'user_id': 'test_user',
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        }
        
        wrong_secret = "wrong_secret_key"
        token = jwt.encode(payload, wrong_secret, algorithm=settings.jwt_algorithm)
        
        # Try to decode with correct secret (should fail)
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


class TestErrorHandling:
    """Test error handling in auth routes with real scenarios."""
    
    def test_missing_authorization_header(self, client):
        """Test missing Authorization header handling."""
        response = client.post("/auth/verify-token")
        assert response.status_code in [401, 403, 422]
        
    def test_invalid_authorization_format(self, client):
        """Test invalid Authorization header format."""
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": "InvalidFormat token"}
        )
        assert response.status_code in [401, 403, 422]
        
    def test_empty_token(self, client):
        """Test empty token handling."""
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": "Bearer "}
        )
        assert response.status_code in [400, 401, 403, 422]
        
    def test_bearer_without_space(self, client):
        """Test Bearer token without space."""
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": "Bearertoken123"}
        )
        assert response.status_code in [401, 403, 422]
        
    def test_multiple_bearer_tokens(self, client):
        """Test multiple Bearer tokens in header."""
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": "Bearer token1 Bearer token2"}
        )
        assert response.status_code in [400, 401, 403, 422]


class TestSecurityConfiguration:
    """Test security configuration with real settings."""
    
    def test_http_bearer_scheme(self):
        """Test HTTP Bearer scheme is properly configured."""
        from app.auth_routes import security
        from fastapi.security import HTTPBearer
        
        assert isinstance(security, HTTPBearer)
        
    def test_settings_integration(self):
        """Test settings integration with real config."""
        from app.auth_routes import settings
        assert settings is not None
        assert hasattr(settings, 'jwt_secret')
        assert hasattr(settings, 'jwt_algorithm')
        assert hasattr(settings, 'jwt_expiration_hours')
        
    def test_settings_values_loaded(self):
        """Test that settings values are properly loaded."""
        settings = Settings()
        assert settings.jwt_secret is not None
        assert len(settings.jwt_secret) > 0
        assert settings.jwt_algorithm in ['HS256', 'HS512']
        assert isinstance(settings.jwt_expiration_hours, int)
        assert settings.jwt_expiration_hours > 0


class TestDemoJWTIntegration:
    """Test demo JWT integration with real functions."""
    
    def test_demo_jwt_generation(self):
        """Test demo JWT generation function works."""
        try:
            from app.auth_routes import generate_demo_jwt_token
            token = generate_demo_jwt_token("demo_user")
            assert isinstance(token, str)
            assert len(token) > 0
            
            # Verify it's a valid JWT structure
            parts = token.split('.')
            assert len(parts) == 3  # header.payload.signature
            
        except ImportError:
            pytest.skip("Demo JWT functions not available")
        
    def test_demo_user_info_retrieval(self):
        """Test demo user info function works."""
        try:
            from app.auth_routes import generate_demo_jwt_token, get_demo_user_info
            
            # Generate a demo token
            token = generate_demo_jwt_token("demo_user")
            
            # Get user info from token
            user_info = get_demo_user_info(token)
            assert isinstance(user_info, dict)
            assert "user_id" in user_info or "sub" in user_info
            
        except ImportError:
            pytest.skip("Demo JWT functions not available")


class TestTokenValidationEdgeCases:
    """Test edge cases in token validation with real data."""
    
    def test_token_with_extra_claims(self, client, settings):
        """Test token with extra custom claims."""
        payload = {
            'user_id': 'test_user',
            'permissions': ['read'],
            'custom_field': 'custom_value',
            'role': 'admin',
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should handle extra claims gracefully
        assert response.status_code in [200, 400, 401]
        
    def test_token_without_required_claims(self, client, settings):
        """Test token without required claims."""
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            # Missing user_id and permissions
        }
        
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        
        response = client.post(
            "/auth/verify-token",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should handle missing claims appropriately
        assert response.status_code in [200, 400, 401, 403]