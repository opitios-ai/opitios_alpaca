# Security Architecture - API Security and Data Integrity

## Overview

This document defines the security architecture for the opitios_alpaca service, focusing on protecting real market data, ensuring data integrity, and maintaining secure API access. The security model is designed to prevent data tampering and ensure only authentic market data flows through the system.

## Security Principles

### 1. Data Integrity First
- **Source Authentication**: Verify all data originates from Alpaca APIs
- **Immutable Data**: Never modify data received from external sources
- **Audit Trail**: Log all data access and processing operations
- **Cryptographic Verification**: Validate data integrity where possible

### 2. Zero Trust Architecture
- **Authenticate Everything**: No implicit trust for any component
- **Authorize Explicitly**: Every request requires explicit authorization
- **Audit All Access**: Log all data access attempts
- **Encrypt in Transit**: All communication encrypted

### 3. Defense in Depth
- **Multiple Security Layers**: Layered security controls
- **Fail Securely**: Security failures result in access denial
- **Least Privilege**: Minimum required permissions
- **Secure by Default**: Secure configurations as default

## Authentication and Authorization

### API Key Authentication

```python
class APIKeyAuthenticator:
    """Secure API key authentication for external clients"""
    
    def __init__(self):
        self.key_store = SecureKeyStore()
        self.rate_limiter = RateLimiter()
    
    async def authenticate_request(self, request: Request) -> AuthenticatedUser | None:
        """Authenticate API request using secure key validation"""
        
        # Extract API key from header
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise AuthenticationError("API key required")
        
        # Validate key format (prevent injection attacks)
        if not self._is_valid_key_format(api_key):
            raise AuthenticationError("Invalid API key format")
        
        # Rate limiting check
        client_id = self._hash_api_key(api_key)
        if not await self.rate_limiter.check_rate_limit(client_id):
            raise RateLimitError("Rate limit exceeded")
        
        # Authenticate against secure store
        user = await self.key_store.authenticate_key(api_key)
        if not user:
            await self._log_failed_authentication(api_key, request)
            raise AuthenticationError("Invalid API key")
        
        await self._log_successful_authentication(user.id, request)
        return user
    
    def _is_valid_key_format(self, key: str) -> bool:
        """Validate API key format to prevent injection"""
        import re
        # API keys must be alphanumeric with specific length
        return re.match(r'^[A-Za-z0-9]{32,64}$', key) is not None
    
    def _hash_api_key(self, key: str) -> str:
        """Hash API key for rate limiting (don't store plain keys)"""
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()[:16]
```

### Role-Based Access Control (RBAC)

```python
class RBACAuthorizer:
    """Role-based access control for market data access"""
    
    PERMISSIONS = {
        "read_stock_data": ["admin", "trader", "viewer"],
        "read_options_data": ["admin", "trader", "premium"],
        "read_historical_data": ["admin", "trader"],
        "admin_endpoints": ["admin"],
        "bulk_operations": ["admin", "premium"]
    }
    
    def check_permission(self, user: AuthenticatedUser, permission: str) -> bool:
        """Check if user has required permission"""
        allowed_roles = self.PERMISSIONS.get(permission, [])
        return user.role in allowed_roles
    
    async def authorize_data_access(self, user: AuthenticatedUser, 
                                   data_type: str, symbols: List[str]) -> bool:
        """Authorize access to specific market data"""
        
        # Check base permission for data type
        if not self.check_permission(user, f"read_{data_type}_data"):
            return False
        
        # Check symbol-specific restrictions (if any)
        restricted_symbols = await self._get_restricted_symbols(user.role)
        for symbol in symbols:
            if symbol in restricted_symbols:
                return False
        
        return True
```

### JWT Token Authentication (Optional Enhancement)

