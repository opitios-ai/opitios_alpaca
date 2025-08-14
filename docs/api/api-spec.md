# Opitios Alpaca API 规格说明

## API 概览

本文档定义了 Opitios Alpaca 高性能交易系统的 REST API 规范。API 设计专注于交易功能，移除了复杂的用户管理，采用简化的 JWT 认证机制，支持股票和期权的高频交易操作。

### API 基本信息

- **基础URL**: `https://api.opitios-alpaca.com/v1`
- **认证方式**: JWT Bearer Token
- **数据格式**: JSON
- **API版本**: v1.0.0
- **最大并发**: 1000 个账户同时访问

## OpenAPI 规范

```yaml
openapi: 3.0.3
info:
  title: Opitios Alpaca Trading API
  description: 高性能股票和期权交易API服务
  version: 1.0.0
  contact:
    name: Opitios Support
    email: info@opitios.com
  license:
    name: MIT
    url: https://opensource.org/licenses/MIT

servers:
  - url: https://api.opitios-alpaca.com/v1
    description: 生产环境
  - url: https://staging-api.opitios-alpaca.com/v1
    description: 测试环境

security:
  - BearerAuth: []

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: "格式: Bearer {jwt_token}"

  schemas:
    # 基础响应模型
    BaseResponse:
      type: object
      properties:
        success:
          type: boolean
          description: 操作是否成功
        timestamp:
          type: string
          format: date-time
          description: 响应时间
        request_id:
          type: string
          description: 请求追踪ID

    ErrorResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            error:
              type: object
              properties:
                code:
                  type: string
                  description: 错误代码
                message:
                  type: string
                  description: 错误消息
                details:
                  type: object
                  description: 错误详情

    # 认证模型
    TokenRequest:
      type: object
      required:
        - account_id
        - api_key
        - secret_key
      properties:
        account_id:
          type: string
          description: 预配置的账户ID
          example: "ACC001"
        api_key:
          type: string
          description: Alpaca API密钥
        secret_key:
          type: string
          description: Alpaca Secret密钥
        account_type:
          type: string
          enum: [master, trading, market_data, backup]
          default: trading
          description: 账户类型

    TokenResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                access_token:
                  type: string
                  description: JWT访问令牌
                token_type:
                  type: string
                  default: "bearer"
                expires_in:
                  type: integer
                  description: 令牌过期时间（秒）
                account_id:
                  type: string
                  description: 账户ID
                permissions:
                  type: array
                  items:
                    type: string
                  description: 账户权限列表

    # 股票模型
    StockQuoteRequest:
      type: object
      required:
        - symbol
      properties:
        symbol:
          type: string
          description: 股票代码
          example: "AAPL"
        include_extended_hours:
          type: boolean
          default: false
          description: 是否包含盘前盘后数据

    MultiStockQuoteRequest:
      type: object
      required:
        - symbols
      properties:
        symbols:
          type: array
          items:
            type: string
          maxItems: 50
          description: 股票代码列表
          example: ["AAPL", "TSLA", "GOOGL"]
        include_extended_hours:
          type: boolean
          default: false

    StockQuote:
      type: object
      properties:
        symbol:
          type: string
          description: 股票代码
        bid_price:
          type: number
          format: float
          description: 买入价
        ask_price:
          type: number
          format: float
          description: 卖出价
        last_price:
          type: number
          format: float
          description: 最新价格
        bid_size:
          type: integer
          description: 买入量
        ask_size:
          type: integer
          description: 卖出量
        volume:
          type: integer
          description: 成交量
        timestamp:
          type: string
          format: date-time
          description: 数据时间戳

    # 期权模型
    OptionQuoteRequest:
      type: object
      required:
        - option_symbol
      properties:
        option_symbol:
          type: string
          description: 期权合约代码
          example: "AAPL240315C00180000"

    MultiOptionQuoteRequest:
      type: object
      required:
        - option_symbols
      properties:
        option_symbols:
          type: array
          items:
            type: string
          maxItems: 20
          description: 期权合约代码列表

    OptionQuote:
      type: object
      properties:
        option_symbol:
          type: string
          description: 期权合约代码
        underlying_symbol:
          type: string
          description: 标的股票代码
        strike_price:
          type: number
          format: float
          description: 行权价
        expiration_date:
          type: string
          format: date
          description: 到期日
        option_type:
          type: string
          enum: [call, put]
          description: 期权类型
        bid_price:
          type: number
          format: float
          description: 买入价
        ask_price:
          type: number
          format: float
          description: 卖出价
        last_price:
          type: number
          format: float
          description: 最新价格
        implied_volatility:
          type: number
          format: float
          description: 隐含波动率
        delta:
          type: number
          format: float
          description: Delta值
        gamma:
          type: number
          format: float
          description: Gamma值
        theta:
          type: number
          format: float
          description: Theta值
        vega:
          type: number
          format: float
          description: Vega值
        timestamp:
          type: string
          format: date-time

    # 订单模型
    OrderRequest:
      type: object
      required:
        - symbol
        - qty
        - side
        - type
      properties:
        symbol:
          type: string
          description: 交易代码（股票或期权）
          example: "AAPL"
        qty:
          type: number
          minimum: 0.01
          description: 交易数量
        side:
          type: string
          enum: [buy, sell]
          description: 买卖方向
        type:
          type: string
          enum: [market, limit, stop, stop_limit]
          description: 订单类型
        time_in_force:
          type: string
          enum: [day, gtc, ioc, fok]
          default: day
          description: 有效期类型
        limit_price:
          type: number
          format: float
          description: 限价（限价单必填）
        stop_price:
          type: number
          format: float
          description: 止损价（止损单必填）
        client_order_id:
          type: string
          description: 客户端订单ID
        extended_hours:
          type: boolean
          default: false
          description: 是否允许盘前盘后交易

    Order:
      type: object
      properties:
        order_id:
          type: string
          description: 订单ID
        client_order_id:
          type: string
          description: 客户端订单ID
        symbol:
          type: string
          description: 交易代码
        asset_class:
          type: string
          enum: [us_equity, us_option]
          description: 资产类别
        qty:
          type: number
          description: 订单数量
        filled_qty:
          type: number
          description: 已成交数量
        side:
          type: string
          enum: [buy, sell]
        order_type:
          type: string
          enum: [market, limit, stop, stop_limit]
        time_in_force:
          type: string
          enum: [day, gtc, ioc, fok]
        limit_price:
          type: number
          format: float
          description: 限价
        stop_price:
          type: number
          format: float
          description: 止损价
        status:
          type: string
          enum: [new, partially_filled, filled, done_for_day, canceled, expired, accepted, pending_new, accepted_for_bidding, pending_cancel, pending_replace, replaced, rejected, suspended, calculated]
          description: 订单状态
        avg_fill_price:
          type: number
          format: float
          description: 平均成交价
        created_at:
          type: string
          format: date-time
          description: 创建时间
        updated_at:
          type: string
          format: date-time
          description: 更新时间
        submitted_at:
          type: string
          format: date-time
          description: 提交时间
        filled_at:
          type: string
          format: date-time
          description: 成交时间

    # 账户和持仓模型
    Account:
      type: object
      properties:
        account_id:
          type: string
          description: 账户ID
        account_number:
          type: string
          description: 账户号码
        status:
          type: string
          enum: [ACTIVE, ACCOUNT_UPDATED, APPROVAL_PENDING, SUBMITTED, INACTIVE, ACCOUNT_CLOSED]
        currency:
          type: string
          default: "USD"
        buying_power:
          type: number
          format: float
          description: 购买力
        regt_buying_power:
          type: number
          format: float
          description: 监管购买力
        daytrading_buying_power:
          type: number
          format: float
          description: 日内交易购买力
        cash:
          type: number
          format: float
          description: 现金余额
        portfolio_value:
          type: number
          format: float
          description: 投资组合价值
        equity:
          type: number
          format: float
          description: 净资产
        last_equity:
          type: number
          format: float
          description: 上次净资产
        multiplier:
          type: integer
          description: 杠杆倍数
        pattern_day_trader:
          type: boolean
          description: 是否为模式日交易者

    Position:
      type: object
      properties:
        symbol:
          type: string
          description: 交易代码
        asset_class:
          type: string
          enum: [us_equity, us_option]
        qty:
          type: number
          description: 持仓数量
        side:
          type: string
          enum: [long, short]
          description: 持仓方向
        market_value:
          type: number
          format: float
          description: 市值
        cost_basis:
          type: number
          format: float
          description: 成本基础
        unrealized_pl:
          type: number
          format: float
          description: 未实现盈亏
        unrealized_plpc:
          type: number
          format: float
          description: 未实现盈亏百分比
        avg_entry_price:
          type: number
          format: float
          description: 平均入场价格
        current_price:
          type: number
          format: float
          description: 当前价格

paths:
  # 认证端点
  /auth/token:
    post:
      tags:
        - Authentication
      summary: 获取访问令牌
      description: 使用预配置的账户凭据获取JWT访问令牌
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TokenRequest'
      responses:
        '200':
          description: 成功获取令牌
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TokenResponse'
        '400':
          description: 请求参数错误
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '401':
          description: 账户凭据无效
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  # 系统状态端点
  /health:
    get:
      tags:
        - System
      summary: 健康检查
      description: 检查系统健康状态
      security: []
      responses:
        '200':
          description: 系统正常
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          status:
                            type: string
                            example: "healthy"
                          version:
                            type: string
                            example: "1.0.0"
                          uptime:
                            type: integer
                            description: 运行时间（秒）

  /stats:
    get:
      tags:
        - System
      summary: 系统统计
      description: 获取系统性能统计信息
      responses:
        '200':
          description: 统计信息
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          active_connections:
                            type: integer
                            description: 活跃连接数
                          total_accounts:
                            type: integer
                            description: 总账户数
                          requests_per_second:
                            type: number
                            description: 每秒请求数
                          avg_response_time:
                            type: number
                            description: 平均响应时间（毫秒）

  # 股票交易端点
  /stocks/quote/{symbol}:
    get:
      tags:
        - Stocks
      summary: 获取股票报价
      description: 获取指定股票的实时报价
      parameters:
        - name: symbol
          in: path
          required: true
          schema:
            type: string
          description: 股票代码
          example: "AAPL"
        - name: include_extended_hours
          in: query
          schema:
            type: boolean
            default: false
          description: 是否包含盘前盘后数据
      responses:
        '200':
          description: 成功获取报价
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/StockQuote'

  /stocks/quotes:
    post:
      tags:
        - Stocks
      summary: 批量获取股票报价
      description: 批量获取多只股票的实时报价
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MultiStockQuoteRequest'
      responses:
        '200':
          description: 成功获取报价
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: array
                        items:
                          $ref: '#/components/schemas/StockQuote'

  /stocks/order:
    post:
      tags:
        - Stocks
      summary: 提交股票订单
      description: 提交股票买卖订单
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OrderRequest'
      responses:
        '201':
          description: 订单提交成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Order'

  # 期权交易端点
  /options/quote/{option_symbol}:
    get:
      tags:
        - Options
      summary: 获取期权报价
      description: 获取指定期权合约的实时报价
      parameters:
        - name: option_symbol
          in: path
          required: true
          schema:
            type: string
          description: 期权合约代码
          example: "AAPL240315C00180000"
      responses:
        '200':
          description: 成功获取报价
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/OptionQuote'

  /options/quotes:
    post:
      tags:
        - Options
      summary: 批量获取期权报价
      description: 批量获取多个期权合约的实时报价
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MultiOptionQuoteRequest'
      responses:
        '200':
          description: 成功获取报价
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: array
                        items:
                          $ref: '#/components/schemas/OptionQuote'

  /options/chain/{underlying_symbol}:
    get:
      tags:
        - Options
      summary: 获取期权链
      description: 获取指定标的股票的期权链
      parameters:
        - name: underlying_symbol
          in: path
          required: true
          schema:
            type: string
          description: 标的股票代码
          example: "AAPL"
        - name: expiration_date
          in: query
          schema:
            type: string
            format: date
          description: 到期日筛选
          example: "2024-03-15"
        - name: option_type
          in: query
          schema:
            type: string
            enum: [call, put]
          description: 期权类型筛选
      responses:
        '200':
          description: 成功获取期权链
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          underlying_symbol:
                            type: string
                          expiration_dates:
                            type: array
                            items:
                              type: string
                              format: date
                          options:
                            type: array
                            items:
                              $ref: '#/components/schemas/OptionQuote'

  /options/order:
    post:
      tags:
        - Options
      summary: 提交期权订单
      description: 提交期权买卖订单
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OrderRequest'
      responses:
        '201':
          description: 订单提交成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Order'

  # 订单管理端点
  /orders:
    get:
      tags:
        - Orders
      summary: 获取订单列表
      description: 获取账户的订单列表
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [new, partially_filled, filled, canceled, expired, rejected]
          description: 订单状态筛选
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 500
            default: 50
          description: 返回数量限制
        - name: page_token
          in: query
          schema:
            type: string
          description: 分页令牌
      responses:
        '200':
          description: 成功获取订单列表
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          orders:
                            type: array
                            items:
                              $ref: '#/components/schemas/Order'
                          next_page_token:
                            type: string
                            description: 下一页令牌

  /orders/{order_id}:
    get:
      tags:
        - Orders
      summary: 获取订单详情
      description: 获取指定订单的详细信息
      parameters:
        - name: order_id
          in: path
          required: true
          schema:
            type: string
          description: 订单ID
      responses:
        '200':
          description: 成功获取订单详情
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Order'

    delete:
      tags:
        - Orders
      summary: 取消订单
      description: 取消指定的待处理订单
      parameters:
        - name: order_id
          in: path
          required: true
          schema:
            type: string
          description: 订单ID
      responses:
        '200':
          description: 订单取消成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Order'

  # 账户管理端点
  /account:
    get:
      tags:
        - Account
      summary: 获取账户信息
      description: 获取当前账户的详细信息
      responses:
        '200':
          description: 成功获取账户信息
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Account'

  /positions:
    get:
      tags:
        - Account
      summary: 获取持仓列表
      description: 获取账户的当前持仓
      responses:
        '200':
          description: 成功获取持仓列表
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        type: array
                        items:
                          $ref: '#/components/schemas/Position'

  /positions/{symbol}:
    get:
      tags:
        - Account
      summary: 获取特定持仓
      description: 获取指定交易代码的持仓信息
      parameters:
        - name: symbol
          in: path
          required: true
          schema:
            type: string
          description: 交易代码
      responses:
        '200':
          description: 成功获取持仓信息
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/BaseResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Position'

  # WebSocket 端点
  /ws/market-data:
    get:
      tags:
        - WebSocket
      summary: 市场数据WebSocket连接
      description: 建立实时市场数据WebSocket连接
      parameters:
        - name: symbols
          in: query
          schema:
            type: string
          description: 订阅的交易代码，逗号分隔
          example: "AAPL,TSLA,GOOGL"
        - name: data_type
          in: query
          schema:
            type: string
            enum: [trades, quotes, bars]
            default: "quotes"
          description: 数据类型
      responses:
        '101':
          description: WebSocket连接升级成功

  /ws/account-updates:
    get:
      tags:
        - WebSocket
      summary: 账户更新WebSocket连接
      description: 建立实时账户更新WebSocket连接
      responses:
        '101':
          description: WebSocket连接升级成功

tags:
  - name: Authentication
    description: 认证相关接口
  - name: System
    description: 系统状态接口
  - name: Stocks
    description: 股票交易接口
  - name: Options
    description: 期权交易接口
  - name: Orders
    description: 订单管理接口
  - name: Account
    description: 账户管理接口
  - name: WebSocket
    description: WebSocket实时数据接口
```

