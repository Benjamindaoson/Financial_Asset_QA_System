import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchChart } from "../services/api";
import { C, F } from "../theme";

const RANGE_OPTIONS = [
  { key: "ytd", label: "YTD" },
  { key: "1y", label: "1Y" },
  { key: "5y", label: "5Y" },
];

const COMPARE_COLORS = ["#1A6EF5", "#D97706", "#0D9B53", "#D93A3A"];

export function Chart({ symbol, rangeKey = "1y", embeddedSeries = null, chartType = "history" }) {
  const [activeRange, setActiveRange] = useState(rangeKey);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(!embeddedSeries);

  useEffect(() => {
    setActiveRange(rangeKey);
  }, [rangeKey]);

  useEffect(() => {
    if (embeddedSeries) {
      setData(formatEmbeddedSeries(embeddedSeries, chartType));
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetchChart(symbol, { rangeKey: activeRange })
      .then((res) => {
        if (cancelled || !res?.data) {
          return;
        }
        setData(
          res.data.map((point) => ({
            date: point.date.slice(5),
            price: point.close,
          }))
        );
      })
      .catch(() => {
        if (!cancelled) {
          setData([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, activeRange, embeddedSeries, chartType]);

  const comparisonKeys = useMemo(() => {
    if (chartType !== "comparison" || data.length === 0) {
      return [];
    }
    return Object.keys(data[0]).filter((key) => key !== "date");
  }, [chartType, data]);

  if (loading) {
    return (
      <div style={boxStyle}>
        <div style={titleStyle}>{symbol || "图表"} 价格走势</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={skeletonLine} />
          <div style={{ ...skeletonLine, width: "95%" }} />
          <div style={{ ...skeletonLine, width: "98%" }} />
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return null;
  }

  return (
    <div style={boxStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 12 }}>
        <div style={titleStyle}>
          {chartType === "comparison" ? "归一化对比图" : `${symbol} 价格走势`}
        </div>
        {!embeddedSeries && (
          <div style={{ display: "flex", gap: 6 }}>
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.key}
                onClick={() => setActiveRange(option.key)}
                style={{
                  border: `1px solid ${activeRange === option.key ? C.accent : C.border}`,
                  background: activeRange === option.key ? C.accentL : C.white,
                  color: activeRange === option.key ? C.accent : C.ts,
                  borderRadius: 999,
                  padding: "4px 10px",
                  fontSize: 10.5,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={220}>
        {chartType === "comparison" ? (
          <LineChart data={data} margin={{ top: 8, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke={C.borderL} strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: C.td, fontSize: 10, fontFamily: F.m }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: C.td, fontSize: 10, fontFamily: F.m }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 11, fontFamily: F.m }}
              formatter={(value) => [`${value.toFixed(2)}`, "归一化"]}
            />
            <Legend />
            {comparisonKeys.map((key, index) => (
              <Line key={key} type="monotone" dataKey={key} dot={false} stroke={COMPARE_COLORS[index % COMPARE_COLORS.length]} strokeWidth={2} />
            ))}
          </LineChart>
        ) : (
          <AreaChart data={data} margin={{ top: 8, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id={`g-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.accent} stopOpacity={0.18} />
                <stop offset="100%" stopColor={C.accent} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={C.borderL} strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: C.td, fontSize: 10, fontFamily: F.m }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: C.td, fontSize: 10, fontFamily: F.m }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 11, fontFamily: F.m }}
              formatter={(value) => [`$${value.toFixed(2)}`, "价格"]}
            />
            <Area type="monotone" dataKey="price" stroke={C.accent} strokeWidth={2} fill={`url(#g-${symbol})`} dot={false} />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function formatEmbeddedSeries(series, chartType) {
  if (chartType === "comparison") {
    return series.map((point) => ({ date: point.date.slice(5), ...point.values }));
  }
  return series.map((point) => ({ date: point.date.slice(5), price: point.close }));
}

const boxStyle = {
  background: C.white,
  borderRadius: 12,
  padding: "14px 16px",
  border: `1px solid ${C.border}`,
  boxShadow: "0 1px 3px rgba(0,0,0,.04)",
};

const titleStyle = {
  fontSize: 11.5,
  fontWeight: 700,
  color: C.ts,
  fontFamily: F.m,
};

const skeletonLine = {
  width: "100%",
  height: 12,
  background: C.sk,
  borderRadius: 4,
};