```python
class JWTAuthenticator:
    """JWT-based authentication for enhanced security"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    async def create_access_token(self, user: AuthenticatedUser, 
                                 expires_delta: timedelta = None) -> str:
        """Create JWT access token"""
        
        if expires_delta is None:
            expires_delta = timedelta(hours=1)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": user.id,
            "role": user.role,
            "permissions": user.permissions,
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "opitios-alpaca-service"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Log token creation
        await self._log_token_creation(user.id, expire)
        
        return token
    
    async def verify_token(self, token: str) -> AuthenticatedUser:
        """Verify and decode JWT token"""
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Validate token claims
            if payload.get("iss") != "opitios-alpaca-service":
                raise TokenValidationError("Invalid token issuer")
            
            # Check expiration
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise TokenValidationError("Token expired")
            
            # Reconstruct user from payload
            user = AuthenticatedUser(
                id=payload["sub"],
                role=payload["role"],
                permissions=payload["permissions"]
            )
            
            return user
            
        except jwt.InvalidTokenError as e:
            raise TokenValidationError(f"Invalid token: {str(e)}")
```

## Data Integrity and Validation

### Cryptographic Data Verification

```python
class DataIntegrityVerifier:
    """Verify integrity of market data from external sources"""
    
    def __init__(self):
        self.hmac_key = self._get_hmac_key()
    
    async def verify_alpaca_response(self, response_data: Dict, 
                                   signature: str = None) -> bool:
        """Verify Alpaca API response integrity"""
        
        # If Alpaca provides response signatures, verify them
        if signature:
            calculated_signature = self._calculate_response_signature(response_data)
            if not self._compare_signatures(signature, calculated_signature):
                raise DataIntegrityError("Response signature verification failed")
        
        # Validate response structure
        if not self._validate_response_structure(response_data):
            raise DataIntegrityError("Response structure validation failed")
        
        # Validate data consistency
        if not self._validate_data_consistency(response_data):
            raise DataIntegrityError("Data consistency validation failed")
        
        return True
    
    def _calculate_response_signature(self, data: Dict) -> str:
        """Calculate HMAC signature for response data"""
        import hmac
        import hashlib
        import json
        
        # Normalize data for consistent hashing
        normalized_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        signature = hmac.new(
            self.hmac_key.encode(),
            normalized_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _compare_signatures(self, provided: str, calculated: str) -> bool:
        """Securely compare signatures (prevent timing attacks)"""
        import hmac
        return hmac.compare_digest(provided, calculated)
    
    def _validate_response_structure(self, data: Dict) -> bool:
        """Validate response has required structure"""
        required_fields = ["timestamp", "symbol"]
        return all(field in data for field in required_fields)
    
    def _validate_data_consistency(self, data: Dict) -> bool:
        """Validate data internal consistency"""
        # Check bid/ask relationship
        if "bid_price" in data and "ask_price" in data:
            if data["bid_price"] and data["ask_price"]:
                if data["bid_price"] > data["ask_price"]:
                    return False
        
        # Check timestamp freshness
        if "timestamp" in data:
            age = datetime.utcnow() - data["timestamp"]
            if age.total_seconds() > 300:  # 5 minutes
                return False
        
        return True
```

### Input Validation and Sanitization

```python
class InputValidator:
    """Comprehensive input validation for API requests"""
    
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate and sanitize stock symbol"""
        if not symbol:
            raise ValidationError("Symbol cannot be empty")
        
        # Remove whitespace and convert to uppercase
        clean_symbol = symbol.strip().upper()
        
        # Validate format (alphanumeric, 1-10 characters)
        if not re.match(r'^[A-Z0-9]{1,10}$', clean_symbol):
            raise ValidationError("Invalid symbol format")
        
        # Check against known malicious patterns
        if clean_symbol in ['DROP', 'DELETE', 'UPDATE', 'INSERT']:
            raise ValidationError("Invalid symbol")
        
        return clean_symbol
    
    @staticmethod
    def validate_option_symbol(option_symbol: str) -> str:
        """Validate option symbol format"""
        if not option_symbol:
            raise ValidationError("Option symbol cannot be empty")
        
        clean_symbol = option_symbol.strip().upper()
        
        # Validate option symbol pattern
        pattern = r'^[A-Z]{1,6}\d{6}[CP]\d{8}$'
        if not re.match(pattern, clean_symbol):
            raise ValidationError("Invalid option symbol format")
        
        return clean_symbol
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> Tuple[datetime, datetime]:
        """Validate and parse date range"""
        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise ValidationError(f"Invalid date format: {str(e)}")
        
        # Validate date range constraints
        if start >= end:
            raise ValidationError("Start date must be before end date")
        
        # Limit historical data range (prevent abuse)
        max_range = timedelta(days=365)
        if end - start > max_range:
            raise ValidationError("Date range too large (max 365 days)")
        
        # Prevent future dates
        if end > datetime.utcnow():
            raise ValidationError("End date cannot be in the future")
        
        return start, end
```

