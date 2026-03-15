# FinSight AI 前端问题分析与解决方案

基于截图反馈与代码审查，整理如下问题及修复建议。

---

## 问题 1：Pipeline 状态条严重冗余（P0）

### 现象
- 首屏几乎被大量重复的「✓ 生成分析报告」占满
- 每个 LLM 流式 token 都会新增一条 pipeline 步骤
- 核心内容（价格、图表、AI 分析）被推到首屏之外

### 根因
- 后端：`core.py` 第 754 行对每个流式 chunk 都发送 `analysis_chunk` 事件
- 前端：`App.jsx` 第 152–156 行对每个 `analysis_chunk` 都往 trace 中 push 一条记录
- 结果：trace 中会有几十甚至上百条 `analysis_chunk`，全部被展示为「生成分析报告」

### 解决方案

**方案 A（推荐）：前端去重**

在 `App.jsx` 中，对 `analysis_chunk` 只保留一条记录，不重复添加：

```javascript
} else if (event.type === "analysis_chunk") {
  analysisText += event.text || "";
  // 仅首次添加一条「生成分析报告」步骤，不重复
  if (!trace.some(e => e.type === 'analysis_chunk')) {
    const traceEvent = { type: 'analysis_chunk', timestamp: Date.now() };
    trace.push(traceEvent);
    setCurrentTrace([...trace]);
  }
  setStreamingText(fullText + "\n\n" + analysisText);
}
```

**方案 B：后端合并**

后端在流式结束时只发送一次 `analysis_chunk` 或 `analysis_start` / `analysis_done`，前端按「开始 / 结束」展示，而不是按每个 token。

---

## 问题 2：价格走势图缺失（P0）

### 现象
- 任务 3 要求顺序为：价格卡片 → 走势图 → AI 分析
- 截图中价格卡片和 AI 分析可见，但走势图完全缺失

### 可能根因

1. **后端未返回 chart block**
   - chart block 依赖 `get_history` 且 `history.get("data")` 非空（`core.py` 第 519 行）
   - 若 `get_history` 未调用、失败或返回空数据，则不会生成 chart block

2. **前端 Chart 组件隐藏空数据**
   - `Chart.jsx` 第 112–114 行：`if (data.length === 0) return null;`
   - `embeddedSeries` 为空或格式不符时，`formatEmbeddedSeries` 得到空数组，组件不渲染

3. **数据格式不匹配**
   - 前端期望：`{ date, close }`（`Chart.jsx` 第 186 行）
   - 后端返回：`{ date, open, high, low, close, volume }`
   - 理论上兼容，但需确认序列化后的字段名一致

### 解决方案

1. **确认后端是否返回 chart block**
   - 在 Network 中查看 `/api/chat` 的 SSE 流，检查 `done` 事件中的 `blocks` 是否包含 `type: "chart"`
   - 若无，排查 `get_history` 是否被调用、是否返回有效数据

2. **前端增加兜底**
   - 当有 `key_metrics` 且有 `symbol` 和 `rangeKey`，但无 chart block 时，由前端主动渲染 Chart，通过 `fetchChart` 拉取数据
   - 需在 `ThreeZoneLayout` 或 `AiMessage` 中根据 `msg.symbol`、`msg.rangeKey` 补全 chart 渲染逻辑

3. **后端兜底**
   - 在 `_compose_answer` 中，若 `get_change` 或 `get_price` 有数据但 `get_history` 无数据，可尝试用 `days` 再调一次 `get_history`，或返回一个「无历史数据」的占位 block，避免前端完全空白

---

## 问题 3：数据来源显示异常（P1）

### 现象
- 显示「Stoog行情」——应为「Stooq 行情」
- 显示「unavailable」——内部状态直接暴露给用户

### 根因
- `SOURCE_LABEL_MAP` 中为 `stooq`，若后端传 `Stoog` 等拼写变体，则无法匹配
- 未对 `unavailable`、`not_configured` 等内部状态做过滤或映射

### 解决方案

在 `ChatComponents.jsx` 的 `mapSourceName` 中：

1. 对 `stooq` 的变体做兼容：`stooq`、`stoog` 等统一映射为「Stooq 行情」
2. 过滤掉 `unavailable`、`not_configured`、`disconnected` 等内部状态，不展示给用户

```javascript
function mapSourceName(name) {
  if (!name) return null;
  const lower = (name || '').toLowerCase();
  // 过滤内部状态
  if (['unavailable', 'not_configured', 'disconnected', 'error'].includes(lower)) return null;
  if (SOURCE_LABEL_MAP[lower]) return SOURCE_LABEL_MAP[lower];
  // 兼容 Stoog -> Stooq
  if (lower === 'stoog') return 'Stooq 行情';
  if (lower.endsWith('.md')) return '__knowledge__';
  return name;
}
```

并在 `SOURCE_LABEL_MAP` 中补充 `stoog: 'Stooq 行情'`。

---

## 问题 4：布局顺序（已基本符合）

### 现状
- 当前顺序：Pipeline 状态条 → 价格卡片 → AI 分析 → 参考来源
- 任务 3 要求：Pipeline → 价格卡片 → **走势图** → AI 分析 → 参考来源

### 结论
- 布局逻辑已按任务 3 实现
- 走势图缺失是数据/渲染问题，不是布局顺序问题

---

## 修复优先级建议

| 优先级 | 问题 | 影响 | 修复难度 |
|--------|------|------|----------|
| P0 | Pipeline 状态条冗余 | 首屏被占满，核心内容不可见 | 低（前端改几行） |
| P0 | 价格走势图缺失 | 核心功能不完整 | 中（需排查后端 + 前端） |
| P1 | 数据来源显示异常 | 专业感下降 | 低（前端映射 + 过滤） |

---

## 建议执行顺序

1. **立即**：修复 Pipeline 冗余（方案 A）
2. **随后**：修复数据来源显示（过滤 unavailable、兼容 Stoog）
3. **深入**：排查走势图缺失（Network 检查 blocks、确认 get_history 与 Chart 数据格式）
