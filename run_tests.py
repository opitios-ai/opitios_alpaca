#!/usr/bin/env python3
"""
测试运行脚本
支持不同类型的测试执行和报告生成
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import time

# 添加Unicode处理支持
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
from unicode_handler import safe_print


def run_command(cmd, description=""):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"正在执行: {description or cmd}")
    print(f"{'='*60}")
    
    start_time = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"执行时间: {end_time - start_time:.2f}秒")
    print(f"返回码: {result.returncode}")
    
    if result.stdout:
        print(f"\n标准输出:\n{result.stdout}")
    
    if result.stderr:
        print(f"\n标准错误:\n{result.stderr}")
    
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="运行opitios_alpaca系统测试")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "performance", "e2e", "security"],
        default="all",
        help="选择测试类型"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--coverage", "-c", action="store_true", help="生成覆盖率报告")
    parser.add_argument("--html", action="store_true", help="生成HTML报告")
    parser.add_argument("--parallel", "-p", action="store_true", help="并行运行测试")
    parser.add_argument("--benchmark", "-b", action="store_true", help="运行性能基准测试")
    parser.add_argument("--fast", "-f", action="store_true", help="快速测试（跳过慢速测试）")
    
    args = parser.parse_args()
    
    # 设置项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # 基础pytest命令
    pytest_cmd = ["python", "-m", "pytest"]
    
    # 添加详细输出
    if args.verbose:
        pytest_cmd.extend(["-v", "-s"])
    else:
        pytest_cmd.append("-q")
    
    # 添加覆盖率
    if args.coverage:
        pytest_cmd.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
        if args.html:
            pytest_cmd.append("--cov-report=html")
    
    # 并行执行
    if args.parallel:
        pytest_cmd.extend(["-n", "auto"])
    
    # 快速模式
    if args.fast:
        pytest_cmd.extend(["-m", "not slow"])
    
    # 根据测试类型添加标记
    test_markers = {
        "unit": "unit",
        "integration": "integration", 
        "performance": "performance",
        "e2e": "e2e",
        "security": "security"
    }
    
    if args.type != "all" and args.type in test_markers:
        pytest_cmd.extend(["-m", test_markers[args.type]])
    
    # 添加测试目录
    pytest_cmd.append("tests/")
    
    # 执行测试
    success = True
    
    safe_print("[START] 开始运行opitios_alpaca系统测试")
    print(f"测试类型: {args.type}")
    print(f"项目目录: {project_root}")
    
    # 检查依赖
    safe_print("\n[INFO] 检查测试依赖...")
    required_packages = ["pytest", "httpx", "fastapi"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            safe_print(f"[OK] {package} - 已安装")
        except ImportError:
            safe_print(f"[FAIL] {package} - 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        safe_print(f"\n[WARN] 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    # 检查环境
    safe_print("\n[INFO] 检查测试环境...")
    
    # 检查Redis连接（可选）
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1)
        r.ping()
        safe_print("[OK] Redis - 连接正常")
    except Exception as e:
        safe_print(f"[WARN] Redis - 连接失败 ({e})，将使用内存模式")
    
    # 检查配置文件
    config_files = ["config.py", "pytest.ini"]
    for config_file in config_files:
        if os.path.exists(config_file):
            safe_print(f"[OK] {config_file} - 存在")
        else:
            safe_print(f"[WARN] {config_file} - 不存在")
    
    # 运行不同类型的测试
    if args.type == "all":
        test_suites = [
            ("unit", "单元测试"),
            ("integration", "集成测试"),
            ("e2e", "端到端测试")
        ]
        
        if args.benchmark:
            test_suites.append(("performance", "性能测试"))
        
        for test_type, description in test_suites:
            cmd = pytest_cmd.copy()
            cmd.extend(["-m", test_type])
            
            safe_print(f"\n[INFO] 运行{description}...")
            if not run_command(" ".join(cmd), f"{description}"):
                success = False
                safe_print(f"[FAIL] {description}失败")
                
                # 询问是否继续
                if input("\n是否继续运行其他测试? (y/N): ").lower() != 'y':
                    break
            else:
                safe_print(f"[OK] {description}通过")
    else:
        # 运行特定类型测试
        test_descriptions = {
            "unit": "单元测试",
            "integration": "集成测试",
            "performance": "性能测试",
            "e2e": "端到端测试",
            "security": "安全测试"
        }
        
        description = test_descriptions.get(args.type, "测试")
        print(f"\n🧪 运行{description}...")
        success = run_command(" ".join(pytest_cmd), description)
    
    # 生成测试报告
    if args.html and os.path.exists("htmlcov"):
        safe_print(f"\n[DATA] 覆盖率报告已生成: {project_root}/htmlcov/index.html")
    
    if os.path.exists("coverage.xml"):
        safe_print(f"[UP] XML覆盖率报告: {project_root}/coverage.xml")
    
    # 总结
    print(f"\n{'='*60}")
    if success:
        safe_print("[SUCCESS] 所有测试执行完成！")
        safe_print("[OK] 测试状态: 通过")
    else:
        safe_print("[FAIL] 测试执行完成，但有失败")
        safe_print("[FAIL] 测试状态: 失败")
    print(f"{'='*60}")
    
    # 额外的系统诊断信息
    if not success:
        safe_print("\n[INFO] 系统诊断信息:")
        print(f"Python版本: {sys.version}")
        print(f"工作目录: {os.getcwd()}")
        print(f"Python路径: {sys.path[:3]}...")  # 只显示前3个路径
        
        # 检查关键文件
        key_files = ["main.py", "app/middleware.py", "app/routes.py", "config.py"]
        for file_path in key_files:
            if os.path.exists(file_path):
                safe_print(f"[OK] {file_path}")
            else:
                safe_print(f"[FAIL] {file_path} - 缺失")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)