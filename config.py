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
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()