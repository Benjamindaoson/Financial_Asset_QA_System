const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

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
    
    // Split on double newlines or single newlines depending on SSE format
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (let line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const dataStr = line.slice(6).trim();
          if (dataStr) {
            const data = JSON.parse(dataStr);
            events.push(data);
          }
        } catch (e) {
          console.error("Failed to parse SSE line:", line, e);
        }
      }
    }
  }

  // Handle remaining buffer if any
  if (buffer.startsWith("data: ")) {
      try {
          events.push(JSON.parse(buffer.slice(6).trim()));
      } catch (e) {}
  }


  return events;
}

export async function fetchChart(symbol, days = 30) {
  const response = await fetch(`${API_BASE}/chart/${symbol}?days=${days}`);
  if (!response.ok) return null;
  return response.json();
}
