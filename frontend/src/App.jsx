import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, fetchMarketOverview } from "./services/api";
import { C, F } from "./theme";
import { LoadSteps, Skel } from "./components/UI/LoadingComponents";
import {
  ConfidenceBadge,
  Disc,
  ResponseBlocks,
  SourcesPanel,
  StreamingText,
} from "./components/Chat/ChatComponents";
import { TechnicalIndicators } from "./components/Chat/TechnicalIndicators";
import { Chart } from "./components/Chart";
import { InputBox } from "./components/UI/InputBox";
import { MarketOverview } from "./components/Market/MarketOverview";
import { SignalFeed } from "./components/Market/SignalFeed";
import { MarketSummary } from "./components/Market/MarketSummary";
import { SectorHeatmap } from "./components/Market/SectorHeatmap";

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
  const [currentBlocks, setCurrentBlocks] = useState([]);
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
  }, [msgs, streamingText]);

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
      setCurrentBlocks([]);

      try {
        let fullText = "";
        let sources = [];
        let symbol = null;
        let rangeKey = "1y";
        let trace = [];
        let meta = {};
        let finalized = false;

        const finalize = () => {
          if (finalized) return;
          finalized = true;
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
              technicalData: meta.technicalData,
            },
          ]);
          setStreamingText("");
        };

        await streamChat(q, sessionId.current, {
          onEvent: (event) => {
          if (event.type === "model_selected") {
            setCurrentStep(0);
            trace.push(`Model: ${event.model}`);
          } else if (event.type === "tool_start") {
            setCurrentStep(1);
            trace.push(event.display || event.name);
          } else if (event.type === "tool_data") {
            setCurrentStep(2);
            if (event.data?.symbol) {
              symbol = event.data.symbol;
            }
            if (event.data?.range_key) {
              rangeKey = event.data.range_key;
            }
            // 收集技术分析数据
            if (event.tool === "get_history" && event.data?.data?.length >= 20) {
              meta.technicalData = event.data;
            }
          } else if (event.type === "blocks") { // New event to receive structured blocks immediately
            const blocksData = Array.isArray(event.data) ? event.data : [];
            meta.blocks = blocksData;
            setCurrentBlocks([...blocksData]);
          } else if (event.type === "chunk") {
            fullText += event.text || "";
            setStreamingText(fullText);
          } else if (event.type === "done") {
            sources = event.sources || [];
            meta = { ...meta, ...(event.data || {}) };
            if (meta?.route?.range_key) {
              rangeKey = meta.route.range_key;
            }
            finalize();
          }
          },
        });

        if (!finalized) {
          finalize();
        }
      } catch (error) {
        setMsgs((prev) => [
          ...prev,
          { role: "ai", text: "请求失败，请检查前后端服务是否已经启动。", error: true },
        ]);
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
              返回
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
          实时数据
        </span>
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
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div
                    style={{
                      background: "#FAFCFF",
                      borderRadius: 12,
                      padding: "18px 18px 14px",
                      border: "1px solid #D6E4F7",
                      position: "relative",
                      fontSize: 13,
                      lineHeight: 1.85,
                      color: C.text,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                      <div
                        style={{
                          position: "relative",
                          top: -9,
                          left: 0,
                          background: C.accentL,
                          color: C.accent,
                          fontSize: 9.5,
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 8,
                          border: "1px solid #BFD5F0",
                        }}
                      >
                        AI 分析
                      </div>
                      <div style={{ position: "relative", top: -10 }}>
                        <ConfidenceBadge confidence={msg.confidence} />
                      </div>
                    </div>
                    {msg.text}
                  </div>

                  <ResponseBlocks blocks={msg.blocks} />

                  {/* 技术指标展示 - 如果有历史数据 */}
                  {msg.technicalData && <TechnicalIndicators data={msg.technicalData} />}

                  {msg.symbol && !msg.blocks?.some((block) => block.type === "chart") && <Chart symbol={msg.symbol} rangeKey={msg.rangeKey} />}

                  {(msg.trace?.length || msg.sources?.length) && (
                    <div style={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 12, padding: "12px 14px" }}>
                      {msg.trace?.length > 0 && (
                        <details style={{ marginBottom: msg.sources?.length ? 12 : 0 }}>
                          <summary
                            style={{
                              cursor: "pointer",
                              listStyle: "none",
                              userSelect: "none",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 8,
                              padding: "4px 10px",
                              borderRadius: 999,
                              background: "#F8FAFC",
                              border: `1px solid ${C.border}`,
                              fontSize: 10.5,
                              fontWeight: 800,
                              color: C.ts,
                              fontFamily: F.m,
                            }}
                          >
                            调用链路
                            <span style={{ fontSize: 10, fontWeight: 700, color: C.td }}>({msg.trace.length})</span>
                            <span style={{ fontSize: 10, color: C.td }}>点击展开</span>
                          </summary>
                          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6, fontSize: 11.5, color: C.text }}>
                            {msg.trace.map((item, traceIndex) => (
                              <div key={traceIndex}>{item}</div>
                            ))}
                          </div>
                        </details>
                      )}
                      <SourcesPanel items={msg.sources} />
                    </div>
                  )}

                  <Disc text={msg.disclaimer} />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={{ animation: "fadeUp .3s ease-out" }}>
              <LoadSteps currentStep={currentStep} />
              
              {/* Show structured blocks natively even while streaming */}
              {currentBlocks.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <ResponseBlocks blocks={currentBlocks} />
                </div>
              )}
              
              {streamingText ? <StreamingText text={streamingText} /> : <Skel />}
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
