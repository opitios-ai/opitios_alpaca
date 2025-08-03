"""
增强的Loguru日志配置
支持多用户环境、结构化日志、性能监控和安全审计
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from loguru import logger
from config import settings


class LoggingConfig:
    """日志配置管理类"""
    
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 确保日志目录存在
        for subdir in ["app", "users", "trading", "security", "performance"]:
            (self.log_dir / subdir).mkdir(exist_ok=True)
    
    def setup_logging(self):
        """设置所有日志配置"""
        # 移除默认处理器
        logger.remove()
        
        # 控制台日志 (开发环境)
        if getattr(settings, 'debug', False):
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
                level="DEBUG",
                colorize=True
            )
        
        # 应用主日志
        logger.add(
            self.log_dir / "app" / "alpaca_service.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="INFO",
            rotation="100 MB",
            retention="30 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )
        
        # 错误日志
        logger.add(
            self.log_dir / "app" / "errors.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="ERROR",
            rotation="50 MB",
            retention="60 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )
        
        # 用户操作日志 (结构化JSON)
        logger.add(
            self.log_dir / "users" / "user_operations.jsonl",
            format=self._json_formatter,
            level="INFO",
            rotation="50 MB",
            retention="90 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            filter=lambda record: record["extra"].get("log_type") == "user_operation"
        )
        
        # 交易日志
        logger.add(
            self.log_dir / "trading" / "trading_operations.jsonl",
            format=self._json_formatter,
            level="INFO",
            rotation="100 MB",
            retention="1 year",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            filter=lambda record: record["extra"].get("log_type") == "trading"
        )
        
        # 安全审计日志
        logger.add(
            self.log_dir / "security" / "security_audit.jsonl",
            format=self._json_formatter,
            level="WARNING",
            rotation="50 MB",
            retention="2 years",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            filter=lambda record: record["extra"].get("log_type") == "security"
        )
        
        # 性能监控日志
        logger.add(
            self.log_dir / "performance" / "performance.jsonl",
            format=self._json_formatter,
            level="INFO",
            rotation="20 MB",
            retention="30 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            filter=lambda record: record["extra"].get("log_type") == "performance"
        )
        
        logger.info("日志系统初始化完成")
    
    def _json_formatter(self, record):
        """JSON格式化器"""
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "module": record.get("module", ""),
            "process_id": record.get("process").id if record.get("process") else None,
            "thread_id": record.get("thread").id if record.get("thread") else None
        }
        
        # 添加额外字段
        if record["extra"]:
            log_entry.update(record["extra"])
        
        # 添加异常信息
        if record["exception"]:
            log_entry["exception"] = {
                "type": record["exception"].type.__name__ if record["exception"].type else None,
                "value": str(record["exception"].value) if record["exception"].value else None,
                "traceback": record["exception"].traceback if record["exception"].traceback else None
            }
        
        return json.dumps(log_entry, ensure_ascii=False) + "\n"


class UserLogger:
    """用户专属日志记录器"""
    
    @staticmethod
    def log_user_operation(user_id: str, operation: str, details: Dict[str, Any], success: bool = True):
        """记录用户操作"""
        logger.info(
            f"User operation: {operation}",
            extra={
                "log_type": "user_operation",
                "user_id": user_id,
                "operation": operation,
                "details": details,
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_trading_operation(user_id: str, operation_type: str, symbol: str, 
                            quantity: Optional[float] = None, price: Optional[float] = None,
                            order_id: Optional[str] = None, success: bool = True, 
                            error_message: Optional[str] = None):
        """记录交易操作"""
        logger.info(
            f"Trading operation: {operation_type} {symbol}",
            extra={
                "log_type": "trading",
                "user_id": user_id,
                "operation_type": operation_type,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "order_id": order_id,
                "success": success,
                "error_message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_security_event(user_id: Optional[str], event_type: str, severity: str,
                          details: Dict[str, Any], ip_address: Optional[str] = None):
        """记录安全事件"""
        log_level = {
            "low": "INFO",
            "medium": "WARNING",
            "high": "ERROR",
            "critical": "CRITICAL"
        }.get(severity.lower(), "WARNING")
        
        logger.log(
            log_level,
            f"Security event: {event_type}",
            extra={
                "log_type": "security",
                "user_id": user_id,
                "event_type": event_type,
                "severity": severity,
                "details": details,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_performance_metric(metric_name: str, value: float, unit: str,
                             user_id: Optional[str] = None, additional_data: Optional[Dict] = None):
        """记录性能指标"""
        logger.info(
            f"Performance metric: {metric_name} = {value} {unit}",
            extra={
                "log_type": "performance",
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
                "user_id": user_id,
                "additional_data": additional_data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        )


class PerformanceMonitor:
    """性能监控装饰器和工具"""
    
    @staticmethod
    def monitor_api_call(func_name: str, user_id: Optional[str] = None):
        """API调用性能监控装饰器"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = datetime.utcnow()
                success = True
                error_message = None
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
                finally:
                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()
                    
                    UserLogger.log_performance_metric(
                        metric_name=f"api_call_duration",
                        value=duration,
                        unit="seconds",
                        user_id=user_id,
                        additional_data={
                            "function_name": func_name,
                            "success": success,
                            "error_message": error_message
                        }
                    )
            
            return wrapper
        return decorator
    
    @staticmethod
    def monitor_alpaca_api_call(operation: str, user_id: str):
        """Alpaca API调用监控"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = datetime.utcnow()
                success = True
                error_message = None
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
                finally:
                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()
                    
                    UserLogger.log_performance_metric(
                        metric_name="alpaca_api_call_duration",
                        value=duration,
                        unit="seconds",
                        user_id=user_id,
                        additional_data={
                            "operation": operation,
                            "success": success,
                            "error_message": error_message
                        }
                    )
            
            return wrapper
        return decorator


# 全局日志配置实例
logging_config = LoggingConfig()

# 导出常用功能
__all__ = [
    "logging_config", 
    "UserLogger", 
    "PerformanceMonitor"
]