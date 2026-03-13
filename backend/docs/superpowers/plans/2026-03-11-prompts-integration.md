# Prompts.yaml 规范化与系统集成实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** 规范化 prompts.yaml 并集成混合路由、响应生成和合规检查功能

**Architecture:** 渐进式增强 - 保留规则路由器作为快速路径，在低置信度时调用 LLM Router，所有响应经过 LLM Generator 和 Compliance Checker

**Tech Stack:** Python 3.11+, FastAPI, DeepSeek API, PyYAML, Jinja2

---

## 实施计划概览

本计划分为 5 个阶段，共 12 个任务：
1. 基础设施（Task 1-3）
2. Prompt 管理和 LLM 客户端（Task 4-5）
3. 路由层实现（Task 6-7）
4. 响应生成和合规检查（Task 8-9）
5. 系统集成和验收（Task 10-12）

预计完成时间：8-10 天

---

## Task 1: 规范化 prompts.yaml

**Files:**
- Create: `prompts.yaml`

**目标:** 创建包含元数据、配置和三个 prompts 的规范化配置文件

- [ ] Step 1: 创建 prompts.yaml 文件
- [ ] Step 2: 验证 YAML 格式正确
- [ ] Step 3: 提交到 git

---

## Task 2: 添加 Python 依赖

**Files:**
- Modify: `backend/requirements.txt`

**目标:** 添加 pyyaml 和 jinja2 依赖

- [ ] Step 1: 在 requirements.txt 添加依赖
- [ ] Step 2: 安装依赖
- [ ] Step 3: 提交到 git

---

## Task 3: 扩展配置文件

**Files:**
- Modify: `backend/app/config.py`

**目标:** 添加 Prompt 和混合路由相关配置项

- [ ] Step 1: 添加新配置项到 Settings 类
- [ ] Step 2: 验证配置加载
- [ ] Step 3: 提交到 git

---

## Task 4: 创建 Prompt 管理器

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/prompt_manager.py`
- Create: `backend/tests/test_prompt_manager.py`

**目标:** 实现 PromptManager 用于加载和管理 prompts.yaml

- [ ] Step 1: 写失败的测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 创建 core 模块
- [ ] Step 4: 实现 PromptManager
- [ ] Step 5: 运行测试验证通过
- [ ] Step 6: 提交到 git

---

## Task 5: 创建统一 LLM 客户端

**Files:**
- Create: `backend/app/core/llm_client.py`
- Create: `backend/tests/test_llm_client.py`

**目标:** 实现 LLMClient 封装 DeepSeek API 调用

- [ ] Step 1: 写失败的测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 实现 LLMClient
- [ ] Step 4: 运行测试验证通过
- [ ] Step 5: 更新 core 模块导出
- [ ] Step 6: 提交到 git

---

## Task 6: 实现 LLM Router

**Files:**
- Create: `backend/app/routing/llm_router.py`
- Create: `backend/tests/test_llm_router.py`

**目标:** 实现 LLM Router 用于智能查询分类

- [ ] Step 1: 写失败的测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 实现 LLMRouter
- [ ] Step 4: 运行测试验证通过
- [ ] Step 5: 提交到 git

---

## Task 7: 实现混合路由器

**Files:**
- Create: `backend/app/routing/hybrid_router.py`
- Create: `backend/tests/test_hybrid_router.py`
- Modify: `backend/app/routing/__init__.py`

**目标:** 实现 HybridRouter 整合规则路由和 LLM Router

- [ ] Step 1: 写失败的测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 实现 HybridRouter（包含置信度计算）
- [ ] Step 4: 运行测试验证通过
- [ ] Step 5: 更新 routing 模块导出
- [ ] Step 6: 提交到 git

---

## Task 8: 实现响应生成器

**Files:**
- Create: `backend/app/core/response_generator.py`
- Create: `backend/tests/test_response_generator.py`

**目标:** 实现 ResponseGenerator 用于结构化输出

- [ ] Step 1: 写失败的测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 实现 ResponseGenerator
- [ ] Step 4: 运行测试验证通过
- [ ] Step 5: 更新 core 模块导出
- [ ] Step 6: 提交到 git

---

## Task 9: 实现合规检查器

**Files:**
- Create: `backend/app/core/compliance_checker.py`
- Create: `backend/tests/test_compliance_checker.py`

**目标:** 实现 ComplianceChecker 提供双重检查机制

- [ ] Step 1: 写失败的测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 实现 ComplianceChecker
- [ ] Step 4: 运行测试验证通过
- [ ] Step 5: 更新 core 模块导出
- [ ] Step 6: 提交到 git

---

## Task 10: 集成到 AgentCore

**Files:**
- Modify: `backend/app/agent/core.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_integration.py`

**目标:** 集成所有新组件到 AgentCore

- [ ] Step 1: 写集成测试
- [ ] Step 2: 运行测试验证失败
- [ ] Step 3: 修改 AgentCore 集成新组件
- [ ] Step 4: 修改 main.py 添加启动初始化
- [ ] Step 5: 运行集成测试验证通过
- [ ] Step 6: 运行所有测试
- [ ] Step 7: 提交到 git

---

## Task 11: 端到端验收测试

**目标:** 验证系统功能和性能

- [ ] Step 1: 启动服务
- [ ] Step 2: 测试简单查询（规则路由）
- [ ] Step 3: 测试复杂查询（LLM Router）
- [ ] Step 4: 测试合规检查
- [ ] Step 5: 检查日志
- [ ] Step 6: 性能测试
- [ ] Step 7: 最终提交

---

## Task 12: 更新文档

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

**目标:** 更新文档说明新功能

- [ ] Step 1: 更新 README.md
- [ ] Step 2: 更新配置示例
- [ ] Step 3: 提交到 git

---

## 验收标准

### 功能验收
- prompts.yaml 加载成功
- 混合路由正常工作
- LLM Router 准确率 > 90%
- 响应生成符合模板格式
- 合规检查拦截违规内容

### 性能验收
- 规则路由延迟 < 5ms
- LLM Router 延迟 < 500ms
- 端到端响应时间 < 3s（P95）
- 90% 查询走快速路径

### 成本验收
- 月成本 < $30（1000 查询/天）

---

**计划完成**
