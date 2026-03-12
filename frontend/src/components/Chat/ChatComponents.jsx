import { Chart } from "../Chart";
import { C, F } from "../../theme";
import {
  formatCellValue,
  getColumnLabel,
  getMetricLabel,
  getUnitLabel,
  getChangeColor,
  getTrendIcon,
} from "../../utils/formatters";

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

export function ResponseBlocks({ blocks = [] }) {
  if (!blocks.length) {
    return null;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {blocks.map((block, index) => (
        <Block key={`${block.type}-${index}`} block={block} />
      ))}
    </div>
  );
}

// 智能高亮 bullet 项中的数据
function BulletItem({ text }) {
  // 匹配百分比、价格、数字等
  const parts = text.split(/(\+?\-?\d+\.?\d*%?|\$\d+\.?\d*|[↑↓])/g);

  return (
    <span>
      {parts.map((part, i) => {
        // 百分比
        if (part.match(/^[\+\-]?\d+\.?\d*%$/)) {
          const value = parseFloat(part);
          return (
            <span key={i} style={{ color: getChangeColor(value), fontWeight: 600 }}>
              {part}
            </span>
          );
        }
        // 价格
        if (part.match(/^\$\d+\.?\d*$/)) {
          return (
            <span key={i} style={{ color: C.accent, fontWeight: 600 }}>
              {part}
            </span>
          );
        }
        // 箭头
        if (part === "↑" || part === "↓") {
          return (
            <span key={i} style={{ color: part === "↑" ? "#16A34A" : "#DC2626", fontWeight: 700, fontSize: 14 }}>
              {part}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

function Block({ block }) {
  if (block.type === "bullets") {
    return (
      <div style={panelStyle}>
        <div style={panelTitleStyle}>{block.title}</div>
        <ul style={{ margin: 0, paddingLeft: 18, color: C.text, fontSize: 12.5, lineHeight: 1.7 }}>
          {(block.data?.items || []).map((item, index) => (
            <li key={index}>
              <BulletItem text={item} />
            </li>
          ))}
        </ul>
        <SupportEvidence items={block.supporting_chunks} />
      </div>
    );
  }

  if (block.type === "table") {
    return (
      <div style={panelStyle}>
        <div style={panelTitleStyle}>{block.title}</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
            <thead>
              <tr>
                {(block.data?.columns || []).map((column) => (
                  <th key={column} style={tableHeadStyle}>
                    {getColumnLabel(column)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(block.data?.rows || []).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {(block.data?.columns || []).map((column) => {
                    const rawValue = row?.[column];
                    const isMetricColumn = column === "metric";
                    const isUnitColumn = column === "unit";
                    const displayValue = isMetricColumn ? getMetricLabel(rawValue) : isUnitColumn ? getUnitLabel(rawValue) : formatCellValue(rawValue, column);
                    const isPercentage = column.includes("pct") || column.includes("return") || column.includes("volatility") || column.includes("drawdown");
                    const color = isPercentage ? getChangeColor(rawValue) : C.text;
                    const icon = isPercentage && rawValue !== null && rawValue !== undefined ? getTrendIcon(rawValue) : "";

                    return (
                      <td key={column} style={{ ...tableCellStyle, color }}>
                        {displayValue}
                        {icon && <span style={{ marginLeft: 4, fontSize: 13, fontWeight: 700 }}>{icon}</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <SupportEvidence items={block.supporting_chunks} />
      </div>
    );
  }

  if (block.type === "chart") {
    const chartType = block.data?.chart_type === "comparison" ? "comparison" : "history";
    const symbol = block.data?.symbol;
    const series = block.data?.series || [];
    return <Chart symbol={symbol} chartType={chartType} embeddedSeries={series} rangeKey={block.data?.range_key || "1y"} />;
  }

  if (block.type === "quote") {
    return (
      <div style={{ ...panelStyle, background: "#FAFCFF", borderColor: "#D6E4F7" }}>
        <div style={panelTitleStyle}>{block.title}</div>
        <SimpleMarkdown text={block.data?.text} />
        <SupportEvidence items={block.supporting_chunks} />
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
        <SupportEvidence items={block.supporting_chunks} />
      </div>
    );
  }

  return null;
}

function SupportEvidence({ items = [] }) {
  if (!items?.length) {
    return null;
  }

  return (
    <details style={{ marginTop: 10, paddingTop: 10, borderTop: `1px dashed ${C.border}` }}>
      <summary
        style={{
          cursor: "pointer",
          listStyle: "none",
          userSelect: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 10px",
          borderRadius: 999,
          background: "#F8FAFC",
          border: `1px solid ${C.border}`,
          fontSize: 10.5,
          fontWeight: 800,
          color: C.ts,
          fontFamily: F.m,
        }}
      >
        证据/来源
        <span style={{ fontSize: 10, fontWeight: 700, color: C.td }}>({items.length})</span>
        <span style={{ fontSize: 10, color: C.td }}>点击展开</span>
      </summary>

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        {items.map((item, index) => (
          <div
            key={`${item.title || item.source}-${index}`}
            style={{
              background: "#F8FAFC",
              border: `1px solid ${C.border}`,
              borderRadius: 10,
              padding: "8px 10px",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 800, color: C.text }}>
              {[item.title, item.section].filter(Boolean).join(" / ") || item.source || "证据"}
            </div>
            <div style={{ fontSize: 10.5, color: C.ts, marginTop: 2 }}>
              {[item.source_type, item.chunk_type, item.asset_code, item.date].filter(Boolean).join(" | ")}
            </div>
            {item.snippet ? (
              <div style={{ marginTop: 4 }}>
                <SimpleMarkdown text={item.snippet} fontSize={11.5} />
              </div>
            ) : null}
            {item.url && (
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                style={{ color: C.accent, textDecoration: "none", fontSize: 10.5, marginTop: 4, display: "inline-block" }}
              >
                打开原文
              </a>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

export function ConfidenceBadge({ confidence }) {
  if (!confidence) {
    return null;
  }

  const palette = {
    high: { bg: "#DCFCE7", color: "#166534", icon: "✓", label: "高" },
    medium: { bg: "#FEF3C7", color: "#92400E", icon: "◐", label: "中" },
    low: { bg: "#FEE2E2", color: "#991B1B", icon: "!", label: "低" },
  };
  const style = palette[confidence.level] || palette.medium;

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11,
        fontWeight: 700,
        borderRadius: 8,
        padding: "6px 12px",
        background: style.bg,
        color: style.color,
        fontFamily: F.m,
        border: `1.5px solid ${style.color}20`,
        boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
      }}
    >
      <span style={{ fontSize: 14 }}>{style.icon}</span>
      <span>置信度: {style.label}</span>
      {confidence.score !== undefined && (
        <span style={{ fontSize: 10, opacity: 0.8 }}>({confidence.score})</span>
      )}
    </div>
  );
}

export function SourcesPanel({ items = [] }) {
  if (!items.length) {
    return null;
  }

  return (
    <details>
      <summary
        style={{
          cursor: "pointer",
          listStyle: "none",
          userSelect: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 10px",
          borderRadius: 999,
          background: "#F8FAFC",
          border: `1px solid ${C.border}`,
          fontSize: 10.5,
          fontWeight: 800,
          color: C.ts,
          fontFamily: F.m,
        }}
      >
        数据来源
        <span style={{ fontSize: 10, fontWeight: 700, color: C.td }}>({items.length})</span>
        <span style={{ fontSize: 10, color: C.td }}>点击展开</span>
      </summary>

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        {items.map((source, index) => (
          <div
            key={`${source.name}-${source.timestamp}-${index}`}
            style={{
              fontSize: 10.5,
              padding: "6px 8px",
              borderRadius: 10,
              background: C.bg,
              border: `1px solid ${C.border}`,
              color: C.ts,
              fontFamily: F.m,
            }}
          >
            <div style={{ color: C.accent, marginBottom: 2 }}>{source.name}</div>
            <div>{formatTimestamp(source.timestamp)}</div>
            {source.url && (
              <a href={source.url} target="_blank" rel="noreferrer" style={{ color: C.accent, textDecoration: "none" }}>
                打开链接
              </a>
            )}
          </div>
        ))}
      </div>
    </details>
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
  padding: "14px 16px",
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
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
  padding: "10px 12px",
  borderBottom: `2px solid ${C.border}`,
  color: C.ts,
  fontWeight: 700,
  fontFamily: F.m,
  fontSize: 12,
  background: "#F8FAFC",
};

const tableCellStyle = {
  padding: "10px 12px",
  borderBottom: `1px solid ${C.borderL}`,
  color: C.text,
  fontSize: 13,
  whiteSpace: "nowrap",
};

// --- New Helper Components for Markdown Rendering ---

function SimpleMarkdown({ text, fontSize = 12.5 }) {
  if (!text) return null;
  
  // Split by double newline for paragraphs to separate distinct blocks
  const paragraphs = text.split(/\n\n+/);
  
  return (
    <div style={{ fontSize, lineHeight: 1.6, color: C.text }}>
      {paragraphs.map((para, i) => {
        const trimmed = para.trim();
        if (!trimmed) return null;

        // Check if paragraph is a header (starts with #)
        if (trimmed.startsWith('#')) {
             const match = trimmed.match(/^#+/);
             const level = match ? match[0].length : 0;
             const content = trimmed.replace(/^#+\s*/, '');
             const size = level === 1 ? fontSize + 3 : level === 2 ? fontSize + 1.5 : fontSize + 0.5;
             return <div key={i} style={{fontWeight: 700, fontSize: size, margin: '8px 0 4px', color: C.ts}}>{content}</div>;
        }
        
        // Handle lists within paragraph
        if (trimmed.includes('\n- ') || trimmed.startsWith('- ')) {
            const lines = trimmed.split('\n');
            return (
                <div key={i} style={{marginBottom: 8}}>
                    {lines.map((line, j) => {
                        const lineTrimmed = line.trim();
                        if (lineTrimmed.startsWith('- ')) {
                            return (
                                <div key={j} style={{display: 'flex', gap: 6, marginLeft: 8}}>
                                    <span style={{color: C.accent, fontWeight: "bold"}}>•</span>
                                    <span style={{flex: 1}}><FormattedText text={lineTrimmed.substring(2)} /></span>
                                </div>
                            );
                        }
                        return <div key={j}><FormattedText text={line} /></div>;
                    })}
                </div>
            );
        }

        return <div key={i} style={{marginBottom: 8, whiteSpace: "pre-wrap"}}><FormattedText text={para} /></div>;
      })}
    </div>
  );
}

function FormattedText({ text }) {
  if (!text) return null;
  // Handle bold **text**
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} style={{fontWeight: 700, color: C.ts}}>{part.slice(2, -2)}</strong>;
        }
        return part;
      })}
    </span>
  );
}
