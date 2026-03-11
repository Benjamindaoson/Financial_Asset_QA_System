# 配置文件更新 - 添加缓存和优化配置

## 新增配置项

在 `backend/app/config.py` 中添加以下配置：

```python
# ============================================================================
# 智能缓存配置
# ============================================================================

# L1 缓存（内存 LRU）
CACHE_L1_SIZE: int = 1000
CACHE_ENABLE_L1: bool = True

# L2 缓存（Redis）
CACHE_L2_TTL: int = 3600  # 1 小时
CACHE_ENABLE_L2: bool = True

# L3 缓存（语义相似）
CACHE_L3_THRESHOLD: float = 0.95
CACHE_ENABLE_L3: bool = True

# ============================================================================
# 查询路由配置
# ============================================================================

# 查询分类
ROUTER_ENABLE_CLASSIFICATION: bool = True

# 策略选择
ROUTER_DEFAULT_STRATEGY: str = "adaptive"  # adaptive, simple, full

# ============================================================================
# Redis 配置（用于 L2 缓存）
# ============================================================================

REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
REDIS_DB: int = 0
REDIS_PASSWORD: str = ""
```

## 环境变量配置

在 `backend/.env` 中添加：

```bash
# ============================================================================
# 智能缓存配置
# ============================================================================

# L1 缓存
CACHE_L1_SIZE=1000
CACHE_ENABLE_L1=true

# L2 缓存
CACHE_L2_TTL=3600
CACHE_ENABLE_L2=true

# L3 缓存
CACHE_L3_THRESHOLD=0.95
CACHE_ENABLE_L3=true

# ============================================================================
# Redis 配置
# ============================================================================

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ============================================================================
# 查询路由配置
# ============================================================================

ROUTER_ENABLE_CLASSIFICATION=true
ROUTER_DEFAULT_STRATEGY=adaptive
```

## 配置说明

### L1 缓存（内存）
- **CACHE_L1_SIZE**: 内存缓存最大条目数（默认 1000）
- **CACHE_ENABLE_L1**: 是否启用 L1 缓存（默认 true）
- **特点**: 最快（< 1ms），但容量有限

### L2 缓存（Redis）
- **CACHE_L2_TTL**: 缓存过期时间（秒，默认 3600 = 1 小时）
- **CACHE_ENABLE_L2**: 是否启用 L2 缓存（默认 true）
- **特点**: 快速（5-10ms），持久化，支持分布式

### L3 缓存（语义）
- **CACHE_L3_THRESHOLD**: 相似度阈值（默认 0.95）
- **CACHE_ENABLE_L3**: 是否启用 L3 缓存（默认 true）
- **特点**: 智能（20-30ms），语义匹配

### Redis 配置
- **REDIS_HOST**: Redis 服务器地址
- **REDIS_PORT**: Redis 端口
- **REDIS_DB**: Redis 数据库编号
- **REDIS_PASSWORD**: Redis 密码（可选）

### 查询路由配置
- **ROUTER_ENABLE_CLASSIFICATION**: 是否启用查询分类
- **ROUTER_DEFAULT_STRATEGY**: 默认策略（adaptive/simple/full）

## 性能调优建议

### 高并发场景
```bash
# 增大 L1 缓存
CACHE_L1_SIZE=5000

# 延长 L2 缓存时间
CACHE_L2_TTL=7200

# 降低 L3 阈值（更多命中）
CACHE_L3_THRESHOLD=0.90
```

### 低内存场景
```bash
# 减小 L1 缓存
CACHE_L1_SIZE=500

# 禁用 L3 缓存
CACHE_ENABLE_L3=false
```

### 无 Redis 场景
```bash
# 禁用 L2 缓存
CACHE_ENABLE_L2=false

# 增大 L1 缓存补偿
CACHE_L1_SIZE=2000
```

## 监控指标

通过 API 端点监控缓存效果：

```bash
# 查看缓存统计
curl http://localhost:8000/api/v2/rag/cache/stats

# 查看路由统计
curl http://localhost:8000/api/v2/rag/router/stats

# 健康检查
curl http://localhost:8000/api/v2/rag/health
```

## 故障排查

### Redis 连接失败
```bash
# 检查 Redis 是否运行
redis-cli ping

# 如果失败，禁用 L2 缓存
CACHE_ENABLE_L2=false
```

### 内存占用过高
```bash
# 减小 L1 缓存
CACHE_L1_SIZE=500

# 禁用 L3 缓存
CACHE_ENABLE_L3=false
```

### 缓存命中率低
```bash
# 降低 L3 阈值
CACHE_L3_THRESHOLD=0.90

# 延长 L2 过期时间
CACHE_L2_TTL=7200
```
