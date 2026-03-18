export type RgpdPurpose =
  | "data_analysis"
  | "rag_indexing"
  | "agent_query"
  | "code_execution";

export interface ConsentRequest {
  purpose: RgpdPurpose;
  granted: boolean;
}

export interface ConsentResponse {
  id: string;
  purpose: RgpdPurpose;
  granted: boolean;
  granted_at: string;
  revoked_at?: string | null;
}

export interface AuditLogEvent {
  id: string;
  action: string;
  resource?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export type AuditLogResponse = AuditLogEvent[];

export interface ExportResponse {
  user_id: string;
  email: string;
  full_name?: string | null;
  preferred_language: "fr" | "en";
  created_at: string;
  consents: ConsentResponse[];
  audit_logs: AuditLogEvent[];
}

export interface ErasureResponse {
  message: string;
  user_id: string;
  deleted_at: string;
}
