# Opitios Alpaca API 完整测试命令列表

## Alpaca WebSocket 支持说明

**✅ Alpaca 免费版本（Paper Trading）完全支持 WebSocket**
- **实时数据流**: 支持股票、期权实时数据
- **限制**: IEX交易所数据（免费版），30个股票符号限制，200个期权报价限制
- **连接**: 单个WebSocket连接，使用API密钥认证
- **端点**: `wss://paper-api.alpaca.markets/stream` (账户更新)
- **数据流**: `wss://stream.data.alpaca.markets/v2/iex` (市场数据)

## 环境变量设置

```bash
export BASE_URL="http://localhost:8081"
export TOKEN=""  # 将在登录后设置
```

## 1. 健康检查和基础端点 (无需认证)

### 根端点
```bash
curl -X GET "${BASE_URL}/"
```

### 健康检查
```bash
curl -X GET "${BASE_URL}/api/v1/health"
```

### 连接测试
```bash
curl -X GET "${BASE_URL}/api/v1/test-connection"
```

## 2. 用户认证端点

### 用户注册
```bash
curl -X POST "${BASE_URL}/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser_'$(date +%s)'",
    "email": "test_'$(date +%s)'@example.com",
    "password": "TestPassword123!",
    "alpaca_api_key": "YOUR_ALPACA_API_KEY",
    "alpaca_secret_key": "YOUR_ALPACA_SECRET_KEY",
    "alpaca_paper_trading": true
  }'
```

### 用户登录 (获取JWT Token)
```bash
# 登录并获取token
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser_123",
    "password": "TestPassword123!"
  }')

# 提取token
export TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')
echo "Token: $TOKEN"
```

## 3. 股票报价端点 (公开访问，无需JWT)

### 单个股票报价 (POST)
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/quote" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'
```

### 单个股票报价 (GET)
```bash
curl -X GET "${BASE_URL}/api/v1/stocks/AAPL/quote"
```

### 批量股票报价
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/quotes/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
  }'
```

### 股票历史数据
```bash
curl -X GET "${BASE_URL}/api/v1/stocks/AAPL/bars?timeframe=1Day&limit=10"
```

## 4. 账户信息端点 (公开访问，用于演示)

### 获取账户信息
```bash
curl -X GET "${BASE_URL}/api/v1/account"
```

### 获取持仓信息
```bash
curl -X GET "${BASE_URL}/api/v1/positions"
```

## 5. 期权数据端点 (公开访问)

### 期权链查询
```bash
curl -X POST "${BASE_URL}/api/v1/options/chain" \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "AAPL",
    "expiration_date": "2024-03-15"
  }'
```

### 期权链查询 (GET)
```bash
curl -X GET "${BASE_URL}/api/v1/options/AAPL/chain?expiration_date=2024-03-15"
```

### 单个期权报价
```bash
curl -X POST "${BASE_URL}/api/v1/options/quote" \
  -H "Content-Type: application/json" \
  -d '{
    "option_symbol": "AAPL240315C00190000"
  }'
```

### 批量期权报价
```bash
curl -X POST "${BASE_URL}/api/v1/options/quotes/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "option_symbols": [
      "AAPL240315C00190000",
      "AAPL240315P00180000"
    ]
  }'
```

## 6. 交易端点 (需要JWT认证)

⚠️ **注意**: 以下端点需要JWT认证，请先登录获取token

### 股票下单
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/order" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "symbol": "AAPL",
    "qty": 1,
    "side": "buy",
    "type": "market",
    "time_in_force": "day"
  }'
```

### 限价股票下单
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/order" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "symbol": "AAPL",
    "qty": 1,
    "side": "buy",
    "type": "limit",
    "limit_price": 190.00,
    "time_in_force": "gtc"
  }'
```

### 期权下单
```bash
curl -X POST "${BASE_URL}/api/v1/options/order" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "option_symbol": "AAPL240315C00190000",
    "qty": 1,
    "side": "buy",
    "type": "limit",
    "limit_price": 5.50,
    "time_in_force": "day"
  }'
```

### 获取订单列表
```bash
curl -X GET "${BASE_URL}/api/v1/orders" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 获取特定状态订单
```bash
curl -X GET "${BASE_URL}/api/v1/orders?status=open&limit=50" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 取消订单
```bash
# 替换 ORDER_ID 为实际订单ID
curl -X DELETE "${BASE_URL}/api/v1/orders/{ORDER_ID}" \
  -H "Authorization: Bearer ${TOKEN}"
```

