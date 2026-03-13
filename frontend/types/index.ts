// Raw shape from /files/list
export interface RawFile {
  filename: string
  type: 'csv' | 'pdf'
  size_bytes: number
  uploaded_at: string
}

// Frontend shape after parseFilename — extracted file_id and original_name
export interface UploadedFile extends RawFile {
  file_id: string
  original_name: string
}

export type FileItem = UploadedFile

// User profile
export interface User {
  id: string
  email: string
  full_name?: string
  is_active: boolean
  is_verified: boolean
  preferred_language: string
  created_at: string
}

// Auth tokens from login/register response
export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name?: string
}

// Agent API request and response
export interface AgentRequest {
  query: string
  file_id?: string
  session_id?: string
  language?: 'fr' | 'en'
}

export interface AgentResponse {
  task_id: string
  session_id: string
  status: 'queued'
  message: string
}

// Task status polling response
export interface TaskStatus {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY'
  result?: BackendResult
  error?: string
}

// Complete result from agent execution
export interface BackendResult {
  success: boolean
  answer: string
  question: string
  task_type: string
  confidence_score: number
  steps_taken: string[]
  result?: BackendResultDetail
  error?: string | null
}

// Analysis result details from agent
export interface BackendResultDetail {
  success: boolean
  dataset_path?: string
  rows?: number
  columns?: number
  eda_insights?: string[]
  best_model?: string
  metrics?: {
    Accuracy: number
    AUC: number
    F1: number
    Precision: number
    Recall: number
  }
  top_features?: TopFeature[]
  anomalies?: BackendAnomalies
  answer?: string
  error?: string | null
}

export interface TopFeature {
  feature: string
  importance: number
  importance_percentage: number
}

export interface BackendAnomalies {
  total: number
  percentage: number
  high: number
  medium: number
  low: number
}

// Frontend shape for displaying analysis — maps from BackendResult
export interface AnalysisResult {
  model?: string
  rows?: number
  columns?: number
  metrics?: {
    Accuracy: number
    AUC: number
    F1: number
    Precision: number
    Recall: number
  }
  top_features?: TopFeature[]
  anomalies?: BackendAnomalies
  eda_insights?: string[]
}

export interface ShapValue {
  feature: string
  importance: number
  importance_percentage: number
}

// Chat message in store
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  language: 'fr' | 'en'
  analysis?: AnalysisResult
  isStreaming?: boolean
  taskId?: string
}

// Conversation history item
export interface HistoryItem {
  id: string
  query: string
  response_preview: string
  type: 'analyse' | 'rag' | 'code'
  language: 'fr' | 'en'
  created_at: string
}

// RGPD consent record
export interface RgpdConsent {
  analytics: boolean
  storage: boolean
  ai_processing: boolean
  created_at: string
}

// RGPD audit log entry
export interface AuditEntry {
  id: string
  action: string
  timestamp: string
  details: string
}
