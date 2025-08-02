# 🚀 Opitios Alpaca Trading Service 设置指南

这是一个基于 FastAPI 的 Alpaca 股票和期权交易服务，支持实时 WebSocket 数据流。

## 📋 快速开始

### 1. 克隆项目
```bash
git clone <your-repo-url>
cd opitios_alpaca
```

### 2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置 API 密钥

#### 方法一：使用配置文件（推荐）
1. 复制配置模板:
```bash
cp config.example.py config_local.py
```

2. 编辑 `config_local.py` 并填入你的 Alpaca API 密钥:
```python
class Settings(BaseSettings):
    alpaca_api_key: str = "YOUR_ACTUAL_API_KEY"
    alpaca_secret_key: str = "YOUR_ACTUAL_SECRET_KEY"
    # ... 其他配置
```

#### 方法二：使用环境变量
1. 复制环境变量模板:
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件并填入你的配置:
```bash
ALPACA_API_KEY=your_actual_api_key_here
ALPACA_SECRET_KEY=your_actual_secret_key_here
```

### 5. 获取 Alpaca API 密钥

1. 访问 [Alpaca Markets](https://alpaca.markets/)
2. 注册并登录你的账户
3. 进入 "Paper Trading" 模式（推荐用于测试）
4. 在 API 设置中生成你的密钥对：
   - API Key ID
   - Secret Key

### 6. 启动服务
```bash
python main.py
```

或使用 uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### 7. 访问服务

- **API 文档**: http://localhost:8080/docs
- **WebSocket 测试页面**: http://localhost:8080/static/websocket_test.html
- **健康检查**: http://localhost:8080/api/v1/health

## 🔧 配置选项

### Alpaca API 配置
- `alpaca_api_key`: 你的 Alpaca API 密钥
- `alpaca_secret_key`: 你的 Alpaca 秘密密钥
- `alpaca_base_url`: API 基础URL（Paper Trading: https://paper-api.alpaca.markets）
- `alpaca_paper_trading`: 是否使用模拟交易模式

### 服务配置
- `host`: 服务监听地址（默认: 0.0.0.0）
- `port`: 服务端口（默认: 8081）
- `debug`: 调试模式（默认: True）

### 数据配置
- `real_data_only`: 仅使用真实数据（默认: True）
- `enable_mock_data`: 启用模拟数据（默认: False）
- `strict_error_handling`: 严格错误处理（默认: True）

## 🔐 安全配置

### JWT 配置
```python
jwt_secret: str = "your-unique-secret-key-here"  # 请修改为你的密钥
jwt_algorithm: str = "HS256"
jwt_expiration_hours: int = 24
```

### Redis 配置（可选）
```python
redis_host: str = "localhost"
redis_port: int = 6379
redis_password: Optional[str] = None
```

## 🧪 测试功能

### 1. 获取演示 JWT Token
```bash
curl http://localhost:8080/api/v1/auth/demo-token
```

### 2. 测试股票报价
```bash
curl -X POST "http://localhost:8080/api/v1/stocks/quote" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "AAPL"}'
```

### 3. 测试 WebSocket 连接
打开浏览器访问: `http://localhost:8080/static/websocket_test.html`

## 📡 WebSocket 功能

### 特性
- ✅ 实时股票报价数据流
- ✅ 支持 Alpaca Paper Trading API
- ✅ IEX 数据源（免费账户）
- ✅ 默认股票: AAPL, TSLA, GOOGL, MSFT, AMZN, NVDA, META, SPY
- ✅ 模拟期权数据
- ✅ 连接状态监控
- ✅ 心跳检测

### 限制
- 免费账户限制: 30个股票代码
- 单一 WebSocket 连接
- 仅限 IEX 交易所数据

## 🛠️ 开发模式

### 运行测试
```bash
pytest
```

### 代码风格检查
```bash
# 如果你有 flake8 或 black
flake8 app/
black app/
```

## 📁 项目结构

```
opitios_alpaca/
├── app/                    # 应用核心代码
│   ├── alpaca_client.py   # Alpaca API 客户端
│   ├── auth_routes.py     # 认证路由
│   ├── websocket_routes.py # WebSocket 路由
│   └── ...
├── static/                # 静态文件
│   └── websocket_test.html # WebSocket 测试页面
├── tests/                 # 测试文件
├── config.py             # 主配置文件
├── config_local.py       # 本地配置（你的密钥）
├── .env.example          # 环境变量模板
└── requirements.txt      # 依赖列表
```

## ⚠️ 注意事项

1. **安全性**: 
   - 永远不要将你的真实 API 密钥提交到版本控制
   - 使用 Paper Trading 模式进行测试
   - 定期轮换你的 API 密钥

2. **生产环境**:
   - 修改默认的 JWT 密钥
   - 启用 HTTPS
   - 配置适当的 CORS 设置
   - 设置合适的日志级别

3. **限制**:
   - 遵守 Alpaca API 的使用限制
   - 注意免费账户的数据限制

## 🆘 故障排除

### 常见问题

1. **"Invalid API credentials"**
   - 检查你的 API 密钥是否正确
   - 确认使用的是 Paper Trading 环境的密钥

2. **WebSocket 连接失败**
   - 检查服务是否正在运行
   - 确认防火墙设置
   - 查看浏览器控制台错误

3. **"Demo mode with simulated data"**
   - 这是正常的，表示未配置真实 API 密钥
   - 系统将使用模拟数据进行演示

### 查看日志
```bash
tail -f logs/alpaca_service.log
```

## 📞 支持

如果遇到问题，请查看:
1. API 文档: http://localhost:8080/docs
2. 检查日志文件
3. 确认配置是否正确

## 🤝 贡献

欢迎贡献代码! 请确保:
1. 遵循现有的代码风格
2. 添加适当的测试
3. 更新相关文档