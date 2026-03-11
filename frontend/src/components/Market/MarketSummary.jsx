import { C, F } from "../../theme";

export function MarketSummary({ summary }) {
  if (!summary?.text) {
    return null;
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
        市场摘要
      </h2>
      <div
        style={{
          background: "#FAFCFF",
          border: "1px solid #D6E4F7",
          borderRadius: 12,
          padding: "18px 20px",
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
            border: "1px solid #BFD5F0",
          }}
        >
          AI 摘要
        </div>
        <div
          style={{
            fontSize: 14,
            lineHeight: 1.7,
            color: C.text,
            fontFamily: F.m,
            whiteSpace: "pre-wrap",
          }}
        >
          {summary.text}
        </div>
        {summary.confidence && (
          <div
            style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: `1px solid ${C.border}`,
              fontSize: 11,
              color: C.td,
              fontFamily: F.m,
            }}
          >
            置信度: {summary.confidence}
          </div>
        )}
      </div>
    </div>
  );
}
