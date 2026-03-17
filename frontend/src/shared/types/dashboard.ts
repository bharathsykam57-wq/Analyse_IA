// History Related Types
export interface HistoryItem {
  id: string;
  query: string;
  result: string;
  timestamp: string;
  status: "SUCCESS" | "FAILURE";
  model_used?: string;
  confidence?: number;
  tags?: string[];
}

export interface HistoryFilters {
  searchQuery?: string;
  dateRange: "last_24h" | "last_7d" | "all";
  status: "all" | "SUCCESS" | "FAILURE";
  page: number;
  pageSize: number;
}

export interface HistoryResponse {
  queries: HistoryItem[];
  total_count: number;
  page: number;
  page_size: number;
}

// Settings Related Types
export interface UserSettings {
  id: string;
  user_id: string;
  language: "fr" | "en";
  theme: "dark" | "light";
  notifications_enabled: boolean;
  email_notifications: boolean;
  default_model: string;
  temperature: number;
  max_tokens: number;
  sidebar_collapsed: boolean;
  auto_save_enabled: boolean;
  created_at: string;
  updated_at: string;
}

// Account Related Types
export interface Account {
  id: string;
  email: string;
  name: string;
  profile_picture_url?: string | null;
  created_at: string;
  subscription_plan: "free" | "pro" | "enterprise";
  provider_type: "password" | "oauth";
  two_factor_enabled: boolean;
  is_verified: boolean;
  preferred_language: "fr" | "en";
}

export interface ApiKey {
  id: string;
  name: string;
  key: string;
  shortKey: string;
  created_at: string;
  last_used?: string | null;
  is_active: boolean;
  expires_at?: string | null;
}

// Export Related Types
export interface ExportOption {
  id: string;
  title: string;
  description: string;
  formats: ("csv" | "json" | "excel")[];
  dataSize?: string;
  isAvailable: boolean;
}

export interface ExportRequest {
  optionId: string;
  format: "csv" | "json" | "excel";
  filters?: Record<string, any>;
}

export interface ExportStats {
  total_queries: number;
  total_models: number;
  total_results: number;
  last_export: string;
  storage_used: string;
}

// FAQ Related Types
export interface FAQ {
  id: string;
  category: "general" | "technical" | "data" | "models" | "account";
  question: string;
  answer: string;
  tags?: string[];
  helpfulCount?: number;
}

export interface Tutorial {
  id: string;
  title: string;
  description: string;
  content?: string;
  duration: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  videoUrl?: string;
  lastUpdated: string;
  tags?: string[];
}

// Navigation Related Types
export interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  badge?: string | number;
  isActive?: boolean;
  children?: NavItem[];
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Error Types
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
  statusCode: number;
}

// Form Input Types
export interface SettingsFormData {
  language: "fr" | "en";
  theme: "dark" | "light";
  notifications_enabled: boolean;
  email_notifications: boolean;
  default_model: string;
  temperature: number;
  max_tokens: number;
  sidebar_collapsed: boolean;
  auto_save_enabled: boolean;
}

export interface ProfileFormData {
  name: string;
  email: string;
  profile_picture?: File;
}

export interface PasswordChangeData {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

// Session Types
export interface Session {
  id: string;
  device: string;
  browser: string;
  lastActive: string;
  isCurrent: boolean;
  ipAddress?: string;
}

// Consent Types
export interface ConsentData {
  analytics: boolean;
  marketing: boolean;
  necessary: boolean;
  timestamp: string;
}

// Audit Log Types
export interface AuditLog {
  id: string;
  action: string;
  resource: string;
  timestamp: string;
  user_id: string;
  details?: Record<string, any>;
}
