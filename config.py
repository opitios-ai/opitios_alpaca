import os
import yaml
from pathlib import Path
from typing import Optional, List, Dict

try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        raise ImportError("Neither pydantic_settings nor pydantic.BaseSettings could be imported. Please install pydantic[dotenv] or pydantic-settings")


def find_project_root() -> Path:
    """Find project root directory by looking for secrets.yml or secrets.example.yml"""
    current_path = Path(__file__).parent.absolute()
    
    # Walk up the directory tree looking for project root markers
    for path in [current_path] + list(current_path.parents):
        # Check for secrets files (primary indicators)
        if (path / "secrets.yml").exists() or (path / "secrets.example.yml").exists():
            return path
        # Check for other project markers
        if (path / "main.py").exists() and (path / "app").exists():
            return path
    
    # Fallback to current directory
    return current_path


def load_accounts_from_database(database_url: str) -> Dict[str, Dict]:
    """Load accounts from database - REQUIRED"""
    try:
        from app.database_models import load_accounts_from_database
        accounts = load_accounts_from_database(database_url)
        if not accounts:
            raise ValueError("No accounts found in database - database must contain account configurations")
        return accounts
    except Exception as e:
        raise RuntimeError(f"Failed to load accounts from database: {e}")


def load_secrets():
    """Load configuration - accounts MUST come from database, other settings from YAML"""
    # Load YAML configuration for database URL and other settings
    project_root = find_project_root()
    secrets_file = project_root / "secrets.yml"
    
    if not secrets_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {secrets_file}")
    
    try:
        with open(secrets_file, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to load secrets.yml: {e}")
    
    # Database URL is REQUIRED
    database_url = yaml_config.get('database', {}).get('url')
    if not database_url:
        raise ValueError("Database URL is required in secrets.yml under 'database.url'")
    
    # Load accounts from database (REQUIRED)
    try:
        database_accounts = load_accounts_from_database(database_url)
        print(f"Database: Loaded {len(database_accounts)} accounts")
    except Exception as e:
        raise RuntimeError(f"Database account loading failed: {e}")
    
    # Merge database accounts with YAML configuration
    final_config = yaml_config.copy()
    final_config['accounts'] = database_accounts
    
    return final_config


# Load secrets at module level
secrets = load_secrets()


class Settings(BaseSettings):
    
    # Multi-Account Configuration (FROM DATABASE ONLY)
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
    minimum_balance: float = secrets.get('trading', {}).get('minimum_balance', 5000.0)
    
    # Logging Configuration
    log_data_failures: bool = True
    log_level: str = secrets.get('app', {}).get('log_level', "INFO")
    
    # JWT Configuration
    jwt_secret: str = secrets.get('jwt', {}).get('secret_key', "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION")
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
    
    # Sell Module Configuration (read entirely from secrets.yml)
    sell_module: Dict = secrets.get('sell_module', {})
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 创建设置实例
settings = Settings()

print(f"Configuration loaded: {len(settings.accounts)} accounts from database")