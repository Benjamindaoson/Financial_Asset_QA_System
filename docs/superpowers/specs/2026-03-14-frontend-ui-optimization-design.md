# Frontend UI Optimization Design

**Date:** 2026-03-14
**Status:** Approved
**Priority:** P0 (CTO Demo)

## 目标

优化 FinSight AI 前端界面，实现：
1. 信息层次重构 - 区分客观数据与分析性描述
2. 查询路由可视化 - 展示系统架构和技术能力
3. 提升产品成熟度和用户体验

## 核心架构

### 三区布局系统

```
backend blocks → <ThreeZoneLayout> → 三区 UI
```

**Zone 1: 数据摘要区 (Data Summary)**
- 目的：展示客观的金融数据
- 包含块类型：`key_metrics`, `quote`, `table` (金融数据)
- 视觉：白色背景，大字体，色块标识涨跌

**Zone 2: AI 分析区 (Analysis)**
- 目的：展示 AI 生成的洞察和解释
- 包含块类型：`analysis`, `bullets`, `chart`, `news`, `warning`
- 视觉：浅蓝背景，舒适阅读字号，支持 Markdown 手风琴

**Zone 3: 元信息区 (Meta)**
- 目的：数据来源、免责声明、调用详情
- 包含：`sources`, `disclaimer`, `trace` (可折叠)
- 视觉：灰色小字，弱化处理

### 查询路由可视化

**组件：`<QueryTimeline>`**

**显示方式：** 始终可见的精简版（3-4个关键步骤）

**事件映射：**

后端实际工具名称到前端显示的映射：

```javascript
const toolDisplayMap = {
  // Market data tools
  'get_price': '📊 获取实时价格',
  'get_history': '📊 获取历史数据',
  'get_change': '📊 计算涨跌幅',
  'get_info': '📊 获取公司信息',
  'get_metrics': '📊 计算风险指标',
  'compare_assets': '📊 对比资产表现',

  // Search tools
  'search_knowledge': '📚 搜索知识库',
  'search_web': '🔍 网络搜索',
  'search_sec': '📄 查询SEC公告',

  // Special events
  'model_selected': '🧠 选择分析模型',
  'analysis_chunk': '✍️ 生成分析报告'
};
```

**状态显示：**
- 完成：绿色勾号 ✓
- 进行中：蓝色加载动画 ⏳
- 未开始：灰色圆点 ○

## 组件设计

### 1. ThreeZoneLayout 组件

**职责：** 智能布局映射器

**输入：**
```javascript
<ThreeZoneLayout
  blocks={msg.blocks}
  sources={msg.sources}
  confidence={msg.confidence}
  disclaimer={msg.disclaimer}
/>
```

**映射逻辑：**
```javascript
const zoneMapping = {
  zone1: ['key_metrics', 'quote', 'table'],  // 数据块
  zone2: ['analysis', 'bullets', 'chart', 'warning'],  // 分析块
  // Zone 3 使用 msg.sources 和 msg.trace 数组，不是 blocks
};
```

**注意：** Zone 3 的内容来自消息对象的 `sources` 和 `trace` 属性，不是 blocks 数组中的块类型。

**降级处理：**
- Zone 1 无块 → 隐藏
- Zone 2 无块 → 显示 `msg.text` (兼容旧版)
- Zone 3 → 始终显示

**错误处理：**
- 无效的块类型 → 记录警告，跳过该块
- `msg.text` 为空且 Zone 2 为空 → 显示 "分析生成失败，请重试"
- 块渲染错误 → 优雅降级到纯文本显示

### 2. QueryTimeline 组件

**职责：** 可视化查询处理流程

**输入：**
```javascript
<QueryTimeline
  events={[
    { type: 'model_selected', model: 'deepseek-chat', timestamp: 1234 },
    { type: 'tool_start', name: 'market_data', display: '获取实时行情' },
    { type: 'tool_data', data: {...} },
    { type: 'chunk', text: '...' }
  ]}
/>
```

**渲染逻辑：**
- 过滤关键事件（model_selected, tool_start, analysis_chunk）
- 映射到中文描述 + 图标（使用 toolDisplayMap）
- 显示状态（完成/进行中）
- 位置：AI 消息上方，blocks 之前
- 始终可见（不可折叠，保证透明度）

**响应式布局规则：**
- **桌面端 (>768px)**: 横向布局，最多显示 5 个步骤
  - 如果步骤 > 5：显示前 2 个 + "..." + 最后 1 个
  - 使用 flex-direction: row，步骤间用箭头连接
- **移动端 (≤768px)**: 纵向布局，最多显示 3 个步骤
  - 如果步骤 > 3：显示前 2 个 + "..." + 最后 1 个
  - 使用 flex-direction: column，步骤间用竖线连接
  - 减小图标和文字大小以适应窄屏

### 3. AnalysisBlock 增强

**Markdown 手风琴解析：**

**方案选择背景：**
- **方案 A**: 基于 Markdown 标题自动分段（轻量级正则解析）
- **方案 B**: 固定的分析结构（硬编码关键词识别）
- **方案 C**: 暂不实现手风琴（仅优化排版）

**选择：方案 A + C 混合**
- 优先尝试解析 `## 标题` 格式生成手风琴
- 如果解析失败或无标题，降级到优化排版的完整文本显示
- 理由：LLM 天然擅长输出 Markdown，后端只需 Prompt 引导，前端实现简单且灵活

**实现逻辑：**
1. 检测 `## 标题` 格式
2. 如果存在 → 生成手风琴，默认展开第一个
3. 如果不存在 → 显示完整文本 + 优化排版

