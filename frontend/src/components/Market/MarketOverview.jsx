import { C, F } from "../../theme";

export function MarketOverview({ indices }) {
  if (!indices || indices.length === 0) {
    return (
      <div style={{ padding: "20px", color: C.td }}>
        加载市场数据中...
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 32 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: C.text,
          marginBottom: 16,
          fontFamily: F.m,
        }}
      >
        市场概览
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16,
        }}
      >
        {indices.map((index) => (
          <IndexCard key={index.symbol} index={index} />
        ))}
      </div>
    </div>
  );
}

function IndexCard({ index }) {
  const isPositive = index.change_pct >= 0;
  const changeColor = isPositive ? "#10B981" : "#EF4444";

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "16px 20px",
        transition: "all 0.2s",
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: C.text,
          marginBottom: 8,
          fontFamily: F.m,
        }}
      >
        {index.name}
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 700,
          color: C.text,
          marginBottom: 4,
          fontFamily: F.m,
        }}
      >
        {index.price?.toLocaleString()}
      </div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: changeColor,
          fontFamily: F.m,
        }}
      >
        {isPositive ? "+" : ""}
        {index.change_pct?.toFixed(2)}%
      </div>
      {index.timestamp && (
        <div
          style={{
            fontSize: 10,
            color: C.td,
            marginTop: 8,
            fontFamily: F.m,
          }}
        >
          更新于: {new Date(index.timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
