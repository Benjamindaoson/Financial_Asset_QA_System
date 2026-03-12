const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://127.0.0.1:8001/api" : "/api")
).replace(/\/$/, "");

export async function fetchChat(query, sessionId = null) {
  const events = [];
  await streamChat(query, sessionId, {
    onEvent: (event) => {
      events.push(event);
    },
  });
  return events;
}

export async function streamChat(query, sessionId = null, options = {}) {
  const { onEvent, signal } = options;
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
    signal,
  });

  if (!response.ok) throw new Error("API request failed");
  if (!response.body) throw new Error("Streaming not supported");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      if (!line.startsWith("data:")) continue;

      const dataStr = line.slice(5).trim();
      if (!dataStr || dataStr === "[DONE]") continue;

      try {
        const data = JSON.parse(dataStr);
        onEvent?.(data);
      } catch (e) {
        console.error("Failed to parse SSE line:", line, e);
      }
    }
  }

  const tail = buffer.trim();
  if (tail.startsWith("data:")) {
    const dataStr = tail.slice(5).trim();
    if (dataStr && dataStr !== "[DONE]") {
      try {
        onEvent?.(JSON.parse(dataStr));
      } catch (e) {}
    }
  }
}

export async function fetchChart(symbol, options = {}) {
  const params = new URLSearchParams();
  if (options.rangeKey) {
    params.set("range_key", options.rangeKey);
  } else {
    params.set("days", String(options.days || 30));
  }
  const response = await fetch(`${API_BASE}/chart/${symbol}?${params.toString()}`);
  if (!response.ok) return null;
  return response.json();
}

export async function fetchMarketOverview() {
  const response = await fetch(`${API_BASE}/market-overview`);
  if (!response.ok) throw new Error("Failed to fetch market overview");
  return response.json();
}