## Network Security

### HTTPS/TLS Configuration

```python
class TLSConfig:
    """TLS configuration for secure communication"""
    
    @staticmethod
    def get_ssl_context():
        """Create secure SSL context"""
        import ssl
        
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        # Require TLS 1.2 or higher
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Disable weak ciphers
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        # Enable certificate verification
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        return context

# FastAPI HTTPS configuration
app = FastAPI(
    title="Opitios Alpaca Service",
    description="Real market data API with enhanced security",
    version="2.0.0"
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response
```

### Rate Limiting and DDoS Protection

```python
class RateLimiter:
    """Advanced rate limiting with Redis backend"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_limits = {
            "per_minute": 60,
            "per_hour": 1000,
            "per_day": 10000
        }
    
    async def check_rate_limit(self, client_id: str, endpoint: str = None) -> bool:
        """Check if client is within rate limits"""
        
        current_time = int(time.time())
        
        # Create rate limit keys
        keys = {
            "minute": f"rate_limit:{client_id}:minute:{current_time // 60}",
            "hour": f"rate_limit:{client_id}:hour:{current_time // 3600}",
            "day": f"rate_limit:{client_id}:day:{current_time // 86400}"
        }
        
        # Check each time window
        for window, key in keys.items():
            current_count = await self.redis.get(key) or 0
            limit = self._get_limit_for_client(client_id, f"per_{window}")
            
            if int(current_count) >= limit:
                await self._log_rate_limit_exceeded(client_id, window, current_count, limit)
                return False
        
        # Increment counters
        pipe = self.redis.pipeline()
        for window, key in keys.items():
            pipe.incr(key)
            pipe.expire(key, self._get_window_seconds(window))
        await pipe.execute()
        
        return True
    
    def _get_limit_for_client(self, client_id: str, window: str) -> int:
        """Get rate limit for specific client (can be customized per client)"""
        # Could be enhanced to have per-client limits
        return self.default_limits.get(window, 100)
    
    def _get_window_seconds(self, window: str) -> int:
        """Get expiration time for rate limit window"""
        return {
            "minute": 60,
            "hour": 3600, 
            "day": 86400
        }.get(window, 60)
```

## Secrets Management

### Secure Configuration Management

```python
class SecureConfigManager:
    """Secure configuration and secrets management"""
    
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
    
    def _get_encryption_key(self) -> bytes:
        """Get encryption key from secure source"""
        # In production, get from environment or key management service
        key = os.environ.get("ENCRYPTION_KEY")
        if not key:
            raise ConfigurationError("Encryption key not found")
        
        return base64.b64decode(key)
    
    def encrypt_secret(self, secret: str) -> str:
        """Encrypt secret for storage"""
        from cryptography.fernet import Fernet
        
        fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key[:32]))
        encrypted = fernet.encrypt(secret.encode())
        
        return base64.b64encode(encrypted).decode()
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt secret for use"""
        from cryptography.fernet import Fernet
        
        fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key[:32]))
        encrypted_bytes = base64.b64decode(encrypted_secret.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        
        return decrypted.decode()
    
    def get_alpaca_credentials(self) -> Tuple[str, str]:
        """Securely retrieve Alpaca API credentials"""
        encrypted_key = os.environ.get("ALPACA_API_KEY_ENCRYPTED")
        encrypted_secret = os.environ.get("ALPACA_SECRET_KEY_ENCRYPTED")
        
        if not encrypted_key or not encrypted_secret:
            raise ConfigurationError("Alpaca credentials not found")
        
        api_key = self.decrypt_secret(encrypted_key)
        secret_key = self.decrypt_secret(encrypted_secret)
        
        return api_key, secret_key
```

