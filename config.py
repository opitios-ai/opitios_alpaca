import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Alpaca API Configuration
    alpaca_api_key: str = "PKEIKZWFXA4BD1JMJAY3"
    alpaca_secret_key: Optional[str] = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_paper_trading: bool = True
    
    # FastAPI Configuration
    app_name: str = "Opitios Alpaca Trading Service"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8081
    
    # Data Service Configuration
    real_data_only: bool = True
    enable_mock_data: bool = False
    strict_error_handling: bool = True
    max_option_symbols_per_request: int = 20
    
    # Logging Configuration
    log_data_failures: bool = True
    log_level: str = "INFO"
    
    # JWT Configuration
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # CORS Configuration
    allowed_origins: list = ["*"]
    
    # Rate Limiting Configuration
    default_rate_limit: int = 120
    rate_limit_window: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()