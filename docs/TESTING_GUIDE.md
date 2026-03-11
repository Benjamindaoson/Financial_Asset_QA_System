# 高级功能测试指南
# Advanced Features Testing Guide

## 测试环境准备

### 1. 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 2. 验证服务状态

```bash
curl http://localhost:8000/health
```

预期响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "redis": "connected",
    "chromadb": "ready",
    "deepseek_api": "configured"
  }
}
```

## 功能测试清单

### ✅ 测试1: 多数据源交叉验证

**测试目标**: 验证系统能从3个数据源获取价格并交叉验证

**测试命令**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=AAPL&validate=true"
```

**验证点**:
- [ ] 返回中位数价格
- [ ] 包含3个数据源的价格
- [ ] 计算了标准差
- [ ] 一致性评级（high/medium/low）
- [ ] 置信度评分

**预期响应结构**:
```json
{
  "price": 178.50,
  "currency": "USD",
  "consistency": "high",
  "confidence": "high",
  "validated": true,
  "details": {
    "message": "数据一致性良好，3个数据源偏差 ≤ 1%",
    "individual_prices": [...],
    "median": 178.51,
    "mean": 178.50,
    "std_dev": 0.02
  }
}
```

**失败场景测试**:
```bash
# 测试无效股票代码
curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=INVALID&validate=true"
```

预期：返回友好错误信息和建议

---

### ✅ 测试2: 深度涨跌分析

**测试目标**: 验证量价配合分析、相对强弱分析

**测试命令**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/change?symbol=AAPL&days=7"
```

**验证点**:
- [ ] 基础涨跌幅计算
- [ ] 量价配合分析（放量上涨/缩量下跌等）
- [ ] 相对强弱分析（与大盘对比）
- [ ] 综合结论生成

**预期响应结构**:
```json
{
  "price_change": {
    "change_percent": 5.2,
    "change_amount": 8.75,
    "trend": "上涨"
  },
  "volume_analysis": {
    "pattern": "放量上涨",
    "interpretation": "量价配合良好，上涨趋势健康",
    "volume_change_percent": 15.3
  },
  "relative_strength": {
    "performance": "跑赢大盘",
    "vs_market": 3.5,
    "interpretation": "强于大盘 3.5%"
  },
  "conclusion": "该股票呈现强势上涨态势..."
}
```

**不同天数测试**:
```bash
# 测试1天
curl -X POST "http://localhost:8000/api/v1/enhanced/change?symbol=AAPL&days=1"

# 测试30天
curl -X POST "http://localhost:8000/api/v1/enhanced/change?symbol=AAPL&days=30"
```

---

### ✅ 测试3: 意图识别和自适应回答

**测试目标**: 验证5种意图识别和3级用户水平估计

**测试命令**:

#### 3.1 定义类查询（初级用户）
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率"}'
```

**验证点**:
- [ ] intent = "definition"
- [ ] user_level = "beginner"
- [ ] 回答简单易懂
- [ ] 包含通俗解释

#### 3.2 方法类查询（中级用户）
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "如何计算市盈率"}'
```

**验证点**:
- [ ] intent = "method"
- [ ] user_level = "intermediate"
- [ ] 包含计算步骤
- [ ] 提供示例

#### 3.3 判断类查询（高级用户）
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "市盈率高于30是否合理"}'
```

**验证点**:
- [ ] intent = "judgment"
- [ ] user_level = "advanced"
- [ ] 提供多角度分析
- [ ] 包含专业术语

#### 3.4 对比类查询
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "市盈率和市净率的区别"}'
```

**验证点**:
- [ ] intent = "comparison"
- [ ] 对比表格或列表
- [ ] 突出差异点

#### 3.5 示例类查询
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "市盈率的例子"}'
```

**验证点**:
- [ ] intent = "example"
- [ ] 包含具体案例
- [ ] 实际数据支持

---

### ✅ 测试4: 混合查询处理

**测试目标**: 验证复合查询自动拆解和并行处理

**测试命令**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL现在多少钱？最近7天涨了多少？"}'
```

**验证点**:
- [ ] 检测到2个子查询
- [ ] 子查询1: 价格查询
- [ ] 子查询2: 涨跌查询
- [ ] 并行处理（查看日志时间戳）
- [ ] 整合答案

**预期流程**:
```
1. 检测到复合查询
2. 拆解为: ["AAPL现在多少钱", "最近7天涨了多少"]
3. 并行执行
4. 整合答案: "📊 价格信息：... \n📈 涨跌分析：..."
```

**复杂混合查询测试**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL和TSLA的价格分别是多少？哪个涨得更多？什么是市盈率？"}'
```

