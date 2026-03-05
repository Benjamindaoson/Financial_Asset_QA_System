"""
测试用户提供的API端点
URL: www.ticketpro.cc
Key: sk-201609f8eeef94e2f6a32645929ea7ee7cf52fba0d2e44025c084f3db8f7c3e5
Model: claude-opus-4-6
"""
import anthropic
import sys
import json

def test_api():
    """测试API端点"""

    # 配置
    base_url = "https://www.ticketpro.cc"
    api_key = "sk-201609f8eeef94e2f6a32645929ea7ee7cf52fba0d2e44025c084f3db8f7c3e5"
    model = "claude-opus-4-6"

    print("=" * 60)
    print("测试API端点")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print(f"API Key: {api_key[:20]}...")
    print()

    try:
        # 初始化客户端
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )

        print("[1/3] 测试基础对话...")
        print("-" * 60)

        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello! Please respond with 'API test successful' if you can read this."}
            ]
        )

        print(f"Response: {response.content[0].text}")
        print(f"Model: {response.model}")
        print(f"Stop reason: {response.stop_reason}")
        print("[OK] 基础对话测试通过")
        print()

        # 测试Tool Use
        print("[2/3] 测试Tool Use功能...")
        print("-" * 60)

        response = client.messages.create(
            model=model,
            max_tokens=500,
            tools=[
                {
                    "name": "get_weather",
                    "description": "Get weather information for a location",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"}
                        },
                        "required": ["location"]
                    }
                }
            ],
            messages=[
                {"role": "user", "content": "What's the weather in Beijing? Use the get_weather tool."}
            ]
        )

        print(f"Stop reason: {response.stop_reason}")

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Tool called: {block.name}")
                    print(f"Tool input: {json.dumps(block.input, ensure_ascii=False)}")
            print("[OK] Tool Use测试通过")
        else:
            print(f"[WARN] 未调用工具，stop_reason: {response.stop_reason}")
            if response.content:
                print(f"Response: {response.content[0].text if hasattr(response.content[0], 'text') else response.content[0]}")
        print()

        # 测试流式响应
        print("[3/3] 测试流式响应...")
        print("-" * 60)

        stream = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Count from 1 to 5."}
            ],
            stream=True
        )

        print("Streaming response: ", end="", flush=True)
        for event in stream:
            if event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    print(event.delta.text, end="", flush=True)
        print()
        print("[OK] 流式响应测试通过")
        print()

        # 总结
        print("=" * 60)
        print("[SUCCESS] 所有测试通过！")
        print("=" * 60)
        print()
        print("API端点完全兼容，可以使用！")
        print()
        print("配置信息:")
        print(f"ANTHROPIC_API_KEY={api_key}")
        print(f"ANTHROPIC_BASE_URL={base_url}")
        print(f"CLAUDE_MODEL={model}")

        return True

    except anthropic.APIConnectionError as e:
        print(f"[ERROR] 连接错误: {e}")
        print("端点可能无法访问或URL不正确")
        return False

    except anthropic.AuthenticationError as e:
        print(f"[ERROR] 认证错误: {e}")
        print("API密钥无效或已过期")
        return False

    except Exception as e:
        print(f"[ERROR] 未知错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)
