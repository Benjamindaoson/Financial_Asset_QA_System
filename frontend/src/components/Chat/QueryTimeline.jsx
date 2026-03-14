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
