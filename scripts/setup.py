"""
Financial Asset QA System - 自动配置脚本
Interactive setup wizard for first-time configuration
"""
import os
import sys
from pathlib import Path

def print_header():
    print("=" * 60)
    print("Financial Asset QA System - 配置向导")
    print("=" * 60)
    print()

def check_env_file():
    """检查.env文件是否存在"""
    env_path = Path("backend/.env")
    return env_path.exists()

def validate_api_key(api_key: str, base_url: str = None) -> bool:
    """验证API密钥是否有效"""
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url if base_url else None
        )

        # 发送测试请求
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )

        return True
    except anthropic.AuthenticationError:
        return False
    except Exception as e:
        print(f"[警告] 无法验证API密钥: {e}")
        return True  # 假设有效，继续

def create_env_file(config: dict):
    """创建.env文件"""
    env_path = Path("backend/.env")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# Anthropic API Configuration\n")
        f.write(f"ANTHROPIC_API_KEY={config['api_key']}\n")

        if config.get('base_url'):
            f.write(f"ANTHROPIC_BASE_URL={config['base_url']}\n")

        f.write("\n# Optional: Alpha Vantage API (backup data source)\n")
        f.write("# ALPHA_VANTAGE_API_KEY=your_key_here\n")

        f.write("\n# Redis Configuration (optional)\n")
        f.write("REDIS_HOST=localhost\n")
        f.write("REDIS_PORT=6379\n")
        f.write("REDIS_DB=0\n")

    print(f"[成功] 配置文件已创建: {env_path}")

def main():
    print_header()

    # 检查是否已配置
    if check_env_file():
        print("[提示] 检测到已存在的配置文件 backend/.env")
        choice = input("是否要重新配置？(y/N): ").strip().lower()
        if choice != 'y':
            print("配置已取消")
            return
        print()

    config =

    # 1. 选择API类型
    print("请选择API类型：")
    print("1. 官方Anthropic API（推荐）")
    print("2. 自定义API端点")
    print()

    api_choice = input("请输入选项 (1/2) [1]: ").strip() or "1"
    print()

    if api_choice == "2":
        print("[注意] 自定义API必须支持Tool Use功能，否则系统无法工作")
        base_url = input("请输入API Base URL: ").strip()
        if base_url:
            config['base_url'] = base_url
        print()

    # 2. 输入API密钥
    print("请输入Anthropic API密钥：")
    if api_choice == "1":
        print("获取密钥: https://console.anthropic.com/")
    print()

    api_key = input("API Key: ").strip()

    if not api_key:
        print("[错误] API密钥不能为空")
        sys.exit(1)

    config['api_key'] = api_key
    print()

    # 3. 验证API密钥
    print("[验证] 正在验证API密钥...")

    if validate_api_key(api_key, config.get('base_url')):
        print("[成功] API密钥验证通过")
    else:
        print("[错误] API密钥无效")
        choice = input("是否仍要继续？(y/N): ").strip().lower()
        if choice != 'y':
            sys.exit(1)

    print()

    # 4. 创建配置文件
    create_env_file(config)
    print()

    # 5. 完成提示
    print("=" * 60)
    print("[完成] 配置已完成！")
    print("=" * 60)
    print()
    print("下一步：")
    print("1. 启动后端: cd backend && start.bat")
    print("2. 启动前端: cd frontend && npm run dev")
    print("3. 访问: http://localhost:3001")
    print()
    print("提示: 如需配置Redis缓存，请参考 STARTUP_GUIDE.md")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[取消] 配置已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n[错误] {e}")
        sys.exit(1)
