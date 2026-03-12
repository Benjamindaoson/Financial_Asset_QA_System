import { C, F } from "../../theme";

/**
 * 技术指标可视化组件
 */
export function TechnicalIndicators({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return null;
  }

  const { rsi, trend, ma5, ma20, support, resistance, volume } = data;

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>技术指标</div>

      <div style={gridStyle}>
        {/* RSI 指标 */}
        {rsi !== null && rsi !== undefined && (
          <div style={cardStyle}>
            <div style={labelStyle}>RSI (相对强弱指标)</div>
            <div style={valueContainerStyle}>
              <span style={{ fontSize: 20, fontWeight: 700, color: getRSIColor(rsi) }}>
                {rsi.toFixed(1)}
              </span>
              <span style={signalStyle(getRSISignal(rsi))}>
                {getRSISignal(rsi)}
              </span>
            </div>
            <RSIBar value={rsi} />
          </div>
        )}

        {/* 趋势指标 */}
        {trend && (
          <div style={cardStyle}>
            <div style={labelStyle}>趋势</div>
            <div style={valueContainerStyle}>
              <span style={{ fontSize: 18, fontWeight: 700, color: getTrendColor(trend) }}>
                {getTrendLabel(trend)}
              </span>
              <span style={{ fontSize: 24, marginLeft: 8 }}>
                {getTrendEmoji(trend)}
              </span>
            </div>
          </div>
        )}

        {/* 均线 */}
        {(ma5 || ma20) && (
          <div style={cardStyle}>
            <div style={labelStyle}>移动平均线</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
              {ma5 && (
                <div style={maLineStyle}>
                  <span style={{ color: C.td }}>MA5:</span>
                  <span style={{ fontWeight: 600, color: "#3B82F6" }}>${ma5.toFixed(2)}</span>
                </div>
              )}
              {ma20 && (
                <div style={maLineStyle}>
                  <span style={{ color: C.td }}>MA20:</span>
                  <span style={{ fontWeight: 600, color: "#8B5CF6" }}>${ma20.toFixed(2)}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 支撑/阻力位 */}
        {(support || resistance) && (
          <div style={cardStyle}>
            <div style={labelStyle}>支撑/阻力位</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
              {support && (
                <div style={maLineStyle}>
                  <span style={{ color: C.td }}>支撑:</span>
                  <span style={{ fontWeight: 600, color: "#16A34A" }}>${support.toFixed(2)}</span>
                </div>
              )}
              {resistance && (
                <div style={maLineStyle}>
                  <span style={{ color: C.td }}>阻力:</span>
                  <span style={{ fontWeight: 600, color: "#DC2626" }}>${resistance.toFixed(2)}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 成交量 */}
        {volume && volume.status && (
          <div style={cardStyle}>
            <div style={labelStyle}>成交量</div>
            <div style={valueContainerStyle}>
              <span style={{ fontSize: 18, fontWeight: 700, color: getVolumeColor(volume.status) }}>
                {getVolumeLabel(volume.status)}
              </span>
              {volume.ratio && (
                <span style={{ fontSize: 12, color: C.td, marginLeft: 8 }}>
                  ({volume.ratio.toFixed(2)}x)
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * RSI 进度条组件
 */
function RSIBar({ value }) {
  const getBarColor = (val) => {
    if (val >= 70) return "#DC2626"; // 超买 - 红色
    if (val <= 30) return "#16A34A"; // 超卖 - 绿色
    return "#3B82F6"; // 中性 - 蓝色
  };

  return (
    <div style={{ marginTop: 8 }}>
      <div style={rsiBarContainerStyle}>
        {/* 超卖区域 */}
        <div style={{ ...rsiZoneStyle, left: 0, width: "30%", background: "rgba(22, 163, 74, 0.1)" }} />
        {/* 超买区域 */}
        <div style={{ ...rsiZoneStyle, right: 0, width: "30%", background: "rgba(220, 38, 38, 0.1)" }} />

        {/* RSI 值指示器 */}
        <div
          style={{
            position: "absolute",
            left: `${value}%`,
            top: "50%",
            transform: "translate(-50%, -50%)",
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: getBarColor(value),
            border: "2px solid white",
            boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
            zIndex: 2,
          }}
        />

        {/* 进度条 */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: "50%",
            transform: "translateY(-50%)",
            width: `${value}%`,
            height: 4,
            background: getBarColor(value),
            borderRadius: 2,
            transition: "width 0.3s ease",
          }}
        />
      </div>

      {/* 刻度标签 */}
      <div style={rsiLabelsStyle}>
        <span style={{ color: "#16A34A", fontSize: 10, fontWeight: 600 }}>30</span>
        <span style={{ color: C.td, fontSize: 10 }}>50</span>
        <span style={{ color: "#DC2626", fontSize: 10, fontWeight: 600 }}>70</span>
      </div>
    </div>
  );
}

// 辅助函数
function getRSIColor(rsi) {
  if (rsi >= 70) return "#DC2626";
  if (rsi <= 30) return "#16A34A";
  return "#3B82F6";
}

function getRSISignal(rsi) {
  if (rsi >= 70) return "超买";
  if (rsi <= 30) return "超卖";
  return "中性";
}

function getTrendLabel(trend) {
  const labels = {
    uptrend: "上涨趋势",
    downtrend: "下跌趋势",
    sideways: "震荡",
    上涨: "上涨趋势",
    下跌: "下跌趋势",
    震荡: "震荡",
  };
  return labels[trend] || trend;
}

function getTrendColor(trend) {
  if (trend === "uptrend" || trend === "上涨") return "#16A34A";
  if (trend === "downtrend" || trend === "下跌") return "#DC2626";
  return "#64748B";
}

function getTrendEmoji(trend) {
  if (trend === "uptrend" || trend === "上涨") return "📈";
  if (trend === "downtrend" || trend === "下跌") return "📉";
  return "➡️";
}

function getVolumeLabel(status) {
  const labels = {
    high: "放量",
    low: "缩量",
    normal: "正常",
  };
  return labels[status] || status;
}

function getVolumeColor(status) {
  if (status === "high") return "#F59E0B";
  if (status === "low") return "#64748B";
  return "#3B82F6";
}

// 样式
const containerStyle = {
  background: C.white,
  borderRadius: 12,
  border: `1px solid ${C.border}`,
  padding: "14px 16px",
};

const titleStyle = {
  fontSize: 11.5,
  fontWeight: 700,
  color: C.ts,
  fontFamily: F.m,
  marginBottom: 12,
  textTransform: "uppercase",
};

const gridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 12,
};

const cardStyle = {
  background: "#F8FAFC",
  borderRadius: 8,
  padding: "12px",
  border: `1px solid ${C.borderL}`,
};

const labelStyle = {
  fontSize: 11,
  color: C.td,
  fontWeight: 600,
  marginBottom: 8,
  fontFamily: F.m,
};

const valueContainerStyle = {
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const signalStyle = (signal) => ({
  fontSize: 11,
  fontWeight: 700,
  padding: "2px 8px",
  borderRadius: 999,
  background: signal === "超买" ? "#FEE2E2" : signal === "超卖" ? "#DCFCE7" : "#E0E7FF",
  color: signal === "超买" ? "#991B1B" : signal === "超卖" ? "#166534" : "#3730A3",
});

const maLineStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  fontSize: 12,
};

const rsiBarContainerStyle = {
  position: "relative",
  width: "100%",
  height: 24,
  background: "#E2E8F0",
  borderRadius: 12,
  overflow: "hidden",
};

const rsiZoneStyle = {
  position: "absolute",
  top: 0,
  height: "100%",
};

const rsiLabelsStyle = {
  display: "flex",
  justifyContent: "space-between",
  marginTop: 4,
  paddingLeft: 2,
  paddingRight: 2,
};
