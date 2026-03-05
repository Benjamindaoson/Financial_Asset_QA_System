"""
测试DeepSeek API
API Key: sk-be1263dcc07b4f77a152bb5a0c5b83a2
Base URL: https://api.deepseek.com
Model: deepseek-chat
"""
from openai import OpenAI
import sys

def test_deepseek():
    print("=" * 60)
    print("测试 DeepSeek API")
    print("=" * 60)
    print("Base URL: https://api.deepseek.com")
    print("Model: deepseek-chat")
    print()

    try:
        client = OpenAI(
            api_key="sk-be1263dcc07b4f77a152bb5a0c5b83a2",
            base_url="https://api.deepseek.com"
        )

        print("[1/2] 测试基础对话...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello! Please respond with 'API test successful'"},
            ],
            stream=False
        )

        print(f"Response: {response.choices[0].message.content}")
        print("[OK] 基础对话测试通过")
        print()

        # 测试流式响应
        print("[2/2] 测试流式响应...")
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "Count from 1 to 5"}
            ],
            stream=True
        )

        print("Streaming response: ", end="", flush=True)
        for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print()
        print("[OK] 流式响应测试通过")
        print()

        print("=" * 60)
        print("[SUCCESS] DeepSeek API 完全可用！")
        print("=" * 60)
        print()
        print("注意: DeepSeek使用OpenAI SDK，不是Anthropic SDK")
        print("需要单独集成到系统中")
        return True

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_deepseek()
    sys.exit(0 if success else 1)
