# 📈 完整 API 使用示例

本文档提供所有 API 端点的全面示例，包含实际使用场景和详细说明。

## 🔗 基础 URL
```
http://localhost:8081
```

## 📋 目录
1. [健康检查和连接](#健康检查和连接)
2. [账户管理](#账户管理)
3. [单个股票报价](#单个股票报价)
4. [批量股票报价](#批量股票报价)
5. [股票历史数据](#股票历史数据)
6. [期权链](#期权链)
7. [单个期权报价](#单个期权报价)
8. [批量期权报价](#批量期权报价)
9. [股票交易](#股票交易)
10. [订单管理](#订单管理)
11. [投资组合管理](#投资组合管理)
12. [错误处理](#错误处理)
13. [完整工作流程](#完整工作流程)

---

## 健康检查和连接

### 健康检查
监控服务状态并确保 API 响应正常。

```bash
curl -X GET "http://localhost:8081/api/v1/health"
```

**响应：**
```json
{
  "status": "healthy",
  "service": "Opitios Alpaca Trading Service"
}
```

### 测试 API 连接
验证 Alpaca API 连通性和账户访问。

```bash
curl -X GET "http://localhost:8081/api/v1/test-connection"
```

**响应：**
```json
{
  "status": "connected",
  "account_number": "PA33OLW2BBG7",
  "buying_power": 200000.0,
  "cash": 100000.0,
  "portfolio_value": 100000.0
}
```

**使用场景**：在开始交易操作前检查此端点以确保 API 连通性。

---

## 账户管理

### 获取账户信息
检索包括购买力、现金和投资组合价值在内的综合账户详情。

```bash
curl -X GET "http://localhost:8081/api/v1/account"
```

**响应：**
```json
{
  "account_number": "PA33OLW2BBG7",
  "buying_power": 200000.0,
  "cash": 100000.0,
  "portfolio_value": 100000.0,
  "equity": 100000.0,
  "last_equity": 100000.0,
  "multiplier": 2,
  "pattern_day_trader": false
}
```

**关键字段说明：**
- `buying_power`：可用于购买的最大金额（包括保证金）
- `cash`：实际可用现金
- `portfolio_value`：账户总价值（现金 + 头寸）
- `equity`：当前权益价值
- `multiplier`：保证金倍数（2 = 2:1 保证金）
- `pattern_day_trader`：日内交易状态

### 获取头寸
查看所有当前股票头寸及盈亏信息。

```bash
curl -X GET "http://localhost:8081/api/v1/positions"
```

**响应：**
```json
[
  {
    "symbol": "AAPL",
    "qty": 10.0,
    "side": "long",
    "market_value": 2125.0,
    "cost_basis": 2100.0,
    "unrealized_pl": 25.0,
    "unrealized_plpc": 0.0119,
    "avg_entry_price": 210.0
  }
]
```

**使用场景**：在进行新交易前监控投资组合表现和头寸规模。

---

## 单个股票报价

### 通过股票代码获取报价（GET）
检索特定股票代码的实时报价。

```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/quote"
```

### 通过请求体获取报价（POST）
使用 POST 请求并在请求体中包含股票代码的替代方法。

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quote" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "AAPL"}'
```

**响应：**
```json
{
  "symbol": "AAPL",
  "bid_price": 210.1,
  "ask_price": 214.3,
  "bid_size": 100,
  "ask_size": 200,
  "timestamp": "2024-01-15T15:30:00.961420+00:00"
}
```

**报价字段说明：**
- `bid_price`：买方愿意支付的最高价格
- `ask_price`：卖方愿意接受的最低价格
- `bid_size`：买价处的股数
- `ask_size`：卖价处的股数
- `timestamp`：UTC 时间戳的报价时间

**使用场景**：在下单前获取当前市价或分析市场条件。

---

## 批量股票报价

### 获取多个股票报价
在单个请求中高效检索多个股票代码的报价。

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
     }'
```

**响应：**
```json
{
  "quotes": [
    {
      "symbol": "AAPL",
      "bid_price": 210.1,
      "ask_price": 214.3,
      "bid_size": 100,
      "ask_size": 200,
      "timestamp": "2024-01-15T15:30:00Z"
    },
    {
      "symbol": "TSLA",
      "bid_price": 185.5,
      "ask_price": 187.2,
      "bid_size": 150,
      "ask_size": 300,
      "timestamp": "2024-01-15T15:30:00Z"
    }
  ],
  "count": 2,
  "requested_symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
}
```

**限制**：每个请求最多 20 个股票代码以保持性能。

**使用场景**：投资组合监控、观察列表更新或市场扫描。

---

## 股票历史数据

### 获取历史价格条
检索用于技术分析的历史价格数据。

```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=5"
```

**参数：**
- `timeframe`：1Min、5Min、15Min、1Hour、1Day
- `limit`：要检索的价格条数量（最多 1000）
- `start`：开始日期（可选，格式：YYYY-MM-DD）
- `end`：结束日期（可选，格式：YYYY-MM-DD）

**响应：**
```json
{
  "symbol": "AAPL",
  "timeframe": "1Day",
  "bars": [
    {
      "timestamp": "2024-01-12T00:00:00Z",
      "open": 208.5,
      "high": 212.3,
      "low": 207.8,
      "close": 211.2,
      "volume": 45678900
    },
    {
      "timestamp": "2024-01-11T00:00:00Z", 
      "open": 205.1,
      "high": 209.4,
      "low": 204.6,
      "close": 208.7,
      "volume": 52341200
    }
  ]
}
```

**使用场景**：技术分析、回测策略、图表生成。

---

## 期权链

### 获取标的股票的期权链
检索特定股票和到期日的所有可用期权合约。

```bash
curl -X POST "http://localhost:8081/api/v1/options/chain" \
     -H "Content-Type: application/json" \
     -d '{
       "underlying_symbol": "AAPL",
       "expiration_date": "2024-02-16"
     }'
```

### 替代 GET 方法
```bash
curl -X GET "http://localhost:8081/api/v1/options/AAPL/chain?expiration_date=2024-02-16"
```

**响应：**
```json
{
  "underlying_symbol": "AAPL",
  "underlying_price": 212.5,
  "expiration_dates": ["2024-02-16"],
  "options_count": 42,
  "options": [
    {
      "symbol": "AAPL240216C00190000",
      "underlying_symbol": "AAPL",
      "strike_price": 190.0,
      "expiration_date": "2024-02-16",
      "option_type": "call",
      "bid_price": 24.25,
      "ask_price": 24.75,
      "last_price": 24.50,
      "implied_volatility": 0.25,
      "delta": 0.85,
      "in_the_money": true
    }
  ],
  "note": "示例期权数据 - 在生产环境中将使用真实市场数据"
}
```

**期权代码格式**：`AAPL240216C00190000`
- `AAPL`：标的股票代码
- `240216`：到期日期（年月日格式）
- `C`：期权类型（C=看涨期权，P=看跌期权）
- `00190000`：行权价格（$190.00）

**使用场景**：期权策略分析、寻找最佳行权价格和到期日。

---

## 单个期权报价

### 获取期权报价
检索特定期权合约的详细定价和希腊字母。

```bash
curl -X POST "http://localhost:8081/api/v1/options/quote" \
     -H "Content-Type: application/json" \
     -d '{"option_symbol": "AAPL240216C00190000"}'
```

**响应：**
```json
{
  "symbol": "AAPL240216C00190000",
  "underlying_symbol": "AAPL",
  "underlying_price": 212.5,
  "strike_price": 190.0,
  "expiration_date": "2024-02-16",
  "option_type": "call",
  "bid_price": 24.25,
  "ask_price": 24.75,
  "last_price": 24.50,
  "implied_volatility": 0.25,
  "delta": 0.85,
  "gamma": 0.05,
  "theta": -0.02,
  "vega": 0.1,
  "in_the_money": true,
  "intrinsic_value": 22.5,
  "time_value": 2.0,
  "timestamp": "2024-01-15T15:30:00Z"
}
```

**希腊字母说明：**
- `delta`：对标的股票价格变动的敏感度
- `gamma`：对标的股票价格变动的 delta 敏感度
- `theta`：时间衰减（每日权利金损失）
- `vega`：波动率敏感度

**使用场景**：期权定价分析、风险评估、策略评估。

---

## 股票交易

### 市价订单 - 买入
以当前市价立即执行购买。

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "buy",
       "type": "market",
       "time_in_force": "day"
     }'
```

### 限价订单 - 卖出
仅以指定价格或更好价格出售股票。

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 5,
       "side": "sell",
       "type": "limit",
       "limit_price": 215.50,
       "time_in_force": "gtc"
     }'
```

### 止损订单
当价格跌至止损水平时触发市价卖出。

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "sell",
       "type": "stop",
       "stop_price": 200.00,
       "time_in_force": "day"
     }'
```

**订单响应：**
```json
{
  "id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa",
  "symbol": "AAPL", 
  "qty": 10.0,
  "side": "buy",
  "order_type": "market",
  "status": "pending_new",
  "filled_qty": 0.0,
  "filled_avg_price": null,
  "submitted_at": "2024-01-15T15:30:13.903790+00:00",
  "filled_at": null
}
```

### 快速交易端点

#### 快速买入（简化）
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/buy?qty=10"
```

#### 快速卖出（简化）
```bash 
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/sell?qty=5&order_type=limit&limit_price=215.50"
```

**订单类型说明：**
- `market`：以当前价格立即执行
- `limit`：仅以指定价格或更好价格执行
- `stop`：达到止损价格时触发市价订单
- `stop_limit`：达到止损价格时触发限价订单

**有效期选项：**
- `day`：仅在当前交易日有效
- `gtc`：有效直到取消（Good Till Cancelled）
- `ioc`：立即成交或取消（Immediate or Cancel）
- `fok`：全部成交或取消（Fill or Kill）

---

## 订单管理

### 获取所有订单
检索带有可选筛选的订单历史。

```bash
# 获取最近订单
curl -X GET "http://localhost:8081/api/v1/orders?limit=10"

# 按状态获取订单
curl -X GET "http://localhost:8081/api/v1/orders?status=filled&limit=5"

# 获取特定股票的订单
curl -X GET "http://localhost:8081/api/v1/orders?symbol=AAPL&limit=5"
```

**响应：**
```json
[
  {
    "id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa",
    "symbol": "AAPL",
    "qty": 10.0,
    "side": "buy",
    "order_type": "market",
    "status": "filled",
    "filled_qty": 10.0,
    "filled_avg_price": 212.15,
    "submitted_at": "2024-01-15T15:30:13.903790+00:00",
    "filled_at": "2024-01-15T15:30:14.125000+00:00",
    "limit_price": null,
    "stop_price": null
  }
]
```

### 取消订单
通过订单 ID 取消待执行订单。

```bash
curl -X DELETE "http://localhost:8081/api/v1/orders/1b7d6894-7040-4284-b7a4-2f900e30b6aa"
```

**响应：**
```json
{
  "status": "cancelled",
  "order_id": "1b7d6894-7040-4284-b7a4-2f900e30b6aa"
}
```

**订单状态：**
- `pending_new`：订单已提交，等待接受
- `accepted`：订单被交易所接受
- `filled`：订单完全成交
- `partially_filled`：订单部分成交
- `cancelled`：订单已取消
- `rejected`：订单被交易所拒绝

---

## 错误处理

### 无效股票代码
```bash
curl -X GET "http://localhost:8081/api/v1/stocks/INVALID/quote"
```

**响应：**
```json
{
  "detail": "No quote data found for INVALID"
}
```

### 批量请求中股票代码过多
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{
       "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "META", "NFLX", "NVDA", "AMD", "INTC", "ORCL", "CRM", "ADBE", "PYPL", "UBER", "LYFT", "SPOT", "SQ", "ROKU", "ZM", "TWTR"]
     }'
```

**响应：**
```json
{
  "detail": "Maximum 20 symbols allowed per request"
}
```

### 购买力不足
```bash
# 尝试购买价值 100 万美元的股票但资金不足
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 5000,
       "side": "buy",
       "type": "market"
     }'
```

**响应：**
```json
{
  "detail": "Insufficient buying power for this order"
}
```

---

## 完整工作流程

### 1. 交易前设置
```bash
# 检查服务健康状态
curl -X GET "http://localhost:8081/api/v1/health"

# 验证 API 连接
curl -X GET "http://localhost:8081/api/v1/test-connection"

# 检查账户状态
curl -X GET "http://localhost:8081/api/v1/account"
```

### 2. 市场研究
```bash
# 获取观察列表的当前报价
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
     -H "Content-Type: application/json" \
     -d '{"symbols": ["AAPL", "TSLA", "GOOGL"]}'

# 获取技术分析的历史数据
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=10"
```

### 3. 期权分析（如适用）
```bash
# 获取期权链
curl -X POST "http://localhost:8081/api/v1/options/chain" \
     -H "Content-Type: application/json" \
     -d '{"underlying_symbol": "AAPL"}'

# 获取特定期权报价
curl -X POST "http://localhost:8081/api/v1/options/quote" \
     -H "Content-Type: application/json" \
     -d '{"option_symbol": "AAPL240216C00190000"}'
```

### 4. 下单
```bash
# 下策略性买入订单
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "buy",
       "type": "limit",
       "limit_price": 210.00,
       "time_in_force": "day"
     }'

# 设置止损
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "sell",
       "type": "stop",
       "stop_price": 200.00,
       "time_in_force": "gtc"
     }'
```

### 5. 监控和管理
```bash
# 检查订单状态
curl -X GET "http://localhost:8081/api/v1/orders?limit=5"

# 监控头寸
curl -X GET "http://localhost:8081/api/v1/positions"

# 如需要取消订单
curl -X DELETE "http://localhost:8081/api/v1/orders/{order_id}"
```

---

## 🎯 准备好交易！

这个全面的 API 提供：

- ✅ **实时市场数据**：单个和批量股票报价
- ✅ **历史数据**：用于技术分析的价格条
- ✅ **期权交易**：完整的期权链和定价
- ✅ **订单管理**：所有主要订单类型及完整生命周期管理
- ✅ **投资组合跟踪**：实时头寸和盈亏
- ✅ **账户管理**：完整的账户信息和监控

**下一步：**
1. **生产设置**：配置实盘交易（更新基础 URL 并禁用模拟交易）
2. **风险管理**：实施头寸规模和止损策略
3. **自动化**：使用这些端点构建自动化交易策略
4. **监控**：为您的交易操作设置警报和监控

**交互式文档**：访问 http://localhost:8081/docs 获取具有请求/响应测试功能的完整交互式 API 参考。

---

**API 版本**：1.0.0  
**最后更新**：2025年1月  
**下一步**：[故障排除指南](故障排除指南.md)