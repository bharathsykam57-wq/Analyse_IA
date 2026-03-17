import { apiClient } from "@/shared/api/client";
import { BackendResult } from "@/shared/types/agent";

export const askAgent = async (prompt: string, file_id?: string): Promise<{ task_id: string, status: string }> => {
  const response = await apiClient.post("agent/ask", {
    query: prompt,  // Backend expects 'query', not 'prompt'
    file_id: file_id,
    session_id: undefined,
    language: undefined
  });
  return response.data;
};

export const checkTaskStatus = async (task_id: string): Promise<BackendResult> => {
  const response = await apiClient.get(`agent/status/${task_id}`);
  return response.data;
};
