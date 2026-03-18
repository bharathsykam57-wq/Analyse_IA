import { apiClient } from "@/shared/api/client";
import {
  ConsentRequest,
  ConsentResponse,
  ExportResponse,
  ErasureResponse,
  AuditLogResponse,
} from "@/shared/types/rgpd";

/**
 * Export all personal data (RGPD Articles 15/20)
 */
export const exportUserData = async (): Promise<ExportResponse> => {
  const response = await apiClient.get("rgpd/export");
  return response.data;
};

/**
 * Record consent for a specific processing purpose
 */
export const recordConsent = async (payload: ConsentRequest): Promise<ConsentResponse> => {
  const response = await apiClient.post("rgpd/consent", payload);
  return response.data;
};

/**
 * Fetch active consent records for current user
 */
export const fetchConsents = async (): Promise<ConsentResponse[]> => {
  const response = await apiClient.get("rgpd/consent");
  return response.data;
};

/**
 * Fetch RGPD audit log for user
 */
export const fetchAuditLog = async (): Promise<AuditLogResponse> => {
  const response = await apiClient.get("rgpd/audit");
  return response.data;
};

/**
 * Execute RGPD erasure workflow (Article 17)
 */
export const eraseUserData = async (): Promise<ErasureResponse> => {
  const response = await apiClient.delete("rgpd/erasure");
  return response.data;
};

// Backward-compatible aliases
export const initiateDataExport = exportUserData;
export const deleteAccount = eraseUserData;
