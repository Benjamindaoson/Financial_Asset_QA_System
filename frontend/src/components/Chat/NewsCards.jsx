import { C, F } from "../../theme";

/** 格式化发布时间 */
function formatPublished(published) {
  if (!published || typeof published !== "string") return "";
  const s = published.trim();
  if (s.length <= 12) return s;
  try {
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric", year: "numeric" });
    }
  } catch (_) {}
  return s.slice(0, 10);
}

export default function NewsCards({ items = [], title = "相关新闻" }) {
  if (!items || items.length === 0) return null;

  return (
    <div
      style={{
        background: C.white,
        borderRadius: 12,
        border: `1px solid ${C.border}`,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: `1px solid ${C.border}`,
          fontSize: 12,
          fontWeight: 600,
          color: C.ts,
          fontFamily: F.s,
        }}
      >
        {title}
      </div>
      <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
        {items.map((item, index) => (
          <a
            key={index}
            href={item.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "block",
              padding: "10px 12px",
              background: "#F8FAFC",
              borderRadius: 8,
              border: "1px solid #E2E8F0",
              textDecoration: "none",
              color: C.text,
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#F1F5F9";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#F8FAFC";
            }}
          >
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                marginBottom: 4,
                color: C.accent,
                fontFamily: F.s,
              }}
            >
              {item.title || "无标题"}
            </div>
            <div
              style={{
                fontSize: 11,
                color: C.td,
                marginBottom: 6,
                fontFamily: F.s,
              }}
            >
              {item.source || "未知"} · {formatPublished(item.published)}
            </div>
            {item.snippet && (
              <div
                style={{
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: C.text,
                  fontFamily: F.s,
                }}
              >
                {item.snippet}
              </div>
            )}
          </a>
        ))}
      </div>
    </div>
  );
}
