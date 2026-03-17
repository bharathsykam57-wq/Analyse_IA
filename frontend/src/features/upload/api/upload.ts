import { apiClient } from "@/shared/api/client";

export interface UploadedFile {
  file_id: string;
  filename: string;
  size_bytes: number;
  type: string;
  uploaded_at: string;
}

export const uploadFile = async (
  file: File, 
  type: 'csv' | 'pdf', 
  onProgress?: (progress: number) => void
): Promise<UploadedFile> => {
  const formData = new FormData();
  formData.append("file", file);

  const endpoint = type === 'csv' ? "files/upload/csv" : "files/upload/pdf";

  const response = await apiClient.post(endpoint, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        onProgress(percentCompleted);
      }
    },
  });

  return response.data;
};

export const fetchFiles = async (): Promise<UploadedFile[]> => {
  const response = await apiClient.get("files/list");
  // Backend returns { files: [...], total: n }, extract the files array
  return Array.isArray(response.data) ? response.data : (response.data.files || []);
};