## API 使用示例

### 1. 获取访问令牌

```bash
curl -X POST https://api.opitios-alpaca.com/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC001",
    "api_key": "your_alpaca_api_key",
    "secret_key": "your_alpaca_secret_key",
    "account_type": "trading"
  }'
```

响应:
```json
{
  "success": true,
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_12345",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "account_id": "ACC001",
    "permissions": ["trade", "market_data"]
  }
}
```

### 2. 获取股票报价

```bash
curl -X GET https://api.opitios-alpaca.com/v1/stocks/quote/AAPL \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

响应:
```json
{
  "success": true,
  "timestamp": "2024-01-15T10:31:00Z",
  "request_id": "req_12346",
  "data": {
    "symbol": "AAPL",
    "bid_price": 185.25,
    "ask_price": 185.30,
    "last_price": 185.27,
    "bid_size": 100,
    "ask_size": 200,
    "volume": 1234567,
    "timestamp": "2024-01-15T10:30:58Z"
  }
}
```

### 3. 提交股票订单

```bash
curl -X POST https://api.opitios-alpaca.com/v1/stocks/order \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "qty": 100,
    "side": "buy",
    "type": "limit",
    "time_in_force": "day",
    "limit_price": 185.00,
    "client_order_id": "my_order_123"
  }'
