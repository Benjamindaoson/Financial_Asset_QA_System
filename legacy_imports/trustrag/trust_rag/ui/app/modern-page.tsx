"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loading } from '@/components/ui/loading';
import { ChartDisplay } from '@/components/multimodal/chart-display';
import { AudioPlayer } from '@/components/multimodal/audio-player';
import { CloudUpload } from '@/components/cloud-upload';
import { useQuery } from '@/hooks/useQuery';
import { useDocuments } from '@/hooks/useDocuments';
import { useNotifications } from '@/hooks/useNotifications';
import { SystemResult, ChartAnalysis, AudioAnalysis } from '@/types';
import { Search, Upload, FileText, BarChart3, Mic, Image, Zap, History } from 'lucide-react';

const DEMO_QUERIES = [
  "What was Nvidia's revenue for FY2023?",
  "Calculate Nvidia's net profit margin for FY2023",
  "What was Nvidia's gross profit in Q3 2024?",
  "Compare Apple and Microsoft revenue growth",
  "Analyze Tesla's quarterly performance trends",
];

const DEMO_CHART: ChartAnalysis = {
  chart_type: 'bar_chart',
  elements: [
    { type: 'data_point', bbox: [100, 200, 150, 250], text: 'Q1', value: 120, confidence: 0.95 },
    { type: 'data_point', bbox: [200, 180, 250, 220], text: 'Q2', value: 150, confidence: 0.92 },
    { type: 'data_point', bbox: [300, 160, 350, 200], text: 'Q3', value: 180, confidence: 0.88 },
    { type: 'data_point', bbox: [400, 140, 450, 180], text: 'Q4', value: 200, confidence: 0.90 },
    { type: 'axis', bbox: [50, 250, 500, 260], text: 'X-Axis', confidence: 0.85 },
    { type: 'label', bbox: [20, 120, 40, 240], text: 'Revenue ($M)', confidence: 0.80 },
  ],
  data_points: [
    { x: 0, y: 120, label: 'Q1', value: 120 },
    { x: 1, y: 150, label: 'Q2', value: 150 },
    { x: 2, y: 180, label: 'Q3', value: 180 },
    { x: 3, y: 200, label: 'Q4', value: 200 },
  ],
  reasoning: [
    "Chart shows quarterly revenue growth trend",
    "Q4 shows highest performance with 200 units",
    "Consistent upward trend across all quarters",
    "Bar chart effectively displays comparative data"
  ]
};

const DEMO_AUDIO: AudioAnalysis = {
  transcription: "This is a sample audio transcription showing how the system can process and analyze spoken content. The transcription includes timestamps and confidence scores for different segments of the audio.",
  duration: 45.2,
  confidence: 0.94,
  language: 'en',
  segments: [
    { start: 0, end: 10, text: "This is a sample audio transcription", confidence: 0.96 },
    { start: 10, end: 25, text: "showing how the system can process", confidence: 0.92 },
    { start: 25, end: 35, text: "and analyze spoken content", confidence: 0.95 },
    { start: 35, end: 45, text: "The transcription includes timestamps", confidence: 0.88 }
  ]
};

