import { C, F } from "../../theme";

export function InputBox({ value, onChange, onSend, onClear, loading }) {
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
            placeholder="输入代码或提问，如：AAPL 最大回撤"
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
