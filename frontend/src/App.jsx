import { useCallback, useEffect, useRef, useState } from "react";
import { fetchChat, fetchChatStream, fetchMarketOverview } from "./services/api";
import { C, F } from "./theme";
import { LoadSteps, Skel } from "./components/UI/LoadingComponents";
import {
  ConfidenceBadge,
  Disc,
  ResponseBlocks,
  SourcesPanel,
  StreamingText,
} from "./components/Chat/ChatComponents";
import { Chart } from "./components/Chart";
import { InputBox } from "./components/UI/InputBox";
import { MarketOverview } from "./components/Market/MarketOverview";
import { SignalFeed } from "./components/Market/SignalFeed";
import { MarketSummary } from "./components/Market/MarketSummary";
import { SectorHeatmap } from "./components/Market/SectorHeatmap";
import { QueryTimeline } from "./components/Chat/QueryTimeline";
import { ThreeZoneLayout } from "./components/Chat/ThreeZoneLayout";
import { RAGDebugPanel } from "./components/Chat/RAGDebugPanel";

function AiMessage({ msg }) {
  const [traceOpen, setTraceOpen] = useState(false);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Query Timeline - always visible */}
      {msg.trace?.length > 0 && (
        <QueryTimeline events={msg.trace} tool_latencies={msg.tool_latencies} loading={false} />
      )}

      {/* Three-Zone Layout */}
      <ThreeZoneLayout
        blocks={msg.blocks || []}
        sources={msg.sources}
        rag_citations={msg.rag_citations}
        llm_used={msg.llm_used}
        confidence={msg.confidence}
        disclaimer={msg.disclaimer}
        fallbackText={msg.text}
        trace={msg.trace}
        symbol={msg.symbol}
        rangeKey={msg.rangeKey}
      />

      {/* Collapsible trace details + RAG Debug — 仅 URL 含 ?debug=true 时显示 */}
      {typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).get("debug") === "true" && (
        <>
          <RAGDebugPanel query={msg.query} rag_citations={msg.rag_citations} trace={msg.trace} />
          {msg.trace?.length > 0 && (
            <div style={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 10, padding: "8px 12px", marginTop: 8 }}>
              <div
                onClick={() => setTraceOpen((v) => !v)}
                style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 6, color: C.ts, fontSize: 11, fontFamily: F.m, userSelect: "none" }}
              >
                <span style={{ fontSize: 9 }}>{traceOpen ? "▼" : "▶"}</span>
                {traceOpen ? "隐藏调用详情" : "查看调用详情"}
              </div>
              {traceOpen && (
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4, fontSize: 11.5, color: C.text }}>
                  {msg.trace.map((item, i) => (
                    <div key={i} style={{ padding: "2px 0", borderBottom: `1px solid ${C.borderL}` }}>
                      {typeof item === 'string' ? item : JSON.stringify(item)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

const QUICK_PROMPTS = [
  "AAPL 近1年波动率和最大回撤",
  "比较 AAPL 和 TSLA 的 1 年表现",
  "什么是市盈率",
  "苹果最近财报和 SEC 公告",
];

export default function App() {
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [streamingText, setStreamingText] = useState("");
  const [streamingBlocks, setStreamingBlocks] = useState([]);
  const [streamingMeta, setStreamingMeta] = useState({ symbol: null, rangeKey: "1y", sources: [], llm_used: false });
  const [currentTrace, setCurrentTrace] = useState([]);
  const [marketData, setMarketData] = useState(null);
  const [loadingMarket, setLoadingMarket] = useState(true);
  const [marketError, setMarketError] = useState("");
  const endRef = useRef(null);
  const sessionId = useRef(`session_${Date.now()}`);

  useEffect(() => {
    loadMarketOverview();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, streamingText, streamingBlocks]);

  const loadMarketOverview = useCallback(async () => {
    try {
      setLoadingMarket(true);
      setMarketError("");
      const data = await fetchMarketOverview();
      setMarketData(data);
    } catch (error) {
      setMarketError("市场概览暂时不可用。");
    } finally {
      setLoadingMarket(false);
    }
  }, []);

  const send = useCallback(
    async (text) => {
      const q = (text || input).trim();
      if (!q || loading) {
        return;
      }

      setMsgs((prev) => [...prev, { role: "user", text: q }]);
      setInput("");
      setLoading(true);
      setCurrentStep(0);
      setStreamingText("");
      setStreamingBlocks([]);
      setStreamingMeta({ symbol: null, rangeKey: "1y", sources: [], llm_used: false });
      setCurrentTrace([]);

      try {
        let fullText = "";
        let sources = [];
        let symbol = null;
        let rangeKey = "1y";
        let trace = [];
        let meta = {};
        let analysisText = "";

        for await (const event of fetchChatStream(q, sessionId.current)) {
          if (event.type === "model_selected") {
            setCurrentStep(0);
            const traceEvent = { type: 'model_selected', model: event.model, timestamp: Date.now() };
            trace.push(traceEvent);
            setCurrentTrace([...trace]);
          } else if (event.type === "tool_start") {
            setCurrentStep(1);
            const traceEvent = { type: 'tool_start', name: event.name, display: event.display, timestamp: Date.now() };
            trace.push(traceEvent);
            setCurrentTrace([...trace]);
          } else if (event.type === "tool_data") {
            setCurrentStep(2);
            if (event.data?.symbol) {
              symbol = event.data.symbol;
            }
            if (event.data?.range_key) {
              rangeKey = event.data.range_key;
            }
          } else if (event.type === "chunk") {
            fullText += event.text || "";
            setStreamingText(fullText);
          } else if (event.type === "analysis_chunk") {
            analysisText += event.text || "";
            setStreamingMeta((m) => ({ ...m, llm_used: true }));
            // 只添加一条「生成分析报告」步骤，避免每个 token 都新增导致 Pipeline 铺满屏幕
            if (!trace.some((e) => e.type === "analysis_chunk")) {
              const traceEvent = { type: "analysis_chunk", timestamp: Date.now() };
              trace.push(traceEvent);
              setCurrentTrace([...trace]);
            }
            setStreamingText(fullText + "\n\n" + analysisText);
          } else if (event.type === "blocks") {
            const d = event.data || {};
            setStreamingBlocks(d.blocks || []);
            if (d.route) {
              setStreamingMeta((m) => ({
                ...m,
                symbol: d.route?.symbols?.[0] || symbol,
                rangeKey: d.route?.range_key || rangeKey,
              }));
            }
          } else if (event.type === "done") {
            sources = event.sources || [];
            meta = event.data || {};
            if (meta?.route?.range_key) {
              rangeKey = meta.route.range_key;
            }
            setStreamingMeta((m) => ({ ...m, sources }));
          }
        }

        setMsgs((prev) => [
          ...prev,
          {
            role: "ai",
            text: fullText,
            symbol,
            rangeKey,
            sources,
            trace,
            confidence: meta.confidence,
            blocks: meta.blocks || [],
            disclaimer: meta.disclaimer,
            rag_citations: meta.rag_citations || [],
            tool_latencies: meta.tool_latencies || [],
            route: meta.route,
            query: q,
            llm_used: meta.llm_used === true,
          },
        ]);
        setStreamingText("");
        setStreamingBlocks([]);
        setStreamingMeta({ symbol: null, rangeKey: "1y", sources: [], llm_used: false });
        setCurrentTrace([]);
      } catch (error) {
        setMsgs((prev) => [
          ...prev,
          { role: "ai", text: "请求失败，请检查前后端服务是否已经启动。", error: true },
        ]);
        setCurrentTrace([]);
      } finally {
        setLoading(false);
        setCurrentStep(0);
      }
    },
    [input, loading]
  );

  const goHome = useCallback(() => {
    setMsgs([]);
    setInput("");
    sessionId.current = `session_${Date.now()}`;
  }, []);

  const inChat = msgs.length > 0;

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        background: C.bg,
        fontFamily: F.s,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <style>{`
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.8); } }
        @keyframes skeleton-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 10px; }
      `}</style>

      <header
        style={{
          background: C.white,
          borderBottom: `1px solid ${C.border}`,
          padding: "0 20px",
          height: 52,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {inChat && (
            <button
              onClick={goHome}
              style={{ background: "none", border: "none", color: C.accent, cursor: "pointer", fontSize: 12.5, fontWeight: 700 }}
            >
              Home
            </button>
          )}
          <div onClick={goHome} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: `linear-gradient(135deg, ${C.accent}, #3B82F6)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontWeight: 800,
              }}
            >
              F
            </div>
            <span style={{ fontSize: 14, fontWeight: 800, color: C.text }}>FinSight AI</span>
          </div>
        </div>
        {(() => {
          const lastAi = [...msgs].reverse().find((m) => m.role === "ai");
          const routeType = lastAi?.route?.type;
          const toolNames = (lastAi?.tool_latencies || []).map((t) => t.tool);
          const marketTools = ["get_price", "get_history", "get_change", "get_info", "get_metrics", "compare_assets"];
          const hasLiveData = routeType === "market" || routeType === "hybrid" || toolNames.some((t) => marketTools.includes(t));
          if (!hasLiveData) return null;
          return (
            <span
              style={{
                fontSize: 10,
                padding: "4px 8px",
                borderRadius: 999,
                background: "#DCFCE7",
                color: "#166534",
                fontWeight: 700,
                fontFamily: F.m,
              }}
            >
              LIVE DATA
            </span>
          );
        })()}
      </header>

      <div style={{ flex: 1, overflowY: "auto", padding: inChat ? "16px 0 116px" : "22px 0" }}>
        <div style={{ maxWidth: inChat ? 820 : 1200, margin: "0 auto", padding: "0 20px" }}>
          {!inChat && (
            <div style={{ animation: "fadeUp .4s ease-out" }}>
              {loadingMarket ? (
                <div style={{ padding: "40px 0", textAlign: "center", color: C.td }}>加载市场概览中...</div>
              ) : marketError ? (
                <div style={{ padding: "20px", border: `1px solid ${C.border}`, borderRadius: 12, background: C.white }}>
                  <div style={{ color: C.text, marginBottom: 10 }}>{marketError}</div>
                  <button
                    onClick={loadMarketOverview}
                    style={{ border: "none", borderRadius: 8, padding: "8px 12px", background: C.accent, color: "#fff", cursor: "pointer" }}
                  >
                    重试
                  </button>
                </div>
              ) : marketData ? (
                <>
                  <MarketOverview indices={marketData.indices} />
                  <MarketSummary summary={marketData.summary} />
                  <SignalFeed signals={marketData.signals} />
                  <SectorHeatmap sectors={marketData.sectors} />
                </>
              ) : null}

              <div style={{ marginTop: 36, marginBottom: 20 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16, fontFamily: F.m }}>搜索与提问</h2>
                <InputBox value={input} onChange={setInput} onSend={() => send()} onClear={() => setInput("")} loading={loading} />
                <div style={{ maxWidth: 640, marginTop: 14, display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => send(prompt)}
                      style={{
                        fontSize: 11.5,
                        padding: "7px 14px",
                        borderRadius: 20,
                        border: `1px solid ${C.border}`,
                        background: C.white,
                        color: C.text,
                        cursor: "pointer",
                      }}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {msgs.map((msg, index) => (
            <div key={index} style={{ marginBottom: 12, animation: "fadeUp .3s ease-out" }}>
              {msg.role === "user" ? (
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div
                    style={{
                      background: C.accent,
                      color: "#fff",
                      borderRadius: "14px 14px 4px 14px",
                      padding: "8px 14px",
                      maxWidth: "75%",
                      fontSize: 13,
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.text}
                  </div>
                </div>
              ) : (
                <AiMessage msg={msg} />
              )}
            </div>
          ))}

          {loading && (
            <div style={{ animation: "fadeUp .3s ease-out" }}>
              {currentTrace.length > 0 && (
                <QueryTimeline events={currentTrace} loading={true} />
              )}
              {streamingBlocks.length > 0 ? (
                <ThreeZoneLayout
                  blocks={streamingBlocks}
                  sources={streamingMeta.sources}
                  rag_citations={streamingMeta.rag_citations}
                  llm_used={streamingMeta.llm_used}
                  fallbackText={streamingText}
                  trace={currentTrace}
                  symbol={streamingMeta.symbol}
                  rangeKey={streamingMeta.rangeKey}
                />
              ) : (
                <>
                  <LoadSteps currentStep={currentStep} />
                  {streamingText ? <StreamingText text={streamingText} /> : <Skel />}
                </>
              )}
            </div>
          )}

          <div ref={endRef} />
        </div>
      </div>

      {inChat && (
        <div
          style={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            background: "rgba(244,246,250,.92)",
            backdropFilter: "blur(12px)",
            borderTop: `1px solid ${C.border}`,
            padding: "8px 20px 12px",
          }}
        >
          <div style={{ maxWidth: 820, margin: "0 auto" }}>
            <InputBox value={input} onChange={setInput} onSend={() => send()} onClear={() => setInput("")} loading={loading} />
            <div style={{ textAlign: "center", marginTop: 4, fontSize: 9, color: C.td }}>
              实时行情 · 知识检索 · SEC 公告 · 风险指标　仅供参考，不构成投资建议。
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
