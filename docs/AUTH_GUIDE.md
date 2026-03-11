# 认证系统使用指南

## 概述

系统支持两种认证方式：
1. **API Key 认证** - 适合服务间调用
2. **JWT Token 认证** - 适合用户登录

## API Key 认证

### 创建 API Key
```bash
POST /api/auth/api-key
Content-Type: application/json

{
  "name": "My Application",
  "rate_limit": 1000
}
```

响应：
```json
{
  "api_key": "faq_xxxxxxxxxx",
  "name": "My Application",
  "rate_limit": 1000,
  "created_at": "2026-03-10T20:30:00"
}
```

### 使用 API Key
```bash
curl -H "X-API-Key: faq_xxxxxxxxxx" \
  http://127.0.0.1:8001/api/chat
```

### 撤销 API Key
```bash
DELETE /api/auth/api-key/{api_key}
```

### 列出所有 API Keys
```bash
GET /api/auth/api-keys
```

## JWT Token 认证

### 登录获取 Token
```bash
POST /api/auth/token
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

响应：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 使用 Token
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  http://127.0.0.1:8001/api/chat
```

### 登出
```bash
POST /api/auth/logout
Authorization: Bearer {token}
```

### 验证认证状态
```bash
GET /api/auth/verify
Authorization: Bearer {token}
```

## 默认凭证

**测试用户**：
- 用户名：`admin`
- 密码：`admin123`

**演示 API Key**：
- `demo_key_12345`

⚠️ **生产环境请务必修改默认凭证！**

## 安全建议

1. 使用 HTTPS 传输
2. 定期轮换 API Key
3. 设置合理的速率限制
4. 监控异常访问
5. 及时撤销泄露的密钥
