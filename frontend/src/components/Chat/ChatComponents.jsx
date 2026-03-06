import { C, F } from "../../theme";

export function StreamingText({ text }) {
  return (
    <div
      style={{
        background: "#FAFCFF",
        borderRadius: 12,
        padding: "18px 18px 14px",
        border: `1px solid #D6E4F7`,
        position: "relative",
        fontSize: 13,
        lineHeight: 1.85,
        color: C.text,
        whiteSpace: "pre-wrap",
      }}
    >
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
      {text}
      <span
        style={{
          display: "inline-block",
          width: 6,
          height: 12,
          background: C.accent,
          marginLeft: 2,
          animation: "blink 1s infinite",
        }}
      />
    </div>
  );
}

export function Src({ items }) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {items.map((s, i) => (
        <span
          key={i}
          style={{
            fontSize: 9.5,
            padding: "3px 8px",
            borderRadius: 10,
            background: C.bg,
            border: `1px solid ${C.border}`,
            color: C.ts,
            fontFamily: F.m,
          }}
        >
          <span style={{ color: C.accent, marginRight: 2 }}>●</span>
          {s.name}
        </span>
      ))}
    </div>
  );
}

export function Disc() {
  return (
    <div
      style={{
        fontSize: 10.5,
        color: C.warn,
        padding: "7px 11px",
        background: C.warnBg,
        borderRadius: 7,
        borderLeft: `3px solid ${C.warn}`,
        lineHeight: 1.5,
      }}
    >
      ⚠️ 行情数据来自公开API，AI分析仅供参考，不构成投资建议。
    </div>
  );
}
