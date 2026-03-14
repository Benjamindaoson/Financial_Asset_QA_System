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
```
model_selected     → 🧠 选择分析模型
tool_start: market_data → 📊 获取实时行情
tool_start: rag_search  → 📚 搜索知识库
tool_start: web_search  → 🔍 网络搜索
tool_start: sec_filings → 📄 查询SEC公告
analysis_chunk     → ✍️ 生成分析报告
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
  zone1: ['key_metrics', 'quote', 'table'],
  zone2: ['analysis', 'bullets', 'chart', 'news', 'warning'],
  zone3: ['source', 'trace']
};
```

**降级处理：**
- Zone 1 无块 → 隐藏
- Zone 2 无块 → 显示 `msg.text` (兼容旧版)
- Zone 3 → 始终显示

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
- 映射到中文描述 + 图标
- 显示状态（完成/进行中）
- 横向或纵向布局（根据空间自适应）

### 3. AnalysisBlock 增强

**Markdown 手风琴解析：**

**方案 A + C 混合：**
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

**文件：** `backend/prompts.yaml` 或相关配置

**修改点：**

在生成分析的系统提示词中添加：

```yaml
analysis_structure: |
  输出分析时，请使用 Markdown 格式组织内容：
  - 使用 ## 标题 划分不同小节
  - 建议的标题：## 近期走势、## 技术面观察、## 风险提示
  - 如果某个小节没有相关信息，可以省略
  - 每个小节内容保持简洁，2-3段为宜
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

**P0 (必须完成):**
1. ThreeZoneLayout 组件 + 映射逻辑
2. QueryTimeline 组件 + 事件映射
3. 后端 Prompt 修改

**P1 (建议完成):**
4. AnalysisBlock Markdown 手风琴
5. Zone 1 额外指标行（7日/30日涨跌幅）

**P2 (可选):**
6. 图表 hover tooltip
7. 快捷问题 chips（已存在，可优化样式）

## 技术约束

- 保持后端块系统的灵活性
- 前端控制布局逻辑
- 向后兼容现有 `msg.text` 响应
- 不引入重型依赖（Markdown 解析用轻量方案）

## 成功标准

1. **视觉层次清晰** - 数据/分析/来源三区明确分离
2. **技术能力可见** - 查询路由时间线直观展示系统架构
3. **用户体验流畅** - 信息易扫描，分析可折叠，不过载
4. **代码可维护** - 组件职责单一，映射逻辑集中

## 不做的事

- ❌ 深色模式
- ❌ 用户登录系统
- ❌ 多轮对话历史
- ❌ 复杂的 K 线蜡烛图
- ❌ 过度动画效果
