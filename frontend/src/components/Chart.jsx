import { useState, useEffect } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { fetchChart } from "../../services/api";
import { C, F } from "../../theme";

export function Chart({ symbol, days = 30 }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchChart(symbol, days)
      .then((res) => {
        if (res?.data) {
          const formatted = res.data.map((d) => ({
            date: d.date.slice(5),
            price: d.close,
          }));
          setData(formatted);
        }
      })
      .finally(() => setLoading(false));
  }, [symbol, days]);

  if (loading || data.length === 0) return null;

  const up = data[data.length - 1].price >= data[0].price;
  const col = up ? C.up : C.dn;

  return (
    <div style={{ background: C.white, borderRadius: 12, padding: "12px 16px", border: `1px solid ${C.border}`, boxShadow: "0 1px 3px rgba(0,0,0,.04)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 600, color: C.ts, marginBottom: 4 }}>
        {symbol} · 价格走势 ({days}日)
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data} margin={{ top: 4, right: 2, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id={`g${symbol}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={col} stopOpacity={0.12} />
              <stop offset="100%" stopColor={col} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" tick={{ fill: C.td, fontSize: 9, fontFamily: F.m }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: C.td, fontSize: 9, fontFamily: F.m }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
          <Tooltip
            contentStyle={{
              background: C.white,
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              fontSize: 11,
              fontFamily: F.m,
            }}
            formatter={(v) => [`$${v.toFixed(2)}`, "价格"]}
          />
          <Area type="monotone" dataKey="price" stroke={col} strokeWidth={1.8} fill={`url(#g${symbol})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
