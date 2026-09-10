// Core API Types
export type VerdictStatus = "VERIFIED" | "REFUSED" | "CONFLICT";

export interface Answer {
  text: string;
  confidence: number;
  sources?: string[];
  reasoning?: string;
}

export interface EvidenceItem {
  metric: string;
  value: string;
  source: string;
  page: number;
  confidence?: number;
  category?: string;
  timestamp?: string;
}

export interface SystemResult {
  verdict: VerdictStatus;
  answer?: Answer;
  evidence: EvidenceItem[];
  trace_id: string;
  reasons?: string[];
  risk_flags?: Record<string, boolean>;
  disclosure_required?: boolean;
  verification_data?: Record<string, unknown>;
  processing_time_ms?: number;
  model_version?: string;
}

export interface QueryHistory {
  query: string;
  result: SystemResult;
  timestamp: string;
  query_id: string;
  user_id?: string;
  session_id?: string;
}

// Document and Upload Types
export interface IngestResult {
  doc_id: string;
  status: string;
  chunks_count: number;
  errors: string[];
  message: string;
  processing_time_ms?: number;
  file_size?: number;
  mime_type?: string;
}

export interface DocumentMetadata {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  uploaded_at: string;
  processed_at?: string;
  chunks_count: number;
  status: 'processing' | 'completed' | 'failed';
  error_message?: string;
}

// Statistics Types
export interface IndexStats {
  total_chunks: number;
  documents_loaded: number;
  documents: string[];
  chunks_by_tier: Record<string, number>;
  last_updated: string;
  total_size_bytes: number;
}

export interface PerformanceMetrics {
  avg_response_time: number;
  total_queries: number;
  success_rate: number;
  cache_hit_rate: number;
  error_rate: number;
}

// Multimodal Types
export interface AudioAnalysis {
  transcription: string;
  duration: number;
  confidence: number;
  language: string;
  segments?: Array<{
    start: number;
    end: number;
    text: string;
    confidence: number;
  }>;
}

export interface ChartAnalysis {
  chart_type: string;
  elements: Array<{
    type: string;
    bbox: [number, number, number, number];
    text?: string;
    value?: number;
    confidence: number;
  }>;
  data_points: Array<{
    x: number;
    y: number;
    label?: string;
    value: number;
  }>;
  reasoning: string[];
}

export interface ImageAnalysis {
  description: string;
  objects: Array<{
    label: string;
    confidence: number;
    bbox: [number, number, number, number];
  }>;
  text_content?: string;
  ocr_confidence?: number;
}

// UI State Types
export interface UIState {
  theme: 'light' | 'dark' | 'auto';
  sidebarOpen: boolean;
  modalOpen: boolean;
  loadingStates: Record<string, boolean>;
  notifications: Notification[];
}

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: number;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

// Real-time Types
export interface StreamingResponse {
  id: string;
  content: string;
  isComplete: boolean;
  progress?: number;
  current_step?: string;
  estimated_time_remaining?: number;
}

export interface RealtimeMetrics {
  active_connections: number;
  queries_per_second: number;
  avg_response_time: number;
  system_load: number;
  memory_usage: number;
  gpu_usage?: number;
}

// Search and Filter Types
export interface SearchFilters {
  dateRange?: {
    start: Date;
    end: Date;
  };
  verdict?: VerdictStatus[];
  confidence?: {
    min: number;
    max: number;
  };
  sources?: string[];
  categories?: string[];
}

export interface SortOption {
  field: 'timestamp' | 'confidence' | 'relevance';
  direction: 'asc' | 'desc';
}

// Export Types
export type ExportFormat = 'json' | 'pdf' | 'csv' | 'markdown';

export interface ExportOptions {
  format: ExportFormat;
  includeEvidence: boolean;
  includeMetadata: boolean;
  includeTrace: boolean;
  dateRange?: {
    start: Date;
    end: Date;
  };
}

// Cloud Storage Types
export interface CloudValidationResult {
  url: string;
  is_valid: boolean;
  provider?: string;
  file_info?: {
    file_id: string;
    filename: string;
    size: number;
    mime_type: string;
    download_url?: string;
    direct_url?: string;
    created_time?: string;
    modified_time?: string;
    owner?: string;
    is_public: boolean;
    expires_at?: string;
    metadata: Record<string, any>;
  };
  error_message?: string;
  confidence: number;
}

export interface CloudDownloadResult {
  url: string;
  success: boolean;
  local_path?: string;
  file_info?: Record<string, any>;
  download_time_seconds: number;
  bytes_downloaded: number;
  error_message?: string;
  ingest_result?: {
    doc_id: string;
    status: string;
    chunks_count: number;
    errors: string[];
    message: string;
  };
}

export interface CloudBatchResult {
  total_links: number;
  processed_links: number;
  successful_downloads: number;
  failed_operations: number;
  results: CloudDownloadResult[];
  summary: {
    valid_links: number;
    invalid_links: number;
    successful_ingests: number;
    failed_ingests: number;
    supported_providers: string[];
  };
}

export interface CloudProvider {
  name: string;
  display_name: string;
  supported: boolean;
  requires_auth: boolean;
  examples: string[];
}

// API Types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  trace_id?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

// Component Props Types
export interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
  id?: string;
}

export interface LoadingProps extends BaseComponentProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  overlay?: boolean;
}

export interface ModalProps extends BaseComponentProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closable?: boolean;
}

// Hook Return Types
export interface UseQueryResult {
  data: SystemResult | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export interface UseDocumentsResult {
  documents: DocumentMetadata[];
  loading: boolean;
  error: string | null;
  upload: (file: File) => Promise<void>;
  remove: (docId: string) => Promise<void>;
  refetch: () => void;
}

export interface UseRealtimeResult {
  metrics: RealtimeMetrics;
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
}
