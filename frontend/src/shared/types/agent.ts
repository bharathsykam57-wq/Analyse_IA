export interface TopFeature {
    name: string;
    feature: string;
    importance: number;
    importance_percentage: number;
}
  
export interface BackendAnomalies {
    high: number;
    medium: number;
    low: number;
    total: number;
    percentage: number;
}
  
export interface AnalysisResult {
  model?: string;
  best_model?: string;
  base_model_name?: string;
  tuned_model_name?: string;
  rows?: number;
  columns?: number;
  anomalies?: BackendAnomalies;
  metrics?: Record<string, number>;
  base_metrics?: Record<string, number>;
  tuned_metrics?: Record<string, number>;
  tuning_applied?: boolean;
  tuning_error?: string | null;
  top_features?: TopFeature[];
  comparison?: Array<Record<string, string | number | null>>;
}
  
export interface BackendResult {
  task_id: string;
  status: 'PENDING' | 'SUCCESS' | 'FAILURE';
  answer?: string;
  result?: {
    success: boolean;
    question?: string;
    task_type?: string;
    confidence_score?: number;
    answer?: string;
    steps_taken?: string[];
    result?: AnalysisResult;
    error?: string | null;
    session_memory?: Record<string, unknown>;
  };
}
  
export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    analysisData?: AnalysisResult;
    isPolling?: boolean;
}
