import { useState, useRef, useEffect, useCallback } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

/* ================================================================
   API SERVICE
   ================================================================ */
const API_BASE = "http://localhost:8000/api";

async function fetchChat(query, sessionId = null) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
  });

  if (!response.ok) throw new Error("API request failed");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const events = [];
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          events.push(data);
        } catch (e) {
          console.error("Failed to parse SSE:", e);
        }
      }
    }
  }

  return events;
}

async function fetchChart(symbol, days = 30) {
  const response = await fetch(`${API_BASE}/chart/${symbol}?days=${days}`);
  if (!response.ok) return null;
  return response.json();
}

/* ================================================================
   TOKENS
   ================================================================ */
const C = {
  bg: "#F4F6FA",
  white: "#FFFFFF",
  border: "#E3E8F0",
  borderL: "#EEF1F6",
  text: "#1A2332",
  ts: "#5A6B80",
  td: "#94A3B8",
  accent: "#1A6EF5",
  accentL: "#EBF3FE",
  up: "#D93A3A",
  upL: "rgba(217,58,58,.08)",
  dn: "#0D9B53",
  dnL: "rgba(13,155,83,.08)",
  warn: "#D97706",
  warnBg: "#FFFBEB",
  purple: "#7C3AED",
  purpleL: "#F3EFFE",
  sk: "#E6EAF0",
};
const F = {
  s: "'PingFang SC','Helvetica Neue',system-ui,sans-serif",
  m: "'JetBrains Mono','SF Mono',monospace",
};
const cc = (v) => (v >= 0 ? C.up : C.dn);

/* ================================================================
   TINY COMPONENTS
   ================================================================ */
