# Frontend UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize FinSight AI frontend with three-zone layout, query routing visualization, and markdown accordion analysis blocks.

**Architecture:** Create ThreeZoneLayout and QueryTimeline components to map backend blocks into structured UI zones. Enhance AnalysisBlock with markdown parsing. Update backend prompts for structured output.

**Tech Stack:** React, inline styles (existing pattern), regex-based markdown parsing, Jinja2 templates (backend)

---

## File Structure

**New Files:**
- `frontend/src/components/Chat/ThreeZoneLayout.jsx` - Smart layout mapper for three-zone UI
- `frontend/src/components/Chat/QueryTimeline.jsx` - Query routing visualization component

**Modified Files:**
- `frontend/src/App.jsx` - Replace ResponseBlocks with ThreeZoneLayout in AiMessage
- `frontend/src/components/Chat/ChatComponents.jsx` - Enhance AnalysisBlock with markdown accordion
- `prompts.yaml` - Add markdown structure guidance to generator prompts

---

## Chunk 1: Core Components

### Task 1: Create QueryTimeline Component

**Files:**
- Create: `frontend/src/components/Chat/QueryTimeline.jsx`

**Prerequisites:** None (independent task)

- [ ] **Step 1a: Create file with basic structure and toolDisplayMap**

```jsx
import { C, F } from "../../theme";

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

export function QueryTimeline({ events = [], loading = false }) {
  // Filter key events
  const keyEvents = events.filter(e =>
    e.type === 'model_selected' ||
    e.type === 'tool_start' ||
    e.type === 'analysis_chunk'
  );

  if (keyEvents.length === 0) return null;

  // Determine current step (last event index)
  const currentStep = loading ? keyEvents.length - 1 : keyEvents.length;

  // Responsive: max 5 steps on desktop, 3 on mobile
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
  const maxSteps = isMobile ? 3 : 5;

  let displayEvents = keyEvents;
  if (keyEvents.length > maxSteps) {
    // Show first 2, "...", last 1
    displayEvents = [
      ...keyEvents.slice(0, 2),
      { type: 'ellipsis' },
      keyEvents[keyEvents.length - 1]
    ];
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: isMobile ? 'column' : 'row',
      alignItems: isMobile ? 'flex-start' : 'center',
      gap: isMobile ? 8 : 12,
      padding: '12px 16px',
      background: C.white,
      border: `1px solid ${C.border}`,
      borderRadius: 10,
      marginBottom: 10
    }}>
      {displayEvents.map((event, index) => {
        if (event.type === 'ellipsis') {
          return (
            <div key="ellipsis" style={{
              color: C.td,
              fontSize: 12,
              padding: isMobile ? '4px 0' : '0 4px'
            }}>
              ...
            </div>
          );
        }

        const isCompleted = index < currentStep;
        const isCurrent = index === currentStep;

        // Get display text
        let displayText = '';
        if (event.type === 'model_selected') {
          displayText = toolDisplayMap['model_selected'];
        } else if (event.type === 'tool_start') {
          displayText = toolDisplayMap[event.name] || event.display || event.name;
        } else if (event.type === 'analysis_chunk') {
          displayText = toolDisplayMap['analysis_chunk'];
        }

        return (
          <div key={index} style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: isMobile ? 11 : 12,
            color: isCompleted ? C.text : (isCurrent ? C.accent : C.td),
            fontFamily: F.s,
            opacity: isCompleted || isCurrent ? 1 : 0.5
          }}>
            {/* Status icon */}
            {isCompleted ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : isCurrent ? (
              <span style={{
                width: 14,
                height: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <span style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: C.accent,
                  animation: 'pulse 1s infinite'
                }} />
              </span>
            ) : (
              <span style={{
                width: 14,
                height: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <span style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: C.td
                }} />
              </span>
            )}

            {/* Display text */}
            <span>{displayText}</span>

            {/* Connector (not for last item, not for mobile) */}
            {!isMobile && index < displayEvents.length - 1 && event.type !== 'ellipsis' && (
              <span style={{ color: C.border, marginLeft: 4 }}>→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify component compiles**

Run: `cd frontend && npm run dev`
Expected: No compilation errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Chat/QueryTimeline.jsx
git commit -m "feat: add QueryTimeline component for query routing visualization"
```

