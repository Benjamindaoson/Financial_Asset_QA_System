/**
 * AI 分析模块 — 走势概述 / 事件归因 / 当前状态，默认全部展开
 * @param {Object} props
 * @param {Array<{title: string, content: string}>} props.sections - 解析后的章节
 * @param {string} [props.title] - 模块标题
 * @param {Object} [props.keyMetrics] - key_metrics 数据，用于展望标签
 */

/** 预处理 Markdown：移除加粗星号（LLM 输出格式不稳定，星号裸露影响阅读） */
function normalizeMarkdown(text) {
  if (!text || typeof text !== "string") return "";
  let out = text.replace(/\uFF0A/g, "*");
  out = out.replace(/\*\*/g, "");
  return out;
}

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { C, F } from "../../theme";

const markdownStyles = {
  p: { margin: "0 0 10px 0", lineHeight: 1.85, fontSize: 14 },
  strong: { fontWeight: 700, color: C.text, fontSize: 14 },
  em: { fontStyle: "italic" },
  ul: { margin: "0 0 10px 0", paddingLeft: 20, fontSize: 14 },
  ol: { margin: "0 0 10px 0", paddingLeft: 20, fontSize: 14 },
  li: { marginBottom: 4 },
  code: { background: "#F1F5F9", padding: "2px 6px", borderRadius: 4, fontSize: 13 },
};

function getSectionIcon(title) {
  const iconMap = {
    近期走势: "📈",
    技术面观察: "🔍",
    风险提示: "⚠️",
    基本面分析: "📊",
    市场情绪: "💭",
    走势概述: "📈",
    事件归因: "📰",
    当前状态: "💡",
    定义: "📖",
    计算公式: "🔢",
    核心区别: "🔢",
    实际应用举例: "💼",
    注意事项: "⚠️",
  };
  if (iconMap[title]) return iconMap[title];
  for (const [key, icon] of Object.entries(iconMap)) {
    if (title.includes(key)) return icon;
  }
  return "📌";
}

function getOutlookFromChangePct(changePct) {
  if (changePct == null) return null;
  if (changePct > 2) return { label: "📈 短期偏多", bg: "#DCFCE7", color: "#166534" };
  if (changePct < -2) return { label: "📉 短期偏空", bg: "#FEE2E2", color: "#991B1B" };
  return { label: "⚖️ 短期中性", bg: "#F3F4F6", color: "#374151" };
}

const analysisBlockStyle = {
  background: "#FAFCFF",
  borderRadius: 12,
  border: "1px solid #D6E4F7",
  padding: "18px 18px 14px",
  position: "relative",
};

const analysisBadgeStyle = {
  position: "absolute",
  top: -9,
  left: 12,
  background: C.purpleL,
  color: C.purple,
  fontSize: 9.5,
  fontWeight: 700,
  padding: "2px 8px",
  borderRadius: 8,
  border: "1px solid #DDD6FE",
};

const analysisDisclaimerStyle = {
  fontSize: 9.5,
  color: C.td,
  marginTop: 12,
  paddingTop: 10,
  borderTop: `1px solid ${C.borderL}`,
  fontStyle: "italic",
};

const DEFAULT_OPEN_TITLES = /^(走势概述|定义|核心区别|近期走势|事件归因|当前状态)$/;

export default function AnalysisSection({ sections = [], title = "AI 分析", keyMetrics }) {
  const [openIndices, setOpenIndices] = useState(() => {
    const defaultOpen = new Set();
    sections.forEach((s, i) => {
      if (DEFAULT_OPEN_TITLES.test((s.title || "").trim())) defaultOpen.add(i);
      else if (sections.length <= 3) defaultOpen.add(i);
    });
    return defaultOpen.size > 0 ? defaultOpen : new Set([0]);
  });
  const outlook = getOutlookFromChangePct(keyMetrics?.change_pct);
  // 展望标签显示在「当前状态」或最后一节
  const currentStateIndex = sections.findIndex((s) => /当前状态|核心要点|综合/.test((s.title || "").trim()));
  const outlookSectionIndex = currentStateIndex >= 0 ? currentStateIndex : sections.length - 1;

  const toggleIndex = (index) => {
    setOpenIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  return (
    <div style={analysisBlockStyle}>
      <div style={analysisBadgeStyle}>{title}</div>
      <div style={{ marginTop: 8 }}>
        {sections.map((section, index) => {
          const isOpen = openIndices.has(index);
          const icon = getSectionIcon(section.title);
          return (
            <div
              key={index}
              style={{
                marginBottom: 12,
                padding: 12,
                background: isOpen ? "#F8FAFC" : "transparent",
                borderRadius: 10,
                border: `1px solid ${isOpen ? C.border : "transparent"}`,
              }}
            >
              <div
                onClick={() => toggleIndex(index)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  padding: "4px 0",
                  userSelect: "none",
                }}
              >
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{ fontSize: 13.5, fontWeight: 600, color: C.text, flex: 1 }}>{section.title}</span>
                {outlook && index === outlookSectionIndex && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      padding: "4px 12px",
                      borderRadius: 999,
                      background: outlook.bg,
                      color: outlook.color,
                    }}
                  >
                    {outlook.label}
                  </span>
                )}
                <span
                  style={{
                    fontSize: 11,
                    color: C.td,
                    transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform 0.2s",
                  }}
                >
                  ▼
                </span>
              </div>
              {isOpen && (
                <div style={{ fontSize: 14, lineHeight: 1.85, color: C.text, paddingLeft: 24, marginTop: 8 }}>
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p style={markdownStyles.p}>{children}</p>,
                      strong: ({ children }) => <strong style={markdownStyles.strong}>{children}</strong>,
                      em: ({ children }) => <em style={markdownStyles.em}>{children}</em>,
                      ul: ({ children }) => <ul style={markdownStyles.ul}>{children}</ul>,
                      ol: ({ children }) => <ol style={markdownStyles.ol}>{children}</ol>,
                      li: ({ children }) => <li style={markdownStyles.li}>{children}</li>,
                      code: ({ children }) => <code style={markdownStyles.code}>{children}</code>,
                    }}
                  >
                    {normalizeMarkdown(section.content)}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={analysisDisclaimerStyle}>以上分析由 AI 基于公开数据生成，不构成投资建议</div>
    </div>
  );
}
