/**
 * Format utilities for dashboard
 */

import { HistoryItem } from "@/shared/types/dashboard";

/**
 * Format file size in human-readable format
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";

  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

/**
 * Format percentage with decimal places
 */
export function formatPercentage(value: number, decimals = 0): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format confidence score
 */
export function formatConfidence(confidence: number | undefined): string {
  if (!confidence) return "N/A";
  return formatPercentage(confidence, 1);
}

/**
 * Get color class for confidence level
 */
export function getConfidenceColor(confidence: number | undefined): string {
  if (!confidence) return "text-gray-400";
  if (confidence >= 0.8) return "text-emerald-400";
  if (confidence >= 0.6) return "text-blue-400";
  if (confidence >= 0.4) return "text-yellow-400";
  return "text-red-400";
}

/**
 * Get background color class for status
 */
export function getStatusColor(
  status: "SUCCESS" | "FAILURE"
): "bg-emerald-500/10 text-emerald-300" | "bg-red-500/10 text-red-300" {
  return status === "SUCCESS"
    ? "bg-emerald-500/10 text-emerald-300"
    : "bg-red-500/10 text-red-300";
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
}

/**
 * Generate CSV from array of objects
 */
export function generateCSV<T extends Record<string, any>>(
  data: T[],
  filename: string
): void {
  if (data.length === 0) return;

  // Get headers from first object
  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(","),
    ...data.map((row) =>
      headers
        .map((header) => {
          const value = row[header];
          // Escape quotes and wrap in quotes if contains comma or quote
          if (value === null || value === undefined) return '""';
          const stringValue = String(value);
          if (stringValue.includes(",") || stringValue.includes('"')) {
            return `"${stringValue.replace(/"/g, '""')}"`;
          }
          return stringValue;
        })
        .join(",")
    ),
  ].join("\n");

  downloadFile(csvContent, filename, "text/csv");
}

/**
 * Generate JSON file from data
 */
export function generateJSON<T>(data: T, filename: string): void {
  const jsonContent = JSON.stringify(data, null, 2);
  downloadFile(jsonContent, filename, "application/json");
}

/**
 * Helper to download file
 */
export function downloadFile(
  content: string | Blob,
  filename: string,
  mimeType: string
): void {
  const blob =
    content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Validation utilities
 */

export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

export function validatePassword(password: string): {
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push("Le mot de passe doit contenir au moins 8 caractères");
  }
  if (!/[A-Z]/.test(password)) {
    errors.push("Le mot de passe doit contenir au moins une lettre majuscule");
  }
  if (!/[a-z]/.test(password)) {
    errors.push("Le mot de passe doit contenir au moins une lettre minuscule");
  }
  if (!/[0-9]/.test(password)) {
    errors.push("Le mot de passe doit contenir au moins un chiffre");
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

/**
 * Sorting utilities
 */

export function sortHistoryItems(
  items: HistoryItem[],
  sortBy: "date" | "confidence" | "status"
): HistoryItem[] {
  const sorted = [...items];

  switch (sortBy) {
    case "date":
      return sorted.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
    case "confidence":
      return sorted.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    case "status":
      return sorted.sort((a, b) => a.status.localeCompare(b.status));
    default:
      return sorted;
  }
}

/**
 * Filter utilities
 */

export function filterHistoryItems(
  items: HistoryItem[],
  filters: {
    searchQuery?: string;
    status?: "all" | "SUCCESS" | "FAILURE";
    minConfidence?: number;
  }
): HistoryItem[] {
  return items.filter((item) => {
    // Filter by search query
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      const matchesQuery =
        item.query.toLowerCase().includes(query) ||
        item.result.toLowerCase().includes(query);
      if (!matchesQuery) return false;
    }

    // Filter by status
    if (filters.status && filters.status !== "all") {
      if (item.status !== filters.status) return false;
    }

    // Filter by minimum confidence
    if (filters.minConfidence !== undefined) {
      if (!item.confidence || item.confidence < filters.minConfidence) {
        return false;
      }
    }

    return true;
  });
}

/**
 * API key utilities
 */

export function maskApiKey(key: string): string {
  if (key.length < 8) return key;
  const firstPart = key.substring(0, key.length - 4);
  const lastPart = key.substring(key.length - 4);
  return `${firstPart}${"*".repeat(Math.min(10, firstPart.length))}${lastPart}`;
}

export function generateShortKey(key: string): string {
  if (key.length < 10) return key;
  return key.substring(0, 8) + "..." + key.substring(key.length - 4);
}

/**
 * Time utilities
 */

export function getTimeAgo(date: Date | string): string {
  const now = new Date();
  const targetDate = typeof date === "string" ? new Date(date) : date;
  const diffInSeconds = Math.floor((now.getTime() - targetDate.getTime()) / 1000);

  if (diffInSeconds < 60) return "À l'instant";
  if (diffInSeconds < 3600) return `Il y a ${Math.floor(diffInSeconds / 60)}m`;
  if (diffInSeconds < 86400) return `Il y a ${Math.floor(diffInSeconds / 3600)}h`;
  if (diffInSeconds < 2592000)
    return `Il y a ${Math.floor(diffInSeconds / 86400)}j`;

  return targetDate.toLocaleDateString("fr-FR");
}

/**
 * Statistics utilities
 */

export interface DashboardStats {
  totalQueries: number;
  successRate: number;
  averageConfidence: number;
  totalRequests: number;
}

export function calculateStats(items: HistoryItem[]): DashboardStats {
  if (items.length === 0) {
    return {
      totalQueries: 0,
      successRate: 0,
      averageConfidence: 0,
      totalRequests: 0,
    };
  }

  const successCount = items.filter((item) => item.status === "SUCCESS").length;
  const confidenceValues = items
    .filter((item) => item.confidence !== undefined)
    .map((item) => item.confidence as number);
  const avgConfidence =
    confidenceValues.length > 0
      ? confidenceValues.reduce((a, b) => a + b, 0) / confidenceValues.length
      : 0;

  return {
    totalQueries: items.length,
    successRate: (successCount / items.length) * 100,
    averageConfidence: avgConfidence,
    totalRequests: items.length,
  };
}

/**
 * Error handling utilities
 */

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  if (typeof error === "object" && error !== null && "message" in error) {
    return String((error as any).message);
  }
  return "Une erreur s'est produite";
}

export function handleApiError(status: number, message?: string): string {
  const errorMessages: Record<number, string> = {
    400: "Requête invalide",
    401: "Non authentifié",
    403: "Accès refusé",
    404: "Non trouvé",
    500: "Erreur serveur",
    503: "Service indisponible",
  };

  return message || errorMessages[status] || "Une erreur s'est produite";
}
