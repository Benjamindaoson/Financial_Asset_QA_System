import { C } from "../../theme";

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
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ background: C.white, borderRadius: 12, padding: 18, border: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div>
            <div style={{ width: 55, height: 12, background: C.sk, borderRadius: 4, marginBottom: 7 }} />
            <div style={{ width: 90, height: 16, background: C.sk, borderRadius: 4 }} />
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ width: 80, height: 22, background: C.sk, borderRadius: 4, marginBottom: 5 }} />
            <div style={{ width: 50, height: 10, background: C.sk, borderRadius: 4, marginLeft: "auto" }} />
          </div>
        </div>
      </div>
    </div>
  );
}