export default function ModernPage() {
  const [activeTab, setActiveTab] = useState<'query' | 'upload' | 'results'>('query');
  const [uploadMode, setUploadMode] = useState<'local' | 'cloud'>('local');
  const [showDemo, setShowDemo] = useState(true);

  const { executeQuery, query, result, loading, history, clearHistory } = useQuery();
  const { uploadDocument, documents, uploading } = useDocuments();
  const { showSuccess, showError } = useNotifications();

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const result = await uploadDocument(file);
    if (result) {
      showSuccess('Document uploaded successfully!');
    }
  };

  const VerdictIcon = ({ verdict }: { verdict: string }) => {
    const icons = {
      VERIFIED: '✅',
      REFUSED: '❌',
      CONFLICT: '⚠️'
    };
    return <span className="text-2xl">{icons[verdict as keyof typeof icons] || '❓'}</span>;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900">
      {/* Header */}
      <motion.header
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="border-b border-white/10 backdrop-blur-md bg-black/20"
      >
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <motion.div
              initial={{ x: -50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              className="flex items-center gap-4"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">GraphRAG</h1>
                <p className="text-sm text-blue-300">AI-Powered Financial Analysis</p>
              </div>
            </motion.div>

            <div className="flex items-center gap-3">
              <Button
                variant={activeTab === 'query' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setActiveTab('query')}
                className="text-white hover:bg-white/10"
              >
                <Search className="w-4 h-4 mr-2" />
                Query
              </Button>
              <Button
                variant={activeTab === 'upload' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setActiveTab('upload')}
                className="text-white hover:bg-white/10"
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload
              </Button>
              <Button
                variant={activeTab === 'results' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setActiveTab('results')}
                className="text-white hover:bg-white/10"
              >
                <History className="w-4 h-4 mr-2" />
                History
              </Button>
            </div>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <AnimatePresence mode="wait">
          {activeTab === 'query' && (
            <motion.div
              key="query"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-8"
            >
              {/* Query Input */}
              <Card className="bg-white/5 border-white/10 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Search className="w-5 h-5" />
                    Ask Financial Questions
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-3">
                    <Input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="e.g., What was Nvidia's revenue for FY2023?"
                      className="flex-1 bg-white/10 border-white/20 text-white placeholder:text-white/50"
                      onKeyDown={(e) => e.key === 'Enter' && executeQuery(query)}
                    />
                    <Button
                      onClick={() => executeQuery(query)}
                      disabled={loading || !query.trim()}
                      size="lg"
                      className="bg-blue-600 hover:bg-blue-700"
                    >
                      {loading ? <Loading size="sm" /> : 'Analyze'}
                    </Button>
                  </div>

                  {/* Demo Queries */}
                  <div>
                    <p className="text-sm text-white/60 mb-3">Try these examples:</p>
                    <div className="flex flex-wrap gap-2">
                      {DEMO_QUERIES.map((demoQuery, i) => (
                        <Button
                          key={i}
                          variant="outline"
                          size="sm"
                          onClick={() => executeQuery(demoQuery)}
                          disabled={loading}
                          className="text-xs border-white/20 text-white/80 hover:bg-white/10"
                        >
                          {demoQuery}
                        </Button>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Demo Multimodal Content */}
              {showDemo && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="grid grid-cols-1 lg:grid-cols-2 gap-6"
                >
                  <ChartDisplay chartData={DEMO_CHART} />
                  <AudioPlayer audioData={DEMO_AUDIO} />
                </motion.div>
              )}

              {/* Cloud Storage Upload Demo */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-8"
              >
                <CloudUpload />
              </motion.div>

              {/* Results */}
              {result && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <Card className="bg-white/5 border-white/10 backdrop-blur-sm">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <VerdictIcon verdict={result.verdict} />
                          <div>
                            <CardTitle className="text-white">{result.verdict}</CardTitle>
                            <p className="text-sm text-white/60">
                              Trace ID: {result.trace_id}
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" className="border-white/20 text-white/80">
                            Export PDF
                          </Button>
                          <Button size="sm" variant="outline" className="border-white/20 text-white/80">
                            Copy
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {result.answer && (
                        <div className="bg-white/5 rounded-lg p-4">
                          <h3 className="text-white font-semibold mb-2">Answer</h3>
                          <p className="text-white/90 leading-relaxed">{result.answer.text}</p>
                          <p className="text-sm text-blue-300 mt-2">
                            Confidence: {(result.answer.confidence * 100).toFixed(1)}%
                          </p>
                        </div>
                      )}

                      {result.evidence && result.evidence.length > 0 && (
                        <div>
                          <h3 className="text-white font-semibold mb-3">Evidence Chain</h3>
                          <div className="space-y-2">
                            {result.evidence.slice(0, 3).map((evidence, i) => (
                              <div key={i} className="bg-white/5 rounded-lg p-3">
                                <div className="flex justify-between items-start mb-2">
                                  <span className="text-blue-300 font-medium">{evidence.metric}</span>
                                  <span className="text-xs text-white/40">Page {evidence.page}</span>
                                </div>
                                <p className="text-white/80">{evidence.value}</p>
                                <p className="text-xs text-white/50 mt-1">{evidence.source}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </motion.div>
          )}

          {activeTab === 'upload' && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <Card className="bg-white/5 border-white/10 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Upload className="w-5 h-5" />
                    Document Upload
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="border-2 border-dashed border-white/20 rounded-lg p-8 text-center">
                    <FileText className="w-12 h-12 text-white/40 mx-auto mb-4" />
                    <p className="text-white/60 mb-4">Upload financial documents for analysis</p>
                    <input
                      type="file"
                      accept=".pdf,.html,.txt,.csv,.xlsx"
                      onChange={handleFileUpload}
                      className="hidden"
                      id="file-upload"
                    />
                    <label htmlFor="file-upload">
                      <Button asChild>
                        <span>Choose File</span>
                      </Button>
                    </label>
                  </div>

                  {documents.length > 0 && (
                    <div>
                      <h3 className="text-white font-semibold mb-3">Uploaded Documents</h3>
                      <div className="space-y-2">
                        {documents.slice(0, 5).map((doc) => (
                          <div key={doc.id} className="flex items-center justify-between bg-white/5 rounded-lg p-3">
                            <div className="flex items-center gap-3">
                              <FileText className="w-4 h-4 text-blue-400" />
                              <span className="text-white">{doc.filename}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-1 rounded text-xs ${
                                doc.status === 'completed' ? 'bg-green-500/20 text-green-300' :
                                doc.status === 'processing' ? 'bg-yellow-500/20 text-yellow-300' :
                                'bg-red-500/20 text-red-300'
                              }`}>
                                {doc.status}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}

          {activeTab === 'results' && (
            <motion.div
              key="results"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <Card className="bg-white/5 border-white/10 backdrop-blur-sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-white flex items-center gap-2">
                      <History className="w-5 h-5" />
                      Query History
                    </CardTitle>
                    {history.length > 0 && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={clearHistory}
                        className="border-white/20 text-white/80"
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {history.length === 0 ? (
                    <p className="text-white/40 text-center py-8">No query history yet</p>
                  ) : (
                    <div className="space-y-3">
                      {history.map((entry) => (
                        <div
                          key={entry.query_id}
                          className="bg-white/5 border border-white/10 rounded-lg p-4 cursor-pointer hover:bg-white/10 transition-all"
                          onClick={() => {
                            setQuery(entry.query);
                            setActiveTab('query');
                          }}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <p className="text-white flex-1">{entry.query}</p>
                            <span className={`px-2 py-1 rounded text-xs ${
                              entry.result.verdict === 'VERIFIED' ? 'bg-green-500/20 text-green-300' :
                              entry.result.verdict === 'REFUSED' ? 'bg-red-500/20 text-red-300' :
                              'bg-yellow-500/20 text-yellow-300'
                            }`}>
                              {entry.result.verdict}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-xs text-white/40">
                            <span>{new Date(entry.timestamp).toLocaleString()}</span>
                            <span>{entry.result.evidence?.length || 0} evidence items</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 backdrop-blur-md bg-black/20 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between">
            <p className="text-white/40 text-sm">
              GraphRAG v2.0 · Evidence-Backed AI Analysis · Built with Next.js & TypeScript
            </p>
            <div className="flex items-center gap-4 text-white/40 text-sm">
              <span>⚡ Real-time Processing</span>
              <span>🔒 Secure & Private</span>
              <span>📊 Data-Driven</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
