# 🧪 RAG 系统快速测试指南

## 3 分钟快速测试

### 步骤 1: 启动应用 (30 秒)

```bash
cd backend
uvicorn app.main:app --reload
```

等待看到: `Application startup complete.`

---

### 步骤 2: 测试健康检查 (10 秒)

```bash
curl http://localhost:8000/api/v2/rag/health
```

**预期**: 返回 `"status": "healthy"`

---

### 步骤 3: 测试基础检索 (30 秒)

```bash
curl -X POST http://localhost:8000/api/v2/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率？", "generate_answer": true}'
```

**预期**: 返回答案和相关文档

---

### 步骤 4: 测试智能缓存 (1 分钟)

```bash
# 第一次查询（无缓存）
time curl -X POST http://localhost:8000/api/v2/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率？", "use_cache": true}'

# 第二次查询（应该命中缓存）
time curl -X POST http://localhost:8000/api/v2/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率？", "use_cache": true}'
```

**预期**: 第二次查询明显更快（< 100ms）

---

### 步骤 5: 查看统计信息 (30 秒)

```bash
# 缓存统计
curl http://localhost:8000/api/v2/rag/cache/stats

# 路由统计
curl http://localhost:8000/api/v2/rag/router/stats
```

---

## 使用 Swagger UI 测试（推荐）

1. 打开浏览器: http://localhost:8000/docs
2. 找到 "RAG v2 (Optimized)" 分组
3. 点击 "POST /api/v2/rag/search"
4. 点击 "Try it out"
5. 输入查询并执行

---

## 自动化测试

```bash
# 运行完整测试套件
python test_rag_system.py
```

测试内容:
- ✅ 健康检查
- ✅ 基础检索
- ✅ 智能缓存
- ✅ 查询路由
- ✅ 性能测试
- ✅ 并发测试

---

## 测试查询示例

```bash
# 简单定义查询
curl -X POST http://localhost:8000/api/v2/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率？"}'

# 计算类查询
curl -X POST http://localhost:8000/api/v2/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "如何计算 ROE？"}'

# 对比分析查询
curl -X POST http://localhost:8000/api/v2/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "市盈率和市净率的区别"}'
```

---

## 性能基准

| 指标 | 目标 | 说明 |
|------|------|------|
| 缓存命中 | < 100ms | 第二次相同查询 |
| 简单查询 | < 1000ms | 跳过查询改写 |
| 复杂查询 | < 2000ms | 完整流程 |

---

## 常见问题

**Q: 连接被拒绝？**
```bash
# 检查应用是否运行
curl http://localhost:8000/
```

**Q: 缓存未命中？**
```bash
# 查看缓存统计
curl http://localhost:8000/api/v2/rag/cache/stats
```

**Q: 性能不达标？**
- 确保使用了缓存 (`use_cache: true`)
- 检查查询类型是否正确识别
- 查看性能详情 (`performance` 字段)

---

**测试完成！** ✅

如需详细测试，请参考 `test_rag_system.py` 自动化测试脚本。
