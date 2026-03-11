import { C, F } from "../../theme";

export function SignalFeed({ signals }) {
  if (!signals || signals.length === 0) {
    return <div style={{ padding: "20px", color: C.td }}>暂无信号。</div>;
  }

  return (
    <div style={{ marginBottom: 32 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: C.text,
          marginBottom: 16,
          fontFamily: F.m,
        }}
      >
        今日信号
      </h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {signals.map((signal, index) => (
          <SignalCard key={`${signal.symbol}-${index}`} signal={signal} />
        ))}
      </div>
    </div>
  );
}

function SignalCard({ signal }) {
  const isPositive = signal.change_pct >= 0;
  const changeColor = isPositive ? "#10B981" : "#EF4444";
  const signalTypeLabel = {
    price_spike: "价格异动",
    volume_spike: "成交量异动",
    news_event: "新闻事件",
    volatility: "高波动",
  };
  const signalStrength = signal.signal_score >= 80 ? "强烈" : signal.signal_score >= 60 ? "中等" : "关注";
  const signalColor = signal.signal_score >= 80 ? "#10B981" : signal.signal_score >= 60 ? "#F59E0B" : "#6B7280";

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "16px 20px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: C.text, fontFamily: F.m }}>{signal.symbol}</span>
          <span style={{ fontSize: 18, fontWeight: 700, color: changeColor, fontFamily: F.m }}>
            {isPositive ? "+" : ""}
            {signal.change_pct?.toFixed(2)}%
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {signal.signal_type && signal.signal_type !== "price_spike" && (
            <span style={{ fontSize: 11, color: C.td, fontFamily: F.m }}>
              {signalTypeLabel[signal.signal_type] || signal.signal_type}
            </span>
          )}
          {signal.volume_ratio && signal.volume_ratio !== 1.0 && (
            <span style={{ fontSize: 11, color: C.td, fontFamily: F.m }}>
              成交量 {signal.volume_ratio.toFixed(1)}x
            </span>
          )}
        </div>
      </div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: signalColor,
          padding: "4px 12px",
          background: `${signalColor}15`,
          borderRadius: 6,
          fontFamily: F.m,
        }}
      >
        {signalStrength}
      </div>
    </div>
  );
}
