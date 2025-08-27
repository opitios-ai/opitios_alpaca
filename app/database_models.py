# -*- coding: utf-8 -*-
"""
Database Models for User Account Management
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Optional
from datetime import datetime
import asyncio
from loguru import logger

Base = declarative_base()


class AlpacaUser(Base):
    """Alpaca User Account Model - mirrors app_alpaca_users table"""
    __tablename__ = 'app_alpaca_users'
    
    id = Column(Integer, primary_key=True)
    user_uuid = Column(String(36), nullable=False)
    account_name = Column(String(100), nullable=False)
    api_key = Column(String(100), nullable=False)
    secret_key = Column(String(100), nullable=False)
    paper_trading = Column(Boolean, default=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_config_dict(self) -> Dict:
        """Convert database record to config dictionary format"""
        return {
            'account_id': self.account_name,
            'name': self.account_name,
            'api_key': self.api_key,
            'secret_key': self.secret_key,
            'paper_trading': bool(self.paper_trading),
            'enabled': bool(self.enabled),
            'region': 'us',
            'tier': 'premium',  # Default tier, can be added to DB later
            'max_connections': 3,
            'user_uuid': self.user_uuid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class DatabaseManager:
    """Database manager for reading user configurations"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
        
    def initialize(self):
        """Initialize database connection"""
        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False  # Set to True for SQL debugging
            )
            
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                
            self._initialized = True
            logger.info(f"Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            if not self.engine:
                return False
                
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_all_users(self) -> List[AlpacaUser]:
        """Get all enabled users from database"""
        if not self._initialized:
            self.initialize()
            
        try:
            with self.SessionLocal() as session:
                users = session.query(AlpacaUser).filter(
                    AlpacaUser.enabled == True
                ).all()
                
                logger.info(f"Retrieved {len(users)} enabled users from database")
                return users
                
        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving users: {e}")
            raise
    
    def get_user_by_account_name(self, account_name: str) -> Optional[AlpacaUser]:
        """Get specific user by account name"""
        if not self._initialized:
            self.initialize()
            
        try:
            with self.SessionLocal() as session:
                user = session.query(AlpacaUser).filter(
                    AlpacaUser.account_name == account_name,
                    AlpacaUser.enabled == True
                ).first()
                
                return user
                
        except SQLAlchemyError as e:
            logger.error(f"Database query failed for account {account_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving user {account_name}: {e}")
            return None
    
    def get_accounts_config_dict(self) -> Dict[str, Dict]:
        """Get all users as accounts configuration dictionary"""
        try:
            users = self.get_all_users()
            accounts_config = {}
            
            for user in users:
                config_dict = user.to_config_dict()
                account_name = config_dict['account_id']
                accounts_config[account_name] = config_dict
                
            logger.info(f"Converted {len(accounts_config)} users to accounts config")
            return accounts_config
            
        except Exception as e:
            logger.error(f"Failed to get accounts config from database: {e}")
            return {}
    
    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False
            logger.info("Database connections closed")


# Global database manager and cache
db_manager = None
_accounts_cache = None
_cache_database_url = None


def get_database_manager(database_url: str) -> DatabaseManager:
    """Get or create database manager instance"""
    global db_manager
    
    if db_manager is None:
        db_manager = DatabaseManager(database_url)
        
    return db_manager


def load_accounts_from_database(database_url: str) -> Dict[str, Dict]:
    """Load accounts configuration from database with caching"""
    global _accounts_cache, _cache_database_url
    
    # Return cached data if available and URL hasn't changed
    if _accounts_cache is not None and _cache_database_url == database_url:
        logger.debug(f"Using cached accounts configuration ({len(_accounts_cache)} accounts)")
        return _accounts_cache
    
    try:
        manager = get_database_manager(database_url)
        accounts = manager.get_accounts_config_dict()
        
        # Cache the results
        _accounts_cache = accounts
        _cache_database_url = database_url
        
        return accounts
        
    except Exception as e:
        logger.error(f"Failed to load accounts from database: {e}")
        return {}