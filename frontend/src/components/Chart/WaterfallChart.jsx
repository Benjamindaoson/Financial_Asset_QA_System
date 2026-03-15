/**
 * 瀑布图 — 用于展示递推计算（如 100亿→扣成本→扣费用→12亿）
 * @param {Array<{label: string, value: number}>} steps - 步骤数组，value 可为正（增加）或负（减少）
 */
import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { C, F } from "../../theme";

export function WaterfallChart({ steps = [] }) {
  if (!steps?.length) return null;

  let running = 0;
  const data = steps.map((s, i) => {
    const prev = running;
    running += s.value;
    return {
      label: s.label,
      value: s.value,
      start: prev,
      end: running,
      isTotal: i === steps.length - 1 && steps.length > 1,
    };
  });

  return (
    <div style={{ padding: "12px 0", minHeight: 180 }}>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 8 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" width={80} tick={{ fontSize: 11, fontFamily: F.m }} />
          <Bar dataKey="value" isAnimationActive={false}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.isTotal ? C.accent : entry.value >= 0 ? "#86EFAC" : "#FCA5A5"}
                stroke={entry.isTotal ? C.accent : "transparent"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
