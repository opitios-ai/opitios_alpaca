# Opitios Alpaca Trading Service

多用户Alpaca交易API服务，支持100并发用户，具备完整的认证、rate limiting、用户隔离和实时市场数据功能。

## 🚀 功能特性

### 核心功能
- **多用户支持**: 支持100个并发用户同时交易  
- **JWT认证**: 安全的token-based认证系统
- **Rate Limiting**: 基于Redis/内存的智能限流
- **用户隔离**: 完全隔离的用户数据和凭据
- **连接池管理**: 高性能Alpaca API连接池
- **实时数据**: WebSocket实时市场数据推送
- **完整日志**: 结构化JSON日志，按用户分类

### 支持的操作
- **股票交易**: 市价单、限价单、止损单
- **期权交易**: 期权链查询、期权报价
- **账户管理**: 账户信息、持仓查询、订单历史
- **市场数据**: 实时报价、历史数据、批量查询

## 📋 系统要求

- Python 3.8+
- Redis Server (可选，用于分布式rate limiting)
- MySQL/SQLite (用户数据存储)
- Alpaca Trading API账户

## 🛠 安装配置

### 1. 环境设置

```bash
# 克隆仓库
git clone <repository-url>
cd opitios_alpaca

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置文件

编辑 `config.py` 文件设置你的配置：

```python
class Settings(BaseSettings):
    # Alpaca API配置
    alpaca_api_key: str = "YOUR_ALPACA_API_KEY"
    alpaca_secret_key: str = "YOUR_ALPACA_SECRET_KEY"  
    alpaca_base_url: str = "https://paper-api.alpaca.markets"  # Paper trading
    alpaca_paper_trading: bool = True
    
    # JWT配置
    jwt_secret: str = "your-strong-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Redis配置 (可选)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Rate Limiting配置
    default_rate_limit: int = 120  # 每分钟120个请求
    rate_limit_window: int = 60    # 60秒窗口
```

### 3. 数据库初始化

系统使用SQLite作为默认数据库，首次运行时会自动创建表结构。如需使用MySQL，请修改 `app/user_manager.py` 中的 `DATABASE_URL`。

### 4. Redis设置 (可选)

如果使用Redis进行分布式rate limiting：

```bash
# 安装Redis (Windows)
# 下载并安装Redis for Windows

# 启动Redis服务
redis-server

# 或使用Docker
docker run -d -p 6379:6379 redis:alpine
```

## 🏃‍♂️ 运行服务

### 1. 验证系统

运行系统验证测试：

```bash
python test_system_startup.py
```

预期输出：
```
============================================================
opitios_alpaca 系统验证测试
============================================================
1. 测试基本导入...
   [OK] 配置加载成功: Opitios Alpaca Trading Service
   [OK] 中间件导入成功
   [OK] 用户管理导入成功
   [OK] 连接池导入成功
   [OK] Alpaca客户端导入成功
   [OK] FastAPI应用导入成功

2. 测试JWT功能...
   [OK] JWT Token创建成功
   [OK] JWT Token验证成功

... (更多测试)

============================================================
测试结果: 7 通过, 0 失败
============================================================
[SUCCESS] 所有测试通过！系统准备就绪。
```

### 2. 启动开发服务器

```bash
# 开发模式（自动重载）
uvicorn main:app --host 0.0.0.0 --port 8081 --reload

# 或使用配置文件中的设置
python -c "from main import app; import uvicorn; from config import settings; uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.debug)"
```

### 3. 生产部署

```bash
# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8081 --workers 4

# 使用Gunicorn (推荐)
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8081
```

## 📚 API使用指南

### 1. 用户注册

```bash
curl -X POST "http://localhost:8081/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "trader1",
    "password": "securepassword123",
    "alpaca_api_key": "ALPACA_API_KEY",
    "alpaca_secret_key": "ALPACA_SECRET_KEY",
    "alpaca_paper_trading": true
  }'
```

### 2. 用户登录

```bash
curl -X POST "http://localhost:8081/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader1",
    "password": "securepassword123"
  }'
```

响应：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user-id-123",
    "username": "trader1",
    "email": "user@example.com",
    "role": "standard",
    "permissions": {...}
  }
}
```

### 3. 获取股票报价

```bash
curl -X GET "http://localhost:8081/api/v1/stocks/quote?symbol=AAPL" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 4. 批量获取报价

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/quotes/batch" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA", "GOOGL", "MSFT"]
  }'
```

### 5. 下单交易

```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "qty": 10,
    "side": "buy",
    "type": "market",
    "time_in_force": "day"
  }'
```

### 6. 获取期权链