function LoadSteps({ currentStep }) {
  const steps = ["识别问题类型...", "获取市场数据...", "生成分析报告..."];
  return (
    <div style={{ padding: "10px 0" }}>
      {steps.map((t, i) => (
        <div
          key={i}
          style={{
            fontSize: 12,
            color: i <= currentStep ? C.accent : C.td,
            display: "flex",
            alignItems: "center",
            gap: 5,
            marginBottom: 3,
            opacity: i <= currentStep ? 1 : 0.4,
            transition: "all .3s",
          }}
        >
          {i < currentStep ? (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : i === currentStep ? (
            <span style={{ width: 13, height: 13, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: C.accent,
                  animation: "pls 1s infinite",
                }}
              />
            </span>
          ) : (
            <span style={{ width: 13, height: 13, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ width: 4, height: 4, borderRadius: "50%", background: C.td }} />
            </span>
          )}
          {t}
        </div>
      ))}
    </div>
  );
}

function Skel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ background: C.white, borderRadius: 12, padding: 18, border: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div>
            <div style={{ width: 55, height: 12, background: C.sk, borderRadius: 4, marginBottom: 7 }} />
            <div style={{ width: 90, height: 16, background: C.sk, borderRadius: 4 }} />
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ width: 80, height: 22, background: C.sk, borderRadius: 4, marginBottom: 5 }} />
            <div style={{ width: 50, height: 10, background: C.sk, borderRadius: 4, marginLeft: "auto" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   ANSWER COMPONENTS
   ================================================================ */
function StreamingText({ text }) {
  return (
    <div
      style={{
        background: "#FAFCFF",
        borderRadius: 12,
        padding: "18px 18px 14px",
        border: `1px solid #D6E4F7`,
        position: "relative",
        fontSize: 13,
        lineHeight: 1.85,
        color: C.text,
        whiteSpace: "pre-wrap",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: -9,
          left: 12,
          background: C.accentL,
          color: C.accent,
          fontSize: 9.5,
          fontWeight: 700,
          padding: "2px 8px",
          borderRadius: 8,
          border: `1px solid #BFD5F0`,
        }}
      >
        AI 分析
      </div>
      {text}
      <span
        style={{
          display: "inline-block",
          width: 6,
          height: 12,
          background: C.accent,
          marginLeft: 2,
          animation: "blink 1s infinite",
        }}
      />
    </div>
  );
}

function Chart({ symbol, days = 30 }) {
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

function Src({ items }) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {items.map((s, i) => (
        <span
          key={i}
          style={{
            fontSize: 9.5,
            padding: "3px 8px",
            borderRadius: 10,
            background: C.bg,
            border: `1px solid ${C.border}`,
            color: C.ts,
            fontFamily: F.m,
          }}
        >
          <span style={{ color: C.accent, marginRight: 2 }}>●</span>
          {s.name}
        </span>
      ))}
    </div>
  );
}

function Disc() {
  return (
    <div
      style={{
        fontSize: 10.5,
        color: C.warn,
        padding: "7px 11px",
        background: C.warnBg,
        borderRadius: 7,
        borderLeft: `3px solid ${C.warn}`,
        lineHeight: 1.5,
      }}
    >
      ⚠️ 行情数据来自公开API，AI分析仅供参考，不构成投资建议。
    </div>
  );
}

/* ================================================================
   INPUT BOX
   ================================================================ */
function InputBox({ value, onChange, onSend, onClear, loading }) {
  return (
    <div style={{ maxWidth: 740, width: "100%", margin: "0 auto" }}>
      <div
        style={{
          background: C.white,
          borderRadius: 14,
          border: `1px solid ${C.border}`,
          boxShadow: "0 2px 8px rgba(0,0,0,.04)",
          overflow: "hidden",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", padding: "4px 5px 4px 16px", gap: 6 }}>
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && onSend()}
            placeholder="输入股票名称、代码或金融问题，如「苹果股票」「什么是市盈率」..."
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: C.text,
              fontSize: 13.5,
              fontFamily: F.s,
              padding: "9px 0",
            }}
          />
          {value && (
            <button
              onClick={onClear}
              style={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                border: "none",
                background: C.bg,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={C.ts} strokeWidth="3" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}
          <button
            onClick={onSend}
            disabled={!value?.trim() || loading}
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              border: "none",
              background: value?.trim() && !loading ? `linear-gradient(135deg,${C.accent},#3B82F6)` : C.bg,
              cursor: value?.trim() && !loading ? "pointer" : "default",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: value?.trim() && !loading ? 1 : 0.35,
            }}
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke={value?.trim() && !loading ? "#fff" : C.td}
              strokeWidth="2.5"
              strokeLinecap="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   MAIN APP
   ================================================================ */
export default function App() {
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [streamingText, setStreamingText] = useState("");
  const endRef = useRef(null);
  const scrollRef = useRef(null);
  const sessionId = useRef(`session_${Date.now()}`);

  useEffect(() => {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  }, [msgs, streamingText]);

  const send = useCallback(
    async (text) => {
      const q = (text || input).trim();
      if (!q || loading) return;

      setMsgs((p) => [...p, { role: "user", text: q }]);
      setInput("");
      setLoading(true);
      setCurrentStep(0);
      setStreamingText("");

      try {
        const events = await fetchChat(q, sessionId.current);
        let fullText = "";
        let symbol = null;
        let sources = [];

        for (const event of events) {
          if (event.type === "model_selected") {
            setCurrentStep(0);
          } else if (event.type === "tool_start") {
            setCurrentStep(1);
          } else if (event.type === "tool_data") {
            setCurrentStep(2);
            if (event.data?.symbol) {
              symbol = event.data.symbol;
            }
          } else if (event.type === "chunk") {
            fullText += event.text;
            setStreamingText(fullText);
          } else if (event.type === "done") {
            if (event.sources) {
              sources = event.sources;
            }
          }
        }

        setMsgs((p) => [
          ...p,
          {
            role: "ai",
            text: fullText,
            symbol,
            sources,
          },
        ]);
        setStreamingText("");
      } catch (error) {
        console.error("Chat error:", error);
        setMsgs((p) => [
          ...p,
          {
            role: "ai",
            text: "抱歉，请求失败。请检查后端服务是否正常运行。",
            error: true,
          },
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
        @keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        @keyframes pls{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}
        @keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:4px}
        ::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:10px}
        input::placeholder{color:${C.td}}
      `}</style>

      {/* HEADER */}
      <header
        style={{
          background: C.white,
          borderBottom: `1px solid ${C.border}`,
          padding: "0 20px",
          height: 48,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {inChat && (
            <button
              onClick={goHome}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.accent,
                fontSize: 11.5,
                fontWeight: 600,
                padding: "4px 6px",
                borderRadius: 5,
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
              首页
            </button>
          )}
          <div onClick={goHome} style={{ display: "flex", alignItems: "center", gap: 7, cursor: "pointer" }}>
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: 6,
                background: `linear-gradient(135deg,${C.accent},#3B82F6)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
                fontWeight: 900,
                color: "#fff",
              }}
            >
              F
            </div>
            <span style={{ fontSize: 14, fontWeight: 800, color: C.text }}>FinSight AI</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {inChat && (
            <button
              onClick={goHome}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                background: C.bg,
                border: `1px solid ${C.border}`,
                cursor: "pointer",
                color: C.ts,
                fontSize: 10.5,
                fontWeight: 600,
                padding: "4px 9px",
                borderRadius: 5,
              }}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              新对话
            </button>
          )}
          <span
            style={{
              fontSize: 9.5,
              padding: "3px 6px",
              borderRadius: 3,
              background: C.upL,
              color: C.up,
              fontWeight: 700,
              fontFamily: F.m,
            }}
          >
            ● LIVE
          </span>
        </div>
      </header>

      {/* CONTENT */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: inChat ? "14px 0 115px" : "0" }}>
        <div style={{ maxWidth: 740, margin: "0 auto", padding: "0 20px" }}>
          {/* HOME */}
          {!inChat && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                minHeight: "calc(100vh - 48px)",
                padding: "0 0 40px",
                animation: "fadeUp .4s ease-out",
              }}
            >
              <div style={{ textAlign: "center", marginBottom: 24 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 12,
                    margin: "0 auto 12px",
                    background: `linear-gradient(135deg,${C.accent},#6366f1)`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 20,
                    fontWeight: 900,
                    color: "#fff",
                    boxShadow: "0 4px 16px rgba(26,110,245,.18)",
                  }}
                >
                  F
                </div>
                <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text, marginBottom: 4 }}>金融资产智能问答</h1>
                <p style={{ fontSize: 13, color: C.ts }}>实时行情查询 · 涨跌原因分析 · 金融知识问答</p>
              </div>

              <InputBox value={input} onChange={setInput} onSend={() => send()} onClear={() => setInput("")} loading={loading} />

              <div style={{ maxWidth: 580, margin: "14px auto 0", display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
                {["苹果股票今天涨了多少", "特斯拉最近走势", "什么是市盈率", "阿里巴巴行情"].map((q, i) => (
                  <button
                    key={i}
                    onClick={() => send(q)}
                    style={{
                      fontSize: 11.5,
                      padding: "6px 14px",
                      borderRadius: 18,
                      border: `1px solid ${C.border}`,
                      background: C.white,
                      color: C.text,
                      cursor: "pointer",
                      transition: "all .15s",
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* MESSAGES */}
          {msgs.map((msg, i) => (
            <div key={i} style={{ marginBottom: 10, animation: "fadeUp .3s ease-out" }}>
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
                      boxShadow: "0 1px 3px rgba(26,110,245,.15)",
                    }}
                  >
                    {msg.text}
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  <div
                    style={{
                      background: "#FAFCFF",
                      borderRadius: 12,
                      padding: "18px 18px 14px",
                      border: `1px solid #D6E4F7`,
                      position: "relative",
                      fontSize: 13,
                      lineHeight: 1.85,
                      color: C.text,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: -9,
                        left: 12,
                        background: C.accentL,
                        color: C.accent,
                        fontSize: 9.5,
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 8,
                        border: `1px solid #BFD5F0`,
                      }}
                    >
                      AI 分析
                    </div>
                    {msg.text}
                  </div>
                  {msg.symbol && <Chart symbol={msg.symbol} days={30} />}
                  {msg.sources && msg.sources.length > 0 && <Src items={msg.sources} />}
                  <Disc />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={{ animation: "fadeUp .3s ease-out" }}>
              <LoadSteps currentStep={currentStep} />
              {streamingText ? <StreamingText text={streamingText} /> : <Skel />}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* BOTTOM INPUT */}
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
          <div style={{ maxWidth: 740, margin: "0 auto" }}>
            <InputBox value={input} onChange={setInput} onSend={() => send()} onClear={() => setInput("")} loading={loading} />
            <div style={{ textAlign: "center", marginTop: 4, fontSize: 9, color: C.td }}>
              FinSight AI · 数据来自 Yahoo Finance · AI分析不构成投资建议
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
