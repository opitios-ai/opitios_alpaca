#!/usr/bin/env python3
"""
WebSocket 测试演示脚本
快速展示如何使用testing subagent创建的测试工具

运行方式:
python demo_websocket_tests.py
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

async def demo_websocket_tests():
    """演示WebSocket测试工具的使用"""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    WebSocket 双端点测试工具演示                              ║
║                        Testing Subagent 创建                                ║
╠══════════════════════════════════════════════════════════════════════════════╣

🎯 测试目标:
├─ 生产端点: ws://localhost:8091/api/v1/ws/market-data
├─ 测试端点: wss://stream.data.alpaca.markets/v2/test
├─ 测试股票: AAPL, TSLA, GOOGL, MSFT 等
├─ 测试期权: AAPL/TSLA 期权合约
└─ 验证数据: 接收速度、准确性、完整性

📋 可用的测试工具:
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # 展示测试工具
    tools = [
        {
            "name": "🚀 终极综合测试工具",
            "file": "run_comprehensive_websocket_tests.py",
            "description": "最全面的测试套件，包含所有测试项目",
            "usage": [
                "python run_comprehensive_websocket_tests.py --quick-test    # 1分钟快速测试",
                "python run_comprehensive_websocket_tests.py --full-test     # 5分钟完整测试",
                "python run_comprehensive_websocket_tests.py --custom --duration 180 --focus stock  # 自定义测试"
            ]
        },
        {
            "name": "⚡ 双端点性能测试",
            "file": "run_websocket_comprehensive_tests.py",
            "description": "专门测试两个端点的连接性能和消息吞吐量",
            "usage": [
                "python run_websocket_comprehensive_tests.py                 # 默认3分钟并行测试",
                "python run_websocket_comprehensive_tests.py --duration 300  # 5分钟测试",
                "python run_websocket_comprehensive_tests.py --production-only  # 只测生产端点"
            ]
        },
        {
            "name": "📊 股票期权数据验证",
            "file": "tests/test_stock_options_data_validation.py",
            "description": "专门验证股票和期权数据的准确性和完整性",
            "usage": [
                "python -m tests.test_stock_options_data_validation 180     # 3分钟验证测试",
                "pytest tests/test_stock_options_data_validation.py -v      # pytest运行"
            ]
        },
        {
            "name": "🌐 Web测试界面",
            "file": "static/websocket_test.html",
            "description": "浏览器中的可视化测试界面，实时监控数据流",
            "usage": [
                "访问: http://localhost:8091/static/websocket_test.html",
                "点击连接按钮，观察实时数据流",
                "支持同时连接两个端点进行对比"
            ]
        },
        {
            "name": "🧪 pytest测试套件",
            "file": "tests/test_websocket_dual_endpoint_comprehensive.py",
            "description": "标准的pytest测试，可集成到CI/CD",
            "usage": [
                "pytest tests/test_websocket_dual_endpoint_comprehensive.py -v",
                "pytest tests/ -k websocket -v                              # 运行所有websocket测试"
            ]
        }
    ]
    
    for i, tool in enumerate(tools, 1):
        print(f"\n{i}. {tool['name']}")
        print(f"   文件: {tool['file']}")
        print(f"   说明: {tool['description']}")
        print(f"   用法:")
        for usage in tool['usage']:
            print(f"     {usage}")
    
    print(f"""
📈 测试报告示例:
╔══════════════════════════════════════════════════════════════════════════════╗
║                      WebSocket双端点系统测试报告                              ║
║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
╠══════════════════════════════════════════════════════════════════════════════╣

⚡ 连接性能测试结果
├─ 生产端点:
│  ├─ 连接时间: 0.123秒
│  ├─ 消息速率: 15.24 msg/s
│  ├─ 成功率: 98.5%
│  └─ 符号数: 8
├─ Alpaca端点:
│  ├─ 连接时间: 0.456秒
│  ├─ 消息速率: 2.15 msg/s
│  ├─ 成功率: 95.2%
│  └─ 符号数: 4
└─ 推荐: 生产端点性能更佳

📊 股票期权数据验证结果
├─ 股票数据覆盖: 85% (生产端点) vs 60% (Alpaca端点)
├─ 期权数据覆盖: 45% (生产端点) vs 0% (Alpaca端点)
└─ 推荐: 使用生产端点获得完整数据支持

