/**
 * 价格卡片 — 展示当前价格、涨跌幅、OHLCV
 * @param {Object} props
 * @param {Object} props.block - key_metrics 类型 block，含 data: { price, change_pct, open, high, low, volume, ... }
 */
import { C, F } from "../../theme";

const PriceCard = ({ block }) => {
  const d = block?.data || {};
  const isUp = (d.change_pct ?? d.change ?? 0) >= 0;
  const changeColor = isUp ? "#16a34a" : "#dc2626";
  const arrow = isUp ? "▲" : "▼";
  const hasPeriodChange = d.change_pct != null;
  const hasOHLCV = d.open != null || d.high != null || d.low != null || d.volume != null;

  return (
    <div style={{ padding: "12px 16px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: "1.8rem", fontWeight: 700, color: C.text, fontFamily: F.m, letterSpacing: "-0.5px" }}>
          {d.currency && d.currency !== "USD" ? d.currency + " " : "$"}
          {d.price != null ? d.price.toFixed(2) : (d.end_price != null ? d.end_price.toFixed(2) : "—")}
        </span>
        {hasPeriodChange && (
          <span style={{ fontSize: "1rem", color: changeColor, fontWeight: 600 }}>
            {arrow}{" "}
            {d.change != null ? `${d.change > 0 ? "+" : ""}${d.change.toFixed(2)} ` : ""}
            ({parseInt(d.change_pct) > 0 ? "+" : ""}{d.change_pct.toFixed(2)}%)
          </span>
        )}
      </div>
      {hasOHLCV && (
        <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: "0.85rem", color: "#6b7280", flexWrap: "wrap" }}>
          {d.open != null && <span>开 {d.open.toFixed(2)}</span>}
          {d.high != null && <span>高 {d.high.toFixed(2)}</span>}
          {d.low != null && <span>低 {d.low.toFixed(2)}</span>}
          {d.volume != null && <span>量 {(d.volume / 1e6).toFixed(1)}M</span>}
        </div>
      )}
    </div>
  );
};

export default PriceCard;
