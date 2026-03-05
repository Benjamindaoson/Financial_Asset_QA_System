"""
测试Ticketpro API (更新的URL)
URL: https://api.ticketpro.cc
Key: sk-201609f8eeef94e2f6a32645929ea7ee7cf52fba0d2e44025c084f3db8f7c3e5
Model: claude-opus-4-6
"""
import anthropic
import sys
import json

def test_ticketpro_new():
    api_key = "sk-201609f8eeef94e2f6a32645929ea7ee7cf52fba0d2e44025c084f3db8f7c3e5"
    base_url = "https://api.ticketpro.cc"
    model = "claude-opus-4-6"

    print("=" * 60)
    print("测试 Ticketpro API (新URL)")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print()

    try:
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )

        print("[1/3] 测试基础对话...")
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello! Please respond with 'API test successful'"}
            ]
        )

        print(f"Response: {response.content[0].text}")
        print(f"Model: {response.model}")
        print("[OK] 基础对话测试通过")
        print()

        print("[2/3] 测试Tool Use功能...")
        response = client.messages.create(
            model=model,
            max_tokens=500,
            tools=[
                {
                    "name": "get_weather",
                    "description": "Get weather information",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                        "required": ["location"]
                    }
                }
            ],
            messages=[
                {"role": "user", "content": "What's the weather in Beijing? Use the get_weather tool."}
            ]
        )

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Tool called: {block.name}")
                    print(f"Tool input: {json.dumps(block.input, ensure_ascii=False)}")
            print("[OK] Tool Use测试通过")
        else:
            print(f"[WARN] 未调用工具，stop_reason: {response.stop_reason}")
        print()

        print("[3/3] 测试流式响应...")
        stream = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Count from 1 to 5"}
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

        print("=" * 60)
        print("[SUCCESS] Ticketpro API 完全可用！")
        print("=" * 60)
        return True

    except anthropic.APIConnectionError as e:
        print(f"[ERROR] 连接错误: {e}")
        return False
    except anthropic.AuthenticationError as e:
        print(f"[ERROR] 认证错误: {e}")
        return False
    except anthropic.InternalServerError as e:
        print(f"[ERROR] 服务器错误: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_ticketpro_new()
    sys.exit(0 if success else 1)
