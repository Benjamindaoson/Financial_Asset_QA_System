"""
运行测试脚本
Run Tests Script
"""
import subprocess
import sys
import os

def run_tests():
    """运行所有测试并生成覆盖率报告"""

    print("=" * 60)
    print("Financial Asset QA System - 测试套件")
    print("=" * 60)

    # 切换到backend目录
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))

    # 安装测试依赖
    print("\n[1/3] 安装测试依赖...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-test.txt"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"[ERROR] 安装依赖失败: {result.stderr}")
        return False

    print("[OK] 测试依赖已安装")

    # 运行测试
    print("\n[2/3] 运行测试...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--cov=app", "--cov-report=term-missing", "--cov-report=html"],
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        print("\n[ERROR] 测试失败")
        return False

    # 生成覆盖率报告
    print("\n[3/3] 生成覆盖率报告...")

    # 解析覆盖率
    if "TOTAL" in result.stdout:
        lines = result.stdout.split('\n')
        for line in lines:
            if "TOTAL" in line:
                parts = line.split()
                if len(parts) >= 4:
                    coverage = parts[-1]
                    print(f"\n{'='*60}")
                    print(f"测试覆盖率: {coverage}")
                    print(f"{'='*60}")

                    # 检查是否达到90%
                    try:
                        coverage_value = float(coverage.rstrip('%'))
                        if coverage_value >= 90:
                            print(f"[OK] 覆盖率达标 (>= 90%)")
                        else:
                            print(f"[WARN] 覆盖率未达标 (< 90%)")
                            print(f"需要提高: {90 - coverage_value:.1f}%")
                    except:
                        pass

    print(f"\n详细报告: htmlcov/index.html")

    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
