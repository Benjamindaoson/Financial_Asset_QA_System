/**
 * RAG Debug 面板 — 仅在 URL 含 ?debug=true 时展示
 * 展示：原始 Query、rag_citations（召回的 Top-K chunks 及分数）
 */
import { useState } from "react";
import { C, F } from "../../theme";

export function RAGDebugPanel({ query, rag_citations = [], trace = [] }) {
  const [open, setOpen] = useState(false);

  const isDebug =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("debug") === "true";

  if (!isDebug) return null;
  if (!query && !rag_citations?.length && !trace?.length) return null;

  return (
    <div
      style={{
        marginTop: 10,
        background: C.white,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "8px 12px",
      }}
    >
      <div
        onClick={() => setOpen((v) => !v)}
        style={{
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 6,
          color: C.ts,
          fontSize: 11,
          fontFamily: F.m,
          userSelect: "none",
        }}
      >
        <span style={{ fontSize: 9 }}>{open ? "▼" : "▶"}</span>
        RAG Debug {rag_citations?.length ? `· ${rag_citations.length} 条引用` : ""}
      </div>
      {open && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 12, fontSize: 11.5, color: C.text }}>
          {query && (
            <div>
              <div style={{ fontWeight: 600, color: C.ts, marginBottom: 4 }}>原始 Query</div>
              <div style={{ padding: 8, background: C.bg, borderRadius: 6 }}>{query}</div>
            </div>
          )}
          {rag_citations?.length > 0 && (
            <div>
              <div style={{ fontWeight: 600, color: C.ts, marginBottom: 4 }}>召回的 Top-K chunks</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {rag_citations.map((c, i) => (
                  <div
                    key={i}
                    style={{
                      padding: 8,
                      background: C.bg,
                      borderRadius: 6,
                      borderLeft: `3px solid ${C.accent}`,
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>
                      [{c.id}] {c.source} · 相关度 {c.score} · {c.method === "vector+rerank" ? "向量+重排" : c.method === "token_match" ? "关键词匹配" : c.method}
                    </div>
                    <div style={{ fontSize: 13, color: C.td }}>{c.preview || "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {rag_citations?.length === 0 && query && (
            <div style={{ color: C.td, fontStyle: "italic" }}>此回答未使用知识库检索</div>
          )}
        </div>
      )}
    </div>
  );
}
