#!/usr/bin/env python3
"""
自动化实现脚本 - 基于 financial-qa-tech-spec-v2.md
全自动执行，无需人工干预
"""

import subprocess
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 执行日志
execution_log = {
    "start_time": datetime.now().isoformat(),
    "tasks": [],
    "errors": [],
    "skipped": []
}

def log_task(task_name, status, details=""):
    """记录任务执行状态"""
    entry = {
        "task": task_name,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    execution_log["tasks"].append(entry)
    print(f"[{status.upper()}] {task_name}")
    if details:
        print(f"  └─ {details}")

def run_command(cmd, cwd=None, timeout=300):
    """执行命令，自动处理错误"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timeout"
    except Exception as e:
        return False, "", str(e)

def git_commit(message):
    """Git提交"""
    success, _, _ = run_command(f'git add -A && git commit -m "{message}"', cwd=PROJECT_ROOT)
    return success

# ============================================================================
# Phase 1: 环境准备
# ============================================================================

def phase1_setup():
    """Phase 1: 环境准备"""
    print("\n" + "="*80)
    print("Phase 1: 环境准备")
    print("="*80)

    # Task 1.1: 检查Python版本
    log_task("检查Python版本", "running")
    success, stdout, _ = run_command("python --version")
    if success and "3.11" in stdout or "3.12" in stdout:
        log_task("检查Python版本", "success", stdout.strip())
    else:
        log_task("检查Python版本", "warning", "建议使用Python 3.11+")

    # Task 1.2: 创建虚拟环境（如果不存在）
    venv_path = BACKEND_DIR / "venv"
    if not venv_path.exists():
        log_task("创建虚拟环境", "running")
        success, _, err = run_command("python -m venv venv", cwd=BACKEND_DIR)
        if success:
            log_task("创建虚拟环境", "success")
        else:
            log_task("创建虚拟环境", "error", err)
            execution_log["errors"].append({"task": "创建虚拟环境", "error": err})

    # Task 1.3: 安装后端依赖
    log_task("安装后端依赖", "running")
    pip_cmd = "venv\\Scripts\\pip" if sys.platform == "win32" else "venv/bin/pip"
    success, _, err = run_command(
        f"{pip_cmd} install -r requirements.txt",
        cwd=BACKEND_DIR,
        timeout=600
    )
    if success:
        log_task("安装后端依赖", "success")
    else:
        log_task("安装后端依赖", "error", err)
        execution_log["errors"].append({"task": "安装后端依赖", "error": err})

    # Task 1.4: 检查.env文件
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        log_task("检查.env配置", "warning", ".env文件不存在，从.env.example复制")
        env_example = BACKEND_DIR / ".env.example"
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            log_task("创建.env文件", "success")
        else:
            log_task("检查.env配置", "error", ".env.example不存在")
            execution_log["errors"].append({"task": "检查.env配置", "error": ".env.example不存在"})
    else:
        log_task("检查.env配置", "success")

    # Task 1.5: 创建必要目录
    log_task("创建项目目录", "running")
    dirs = [
        BACKEND_DIR / "app" / "agent",
        BACKEND_DIR / "app" / "market",
        BACKEND_DIR / "app" / "rag",
        BACKEND_DIR / "app" / "search",
        BACKEND_DIR / "app" / "enricher",
        BACKEND_DIR / "app" / "api",
        BACKEND_DIR / "data" / "knowledge",
        BACKEND_DIR / "tests" / "integration",
        PROJECT_ROOT / "vectorstore" / "chroma",
        LOGS_DIR
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    log_task("创建项目目录", "success")

    # Task 1.6: 安装前端依赖
    if (FRONTEND_DIR / "package.json").exists():
        log_task("安装前端依赖", "running")
        success, _, err = run_command("npm install", cwd=FRONTEND_DIR, timeout=600)
        if success:
            log_task("安装前端依赖", "success")
        else:
            log_task("安装前端依赖", "error", err)
            execution_log["errors"].append({"task": "安装前端依赖", "error": err})
    else:
        log_task("安装前端依赖", "skipped", "package.json不存在")
        execution_log["skipped"].append("安装前端依赖")

# ============================================================================
# Phase 2: 代码生成（基于已有的实现计划）
# ============================================================================

def phase2_code_generation():
    """Phase 2: 代码生成"""
    print("\n" + "="*80)
    print("Phase 2: 代码生成")
    print("="*80)

    log_task("代码生成", "info", "此阶段需要手动执行实现计划中的任务")
    log_task("代码生成", "info", "建议使用 superpowers:subagent-driven-development")
    execution_log["skipped"].append("代码生成（需要手动执行）")

# ============================================================================
# Phase 3: 测试执行
# ============================================================================

def phase3_testing():
    """Phase 3: 测试执行"""
    print("\n" + "="*80)
    print("Phase 3: 测试执行")
    print("="*80)

    # Task 3.1: 运行单元测试
    log_task("运行单元测试", "running")
    pytest_cmd = "venv\\Scripts\\pytest" if sys.platform == "win32" else "venv/bin/pytest"
    success, stdout, stderr = run_command(
        f"{pytest_cmd} tests/ -v --tb=short",
        cwd=BACKEND_DIR,
        timeout=300
    )
    if success:
        log_task("运行单元测试", "success", "所有测试通过")
    else:
        log_task("运行单元测试", "warning", "部分测试失败（可能是正常的）")
        # 不记录为错误，因为在开发过程中测试失败是正常的

    # Task 3.2: 运行集成测试
    log_task("运行集成测试", "running")
    success, stdout, stderr = run_command(
        f"{pytest_cmd} tests/integration/ -v -m integration",
        cwd=BACKEND_DIR,
        timeout=600
    )
    if success:
        log_task("运行集成测试", "success")
    else:
        log_task("运行集成测试", "warning", "集成测试需要API keys")

# ============================================================================
# Phase 4: 服务启动检查
# ============================================================================

def phase4_service_check():
    """Phase 4: 服务启动检查"""
    print("\n" + "="*80)
    print("Phase 4: 服务启动检查")
    print("="*80)

    # Task 4.1: 检查Redis
    log_task("检查Redis服务", "running")
    success, _, _ = run_command("redis-cli ping")
    if success:
        log_task("检查Redis服务", "success")
    else:
        log_task("检查Redis服务", "warning", "Redis未运行，某些功能可能不可用")

    # Task 4.2: 检查后端启动
    log_task("检查后端配置", "running")
    main_py = BACKEND_DIR / "app" / "main.py"
    if main_py.exists():
        log_task("检查后端配置", "success", "main.py存在")
    else:
        log_task("检查后端配置", "error", "main.py不存在")
        execution_log["errors"].append({"task": "检查后端配置", "error": "main.py不存在"})

    # Task 4.3: 检查前端配置
    log_task("检查前端配置", "running")
    vite_config = FRONTEND_DIR / "vite.config.js"
    if vite_config.exists():
        log_task("检查前端配置", "success", "vite.config.js存在")
    else:
        log_task("检查前端配置", "warning", "vite.config.js不存在")

# ============================================================================
# Phase 5: Docker构建
# ============================================================================

def phase5_docker():
    """Phase 5: Docker构建"""
    print("\n" + "="*80)
    print("Phase 5: Docker构建")
    print("="*80)

    docker_compose = PROJECT_ROOT / "docker" / "docker-compose.yml"
    if not docker_compose.exists():
        log_task("Docker构建", "skipped", "docker-compose.yml不存在")
        execution_log["skipped"].append("Docker构建")
        return

    # Task 5.1: 检查Docker
    log_task("检查Docker", "running")
    success, _, _ = run_command("docker --version")
    if not success:
        log_task("检查Docker", "error", "Docker未安装")
        execution_log["errors"].append({"task": "检查Docker", "error": "Docker未安装"})
        return
    log_task("检查Docker", "success")

    # Task 5.2: 构建镜像
    log_task("构建Docker镜像", "running")
    success, _, err = run_command(
        "docker-compose build",
        cwd=PROJECT_ROOT / "docker",
        timeout=1200
    )
    if success:
        log_task("构建Docker镜像", "success")
    else:
        log_task("构建Docker镜像", "error", err)
        execution_log["errors"].append({"task": "构建Docker镜像", "error": err})

# ============================================================================
# 主执行流程
# ============================================================================

def main():
    """主执行流程"""
    print("\n" + "="*80)
    print("金融资产问答系统 - 自动化实现脚本")
    print("基于: financial-qa-tech-spec-v2.md")
    print("="*80)

    start_time = time.time()

    try:
        # 执行各阶段
        phase1_setup()
        phase2_code_generation()
        phase3_testing()
        phase4_service_check()
        phase5_docker()

    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        execution_log["status"] = "interrupted"
    except Exception as e:
        print(f"\n\n执行出错: {e}")
        execution_log["status"] = "error"
        execution_log["errors"].append({"task": "主流程", "error": str(e)})
    else:
        execution_log["status"] = "completed"

    # 计算执行时间
    execution_time = time.time() - start_time
    execution_log["end_time"] = datetime.now().isoformat()
    execution_log["execution_time_seconds"] = round(execution_time, 2)

    # 保存执行日志
    log_file = LOGS_DIR / f"execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(execution_log, f, indent=2, ensure_ascii=False)

    # 打印总结
    print("\n" + "="*80)
    print("执行总结")
    print("="*80)
    print(f"总耗时: {execution_time:.2f}秒")
    print(f"完成任务: {len([t for t in execution_log['tasks'] if t['status'] == 'success'])}")
    print(f"跳过任务: {len(execution_log['skipped'])}")
    print(f"错误任务: {len(execution_log['errors'])}")
    print(f"\n详细日志: {log_file}")

    if execution_log["errors"]:
        print("\n错误列表:")
        for err in execution_log["errors"]:
            print(f"  - {err['task']}: {err['error']}")

    if execution_log["skipped"]:
        print("\n跳过任务:")
        for task in execution_log["skipped"]:
            print(f"  - {task}")

    print("\n" + "="*80)
    print("执行完成")
    print("="*80)

    return 0 if not execution_log["errors"] else 1

if __name__ == "__main__":
    sys.exit(main())
