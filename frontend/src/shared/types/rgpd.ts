export interface ExportStatus {
  export_id: string;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  created_at: string;
  expires_at: string;
  download_url?: string;
  error?: string;
}

export interface ErasureResponse {
  status: 'deleted' | 'error';
  message: string;
}

export interface AuditLogEvent {
  id: string;
  timestamp: string;
  event_type: 'login' | 'logout' | 'file_upload' | 'query_executed' | 'data_export' | 'profile_change';
  ip_address: string;
  user_agent?: string;
  details?: string;
  status: 'success' | 'failure';
}

export interface AuditLogResponse {
  events: AuditLogEvent[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface ConsentPreferences {
  marketing: boolean;
  analytics: boolean;
  essential: boolean; // Always true
}

export interface GDPRComplianceReport {
  data_categories: string[];
  retention_days: number;
  last_backup_date: string;
  processing_locations: string[];
}
