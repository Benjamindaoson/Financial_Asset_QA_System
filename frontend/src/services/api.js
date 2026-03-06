const API_BASE = "http://localhost:8000/api";

export async function fetchChat(query, sessionId = null) {
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

export async function fetchChart(symbol, days = 30) {
  const response = await fetch(`${API_BASE}/chart/${symbol}?days=${days}`);
  if (!response.ok) return null;
  return response.json();
}
