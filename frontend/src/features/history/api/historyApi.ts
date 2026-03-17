import { apiClient } from "@/shared/api/client";
import { HistoryResponse, HistoryFilters } from "@/shared/types/history";

/**
 * Fetch user's query history from backend
 * @param filters - Optional filters for search, date range, status
 * @returns HistoryResponse with paginated query history
 */
export const fetchHistory = async (filters?: HistoryFilters): Promise<HistoryResponse> => {
  const params = new URLSearchParams();

  if (filters?.searchQuery) params.append("search", filters.searchQuery);
  if (filters?.dateRange && filters.dateRange !== 'all') {
    params.append("date_range", filters.dateRange);
  }
  if (filters?.status && filters.status !== 'all') {
    params.append("status", filters.status);
  }
  if (filters?.page) params.append("page", String(filters.page));
  if (filters?.pageSize) params.append("page_size", String(filters.pageSize));

  const response = await apiClient.get(`agent/history${params.toString() ? '?' + params.toString() : ''}`);
  return response.data;
};

/**
 * Re-run a previous query
 * @param historyId - ID of the history item to re-run
 * @returns Task ID for the new query execution
 */
export const rerunQuery = async (historyId: string): Promise<{ task_id: string }> => {
  const response = await apiClient.post(`agent/history/${historyId}/rerun`);
  return response.data;
};