```

响应:
```json
{
  "success": true,
  "timestamp": "2024-01-15T10:32:00Z",
  "request_id": "req_12347",
  "data": {
    "order_id": "ord_abc123",
    "client_order_id": "my_order_123",
    "symbol": "AAPL",
    "asset_class": "us_equity",
    "qty": 100,
    "filled_qty": 0,
    "side": "buy",
    "order_type": "limit",
    "time_in_force": "day",
    "limit_price": 185.00,
    "status": "new",
    "created_at": "2024-01-15T10:32:00Z",
    "submitted_at": "2024-01-15T10:32:00Z"
  }
}
```

### 4. 获取期权报价

```bash
curl -X GET https://api.opitios-alpaca.com/v1/options/quote/AAPL240315C00180000 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 5. WebSocket 连接示例

```javascript
const ws = new WebSocket('wss://api.opitios-alpaca.com/v1/ws/market-data?symbols=AAPL,TSLA&data_type=quotes');

ws.onopen = function() {
  console.log('WebSocket连接已建立');
  // 发送认证消息
  ws.send(JSON.stringify({
    action: 'auth',
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
  }));
};

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('收到实时数据:', data);
};
```

## 错误处理

### 错误码定义

| 错误码 | HTTP状态 | 描述 |
|--------|----------|------|
| INVALID_TOKEN | 401 | JWT令牌无效或过期 |
| ACCOUNT_NOT_FOUND | 404 | 账户不存在 |
| INSUFFICIENT_FUNDS | 400 | 资金不足 |
| INVALID_SYMBOL | 400 | 无效的交易代码 |
| MARKET_CLOSED | 400 | 市场已关闭 |
| ORDER_REJECTED | 400 | 订单被拒绝 |
| RATE_LIMIT_EXCEEDED | 429 | 超过频率限制 |
| INTERNAL_ERROR | 500 | 内部服务器错误 |