**标题图标映射：**
```javascript
const iconMap = {
  '近期走势': '📈',
  '技术面观察': '🔍',
  '风险提示': '⚠️',
  '基本面分析': '📊',
  '市场情绪': '💭'
};
```

**降级排版优化：**
- 行高：1.85
- 段落间距：12px
- 字体大小：13px
- 颜色：#1A2332

## 后端 Prompt 优化

**文件：** `backend/prompts.yaml`

**修改策略：**
1. 保持现有 `system_prompt` 不变
2. 在 `user_template` 中，针对 `route_type == "market"` 和 `route_type == "hybrid"` 添加 Markdown 结构引导
3. 保留现有的字数限制和小节要求
4. 新增指令：使用 `## 标题` 格式划分小节

**具体修改：**

在 `generator.user_template` 的市场分析部分添加：

```yaml
generator:
  user_template: |
    {% if route_type == "market" %}
    请按以下结构回答（共200-350字）：

    使用 Markdown 格式组织内容，用 ## 标题 划分小节：
    - ## 近期走势：价格变化、关键价位
    - ## 技术面观察：技术指标、支撑阻力
    - ## 风险提示：需要关注的因素

    如果某个小节没有相关信息，可以省略。每个小节保持简洁，2-3段为宜。
    {% endif %}
```

**预期效果：**
```markdown
## 近期走势
AAPL 在过去7天上涨3.7%，突破了前期阻力位...

## 技术面观察
从技术指标来看，RSI 处于65，显示轻度超买...

## 风险提示
需要关注美联储利率决议和财报季的影响...
```

## 实现优先级

**P0 (必须完成 - CTO 演示核心):**
1. ThreeZoneLayout 组件 + 映射逻辑 - 直接展示信息层次重构
2. QueryTimeline 组件 + 事件映射 - 可视化系统架构能力
3. 后端 Prompt 修改 - 支持结构化输出

**P1 (建议完成 - 提升体验):**
4. AnalysisBlock Markdown 手风琴 - 改善长文本可读性
5. Zone 1 额外指标行（7日/30日涨跌幅）- 增强数据密度

**P2 (可选 - 锦上添花):**
6. 图表 hover tooltip - 交互细节优化
7. 快捷问题 chips 样式优化（已存在基础功能）

**优先级理由：**
- **P0**: 直接命中"信息层次重构"和"查询路由可视化"两大核心目标，是 CTO 演示的差异化亮点
- **P1**: 提升用户体验和专业度，但不影响核心功能演示
- **P2**: 细节打磨，时间允许的情况下完成

## 技术约束

- 保持后端块系统的灵活性
- 前端控制布局逻辑
- 向后兼容现有 `msg.text` 响应
- 不引入重型依赖（Markdown 解析用轻量方案）

## 文件结构

新增组件位置：
- `frontend/src/components/Chat/ThreeZoneLayout.jsx` - 三区布局组件
- `frontend/src/components/Chat/QueryTimeline.jsx` - 查询时间线组件
- `frontend/src/components/Chat/ChatComponents.jsx` - 增强 AnalysisBlock（已存在）

后端修改：
- `backend/prompts.yaml` - 添加 Markdown 结构化输出指令

## UX 增强设计

### 1. 首屏空状态设计

**目的：** 提升 Demo 第一印象，引导用户快速上手

**设计：**
- 显示欢迎信息："👋 你好，我是 FinSight AI"
- 副标题："实时行情分析 · 知识检索 · SEC 公告查询"
- 快捷问题 Chips（已存在，保持）：
  - "AAPL 近1年波动率和最大回撤"
  - "比较 AAPL 和 TSLA 的 1 年表现"
  - "什么是市盈率"
  - "苹果最近财报和 SEC 公告"
- 市场概览卡片（已存在，保持）

**视觉：**
- 居中布局，渐入动画
- 使用品牌色和图标增强专业感
- 清晰的视觉层次：欢迎 → 功能说明 → 快捷入口

### 2. 加载状态设计

**目的：** LLM 生成过程中提供视觉反馈，避免"卡住"感

**现有组件：** `LoadSteps` 和 `Skel` 已存在，需要增强

**增强方案：**

**阶段 1 - 查询处理中（0-2秒）：**
- 显示 `<LoadSteps>` 组件（已存在）
- 三个步骤：识别问题类型 → 获取市场数据 → 生成分析报告
- 当前步骤高亮 + 脉冲动画

**阶段 2 - 数据获取中（2-4秒）：**
- 显示 `<QueryTimeline>` 的进行中状态
- 已完成的步骤显示绿色勾号
- 当前步骤显示蓝色加载动画 ⏳

**阶段 3 - LLM 生成中（4秒+）：**
- 显示 `<StreamingText>` 组件（已存在）
- 流式输出文字 + 光标闪烁动画
- 如果流式输出未开始，显示 `<Skel>` 骨架屏

**关键改进：**
- 确保每个阶段都有明确的视觉反馈
- 使用现有组件，只需调整显示时机和过渡
- 避免长时间空白等待

## 成功标准

1. **视觉层次清晰** - 数据/分析/来源三区明确分离
2. **技术能力可见** - 查询路由时间线直观展示系统架构
3. **用户体验流畅** - 信息易扫描，分析可折叠，不过载，加载状态清晰
4. **代码可维护** - 组件职责单一，映射逻辑集中
5. **响应式友好** - 移动端和桌面端都有良好体验
6. **首屏吸引力** - 空状态设计专业，引导明确

## 不做的事

- ❌ 深色模式
- ❌ 用户登录系统
- ❌ 多轮对话历史
- ❌ 复杂的 K 线蜡烛图
- ❌ 过度动画效果
