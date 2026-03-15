import requests
import sys

try:
    proxies = {"http": None, "https": None}
    resp = requests.post(
        "http://127.0.0.1:8001/api/chat", 
        json={"query": "特斯拉当前股价", "session_id": "test"},
        stream=True,
        proxies=proxies
    )
    print(f"Status: {resp.status_code}")
    for line in resp.iter_lines():
        if line:
            print(line.decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
