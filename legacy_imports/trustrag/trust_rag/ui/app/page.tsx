"use client";

import { useState, useRef } from "react";

// Types aligned with backend SystemResult
type VerdictStatus = "VERIFIED" | "REFUSED" | "CONFLICT";

interface Answer {
  text: string;
  confidence: number;
}

interface EvidenceItem {
  metric: string;
  value: string;
  source: string;
  page: number;
}

interface SystemResult {
  verdict: VerdictStatus;
  answer?: Answer;
  evidence: EvidenceItem[];
  trace_id: string;
  reasons?: string[];
  risk_flags?: Record<string, boolean>;
  disclosure_required?: boolean;
  verification_data?: Record<string, unknown>;
}

interface QueryHistory {
  query: string;
  result: SystemResult;
  timestamp: string;
  query_id: string;
}

interface IngestResult {
  doc_id: string;
  status: string;
  chunks_count: number;
  errors: string[];
  message: string;
}

interface IndexStats {
  total_chunks: number;
  documents_loaded: number;
  documents: string[];
  chunks_by_tier: Record<string, number>;
}

// Demo example queries
const DEMO_QUERIES = [
  "What was Nvidia's revenue for FY2023?",
  "Calculate Nvidia's net profit margin for FY2023",
  "What was Nvidia's gross profit in Q3 2024?",
  "Compare Apple and Microsoft revenue growth",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SystemResult | null>(null);
  const [copied, setCopied] = useState(false);
  
  // Document upload state
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<IngestResult | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Stats state
  const [stats, setStats] = useState<IndexStats | null>(null);
  const [showStats, setShowStats] = useState(false);
  
  // Evidence chain visualization
  const [showEvidenceSidebar, setShowEvidenceSidebar] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  
  // Query history
  const [queryHistory, setQueryHistory] = useState<QueryHistory[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleQuery = async (q: string) => {
    if (!q.trim()) return;
    
    setQuery(q);
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, risk_level: "medium" }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.detail || errorData.detail || `API error: ${response.status}`);
      }
      
      const data: SystemResult = await response.json();
      setResult(data);
      
      // Add to history
      const queryId = `q_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const historyEntry: QueryHistory = {
        query: q,
        result: data,
        timestamp: new Date().toISOString(),
        query_id: queryId
      };
      setQueryHistory(prev => [historyEntry, ...prev].slice(0, 50)); // Keep last 50
    } catch (error) {
      console.error("Query failed:", error);
      const errorMessage = error instanceof Error ? error.message : "Unknown error occurred";
      setResult({
        verdict: "REFUSED",
        trace_id: `err_${Date.now()}`,
        reasons: [errorMessage],
        evidence: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("profile", "generic");

      const response = await fetch(`${apiUrl}/api/ingest`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.detail || errorData.detail || `Upload failed: ${response.status}`);
      }

      const data: IngestResult = await response.json();
      setUploadResult(data);
      
      // Refresh stats after upload
      fetchStats();
    } catch (error) {
      console.error("Upload failed:", error);
      const errorMessage = error instanceof Error ? error.message : "Upload failed";
      setUploadResult({
        doc_id: file.name,
        status: "FAILED",
        chunks_count: 0,
        errors: [errorMessage],
        message: errorMessage,
      });
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/stats`);
      if (response.ok) {
        const data: IndexStats = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    }
  };

  const copyTraceId = () => {
    if (result?.trace_id) {
      navigator.clipboard.writeText(result.trace_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const copyResultSummary = () => {
    if (!result) return;
    const summary = `TrustRAG Result
Query: ${query}
Verdict: ${result.verdict}
${result.answer ? `Answer: ${result.answer.text}` : ""}
Trace ID: ${result.trace_id}`;
    navigator.clipboard.writeText(summary);
  };

  const exportEvidenceChain = async (format: "json" | "pdf") => {
    if (!result) return;
    
    const exportData = {
      query: query,
      trace_id: result.trace_id,
      verdict: result.verdict,
      timestamp: new Date().toISOString(),
      answer: result.answer,
      evidence: result.evidence,
      reasons: result.reasons,
      risk_flags: result.risk_flags,
      verification_data: result.verification_data
    };
    
    if (format === "json") {
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `evidence_chain_${result.trace_id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      // PDF export using browser print
      const printWindow = window.open("", "_blank");
      if (printWindow) {
        printWindow.document.write(`
          <html>
            <head><title>Evidence Chain - ${result.trace_id}</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
              <h1>TrustRAG Evidence Chain Report</h1>
              <h2>Query</h2>
              <p>${query}</p>
              <h2>Verdict</h2>
              <p><strong>${result.verdict}</strong></p>
              ${result.answer ? `<h2>Answer</h2><p>${result.answer.text}</p><p>Confidence: ${(result.answer.confidence * 100).toFixed(0)}%</p>` : ""}
              <h2>Evidence Chain</h2>
              <table border="1" cellpadding="5" style="width: 100%; border-collapse: collapse;">
                <tr><th>Metric</th><th>Value</th><th>Source</th><th>Page</th></tr>
                ${result.evidence.map(ev => `<tr><td>${ev.metric}</td><td>${ev.value}</td><td>${ev.source}</td><td>${ev.page}</td></tr>`).join("")}
              </table>
              ${result.reasons && result.reasons.length > 0 ? `<h2>Decision Reasons</h2><ul>${result.reasons.map(r => `<li>${r}</li>`).join("")}</ul>` : ""}
              ${result.risk_flags ? `<h2>Risk Flags</h2><pre>${JSON.stringify(result.risk_flags, null, 2)}</pre>` : ""}
              <p style="margin-top: 30px; color: #666; font-size: 12px;">Trace ID: ${result.trace_id} | Generated: ${new Date().toISOString()}</p>
            </body>
          </html>
        `);
        printWindow.document.close();
        setTimeout(() => {
          printWindow.print();
        }, 250);
      }
    }
  };

  const getVerdictConfig = (v: VerdictStatus) => {
    switch (v) {
      case "VERIFIED":
        return { bg: "bg-emerald-500", text: "text-emerald-500", icon: "✓", label: "Verified" };
      case "REFUSED":
        return { bg: "bg-red-500", text: "text-red-500", icon: "✕", label: "Refused" };
      case "CONFLICT":
        return { bg: "bg-amber-500", text: "text-amber-500", icon: "!", label: "Conflict" };
    }
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case "OK":
        return { bg: "bg-emerald-500", icon: "✓" };
      case "DEGRADED":
        return { bg: "bg-amber-500", icon: "!" };
      case "FAILED":
        return { bg: "bg-red-500", icon: "✕" };
      default:
        return { bg: "bg-gray-500", icon: "?" };
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="border-b border-white/10">
        <div className="max-w-4xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-lg flex items-center justify-center font-black text-sm">
                  T
                </div>
                <h1 className="text-2xl font-bold tracking-tight">TrustRAG</h1>
                <span className="text-xs text-white/40 font-mono">v1.0</span>
              </div>
              <p className="text-white/60 text-sm font-medium">
                Deterministic, Evidence-Backed Financial QA
              </p>
            </div>
            
            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => { setShowHistory(!showHistory); }}
                className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                         rounded text-xs text-white/60 hover:text-white transition-all"
              >
                📜 History ({queryHistory.length})
              </button>
              <button
                onClick={() => { setShowStats(!showStats); if (!stats) fetchStats(); }}
                className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                         rounded text-xs text-white/60 hover:text-white transition-all"
              >
                📊 Stats
              </button>
              <button
                onClick={() => setShowUpload(!showUpload)}
                className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 
                         rounded text-xs text-blue-400 hover:text-blue-300 transition-all"
              >
                📄 Upload Document
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        
        {/* Query History Panel */}
        {showHistory && (
          <section className="mb-6 bg-white/5 border border-white/10 rounded-xl p-4 max-h-96 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white/70">Query History</h3>
              <button onClick={() => setShowHistory(false)} className="text-white/40 hover:text-white">✕</button>
            </div>
            {queryHistory.length === 0 ? (
              <p className="text-white/40 text-xs">No query history yet</p>
            ) : (
              <div className="space-y-2">
                {queryHistory.map((entry, i) => (
                  <div
                    key={entry.query_id}
                    className="bg-white/5 border border-white/10 rounded-lg p-3 cursor-pointer hover:bg-white/[0.07] transition-all"
                    onClick={() => {
                      setQuery(entry.query);
                      setResult(entry.result);
                      setShowHistory(false);
                    }}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <p className="text-sm text-white/80 line-clamp-1 flex-1">{entry.query}</p>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        entry.result.verdict === "VERIFIED" ? "bg-emerald-500/20 text-emerald-400" :
                        entry.result.verdict === "REFUSED" ? "bg-red-500/20 text-red-400" :
                        "bg-amber-500/20 text-amber-400"
                      }`}>
                        {entry.result.verdict}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-white/40 mt-2">
                      <span>{new Date(entry.timestamp).toLocaleString()}</span>
                      <span className="font-mono">{entry.query_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Stats Panel */}
        {showStats && stats && (
          <section className="mb-6 bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white/70">Index Statistics</h3>
              <button onClick={() => setShowStats(false)} className="text-white/40 hover:text-white">✕</button>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-blue-400">{stats.documents_loaded}</p>
                <p className="text-xs text-white/50">Documents</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-400">{stats.total_chunks}</p>
                <p className="text-xs text-white/50">Total Chunks</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-400">
                  {Object.values(stats.chunks_by_tier).reduce((a, b) => a + b, 0)}
                </p>
                <p className="text-xs text-white/50">Indexed</p>
              </div>
            </div>
            {stats.documents.length > 0 && (
              <div className="mt-3 pt-3 border-t border-white/10">
                <p className="text-xs text-white/40 mb-2">Documents:</p>
                <div className="flex flex-wrap gap-1">
                  {stats.documents.slice(0, 5).map((doc, i) => (
                    <span key={i} className="px-2 py-0.5 bg-white/10 rounded text-xs text-white/60">
                      {doc}
                    </span>
                  ))}
                  {stats.documents.length > 5 && (
                    <span className="px-2 py-0.5 text-xs text-white/40">
                      +{stats.documents.length - 5} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Upload Panel */}
        {showUpload && (
          <section className="mb-6 bg-blue-500/5 border border-blue-500/20 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-blue-400">Upload Document</h3>
              <button onClick={() => setShowUpload(false)} className="text-white/40 hover:text-white">✕</button>
            </div>
            
            <div className="flex items-center gap-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.html,.txt,.csv,.xlsx"
                onChange={handleFileUpload}
                disabled={uploading}
                className="flex-1 text-sm text-white/60 file:mr-4 file:py-2 file:px-4
                         file:rounded file:border-0 file:text-sm file:font-semibold
                         file:bg-blue-600 file:text-white hover:file:bg-blue-500
                         file:cursor-pointer file:transition-all"
              />
              {uploading && (
                <div className="flex items-center gap-2 text-blue-400">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  <span className="text-xs">Processing...</span>
                </div>
              )}
            </div>
            
            <p className="mt-2 text-xs text-white/40">
              Supported formats: PDF, HTML, TXT, CSV, XLSX (max 50MB)
            </p>
            
            {/* Upload Result */}
            {uploadResult && (
              <div className={`mt-4 p-3 rounded-lg ${
                uploadResult.status === "OK" ? "bg-emerald-500/10 border border-emerald-500/20" :
                uploadResult.status === "DEGRADED" ? "bg-amber-500/10 border border-amber-500/20" :
                "bg-red-500/10 border border-red-500/20"
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-6 h-6 rounded flex items-center justify-center text-white text-sm ${getStatusConfig(uploadResult.status).bg}`}>
                    {getStatusConfig(uploadResult.status).icon}
                  </span>
                  <span className="font-medium text-sm">{uploadResult.message}</span>
                </div>
                <div className="text-xs text-white/60 space-y-1">
                  <p>Document ID: <span className="font-mono">{uploadResult.doc_id}</span></p>
                  <p>Chunks created: {uploadResult.chunks_count}</p>
                  {uploadResult.errors.length > 0 && (
                    <div className="mt-2 text-red-400">
                      {uploadResult.errors.map((err, i) => (
                        <p key={i}>⚠️ {err}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>
        )}
        
        {/* Demo Guide */}
        <section className="mb-8">
          <p className="text-white/50 text-xs uppercase tracking-wider mb-3 font-semibold">
            Try a factual financial question
          </p>
          <div className="flex flex-wrap gap-2">
            {DEMO_QUERIES.map((q, i) => (
              <button
                key={i}
                onClick={() => handleQuery(q)}
                disabled={loading}
                className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                         rounded-full text-xs text-white/70 hover:text-white transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {q}
              </button>
            ))}
          </div>
        </section>

        {/* Query Input */}
        <section className="mb-8">
          <div className="flex gap-3">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQuery(query)}
              placeholder="Ask a financial question..."
              disabled={loading}
              className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-lg
                       text-white placeholder:text-white/30 outline-none
                       focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20
                       disabled:opacity-50 transition-all"
            />
            <button
              onClick={() => handleQuery(query)}
              disabled={loading || !query.trim()}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-semibold
                       disabled:bg-white/10 disabled:text-white/30 disabled:cursor-not-allowed
                       transition-all"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Running
                </span>
              ) : (
                "Run"
              )}
            </button>
          </div>
        </section>

        {/* Result Area */}
        {result && (
          <section className="space-y-6 animate-in fade-in duration-300">
            {/* Verdict Badge */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`w-14 h-14 ${getVerdictConfig(result.verdict).bg} rounded-xl 
                              flex items-center justify-center text-white text-2xl font-bold shadow-lg`}>
                  {getVerdictConfig(result.verdict).icon}
                </div>
                <div>
                  <p className={`text-xl font-bold ${getVerdictConfig(result.verdict).text}`}>
                    {getVerdictConfig(result.verdict).label}
                  </p>
                  {result.answer && (
                    <p className="text-white/50 text-sm">
                      Confidence: {(result.answer.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                  {result.disclosure_required && (
                    <p className="text-amber-400 text-xs mt-1">⚠️ Disclosure required</p>
                  )}
                </div>
              </div>
              
              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowEvidenceSidebar(true)}
                  className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 
                           rounded text-xs text-blue-400 hover:text-blue-300 transition-all"
                >
                  🔗 Evidence Chain
                </button>
                <button
                  onClick={() => exportEvidenceChain("json")}
                  className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                           rounded text-xs text-white/60 hover:text-white transition-all"
                >
                  📥 Export JSON
                </button>
                <button
                  onClick={() => exportEvidenceChain("pdf")}
                  className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                           rounded text-xs text-white/60 hover:text-white transition-all"
                >
                  📄 Export PDF
                </button>
                <button
                  onClick={copyResultSummary}
                  className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                           rounded text-xs text-white/60 hover:text-white transition-all"
                >
                  Copy Summary
                </button>
                <button
                  onClick={copyTraceId}
                  className="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 
                           rounded font-mono text-xs text-white/60 hover:text-white transition-all"
                >
                  {copied ? "Copied!" : result.trace_id}
                </button>
              </div>
            </div>

            {/* Answer - Clickable for Evidence Chain */}
            {result.answer && (
              <div 
                className="bg-white/5 border border-white/10 rounded-xl p-6 cursor-pointer hover:bg-white/[0.07] transition-all"
                onClick={() => setShowEvidenceSidebar(true)}
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="text-white/40 text-xs uppercase tracking-wider font-semibold">
                    Answer
                  </p>
                  <span className="text-xs text-blue-400 hover:text-blue-300">
                    Click to view evidence chain →
                  </span>
                </div>
                <p className="text-lg text-white leading-relaxed">
                  {result.answer.text}
                </p>
              </div>
            )}

            {/* Refusal/Conflict Reasons */}
            {(result.verdict === "REFUSED" || result.verdict === "CONFLICT") && result.reasons && result.reasons.length > 0 && (
              <div className={`${
                result.verdict === "CONFLICT" ? "bg-amber-500/10 border-amber-500/20" : "bg-red-500/10 border-red-500/20"
              } border rounded-xl p-6`}>
                <p className={`${
                  result.verdict === "CONFLICT" ? "text-amber-400" : "text-red-400"
                } text-xs uppercase tracking-wider mb-2 font-semibold`}>
                  {result.verdict === "CONFLICT" ? "Conflict Details" : "Reason"}
                </p>
                {result.reasons.map((r, i) => (
                  <p key={i} className={`${
                    result.verdict === "CONFLICT" ? "text-amber-300" : "text-red-300"
                  } ${i > 0 ? "mt-1" : ""}`}>
                    {r}
                  </p>
                ))}
              </div>
            )}

            {/* Risk Flags */}
            {result.risk_flags && Object.keys(result.risk_flags).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(result.risk_flags).map(([flag, value]) => (
                  value && (
                    <span key={flag} className="px-2 py-1 bg-amber-500/10 border border-amber-500/20 
                                               rounded text-xs text-amber-400">
                      ⚡ {flag.replace(/_/g, " ")}
                    </span>
                  )
                ))}
              </div>
            )}

            {/* Evidence */}
            {result.evidence.length > 0 && (
              <details className="group">
                <summary className="flex items-center justify-between cursor-pointer 
                                  bg-white/5 border border-white/10 rounded-xl px-6 py-4
                                  hover:bg-white/[0.07] transition-all">
                  <div className="flex items-center gap-3">
                    <span className="text-white/40 text-xs uppercase tracking-wider font-semibold">
                      Supporting Evidence
                    </span>
                    <span className="bg-white/10 text-white/60 text-xs px-2 py-0.5 rounded-full">
                      {result.evidence.length}
                    </span>
                  </div>
                  <span className="text-white/30 text-xs group-open:rotate-180 transition-transform">
                    ▼
                  </span>
                </summary>
                <div className="mt-2 bg-white/5 border border-white/10 rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10 text-white/40 text-xs uppercase tracking-wider">
                        <th className="text-left px-6 py-3 font-semibold">Metric</th>
                        <th className="text-left px-6 py-3 font-semibold">Value</th>
                        <th className="text-left px-6 py-3 font-semibold">Source</th>
                        <th className="text-center px-6 py-3 font-semibold">Page</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {result.evidence.map((ev, i) => (
                        <tr key={i} className="text-white/80 hover:bg-white/5 transition-colors">
                          <td className="px-6 py-3 font-medium">{ev.metric}</td>
                          <td className="px-6 py-3 text-blue-400 font-semibold max-w-xs truncate">{ev.value}</td>
                          <td className="px-6 py-3 text-white/60">{ev.source}</td>
                          <td className="px-6 py-3 text-center text-white/50">{ev.page}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            {/* Arbitration Process Visualization */}
            {result.verification_data && (
              <details className="group">
                <summary className="flex items-center justify-between cursor-pointer 
                                  bg-white/5 border border-white/10 rounded-xl px-6 py-4
                                  hover:bg-white/[0.07] transition-all">
                  <span className="text-white/40 text-xs uppercase tracking-wider font-semibold">
                    Arbitration Process & Decision Path
                  </span>
                  <span className="text-white/30 text-xs group-open:rotate-180 transition-transform">
                    ▼
                  </span>
                </summary>
                <div className="mt-2 bg-white/5 border border-white/10 rounded-xl p-6 space-y-4">
                  {/* Decision Flow */}
                  <div>
                    <h4 className="text-white/70 text-sm font-semibold mb-3">Decision Flow</h4>
                    <div className="flex items-center gap-2 text-xs">
                      <div className="px-3 py-2 bg-blue-500/20 border border-blue-500/30 rounded">Query</div>
                      <span>→</span>
                      <div className="px-3 py-2 bg-blue-500/20 border border-blue-500/30 rounded">Retrieval</div>
                      <span>→</span>
                      <div className="px-3 py-2 bg-blue-500/20 border border-blue-500/30 rounded">Arbitration</div>
                      <span>→</span>
                      <div className={`px-3 py-2 border rounded ${
                        result.verdict === "VERIFIED" ? "bg-emerald-500/20 border-emerald-500/30" :
                        result.verdict === "REFUSED" ? "bg-red-500/20 border-red-500/30" :
                        "bg-amber-500/20 border-amber-500/30"
                      }`}>
                        {result.verdict}
                      </div>
                    </div>
                  </div>
                  
                  {/* Risk Flags Tree */}
                  {result.risk_flags && Object.keys(result.risk_flags).length > 0 && (
                    <div>
                      <h4 className="text-white/70 text-sm font-semibold mb-3">Risk Assessment</h4>
                      <div className="space-y-2">
                        {Object.entries(result.risk_flags).map(([flag, value]) => (
                          <div key={flag} className="flex items-center gap-2 text-xs">
                            <span className={`w-2 h-2 rounded-full ${value ? "bg-amber-400" : "bg-emerald-400"}`}></span>
                            <span className="text-white/60">{flag.replace(/_/g, " ")}</span>
                            <span className={`ml-auto ${value ? "text-amber-400" : "text-emerald-400"}`}>
                              {value ? "⚠️ Active" : "✓ Safe"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Scoring Details */}
                  {result.verification_data && typeof result.verification_data === 'object' && 'processing_time_ms' in result.verification_data && (
                    <div>
                      <h4 className="text-white/70 text-sm font-semibold mb-3">Performance Metrics</h4>
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-white/40">Processing Time:</span>
                          <span className="ml-2 text-white/80">{String(result.verification_data.processing_time_ms)}ms</span>
                        </div>
                        {'candidates_count' in result.verification_data && result.verification_data.candidates_count ? (
                          <div>
                            <span className="text-white/40">Candidates:</span>
                            <span className="ml-2 text-white/80">{String(result.verification_data.candidates_count)}</span>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  )}
                  
                  {/* Debug Data */}
                  <details className="mt-4">
                    <summary className="text-white/40 text-xs cursor-pointer hover:text-white/60">
                      Raw Verification Data
                    </summary>
                    <pre className="mt-2 text-xs text-white/60 overflow-auto bg-black/20 p-3 rounded">
                      {JSON.stringify(result.verification_data || {}, null, 2)}
                    </pre>
                  </details>
                </div>
              </details>
            )}
          </section>
        )}
        
        {/* Evidence Chain Sidebar */}
        {showEvidenceSidebar && result && (
          <div className="fixed inset-0 z-50 flex">
            {/* Backdrop */}
            <div 
              className="flex-1 bg-black/80 backdrop-blur-sm"
              onClick={() => setShowEvidenceSidebar(false)}
            ></div>
            
            {/* Sidebar */}
            <div className="w-full max-w-2xl bg-[#0a0a0a] border-l border-white/10 overflow-y-auto">
              <div className="sticky top-0 bg-[#0a0a0a] border-b border-white/10 p-6 flex items-center justify-between">
                <h2 className="text-xl font-bold">Evidence Chain & Traceability</h2>
                <button
                  onClick={() => setShowEvidenceSidebar(false)}
                  className="text-white/40 hover:text-white text-2xl"
                >
                  ×
                </button>
              </div>
              
              <div className="p-6 space-y-6">
                {/* Query Info */}
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <h3 className="text-white/40 text-xs uppercase tracking-wider mb-2 font-semibold">Query</h3>
                  <p className="text-white">{query}</p>
                  <div className="mt-2 flex items-center gap-4 text-xs text-white/60">
                    <span>Trace ID: <span className="font-mono">{result.trace_id}</span></span>
                    <span>Verdict: <span className={`font-semibold ${
                      result.verdict === "VERIFIED" ? "text-emerald-400" :
                      result.verdict === "REFUSED" ? "text-red-400" :
                      "text-amber-400"
                    }`}>{result.verdict}</span></span>
                  </div>
                </div>
                
                {/* All Evidence Items */}
                <div>
                  <h3 className="text-white/70 text-sm font-semibold mb-4">
                    Evidence Items ({result.evidence.length})
                  </h3>
                  <div className="space-y-3">
                    {result.evidence.map((ev, i) => (
                      <div
                        key={i}
                        className={`bg-white/5 border rounded-xl p-4 cursor-pointer transition-all ${
                          selectedEvidence === ev ? "border-blue-500 bg-blue-500/10" : "border-white/10 hover:bg-white/[0.07]"
                        }`}
                        onClick={() => setSelectedEvidence(ev)}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs text-white/40">#{i + 1}</span>
                              <span className="text-sm font-semibold text-white">{ev.metric}</span>
                            </div>
                            <p className="text-blue-400 font-medium mb-2">{ev.value}</p>
                            <div className="flex items-center gap-4 text-xs text-white/60">
                              <span>📄 {ev.source}</span>
                              <span>📑 Page {ev.page}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Selected Evidence Detail */}
                {selectedEvidence && (
                  <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
                    <h3 className="text-blue-400 text-sm font-semibold mb-3">Evidence Detail</h3>
                    <div className="space-y-2 text-sm">
                      <div>
                        <span className="text-white/40">Metric:</span>
                        <span className="ml-2 text-white">{selectedEvidence.metric}</span>
                      </div>
                      <div>
                        <span className="text-white/40">Value:</span>
                        <span className="ml-2 text-blue-400 font-medium">{selectedEvidence.value}</span>
                      </div>
                      <div>
                        <span className="text-white/40">Source Document:</span>
                        <span className="ml-2 text-white">{selectedEvidence.source}</span>
                      </div>
                      <div>
                        <span className="text-white/40">Page Number:</span>
                        <span className="ml-2 text-white">{selectedEvidence.page}</span>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Decision Reasons */}
                {result.reasons && result.reasons.length > 0 && (
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="text-white/70 text-sm font-semibold mb-3">Arbitration Reasons</h3>
                    <ul className="space-y-2">
                      {result.reasons.map((reason, i) => (
                        <li key={i} className="text-sm text-white/80 flex items-start gap-2">
                          <span className="text-white/40 mt-1">•</span>
                          <span>{reason}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Export Actions */}
                <div className="flex gap-3 pt-4 border-t border-white/10">
                  <button
                    onClick={() => exportEvidenceChain("json")}
                    className="flex-1 px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 
                             rounded text-sm text-blue-400 hover:text-blue-300 transition-all"
                  >
                    📥 Export JSON
                  </button>
                  <button
                    onClick={() => exportEvidenceChain("pdf")}
                    className="flex-1 px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 
                             rounded text-sm text-blue-400 hover:text-blue-300 transition-all"
                  >
                    📄 Export PDF
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 border-t border-white/10 bg-[#0a0a0a]/90 backdrop-blur">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <p className="text-white/30 text-xs">
            TrustRAG v1.0 · All answers are evidence-backed · No hallucination
          </p>
          <a 
            href="https://github.com/trustrag/trustrag" 
            target="_blank"
            rel="noopener noreferrer"
            className="text-white/30 hover:text-white/60 text-xs transition-colors"
          >
            GitHub →
          </a>
        </div>
      </footer>
    </div>
  );
}
