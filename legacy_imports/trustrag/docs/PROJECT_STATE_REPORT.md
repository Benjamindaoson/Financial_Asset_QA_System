# Project Overview

## 1. 项目当前在做什么（What it is doing now）
**核心定位**：`trust_rag` 当前是一个**“高可信仲裁核心（Judgment Core）”**的类库实现，而非一个完整的 RAG 系统。

**已实现功能**：
- **严格的数据协议**：定义了 `EvidencePack`（证据包）和 `DocIR`（文档中间表达）作为系统交互的标准。
- **确定性仲裁逻辑**：实现了 `arbitrate_proposals`，能够基于预定义的规则（如置信度校验、证据一致性检查）对多个来源的“提案（Proposal）”进行裁决，输出最终的“判决（Verdict）”。
- **基础评估框架**：实现了 `evaluate_judgment`，用于对仲裁结果进行自动化评分。

**最小闭环**：
- 当前无法运行完整的“提问-回答”闭环。
- **能跑通的唯一闭环是**：`EvidencePack` (输入) -> `ProposalSet` (多路提案) -> `Arbitration` (仲裁逻辑) -> `Judgment` (输出)。这是一个纯逻辑校验闭环，不包含任何 LLM 调用或检索动作。

## 2. 当前系统的整体设计（System Design）
**模块划分与职责**：
- **`core/evidence`**：定义了事实（Fact）、观点（Opinion）等证据类型，并强制要求关联来源（Provenance）。这是系统的“数据基石”。
- **`core/judgment`**：系统的“大脑”。包含 `Proposal`（判决提案）和 `Verdict`（最终结论）。核心逻辑在于**拒绝不明确的提案**（INCONCLUSIVE），而非生成答案。
- **`core/parsing`**：定义了通用文档结构 `DocIR`，为未来的文档处理制定了标准接口。
- **`services` / `retrieval` / `answering`**：目前仅为目录占位（包含 `__init__.py` 或简单渲染代码），**内部逻辑几乎为空**。

**数据流**：
```mermaid
graph LR
    EP[EvidencePack] --> P[Proposals]
    P --> |arbitrate_proposals| AL[Arbitration Logic]
    AL --> |Strict Rules| J[Judgment]
    J --> |render| OUT[JSON/Markdown]
```
架构体现了**“重逻辑、轻生成”**的特征，试图通过代码规则约束 RAG 的幻觉问题，而非依赖 LLM 自我反思。

## 3. 已有实现的优点（Strengths）
1.  **极致的防御性编程**：
    - 大量使用 Pydantic 的 `Unified Config`（`extra="forbid"`, `frozen=True`），极度强调数据不可变性和类型安全。
    - 验证器（Validators）逻辑严密，例如 `EvidenceUnit` 禁止“Opinion”类型证据作为支撑结论的依据，这是非常有领域深度的设计。
2.  **清晰的领域建模**：
    - 将 RAG 的过程解耦为“证据收集”与“判决仲裁”。这种 Domain-Driven Design (DDD) 风格为构建高可信系统打下了极好的基础。
3.  **确定性优先**：
    - 仲裁逻辑（`test_arbitration.py`）是纯确定性的 Python 代码，不依赖 LLM。这意味着“由谁说了算”这一核心问题被收敛到了可测试的代码逻辑中，而非不可控的模型概率中。

## 4. 已有实现的缺点与风险（Weaknesses & Risks）
1.  **“空壳”应用**：
    - **`retrieval`（检索）模块为空**：没有任何向量数据库、关键词检索或 Embedding 的实现代码。
    - **`services`（服务）模块为空**：API 入口仅有目录结构，没有实际路由和业务逻辑。
    - **无 LLM 交互**：目前代码中**找不到任何 LLM 客户端、Prompt 模板或生成逻辑**。这意味着项目离“能用”还有巨大的距离。
2.  **过度设计的风险**：
    - `DocIR` 等结构定义得非常细致（甚至包含 BBox 校验），但在没有实际解析器（Parser）填充数据的情况下，这些复杂定义可能成为后续集成的负担。
3.  **缺失核心链路**：
    - 只有“裁决者”，没有“搜查员（Retriever）”和“陈述者（Generator）”。当前系统就像一个并没有案件可审的法庭。

## 5. 当前项目所处阶段判断（Project Stage）
**判断：核心领域模型原型（Core Domain Prototype）**

**理由**：
- 它不是 PoC（概念验证），因为代码质量远超随意的 PoC 脚本，具有极高的工程标准。
- 它不是 MVP（最小可行产品），因为它无法独立运行解决用户问题（缺少检索和生成）。
- 它是**工程化初期**的一个特例：**优先实现了最难的业务逻辑内核**。作者显然是想先定义好“什么是可信”，再去填补“如何获取数据”和“如何提供服务”的拼图。这是一个自顶向下、质量优先的构建策略。