**验证点**:
- [ ] 检测到3个子查询
- [ ] 价格查询 × 2
- [ ] 涨跌对比 × 1
- [ ] 知识查询 × 1

---

### ✅ 测试5: 置信度评估和澄清

**测试目标**: 验证低置信度时请求用户澄清

**测试命令**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/route" \
  -H "Content-Type: application/json" \
  -d '{"query": "特斯拉"}'
```

**验证点**:
- [ ] 置信度 < 0.8
- [ ] route = "clarification_needed"
- [ ] 提供3个选项：价格/涨跌/知识
- [ ] 每个选项有清晰的label

**预期响应**:
```json
{
  "route": "clarification_needed",
  "confidence": 0.65,
  "clarification": {
    "message": "我不太确定您的问题类型，请选择：",
    "options": [
      {"type": "price", "label": "查询 TSLA 的当前价格"},
      {"type": "change", "label": "查询 TSLA 的涨跌情况"},
      {"type": "knowledge", "label": "了解相关金融知识"}
    ]
  }
}
```

**高置信度测试**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/route" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL最新价格是多少"}'
```

**验证点**:
- [ ] 置信度 > 0.8
- [ ] route = "price"
- [ ] 直接返回路由决策

---

### ✅ 测试6: 智能格式化

**测试目标**: 验证6种数据类型的自动格式选择

#### 6.1 对比类 → 表格
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/format" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AAPL和TSLA对比",
    "data": {
      "AAPL": {"price": 178.50, "change": 2.5},
      "TSLA": {"price": 245.30, "change": -1.2}
    }
  }'
```

**验证点**:
- [ ] type = "table"
- [ ] 包含headers和rows
- [ ] 数据正确对齐

#### 6.2 趋势类 → 图表
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/format" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AAPL价格趋势",
    "data": {
      "data": [
        {"date": "2024-01-01", "close": 170},
        {"date": "2024-01-02", "close": 172},
        {"date": "2024-01-03", "close": 175}
      ]
    }
  }'
```

**验证点**:
- [ ] type = "chart"
- [ ] chart_type = "line"
- [ ] 包含labels和datasets

#### 6.3 步骤类 → 有序列表
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/format" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何买股票",
    "data": {
      "steps": ["开户", "入金", "选股", "下单"]
    }
  }'
```

**验证点**:
- [ ] type = "ordered_list"
- [ ] 步骤按顺序排列

#### 6.4 特征类 → 无序列表
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/format" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AAPL的特点",
    "data": {
      "feature1": "科技龙头",
      "feature2": "高市值",
      "feature3": "稳定增长"
    }
  }'
```

**验证点**:
- [ ] type = "bullet_list"
- [ ] 特征清晰列出

#### 6.5 指标类 → 指标卡片
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/format" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AAPL指标",
    "data": {
      "price": 178.50,
      "change_percent": 2.5,
      "volume": 50000000
    }
  }'
```

**验证点**:
- [ ] type = "metrics_card"
- [ ] 包含多个指标
- [ ] 每个指标有label、value、unit、trend

---

### ✅ 测试7: 友好错误处理

**测试目标**: 验证各种错误场景的友好提示

#### 7.1 股票代码未找到
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "苹果公司股价"}'
```

**验证点**:
- [ ] 识别"苹果公司"
- [ ] 建议使用"AAPL"
- [ ] 提供相似股票列表
- [ ] 提供示例查询

#### 7.2 数据不可用
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=DELISTED&validate=true"
```

**验证点**:
- [ ] 解释原因（退市/维护）
- [ ] 提供替代方案
- [ ] 建议其他股票

#### 7.3 无效查询
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "asdfghjkl"}'
```

**验证点**:
- [ ] 友好提示
- [ ] 提供查询示例
- [ ] 分类展示（价格/涨跌/知识）

---

### ✅ 测试8: 完整流程测试

**测试目标**: 验证增强版聊天接口的完整流程

**测试命令**:
```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL最新价格是多少？", "enable_validation": true, "enable_intent_recognition": true}'
```

**验证流程**:
1. [ ] 接收查询
2. [ ] 智能路由（置信度评估）
3. [ ] 识别为价格查询
4. [ ] 调用多数据源验证
5. [ ] 生成回答
6. [ ] 智能格式化
7. [ ] 返回流式响应

