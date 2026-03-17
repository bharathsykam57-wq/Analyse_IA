export interface HistoryItem {
  id: string;
  query: string;
  result: string; // Analysis result or summary
  timestamp: string; // ISO datetime
  model_used: string; // Model name
  confidence: number; // 0-1 confidence score
  status: 'SUCCESS' | 'FAILURE';
  task_type?: string; // analysis, rag, code
}

export interface HistoryResponse {
  queries: HistoryItem[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface HistoryFilters {
  searchQuery?: string;
  dateRange?: 'last_24h' | 'last_7d' | 'all';
  status?: 'all' | 'success' | 'failed';
  page?: number;
  pageSize?: number;
}