```bash
curl -X GET "http://localhost:8081/api/v1/options/chain?underlying_symbol=AAPL" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 📊 系统监控

### 1. 健康检查

```bash
curl -X GET "http://localhost:8081/api/v1/health"
```

### 2. 测试连接

```bash
curl -X GET "http://localhost:8081/api/v1/test-connection" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. 账户信息

```bash
curl -X GET "http://localhost:8081/api/v1/account" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔧 Rate Limiting

系统提供多层级的rate limiting：

### 默认限制
- **通用端点**: 120 请求/分钟
- **股票报价**: 60 请求/分钟
- **批量报价**: 30 请求/分钟
- **交易订单**: 10 请求/分钟

### Response Headers
每个请求都会返回rate limiting信息：
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1699123456
```

### 429错误响应
```json
{
  "detail": "Rate limit exceeded",
  "limit": 60,
  "remaining": 0,
  "reset_time": 1699123456
}
```

## 🔐 安全特性

### 1. JWT认证
- HS256算法签名
- 24小时token有效期
- 自动刷新机制

### 2. 凭据加密
- Fernet对称加密存储Alpaca凭据
- 运行时解密，内存中明文时间最短

### 3. 用户隔离
- 完全独立的用户上下文
- 连接池按用户隔离
- 数据访问权限控制

### 4. 输入验证
- Pydantic模型验证
- SQL注入防护
- XSS防护

## 📈 性能优化

### 1. 连接池
- 每用户最多5个连接
- 智能连接复用
- 自动健康检查
- 空闲连接清理

### 2. 缓存策略
- Redis缓存市场数据
- 内存缓存用户会话
- 智能缓存失效

### 3. 并发处理
- 异步I/O操作
- 连接池管理
- 非阻塞请求处理

## 🛠 开发和测试

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_middleware.py -v

# 运行带覆盖率的测试
python -m pytest tests/ --cov=app --cov-report=html
```

### 代码质量

```bash
# 代码格式化
black app/ tests/

# 类型检查
mypy app/

# 代码风格检查
flake8 app/ tests/
```

## 📁 项目结构

```
opitios_alpaca/
├── app/
│   ├── __init__.py
│   ├── middleware.py          # 认证、限流、日志中间件
│   ├── user_manager.py        # 用户管理和数据库
│   ├── connection_pool.py     # Alpaca连接池管理
│   ├── alpaca_client.py       # Alpaca API客户端
│   ├── logging_config.py      # 日志配置
│   └── models.py              # Pydantic数据模型
├── tests/
│   ├── test_auth.py           # 认证测试
│   ├── test_middleware.py     # 中间件测试
│   ├── test_user_isolation.py # 用户隔离测试
│   └── ...
├── config.py                  # 配置文件
├── main.py                    # FastAPI应用主文件
├── requirements.txt           # Python依赖
├── test_system_startup.py     # 系统验证脚本
└── README.md                  # 本文档
```

## 🔍 故障排除

### 1. 导入错误
如果遇到导入错误，检查虚拟环境是否正确激活：
```bash
# 检查Python路径
which python
# 或
where python

# 重新安装依赖
pip install -r requirements.txt
```

### 2. Redis连接失败
如果看到Redis连接错误，系统会自动降级到内存rate limiting：
```bash
# 检查Redis服务状态
redis-cli ping

# 启动Redis服务
redis-server
```

### 3. Alpaca API错误
检查API密钥配置：
```bash
# 验证API密钥
curl -u "YOUR_API_KEY:YOUR_SECRET_KEY" \
  https://paper-api.alpaca.markets/v2/account
```

### 4. 数据库错误
检查数据库文件权限：
```bash
# 检查SQLite文件
ls -la users.db

# 删除并重新创建
rm users.db
python -c "from app.user_manager import Base, engine; Base.metadata.create_all(bind=engine)"
```

## 📞 支持和贡献

### 常见问题
1. **Q: 如何增加并发用户数？**
   A: 修改 `connection_pool.py` 中的 `max_connections_per_user` 参数

2. **Q: 如何自定义rate limiting？**
   A: 修改 `middleware.py` 中的 `endpoint_limits` 配置

3. **Q: 如何切换到实盘交易？**
   A: 设置 `alpaca_paper_trading: false` 并使用实盘API密钥

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看用户日志  
tail -f logs/users/user_123.log

# 查看性能日志
tail -f logs/performance.log
```

## 📜 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🔄 版本历史

### v1.0.0 (2025-01-31)
- ✅ 多用户架构完成
- ✅ JWT认证系统
- ✅ Rate limiting实现
- ✅ 连接池管理
- ✅ 完整日志系统
- ✅ 用户隔离机制
- ✅ Alpaca API集成
- ✅ 测试套件完成

---

🚀 **准备开始交易！** 系统已通过所有验证测试，可以安全地支持多用户并发交易。