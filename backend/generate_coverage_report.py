"""
测试覆盖率报告生成脚本
"""
import subprocess
import sys
import os
import re


def run_tests_with_coverage():
    """运行测试并生成覆盖率报告"""

    print("=" * 70)
    print("Financial Asset QA System - 测试覆盖率报告")
    print("=" * 70)

    # 切换到backend目录
    backend_dir = os.path.join(os.path.dirname(__file__), '..')
    os.chdir(backend_dir)

    # 运行测试
    print("\n[1/2] 运行测试套件...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v",
         "--cov=app", "--cov-report=term-missing", "--cov-report=html",
         "--cov-report=json", "-x"],  # -x: stop on first failure
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.stderr:
        print(result.stderr)

    # 解析覆盖率
    print("\n[2/2] 生成覆盖率报告...")

    coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', result.stdout)

    if coverage_match:
        coverage = int(coverage_match.group(1))

        print(f"\n{'=' * 70}")
        print(f"测试覆盖率: {coverage}%")
        print(f"{'=' * 70}")

        if coverage >= 90:
            print(f"✅ 覆盖率达标 (>= 90%)")
            status = "PASS"
        elif coverage >= 80:
            print(f"⚠️  覆盖率接近达标 (80-89%)")
            print(f"需要提高: {90 - coverage}%")
            status = "WARN"
        else:
            print(f"❌ 覆盖率未达标 (< 80%)")
            print(f"需要提高: {90 - coverage}%")
            status = "FAIL"

        # 统计测试数量
        passed_match = re.search(r'(\d+) passed', result.stdout)
        failed_match = re.search(r'(\d+) failed', result.stdout)

        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        total = passed + failed

        print(f"\n测试统计:")
        print(f"  总测试数: {total}")
        print(f"  通过: {passed}")
        print(f"  失败: {failed}")
        print(f"  通过率: {(passed/total*100):.1f}%")

        print(f"\n详细报告:")
        print(f"  HTML: htmlcov/index.html")
        print(f"  JSON: coverage.json")

        # 生成总结
        print(f"\n{'=' * 70}")
        print(f"总结: {status}")
        print(f"{'=' * 70}")

        return coverage >= 90

    else:
        print("❌ 无法解析覆盖率数据")
        return False


if __name__ == "__main__":
    success = run_tests_with_coverage()
    sys.exit(0 if success else 1)
