# WebSocket 双端点系统测试指南

这份指南详细说明如何使用comprehensive testing suite测试WebSocket双端点系统，确保生产端点和Alpaca测试端点都能正常工作。

## 🎯 测试目标

本测试套件专门针对以下两个端点进行全面测试：

- **生产端点**: `ws://localhost:8091/api/v1/ws/market-data`
- **Alpaca测试端点**: `wss://stream.data.alpaca.markets/v2/test`

### 测试覆盖范围

1. **连接性能测试** - 测试连接速度、稳定性和消息吞吐量
2. **股票数据验证** - 验证不同股票符号的数据接收准确性
3. **期权数据验证** - 测试期权数据的完整性和准确性
4. **实时数据流完整性** - 验证数据流的实时性和延迟
5. **性能基准测试** - 对比两个端点的性能表现

## 📋 测试文件结构

```
opitios_alpaca/
├── run_comprehensive_websocket_tests.py          # 终极综合测试运行器
├── run_websocket_comprehensive_tests.py          # 标准测试运行器
├── tests/
│   ├── test_websocket_dual_endpoint_comprehensive.py  # 双端点性能测试
│   ├── test_stock_options_data_validation.py          # 股票期权数据验证
│   └── test_websocket_connections.py                  # 基础连接测试
├── static/
│   └── websocket_test.html                           # Web测试界面
└── WEBSOCKET_TESTING_GUIDE.md                       # 本指南
```

## 🚀 快速开始

### 1. 环境准备

确保Python虚拟环境已激活且依赖已安装：

```bash
# Windows
cd D:\Github\opitios_alpaca
venv\Scripts\activate

# Linux/Mac  
cd /path/to/opitios_alpaca
source venv/bin/activate

# 安装依赖
pip install websockets aiohttp pytest pytest-asyncio
```

### 2. 启动服务

在运行测试前，确保生产端点服务已启动：

```bash
# 启动FastAPI服务
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8091 --reload
```

验证服务运行：
- 访问 `http://localhost:8091/` 确认API服务运行
- 访问 `http://localhost:8091/static/websocket_test.html` 查看测试页面

### 3. 运行测试

#### 🏃‍♂️ 快速测试 (1分钟)

适合快速验证基本功能：

```bash
python run_comprehensive_websocket_tests.py --quick-test
```

#### 🔬 完整测试 (5分钟)

进行全面深入的测试：

```bash
python run_comprehensive_websocket_tests.py --full-test
```

#### ⚙️ 自定义测试

根据需要自定义测试参数：

```bash
# 3分钟股票专项测试
python run_comprehensive_websocket_tests.py --custom --duration 180 --focus stock

# 5分钟期权专项测试
python run_comprehensive_websocket_tests.py --custom --duration 300 --focus option

# 10分钟性能专项测试
python run_comprehensive_websocket_tests.py --custom --duration 600 --focus performance

# 详细输出模式
python run_comprehensive_websocket_tests.py --full-test --verbose
```

## 📊 测试类型详解

### 1. 连接性能测试

测试内容：
- WebSocket连接建立时间
- 消息接收速度 (messages/second)
- 连接稳定性和错误率
- 同时连接两个端点的性能对比

使用方法：
```bash
# 专注性能测试
python run_comprehensive_websocket_tests.py --custom --duration 300 --focus performance

# 或单独运行
python run_websocket_comprehensive_tests.py --duration 180 --parallel
```

### 2. 股票数据验证测试

测试内容：
- 测试股票：AAPL, TSLA, GOOGL, MSFT, AMZN, NVDA, META, SPY等
- 验证报价数据（bid/ask价格和数量）
- 验证交易数据（成交价格和数量）
- 数据覆盖率和质量分析

使用方法：
```bash
# 股票专项测试
python run_comprehensive_websocket_tests.py --custom --duration 180 --focus stock

# 或单独运行股票期权验证
python -m tests.test_stock_options_data_validation 180
```

### 3. 期权数据验证测试

测试内容：
- 测试期权：AAPL/TSLA/SPY的Call和Put期权
- 期权符号解析验证
- 期权报价和交易数据完整性
- 与标的股票的数据一致性

使用方法：
```bash
# 期权专项测试  
python run_comprehensive_websocket_tests.py --custom --duration 180 --focus option
```

### 4. 实时数据完整性测试

测试内容：
- 首条消息到达延迟
- 消息间隔分析
- 数据流连续性检查
- 延迟统计分析

### 5. Web界面测试

访问 `http://localhost:8091/static/websocket_test.html` 进行手动测试：

- 实时查看两个端点的连接状态
- 观察股票和期权数据流
- 监控消息接收统计
- 手动测试心跳和订阅功能

## 📈 测试报告解读

### 报告文件

测试完成后会生成以下文件：

```
websocket_comprehensive_test_report_YYYYMMDD_HHMMSS.txt  # 详细文本报告
websocket_comprehensive_test_data_YYYYMMDD_HHMMSS.json   # 原始JSON数据
```

### 关键指标

#### 连接性能指标
- **连接时间**: 建立WebSocket连接所需时间（应 < 5秒）
- **消息速率**: 每秒接收消息数（生产环境应 > 1 msg/s）
- **成功率**: 无错误接收消息的百分比（应 > 95%）
- **数据覆盖**: 有数据的股票/期权符号比例

