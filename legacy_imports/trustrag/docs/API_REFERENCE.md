# TrustRAG API Reference / API 参考文档

## Table of Contents / 目录

- [Base URL / 基础URL](#base-url)
- [Authentication / 认证](#authentication)
- [Query Endpoints / 查询接口](#query-endpoints)
- [Ingestion Endpoints / 摄入接口](#ingestion-endpoints)
- [System Endpoints / 系统接口](#system-endpoints)
- [Error Codes / 错误码](#error-codes)
- [Examples / 示例](#examples)

---

## Base URL / 基础URL

```
Development: http://localhost:8000
Production: https://api.trustrag.example.com
```

---

## Authentication / 认证

Currently, TrustRAG API does not require authentication. For production deployments, implement API key or OAuth2 authentication.

当前 TrustRAG API 不需要认证。生产环境部署时，请实现 API 密钥或 OAuth2 认证。

---

## Query Endpoints / 查询接口

### POST /api/query

Process a financial question and return verified answer.

处理财务问题并返回验证答案。

#### Request Body / 请求体

```json
{
  "query": "What was Nvidia's revenue for FY2023?",
  "risk_level": "medium"
}
```

#### Parameters / 参数

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | The question to ask |
| `risk_level` | string | No | Risk level: "low", "medium", "high" (default: "medium") |

#### Response / 响应

**Success (200 OK)**

```json
{
  "verdict": "VERIFIED",
  "answer": {
    "text": "Nvidia's revenue for FY2023 was $26.97 billion.",
    "confidence": 0.95
  },
  "evidence": [
    {
      "metric": "revenue",
      "value": "$26.97 billion",
      "source": "Nvidia 10-K FY2023",
      "page": 45
    }
  ],
  "trace_id": "tr_1704067200000",
  "reasons": ["Evidence matches query intent"],
  "risk_flags": {},
  "disclosure_required": false,
  "verification_data": {
    "processing_time_ms": 234,
    "candidates_count": 15,
    "arbitration_status": "ALLOW"
  }
}
```

#### Verdict Types / 裁决类型

- **VERIFIED**: Answer is verified and backed by evidence
- **REFUSED**: System refuses to answer (insufficient evidence, conflicts, etc.)
- **CONFLICT**: Conflicting evidence detected from multiple sources

#### Error Responses / 错误响应

**400 Bad Request**

```json
{
  "error": "Invalid request",
  "detail": "Query is too short"
}
```

**500 Internal Server Error**

```json
{
  "error": "Internal Server Error",
  "detail": "Query processing failed: ...",
  "trace_id": "err_1704067200000"
}
```

---

## Ingestion Endpoints / 摄入接口

### POST /api/ingest

Upload and ingest a document.

上传并摄入文档。

#### Request / 请求

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Document file (PDF, HTML, TXT, CSV, XLSX) |
| `doc_id` | string | No | Custom document ID |
| `profile` | string | No | Ingest profile (default: "generic") |

#### Response / 响应

**Success (200 OK)**

```json
{
  "doc_id": "nvidia_fy2023",
  "status": "OK",
  "chunks_count": 1250,
  "errors": [],
  "message": "Document ingested successfully"
}
```

#### Status Values / 状态值

- **OK**: Document ingested successfully
- **DEGRADED**: Document ingested with quality issues (e.g., OCR degradation)
- **FAILED**: Document ingestion failed

#### Error Responses / 错误响应

**400 Bad Request**

```json
{
  "error": "Unsupported file type",
  "detail": "File extension '.docx' is not supported",
  "allowed": [".pdf", ".html", ".txt", ".csv", ".xlsx"]
}
```

**400 Bad Request** (File too large)

```json
{
  "error": "File too large",
  "detail": "File size exceeds 50MB limit"
}
```

### POST /api/ingest/refresh

Refresh the search index with newly ingested documents.

刷新索引以包含新摄入的文档。

#### Response / 响应

**Success (200 OK)**

```json
{
  "status": "success",
  "new_chunks_added": 1250,
  "message": "Index refreshed with 1250 new chunks"
}
```

---

## System Endpoints / 系统接口

### GET /api/health

Health check endpoint.

健康检查接口。

#### Response / 响应

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "index_loaded": true,
  "documents_count": 15,
  "chunks_count": 12500
}
```

### GET /api/stats

Get detailed index statistics.

获取详细索引统计信息。

#### Response / 响应

```json
{
  "total_chunks": 12500,
  "documents_loaded": 15,
  "documents": [
    "nvidia_fy2023",
    "apple_10k_2023",
    "microsoft_q3_2024"
  ],
  "chunks_by_tier": {
    "micro": 2500,
    "base": 8000,
    "macro": 2000
  }
}
```

### GET /api/config

Get current system configuration (non-sensitive parts).

获取当前系统配置（非敏感部分）。

#### Response / 响应

```json
{
  "feature_flags": {
    "enable_llm_classifier": false,
    "enable_rerank": false,
    "enable_cross_modal": true
  },
  "query_thresholds": {
    "confidence_threshold": 0.7,
    "low_confidence_threshold": 0.5
  },
  "evidence_selection": {
    "max_core_factual": 3,
    "max_core_summary": 5
  },
  "api": {
    "max_upload_size_mb": 50
  }
}
```

---

## Error Codes / 错误码

### HTTP Status Codes / HTTP 状态码

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid input) |
| 404 | Not Found |
| 500 | Internal Server Error |

### Refusal Codes / 拒绝码

When `verdict` is "REFUSED", the system may include refusal codes in `verification_data`:

当 `verdict` 为 "REFUSED" 时，系统可能在 `verification_data` 中包含拒绝码：

| Code | Name | Description |
|------|------|-------------|
| R1 | Out of Scope | Query is non-financial or non-compliance related |
| R2 | Rank-1 Conflict | Two high-authority sources contradict each other |
| R3 | Low Evidence | Evidence score below threshold |
| R4 | Insufficient Confidence | Confidence too low for risk level |
| R5 | OCR Only Numeric | OCR-only evidence for numeric query |
| R6 | Modal Conflict | Modality conflict (native vs OCR) |
| R7 | Temporal Ambiguity | Time period ambiguous |
| R8 | Entity Mismatch | Entity cannot be matched |
| R9 | Metric Mismatch | Metric cannot be matched |
| R10 | Period Mismatch | Period cannot be matched |
| R11 | Evidence Insufficient | Insufficient evidence after selection |
| R12 | High Risk Only | Only high-risk evidence available |

### Error Categories / 错误类别

| Category | Description |
|----------|-------------|
| `ingestion` | Document ingestion errors |
| `retrieval` | Retrieval/query errors |
| `judgment` | Arbitration/judgment errors |
| `validation` | Validation errors |
| `config` | Configuration errors |
| `index` | Index errors |
| `system` | General system errors |

---

## Examples / 示例

### Python Example / Python 示例

```python
import requests

# Query
response = requests.post(
    "http://localhost:8000/api/query",
    json={
        "query": "What was Nvidia's revenue for FY2023?",
        "risk_level": "medium"
    }
)
result = response.json()
print(f"Verdict: {result['verdict']}")
print(f"Answer: {result.get('answer', {}).get('text', 'N/A')}")

# Upload document
with open("report.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/ingest",
        files={"file": f},
        data={"profile": "generic"}
    )
    result = response.json()
    print(f"Status: {result['status']}")
    print(f"Chunks: {result['chunks_count']}")
```

### cURL Example / cURL 示例

```bash
# Query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was Nvidia'\''s revenue for FY2023?",
    "risk_level": "medium"
  }'

# Upload document
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@report.pdf" \
  -F "profile=generic"

# Get stats
curl http://localhost:8000/api/stats
```

### JavaScript Example / JavaScript 示例

```javascript
// Query
const response = await fetch('http://localhost:8000/api/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: "What was Nvidia's revenue for FY2023?",
    risk_level: "medium"
  })
});

const result = await response.json();
console.log('Verdict:', result.verdict);
console.log('Answer:', result.answer?.text);

// Upload document
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('profile', 'generic');

const uploadResponse = await fetch('http://localhost:8000/api/ingest', {
  method: 'POST',
  body: formData
});

const uploadResult = await uploadResponse.json();
console.log('Status:', uploadResult.status);
```

---

## Rate Limiting / 速率限制

Currently, TrustRAG API does not enforce rate limiting. For production deployments, implement rate limiting middleware.

当前 TrustRAG API 不强制执行速率限制。生产环境部署时，请实现速率限制中间件。

Recommended limits:
- 60 requests per minute per IP
- 1000 requests per hour per API key

---

## Versioning / 版本控制

API version is included in the health endpoint response. Current version: **1.0.0**

API 版本包含在健康检查接口响应中。当前版本：**1.0.0**

---

**Last Updated**: 2025-01-XX
**Version**: 1.0



