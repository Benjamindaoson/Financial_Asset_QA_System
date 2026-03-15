import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Chart } from "../Chart";
import PriceCard from "../Stock/PriceCard";
import AnalysisSection from "./AnalysisSection";
import NewsCards from "./NewsCards";
import ReferenceSource from "./ReferenceSource";
import { C, F } from "../../theme";

/** 预处理 Markdown：移除加粗星号（LLM 输出格式不稳定，星号裸露影响阅读） */
function normalizeMarkdown(text) {
  if (!text || typeof text !== "string") return "";
  let out = text.replace(/\uFF0A/g, "*");
  out = out.replace(/\*\*/g, "");
  return out;
}

const markdownStyles = {
  p: { margin: "0 0 10px 0", lineHeight: 1.85, fontSize: 14 },
  strong: { fontWeight: 700, color: C.text, fontSize: 14 },
  em: { fontStyle: "italic" },
  ul: { margin: "0 0 10px 0", paddingLeft: 20, fontSize: 14 },
  ol: { margin: "0 0 10px 0", paddingLeft: 20, fontSize: 14 },
  li: { marginBottom: 4 },
  code: { background: "#F1F5F9", padding: "2px 6px", borderRadius: 4, fontSize: 13 },
};

// Map internal source names to user-friendly labels
const SOURCE_LABEL_MAP = {
  stooq: 'Stooq 行情',
  stoog: 'Stooq 行情', // 兼容拼写变体
  yfinance: 'YFinance 行情',
  finnhub: 'Finnhub 行情',
  tavily: 'Tavily 新闻',
  alpha_vantage: 'Alpha Vantage',
  sec: 'SEC 公告',
  web: '网络搜索',
};

const HIDDEN_SOURCE_VALUES = ['unavailable', 'not_configured', 'disconnected', 'error', ''];

function mapSourceName(name) {
  if (!name) return null;
  const lower = (String(name) || '').toLowerCase().trim();
  if (HIDDEN_SOURCE_VALUES.includes(lower)) return null;
  if (SOURCE_LABEL_MAP[lower]) return SOURCE_LABEL_MAP[lower];
  // Hide internal .md file names — group them as knowledge base
  if (lower.endsWith('.md')) return '__knowledge__';
  return name;
}

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
  news: 4,
  table: 5,
  quote: 6,
  bullets: 7,
  source: 8,
  trace: 9,
  warning: 10,
};

export function ResponseBlocks({ blocks = [] }) {
  if (!blocks.length) {
    return null;
  }

  const sorted = [...blocks].sort(
    (a, b) => (BLOCK_ORDER[a.type] || 99) - (BLOCK_ORDER[b.type] || 99)
  );
  const keyMetrics = blocks.find((b) => b.type === "key_metrics")?.data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {sorted.map((block, index) => (
        <Block key={`${block.type}-${index}`} block={block} keyMetrics={keyMetrics} />
      ))}
    </div>
  );
}

function parseMarkdownSections(text) {
  // Try to parse ## headings
  const headingRegex = /^##\s+(.+)$/gm;
  const matches = [...text.matchAll(headingRegex)];

  if (matches.length === 0) {
    return null; // No sections found, use fallback
  }

  const sections = [];
  matches.forEach((match, index) => {
    const title = match[1].trim();
    const startPos = match.index + match[0].length;
    const endPos = index < matches.length - 1 ? matches[index + 1].index : text.length;
    const content = text.substring(startPos, endPos).trim();

    sections.push({ title, content });
  });

  return sections;
}

function Block({ block, keyMetrics }) {
  if (block.type === "key_metrics") {
    return <PriceCard block={block} />;
  }

  if (block.type === "news") {
    return (
      <NewsCards
        items={block.data?.items || []}
        title={block.title || "相关新闻"}
      />
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
    return <ReferenceSource block={block} />;
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
    const sections = parseMarkdownSections(block.data?.text || "");

    // If no sections found, use fallback with optimized typography
    if (!sections) {
      return (
        <div style={analysisBlockStyle}>
          <div style={analysisBadgeStyle}>{block.title || "AI 分析"}</div>
          <div style={{
            ...analysisContentStyle,
            lineHeight: 1.85,
            fontSize: 13,
            color: '#1A2332'
          }}>
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
              {normalizeMarkdown(block.data?.text || "")}
            </ReactMarkdown>
          </div>
          <div style={analysisDisclaimerStyle}>
            以上分析由 AI 基于公开数据生成，不构成投资建议
          </div>
        </div>
      );
    }

    return <AnalysisSection sections={sections} title={block.title} keyMetrics={keyMetrics} />;
  }

  if (block.type === "trace") {
    return <TraceBlock block={block} />;
  }

  return null;
}

function TraceBlock({ block }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 8 }}>
      <div 
        onClick={() => setOpen(!open)}
        style={{ cursor: "pointer", color: "#9ca3af", fontSize: "0.8rem" }}
      >
        {open ? "▼ 隐藏调用详情" : "▶ 查看调用详情"}
      </div>
      {open && (
        <div style={{ marginTop: 4, fontSize: "0.8rem", color: "#6b7280" }}>
          {block.data?.text || block.content}
        </div>
      )}
    </div>
  );
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

export function SourcesPanel({ items = [], rag_citations = [] }) {
  const rawNames = [...new Set(items.map(s => s.name))];
  const mappedLabels = new Set();
  let hasKnowledge = false;

  rawNames.forEach(name => {
    const label = mapSourceName(name);
    if (label === '__knowledge__') {
      hasKnowledge = true;
    } else if (label) {
      mappedLabels.add(label);
    }
  });

  if (hasKnowledge || rag_citations.length > 0) mappedLabels.add('知识库');
  const displayNames = [...mappedLabels];

  const citationSuffix = rag_citations.length > 0 ? ` · ${rag_citations.length} 条引用` : '';

  if (displayNames.length === 0 && rag_citations.length === 0) return null;

  const latestTimestamp = items.length > 0
    ? items.reduce((latest, source) => {
        const sourceTime = new Date(source.timestamp).getTime();
        const latestTime = new Date(latest).getTime();
        return sourceTime > latestTime ? source.timestamp : latest;
      }, items[0].timestamp)
    : null;

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
      数据来源：{displayNames.join(' · ')}{citationSuffix}
      {latestTimestamp && ` | 更新时间：${formatTimestamp(latestTimestamp)}`}
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