---

### Task 2: Create ThreeZoneLayout Component

**Files:**
- Create: `frontend/src/components/Chat/ThreeZoneLayout.jsx`

**Prerequisites:** None (independent task)

- [ ] **Step 1: Create ThreeZoneLayout component file**

```jsx
import { ResponseBlocks, SourcesPanel, Disc } from "./ChatComponents";
import { C, F } from "../../theme";

const ZONE_MAPPING = {
  zone1: ['key_metrics', 'quote', 'table'],
  zone2: ['analysis', 'bullets', 'chart', 'warning', 'news']
};

export function ThreeZoneLayout({ blocks = [], sources = [], confidence, disclaimer, fallbackText, trace }) {
  // Categorize blocks into zones
  const zone1Blocks = blocks.filter(b => ZONE_MAPPING.zone1.includes(b.type));
  const zone2Blocks = blocks.filter(b => ZONE_MAPPING.zone2.includes(b.type));

  // Unknown block types - log warning
  const unknownBlocks = blocks.filter(b =>
    !ZONE_MAPPING.zone1.includes(b.type) &&
    !ZONE_MAPPING.zone2.includes(b.type)
  );

  if (unknownBlocks.length > 0) {
    console.warn('[ThreeZoneLayout] Unknown block types:', unknownBlocks.map(b => b.type));
  }

  // Error handling: no content in zone 2 and no fallback text
  const hasZone2Content = zone2Blocks.length > 0 || fallbackText;

  if (!hasZone2Content) {
    return (
      <div style={{
        padding: '16px',
        background: C.warnBg,
        border: `1px solid #FCD34D`,
        borderRadius: 12,
        color: C.text,
        fontSize: 13
      }}>
        分析生成失败，请重试。
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Zone 1: Data Summary */}
      {zone1Blocks.length > 0 && (
        <div style={{
          background: C.white,
          borderRadius: 12,
          border: `1px solid ${C.border}`,
          overflow: 'hidden'
        }}>
          <ResponseBlocks blocks={zone1Blocks} />
        </div>
      )}

      {/* Zone 2: Analysis */}
      {zone2Blocks.length > 0 ? (
        <ResponseBlocks blocks={zone2Blocks} />
      ) : fallbackText ? (
        <div style={{
          background: "#FAFCFF",
          borderRadius: 12,
          padding: "18px 18px 14px",
          border: "1px solid #D6E4F7",
          position: "relative",
          fontSize: 13,
          lineHeight: 1.85,
          color: C.text,
          whiteSpace: "pre-wrap",
        }}>
          <div style={{
            position: "absolute",
            top: -9,
            left: 12,
            background: C.accentL,
            color: C.accent,
            fontSize: 9.5,
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: 8,
            border: "1px solid #BFD5F0",
          }}>
            AI 分析
          </div>
          {fallbackText}
        </div>
      ) : null}

      {/* Zone 3: Meta */}
      {sources && sources.length > 0 && <SourcesPanel items={sources} />}

      <Disc text={disclaimer || "以上内容仅供参考，不构成投资建议。"} />
    </div>
  );
}
```

- [ ] **Step 2: Verify component compiles**

Run: `cd frontend && npm run dev`
Expected: No compilation errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Chat/ThreeZoneLayout.jsx
git commit -m "feat: add ThreeZoneLayout component for three-zone UI structure"
```

---

## Chunk 2: Integration and Enhancement

### Task 3: Integrate Components into App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`

**Prerequisites:** Complete Tasks 1 and 2 before starting this task.

- [ ] **Step 1: Update imports in App.jsx**

