import { useState, useRef, useEffect, useCallback } from "react";
import { fetchChat } from "../services/api";
import { C, F } from "../theme";
import { LoadSteps, Skel } from "../components/UI/LoadingComponents";
import { StreamingText, Src, Disc } from "../components/Chat/ChatComponents";
import { Chart } from "../components/Chart";
import { InputBox } from "../components/UI/InputBox";

export const ChatPage = () => {
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [streamingText, setStreamingText] = useState("");
  const endRef = useRef(null);
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
        let trace = [];

        for (const event of events) {
          if (event.type === "model_selected") {
            setCurrentStep(0);
            trace.push(`🧠 Using ${event.model} (Complexity: ${event.complexity || 'fast'})`);
          } else if (event.type === "tool_start") {
            setCurrentStep(1);
            trace.push(`🔧 ${event.display || event.name}`);
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
            trace,
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

  const clearChat = useCallback(() => {
    setMsgs([]);
    setInput("");
    sessionId.current = `session_${Date.now()}`;
  }, []);

  const inChat = msgs.length > 0;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, overflowY: "auto", padding: inChat ? "14px 0 115px" : "0" }}>
        <div style={{ maxWidth: 740, margin: "0 auto", padding: "0 20px" }}>
          {!inChat && (
            <div style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              minHeight: "calc(100vh - 120px)",
              padding: "0 0 40px",
              animation: "fadeUp .4s ease-out",
            }}>
              <div style={{ textAlign: "center", marginBottom: 24 }}>
                <div style={{
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
                }}>
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

          {msgs.map((msg, i) => (
            <div key={i} style={{ marginBottom: 10, animation: "fadeUp .3s ease-out" }}>
              {msg.role === "user" ? (
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <div style={{
                    background: C.accent,
                    color: "#fff",
                    borderRadius: "14px 14px 4px 14px",
                    padding: "8px 14px",
                    maxWidth: "75%",
                    fontSize: 13,
                    lineHeight: 1.5,
                    boxShadow: "0 1px 3px rgba(26,110,245,.15)",
                  }}>
                    {msg.text}
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {msg.trace && msg.trace.length > 0 && (
                    <div style={{
                      fontSize: 11,
                      color: C.ts,
                      background: C.white,
                      border: `1px solid ${C.border}`,
                      padding: "8px 12px",
                      borderRadius: 8,
                      marginBottom: 4,
                      fontFamily: F.m
                    }}>
                      <div style={{ fontWeight: 600, color: C.text, marginBottom: 4 }}>💡 分析链路追踪</div>
                      {msg.trace.map((t, idx) => (
                        <div key={idx} style={{ padding: "2px 0" }}>{t}</div>
                      ))}
                    </div>
                  )}
                  <div style={{
                    background: "#FAFCFF",
                    borderRadius: 12,
                    padding: "18px 18px 14px",
                    border: `1px solid #D6E4F7`,
                    position: "relative",
                    fontSize: 13,
                    lineHeight: 1.85,
                    color: C.text,
                    whiteSpace: "pre-wrap",
                  }}>
                    <div style={{
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
                    }}>
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

      {inChat && (
        <div style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          background: "rgba(244,246,250,.92)",
          backdropFilter: "blur(12px)",
          borderTop: `1px solid ${C.border}`,
          padding: "8px 20px 12px",
        }}>
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
};