### 错误响应格式

```json
{
  "success": false,
  "timestamp": "2024-01-15T10:33:00Z",
  "request_id": "req_12348",
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Insufficient buying power for this order",
    "details": {
      "required_buying_power": 18500.00,
      "available_buying_power": 15000.00,
      "order_value": 18500.00
    }
  }
}
```

## 频率限制

### 全局限制
- 每秒最大请求数：10,000
- 每分钟最大请求数：600,000
- 每小时最大请求数：36,000,000

### 端点特定限制
- 市场数据端点：每秒100次
- 订单提交端点：每分钟60次
- 账户查询端点：每分钟120次

### 限制头信息
所有响应都包含以下头信息：
- `X-RateLimit-Limit`: 限制数量
- `X-RateLimit-Remaining`: 剩余请求数
- `X-RateLimit-Reset`: 重置时间戳

## WebSocket 协议

### 连接流程
1. 建立WebSocket连接
2. 发送认证消息
3. 订阅数据流
4. 接收实时数据
5. 心跳维持连接

### 消息格式

#### 认证消息
```json
{
  "action": "auth",
  "token": "jwt_token_here"
}
```

#### 订阅消息
```json
{
  "action": "subscribe",
  "data_type": "quotes",
  "symbols": ["AAPL", "TSLA", "GOOGL"]
}
```

#### 数据消息
```json
{
  "type": "quote",
  "symbol": "AAPL",
  "data": {
    "bid_price": 185.25,
    "ask_price": 185.30,
    "timestamp": "2024-01-15T10:30:58Z"
  }
}
```

## 性能特性

### 响应时间目标
- P50: < 20ms
- P95: < 50ms
- P99: < 100ms

### 可用性目标
- 系统可用性: 99.9%
- API成功率: 99.95%

### 并发支持
- 最大并发连接: 2000
- 最大并发账户: 1000
- WebSocket连接: 1000

这个API规范专为高频交易场景设计，提供了简洁高效的接口，支持股票和期权的实时交易操作。