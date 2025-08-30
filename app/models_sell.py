"""
卖出模块数据模型
定义卖出相关的数据库表结构
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.database.database import SQLAlchemyBaseUserTable


class AppConfig(SQLAlchemyBaseUserTable):
    """
    应用配置表
    存储不同股票符号的策略配置
    """
    __tablename__ = "app_config"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, comment="股票符号，如 AAPL, TSLA")
    
    # 策略一配置
    strategy_one_profit_rate = Column(Float, default=1.1, comment="策略一止盈率，如1.1表示10%盈利")
    strategy_one_stop_loss_rate = Column(Float, default=0.8, comment="策略一止损率，如0.8表示-20%亏损")
    
    # 策略控制
    enabled = Column(Boolean, default=True, comment="是否启用")
    
    # 备注信息
    description = Column(Text, comment="配置描述")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    def __repr__(self):
        return f"<AppConfig(symbol={self.symbol}, profit_rate={self.strategy_one_profit_rate}, stop_loss_rate={self.strategy_one_stop_loss_rate})>"


class SellExecutionLog(SQLAlchemyBaseUserTable):
    """
    卖出执行日志表
    记录所有卖出策略的执行历史
    """
    __tablename__ = "sell_execution_log"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本信息
    account_id = Column(String(50), index=True, comment="账户ID")
    symbol = Column(String(50), index=True, comment="期权符号")
    underlying_symbol = Column(String(10), index=True, comment="标的股票符号")
    
    # 持仓信息
    qty = Column(Float, comment="持仓数量")
    avg_entry_price = Column(Float, comment="平均成本价")
    
    # 执行信息
    strategy_name = Column(String(20), comment="策略名称")
    execution_reason = Column(String(50), comment="执行原因：止盈、止损、收盘等")
    sell_price = Column(Float, comment="卖出价格")
    
    # 配置信息
    profit_rate = Column(Float, comment="使用的止盈率")
    stop_loss_rate = Column(Float, comment="使用的止损率")
    
    # 结果信息
    success = Column(Boolean, comment="是否执行成功")
    order_id = Column(String(100), comment="订单ID")
    error_message = Column(Text, comment="错误信息（如有）")
    
    # 盈亏信息
    profit_loss = Column(Float, comment="盈亏金额")
    profit_loss_percent = Column(Float, comment="盈亏百分比")
    
    # 时间戳
    executed_at = Column(DateTime, default=datetime.utcnow, comment="执行时间")
    
    def __repr__(self):
        return f"<SellExecutionLog(account_id={self.account_id}, symbol={self.symbol}, reason={self.execution_reason}, success={self.success})>"


class PositionSnapshot(SQLAlchemyBaseUserTable):
    """
    持仓快照表
    定期记录持仓状态，用于分析和监控
    """
    __tablename__ = "position_snapshot"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本信息
    account_id = Column(String(50), index=True, comment="账户ID")
    symbol = Column(String(50), index=True, comment="期权符号")
    underlying_symbol = Column(String(10), index=True, comment="标的股票符号")
    
    # 持仓信息
    qty = Column(Float, comment="持仓数量")
    avg_entry_price = Column(Float, comment="平均成本价")
    market_value = Column(Float, comment="市值")
    unrealized_pl = Column(Float, comment="未实现盈亏")
    unrealized_pl_percent = Column(Float, comment="未实现盈亏百分比")
    
    # 价格信息
    current_price = Column(Float, comment="当前价格")
    bid_price = Column(Float, comment="买一价")
    ask_price = Column(Float, comment="卖一价")
    
    # 期权信息
    expiration_date = Column(String(10), comment="到期日")
    strike_price = Column(Float, comment="行权价")
    option_type = Column(String(4), comment="期权类型：call或put")
    
    # 策略状态
    is_zero_day = Column(Boolean, comment="是否为零日期权")
    days_to_expiry = Column(Integer, comment="距离到期天数")
    
    # 时间戳
    snapshot_time = Column(DateTime, default=datetime.utcnow, comment="快照时间")
    
    def __repr__(self):
        return f"<PositionSnapshot(account_id={self.account_id}, symbol={self.symbol}, qty={self.qty}, unrealized_pl={self.unrealized_pl})>"


class MonitorStatus(SQLAlchemyBaseUserTable):
    """
    监控状态表
    记录卖出监控器的运行状态
    """
    __tablename__ = "monitor_status"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 状态信息
    is_running = Column(Boolean, default=False, comment="是否正在运行")
    start_time = Column(DateTime, comment="启动时间")
    last_check_time = Column(DateTime, comment="最后检查时间")
    
    # 统计信息
    total_positions_checked = Column(Integer, default=0, comment="检查的持仓总数")
    total_strategies_executed = Column(Integer, default=0, comment="执行的策略总数")
    total_orders_placed = Column(Integer, default=0, comment="下单总数")
    
    # 错误信息
    last_error = Column(Text, comment="最后一次错误信息")
    error_count = Column(Integer, default=0, comment="错误计数")
    
    # 配置信息
    check_interval = Column(Integer, default=5, comment="检查间隔（秒）")
    strategy_one_enabled = Column(Boolean, default=True, comment="策略一是否启用")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    def __repr__(self):
        return f"<MonitorStatus(is_running={self.is_running}, last_check_time={self.last_check_time})>"