✅ 测试结论
├─ 整体状态: 全部通过
├─ 部署建议: 推荐部署到生产环境
└─ 最佳端点: 生产端点(功能更全)
╚══════════════════════════════════════════════════════════════════════════════╝

🎯 快速开始指南:

1. 🚀 启动服务:
   cd D:\\Github\\opitios_alpaca
   venv\\Scripts\\activate
   python main.py

2. ⚡ 运行快速测试 (推荐首次使用):
   python run_comprehensive_websocket_tests.py --quick-test

3. 🔬 运行完整测试:
   python run_comprehensive_websocket_tests.py --full-test

4. 🌐 查看Web界面:
   http://localhost:8091/static/websocket_test.html

5. 📄 查看详细指南:
   打开 WEBSOCKET_TESTING_GUIDE.md 文件

⚠️ 注意事项:
- 确保FastAPI服务在8091端口运行
- 市场开盘时间测试数据更丰富
- 首次运行建议使用 --quick-test 选项
- 生产环境部署前务必运行 --full-test

📧 如需技术支持，请提供:
- 测试报告文件 (.txt)
- 测试数据文件 (.json)  
- 运行命令和错误信息
- 网络连接状态
""")

def check_requirements():
    """检查运行环境"""
    print("🔍 检查运行环境...")
    
    # 检查Python版本
    if sys.version_info < (3.7):
        print("❌ Python版本过低，需要3.7+")
        return False
    else:
        print(f"✅ Python版本: {sys.version.split()[0]}")
    
    # 检查依赖包
    required_packages = ['websockets', 'aiohttp', 'pytest']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    # 检查测试文件
    test_files = [
        "run_comprehensive_websocket_tests.py",
        "run_websocket_comprehensive_tests.py", 
        "tests/test_websocket_dual_endpoint_comprehensive.py",
        "tests/test_stock_options_data_validation.py",
        "static/websocket_test.html"
    ]
    
    project_root = Path(__file__).parent
    missing_files = []
    
    for file_path in test_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} 未找到")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  缺少测试文件: {len(missing_files)}个")
        return False
    
    print("\n🎉 环境检查完成，可以开始测试!")
    return True

async def run_quick_demo():
    """运行快速演示测试"""
    print("\n🚀 运行快速演示测试...")
    
    try:
        # 导入测试类进行简单验证
        from tests.test_websocket_dual_endpoint_comprehensive import DualEndpointWebSocketTester
        
        print("✅ 测试模块导入成功")
        
        # 创建测试器实例
        tester = DualEndpointWebSocketTester()
        print("✅ 测试器创建成功")
        
        # 验证端点配置
        print(f"✅ 生产端点: {tester.PRODUCTION_WS_URL}")
        print(f"✅ 测试端点: {tester.TEST_WS_URL}")
        print(f"✅ 测试股票: {', '.join(tester.TEST_STOCKS[:5])}...")
        print(f"✅ 测试期权: {len(tester.TEST_OPTIONS)} 个合约")
        
        print("""
🎯 演示完成! 测试工具已就绪

要运行实际测试，请使用以下命令:

快速测试 (1分钟):
  python run_comprehensive_websocket_tests.py --quick-test

完整测试 (5分钟):  
  python run_comprehensive_websocket_tests.py --full-test

自定义测试:
  python run_comprehensive_websocket_tests.py --custom --duration 180 --focus stock

Web界面测试:
  访问 http://localhost:8091/static/websocket_test.html (需要先启动服务)
        """)
        
    except Exception as e:
        print(f"❌ 演示测试失败: {e}")
        print("请确保已正确安装所有依赖并在项目根目录运行")

if __name__ == "__main__":
    print("🔧 WebSocket 测试工具演示")
    print("=" * 50)
    
    # 检查环境
    if not check_requirements():
        print("\n❌ 环境检查失败，请修复问题后重新运行")
        sys.exit(1)
    
    # 运行演示
    try:
        asyncio.run(demo_websocket_tests())
        asyncio.run(run_quick_demo())
    except KeyboardInterrupt:
        print("\n⚠️ 演示被用户中断")
    except Exception as e:
        print(f"\n❌ 演示过程发生错误: {e}")
    finally:
        print("\n👋 演示结束，祝测试顺利!")