## Audit Logging and Monitoring

### Security Event Logging

```python
class SecurityAuditLogger:
    """Comprehensive security event logging"""
    
    def __init__(self):
        self.logger = self._setup_security_logger()
    
    def _setup_security_logger(self):
        """Setup dedicated security audit logger"""
        security_logger = loguru.logger.bind(audit=True)
        
        # Separate log file for security events
        security_logger.add(
            "logs/security_audit_{time:YYYY-MM-DD}.log",
            rotation="daily",
            retention="90 days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | SECURITY | {level} | {message}",
            serialize=True,
            compression="gz"
        )
        
        return security_logger
    
    async def log_authentication_attempt(self, client_id: str, success: bool, 
                                       ip_address: str, user_agent: str):
        """Log authentication attempts"""
        event = {
            "event_type": "authentication_attempt",
            "client_id": self._hash_client_id(client_id),
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if success:
            self.logger.info("Authentication successful", **event)
        else:
            self.logger.warning("Authentication failed", **event)
    
    async def log_data_access(self, user_id: str, data_type: str, symbols: List[str], 
                            success: bool, ip_address: str):
        """Log market data access attempts"""
        event = {
            "event_type": "data_access",
            "user_id": self._hash_user_id(user_id),
            "data_type": data_type,
            "symbol_count": len(symbols),
            "symbols": symbols[:10],  # Log first 10 symbols only
            "success": success,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info("Data access attempt", **event)
    
    async def log_security_violation(self, violation_type: str, details: Dict, 
                                   client_id: str = None, ip_address: str = None):
        """Log security violations"""
        event = {
            "event_type": "security_violation",
            "violation_type": violation_type,
            "details": details,
            "client_id": self._hash_client_id(client_id) if client_id else None,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.error("Security violation detected", **event)
    
    def _hash_client_id(self, client_id: str) -> str:
        """Hash client ID for privacy in logs"""
        import hashlib
        return hashlib.sha256(client_id.encode()).hexdigest()[:16]
```

## Security Monitoring and Alerts

### Threat Detection

```python
class ThreatDetector:
    """Detect and respond to security threats"""
    
    def __init__(self):
        self.redis = redis.Redis()
        self.alert_thresholds = {
            "failed_auth_per_ip": 10,
            "failed_auth_per_minute": 50,
            "unusual_data_access": 100,
            "invalid_requests_per_ip": 20
        }
    
    async def detect_brute_force_attack(self, ip_address: str) -> bool:
        """Detect potential brute force attacks"""
        current_minute = int(time.time()) // 60
        key = f"failed_auth:{ip_address}:{current_minute}"
        
        failed_attempts = await self.redis.incr(key)
        await self.redis.expire(key, 60)
        
        if failed_attempts >= self.alert_thresholds["failed_auth_per_ip"]:
            await self._trigger_security_alert(
                "brute_force_attack",
                {"ip_address": ip_address, "attempts": failed_attempts}
            )
            return True
        
        return False
    
    async def detect_unusual_data_access(self, user_id: str, request_count: int) -> bool:
        """Detect unusual data access patterns"""
        if request_count >= self.alert_thresholds["unusual_data_access"]:
            await self._trigger_security_alert(
                "unusual_data_access",
                {"user_id": user_id, "request_count": request_count}
            )
            return True
        
        return False
    
    async def _trigger_security_alert(self, alert_type: str, details: Dict):
        """Trigger security alert"""
        alert = {
            "alert_type": alert_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "high"
        }
        
        # Log the alert
        logger.error(f"Security alert: {alert_type}", **alert)
        
        # Could integrate with external alerting systems
        # await self.send_alert_to_slack(alert)
        # await self.send_alert_to_pagerduty(alert)
```

This comprehensive security architecture ensures the integrity of real market data while protecting against various security threats and maintaining audit trails for compliance and monitoring purposes.