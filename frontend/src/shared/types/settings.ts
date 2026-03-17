export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  preferred_language: 'fr' | 'en';
  created_at: string; // ISO datetime
  last_login: string; // ISO datetime
}

export interface ProfileUpdateRequest {
  full_name?: string;
  preferred_language?: 'fr' | 'en';
}

export interface UserPreferences {
  language: 'fr' | 'en';
  theme: 'dark' | 'light';
  notifications: {
    on_task_completion: boolean;
    weekly_summary: boolean;
    security_alerts: boolean;
  };
  marketing_consent: boolean;
  analytics_consent: boolean;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface UpdatePreferencesRequest {
  preferences: UserPreferences;
}
