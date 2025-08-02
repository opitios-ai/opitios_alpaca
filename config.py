import os
import yaml
from pydantic_settings import BaseSettings
from typing import Optional, List

def load_secrets():
    """Load secrets from secrets.yml file"""
    secrets_file = "secrets.yml"
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"❌ 加载 secrets.yml 时出错: {e}")
            return {}
    else:
        print("⚠️  未找到 secrets.yml 文件，使用默认配置。请复制 secrets.example.yml 为 secrets.yml 并配置您的密钥。")
        return {}

# Load secrets at module level
secrets = load_secrets()

class Settings(BaseSettings):
    # Alpaca API Configuration
    alpaca_api_key: str = secrets.get('alpaca', {}).get('api_key', "YOUR_ALPACA_API_KEY_HERE")
    alpaca_secret_key: Optional[str] = secrets.get('alpaca', {}).get('secret_key')
    alpaca_base_url: str = secrets.get('alpaca', {}).get('base_url', "https://paper-api.alpaca.markets")
    alpaca_paper_trading: bool = secrets.get('alpaca', {}).get('paper_trading', True)
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 创建设置实例
settings = Settings()

# 尝试导入本地配置覆盖（保持向后兼容性）
try:
    from config_local import settings as local_settings
    settings = local_settings
    print("✅ 已加载本地配置文件: config_local.py（警告：建议迁移到 secrets.yml）")
except ImportError:
    if secrets:
        print("✅ 已加载配置文件: secrets.yml")
    else:
        print("⚠️  未找到配置文件，使用默认配置。")
except Exception as e:
    print(f"❌ 加载本地配置时出错: {e}")
    print("使用 secrets.yml 配置...")