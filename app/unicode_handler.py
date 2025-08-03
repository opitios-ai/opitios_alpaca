"""
Unicode处理工具类
提供跨平台兼容的字符处理，解决Windows GBK编码问题
"""
import sys
import os
import platform
from typing import Any, Dict, Optional
from loguru import logger


class UnicodeHandler:
    """Unicode字符处理工具类，确保跨平台兼容性"""
    
    # Unicode字符到ASCII兼容字符的映射
    UNICODE_MAPPING = {
        # 状态指示符
        '✅': '[OK]',
        '❌': '[FAIL]',
        '⚠️': '[WARN]',
        '🚀': '[START]',
        '🎯': '[TARGET]',
        '🎉': '[SUCCESS]',
        '📊': '[DATA]',
        '📈': '[UP]',
        '📉': '[DOWN]',
        '📋': '[INFO]',
        '📝': '[NOTE]',
        '💰': '[MONEY]',
        '🔥': '[HOT]',
        '⭐': '[STAR]',
        '💡': '[IDEA]',
        '🔴': '[RED]',
        '🟢': '[GREEN]',
        '💎': '[DIAMOND]',
        '🏆': '[TROPHY]',
        '🔑': '[KEY]',
        '💻': '[COMPUTER]',
        '📱': '[MOBILE]',
        '⌚': '[WATCH]',
        '📺': '[TV]',
        '🖥️': '[MONITOR]',
        '🖨️': '[PRINTER]',
        '⌨️': '[KEYBOARD]',
        '🖱️': '[MOUSE]',
        '💾': '[SAVE]',
        '💿': '[CD]',
        '📀': '[DVD]',
        '💽': '[DISK]',
        '🗂️': '[FOLDER]',
        '📁': '[FOLDER]',
        '📂': '[OPEN_FOLDER]',
        '🗃️': '[FILE_BOX]',
        '🗄️': '[CABINET]',
        '🗑️': '[TRASH]',
        '📌': '[PIN]',
        '📍': '[LOCATION]',
        '📎': '[CLIP]',
        '🖇️': '[PAPERCLIP]',
        '📏': '[RULER]',
        '📐': '[TRIANGLE]',
        '✂️': '[SCISSORS]',
        '📦': '[PACKAGE]',
        '📫': '[MAILBOX]',
        '📪': '[MAILBOX_CLOSED]',
        '📬': '[MAILBOX_WITH_MAIL]',
        '📭': '[MAILBOX_NO_MAIL]',
        '📮': '[POSTBOX]',
        '🗳️': '[BALLOT]',
        '✉️': '[ENVELOPE]',
        '📧': '[EMAIL]',
        '📨': '[INCOMING_ENVELOPE]',
        '📩': '[ENVELOPE_ARROW]',
        '📤': '[OUTBOX]',
        '📥': '[INBOX]',
        '💯': '[100]',
        '🛡️': '[SHIELD]',
        '⚡': '[LIGHTNING]',
        '🌟': '[STAR2]',
        '⏹️': '[STOP]',
        'ℹ️': '[INFO]',
    }
    
    @classmethod
    def is_windows_gbk_environment(cls) -> bool:
        """检测是否为Windows GBK环境"""
        if platform.system() != 'Windows':
            return False
        
        # 检查系统编码
        encoding = sys.getdefaultencoding().lower()
        if 'gbk' in encoding or 'gb2312' in encoding:
            return True
        
        # 检查控制台编码
        try:
            console_encoding = sys.stdout.encoding
            if console_encoding and ('gbk' in console_encoding.lower() or 'gb' in console_encoding.lower()):
                return True
        except:
            pass
        
        return False
    
    @classmethod
    def safe_unicode_to_ascii(cls, text: str) -> str:
        """将Unicode字符安全转换为ASCII兼容字符"""
        if not text:
            return text
        
        result = text
        for unicode_char, ascii_replacement in cls.UNICODE_MAPPING.items():
            result = result.replace(unicode_char, ascii_replacement)
        
        return result
    
    @classmethod
    def format_log_message(cls, message: str, force_ascii: Optional[bool] = None) -> str:
        """格式化日志消息，根据环境决定是否转换Unicode"""
        if force_ascii is None:
            force_ascii = cls.is_windows_gbk_environment()
        
        if force_ascii:
            return cls.safe_unicode_to_ascii(message)
        
        return message
    
    @classmethod
    def safe_print(cls, message: str, **kwargs) -> None:
        """安全的打印函数，自动处理Unicode兼容性"""
        try:
            formatted_message = cls.format_log_message(message)
            print(formatted_message, **kwargs)
        except UnicodeEncodeError:
            # 如果仍然出现编码错误，强制转换为ASCII
            ascii_message = cls.safe_unicode_to_ascii(message)
            print(ascii_message, **kwargs)
        except Exception as e:
            # 最后的fallback
            print(f"[PRINT_ERROR] Original message encoding failed: {str(e)}")


class SafeLogger:
    """安全的日志记录器包装器"""
    
    def __init__(self, logger_instance):
        self.logger = logger_instance
    
    def _safe_format(self, message: str) -> str:
        """安全格式化消息"""
        return UnicodeHandler.format_log_message(message)
    
    def info(self, message: str, *args, **kwargs):
        """安全的info日志"""
        formatted_message = self._safe_format(message)
        self.logger.info(formatted_message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """安全的error日志"""
        formatted_message = self._safe_format(message)
        self.logger.error(formatted_message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """安全的warning日志"""
        formatted_message = self._safe_format(message)
        self.logger.warning(formatted_message, *args, **kwargs)
    
    def success(self, message: str, *args, **kwargs):
        """安全的success日志"""
        formatted_message = self._safe_format(message)
        self.logger.success(formatted_message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """安全的debug日志"""
        formatted_message = self._safe_format(message)
        self.logger.debug(formatted_message, *args, **kwargs)


def create_safe_logger(logger_instance=None):
    """创建安全的日志记录器"""
    if logger_instance is None:
        logger_instance = logger
    return SafeLogger(logger_instance)


# 全局安全日志实例和便捷函数
safe_logger = create_safe_logger()


def safe_print(message: str, **kwargs):
    """便捷的安全打印函数"""
    UnicodeHandler.safe_print(message, **kwargs)


def get_environment_info():
    """获取环境信息"""
    return UnicodeHandler.configure_environment()