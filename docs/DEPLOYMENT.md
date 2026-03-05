# 部署指南 (Deployment Guide)

本文档提供金融资产问答系统的生产环境部署指南。

## 目录

- [部署架构](#部署架构)
- [环境准备](#环境准备)
- [Docker 部署](#docker-部署)
- [手动部署](#手动部署)
- [环境变量配置](#环境变量配置)
- [性能优化](#性能优化)
- [监控与日志](#监控与日志)
- [故障排查](#故障排查)
- [安全建议](#安全建议)

## 部署架构

```
┌─────────────┐
│   用户浏览器   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Nginx/CDN  │ (可选)
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│  前端服务  │   │  后端服务  │   │  Redis   │
│  (5173)  │   │  (8000)  │   │  (6379)  │
└──────────┘   └─────┬────┘   └──────────┘
                     │
                     ├─────────────┬─────────────┐
                     ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ ChromaDB │  │ Claude   │  │ Tavily   │
              │  向量库   │  │   API    │  │   API    │
              └──────────┘  └──────────┘  └──────────┘
```

## 环境准备

### 系统要求

- **操作系统**：Ubuntu 20.04+ / CentOS 8+ / Windows Server 2019+
- **CPU**：4 核心以上
- **内存**：8GB 以上（推荐 16GB）
- **磁盘**：50GB 以上 SSD
- **网络**：稳定的互联网连接（访问 Anthropic API）

### 软件依赖

- Docker 20.10+
- Docker Compose 2.0+
- Git 2.30+

或手动部署需要：
- Python 3.11+
- Node.js 18+
- Redis 7.0+
- Nginx 1.20+ (可选)

## Docker 部署

### 1. 克隆项目

```bash
git clone <repository-url>
cd Financial_Asset_QA_System
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，填写必要的 API 密钥：

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
TAVILY_API_KEY=tvly-xxxxx
REDIS_HOST=redis
REDIS_PORT=6379
LOG_LEVEL=INFO
```

### 3. 构建并启动服务

```bash
cd ../docker
docker-compose up -d
```

### 4. 查看服务状态

```bash
docker-compose ps
docker-compose logs -f
```

### 5. 访问应用

- 前端：`http://your-server-ip:5173`
- 后端 API：`http://your-server-ip:8000`
- API 文档：`http://your-server-ip:8000/docs`

### 6. 停止服务

```bash
docker-compose down
```

### 7. 更新服务

```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 手动部署

### 后端部署

#### 1. 安装 Python 依赖

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件
```

#### 3. 启动 Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# CentOS/RHEL
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis
```

#### 4. 启动后端服务

使用 systemd 管理服务（推荐）：

创建 `/etc/systemd/system/financial-qa-backend.service`：

```ini
[Unit]
Description=Financial QA Backend Service
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/Financial_Asset_QA_System/backend
Environment="PYTHONPATH=."
Environment="HF_HOME=/opt/Financial_Asset_QA_System/models/huggingface"
Environment="TRANSFORMERS_CACHE=/opt/Financial_Asset_QA_System/models/transformers"
Environment="HF_HUB_CACHE=/opt/Financial_Asset_QA_System/models/huggingface/hub"
ExecStart=/opt/Financial_Asset_QA_System/backend/venv/bin/python -m app.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start financial-qa-backend
sudo systemctl enable financial-qa-backend
sudo systemctl status financial-qa-backend
```

### 前端部署

#### 1. 安装依赖并构建

```bash
cd frontend
npm install
npm run build
```

#### 2. 配置 Nginx

创建 `/etc/nginx/sites-available/financial-qa`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /opt/Financial_Asset_QA_System/frontend/dist;
        try_files $uri $uri/ /index.html;

        # 缓存静态资源
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/financial-qa /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 3. 配置 HTTPS（推荐）

使用 Let's Encrypt：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 环境变量配置

### 必需配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | `sk-ant-xxxxx` |

### 可选配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TAVILY_API_KEY` | Tavily 搜索 API 密钥 | - |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API 密钥 | - |
| `REDIS_HOST` | Redis 主机地址 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_DB` | Redis 数据库编号 | `0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 模型缓存配置

| 变量名 | 说明 | 推荐值 |
|--------|------|--------|
| `HF_HOME` | Hugging Face 缓存目录 | `/opt/models/huggingface` |
| `TRANSFORMERS_CACHE` | Transformers 缓存目录 | `/opt/models/transformers` |
| `HF_HUB_CACHE` | HF Hub 缓存目录 | `/opt/models/huggingface/hub` |
| `HF_ENDPOINT` | HF 镜像地址（国内） | `https://hf-mirror.com` |

## 性能优化

### 1. Redis 优化

编辑 `/etc/redis/redis.conf`：

```conf
# 最大内存限制
maxmemory 2gb
maxmemory-policy allkeys-lru

# 持久化配置（根据需求调整）
save 900 1
save 300 10
save 60 10000

# 网络优化
tcp-backlog 511
timeout 300
tcp-keepalive 300
```

### 2. 后端优化

#### Uvicorn 配置

修改 `backend/app/main.py`：

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # 根据 CPU 核心数调整
        log_level="info",
        access_log=True,
        use_colors=True
    )
```

#### 模型预加载

在应用启动时预加载模型，避免首次请求延迟：

```python
@app.on_event("startup")
async def startup_event():
    # 预加载嵌入模型
    from app.rag.pipeline import get_rag_pipeline
    get_rag_pipeline()
    logger.info("Models preloaded successfully")
```

### 3. 前端优化

#### 构建优化

修改 `frontend/vite.config.js`：

```javascript
export default {
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'chart-vendor': ['recharts']
        }
      }
    },
    chunkSizeWarningLimit: 1000
  }
}
```

#### CDN 加速

使用 CDN 加速静态资源：

```html
<!-- 在 index.html 中添加 -->
<link rel="dns-prefetch" href="//cdn.jsdelivr.net">
<link rel="preconnect" href="//cdn.jsdelivr.net">
```

### 4. 数据库优化

#### ChromaDB 优化

```python
# 使用持久化存储
client = chromadb.PersistentClient(path="/opt/vectorstore")

# 批量插入
collection.add(
    documents=documents,
    embeddings=embeddings,
    ids=ids,
    metadatas=metadatas
)
```

## 监控与日志

### 日志管理

#### 后端日志

日志位置：`/opt/Financial_Asset_QA_System/logs/`

配置日志轮转 `/etc/logrotate.d/financial-qa`：

```
/opt/Financial_Asset_QA_System/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload financial-qa-backend > /dev/null 2>&1 || true
    endscript
}
```

#### 查看日志

```bash
# 实时查看日志
tail -f /opt/Financial_Asset_QA_System/logs/app.log

# 查看错误日志
grep ERROR /opt/Financial_Asset_QA_System/logs/app.log

# 查看服务日志
sudo journalctl -u financial-qa-backend -f
```

### 性能监控

#### 系统监控

```bash
# CPU 和内存使用
htop

# 磁盘使用
df -h

# 网络连接
netstat -tunlp | grep -E '8000|6379|5173'
```

#### Redis 监控

```bash
redis-cli INFO
redis-cli MONITOR
redis-cli --stat
```

#### 应用监控

推荐使用：
- **Prometheus + Grafana**：指标监控
- **Sentry**：错误追踪
- **ELK Stack**：日志分析

## 故障排查

### 1. 后端服务无法启动

#### 检查端口占用

```bash
# 检查 8000 端口
sudo lsof -i :8000
sudo netstat -tunlp | grep 8000

# 杀死占用进程
sudo kill -9 <PID>
```

#### 检查 Python 环境

```bash
# 验证 Python 版本
python --version  # 应该是 3.11+

# 验证依赖安装
pip list | grep -E 'fastapi|anthropic|chromadb'

# 重新安装依赖
pip install --upgrade -r requirements.txt
```

#### 检查环境变量

```bash
# 验证 .env 文件
cat backend/.env

# 测试 API Key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-6","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

### 2. Redis 连接失败

#### 检查 Redis 服务

```bash
# 检查服务状态
sudo systemctl status redis

# 测试连接
redis-cli ping  # 应返回 PONG

# 检查配置
redis-cli CONFIG GET bind
redis-cli CONFIG GET protected-mode
```

#### 修复连接问题

```bash
# 允许远程连接（谨慎使用）
sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
sudo systemctl restart redis

# 或使用 Docker
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

### 3. 模型下载失败

#### 使用国内镜像

```bash
# 设置环境变量
export HF_ENDPOINT=https://hf-mirror.com

# 或在 .env 中添加
echo "HF_ENDPOINT=https://hf-mirror.com" >> backend/.env
```

#### 手动下载模型

```bash
# 创建模型目录
mkdir -p models/huggingface/hub

# 使用 git-lfs 下载
cd models/huggingface/hub
git lfs install
git clone https://huggingface.co/BAAI/bge-base-zh-v1.5
git clone https://huggingface.co/BAAI/bge-reranker-base
```

### 4. 前端无法连接后端

#### 检查 CORS 配置

确保后端允许跨域请求：

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 检查防火墙

```bash
# Ubuntu/Debian
sudo ufw allow 8000
sudo ufw allow 5173

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=5173/tcp
sudo firewall-cmd --reload
```

### 5. 内存不足

#### 监控内存使用

```bash
# 查看内存使用
free -h

# 查看进程内存
ps aux --sort=-%mem | head -10
```

#### 优化内存使用

```bash
# 增加 swap 空间
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 清理缓存
sudo sync && sudo sysctl -w vm.drop_caches=3
```

### 6. API 请求超时

#### 增加超时时间

```python
# backend/app/config.py
ANTHROPIC_TIMEOUT = 300  # 5 分钟

# Nginx 配置
proxy_read_timeout 300s;
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
```

#### 检查网络连接

```bash
# 测试 Anthropic API 连通性
curl -I https://api.anthropic.com

# 检查 DNS 解析
nslookup api.anthropic.com

# 使用代理（如需要）
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

## 安全建议

### 1. API 密钥安全

- **不要**将 API 密钥提交到版本控制系统
- 使用环境变量或密钥管理服务（如 AWS Secrets Manager）
- 定期轮换 API 密钥
- 限制 API 密钥的权限和配额

### 2. 网络安全

```bash
# 配置防火墙，只开放必要端口
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Redis 只监听本地
bind 127.0.0.1
protected-mode yes
requirepass your_strong_password
```

### 3. HTTPS 配置

强制使用 HTTPS：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # ... 其他配置
}
```

### 4. 访问控制

```nginx
# 限制 API 请求频率
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    # ... 其他配置
}

# IP 白名单（可选）
location /api/admin/ {
    allow 192.168.1.0/24;
    deny all;
    # ... 其他配置
}
```

### 5. 数据备份

```bash
# 备份脚本 /opt/backup.sh
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份向量数据库
tar -czf $BACKUP_DIR/vectorstore_$DATE.tar.gz /opt/Financial_Asset_QA_System/vectorstore

# 备份 Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# 删除 30 天前的备份
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete
```

设置定时任务：

```bash
# 每天凌晨 2 点备份
crontab -e
0 2 * * * /opt/backup.sh
```

## 扩展部署

### 负载均衡

使用 Nginx 实现后端负载均衡：

```nginx
upstream backend_servers {
    least_conn;
    server 127.0.0.1:8000 weight=1;
    server 127.0.0.1:8001 weight=1;
    server 127.0.0.1:8002 weight=1;
}

location /api/ {
    proxy_pass http://backend_servers/;
    # ... 其他配置
}
```

### Redis 集群

使用 Redis Sentinel 或 Redis Cluster 实现高可用。

### 容器编排

使用 Kubernetes 部署：

```yaml
# 示例 deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: financial-qa-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: financial-qa-backend
  template:
    metadata:
      labels:
        app: financial-qa-backend
    spec:
      containers:
      - name: backend
        image: financial-qa-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic
```

## 总结

本文档涵盖了金融资产问答系统的完整部署流程，包括 Docker 部署、手动部署、性能优化、监控日志和故障排查。

关键要点：
- 确保 API 密钥配置正确
- Redis 服务正常运行
- 模型文件下载完整
- 网络连接稳定
- 定期备份数据
- 监控系统性能

如遇到问题，请参考故障排查章节或提交 Issue。
