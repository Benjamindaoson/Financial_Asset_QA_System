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

function Block({ block }) {
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
    return <Chart symbol={symbol} chartType={chartType} embeddedSeries={series} rangeKey={block.data?.range_key || "1y"} />;
  }

  if (block.type === "quote") {
    return (
      <div style={{ ...panelStyle, background: "#FAFCFF", borderColor: "#D6E4F7" }}>
        <div style={panelTitleStyle}>{block.title}</div>
        <div style={{ fontSize: 12.5, lineHeight: 1.8, whiteSpace: "pre-wrap", color: C.text }}>{block.data?.text}</div>
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

  return null;
}

export function ConfidenceBadge({ confidence }) {
  if (!confidence) {
    return null;
  }

  const palette = {
    high: { bg: "#DCFCE7", color: "#166534" },
    medium: { bg: "#FEF3C7", color: "#92400E" },
    low: { bg: "#FEE2E2", color: "#991B1B" },
  };
  const style = palette[confidence.level] || palette.medium;

  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        borderRadius: 999,
        padding: "4px 8px",
        background: style.bg,
        color: style.color,
        fontFamily: F.m,
      }}
    >
      置信度 {confidence.score}
    </span>
  );
}

export function SourcesPanel({ items = [] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((source, index) => (
        <div
          key={`${source.name}-${source.timestamp}-${index}`}
          style={{
            fontSize: 10.5,
            padding: "6px 8px",
            borderRadius: 8,
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
              查看来源
            </a>
          )}
        </div>
      ))}
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
