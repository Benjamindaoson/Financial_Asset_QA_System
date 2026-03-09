import { C, F } from "../../theme";

export function AIAnalysis({ analysis }) {
  if (!analysis) {
    return null;
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: C.text,
          marginBottom: 16,
          fontFamily: F.m,
        }}
      >
        AI ANALYSIS
      </h2>

      {/* Main Analysis Card */}
      <div
        style={{
          background: "#FAFCFF",
          border: `1px solid #D6E4F7`,
          borderRadius: 12,
          padding: "20px",
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: -9,
            left: 16,
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

        {/* Trend Summary */}
        {analysis.trend_summary && (
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: C.ts,
                marginBottom: 6,
                fontFamily: F.m,
              }}
            >
              走势摘要
            </div>
            <div
              style={{
                fontSize: 14,
                lineHeight: 1.7,
                color: C.text,
                fontFamily: F.m,
              }}
            >
              {analysis.trend_summary}
            </div>
          </div>
        )}

        {/* Driving Factors */}
        {analysis.drivers && analysis.drivers.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: C.ts,
                marginBottom: 8,
                fontFamily: F.m,
              }}
            >
              主要驱动因素
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {analysis.drivers.map((driver, idx) => (
                <div
                  key={idx}
                  style={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: C.text,
                    fontFamily: F.m,
                    paddingLeft: 16,
                    position: "relative",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: 0,
                      color: C.accent,
                    }}
                  >
                    {idx + 1}.
                  </span>
                  {driver}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk Factors */}
        {analysis.risks && analysis.risks.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: C.ts,
                marginBottom: 8,
                fontFamily: F.m,
              }}
            >
              风险与不确定性
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {analysis.risks.map((risk, idx) => (
                <div
                  key={idx}
                  style={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: C.text,
                    fontFamily: F.m,
                    paddingLeft: 16,
                    position: "relative",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: 0,
                      color: "#EF4444",
                    }}
                  >
                    •
                  </span>
                  {risk}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Observation Points */}
        {analysis.watch_points && analysis.watch_points.length > 0 && (
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: C.ts,
                marginBottom: 8,
                fontFamily: F.m,
              }}
            >
              当前观察点
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {analysis.watch_points.map((point, idx) => (
                <div
                  key={idx}
                  style={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: C.text,
                    fontFamily: F.m,
                    paddingLeft: 16,
                    position: "relative",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: 0,
                      color: "#F59E0B",
                    }}
                  >
                    →
                  </span>
                  {point}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Confidence Level */}
        {analysis.confidence && (
          <div
            style={{
              marginTop: 16,
              paddingTop: 12,
              borderTop: `1px solid ${C.border}`,
              fontSize: 11,
              color: C.td,
              fontFamily: F.m,
            }}
          >
            置信度: {analysis.confidence}
          </div>
        )}
      </div>
    </div>
  );
}

export function RiskPanel({ risks }) {
  if (!risks) {
    return null;
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: C.text,
          marginBottom: 16,
          fontFamily: F.m,
        }}
      >
        RISK ASSESSMENT
      </h2>

      <div
        style={{
          background: "#FFFFFF",
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          padding: "20px",
        }}
      >
        {/* Short-term Trend */}
        {risks.short_term && (
          <RiskItem label="短期趋势" value={risks.short_term} />
        )}

        {/* Medium-term Risk */}
        {risks.medium_term && (
          <RiskItem label="中期风险" value={risks.medium_term} />
        )}

        {/* Key Variables */}
        {risks.key_variables && risks.key_variables.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: C.ts,
                marginBottom: 8,
                fontFamily: F.m,
              }}
            >
              关注变量
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {risks.key_variables.map((variable, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: 11,
                    padding: "4px 10px",
                    borderRadius: 6,
                    background: C.bg,
                    border: `1px solid ${C.border}`,
                    color: C.text,
                    fontFamily: F.m,
                  }}
                >
                  {variable}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RiskItem({ label, value }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          fontSize: 11,
          color: C.td,
          marginBottom: 4,
          fontFamily: F.m,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 500,
          color: C.text,
          fontFamily: F.m,
        }}
      >
        {value}
      </div>
    </div>
  );
}