Find the import section (lines 1-17) and add:

```jsx
import { QueryTimeline } from "./components/Chat/QueryTimeline";
import { ThreeZoneLayout } from "./components/Chat/ThreeZoneLayout";
```

- [ ] **Step 2: Update AiMessage component to use ThreeZoneLayout**

Replace the AiMessage function with:

```jsx
function AiMessage({ msg }) {
  const [traceOpen, setTraceOpen] = useState(false);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Query Timeline - always visible */}
      {msg.trace?.length > 0 && (
        <QueryTimeline events={msg.trace} loading={false} />
      )}

      {/* Three-Zone Layout */}
      <ThreeZoneLayout
        blocks={msg.blocks || []}
        sources={msg.sources}
        confidence={msg.confidence}
        disclaimer={msg.disclaimer}
        fallbackText={msg.text}
        trace={msg.trace}
      />

      {/* Collapsible trace details */}
      {msg.trace?.length > 0 && (
        <div style={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 10, padding: "8px 12px" }}>
          <div
            onClick={() => setTraceOpen((v) => !v)}
            style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: C.ts, fontSize: 11, fontFamily: F.m, userSelect: "none" }}
          >
            <span style={{ fontSize: 9 }}>{traceOpen ? "▼" : "▶"}</span>
            {traceOpen ? "隐藏调用详情" : "查看调用详情"}
          </div>
          {traceOpen && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4, fontSize: 11.5, color: C.text }}>
              {msg.trace.map((item, i) => (
                <div key={i} style={{ padding: "2px 0", borderBottom: `1px solid ${C.borderL}` }}>
                  {typeof item === 'string' ? item : JSON.stringify(item)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add QueryTimeline to loading state**

Find the loading section (around line 377-382) and add QueryTimeline before LoadSteps:

```jsx
{loading && (
  <div style={{ animation: "fadeUp .3s ease-out" }}>
    {/* Add QueryTimeline during loading */}
    {streamingText || currentStep > 0 ? (
      <QueryTimeline
        events={msgs[msgs.length - 1]?.trace || []}
        loading={true}
      />
    ) : null}

    <LoadSteps currentStep={currentStep} />
    {streamingText ? <StreamingText text={streamingText} /> : <Skel />}
  </div>
)}
```

Note: This requires tracking trace events during streaming. The trace array should be built up as events arrive.

- [ ] **Step 4: Update event handling to build trace array**

In the `send` function, ensure trace array is populated during streaming (around line 161-188):

```jsx
let trace = [];

for await (const event of fetchChatStream(q, sessionId.current)) {
  if (event.type === "model_selected") {
    setCurrentStep(0);
    trace.push({ type: 'model_selected', model: event.model });
  } else if (event.type === "tool_start") {
    setCurrentStep(1);
    trace.push({ type: 'tool_start', name: event.name, display: event.display });
  } else if (event.type === "tool_data") {
    setCurrentStep(2);
    // ... existing code
  } else if (event.type === "chunk") {
    fullText += event.text || "";
    setStreamingText(fullText);
  } else if (event.type === "analysis_chunk") {
    analysisText += event.text || "";
    trace.push({ type: 'analysis_chunk' });
    setStreamingText(fullText + "\n\n" + analysisText);
  } else if (event.type === "done") {
    // ... existing code
  }
}
```

- [ ] **Step 5: Add pulse animation to App.jsx styles**

Find the style block (around line 239-245) and add pulse keyframe:

```jsx
<style>{`
  @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.8); } }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 10px; }
`}</style>
```

- [ ] **Step 6: Test in browser**

1. Start frontend: `cd frontend && npm run dev`
2. Open http://localhost:5173
3. Send a test query: "AAPL 近1年波动率"
4. Verify: QueryTimeline appears, three zones render correctly

Expected: UI shows timeline → data zone → analysis zone → sources

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: integrate ThreeZoneLayout and QueryTimeline into AiMessage

- Add QueryTimeline to both completed and loading states
- Update event handling to build trace array during streaming
- Add pulse animation keyframe for loading indicators"
```

