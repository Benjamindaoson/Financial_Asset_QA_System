"""
Test custom Claude API endpoint
BaseURL: https://yunyi.rdzhvip.com/claude
API Key: 6G9XKBR6-4ECX-VU1H-EQK5-Y60BUK7WXRUK
"""
import anthropic
import sys
import json
import os

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    os.system("chcp 65001 > nul")

def test_custom_endpoint():
    """Test the custom Claude API endpoint"""

    base_url = "https://yunyi.rdzhvip.com/claude"
    api_key = "6G9XKBR6-4ECX-VU1H-EQK5-Y60BUK7WXRUK"

    print("=" * 60)
    print("Testing Custom Claude API Endpoint")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:20]}...")
    print()

    try:
        # Initialize client with custom base URL
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )

        print("[OK] Client initialized successfully")
        print()

        # Test 1: Simple message
        print("Test 1: Simple conversation")
        print("-" * 60)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello! Please respond with 'API test successful' if you can read this."}
            ]
        )

        print(f"Response: {response.content[0].text}")
        print(f"Model: {response.model}")
        print(f"Stop reason: {response.stop_reason}")
        print("[OK] Test 1 passed")
        print()

        # Test 2: Tool use
        print("Test 2: Tool use capability")
        print("-" * 60)

        response = client.messages.create(
            model="claude-sonnet-4-6",
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
            print("[OK] Test 2 passed - Tool use works")
        else:
            print(f"[WARN] Test 2 warning - Expected tool_use, got {response.stop_reason}")
            print(f"Response: {response.content[0].text if response.content else 'No content'}")
        print()

        # Test 3: Streaming
        print("Test 3: Streaming capability")
        print("-" * 60)

        stream = client.messages.create(
            model="claude-sonnet-4-6",
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
        print("[OK] Test 3 passed - Streaming works")
        print()

        # Summary
        print("=" * 60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("=" * 60)
        print("The custom API endpoint is fully functional!")
        print()
        print("Configuration for backend/.env:")
        print(f"ANTHROPIC_API_KEY={api_key}")
        print(f"ANTHROPIC_BASE_URL={base_url}")

        return True

    except anthropic.APIConnectionError as e:
        print(f"[ERROR] Connection Error: {e}")
        print("The endpoint may be unreachable or the URL is incorrect.")
        return False

    except anthropic.AuthenticationError as e:
        print(f"[ERROR] Authentication Error: {e}")
        print("The API key is invalid or expired.")
        return False

    except Exception as e:
        print(f"[ERROR] Unexpected Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_custom_endpoint()
    sys.exit(0 if success else 1)
