import os
import yaml
from pydantic_settings import BaseSettings
from typing import Optional, List, Dict

def load_secrets():
    """Load secrets from secrets.yml file"""
    secrets_file = "secrets.yml"
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading secrets.yml: {e}")
            return {}
    else:
        print("Warning: secrets.yml not found. Please copy secrets.example.yml to secrets.yml and configure your API keys.")
        return {}

# Load secrets at module level
secrets = load_secrets()

class Settings(BaseSettings):
    
    # Multi-Account Configuration
    accounts: Dict = secrets.get('accounts', {})
    
    # FastAPI Configuration
    app_name: str = "Opitios Alpaca Trading Service"
    debug: bool = secrets.get('app', {}).get('debug', True)
    host: str = "0.0.0.0"
    port: int = 8090
    
    # Data Service Configuration
    real_data_only: bool = secrets.get('trading', {}).get('real_data_only', True)
    enable_mock_data: bool = secrets.get('trading', {}).get('enable_mock_data', False)
    strict_error_handling: bool = secrets.get('trading', {}).get('strict_error_handling', True)
    max_option_symbols_per_request: int = secrets.get('trading', {}).get('max_option_symbols_per_request', 20)
    
    # Logging Configuration
    log_data_failures: bool = True
    log_level: str = secrets.get('app', {}).get('log_level', "INFO")
    
    # JWT Configuration
    jwt_secret: str = secrets.get('jwt', {}).get('secret', "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION")
    jwt_algorithm: str = secrets.get('jwt', {}).get('algorithm', "HS256")
    jwt_expiration_hours: int = secrets.get('jwt', {}).get('expiration_hours', 24)
    
    # Redis Configuration
    redis_host: str = secrets.get('redis', {}).get('host', "localhost")
    redis_port: int = secrets.get('redis', {}).get('port', 6379)
    redis_db: int = secrets.get('redis', {}).get('db', 0)
    redis_password: Optional[str] = secrets.get('redis', {}).get('password')
    
    # CORS Configuration
    allowed_origins: List[str] = secrets.get('app', {}).get('allowed_origins', ["*"])
    
    # Rate Limiting Configuration
    default_rate_limit: int = secrets.get('rate_limit', {}).get('default_limit', 120)
    rate_limit_window: int = secrets.get('rate_limit', {}).get('window_seconds', 60)
    
    # Market Hours Configuration
    market_config: Dict = secrets.get('market', {
        'open_hour': 8,
        'open_minute': 50,
        'close_hour': 17,
        'close_minute': 0,
        'timezone': 'US/Eastern',
        'trading_days': [0, 1, 2, 3, 4]
    })
    
    # Discord Configuration
    discord_config: Dict = secrets.get('discord', {
        'transaction_channel': None
    })
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 创建设置实例
settings = Settings()

# 配置加载状态反馈
if secrets:
    print("Loaded configuration from: secrets.yml")
else:
    print("Warning: secrets.yml not found, using default configuration.")