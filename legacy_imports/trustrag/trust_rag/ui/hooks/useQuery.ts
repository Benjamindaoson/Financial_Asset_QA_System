"use client";

import { useState, useCallback } from 'react';
import { SystemResult, QueryHistory, ApiResponse } from '@/types';
import { useLocalStorage } from './useLocalStorage';
import { useNotifications } from './useNotifications';

interface UseQueryOptions {
  persistHistory?: boolean;
  maxHistorySize?: number;
  enableRealtime?: boolean;
}

export function useQuery(options: UseQueryOptions = {}) {
  const {
    persistHistory = true,
    maxHistorySize = 50,
    enableRealtime = false
  } = options;

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SystemResult | null>(null);
  const [streamingResult, setStreamingResult] = useState<SystemResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [history, setHistory] = useLocalStorage<QueryHistory[]>('query-history', []);
  const { addNotification } = useNotifications();

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const executeQuery = useCallback(async (q: string, context?: Record<string, any>) => {
    if (!q.trim()) return;

    setQuery(q);
    setLoading(true);
    setError(null);
    setResult(null);

    // Add to recent queries for suggestions
    updateRecentQueries(q);

    try {
      const response = await fetch(`${apiUrl}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          context,
          enable_streaming: enableRealtime,
          risk_level: 'medium'
        }),
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

      if (persistHistory) {
        setHistory(prev => [historyEntry, ...prev.slice(0, maxHistorySize - 1)]);
      }

      // Show success notification
      addNotification({
        type: 'success',
        title: 'Query Completed',
        message: `Found ${data.evidence.length} evidence items`,
        duration: 3000
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);

      // Show error notification
      addNotification({
        type: 'error',
        title: 'Query Failed',
        message: errorMessage,
        duration: 5000
      });
    } finally {
      setLoading(false);
    }
  }, [apiUrl, enableRealtime, persistHistory, maxHistorySize, addNotification, setHistory]);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, [setHistory]);

  const removeHistoryItem = useCallback((queryId: string) => {
    setHistory(prev => prev.filter(item => item.query_id !== queryId));
  }, [setHistory]);

  const retryQuery = useCallback((historyItem: QueryHistory) => {
    executeQuery(historyItem.query);
  }, [executeQuery]);

  const exportHistory = useCallback((format: 'json' | 'csv' = 'json') => {
    const data = history.map(item => ({
      query: item.query,
      verdict: item.result.verdict,
      confidence: item.result.answer?.confidence || 0,
      evidence_count: item.result.evidence.length,
      timestamp: item.timestamp,
      trace_id: item.result.trace_id
    }));

    if (format === 'json') {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `query_history_${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else if (format === 'csv') {
      const csv = [
        ['Query', 'Verdict', 'Confidence', 'Evidence Count', 'Timestamp', 'Trace ID'],
        ...data.map(row => [
          `"${row.query}"`,
          row.verdict,
          row.confidence.toString(),
          row.evidence_count.toString(),
          row.timestamp,
          row.trace_id
        ])
      ].map(row => row.join(',')).join('\n');

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `query_history_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [history]);

  return {
    // State
    query,
    loading,
    result,
    streamingResult,
    error,
    history,

    // Actions
    executeQuery,
    setQuery,
    clearHistory,
    removeHistoryItem,
    retryQuery,
    exportHistory,

    // Utilities
    hasResults: result !== null,
    hasError: error !== null,
    isEmptyHistory: history.length === 0
  };
}

// Recent queries for suggestions
let recentQueries: string[] = [];

function updateRecentQueries(query: string) {
  // Remove if already exists
  recentQueries = recentQueries.filter(q => q !== query);
  // Add to beginning
  recentQueries.unshift(query);
  // Keep only last 10
  recentQueries = recentQueries.slice(0, 10);
}

export function getRecentQueries(): string[] {
  return [...recentQueries];
}







