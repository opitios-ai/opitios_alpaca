# 卖出模块使用指南

## 概述

卖出模块是一个自动化的期权和股票持仓监控系统，类似于Tiger项目的sell_watcher_schedule.py功能。它可以：

- 自动监控所有账户的持仓
- 执行多种卖出策略
- 处理零日期权强制平仓
- 取消过期订单
- 提供实时状态监控

## 文件结构

```
app/sell_module/
├── __init__.py
├── sell_watcher.py          # 主监控器
├── config_manager.py        # 配置管理
├── position_manager.py      # 持仓管理
├── order_manager.py         # 订单管理
├── price_tracker.py         # 价格跟踪
└── sell_strategies/
    ├── __init__.py
    ├── base_strategy.py     # 策略基类
    └── strategy_one.py      # 策略一实现

sell_main.py                 # 独立启动脚本
app/sell_routes.py           # API路由（与FastAPI集成）
```

## 启动方式

### 方式1: 独立运行（推荐用于专门的卖出服务）

```bash
cd D:/Github/opitios_alpaca
python sell_main.py
```

### 方式2: API集成（与主服务一起运行）

1. 在main.py中添加路由：

```python
from app.sell_routes import sell_router
app.include_router(sell_router, prefix="/api/v1", tags=["sell_module"])
```

2. 通过API控制：

```bash
# 启动监控
curl -X POST "http://localhost:8090/api/v1/sell/start" -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 查看状态
curl -X GET "http://localhost:8090/api/v1/sell/status" -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 停止监控
curl -X POST "http://localhost:8090/api/v1/sell/stop" -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 配置说明

在`secrets.yml`中配置：

```yaml
# 卖出模块配置
sell_module:
    enabled: true
    check_interval: 5           # 每5秒检查一次
    order_cancel_minutes: 3     # 取消3分钟前的订单
    zero_day_handling: true     # 处理零日期权

    strategy_one:
      enabled: true
      profit_rate: 1.1         # 10%止盈
      stop_loss_rate: 0.8      # -20%止损
```

## 主要功能

### 1. 持仓监控
- 自动获取所有账户的持仓
- 区分多头/空头持仓
- 识别零日期权

### 2. 策略执行
- **策略一**: 基于盈亏比率的自动卖出
- 支持止盈和止损
- 可扩展添加更多策略

### 3. 订单管理
- 自动取消过期的卖出订单
- 支持市价和限价订单
- 完整的订单跟踪

### 4. 风险控制
- 零日期权强制平仓
- 空头持仓自动平仓
- 市场时间检查

## 日志示例

```
2025-08-26 22:30:00 | INFO | 卖出监控器启动
2025-08-26 22:30:00 | INFO | 发现 3 个多头期权持仓需要监控
2025-08-26 22:30:01 | INFO | 开始取消超过 3 分钟的卖出订单
2025-08-26 22:30:01 | INFO | 策略一已启用，开始检查 AAPL250829C00150000
2025-08-26 22:30:02 | INFO | 策略一执行成功 AAPL250829C00150000: 达到止盈条件, 价格: $2.50
```

## API接口

### 获取状态
```
GET /api/v1/sell/status
```

### 启动/停止监控
```
POST /api/v1/sell/start
POST /api/v1/sell/stop
```

### 执行一次检查
```
POST /api/v1/sell/run-once
```

### 获取配置
```
GET /api/v1/sell/config
```

### 获取监控持仓
```
GET /api/v1/sell/positions
```

## 故障排除

### 常见问题

1. **模块未启动**
   - 检查`secrets.yml`中`sell_module.enabled`是否为true
   - 检查数据库连接是否正常
   - 查看日志中的错误信息

2. **策略不执行**
   - 确认市场是否开放（9:30-16:00 ET）
   - 检查`strategy_one.enabled`配置
   - 验证持仓是否为多头期权

3. **订单取消失败**
   - 检查API连接是否正常
   - 确认订单状态是否可取消
   - 查看详细错误日志

### 调试模式

设置更详细的日志：

```python
logger.add("sell_module_debug.log", level="DEBUG")
```

## 性能优化

- 使用连接池减少API调用
- 批量处理持仓和订单
- 缓存价格数据避免重复请求
- 异步处理提高并发性能

## 安全考虑

- 所有API操作需要JWT认证
- 管理员权限才能启停监控
- 订单操作有完整审计日志
- 支持IP白名单限制