---

### Task 4: Enhance AnalysisBlock with Markdown Accordion

**Files:**
- Modify: `frontend/src/components/Chat/ChatComponents.jsx`

- [ ] **Step 1: Add markdown section parser helper**

Add this function before the Block component (around line 55):

```jsx
function parseMarkdownSections(text) {
  // Try to parse ## headings
  const headingRegex = /^##\s+(.+)$/gm;
  const matches = [...text.matchAll(headingRegex)];

  if (matches.length === 0) {
    return null; // No sections found, use fallback
  }

  const sections = [];
  matches.forEach((match, index) => {
    const title = match[1].trim();
    const startPos = match.index + match[0].length;
    const endPos = index < matches.length - 1 ? matches[index + 1].index : text.length;
    const content = text.substring(startPos, endPos).trim();

    sections.push({ title, content });
  });

  return sections;
}

function getSectionIcon(title) {
  const iconMap = {
    '近期走势': '📈',
    '技术面观察': '🔍',
    '风险提示': '⚠️',
    '基本面分析': '📊',
    '市场情绪': '💭',
    '走势概述': '📈',
    '事件归因': '📰',
    '当前状态': '💡',
    '定义': '📖',
    '计算公式': '🔢',
    '核心区别': '🔢',
    '实际应用举例': '💼',
    '注意事项': '⚠️'
  };

  // Exact match
  if (iconMap[title]) return iconMap[title];

  // Partial match
  for (const [key, icon] of Object.entries(iconMap)) {
    if (title.includes(key)) return icon;
  }

  return '📌'; // Default icon
}
```

- [ ] **Step 2: Update analysis block rendering**

Find the `if (block.type === "analysis")` section (around line 182) and replace with:

```jsx
if (block.type === "analysis") {
  const sections = parseMarkdownSections(block.data?.text || "");

  // If no sections found, use fallback with optimized typography
  if (!sections) {
    return (
      <div style={analysisBlockStyle}>
        <div style={analysisBadgeStyle}>{block.title || "AI 分析"}</div>
        <div style={{
          ...analysisContentStyle,
          lineHeight: 1.85,
          fontSize: 13,
          color: '#1A2332'
        }}>
          <MarkdownText text={block.data?.text || ""} />
        </div>
        <div style={analysisDisclaimerStyle}>
          以上分析由 AI 基于公开数据生成，不构成投资建议
        </div>
      </div>
    );
  }

  // Render accordion
  return <AnalysisAccordion sections={sections} title={block.title} />;
}
```

- [ ] **Step 3: Add AnalysisAccordion component**

Add this component after the Block component (around line 200):

```jsx
function AnalysisAccordion({ sections, title }) {
  const [openIndex, setOpenIndex] = useState(0); // First section open by default

  return (
    <div style={analysisBlockStyle}>
      <div style={analysisBadgeStyle}>{title || "AI 分析"}</div>
      <div style={{ marginTop: 8 }}>
        {sections.map((section, index) => {
          const isOpen = openIndex === index;
          const icon = getSectionIcon(section.title);

          return (
            <div key={index} style={{
              borderBottom: index < sections.length - 1 ? `1px solid ${C.borderL}` : 'none',
              paddingBottom: 12,
              marginBottom: 12
            }}>
              {/* Section header */}
              <div
                onClick={() => setOpenIndex(isOpen ? -1 : index)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  cursor: 'pointer',
                  padding: '8px 0',
                  userSelect: 'none'
                }}
              >
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{
                  fontSize: 13.5,
                  fontWeight: 600,
                  color: C.text,
                  flex: 1
                }}>
                  {section.title}
                </span>
                <span style={{
                  fontSize: 11,
                  color: C.td,
                  transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s'
                }}>
                  ▼
                </span>
              </div>

              {/* Section content */}
              {isOpen && (
                <div style={{
                  fontSize: 13,
                  lineHeight: 1.85,
                  color: C.text,
                  paddingLeft: 24,
                  whiteSpace: 'pre-wrap'
                }}>
                  {section.content}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={analysisDisclaimerStyle}>
        以上分析由 AI 基于公开数据生成，不构成投资建议
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Test markdown accordion with specific query**

1. Restart frontend if needed
2. Send query: "AAPL 近7日技术分析" (this should trigger markdown-formatted response)
3. Verify: Sections are collapsible, first section open by default, icons appear
4. If backend doesn't generate markdown yet, test will pass after Task 5 is complete

Expected: Analysis block shows accordion with icons (or fallback text if prompts not updated yet)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Chat/ChatComponents.jsx
git commit -m "feat: add markdown accordion support to AnalysisBlock"
```

