import { C, F } from "../../theme";

export function NewsTimeline({ news }) {
  if (!news || news.length === 0) {
    return null;
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: C.text,
          marginBottom: 16,
          fontFamily: F.m,
        }}
      >
        NEWS & EVENTS
      </h2>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {news.map((item, idx) => (
          <NewsItem key={idx} news={item} />
        ))}
      </div>
    </div>
  );
}

function NewsItem({ news }) {
  const timeAgo = getTimeAgo(news.timestamp);

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "16px",
        transition: "all 0.2s",
        cursor: news.url ? "pointer" : "default",
      }}
      onClick={() => {
        if (news.url) {
          window.open(news.url, "_blank");
        }
      }}
      onMouseEnter={(e) => {
        if (news.url) {
          e.currentTarget.style.borderColor = C.accent;
          e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = C.border;
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      {/* Timestamp */}
      <div
        style={{
          fontSize: 10,
          color: C.td,
          marginBottom: 6,
          fontFamily: F.m,
        }}
      >
        {timeAgo}
        {news.source && (
          <span style={{ marginLeft: 8 }}>· {news.source}</span>
        )}
      </div>

      {/* Title */}
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: C.text,
          marginBottom: 6,
          lineHeight: 1.5,
          fontFamily: F.m,
        }}
      >
        {news.title}
      </div>

      {/* Summary */}
      {news.summary && (
        <div
          style={{
            fontSize: 13,
            color: C.ts,
            lineHeight: 1.6,
            fontFamily: F.m,
          }}
        >
          {news.summary}
        </div>
      )}

      {/* Tags */}
      {news.tags && news.tags.length > 0 && (
        <div
          style={{
            marginTop: 10,
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
          }}
        >
          {news.tags.map((tag, idx) => (
            <span
              key={idx}
              style={{
                fontSize: 10,
                padding: "2px 8px",
                borderRadius: 4,
                background: C.bg,
                border: `1px solid ${C.border}`,
                color: C.ts,
                fontFamily: F.m,
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function getTimeAgo(timestamp) {
  if (!timestamp) return "";

  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now - time;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;

  return time.toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
  });
}
