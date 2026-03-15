/**
 * 参考来源折叠区 — 知识库摘录，支持 items（source/score/preview/method）或 text 兼容
 */
import { useState } from "react";
import { C, F } from "../../theme";

const methodLabel = (m) => (m === "vector+rerank" ? "向量+重排" : m === "token_match" ? "关键词匹配" : m || "未知");

const stripBold = (s) => (s || "").replace(/\*\*/g, "");

const ReferenceSource = ({ block }) => {
  const data = block?.data || {};
  const items = data.items || [];
  const [open, setOpen] = useState(items.length > 0);
  const hasItems = items.length > 0;
  const cleanText = stripBold(
    (data.text || "").replace(/^-?\s*---\s*\n[\s\S]*?\n---\s*\n/gm, "").trim()
  );

  return (
    <div
      style={{
        borderRadius: 10,
        border: `1px solid ${C.borderL}`,
        background: "#F8FAFC",
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "9px 14px",
          cursor: "pointer",
          userSelect: "none",
          gap: 8,
        }}
      >
        <span style={{ fontSize: 11.5, color: C.ts, fontFamily: F.m, fontWeight: 600 }}>
          📚 参考来源{block?.title ? `：${block.title}` : ""}
          {hasItems && ` · ${items.length} 条引用`}
          （点击展开）
        </span>
        <span
          style={{
            fontSize: 10,
            color: C.td,
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
            flexShrink: 0,
          }}
        >
          ▼
        </span>
      </div>
      {open && (
        <div
          style={{
            padding: "12px 14px",
            borderTop: `1px solid ${C.borderL}`,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {hasItems ? (
            items.map((item) => (
              <div
                key={item.id}
                style={{
                  background: C.white,
                  borderRadius: 8,
                  border: `1px solid ${C.border}`,
                  padding: "10px 12px",
                  fontSize: 12,
                  lineHeight: 1.6,
                  color: C.text,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, color: C.accent, fontFamily: F.m }}>
                    [{item.id}] {item.source}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: "#E0F2FE",
                      color: "#0369A1",
                      fontFamily: F.m,
                    }}
                  >
                    相关度 {item.score}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      color: C.td,
                      fontFamily: F.m,
                    }}
                  >
                    {methodLabel(item.method)}
                  </span>
                </div>
                <div style={{ color: "#6b7280", whiteSpace: "pre-wrap", fontSize: 13 }}>{stripBold(item.preview)}</div>
              </div>
            ))
          ) : cleanText ? (
            <div style={{ fontSize: 13, lineHeight: 1.75, whiteSpace: "pre-wrap", color: "#6b7280" }}>
              {cleanText}
            </div>
          ) : (
            <div style={{ fontSize: 13, color: C.td }}>
              此回答由模型推理生成，未使用知识库
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReferenceSource;
