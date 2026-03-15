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

function formatLatency(ms) {
  if (ms == null || ms < 0) return '';
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export function QueryTimeline({ events = [], tool_latencies = [], loading = false }) {
  const latencyMap = Object.fromEntries(
    (tool_latencies || []).map(t => [t.tool, t.latency_ms])
  );

  // Filter key events
  const keyEvents = events.filter(e =>
    e.type === 'model_selected' ||
    e.type === 'tool_start' ||
    e.type === 'analysis_chunk'
  );

  if (keyEvents.length === 0) return null;

  // Determine current step (last event index)
  const currentStep = loading ? keyEvents.length - 1 : keyEvents.length;

  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;

  // Show all events, no truncation
  const displayEvents = keyEvents;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'row',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: isMobile ? 6 : 10,
      padding: '10px 16px',
      background: C.white,
      border: `1px solid ${C.border}`,
      borderRadius: 10,
      marginBottom: 10
    }}>
      {displayEvents.map((event, index) => {
        const isCompleted = index < currentStep;
        const isCurrent = index === currentStep;

        // Get display text
        let displayText = '';
        let latencyMs = null;
        if (event.type === 'model_selected') {
          displayText = toolDisplayMap['model_selected'];
        } else if (event.type === 'tool_start') {
          displayText = toolDisplayMap[event.name] || event.display || event.name;
          latencyMs = latencyMap[event.name];
        } else if (event.type === 'analysis_chunk') {
          displayText = toolDisplayMap['analysis_chunk'];
          latencyMs = latencyMap['analysis_chunk'] ?? latencyMap['llm'];
        }

        const latencyStr = formatLatency(latencyMs);

        return (
          <div key={index} style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: isMobile ? 11 : 11.5,
            color: isCompleted ? C.text : (isCurrent ? C.accent : C.td),
            fontFamily: F.s,
            opacity: isCompleted || isCurrent ? 1 : 0.5
          }}>
            {/* Status icon */}
            {isCompleted ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : isCurrent ? (
              <span style={{ width: 13, height: 13, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.accent, animation: 'pulse 1s infinite' }} />
              </span>
            ) : (
              <span style={{ width: 13, height: 13, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: C.td }} />
              </span>
            )}

            <span>{displayText}{latencyStr && <span style={{ color: C.td, marginLeft: 4, fontSize: '0.9em' }}>{latencyStr}</span>}</span>

            {/* Connector arrow - not for last item */}
            {index < displayEvents.length - 1 && (
              <span style={{ color: C.border, marginLeft: 2, fontSize: 10 }}>→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
