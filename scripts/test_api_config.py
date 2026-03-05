"""
Test script to verify API configuration
"""
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Change to backend directory FIRST
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
backend_dir = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
env_file = os.path.join(backend_dir, '.env')
os.chdir(backend_dir)

# NOW load .env file explicitly with override
from dotenv import load_dotenv
load_dotenv(dotenv_path=env_file, override=True)

sys.path.insert(0, backend_dir)

from anthropic import Anthropic

# Get configuration directly from environment after loading .env
API_KEY = os.getenv('ANTHROPIC_API_KEY')
BASE_URL = os.getenv('ANTHROPIC_BASE_URL')
MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-4-6')

def test_api_connection():
    """Test if the API is configured correctly and can be called"""

    print("=" * 60)
    print("API Configuration Test")
    print("=" * 60)
    print(f"API Key: {API_KEY[:20]}...")
    print(f"Base URL: {BASE_URL}")
    print(f"Model: {MODEL}")
    print("=" * 60)

    try:
        # Initialize client
        client = Anthropic(
            api_key=API_KEY,
            base_url=BASE_URL
        )

        print("\n[OK] Client initialized successfully")

        # Test API call
        print("\nSending test message to API...")
        response = client.messages.create(
            model=MODEL,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello! Please respond with 'API test successful' if you receive this message."}
            ]
        )

        print("\n[OK] API call successful!")
        print(f"\nResponse:")
        print(f"  Model: {response.model}")
        print(f"  Content: {response.content[0].text}")
        print(f"  Usage: {response.usage}")

        print("\n" + "=" * 60)
        print("[OK] All tests passed! API is configured correctly.")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n[ERROR] Error: {type(e).__name__}")
        print(f"  Message: {str(e)}")
        print("\n" + "=" * 60)
        print("[ERROR] Test failed. Please check your configuration.")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_api_connection()
    sys.exit(0 if success else 1)
