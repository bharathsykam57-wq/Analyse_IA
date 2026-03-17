import { apiClient } from "@/shared/api/client";
import { ExportStatus, ErasureResponse, AuditLogResponse, ConsentPreferences, GDPRComplianceReport } from "@/shared/types/rgpd";

/**
 * Initiate data export
 * @returns Export job info with export_id
 */
export const initiateDataExport = async (): Promise<ExportStatus> => {
  const response = await apiClient.post("rgpd/export");
  return response.data;
};

/**
 * Check export status
 * @param exportId - Export ID to check
 * @returns Current export status
 */
export const checkExportStatus = async (exportId: string): Promise<ExportStatus> => {
  const response = await apiClient.get(`rgpd/export/${exportId}`);
  return response.data;
};

/**
 * Delete user account permanently
 * @param password - User password for confirmation
 * @returns Deletion status
 */
export const deleteAccount = async (password: string): Promise<ErasureResponse> => {
  const response = await apiClient.post("rgpd/erasure", { password });
  return response.data;
};

/**
 * Fetch audit log for user
 * @param page - Page number (default 1)
 * @param pageSize - Items per page (default 10)
 * @returns Paginated audit log
 */
export const fetchAuditLog = async (page: number = 1, pageSize: number = 10): Promise<AuditLogResponse> => {
  const response = await apiClient.get(`rgpd/audit?page=${page}&page_size=${pageSize}`);
  return response.data;
};

/**
 * Update consent preferences
 * @param preferences - Consent settings
 * @returns Updated preferences
 */
export const updateConsent = async (preferences: ConsentPreferences): Promise<ConsentPreferences> => {
  const response = await apiClient.post("rgpd/consent", preferences);
  return response.data;
};

/**
 * Fetch GDPR compliance information
 * @returns Compliance report
 */
export const fetchComplianceReport = async (): Promise<GDPRComplianceReport> => {
  const response = await apiClient.get("rgpd/compliance-report");
  return response.data;
};

/**
 * Generate and download GDPR compliance PDF
 */
export const downloadCompliancePDF = async (): Promise<void> => {
  const response = await apiClient.get("rgpd/compliance-pdf", {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `GDPR-Report-${new Date().toISOString().split('T')[0]}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
};
