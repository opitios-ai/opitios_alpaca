"""
Strategy Validator for Alpaca Trading Service
Validates trading strategies before order placement
"""

from fastapi import HTTPException
from loguru import logger
from typing import Optional


def validate_order_strategy(
    db_manager,
    account_id: str,
    strategy_name: str
) -> bool:
    """
    Validate if an order is allowed based on user's active trading strategies.
    
    Args:
        db_manager: Database manager instance
        account_id: Alpaca account ID
        strategy_name: Strategy to check (MODE_STOCK_TRADE, MODE_OPTION_TRADE, MODE_DAY_TRADE)
    
    Returns:
        True if strategy is active
        
    Raises:
        HTTPException(404): Account not found
        HTTPException(403): Strategy not active
    """
    try:
        # Get account with strategy flags
        account = db_manager.get_user_by_account_name(account_id)
        
        if account is None:
            logger.error(f"Account '{account_id}' not found for strategy validation")
            raise HTTPException(
                status_code=404,
                detail=f"Account '{account_id}' not found or not enabled"
            )
        
        # Convert to config dict to get strategy flags
        account_config = account.to_config_dict()
        
        # Get the strategy flag value
        strategy_value = account_config.get(strategy_name, 0)
        
        # Strategy is active if value is 1
        if strategy_value != 1:
            logger.warning(
                f"Strategy validation failed: {account_id} | {strategy_name} = {strategy_value}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Strategy '{strategy_name}' is not active for account '{account_id}'. Please activate the strategy before placing orders."
            )
        
        logger.debug(f"Strategy validation passed: {account_id} | {strategy_name}")
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating strategy for {account_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate trading strategy: {str(e)}"
        )


def validate_stock_strategy(db_manager, account_id: str) -> bool:
    """Validate MODE_STOCK_TRADE strategy"""
    return validate_order_strategy(db_manager, account_id, "MODE_STOCK_TRADE")


def validate_option_strategy(db_manager, account_id: str) -> bool:
    """Validate MODE_OPTION_TRADE strategy"""
    return validate_order_strategy(db_manager, account_id, "MODE_OPTION_TRADE")


def validate_day_trade_strategy(db_manager, account_id: str) -> bool:
    """Validate MODE_DAY_TRADE strategy"""
    return validate_order_strategy(db_manager, account_id, "MODE_DAY_TRADE")
