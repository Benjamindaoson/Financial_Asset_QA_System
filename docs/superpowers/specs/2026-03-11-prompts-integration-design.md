# Prompts.yaml 规范化与系统集成设计

**日期**: 2026-03-11
**版本**: 1.0.0
**状态**: 已批准
**作者**: Financial QA System Team

---

## 执行摘要

本设计文档描述了如何规范化 `prompts.yaml` 文件，并将其集成到 Financial Asset QA System 中，实现：
1. **提升路由准确性** - 通过混合路由（规则 + LLM）处理复杂查询
2. **改进响应质量** - 使用结构化的 LLM Generator 生成专业回答
3. **确保合规性** - 通过双重检查（规则 + LLM）拦截违规内容

**核心方案：** 渐进式增强（方案 A）
- 保留现有规则路由器作为快速路径
- 在低置信度时调用 LLM Router 增强
- 所有响应经过 LLM Generator 和 Compliance Checker

**预期效果：**
- 90% 查询保持快速（< 5ms 路由）
- 10% 复杂查询使用 LLM 增强
- 月成本约 $17（1000 查询/天）

---

## 目录

1. [概述](#概述)
2. [目标](#目标)
3. [方案选择](#方案选择)
4. [架构设计](#架构设计)
5. [核心组件](#核心组件)
6. [置信度计算](#置信度计算)
7. [错误处理](#错误处理)
8. [配置管理](#配置管理)
9. [成本估算](#成本估算)
10. [实施计划](#实施计划)

---

## 概述

### 背景

当前系统使用基于规则的 `QueryRouter` 进行查询路由，优点是快速、可靠，但在处理复杂语义和歧义查询时存在局限性。

用户创建了 `prompts.yaml` 文件，包含三个核心 Prompt：
- **Router**: LLM 驱动的查询分类器
- **Generator**: RAG 响应生成器
- **Compliance**: 合规检查器

### 设计目标

将 `prompts.yaml` 集成到系统中，同时：
- ✅ 保留现有规则路由器的优势（快速、可靠）
- ✅ 利用 LLM 处理复杂查询
- ✅ 提升响应质量和合规性
- ✅ 控制成本和延迟

---

## 目标

### 功能目标
- ✅ 规范化 prompts.yaml 文件结构
- ✅ 实现混合路由层（规则路由器 + LLM Router）
- ✅ 集成 LLM 响应生成器
- ✅ 实现双重合规检查机制
- ✅ 支持流式响应
- ✅ 支持配置热更新

### 性能目标
- ✅ 90% 查询保持快速路径（< 5ms 路由）
- ✅ 10% 复杂查询使用 LLM 增强（< 500ms）
- ✅ 端到端响应时间 < 3s（P95）

### 成本目标
- ✅ 月成本控制在 $30 以内（1000 查询/天）

---

## 方案选择

### 对比分析

| 方案 | 路由策略 | 成本/月 | 性能 | 复杂度 | 推荐度 |
|------|---------|---------|------|--------|--------|
| A. 渐进式增强 | 规则优先 + LLM 增强 | $17 | ⭐⭐⭐⭐⭐ | 中 | ⭐⭐⭐⭐⭐ |
| B. 全 LLM 驱动 | LLM 优先 + 规则 fallback | $25 | ⭐⭐⭐ | 低 | ⭐⭐ |
| C. 仅响应增强 | 规则路由（不变） | $17 | ⭐⭐⭐⭐ | 低 | ⭐⭐⭐ |

### 最终选择：方案 A（渐进式增强）

**理由：**
1. **平衡性能和准确性** - 快速路径 + 智能增强
2. **成本可控** - 与方案 C 相同，但路由更准确
3. **风险最低** - 规则路由器作为可靠的 fallback
4. **全面提升** - 路由和响应都得到改进

---

## 架构设计

### 整体架构图

```
用户查询
    ↓
混合路由层
    ├─ 规则路由器（快速路径，< 5ms）
    ├─ 置信度计算
    └─ LLM Router（低置信度时调用）
    ↓
执行工具调用
    ├─ get_price
    ├─ get_history
    ├─ search_web
    └─ search_rag
    ↓
数据整合
    ├─ API 数据
    ├─ RAG 文档
    └─ 置信度信息
    ↓
LLM Generator（响应生成）
    ↓
Compliance Checker（合规检查）
    ├─ 规则检查（快速）
    └─ LLM 检查（深度）
    ↓
返回用户
```

### 文件结构

```
Financial_Asset_QA_System/
├── backend/
│   ├── app/
│   │   ├── core/                    # 新增核心模块
│   │   │   ├── __init__.py
│   │   │   ├── prompt_manager.py   # Prompt 管理器
│   │   │   ├── llm_client.py       # 统一 LLM 客户端
│   │   │   ├── response_generator.py  # 响应生成器
│   │   │   └── compliance_checker.py  # 合规检查器
│   │   │
│   │   ├── routing/                 # 路由模块（扩展）
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # 现有规则路由器（保持不变）
│   │   │   ├── hybrid_router.py    # 新增：混合路由器
│   │   │   └── llm_router.py       # 新增：LLM 路由器
│   │   │
│   │   ├── agent/
│   │   │   └── core.py             # 修改：集成新组件
│   │   │
│   │   └── config.py               # 扩展：添加新配置项
│   │
│   └── requirements.txt             # 添加依赖：pyyaml, jinja2
│
├── prompts.yaml                     # 规范化的 Prompt 配置
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-03-11-prompts-integration-design.md
```

---

## 核心组件

### 1. PromptManager（Prompt 管理器）

**职责：**
- 加载和解析 prompts.yaml
- 提供 prompt 模板访问接口
- 渲染模板变量（使用 Jinja2）
- 获取配置参数
- 支持热更新

**关键接口：**
```python
class PromptManager:
    def get_system_prompt(self, prompt_type: str) -> str
    def render_user_prompt(self, prompt_type: str, **kwargs) -> str
    def get_temperature(self, prompt_type: str) -> float
    def reload(self) -> None
```

**位置：** `backend/app/core/prompt_manager.py`

---

### 2. LLMClient（统一 LLM 客户端）

**职责：**
- 封装 DeepSeek API 调用
- 提供统一的聊天补全接口
- 处理超时和重试
- 支持 JSON 模式输出

**模型选择：** 统一使用 DeepSeek（成本低、性能足够）

**关键接口：**
```python
class LLMClient:
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None
    ) -> str
```

**位置：** `backend/app/core/llm_client.py`

---

### 3. HybridRouter（混合路由器）

**职责：**
- 协调规则路由器和 LLM 路由器
- 计算置信度
- 决定使用哪个路由结果
- 合并路由结果
- 错误处理和降级

**决策逻辑：**
```python
if confidence > 0.8:
    使用规则路由
else:
    调用 LLM Router
    if LLM 成功:
        合并两者优势
    else:
        回退到规则路由
```

**位置：** `backend/app/routing/hybrid_router.py`

---

### 4. LLMRouter（LLM 路由器）

**职责：**
- 调用 DeepSeek API 进行查询分类
- 解析 JSON 响应
- 验证路由结果

**输出格式：**
```json
{
  "question_type": "real_time_quote",
  "confidence": 0.95,
  "route": "api_direct",
  "entities": {
    "ticker": "AAPL",
    "company": "Apple",
    "time_range": "today"
  },
  "reasoning": "明确询问实时价格变动"
}
```

**位置：** `backend/app/routing/llm_router.py`

---

### 5. ResponseGenerator（响应生成器）

**职责：**
- 基于工具结果生成结构化响应
- 使用 Generator prompt
- 确保输出符合模板格式
- 支持流式生成

**输出模板：**
```markdown
## [问题标题]

### 📊 数据摘要
[结构化数据展示]
数据来源：[API名称] | 时间：[timestamp]

### 📝 分析说明
[基于数据的客观分析]

### 📎 参考来源
- [文档标题] | 发布日期：[date]

### 💡 相关问题
- [推荐追问1]
- [推荐追问2]

---
⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。
```

**位置：** `backend/app/core/response_generator.py`

---

### 6. ComplianceChecker（合规检查器）

**职责：**
- 检查响应内容合规性
- 双重检查（规则 + LLM）
- 识别违规内容
- 提供安全替代回复

**检查流程：**
```python
1. 规则检查（< 1ms）
   - 投资建议关键词
   - 免责声明检查

2. 如果规则检查发现高风险 → 直接拦截

3. 否则，LLM 深度检查（~200ms）
   - 数据编造检查
   - 敏感内容检查

4. 合并结果，取更严格的
```

**位置：** `backend/app/core/compliance_checker.py`

---

## 置信度计算

### 计算公式

```python
confidence = (
    keyword_score * 0.4 +      # 关键词匹配度
    entity_score * 0.3 +       # 实体提取成功率
    complexity_score * 0.3     # 查询复杂度（反向）
)

# 阈值：0.8
# > 0.8：使用规则路由
# ≤ 0.8：调用 LLM Router
```

### 评分规则

#### 1. 关键词匹配度
- 3+ 个关键词：1.0
- 2 个关键词：0.7
- 1 个关键词：0.5
- 无匹配：0.2

#### 2. 实体提取成功率
- 股票代码 + 时间：1.0
- 仅股票代码：0.7
- 仅时间：0.5
- 都无：0.3

#### 3. 查询复杂度（反向）
- 简单查询：1.0
- 中等复杂：0.6
- 高度复杂：0.3

**复杂度判断：**
- 包含"为什么"、"原因"：+1
- 多个股票代码：+1
- 对比词：+1
- 长度 > 30 字：+1

### 实际案例

| 查询 | keyword | entity | complexity | confidence | 决策 |
|------|---------|--------|-----------|-----------|------|
| "AAPL今天涨了多少？" | 1.0 | 1.0 | 1.0 | 1.0 | 规则路由 |
| "为什么特斯拉今天暴涨？" | 0.7 | 0.7 | 0.6 | 0.67 | LLM Router |
| "什么是市盈率？" | 0.5 | 0.3 | 1.0 | 0.59 | LLM Router |

---

## 错误处理

### 降级策略矩阵

| 规则路由 | 规则置信度 | LLM Router | LLM 置信度 | 最终决策 |
|---------|-----------|-----------|-----------|---------|
| ✅ 成功 | > 0.8 | 不调用 | - | 使用规则路由 |
| ✅ 成功 | ≤ 0.8 | ✅ 成功 | > 0.7 | 合并两者 |
| ✅ 成功 | ≤ 0.8 | ✅ 成功 | ≤ 0.7 | 使用规则路由 |
| ✅ 成功 | ≤ 0.8 | ❌ 失败 | - | 使用规则路由 |
| ❌ 失败 | - | ✅ 成功 | > 0.7 | 使用 LLM 路由 |
| ❌ 失败 | - | ✅ 成功 | ≤ 0.7 | 默认路由 |
| ❌ 失败 | - | ❌ 失败 | - | 默认路由 |

### 关键原则

1. **规则路由器是第一选择**（快速、可靠）
2. **LLM Router 是增强和备份**（智能、灵活）
3. **默认路由是最后保险**（保证系统不崩溃）
4. **多层降级，确保鲁棒性**

---

## 配置管理

### Prompts.yaml 结构

```yaml
metadata:
  version: "1.0.0"
  last_updated: "2026-03-11"

config:
  temperature:
    router: 0.0
    generator: 0.3
    compliance: 0.0

  max_tokens:
    router: 500
    generator: 2000
    compliance: 800

  hybrid_routing:
    enabled: true
    confidence_threshold: 0.8
    fallback_to_rule: true

prompts:
  router:
    system_prompt: |
      ...
    user_template: |
      {user_question}
    examples:
      - input: "AAPL今天涨了多少？"
        output: |
          {...}

  generator:
    system_prompt: |
      ...
    user_template: |
      ...

  compliance:
    system_prompt: |
      ...
    user_template: |
      ...
```

### 环境变量配置

```python
# backend/app/config.py（新增）

# Prompt 配置
PROMPTS_CONFIG_PATH: str = "prompts.yaml"

# 混合路由配置
HYBRID_ROUTING_ENABLED: bool = True
HYBRID_ROUTING_CONFIDENCE_THRESHOLD: float = 0.8

# LLM 调用配置
LLM_ROUTER_TEMPERATURE: float = 0.0
LLM_ROUTER_MAX_TOKENS: int = 500
LLM_ROUTER_TIMEOUT: int = 10

LLM_GENERATOR_TEMPERATURE: float = 0.3
LLM_GENERATOR_MAX_TOKENS: int = 2000
LLM_GENERATOR_TIMEOUT: int = 30

LLM_COMPLIANCE_TEMPERATURE: float = 0.0
LLM_COMPLIANCE_MAX_TOKENS: int = 800
LLM_COMPLIANCE_TIMEOUT: int = 10

# 合规检查配置
COMPLIANCE_RULE_CHECK_ENABLED: bool = True
COMPLIANCE_LLM_CHECK_ENABLED: bool = True
COMPLIANCE_STRICT_MODE: bool = True
```

### 配置优先级

1. **环境变量**（.env 文件）- 最高优先级
2. **prompts.yaml** 中的 config 部分
3. **代码中的默认值** - 最低优先级

---

## 成本估算

### DeepSeek 定价（假设）
- 输入：¥0.001/1K tokens
- 输出：¥0.002/1K tokens

### 每次调用成本

| 组件 | 输入 tokens | 输出 tokens | 成本/次 |
|------|------------|------------|---------|
| LLM Router | 500 | 150 | ¥0.001 |
| Response Generator | 2000 | 500 | ¥0.003 |
| Compliance Checker | 800 | 150 | ¥0.001 |

### 月成本估算（1000 查询/天）

```
假设：
- 10% 查询调用 LLM Router（100次/天）
- 100% 查询调用 Generator（1000次/天）
- 100% 查询调用 Compliance（1000次/天）

每天成本：
- Router：100次 × ¥0.001 = ¥0.10
- Generator：1000次 × ¥0.003 = ¥3.00
- Compliance：1000次 × ¥0.001 = ¥1.00
总计：¥4.10/天

月成本：¥4.10 × 30 = ¥123（约 $17/月）
```

---

## 实施计划

### 阶段 1：基础设施（第 1-2 天）
- [ ] 规范化 prompts.yaml
- [ ] 创建 PromptManager
- [ ] 创建 LLMClient
- [ ] 添加依赖（pyyaml, jinja2）
- [ ] 更新配置文件

### 阶段 2：路由层（第 3-4 天）
- [ ] 实现 LLMRouter
- [ ] 实现 HybridRouter
- [ ] 实现置信度计算
- [ ] 集成到 AgentCore

### 阶段 3：响应生成（第 5-6 天）
- [ ] 实现 ResponseGenerator
- [ ] 实现数据整合逻辑
- [ ] 支持流式响应
- [ ] 集成到 AgentCore

### 阶段 4：合规检查（第 7 天）
- [ ] 实现 ComplianceChecker
- [ ] 实现规则检查
- [ ] 实现 LLM 检查
- [ ] 集成到 AgentCore

### 阶段 5：测试和优化（第 8-10 天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试
- [ ] 置信度阈值调优
- [ ] 文档更新

---

## 验收标准

### 功能验收
- ✅ prompts.yaml 加载成功
- ✅ 混合路由正常工作
- ✅ LLM Router 准确率 > 90%
- ✅ 响应生成符合模板格式
- ✅ 合规检查拦截违规内容
- ✅ 流式响应正常工作
- ✅ 配置热更新正常工作

### 性能验收
- ✅ 规则路由延迟 < 5ms
- ✅ LLM Router 延迟 < 500ms
- ✅ 端到端响应时间 < 3s（P95）
- ✅ 90% 查询走快速路径

### 成本验收
- ✅ 月成本 < $30（1000 查询/天）

---

## 风险和缓解

### 风险 1：LLM API 不稳定
**缓解措施：**
- 规则路由器作为 fallback
- 实现重试机制
- 监控 API 可用性

### 风险 2：置信度阈值不准确
**缓解措施：**
- 收集真实查询数据
- A/B 测试不同阈值
- 支持动态调整

### 风险 3：成本超预算
**缓解措施：**
- 监控每日成本
- 调整置信度阈值
- 实现请求限流

---

## 附录

### A. 相关文档
- Prompts.yaml 完整示例（项目根目录）
- API Quick Reference
- Product Roadmap

### B. 参考资料
- DeepSeek API 文档
- OpenAI API 文档
- Jinja2 模板引擎文档

---

**文档结束**