## 7. 快速交易端点 (需要JWT认证)

### 快速买入股票
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/AAPL/buy" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "qty": 1,
    "order_type": "market"
  }'
```

### 快速卖出股票
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/AAPL/sell" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "qty": 1,
    "order_type": "market"
  }'
```

### 限价快速买入
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/AAPL/buy" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "qty": 1,
    "order_type": "limit",
    "limit_price": 190.00
  }'
```

## 8. 管理员端点 (需要管理员JWT)

### 获取所有用户 (管理员)
```bash
curl -X GET "${BASE_URL}/api/v1/admin/users" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

### 删除用户 (管理员)
```bash
curl -X DELETE "${BASE_URL}/api/v1/admin/users/{USER_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

## 9. 完整测试脚本

### 自动化测试脚本
```bash
#!/bin/bash

# 设置基础URL
BASE_URL="http://localhost:8081"

echo "=== Opitios Alpaca API 完整测试 ==="

# 1. 健康检查
echo "1. 健康检查..."
curl -s "${BASE_URL}/api/v1/health" | jq '.'

# 2. 用户注册
echo "2. 用户注册..."
TIMESTAMP=$(date +%s)
REGISTER_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"testuser_${TIMESTAMP}\",
    \"email\": \"test_${TIMESTAMP}@example.com\",
    \"password\": \"TestPassword123!\",
    \"alpaca_api_key\": \"YOUR_ALPACA_API_KEY\",
    \"alpaca_secret_key\": \"YOUR_ALPACA_SECRET_KEY\",
    \"alpaca_paper_trading\": true
  }")

echo $REGISTER_RESPONSE | jq '.'

# 3. 用户登录
echo "3. 用户登录..."
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"testuser_${TIMESTAMP}\",
    \"password\": \"TestPassword123!\"
  }")

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "获取到 Token: ${TOKEN:0:50}..."

# 4. 股票报价测试
echo "4. 股票报价测试..."
curl -s -X GET "${BASE_URL}/api/v1/stocks/AAPL/quote" | jq '.'

# 5. 交易测试 (如果有有效token)
if [ "$TOKEN" != "null" ] && [ -n "$TOKEN" ]; then
    echo "5. 交易端点测试..."
    curl -s -X GET "${BASE_URL}/api/v1/orders" \
      -H "Authorization: Bearer ${TOKEN}" | jq '.'
else
    echo "5. 跳过交易测试 - 无有效token"
fi

echo "=== 测试完成 ==="
```

## 10. 错误测试用例

### 无效symbol测试
```bash
curl -X GET "${BASE_URL}/api/v1/stocks/INVALID_SYMBOL_12345/quote"
```

### 无认证访问受保护端点
```bash
curl -X GET "${BASE_URL}/api/v1/orders"
```

### 无效JWT token
```bash
curl -X GET "${BASE_URL}/api/v1/orders" \
  -H "Authorization: Bearer invalid_token_12345"
```

### 空请求体测试
```bash
curl -X POST "${BASE_URL}/api/v1/stocks/quote" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 预期响应格式

### 成功响应
```json
{
  "symbol": "AAPL",
  "bid_price": 210.1,
  "ask_price": 214.3,
  "timestamp": "2024-01-15T15:30:00Z"
}
```

### 错误响应
```json
{
  "detail": "Error message description"
}
```

### JWT Token 响应
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_info": {
    "user_id": "123",
    "username": "testuser",
    "email": "test@example.com"
  }
}
```

## 注意事项

1. **Alpaca WebSocket**: 免费版本完全支持，仅数据源有限制
2. **JWT认证**: 所有交易端点需要Bearer token
3. **公开端点**: 股票报价、账户信息无需认证
4. **Rate Limiting**: 每用户每分钟120请求
5. **Paper Trading**: 所有交易都在模拟环境执行
6. **实时数据**: IEX交易所数据，30股票符号限制

## Swagger UI 访问

- **文档地址**: http://localhost:8081/docs
- **JWT认证**: 点击右上角 "Authorize" 按钮，输入 "Bearer YOUR_TOKEN"
- **测试**: 可直接在Swagger UI中测试所有API