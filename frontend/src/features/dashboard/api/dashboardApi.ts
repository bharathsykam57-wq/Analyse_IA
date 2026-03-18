import { apiClient } from "@/shared/api/client";
import { 
  HistoryResponse, 
  HistoryFilters,
  ExportStats,
  Account,
  ApiKey,
  UserSettings,
} from "@/shared/types/dashboard";

interface AccountSession {
  id: string;
  device?: string;
  browser?: string;
  lastActive?: string;
  isCurrent?: boolean;
  ipAddress?: string;
}

type ConsentStatus = Record<string, boolean | string | number | null>;
type FaqItem = Record<string, unknown>;
type TutorialItem = Record<string, unknown>;
type ApiDoc = Record<string, unknown>;

/**
 * History API Functions
 */
export const historyApi = {
  async fetchHistory(filters: HistoryFilters): Promise<HistoryResponse> {
    const queryParams = new URLSearchParams({
      page: filters.page.toString(),
      page_size: filters.pageSize.toString(),
      date_range: filters.dateRange,
      status: filters.status,
      ...(filters.searchQuery && { query: filters.searchQuery }),
    });

    const response = await apiClient.get<HistoryResponse>(
      `/api/history?${queryParams}`
    );
    return response.data;
  },

  async rerunQuery(historyId: string): Promise<{ task_id: string }> {
    const response = await apiClient.post<{ task_id: string }>(
      `/api/history/${historyId}/rerun`
    );
    return response.data;
  },

  async deleteHistoryItem(historyId: string): Promise<void> {
    await apiClient.delete(`/api/history/${historyId}`);
  },

  async clearHistory(): Promise<void> {
    await apiClient.delete(`/api/history`);
  },

  async exportHistory(format: "csv" | "json"): Promise<Blob> {
    const response = await apiClient.get<Blob>(
      `/api/history/export?format=${format}`,
      { responseType: "blob" }
    );
    return response.data;
  },
};

/**
 * Exports API Functions
 */
export const exportsApi = {
  async getExportStats(): Promise<ExportStats> {
    const response = await apiClient.get<ExportStats>("/api/exports/stats");
    return response.data;
  },

  async exportData(
    optionId: string,
    format: "csv" | "json" | "excel"
  ): Promise<Blob> {
    const response = await apiClient.get<Blob>(
      `/api/exports/${optionId}?format=${format}`,
      { responseType: "blob" }
    );
    return response.data;
  },

  async exportAll(format: "csv" | "json" | "excel"): Promise<Blob> {
    const response = await apiClient.get<Blob>(
      `/api/exports/all?format=${format}`,
      { responseType: "blob" }
    );
    return response.data;
  },
};

/**
 * Settings API Functions
 */
export const settingsApi = {
  async getSettings(): Promise<UserSettings> {
    const response = await apiClient.get<UserSettings>("/api/settings");
    return response.data;
  },

  async updateSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
    const response = await apiClient.put<UserSettings>("/api/settings", settings);
    return response.data;
  },

  async updatePassword(data: {
    current_password: string;
    new_password: string;
  }): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>("/api/settings/password", data);
    return response.data;
  },

  async enableTwoFactor(): Promise<{ secret: string; qr_code: string }> {
    const response = await apiClient.post<{ secret: string; qr_code: string }>("/api/settings/2fa/enable");
    return response.data;
  },

  async disableTwoFactor(code: string): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>("/api/settings/2fa/disable", { code });
    return response.data;
  },

  async exportData(): Promise<Blob> {
    const response = await apiClient.get<Blob>("/api/settings/export", {
      responseType: "blob",
    });
    return response.data;
  },

  async deleteAccount(password: string): Promise<{ message: string }> {
    const response = await apiClient.delete<{ message: string }>("/api/account", { data: { password } });
    return response.data;
  },
};

/**
 * Account API Functions
 */
export const accountApi = {
  async getAccount(): Promise<Account> {
    const response = await apiClient.get<Account>("/api/account");
    return response.data;
  },

  async updateProfile(data: {
    name?: string;
    profile_picture?: File;
  }): Promise<Account> {
    const formData = new FormData();
    if (data.name) formData.append("name", data.name);
    if (data.profile_picture) formData.append("profile_picture", data.profile_picture);

    const response = await apiClient.post<Account>("/api/account/profile", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  async getApiKeys(): Promise<ApiKey[]> {
    const response = await apiClient.get<ApiKey[]>("/api/account/api-keys");
    return response.data;
  },

  async createApiKey(name: string): Promise<ApiKey> {
    const response = await apiClient.post<ApiKey>("/api/account/api-keys", { name });
    return response.data;
  },

  async regenerateApiKey(keyId: string): Promise<ApiKey> {
    const response = await apiClient.put<ApiKey>(`/api/account/api-keys/${keyId}/regenerate`);
    return response.data;
  },

  async deleteApiKey(keyId: string): Promise<void> {
    await apiClient.delete(`/api/account/api-keys/${keyId}`);
  },

  async getSessions(): Promise<AccountSession[]> {
    const response = await apiClient.get<AccountSession[]>("/api/account/sessions");
    return response.data;
  },

  async logoutAllSessions(): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>("/api/account/sessions/logout-all");
    return response.data;
  },

  async logoutSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/api/account/sessions/${sessionId}`);
  },
};

/**
 * GDPR API Functions
 */
export const gdprApi = {
  async exportPersonalData(): Promise<Blob> {
    const response = await apiClient.get<Blob>("/api/gdpr/export", {
      responseType: "blob",
    });
    return response.data;
  },

  async deletePersonalData(): Promise<{ message: string }> {
    const response = await apiClient.delete<{ message: string }>("/api/gdpr/delete");
    return response.data;
  },

  async getConsentStatus(): Promise<ConsentStatus> {
    const response = await apiClient.get<ConsentStatus>("/api/gdpr/consent");
    return response.data;
  },

  async updateConsent(consent: Record<string, boolean>): Promise<ConsentStatus> {
    const response = await apiClient.put<ConsentStatus>("/api/gdpr/consent", consent);
    return response.data;
  },
};

/**
 * Documentation API Functions
 */
export const docsApi = {
  async searchFaqs(query: string): Promise<FaqItem[]> {
    const response = await apiClient.get<FaqItem[]>("/api/docs/faq/search", {
      params: { q: query },
    });
    return response.data;
  },

  async getTutorials(): Promise<TutorialItem[]> {
    const response = await apiClient.get<TutorialItem[]>("/api/docs/tutorials");
    return response.data;
  },

  async getTutorial(id: string): Promise<TutorialItem> {
    const response = await apiClient.get<TutorialItem>(`/api/docs/tutorials/${id}`);
    return response.data;
  },

  async getApiDocumentation(): Promise<ApiDoc> {
    const response = await apiClient.get<ApiDoc>("/api/docs/api");
    return response.data;
  },
};

/**
 * Analytics API Functions
 */
export const analyticsApi = {
  async trackEvent(eventName: string, data?: Record<string, unknown>): Promise<void> {
    // Don't await, just fire and forget
    apiClient.post("/api/analytics/events", { event: eventName, data });
  },

  async trackPageView(page: string): Promise<void> {
    apiClient.post("/api/analytics/pageviews", { page });
  },
};

const dashboardApi = {
  history: historyApi,
  exports: exportsApi,
  settings: settingsApi,
  account: accountApi,
  gdpr: gdprApi,
  docs: docsApi,
  analytics: analyticsApi,
};

export default dashboardApi;
