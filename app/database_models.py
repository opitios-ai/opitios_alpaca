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
        config = {
            'account_id': self.account_name,
            'name': self.account_name,
            'api_key': self.api_key,
            'secret_key': self.secret_key,
            'paper_trading': bool(self.paper_trading),
            'enabled': bool(self.enabled),
            'region': 'us',
            'tier': 'premium',
            'max_connections': 3,
            'user_uuid': self.user_uuid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Add strategy flags if they exist (set by get_user_with_strategies)
        if hasattr(self, 'MODE_STOCK_TRADE'):
            config['MODE_STOCK_TRADE'] = self.MODE_STOCK_TRADE
        if hasattr(self, 'MODE_OPTION_TRADE'):
            config['MODE_OPTION_TRADE'] = self.MODE_OPTION_TRADE
        if hasattr(self, 'MODE_DAY_TRADE'):
            config['MODE_DAY_TRADE'] = self.MODE_DAY_TRADE
            
        return config


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
        """Get specific user by account name with strategy flags"""
        if not self._initialized:
            self.initialize()
            
        try:
            with self.SessionLocal() as session:
                # Query with JOIN to trading_rules table (similar to Tiger service)
                # Note: Relies on SQLAlchemy's table metadata to use the correct schema
                query = text("""
                    SELECT 
                        au.id,
                        au.user_uuid,
                        au.account_name,
                        au.api_key,
                        au.secret_key,
                        au.paper_trading,
                        au.enabled,
                        au.created_at,
                        au.updated_at,
                        MAX(CASE WHEN tr.rule_name = 'MODE_STOCK_TRADE' AND tr.is_active = 1 AND tr.created_by_admin = 1 THEN 1 ELSE 0 END) AS MODE_STOCK_TRADE,
                        MAX(CASE WHEN tr.rule_name = 'MODE_OPTION_TRADE' AND tr.is_active = 1 AND tr.created_by_admin = 1 THEN 1 ELSE 0 END) AS MODE_OPTION_TRADE,
                        MAX(CASE WHEN tr.rule_name = 'MODE_DAY_TRADE' AND tr.is_active = 1 AND tr.created_by_admin = 1 THEN 1 ELSE 0 END) AS MODE_DAY_TRADE
                    FROM app_alpaca_users au
                    LEFT JOIN trading_rules tr ON au.user_uuid = tr.user_id
                        AND tr.rule_name IN ('MODE_STOCK_TRADE', 'MODE_OPTION_TRADE', 'MODE_DAY_TRADE')
                    WHERE au.account_name = :account_name
                        AND au.enabled = TRUE
                    GROUP BY 
                        au.id, au.user_uuid, au.account_name, au.api_key, 
                        au.secret_key, au.paper_trading, au.enabled, 
                        au.created_at, au.updated_at
                """)
                
                result = session.execute(query, {"account_name": account_name})
                row = result.fetchone()
                
                if row is None:
                    return None
                
                # Create AlpacaUser object with strategy flags
                user = AlpacaUser()
                user.id = row.id
                user.user_uuid = row.user_uuid
                user.account_name = row.account_name
                user.api_key = row.api_key
                user.secret_key = row.secret_key
                user.paper_trading = row.paper_trading
                user.enabled = row.enabled
                user.created_at = row.created_at
                user.updated_at = row.updated_at
                
                # Add strategy flags as attributes
                user.MODE_STOCK_TRADE = row.MODE_STOCK_TRADE
                user.MODE_OPTION_TRADE = row.MODE_OPTION_TRADE
                user.MODE_DAY_TRADE = row.MODE_DAY_TRADE
                
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
    
    def create_or_update_alpaca_user(
        self,
        user_uuid: str,
        username: str,
        api_key: str,
        secret_key: str,
        paper_trading: bool,
        enabled: bool = True
    ) -> dict:
        """
        Create or update an Alpaca user account.
        Account name is auto-generated from username: {username} for paper, {username}_live for live.
        Uses (user_uuid, paper_trading) as unique identifier.
        
        Args:
            user_uuid: User's UUID from auth system
            username: User's username (from JWT)
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            paper_trading: True for paper trading, False for live trading
            enabled: Whether the account is enabled
            
        Returns:
            dict with success status and account info
        """
        if not self._initialized:
            self.initialize()
        
        # Auto-generate account_name from username
        # Paper: {username}, Live: {username}_live
        account_name = username if paper_trading else f"{username}_live"
            
        try:
            with self.SessionLocal() as session:
                # Check if account for this user + paper_trading combination exists
                # This matches the unique index (user_uuid, paper_trading)
                existing = session.query(AlpacaUser).filter(
                    AlpacaUser.user_uuid == user_uuid,
                    AlpacaUser.paper_trading == paper_trading
                ).first()
                
                if existing:
                    # Update existing record (including account_name in case username changed)
                    existing.account_name = account_name
                    existing.api_key = api_key
                    existing.secret_key = secret_key
                    existing.enabled = enabled
                    existing.updated_at = datetime.utcnow()
                    session.commit()
                    
                    logger.info(f"Updated Alpaca account {account_name} for user {user_uuid}")
                    return {
                        "success": True,
                        "message": "Alpaca account updated successfully",
                        "account_id": existing.id,
                        "account_name": account_name,
                        "is_new": False
                    }
                else:
                    # Create new record
                    new_user = AlpacaUser(
                        user_uuid=user_uuid,
                        account_name=account_name,
                        api_key=api_key,
                        secret_key=secret_key,
                        paper_trading=paper_trading,
                        enabled=enabled,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(new_user)
                    session.commit()
                    session.refresh(new_user)
                    
                    logger.info(f"Created new Alpaca account {account_name} for user {user_uuid}")
                    return {
                        "success": True,
                        "message": "Alpaca account created successfully",
                        "account_id": new_user.id,
                        "account_name": account_name,
                        "is_new": True
                    }
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error creating/updating Alpaca user: {e}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error creating/updating Alpaca user: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def get_alpaca_accounts_by_user(self, user_uuid: str) -> list:
        """
        Get all Alpaca accounts for a user.
        
        Args:
            user_uuid: User's UUID
            
        Returns:
            List of account info dicts (without sensitive keys)
        """
        if not self._initialized:
            self.initialize()
            
        try:
            with self.SessionLocal() as session:
                accounts = session.query(AlpacaUser).filter(
                    AlpacaUser.user_uuid == user_uuid
                ).all()
                
                result = []
                for acc in accounts:
                    result.append({
                        "id": acc.id,
                        "account_name": acc.account_name,
                        "paper_trading": bool(acc.paper_trading),
                        "enabled": bool(acc.enabled),
                        "has_credentials": bool(acc.api_key and acc.secret_key),
                        "created_at": acc.created_at.isoformat() if acc.created_at else None,
                        "updated_at": acc.updated_at.isoformat() if acc.updated_at else None
                    })
                
                return result
                
        except SQLAlchemyError as e:
            logger.error(f"Database error getting Alpaca accounts: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Alpaca accounts: {e}")
            return []
    
    def set_alpaca_account_enabled(
        self,
        user_uuid: str,
        username: str,
        paper_trading: bool,
        enabled: bool
    ) -> dict:
        """
        Enable or disable an Alpaca account.
        When enabling one account, automatically disable the other.
        
        Args:
            user_uuid: User's UUID
            username: User's username (for generating account_name)
            paper_trading: Which account to modify (True=paper, False=live)
            enabled: New enabled status
            
        Returns:
            dict with success status
        """
        if not self._initialized:
            self.initialize()
        
        # Generate account_name from username
        account_name = username if paper_trading else f"{username}_live"
        other_account_name = f"{username}_live" if paper_trading else username
            
        try:
            with self.SessionLocal() as session:
                # Find the target account
                account = session.query(AlpacaUser).filter(
                    AlpacaUser.account_name == account_name,
                    AlpacaUser.user_uuid == user_uuid
                ).first()
                
                if not account:
                    return {
                        "success": False,
                        "error": f"No {'paper' if paper_trading else 'live'} trading account found"
                    }
                
                # If enabling this account, disable the other one
                if enabled:
                    other_account = session.query(AlpacaUser).filter(
                        AlpacaUser.account_name == other_account_name,
                        AlpacaUser.user_uuid == user_uuid
                    ).first()
                    
                    if other_account:
                        other_account.enabled = False
                        other_account.updated_at = datetime.utcnow()
                
                # Update target account
                account.enabled = enabled
                account.updated_at = datetime.utcnow()
                session.commit()
                
                logger.info(f"Set Alpaca account {account_name} enabled={enabled}")
                return {
                    "success": True,
                    "message": f"Account {'enabled' if enabled else 'disabled'} successfully"
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error setting account enabled: {e}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error setting account enabled: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

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