**预期事件序列**:
```
event: status - "智能分析查询意图..."
event: route_decision - {"route": "price", "confidence": 0.95}
event: tool_start - {"name": "get_price_validated"}
event: tool_data - {价格数据}
event: chunk - "AAPL 当前价格：178.50 USD"
event: chunk - "数据验证：3个数据源一致性良好"
event: done - {formatted数据}
```

---

## 性能测试

### 测试9: 并行处理性能

**测试目标**: 验证混合查询的并行处理效率

**测试脚本**:
```bash
# 串行基准测试
time curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=AAPL&validate=false"
time curl -X POST "http://localhost:8000/api/v1/enhanced/change?symbol=AAPL&days=7"

# 并行测试（混合查询）
time curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL价格多少？涨跌如何？"}'
```

**验证点**:
- [ ] 并行时间 < 串行时间总和
- [ ] 理想情况：并行时间 ≈ max(单个查询时间)

### 测试10: 缓存效果

**测试目标**: 验证缓存提升性能

**测试脚本**:
```bash
# 第一次查询（无缓存）
time curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=AAPL&validate=true"

# 第二次查询（有缓存）
time curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=AAPL&validate=true"
```

**验证点**:
- [ ] 第二次查询明显更快
- [ ] 缓存命中率 > 80%

---

## 集成测试

### 测试11: 前后端集成

**测试目标**: 验证前端能正确调用增强版API

**前端测试代码**:
```javascript
// 在浏览器控制台执行
const response = await fetch('http://localhost:8000/api/v1/enhanced/chat', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    query: 'AAPL最新价格',
    enable_validation: true
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

**验证点**:
- [ ] SSE流式响应正常
- [ ] 前端能解析事件
- [ ] UI正确显示

---

## 回归测试

### 测试12: 原有功能不受影响

**测试目标**: 确保增强功能不影响原有功能

**测试命令**:
```bash
# 测试原有聊天接口
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL最新价格"}'

# 测试原有市场数据接口
curl "http://localhost:8000/api/market/price/AAPL"

# 测试RAG检索
curl "http://localhost:8000/rag/search?query=市盈率"
```

**验证点**:
- [ ] 所有原有接口正常工作
- [ ] 响应格式未改变
- [ ] 性能无明显下降

---

## 测试报告模板

```markdown
# 高级功能测试报告

## 测试环境
- 日期: YYYY-MM-DD
- 测试人: [姓名]
- 后端版本: 1.0.0
- Python版本: 3.11

## 测试结果汇总

| 测试项 | 状态 | 备注 |
|--------|------|------|
| 多数据源验证 | ✅ | 3个数据源正常 |
| 深度涨跌分析 | ✅ | 量价分析准确 |
| 意图识别 | ✅ | 5种意图全部识别 |
| 混合查询 | ✅ | 并行处理正常 |
| 置信度评估 | ✅ | 澄清机制有效 |
| 智能格式化 | ✅ | 6种格式正确 |
| 友好错误 | ✅ | 建议准确 |
| 完整流程 | ✅ | 端到端正常 |
| 性能测试 | ✅ | 响应时间 < 2s |
| 集成测试 | ✅ | 前后端正常 |
| 回归测试 | ✅ | 原有功能正常 |

## 发现的问题

1. [问题描述]
   - 严重程度: 高/中/低
   - 复现步骤: ...
   - 预期结果: ...
   - 实际结果: ...

## 性能数据

- 平均响应时间: XXX ms
- P95响应时间: XXX ms
- 缓存命中率: XX%
- 并发处理能力: XX req/s

## 建议

1. [优化建议]
2. [功能改进]
```

---

## 自动化测试脚本

```bash
#!/bin/bash
# test_all.sh - 运行所有测试

echo "开始测试..."

# 测试1: 多数据源验证
echo "测试1: 多数据源验证"
curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=AAPL&validate=true" | jq .

# 测试2: 深度涨跌分析
echo "测试2: 深度涨跌分析"
curl -X POST "http://localhost:8000/api/v1/enhanced/change?symbol=AAPL&days=7" | jq .

# 测试3: 意图识别
echo "测试3: 意图识别"
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率"}' | jq .

# 测试4: 混合查询
echo "测试4: 混合查询"
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL价格多少？涨跌如何？"}'

echo "测试完成！"
```

运行测试：
```bash
chmod +x test_all.sh
./test_all.sh
```
