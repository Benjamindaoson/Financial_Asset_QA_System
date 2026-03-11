# OpenAPI 文档访问指南

## 📖 API 文档

系统已集成 FastAPI 自动生成的 OpenAPI 文档，提供完整的 API 接口说明。

### 访问方式

启动后端服务后，可通过以下地址访问：

#### 1. Swagger UI（推荐）
```
http://127.0.0.1:8001/docs
```
- 交互式 API 文档
- 可直接在浏览器中测试 API
- 查看请求/响应示例

#### 2. ReDoc
```
http://127.0.0.1:8001/redoc
```
- 更美观的文档展示
- 适合阅读和打印

#### 3. OpenAPI JSON
```
http://127.0.0.1:8001/openapi.json
```
- 原始 OpenAPI 3.0 规范
- 可导入 Postman、Insomnia 等工具

---

## 🔌 主要 API 端点

### 1. 健康检查
```http
GET /api/health
```
返回系统健康状态和组件可用性。

### 2. 聊天接口（SSE 流式）
```http
POST /api/chat
Content-Type: application/json

{
  "query": "苹果股票今天涨了多少",
  "session_id": "optional-session-id"
}
```
返回 Server-Sent Events (SSE) 流式响应。

### 3. 模型列表
```http
GET /api/models
```
返回可用的 AI 模型列表和使用统计。

### 4. 图表数据
```http
GET /api/chart/{symbol}?days=30&range_key=1y
```
返回指定股票的历史价格数据。

### 5. 市场概览
```http
GET /api/market/overview
```
返回市场概览数据（热门股票、指数等）。

---

## 🧪 测试示例

### 使用 curl 测试
```bash
# 健康检查
curl http://127.0.0.1:8001/api/health

# 聊天查询
curl -X POST http://127.0.0.1:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL最新价格"}'

# 获取图表数据
curl http://127.0.0.1:8001/api/chart/AAPL?days=30
```

### 使用 Python 测试
```python
import requests

# 健康检查
response = requests.get("http://127.0.0.1:8001/api/health")
print(response.json())

# 聊天查询（SSE）
import sseclient

response = requests.post(
    "http://127.0.0.1:8001/api/chat",
    json={"query": "特斯拉股价"},
    stream=True
)

client = sseclient.SSEClient(response)
for event in client.events():
    print(event.data)
```

---

## 📝 响应格式

### SSE 事件类型

聊天接口返回以下事件类型：

1. **model_selected** - 模型选择完成
```json
{
  "type": "model_selected",
  "model": "deepseek-chat",
  "provider": "deepseek"
}
```

2. **tool_start** - 工具调用开始
```json
{
  "type": "tool_start",
  "name": "get_price",
  "display": "正在获取 AAPL 的最新价格..."
}
```

3. **tool_data** - 工具返回数据
```json
{
  "type": "tool_data",
  "tool": "get_price",
  "data": {"symbol": "AAPL", "price": 178.52}
}
```

4. **chunk** - 流式文本片段
```json
{
  "type": "chunk",
  "text": "AAPL 最新价格为 178.52 美元"
}
```

5. **done** - 响应完成
```json
{
  "type": "done",
  "verified": true,
  "sources": [...],
  "data": {
    "confidence": {"level": "high", "score": 95},
    "blocks": [...]
  }
}
```

6. **error** - 错误信息
```json
{
  "type": "error",
  "message": "错误描述",
  "code": "ERROR_CODE"
}
```

---

## 🔒 认证（即将支持）

当前版本暂不需要认证。未来版本将支持：
- API Key 认证
- JWT Token 认证
- OAuth 2.0

---

## 📚 更多信息

- 完整 API 文档：http://127.0.0.1:8001/docs
- 项目 README：[../README.md](../README.md)
- 技术架构：[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
