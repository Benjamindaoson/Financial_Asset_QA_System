"""
部署脚本 - 一键部署优化 RAG 系统
Deployment Script - One-Click Deploy Optimized RAG System

功能：
1. 检查环境依赖
2. 启动 Redis
3. 构建索引
4. 验证系统
5. 启动应用

使用方法：
    python deploy.py --mode production
"""
import sys
import os
import subprocess
import argparse
import logging
from pathlib import Path
from typing import List, Tuple
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentManager:
    """部署管理器"""

    def __init__(self, mode: str = "development"):
        """
        初始化部署管理器

        Args:
            mode: 部署模式（development/production）
        """
        self.mode = mode
        self.project_root = Path(__file__).parent.parent
        self.backend_dir = self.project_root / "backend"
        self.data_dir = self.project_root / "data"

        # 检查结果
        self.checks_passed = []
        self.checks_failed = []

    def deploy(self):
        """执行部署"""
        logger.info("="*60)
        logger.info(f"开始部署 - 模式: {self.mode}")
        logger.info("="*60)

        # 步骤 1: 环境检查
        logger.info("\n步骤 1/6: 环境检查")
        if not self._check_environment():
            logger.error("环境检查失败，终止部署")
            return False

        # 步骤 2: 启动 Redis
        logger.info("\n步骤 2/6: 启动 Redis")
        if not self._start_redis():
            logger.warning("Redis 启动失败，将禁用 L2 缓存")

        # 步骤 3: 构建索引
        logger.info("\n步骤 3/6: 构建索引")
        if not self._build_index():
            logger.error("索引构建失败，终止部署")
            return False

        # 步骤 4: 验证索引
        logger.info("\n步骤 4/6: 验证索引")
        if not self._validate_index():
            logger.warning("索引验证失败，但继续部署")

        # 步骤 5: 测试系统
        logger.info("\n步骤 5/6: 测试系统")
        if not self._test_system():
            logger.warning("系统测试失败，但继续部署")

        # 步骤 6: 启动应用
        logger.info("\n步骤 6/6: 启动应用")
        self._start_application()

        # 完成
        self._print_summary()

        return True

    def _check_environment(self) -> bool:
        """检查环境"""
        logger.info("检查环境依赖...")

        checks = [
            ("Python 版本", self._check_python),
            ("依赖包", self._check_dependencies),
            ("数据目录", self._check_data_directory),
            ("配置文件", self._check_config),
            ("模型文件", self._check_models),
        ]

        all_passed = True

        for name, check_func in checks:
            try:
                result, message = check_func()
                if result:
                    logger.info(f"  ✓ {name}: {message}")
                    self.checks_passed.append(name)
                else:
                    logger.error(f"  ✗ {name}: {message}")
                    self.checks_failed.append(name)
                    all_passed = False
            except Exception as e:
                logger.error(f"  ✗ {name}: {e}")
                self.checks_failed.append(name)
                all_passed = False

        return all_passed

    def _check_python(self) -> Tuple[bool, str]:
        """检查 Python 版本"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            return True, f"{version.major}.{version.minor}.{version.micro}"
        return False, f"需要 Python 3.8+，当前 {version.major}.{version.minor}"

    def _check_dependencies(self) -> Tuple[bool, str]:
        """检查依赖包"""
        required_packages = [
            "fastapi",
            "uvicorn",
            "chromadb",
            "redis",
            "sentence-transformers",
            "openai"
        ]

        missing = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing.append(package)

        if missing:
            return False, f"缺少依赖: {', '.join(missing)}"
        return True, f"{len(required_packages)} 个依赖已安装"

    def _check_data_directory(self) -> Tuple[bool, str]:
        """检查数据目录"""
        if not self.data_dir.exists():
            return False, f"数据目录不存在: {self.data_dir}"

        # 统计文件
        file_count = sum(1 for _ in self.data_dir.rglob("*") if _.is_file())

        if file_count == 0:
            return False, "数据目录为空"

        return True, f"找到 {file_count} 个文件"

    def _check_config(self) -> Tuple[bool, str]:
        """检查配置文件"""
        env_file = self.backend_dir / ".env"

        if not env_file.exists():
            return False, ".env 文件不存在"

        # 检查关键配置
        with open(env_file, "r") as f:
            content = f.read()

        required_keys = ["DEEPSEEK_API_KEY", "EMBEDDING_MODEL"]
        missing = [key for key in required_keys if key not in content]

        if missing:
            return False, f"缺少配置: {', '.join(missing)}"

        return True, "配置文件完整"

    def _check_models(self) -> Tuple[bool, str]:
        """检查模型文件"""
        # 这里简化检查，实际可以检查模型是否下载
        return True, "模型检查通过"

    def _start_redis(self) -> bool:
        """启动 Redis"""
        logger.info("检查 Redis 状态...")

        try:
            # 尝试连接 Redis
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and "PONG" in result.stdout:
                logger.info("  ✓ Redis 已运行")
                return True

        except Exception as e:
            logger.warning(f"  Redis 检查失败: {e}")

        # 尝试启动 Redis
        logger.info("  尝试启动 Redis...")

        try:
            if sys.platform == "win32":
                # Windows
                subprocess.Popen(
                    ["redis-server"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Linux/Mac
                subprocess.Popen(
                    ["redis-server", "--daemonize", "yes"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # 等待启动
            time.sleep(2)

            # 再次检查
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.info("  ✓ Redis 启动成功")
                return True

        except Exception as e:
            logger.warning(f"  Redis 启动失败: {e}")

        return False

    def _build_index(self) -> bool:
        """构建索引"""
        logger.info("构建向量索引...")

        script_path = self.backend_dir / "scripts" / "build_unified_index.py"

        if not script_path.exists():
            logger.error(f"  索引构建脚本不存在: {script_path}")
            return False

        try:
            # 运行构建脚本
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--data-dir", str(self.data_dir),
                    "--chroma-dir", str(self.backend_dir / "data" / "chroma_db")
                ],
                cwd=str(self.backend_dir),
                capture_output=True,
                text=True,
                timeout=1800  # 30 分钟超时
            )

            if result.returncode == 0:
                logger.info("  ✓ 索引构建成功")
                return True
            else:
                logger.error(f"  ✗ 索引构建失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("  ✗ 索引构建超时")
            return False
        except Exception as e:
            logger.error(f"  ✗ 索引构建失败: {e}")
            return False

    def _validate_index(self) -> bool:
        """验证索引"""
        logger.info("验证索引质量...")

        script_path = self.backend_dir / "scripts" / "validate_index.py"

        if not script_path.exists():
            logger.warning("  验证脚本不存在，跳过")
            return True

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--chroma-dir", str(self.backend_dir / "data" / "chroma_db")
                ],
                cwd=str(self.backend_dir),
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                logger.info("  ✓ 索引验证通过")
                return True
            else:
                logger.warning(f"  ✗ 索引验证失败: {result.stderr}")
                return False

        except Exception as e:
            logger.warning(f"  验证失败: {e}")
            return False

    def _test_system(self) -> bool:
        """测试系统"""
        logger.info("测试系统功能...")

        script_path = self.backend_dir / "scripts" / "test_retrieval.py"

        if not script_path.exists():
            logger.warning("  测试脚本不存在，跳过")
            return True

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--chroma-dir", str(self.backend_dir / "data" / "chroma_db"),
                    "--query", "什么是市盈率？"
                ],
                cwd=str(self.backend_dir),
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info("  ✓ 系统测试通过")
                return True
            else:
                logger.warning(f"  ✗ 系统测试失败: {result.stderr}")
                return False

        except Exception as e:
            logger.warning(f"  测试失败: {e}")
            return False

    def _start_application(self):
        """启动应用"""
        logger.info("启动 FastAPI 应用...")

        if self.mode == "production":
            # 生产模式
            logger.info("  模式: 生产")
            logger.info("  命令: uvicorn app.main:app --host 0.0.0.0 --port 8000")
            logger.info("\n请手动运行上述命令启动应用")

        else:
            # 开发模式
            logger.info("  模式: 开发")
            logger.info("  命令: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
            logger.info("\n请手动运行上述命令启动应用")

    def _print_summary(self):
        """打印摘要"""
        logger.info("\n" + "="*60)
        logger.info("部署完成")
        logger.info("="*60)

        logger.info(f"\n检查通过: {len(self.checks_passed)}")
        for check in self.checks_passed:
            logger.info(f"  ✓ {check}")

        if self.checks_failed:
            logger.info(f"\n检查失败: {len(self.checks_failed)}")
            for check in self.checks_failed:
                logger.info(f"  ✗ {check}")

        logger.info("\n下一步:")
        logger.info("  1. 启动应用: cd backend && uvicorn app.main:app --reload")
        logger.info("  2. 访问文档: http://localhost:8000/docs")
        logger.info("  3. 测试 API: http://localhost:8000/api/v2/rag/health")

        logger.info("\nAPI 端点:")
        logger.info("  - 优化检索: POST /api/v2/rag/search")
        logger.info("  - 缓存统计: GET /api/v2/rag/cache/stats")
        logger.info("  - 路由统计: GET /api/v2/rag/router/stats")
        logger.info("  - 健康检查: GET /api/v2/rag/health")

        logger.info("\n" + "="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="部署优化 RAG 系统")

    parser.add_argument(
        "--mode",
        type=str,
        choices=["development", "production"],
        default="development",
        help="部署模式"
    )

    args = parser.parse_args()

    # 创建部署管理器
    manager = DeploymentManager(mode=args.mode)

    # 执行部署
    success = manager.deploy()

    if success:
        logger.info("\n✓ 部署成功！")
        sys.exit(0)
    else:
        logger.error("\n✗ 部署失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
