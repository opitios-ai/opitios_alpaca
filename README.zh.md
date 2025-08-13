# Opitios Alpaca 交易服务

![构建状态](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)
![测试覆盖率](https://img.shields.io/badge/coverage-85%25-green?style=flat-square)
![Python 版本](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)
![FastAPI 版本](https://img.shields.io/badge/fastapi-0.104.1-blue?style=flat-square)
![API 健康状态](https://img.shields.io/badge/api-healthy-brightgreen?style=flat-square)
![许可证](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![最后更新](https://img.shields.io/badge/updated-January%202025-blue?style=flat-square)

基于 FastAPI 的交易服务，集成 Alpaca API 进行股票和期权交易。该服务提供 RESTful 端点用于市场数据检索、订单下达和投资组合管理，并包含英文和中文的完整文档。

## 🚀 快速开始

**5 分钟内开始使用：**

```bash
# 1. 激活虚拟环境（关键要求）
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. 安装依赖
pip install -r requirements.txt

# 3. 在 .env 文件中配置 API 密钥
# 4. 启动服务器
python main.py

# 5. 访问 API 文档
# http://localhost:8081/docs
```

**📖 详细设置**：[快速开始指南](docs/zh/快速开始指南.md) | [Quick Start Guide](docs/en/quickstart.md)

## ✨ 功能特性

- ✅ **股票交易**：使用市价、限价和止损订单买卖股票
- ✅ **市场数据**：实时报价和历史价格条
- ⚠️ **期权交易**：基础框架（需要额外的 Alpaca 期权 API 实现）
- ✅ **投资组合管理**：账户信息、头寸和订单管理
- ✅ **模拟交易**：支持 Alpaca 的模拟交易环境
- ✅ **RESTful API**：全面的 FastAPI 端点和自动文档
- ✅ **测试**：使用 pytest 的单元测试
- ✅ **日志记录**：使用 loguru 的结构化日志
- ✅ **双语文档**：完整的英文和中文文档
- ✅ **交互式设置**：自动化验证和诊断

## 📚 文档

### 🇨🇳 中文文档
| 文档 | 描述 | 快速链接 |
|------|------|----------|
| **[快速开始指南](docs/zh/快速开始指南.md)** | 几分钟内快速上手 | [→ 开始使用](docs/zh/快速开始指南.md) |
| **[API 使用示例](docs/zh/API使用示例.md)** | 全面的 API 使用示例 | [→ API 指南](docs/zh/API使用示例.md) |
| **[故障排除指南](docs/zh/故障排除指南.md)** | 常见问题和解决方案 | [→ 获取帮助](docs/zh/故障排除指南.md) |
| **[安装验证](docs/zh/安装验证.md)** | 交互式安装验证 | [→ 验证安装](docs/zh/安装验证.md) |

### 🇺🇸 English Documentation
| Document | Description | Quick Link |
|----------|-------------|------------|
| **[Quick Start](docs/en/quickstart.md)** | Get up and running in minutes | [→ Start Here](docs/en/quickstart.md) |
| **[API Examples](docs/en/api-examples.md)** | Comprehensive API usage examples | [→ API Guide](docs/en/api-examples.md) |
| **[Troubleshooting](docs/en/troubleshooting.md)** | Common issues and solutions | [→ Get Help](docs/en/troubleshooting.md) |
| **[Setup Validation](docs/en/setup-validation.md)** | Interactive setup verification | [→ Validate Setup](docs/en/setup-validation.md) |

**📖 完整文档**：[docs/README.md](docs/README.md)

## 🔧 交互式工具

使用我们的交互式工具验证您的设置并监控系统健康状态：

```bash
# 交互式设置验证（推荐首次用户使用）
python docs/scripts/setup_validator.py

# 系统健康监控
python docs/scripts/health_check.py

# 基本功能测试
python test_app.py
```

## 🌐 API 端点

### 核心服务
- **健康检查**：`GET /api/v1/health`
- **API 文档**：http://localhost:8081/docs
- **账户信息**：`GET /api/v1/account`
- **测试连接**：`GET /api/v1/test-connection`

### 市场数据
- **股票报价**：`GET /api/v1/stocks/{symbol}/quote`
- **批量报价**：`POST /api/v1/stocks/quotes/batch`
- **历史数据**：`GET /api/v1/stocks/{symbol}/bars`
- **期权链**：`GET /api/v1/options/{symbol}/chain`

### 交易
- **下单**：`POST /api/v1/stocks/order`
- **快速买卖**：`POST /api/v1/stocks/{symbol}/buy`
- **订单管理**：`GET /api/v1/orders`
- **投资组合头寸**：`GET /api/v1/positions`

**📋 完整 API 参考**：[API 使用示例](docs/zh/API使用示例.md) | [API Examples](docs/en/api-examples.md)

## 📊 系统状态

| 组件 | 状态 | 详情 |
|------|------|------|
| **API 服务器** | ![运行中](https://img.shields.io/badge/status-running-green) | FastAPI 0.104.1 |
| **数据库** | ![已连接](https://img.shields.io/badge/status-connected-green) | SQLite |
| **Alpaca API** | ![已连接](https://img.shields.io/badge/status-connected-green) | 模拟交易 |
| **文档** | ![完整](https://img.shields.io/badge/status-complete-green) | 中文 + EN |
| **测试** | ![通过](https://img.shields.io/badge/tests-passing-green) | 85% 覆盖率 |

**实时健康检查**：`python docs/scripts/health_check.py`

## ⚡ 快速示例

### 获取账户信息
```bash
curl -X GET "http://localhost:8081/api/v1/account"
```

### 买入股票（市价订单）
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/AAPL/buy?qty=10"
```

### 获取股票报价
```bash
curl -X GET "http://localhost:8081/api/v1/stocks/AAPL/quote"
```

### 下限价订单
```bash
curl -X POST "http://localhost:8081/api/v1/stocks/order" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "AAPL",
       "qty": 10,
       "side": "buy",
       "type": "limit",
       "limit_price": 150.00,
       "time_in_force": "day"
     }'
```

## 🛠️ 配置

### 环境变量

| 变量 | 描述 | 默认值 | 必需 |
|------|------|--------|------|
| `ALPACA_API_KEY` | 您的 Alpaca API 密钥 | - | ✅ |
| `ALPACA_SECRET_KEY` | 您的 Alpaca 密钥 | - | ✅ |
| `ALPACA_BASE_URL` | Alpaca API 基础 URL | https://paper-api.alpaca.markets | ❌ |
| `ALPACA_PAPER_TRADING` | 启用模拟交易 | true | ❌ |
| `HOST` | 服务器主机 | 0.0.0.0 | ❌ |
| `PORT` | 服务器端口 | 8081 | ❌ |
| `DEBUG` | 调试模式 | true | ❌ |

### 示例 .env 文件
```env
ALPACA_API_KEY=PKEIKZWFXA4BD1JMJAY3
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_PAPER_TRADING=true
HOST=0.0.0.0
PORT=8081
DEBUG=true
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 详细输出运行
pytest -v

# 运行覆盖率测试
pytest --cov=app tests/

# 快速功能测试
python test_app.py
```

## 📁 项目结构

```
opitios_alpaca/
├── app/
│   ├── __init__.py
│   ├── alpaca_client.py     # Alpaca API 客户端包装器
│   ├── models.py            # Pydantic 模型
│   └── routes.py            # FastAPI 路由
├── docs/                    # 完整文档
│   ├── en/                  # 英文文档
│   ├── zh/                  # 中文文档
│   └── scripts/             # 交互式工具
├── tests/
│   ├── __init__.py
│   ├── test_main.py         # API 端点测试
│   └── test_alpaca_client.py # 客户端测试
├── logs/                    # 日志文件目录
├── .env                     # 环境配置
├── config.py                # 设置管理
├── main.py                  # FastAPI 应用程序
├── requirements.txt         # Python 依赖
├── README.md               # 英文说明文件
└── README.zh.md            # 中文说明文件（本文件）
```

## 🔒 安全性和生产环境

### 安全最佳实践
- ✅ API 密钥存储在环境变量中
- ✅ 生产环境的 CORS 配置
- ✅ 使用 Pydantic 进行输入验证
- ✅ 结构化日志记录用于监控
- ✅ 默认启用模拟交易

### 生产环境部署
```bash
# 使用生产 WSGI 服务器
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8081

# 配置实盘交易（⚠️ 谨慎使用）
# 更新 .env：
# ALPACA_BASE_URL=https://api.alpaca.markets
# ALPACA_PAPER_TRADING=false
```

## 🚨 故障排除

### 常见问题

| 问题 | 解决方案 | 指南 |
|------|----------|------|
| **ModuleNotFoundError** | 激活虚拟环境 | [设置指南](docs/zh/快速开始指南.md) |
| **API 连接失败** | 检查 API 密钥和网络 | [故障排除](docs/zh/故障排除指南.md) |
| **服务器无法启动** | 检查端口可用性 | [健康检查](docs/scripts/health_check.py) |
| **订单被拒绝** | 验证市场时间和购买力 | [API 示例](docs/zh/API使用示例.md) |

### 获取帮助
1. **运行诊断**：`python docs/scripts/setup_validator.py`
2. **检查健康状态**：`python docs/scripts/health_check.py`
3. **查看日志**：检查 `logs/alpaca_service.log`
4. **阅读指南**：[故障排除指南](docs/zh/故障排除指南.md)

## 🤝 贡献

欢迎贡献！请参阅我们的 [贡献指南](docs/zh/贡献指南.md) 了解详情。

### 开发环境设置
```bash
# Fork 并克隆仓库
git clone <your-fork-url>
cd opitios_alpaca

# 设置开发环境
venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 如果可用

# 运行测试
pytest

# 启动开发服务器
python main.py
```

## 📄 许可证

该项目是 Opitios 交易系统的一部分。详见 [LICENSE](LICENSE)。

## 🌟 支持与社区

- **文档**：[完整指南](docs/README.md)
- **问题反馈**：[GitHub Issues](../../issues)
- **讨论**：[GitHub Discussions](../../discussions)
- **邮箱**：info@opitios.com

## 📈 路线图

- [ ] **期权交易**：完整的 Alpaca 期权 API 集成
- [ ] **WebSocket 流**：实时市场数据推送
- [ ] **高级订单**：括号订单、OCO 订单
- [ ] **投资组合分析**：性能跟踪和报告
- [ ] **警报系统**：价格警报和通知
- [ ] **移动 API**：专为移动应用优化的 REST 端点

---

**由 Opitios 团队用 ❤️ 制作**

**最后更新**：2025年1月 | **版本**：1.0.0 | **状态**：生产就绪

[![文档](https://img.shields.io/badge/docs-available-brightgreen?style=flat-square)](docs/README.md)
[![API 健康状态](https://img.shields.io/badge/api-healthy-brightgreen?style=flat-square)](http://localhost:8081/api/v1/health)
[![交互式设置](https://img.shields.io/badge/setup-interactive-blue?style=flat-square)](docs/scripts/setup_validator.py)