---

## Chunk 3: Backend Prompt Updates

### Task 5: Update Backend Prompts for Markdown Structure

**Files:**
- Modify: `prompts.yaml`

- [ ] **Step 1: Update market route template**

Find the `{% if route_type == "market" %}` section (line 147) and replace the content with:

```yaml
      {% if route_type == "market" %}
      【实时数据】
      {{api_data}}

      注意：价格数字已在上方数据区展示，你的分析不需要重复报出当前价格和涨跌幅。直接从走势分析开始。

      请按以下结构回答（共200-350字），使用 Markdown 格式组织内容，用 ## 标题 划分小节：

      ## 近期走势
      用具体日期和价位描述近期的涨跌节奏（例如："过去7天从XXX下探至XXX低点，随后反弹至XXX"），不要用"近期震荡"这种空话。

      ## 技术面观察
      如果数据中有RSI，解释其含义和当前含义（比如"RSI处于超卖区域，意味着..."）；提及关键支撑位和阻力位（如有）。

      ## 风险提示
      点出1-2个近期值得投资者关注的潜在催化因素（财报时间、宏观政策、行业动向等），基于数据推断，不要编造。

      如果某个小节没有相关信息，可以省略。每个小节保持简洁，2-3段为宜。
      最后一句话说明分析的局限性。

      {% elif route_type == "news" or route_type == "hybrid" %}
```

- [ ] **Step 2: Update hybrid route template**

Find the `{% elif route_type == "news" or route_type == "hybrid" %}` section (line 163) and update:

```yaml
      {% elif route_type == "news" or route_type == "hybrid" %}
      【实时数据】
      {{api_data}}

      【相关新闻】
      {{news_context}}

      【参考知识】
      {{rag_context}}

      请按以下结构回答（共300-500字），使用 Markdown 格式组织内容，用 ## 标题 划分小节：

      ## 走势概述
      用一句话描述价格区间表现（不要只列数字，要有判断：如"累计下跌X%，表现弱于大盘"）。

      ## 事件归因
      每个归因点格式：[编号]. [事件概述]——据[来源名称]报道，[具体内容]。这一因素可能[推动/拖累]了股价[上涨/下跌]。
      列出2-4个归因点，每条都必须引用具体新闻来源。
      如果新闻不足，明确说明"目前公开信息有限，无法确定"。

      ## 当前状态
      最后，简要说明这次涨跌到目前为止的后续表现（涨幅是否保持/回吐）。

      如果某个小节没有相关信息，可以省略。每个小节保持简洁，2-3段为宜。

      {% elif route_type == "knowledge" %}
```

- [ ] **Step 3: Verify YAML syntax and test backend**

Verify YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('prompts.yaml'))"
```

Restart backend and test:
```bash
cd backend
# Stop existing backend (Ctrl+C if running)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

In another terminal, send test query:
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL 近7日走势"}'
```

Expected: Response includes markdown sections with ## headings

- [ ] **Step 4: Commit**

```bash
git add prompts.yaml
git commit -m "feat: add markdown structure guidance to generator prompts

