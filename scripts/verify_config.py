"""
验证Ticketpro API配置
"""
import sys
import os
from pathlib import Path

# 切换到backend目录以正确加载.env
backend_dir = Path(__file__).parent.parent / "backend"
os.chdir(backend_dir)

# 添加项目路径
sys.path.insert(0, str(backend_dir))

from app.config import settings

print("=" * 60)
print("配置验证")
print("=" * 60)
print()

print("API配置:")
print(f"  ANTHROPIC_API_KEY: {settings.ANTHROPIC_API_KEY[:20]}...")
print(f"  ANTHROPIC_BASE_URL: {settings.ANTHROPIC_BASE_URL}")
print(f"  CLAUDE_MODEL: {settings.CLAUDE_MODEL}")
print()

print("其他配置:")
print(f"  REDIS_HOST: {settings.REDIS_HOST}")
print(f"  REDIS_PORT: {settings.REDIS_PORT}")
print(f"  LOG_LEVEL: {settings.LOG_LEVEL}")
print()

# 验证配置
if settings.ANTHROPIC_API_KEY.startswith("sk-"):
    print("[OK] API密钥格式正确")
else:
    print("[WARN] API密钥格式可能不正确")

if settings.ANTHROPIC_BASE_URL:
    print(f"[OK] 使用自定义API端点: {settings.ANTHROPIC_BASE_URL}")
else:
    print("[INFO] 使用官方Anthropic API端点")

if settings.CLAUDE_MODEL:
    print(f"[OK] 模型配置: {settings.CLAUDE_MODEL}")

print()
print("=" * 60)
print("配置已加载")
print("=" * 60)
print()
print("注意: Ticketpro API当前返回503错误（无可用账户）")
print("建议: 联系服务商确认服务状态")
print()
