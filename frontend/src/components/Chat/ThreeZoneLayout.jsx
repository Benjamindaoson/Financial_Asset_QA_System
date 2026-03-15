import { Chart } from "../Chart";
import { ResponseBlocks, SourcesPanel, Disc } from "./ChatComponents";
import { C, F } from "../../theme";

// Priority order for rendering blocks
// 1. key_metrics  — price card (top)
// 2. chart        — price chart
// 3. analysis / bullets / warning / news / table  — AI analysis (default expanded)
// 4. quote        — reference excerpts (collapsible, bottom)
const ZONE_PRICE = ['key_metrics'];
const ZONE_CHART = ['chart'];
const ZONE_ANALYSIS = ['analysis', 'bullets', 'warning', 'news', 'table'];
const ZONE_REFS = ['quote'];

export function ThreeZoneLayout({ blocks = [], sources = [], rag_citations = [], llm_used = false, confidence, disclaimer, fallbackText, trace, symbol, rangeKey }) {
  const priceBlocks    = blocks.filter(b => ZONE_PRICE.includes(b.type));
  const chartBlocks    = blocks.filter(b => ZONE_CHART.includes(b.type));
  const analysisBlocks = blocks.filter(b => ZONE_ANALYSIS.includes(b.type));
  const refBlocks      = blocks.filter(b => ZONE_REFS.includes(b.type));

  // 兜底：从 key_metrics 取 symbol（当 stream 未传时）
  const effectiveSymbol = symbol || priceBlocks[0]?.data?.symbol;

  const unknownBlocks = blocks.filter(b =>
    !ZONE_PRICE.includes(b.type) &&
    !ZONE_CHART.includes(b.type) &&
    !ZONE_ANALYSIS.includes(b.type) &&
    !ZONE_REFS.includes(b.type)
  );

  if (unknownBlocks.length > 0) {
    console.warn('[ThreeZoneLayout] Unknown block types:', unknownBlocks.map(b => b.type));
  }

  const hasMainContent = analysisBlocks.length > 0 || priceBlocks.length > 0 || fallbackText;

  if (!hasMainContent) {
    return (
      <div style={{
        padding: '16px',
        background: C.warnBg,
        border: `1px solid #FCD34D`,
        borderRadius: 12,
        color: C.text,
        fontSize: 13
      }}>
        分析生成失败，请重试。
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 1. Price card */}
      {priceBlocks.length > 0 && (
        <div style={{
          background: C.white,
          borderRadius: 12,
          border: `1px solid ${C.border}`,
          overflow: 'hidden'
        }}>
          <ResponseBlocks blocks={priceBlocks} />
        </div>
      )}

      {/* 2a. 走势概述指标卡片（至少 2 个时显示，避免单卡片残片感） */}
      {priceBlocks.length > 0 && (() => {
        const km = priceBlocks[0]?.data || {};
        // 兜底：从 chart series 计算 period_high/low/change_pct（当后端未传时）
        let periodHigh = km.period_high;
        let periodLow = km.period_low;
        let changePct = km.change_pct;
        let periodAmplitudePct = km.period_amplitude_pct;
        let periodDays = km.period_days || 7;
        if ((periodHigh == null || periodLow == null || changePct == null) && chartBlocks.length > 0) {
          const series = chartBlocks[0]?.data?.series || [];
          if (series.length >= 2) {
            const highs = series.map((p) => p.high ?? p.close).filter((v) => v != null);
            const lows = series.map((p) => p.low ?? p.close).filter((v) => v != null);
            const startPrice = series[0]?.close ?? series[0]?.open;
            const endPrice = series[series.length - 1]?.close ?? series[series.length - 1]?.open;
            if (highs.length && lows.length) {
              if (periodHigh == null) periodHigh = Math.max(...highs);
              if (periodLow == null) periodLow = Math.min(...lows);
              if (periodLow > 0 && periodAmplitudePct == null) {
                periodAmplitudePct = Math.round((periodHigh - periodLow) / periodLow * 10000) / 100;
              }
            }
            if (changePct == null && startPrice != null && endPrice != null && startPrice > 0) {
              changePct = Math.round((endPrice - startPrice) / startPrice * 10000) / 100;
            }
            periodDays = series.length;
          }
        }
        const cards = [];
        if (periodHigh != null) cards.push({ label: `${periodDays}日最高`, value: Number(periodHigh).toFixed(2), color: null });
        if (periodLow != null) cards.push({ label: `${periodDays}日最低`, value: Number(periodLow).toFixed(2), color: null });
        if (periodAmplitudePct != null) cards.push({ label: "区间振幅", value: `${periodAmplitudePct}%`, color: null });
        if (changePct != null) cards.push({ label: "累计涨跌", value: `${changePct >= 0 ? "+" : ""}${Number(changePct).toFixed(2)}%`, color: changePct >= 0 ? "#16a34a" : "#dc2626" });
        if (cards.length < 2) return null;
        return (
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${cards.length}, 1fr)`,
            gap: 10,
            width: "100%",
          }}>
            {cards.map((c, i) => (
              <div key={i} style={{ background: "#F8FAFC", borderRadius: 10, padding: "10px 14px", border: "1px solid #E2E8F0", textAlign: "center" }}>
                <div style={{ fontSize: 10, color: "#64748b", marginBottom: 4, fontFamily: F.m }}>{c.label}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: c.color || C.text, fontFamily: F.m }}>{c.value}</div>
              </div>
            ))}
          </div>
        );
      })()}

      {/* 2b. Price chart — 后端有则用，无则用 symbol 兜底拉取 */}
      {chartBlocks.length > 0 ? (
        <ResponseBlocks blocks={chartBlocks} />
      ) : (effectiveSymbol && (priceBlocks.length > 0 || analysisBlocks.length > 0)) ? (
        <Chart
          symbol={effectiveSymbol}
          rangeKey={rangeKey || "1y"}
          chartType="history"
        />
      ) : null}

      {/* 3. AI Analysis — always expanded by default */}
      {analysisBlocks.length > 0 ? (
        <ResponseBlocks blocks={analysisBlocks} />
      ) : fallbackText ? (
        (() => {
          const isRagOnly = !llm_used && (refBlocks.length > 0 || (rag_citations && rag_citations.length > 0));
          const badgeLabel = isRagOnly ? "知识库" : "AI 分析";
          const badgeBg = isRagOnly ? "#E0F2FE" : C.accentL;
          const badgeColor = isRagOnly ? "#0369A1" : C.accent;
          const badgeBorder = isRagOnly ? "#BAE6FD" : "#BFD5F0";
          return (
            <div style={{
              background: "#FAFCFF",
              borderRadius: 12,
              padding: "18px 18px 14px",
              border: "1px solid #D6E4F7",
              position: "relative",
              fontSize: 14,
              lineHeight: 1.85,
              color: C.text,
              whiteSpace: "pre-wrap",
            }}>
              <div style={{
                position: "absolute",
                top: -9,
                left: 12,
                background: badgeBg,
                color: badgeColor,
                fontSize: 9.5,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 8,
                border: `1px solid ${badgeBorder}`,
              }}>
                {badgeLabel}
              </div>
              {fallbackText}
            </div>
          );
        })()
      ) : null}

      {/* 4. Reference excerpts (knowledge base) — collapsible, at bottom */}
      {refBlocks.length > 0 && (
        <ResponseBlocks blocks={refBlocks} />
      )}

      {/* 5. Data source attribution */}
      {(sources?.length > 0 || rag_citations?.length > 0) && (
        <SourcesPanel items={sources || []} rag_citations={rag_citations} />
      )}

      <Disc text={disclaimer || "以上内容仅供参考，不构成投资建议。"} />
    </div>
  );
}
