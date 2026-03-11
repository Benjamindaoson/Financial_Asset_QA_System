# 性能监控系统使用指南

## 概述

系统已集成完整的性能监控功能，提供实时性能指标、健康检查和统计数据。

## API 端点

### 1. 获取性能指标
```bash
GET /api/monitoring/metrics
```

返回系统性能指标：
- CPU 使用率
- 内存使用情况
- 磁盘使用情况
- 响应时间统计（平均、P50、P95）
- 请求计数和错误计数
- 系统运行时间

### 2. 详细健康检查
```bash
GET /api/monitoring/health/detailed
```

返回详细健康状态：
- 整体状态（healthy/degraded/unhealthy）
- 各组件状态（RAG、LLM、系统）
- 关键指标（文档数、CPU、内存等）

### 3. 端点统计
```bash
GET /api/monitoring/stats/endpoints
```

返回各 API 端点的统计信息：
- 请求次数
- 平均响应时间
- 错误次数和错误率

### 4. 重置统计
```bash
POST /api/monitoring/stats/reset
```

重置所有性能统计数据。

## 使用示例

```bash
# 查看性能指标
curl http://127.0.0.1:8001/api/monitoring/metrics

# 查看详细健康状态
curl http://127.0.0.1:8001/api/monitoring/health/detailed

# 查看端点统计
curl http://127.0.0.1:8001/api/monitoring/stats/endpoints
```

## 自动监控

系统已集成性能监控中间件，自动记录所有请求的：
- 响应时间
- 成功/失败状态
- 端点访问统计

无需额外配置，启动系统即可使用。
