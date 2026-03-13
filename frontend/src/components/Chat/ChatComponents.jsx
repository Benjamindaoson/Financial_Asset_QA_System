import { useState } from "react";
import { Chart } from "../Chart";
import { C, F } from "../../theme";

export function StreamingText({ text }) {
  return (
    <div style={messageCardStyle}>
      <div style={messageBadgeStyle}>AI 分析</div>
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

const BLOCK_ORDER = {
  chart: 1,
  key_metrics: 2,
  analysis: 3,
  table: 4,
  quote: 5,
  bullets: 6,
  warning: 7,
  source: 8,
  trace: 9,
};

export function ResponseBlocks({ blocks = [] }) {
  if (!blocks.length) {
    return null;
  }

  const sorted = [...blocks].sort(
    (a, b) => (BLOCK_ORDER[a.type] || 99) - (BLOCK_ORDER[b.type] || 99)
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {sorted.map((block, index) => (
        <Block key={`${block.type}-${index}`} block={block} />
      ))}
    </div>
  );
}

function Block({ block }) {
  if (block.type === "key_metrics") {
    const d = block.data || {};
    const isUp = (d.change_pct ?? d.change ?? 0) >= 0;
    const changeColor = isUp ? "#16a34a" : "#dc2626";
    const arrow = isUp ? "▲" : "▼";
    const hasPeriodChange = d.change_pct != null;
    const hasOHLCV = d.open != null || d.high != null || d.low != null;

    return (
      <div style={{ ...panelStyle, padding: "14px 16px" }}>
        {/* Price row */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: "1.75rem", fontWeight: 800, color: C.text, fontFamily: F.m, letterSpacing: "-0.5px" }}>
            {d.currency && d.currency !== "USD" ? d.currency + " " : "$"}
            {d.price != null ? d.price.toFixed(2) : (d.end_price != null ? d.end_price.toFixed(2) : "—")}
          </span>
          {hasPeriodChange && (
            <span style={{ fontSize: "0.95rem", color: changeColor, fontWeight: 700 }}>
              {arrow}{" "}
              {d.change != null ? `${d.change > 0 ? "+" : ""}${d.change.toFixed(2)} ` : ""}
              ({d.change_pct > 0 ? "+" : ""}{d.change_pct.toFixed(2)}%
              {d.period_days && d.period_days > 1 ? `, ${d.period_days}日` : ""})
            </span>
          )}
          {d.trend && (
            <span style={{
              fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "3px 8px",
              background: d.trend === "上涨" ? "#DCFCE7" : d.trend === "下跌" ? "#FEE2E2" : "#F1F5F9",
              color: d.trend === "上涨" ? "#166534" : d.trend === "下跌" ? "#991B1B" : "#475569",
              fontFamily: F.m,
            }}>
              {d.trend}
            </span>
          )}
        </div>

        {/* OHLCV row */}
        {hasOHLCV && (
          <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: "0.82rem", color: C.ts, flexWrap: "wrap" }}>
            {d.open != null && <span>开 <b style={{ color: C.text }}>{d.open.toFixed(2)}</b></span>}
            {d.high != null && <span>高 <b style={{ color: "#16a34a" }}>{d.high.toFixed(2)}</b></span>}
            {d.low != null && <span>低 <b style={{ color: "#dc2626" }}>{d.low.toFixed(2)}</b></span>}
            {d.volume != null && (
              <span>量 <b style={{ color: C.text }}>{d.volume >= 1e6 ? `${(d.volume / 1e6).toFixed(1)}M` : d.volume.toLocaleString()}</b></span>
            )}
          </div>
        )}

        {/* Period summary row */}
        {d.start_price != null && d.end_price != null && d.period_days && (
          <div style={{ marginTop: 6, fontSize: "0.8rem", color: C.ts }}>
            {d.period_days}日区间：{d.start_price.toFixed(2)} → {d.end_price.toFixed(2)}
          </div>
        )}
      </div>
    );
  }

  if (block.type === "bullets") {
    return (
      <div style={panelStyle}>
        <div style={panelTitleStyle}>{block.title}</div>
        <ul style={{ margin: 0, paddingLeft: 18, color: C.text, fontSize: 12.5, lineHeight: 1.7 }}>
          {(block.data?.items || []).map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </div>
    );
  }

  if (block.type === "table") {
    return (
      <div style={panelStyle}>
        <div style={panelTitleStyle}>{block.title}</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr>
                {(block.data?.columns || []).map((column) => (
                  <th key={column} style={tableHeadStyle}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(block.data?.rows || []).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {(block.data?.columns || []).map((column) => (
                    <td key={column} style={tableCellStyle}>
                      {row?.[column] ?? "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (block.type === "chart") {
    const chartType = block.data?.chart_type === "comparison" ? "comparison" : "history";
    const symbol = block.data?.symbol;
    const series = block.data?.series || [];
    const defaultRange = block.data?.default_range || null;
    return (
      <Chart
        symbol={symbol}
        chartType={chartType}
        embeddedSeries={series}
        rangeKey={block.data?.range_key || "1y"}
        defaultRange={defaultRange}
      />
    );
  }

  if (block.type === "quote") {
    // Strip YAML frontmatter from quote content
    const cleanContent = (block.data?.text || '')
      .replace(/^-?\s*---\s*\n[\s\S]*?\n---\s*\n/gm, '')
      .trim();

    return (
      <div style={{ ...panelStyle, background: "#FAFCFF", borderColor: "#D6E4F7" }}>
        <div style={panelTitleStyle}>{block.title}</div>
        <div style={{ fontSize: 12.5, lineHeight: 1.8, whiteSpace: "pre-wrap", color: C.text }}>{cleanContent}</div>
      </div>
    );
  }

  if (block.type === "warning") {
    return (
      <div style={{ ...panelStyle, background: C.warnBg, borderColor: "#FCD34D" }}>
        <div style={{ ...panelTitleStyle, color: C.warn }}>{block.title}</div>
        <ul style={{ margin: 0, paddingLeft: 18, color: C.text, fontSize: 12.5, lineHeight: 1.7 }}>
          {(block.data?.items || []).map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </div>
    );
  }

  if (block.type === "analysis") {
    return (
      <div style={analysisBlockStyle}>
        <div style={analysisBadgeStyle}>{block.title || "AI 分析"}</div>
        <div style={analysisContentStyle}>
          <MarkdownText text={block.data?.text || ""} />
        </div>
        <div style={analysisDisclaimerStyle}>
          以上分析由 AI 基于公开数据生成，不构成投资建议
        </div>
      </div>
    );
  }

  return null;
}

function MarkdownText({ text }) {
  // Simple markdown parser for basic formatting
  const lines = text.split("\n");
  const elements = [];
  let currentParagraph = [];
  let inList = false;
  let listItems = [];

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      elements.push(
        <p key={`p-${elements.length}`} style={{ margin: "0 0 12px 0" }}>
          {parseInlineMarkdown(currentParagraph.join(" "))}
        </p>
      );
      currentParagraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} style={{ margin: "0 0 12px 0", paddingLeft: 20 }}>
          {listItems.map((item, idx) => (
            <li key={idx} style={{ marginBottom: 4 }}>
              {parseInlineMarkdown(item)}
            </li>
          ))}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    // List item
    if (trimmed.match(/^[-*]\s+/)) {
      flushParagraph();
      inList = true;
      listItems.push(trimmed.replace(/^[-*]\s+/, ""));
    }
    // Empty line
    else if (trimmed === "") {
      flushList();
      flushParagraph();
    }
    // Regular text
    else {
      if (inList) {
        flushList();
      }
      currentParagraph.push(trimmed);
    }
  });

  flushList();
  flushParagraph();

  return <div>{elements}</div>;
}

function parseInlineMarkdown(text) {
  // Parse bold **text**
  const parts = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    if (boldMatch) {
      const before = remaining.substring(0, boldMatch.index);
      if (before) parts.push(<span key={key++}>{before}</span>);
      parts.push(<strong key={key++}>{boldMatch[1]}</strong>);
      remaining = remaining.substring(boldMatch.index + boldMatch[0].length);
    } else {
      parts.push(<span key={key++}>{remaining}</span>);
      break;
    }
  }

  return parts.length > 0 ? parts : text;
}

export function ConfidenceBadge({ confidence }) {
  if (!confidence) {
    return null;
  }

  const getConfidenceLabel = (score) => {
    if (score >= 70) return { text: '数据充分', color: '#16a34a', bg: '#DCFCE7' };
    if (score >= 40) return { text: '数据参考', color: '#2563eb', bg: '#DBEAFE' };
    return null; // Don't show for low confidence
  };

  const label = getConfidenceLabel(confidence.score);
  if (!label) return null;

  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        borderRadius: 999,
        padding: "4px 8px",
        background: label.bg,
        color: label.color,
        fontFamily: F.m,
      }}
    >
      {label.text}
    </span>
  );
}

export function SourcesPanel({ items = [] }) {
  if (!items.length) {
    return null;
  }

  // Get unique source names
  const sourceNames = [...new Set(items.map(s => s.name))];

  // Get the most recent timestamp
  const latestTimestamp = items.reduce((latest, source) => {
    const sourceTime = new Date(source.timestamp).getTime();
    const latestTime = new Date(latest).getTime();
    return sourceTime > latestTime ? source.timestamp : latest;
  }, items[0].timestamp);

  const formatTimestamp = (ts) => {
    try {
      const date = new Date(ts);
      return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
    } catch {
      return ts;
    }
  };

  return (
    <div
      style={{
        fontSize: 10.5,
        padding: "6px 10px",
        borderRadius: 8,
        background: C.bg,
        border: `1px solid ${C.border}`,
        color: C.ts,
        fontFamily: F.m,
      }}
    >
      数据来源：{sourceNames.join(' · ')} | 更新时间：{formatTimestamp(latestTimestamp)}
    </div>
  );
}

export function Disc({ text = "以上内容仅供参考，不构成投资建议。" }) {
  return (
    <div
      style={{
        fontSize: 9.5,
        color: C.td,
        padding: "6px 10px",
        background: "#F8F9FA",
        borderRadius: 6,
        lineHeight: 1.4,
        textAlign: "center",
      }}
    >
      {text}
    </div>
  );
}

function formatTimestamp(value) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

const messageCardStyle = {
  background: "#FAFCFF",
  borderRadius: 12,
  padding: "18px 18px 14px",
  border: "1px solid #D6E4F7",
  position: "relative",
  fontSize: 13,
  lineHeight: 1.85,
  color: C.text,
  whiteSpace: "pre-wrap",
};

const messageBadgeStyle = {
  position: "absolute",
  top: -9,
  left: 12,
  background: C.accentL,
  color: C.accent,
  fontSize: 9.5,
  fontWeight: 700,
  padding: "2px 8px",
  borderRadius: 8,
  border: "1px solid #BFD5F0",
};

const panelStyle = {
  background: C.white,
  borderRadius: 12,
  border: `1px solid ${C.border}`,
  padding: "12px 14px",
};

const panelTitleStyle = {
  fontSize: 11,
  fontWeight: 700,
  color: C.ts,
  marginBottom: 8,
  fontFamily: F.m,
  textTransform: "uppercase",
};

const tableHeadStyle = {
  textAlign: "left",
  padding: "8px 10px",
  borderBottom: `1px solid ${C.border}`,
  color: C.ts,
  fontWeight: 700,
  fontFamily: F.m,
};

const tableCellStyle = {
  padding: "8px 10px",
  borderBottom: `1px solid ${C.borderL}`,
  color: C.text,
};

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

const analysisContentStyle = {
  fontSize: 13,
  lineHeight: 1.85,
  color: C.text,
};

const analysisDisclaimerStyle = {
  fontSize: 9.5,
  color: C.td,
  marginTop: 12,
  paddingTop: 10,
  borderTop: `1px solid ${C.borderL}`,
  fontStyle: "italic",
};