#### 数据质量指标
- **股票数据覆盖**: 有数据的股票符号百分比
- **期权数据覆盖**: 有数据的期权符号百分比  
- **数据质量分数**: 0-100分，综合评估数据完整性
- **延迟统计**: 平均、中位数、最大最小延迟

#### 实时性指标
- **首条消息延迟**: 连接后到首条数据的时间
- **平均消息间隔**: 消息到达的平均间隔时间
- **最大消息间隔**: 最长的消息间隔（检测中断）

### 报告示例解读

```
⚡ 连接性能测试结果
├─ 生产端点:
│  ├─ 连接时间: 0.123秒     ✅ 优秀
│  ├─ 消息速率: 15.24 msg/s ✅ 良好  
│  ├─ 成功率: 98.5%         ✅ 优秀
│  └─ 符号数: 8             ✅ 正常

📊 股票期权数据验证结果
├─ 生产端点数据质量:
│  ├─ 股票数据覆盖: 85%     ✅ 良好
│  ├─ 期权数据覆盖: 45%     ⚠️  一般
│  └─ 总消息数: 2,150       ✅ 丰富
```

## 🔧 故障排除

### 常见问题

#### 1. 连接失败
```
❌ 生产端点连接失败: Connection refused
```

解决方法：
- 检查FastAPI服务是否启动：`http://localhost:8091/`
- 确认端口8091未被占用
- 检查防火墙设置

#### 2. 认证失败
```  
❌ Alpaca端点认证失败
```

解决方法：
- Alpaca测试端点使用测试密钥，无需真实API密钥
- 检查网络连接，确保可以访问外部HTTPS

#### 3. 数据接收为零
```
⚠️ 股票数据覆盖: 0%
```

可能原因：
- 市场闭市期间（期权和股票数据可能有限）
- 测试时间过短（建议至少60秒）
- WebSocket端点配置问题

#### 4. 测试超时
```
❌ 测试执行失败: TimeoutError
```

解决方法：
- 增加测试时长：`--duration 300`
- 检查网络稳定性
- 使用 `--verbose` 查看详细日志

### 调试技巧

#### 1. 查看详细日志
```bash
python run_comprehensive_websocket_tests.py --full-test --verbose
```

#### 2. 单独测试组件
```bash
# 只测试生产端点
python run_websocket_comprehensive_tests.py --production-only --duration 60

# 只测试Alpaca端点  
python run_websocket_comprehensive_tests.py --alpaca-only --duration 60
```

#### 3. Web界面调试
访问测试页面观察实时状态：
`http://localhost:8091/static/websocket_test.html`

#### 4. 检查服务状态
```bash
# 检查WebSocket状态API
curl http://localhost:8091/api/v1/ws/status
```

## 🎯 测试结果判断

### ✅ 优秀结果
- 连接时间 < 1秒
- 消息速率 > 5 msg/s
- 成功率 > 95%
- 股票数据覆盖 > 80%
- 期权数据覆盖 > 30%

### ⚠️ 可接受结果
- 连接时间 < 5秒
- 消息速率 > 1 msg/s
- 成功率 > 90%
- 股票数据覆盖 > 50%
- 期权数据覆盖 > 10%

### ❌ 需要改进
- 连接时间 > 10秒
- 消息速率 < 0.5 msg/s
- 成功率 < 90%
- 数据覆盖 < 30%

## 📚 进阶使用

### 1. 持续集成测试

在CI/CD流程中集成：

```yaml
# .github/workflows/websocket-test.yml
name: WebSocket Tests
on: [push, pull_request]
jobs:
  websocket-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v3
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Start service
        run: |
          python main.py &
          sleep 10
      - name: Run WebSocket tests
        run: |
          python run_comprehensive_websocket_tests.py --quick-test
```

### 2. 定期监控脚本

```bash
#!/bin/bash
# monitor_websocket.sh - 定期运行测试
while true; do
    python run_comprehensive_websocket_tests.py --quick-test --no-report
    sleep 300  # 每5分钟测试一次
done
```

### 3. 自定义测试符号

修改测试脚本中的股票和期权列表：

```python
# 在 test_stock_options_data_validation.py 中
TEST_STOCKS = ["YOUR", "CUSTOM", "SYMBOLS"]  
TEST_OPTIONS = ["YOUR_CUSTOM_OPTIONS"]
```

## 💡 最佳实践

### 1. 测试时机
- **开发阶段**: 使用快速测试验证基本功能
- **部署前**: 运行完整测试确保质量
- **生产监控**: 定期运行快速测试监控健康度

### 2. 测试环境
- 确保测试环境网络稳定
- 避免在高负载时进行性能测试
- 市场开盘时间测试数据更丰富

### 3. 结果解释
- 关注趋势变化，而非绝对数值
- 对比历史测试结果识别问题
- 结合业务需求评估测试结果

### 4. 问题反馈
遇到问题时请提供：
- 完整的测试报告文件
- 运行命令和参数
- 系统环境信息
- 网络连接状态

## 🔗 相关资源

- [WebSocket测试页面](http://localhost:8091/static/websocket_test.html)
- [API文档](http://localhost:8091/docs)
- [服务状态检查](http://localhost:8091/api/v1/ws/status)

---

**注意**: 本测试套件设计用于开发和测试环境。在生产环境使用前请确保充分了解测试影响。