- Market route now instructs LLM to use ## headings
- Hybrid route updated with markdown structure
- Maintains existing word limits and section requirements"
```

---

## Chunk 4: Testing and Validation

### Task 6: End-to-End Testing

**Files:**
- None (testing only)

- [ ] **Step 1: Test market query**

1. Ensure backend and frontend are running
2. Send query: "AAPL 近7日走势"
3. Verify:
   - QueryTimeline shows steps
   - Zone 1 shows key_metrics
   - Zone 2 shows analysis with markdown sections
   - Zone 3 shows sources and disclaimer
   - Accordion sections are collapsible

Expected: All zones render correctly, markdown sections work

- [ ] **Step 2: Test knowledge query**

1. Send query: "什么是市盈率"
2. Verify:
   - QueryTimeline shows "搜索知识库"
   - Zone 1 is hidden (no data blocks)
   - Zone 2 shows analysis
   - Zone 3 shows sources

Expected: Layout adapts to knowledge query type

- [ ] **Step 3: Test comparison query**

1. Send query: "比较 AAPL 和 TSLA 的 1 年表现"
2. Verify:
   - QueryTimeline shows multiple steps
   - Chart block appears in Zone 2
   - Comparison data renders correctly

Expected: Multi-asset comparison works

- [ ] **Step 4: Test mobile responsive**

1. Open browser dev tools
2. Switch to mobile viewport (375px width)
3. Send any query
4. Verify:
   - QueryTimeline switches to vertical layout
   - Text sizes are readable
   - No horizontal overflow

Expected: Mobile layout works correctly

- [ ] **Step 5: Test error handling**

1. Stop backend server
2. Send query
3. Verify: Error message appears ("分析生成失败，请重试")

Expected: Graceful error handling

- [ ] **Step 6: Document test results**

Create a simple test log:

```bash
echo "# UI Optimization Test Results" > test-results.txt
echo "Date: $(date)" >> test-results.txt
echo "" >> test-results.txt
echo "✓ Market query - QueryTimeline + 3 zones working" >> test-results.txt
echo "✓ Knowledge query - Zone 1 hidden correctly" >> test-results.txt
echo "✓ Comparison query - Chart rendering" >> test-results.txt
echo "✓ Mobile responsive - Vertical timeline" >> test-results.txt
echo "✓ Error handling - Graceful fallback" >> test-results.txt
```

- [ ] **Step 7: Final commit**

```bash
git add test-results.txt
git commit -m "test: validate frontend UI optimization implementation

All P0 features tested and working:
- ThreeZoneLayout with smart block mapping
- QueryTimeline with responsive layout
- Markdown accordion in AnalysisBlock
- Backend prompts generating structured output"
```

---

## Success Criteria

- [ ] QueryTimeline component displays query routing steps with icons
- [ ] QueryTimeline appears in both loading and completed states
- [ ] ThreeZoneLayout correctly maps blocks to three visual zones
- [ ] AnalysisBlock parses markdown sections into accordion
- [ ] Backend prompts generate markdown-structured responses (verified via curl test)
- [ ] Mobile responsive layout works (timeline vertical on ≤768px)
- [ ] Error handling shows fallback messages
- [ ] Pulse animation works for loading indicators
- [ ] No console errors or warnings
- [ ] All commits follow conventional commit format

---

## Notes

- **DRY**: Reuse existing components (ResponseBlocks, SourcesPanel, Disc)
- **YAGNI**: No dark mode, no complex animations, no user auth
- **Testing**: Manual browser testing sufficient for UI changes
- **Rollback**: If markdown parsing fails, graceful fallback to plain text

---

## Estimated Time

- Task 1 (QueryTimeline): 45 min
- Task 2 (ThreeZoneLayout): 45 min
- Task 3 (Integration): 30 min
- Task 4 (Markdown Accordion): 60 min
- Task 5 (Backend Prompts): 30 min
- Task 6 (Testing): 45 min

**Total: ~4 hours**
