import { C } from "../../theme";

const pulseStyle = {
  animation: "skeleton-pulse 1.5s ease-in-out infinite",
};

export function LoadSteps({ currentStep }) {
  const steps = ["识别问题类型...", "获取市场数据...", "生成分析报告..."];
  return (
    <div style={{ padding: "10px 0" }}>
      {steps.map((t, i) => (
        <div
          key={i}
          style={{
            fontSize: 12,
            color: i <= currentStep ? C.accent : C.td,
            display: "flex",
            alignItems: "center",
            gap: 5,
            marginBottom: 3,
            opacity: i <= currentStep ? 1 : 0.4,
            transition: "all .3s",
          }}
        >
          {i < currentStep ? (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : i === currentStep ? (
            <span style={{ width: 13, height: 13, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: C.accent,
                  animation: "pls 1s infinite",
                }}
              />
            </span>
          ) : (
            <span style={{ width: 13, height: 13, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ width: 4, height: 4, borderRadius: "50%", background: C.td }} />
            </span>
          )}
          {t}
        </div>
      ))}
    </div>
  );
}

export function Skel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* 价格卡片骨架 */}
      <div style={{
        background: C.white,
        borderRadius: 12,
        border: `1px solid ${C.border}`,
        padding: "12px 16px",
      }}>
        <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
          <div style={{ width: 80, height: 28, background: C.sk, borderRadius: 4, ...pulseStyle }} />
          <div style={{ width: 60, height: 18, background: C.sk, borderRadius: 4, ...pulseStyle }} />
        </div>
        <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ width: 50, height: 12, background: C.sk, borderRadius: 4, ...pulseStyle }} />
          ))}
        </div>
      </div>

      {/* 走势图骨架 */}
      <div style={{
        background: C.white,
        borderRadius: 12,
        padding: "14px 16px",
        border: `1px solid ${C.border}`,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={{ width: 100, height: 14, background: C.sk, borderRadius: 4, ...pulseStyle }} />
          <div style={{ display: "flex", gap: 5 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ width: 32, height: 22, background: C.sk, borderRadius: 999, ...pulseStyle }} />
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ width: "100%", height: 80, background: C.sk, borderRadius: 4, ...pulseStyle }} />
          <div style={{ width: "95%", height: 80, background: C.sk, borderRadius: 4, ...pulseStyle }} />
          <div style={{ width: "98%", height: 80, background: C.sk, borderRadius: 4, ...pulseStyle }} />
        </div>
      </div>

      {/* AI 分析骨架 */}
      <div style={{
        background: "#FAFCFF",
        borderRadius: 12,
        padding: 18,
        border: `1px solid #D6E4F7`,
        position: "relative"
      }}>
        <div
          style={{
            position: "absolute",
            top: -9,
            left: 12,
            background: C.accentL,
            color: C.accent,
            fontSize: 9.5,
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: 8,
            border: `1px solid #BFD5F0`,
          }}
        >
          AI 分析
        </div>
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 12 }}>
          {["走势概述", "事件归因", "当前状态"].map((title, i) => (
            <div key={i}>
              <div style={{ width: "25%", height: 16, background: C.sk, borderRadius: 4, marginBottom: 8, ...pulseStyle }} />
              <div style={{ width: "90%", height: 14, background: C.sk, borderRadius: 4, marginBottom: 6, ...pulseStyle }} />
              <div style={{ width: "75%", height: 14, background: C.sk, borderRadius: 4, marginBottom: 6, ...pulseStyle }} />
              <div style={{ width: "85%", height: 14, background: C.sk, borderRadius: 4, ...pulseStyle }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
