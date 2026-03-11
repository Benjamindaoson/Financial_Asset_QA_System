# 多轮对话使用指南

## 概述

系统支持多轮对话会话管理，可保存对话历史和上下文。

## 会话管理

### 创建会话
```bash
POST /api/sessions
Content-Type: application/json

{
  "initial_context": {
    "user_id": "user123",
    "preferences": {}
  }
}
```

响应：
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-03-10T20:30:00",
  "updated_at": "2026-03-10T20:30:00",
  "messages": [],
  "context": {},
  "active": true
}
```

### 获取会话
```bash
GET /api/sessions/{session_id}
```

### 更新会话上下文
```bash
PUT /api/sessions/{session_id}
Content-Type: application/json

{
  "context": {
    "last_symbol": "AAPL",
    "user_preferences": {}
  }
}
```

### 删除会话
```bash
DELETE /api/sessions/{session_id}
```

## 消息管理

### 添加消息
```bash
POST /api/sessions/{session_id}/messages
Content-Type: application/json

{
  "role": "user",
  "content": "AAPL最新价格是多少？",
  "metadata": {
    "source": "web"
  }
}
```

### 获取消息历史
```bash
GET /api/sessions/{session_id}/messages?limit=20&offset=0
```

### 获取会话上下文
```bash
GET /api/sessions/{session_id}/context
```

## 会话列表

### 列出所有会话
```bash
GET /api/sessions?active_only=true&limit=50
```

### 获取会话摘要
```bash
GET /api/sessions/{session_id}/summary
```

## 会话清理

### 手动清理过期会话
```bash
POST /api/sessions/cleanup
```

系统会自动清理 24 小时未活动的会话。

## 使用示例

```python
import requests

# 1. 创建会话
response = requests.post("http://127.0.0.1:8001/api/sessions", json={})
session_id = response.json()["session_id"]

# 2. 添加用户消息
requests.post(
    f"http://127.0.0.1:8001/api/sessions/{session_id}/messages",
    json={"role": "user", "content": "AAPL最新价格？"}
)

# 3. 添加助手回复
requests.post(
    f"http://127.0.0.1:8001/api/sessions/{session_id}/messages",
    json={"role": "assistant", "content": "AAPL 当前价格为 178.52 美元"}
)

# 4. 获取消息历史
history = requests.get(
    f"http://127.0.0.1:8001/api/sessions/{session_id}/messages"
).json()

print(f"Total messages: {history['total']}")
```

## 注意事项

1. 会话最多保存 50 条消息
2. 24 小时未活动的会话将被自动清理
3. 会话数据存储在内存中（生产环境建议使用 Redis）
4. 每个会话有独立的上下文和消息历史
