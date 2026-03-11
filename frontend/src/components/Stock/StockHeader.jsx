import { C, F } from "../../theme";

export function StockHeader({ stock }) {
  if (!stock) {
    return (
      <div style={{ padding: "20px", color: C.td }}>
        加载股票数据中...
      </div>
    );
  }

  const isPositive = stock.change_pct >= 0;
  const changeColor = isPositive ? "#10B981" : "#EF4444";

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "24px",
        marginBottom: 20,
      }}
    >
      {/* Stock Name and Symbol */}
      <div style={{ marginBottom: 16 }}>
        <h1
          style={{
            fontSize: 24,
            fontWeight: 800,
            color: C.text,
            marginBottom: 4,
            fontFamily: F.m,
          }}
        >
          {stock.name || stock.symbol}
        </h1>
        <div
          style={{
            fontSize: 14,
            color: C.ts,
            fontFamily: F.m,
          }}
        >
          {stock.symbol}
          {stock.exchange && (
            <span style={{ marginLeft: 8, color: C.td }}>
              · {stock.exchange}
            </span>
          )}
        </div>
      </div>

      {/* Price and Change */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 16,
          marginBottom: 20,
        }}
      >
        <div
          style={{
            fontSize: 36,
            fontWeight: 700,
            color: C.text,
            fontFamily: F.m,
          }}
        >
          ${stock.price?.toFixed(2)}
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 600,
            color: changeColor,
            fontFamily: F.m,
          }}
        >
          {isPositive ? "+" : ""}
          {stock.change_pct?.toFixed(2)}%
        </div>
        {stock.change && (
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: changeColor,
              fontFamily: F.m,
            }}
          >
            ({isPositive ? "+" : ""}${stock.change?.toFixed(2)})
          </div>
        )}
      </div>

      {/* Key Metrics Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 16,
          paddingTop: 16,
          borderTop: `1px solid ${C.border}`,
        }}
      >
        {stock.day_change_pct !== undefined && (
          <MetricItem
            label="日涨跌"
            value={`${stock.day_change_pct >= 0 ? "+" : ""}${stock.day_change_pct.toFixed(2)}%`}
            color={stock.day_change_pct >= 0 ? "#10B981" : "#EF4444"}
          />
        )}
        {stock.week_change_pct !== undefined && (
          <MetricItem
            label="7日"
            value={`${stock.week_change_pct >= 0 ? "+" : ""}${stock.week_change_pct.toFixed(2)}%`}
            color={stock.week_change_pct >= 0 ? "#10B981" : "#EF4444"}
          />
        )}
        {stock.month_change_pct !== undefined && (
          <MetricItem
            label="30日"
            value={`${stock.month_change_pct >= 0 ? "+" : ""}${stock.month_change_pct.toFixed(2)}%`}
            color={stock.month_change_pct >= 0 ? "#10B981" : "#EF4444"}
          />
        )}
        {stock.volume && (
          <MetricItem
            label="成交量"
            value={formatVolume(stock.volume)}
            color={C.text}
          />
        )}
        {stock.market_cap && (
          <MetricItem
            label="市值"
            value={formatMarketCap(stock.market_cap)}
            color={C.text}
          />
        )}
      </div>

      {/* Data Source and Timestamp */}
      <div
        style={{
          marginTop: 16,
          paddingTop: 12,
          borderTop: `1px solid ${C.border}`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ fontSize: 10, color: C.td, fontFamily: F.m }}>
          数据源: {stock.source || "N/A"}
        </div>
        {stock.timestamp && (
          <div style={{ fontSize: 10, color: C.td, fontFamily: F.m }}>
            更新于: {new Date(stock.timestamp).toLocaleString()}
          </div>
        )}
      </div>
    </div>
  );
}

function MetricItem({ label, value, color }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          color: C.td,
          marginBottom: 4,
          fontFamily: F.m,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: color,
          fontFamily: F.m,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function formatVolume(volume) {
  if (volume >= 1e9) return `${(volume / 1e9).toFixed(2)}B`;
  if (volume >= 1e6) return `${(volume / 1e6).toFixed(2)}M`;
  if (volume >= 1e3) return `${(volume / 1e3).toFixed(2)}K`;
  return volume.toLocaleString();
}

function formatMarketCap(marketCap) {
  if (marketCap >= 1e12) return `$${(marketCap / 1e12).toFixed(2)}T`;
  if (marketCap >= 1e9) return `$${(marketCap / 1e9).toFixed(2)}B`;
  if (marketCap >= 1e6) return `$${(marketCap / 1e6).toFixed(2)}M`;
  return `$${marketCap.toLocaleString()}`;
}
