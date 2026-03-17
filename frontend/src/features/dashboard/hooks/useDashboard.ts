import { useState, useCallback } from "react";
import { exportsApi } from "@/features/dashboard/api/dashboardApi";
import { analyticsApi } from "@/features/dashboard/api/dashboardApi";

/**
 * Hook for managing exports
 */
export function useExport() {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const exportData = useCallback(
    async (optionId: string, format: "csv" | "json" | "excel") => {
      try {
        setIsExporting(true);
        setError(null);
        setSuccess(false);

        const blob = await exportsApi.exportData(optionId, format);

        // Trigger download
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `export_${optionId}_${Date.now()}.${format}`;
        a.click();
        URL.revokeObjectURL(url);

        setSuccess(true);
        analyticsApi.trackEvent("export_completed", { optionId, format });

        // Clear success after 3 seconds
        setTimeout(() => setSuccess(false), 3000);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Export failed";
        setError(message);
        analyticsApi.trackEvent("export_failed", { optionId, format, error: message });
      } finally {
        setIsExporting(false);
      }
    },
    []
  );

  const exportAll = useCallback(async (format: "csv" | "json" | "excel") => {
    try {
      setIsExporting(true);
      setError(null);
      setSuccess(false);

      const blob = await exportsApi.exportAll(format);

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `all_data_${Date.now()}.${format}`;
      a.click();
      URL.revokeObjectURL(url);

      setSuccess(true);
      analyticsApi.trackEvent("export_all_completed", { format });

      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Export failed";
      setError(message);
      analyticsApi.trackEvent("export_all_failed", { format, error: message });
    } finally {
      setIsExporting(false);
    }
  }, []);

  const reset = useCallback(() => {
    setError(null);
    setSuccess(false);
  }, []);

  return { isExporting, error, success, exportData, exportAll, reset };
}

/**
 * Hook for managing API keys
 */
export function useApiKeys() {
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const toggleShowKey = useCallback((keyId: string) => {
    setShowKey((prev) => ({ ...prev, [keyId]: !prev[keyId] }));
  }, []);

  const copyToClipboard = useCallback((key: string, id: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  }, []);

  return { showKey, copiedKey, toggleShowKey, copyToClipboard };
}

/**
 * Hook for managing form state with auto-save
 */
export function useAutoSaveForm<T extends Record<string, any>>(
  initialValues: T,
  onSave: (values: T) => Promise<void>,
  debounceMs = 1000
) {
  const [values, setValues] = useState<T>(initialValues);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setError] = useState<string | null>(null);
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null);

  const handleChange = useCallback(
    (newValues: Partial<T>) => {
      const updated = { ...values, ...newValues };
      setValues(updated);
      setIsDirty(true);
      setError(null);

      // Clear previous timeout
      if (timeoutId) clearTimeout(timeoutId);

      // Set new timeout
      const newTimeoutId = setTimeout(async () => {
        try {
          setIsSaving(true);
          await onSave(updated);
          setIsDirty(false);
          analyticsApi.trackEvent("form_auto_saved");
        } catch (err) {
          const message = err instanceof Error ? err.message : "Save failed";
          setError(message);
        } finally {
          setIsSaving(false);
        }
      }, debounceMs);

      setTimeoutId(newTimeoutId);
    },
    [values, onSave, debounceMs, timeoutId]
  );

  return {
    values,
    isDirty,
    isSaving,
    error: saveError,
    handleChange,
  };
}

/**
 * Hook for managing modal/dialog state
 */
export function useModal() {
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  return { isOpen, open, close, toggle };
}

/**
 * Hook for tracking analytics events
 */
export function useAnalytics() {
  const trackEvent = useCallback(
    (eventName: string, data?: Record<string, any>) => {
      analyticsApi.trackEvent(eventName, data);
    },
    []
  );

  const trackPageView = useCallback((page: string) => {
    analyticsApi.trackPageView(page);
  }, []);

  return { trackEvent, trackPageView };
}

/**
 * Hook for managing tabs
 */
export function useTabs(defaultTab: string) {
  const [activeTab, setActiveTab] = useState(defaultTab);

  const switchTab = useCallback((tab: string) => {
    setActiveTab(tab);
    analyticsApi.trackEvent("tab_switched", { tab });
  }, []);

  return { activeTab, switchTab };
}

/**
 * Hook for managing search with debounce
 */
export function useSearch(onSearch: (query: string) => void, debounceMs = 300) {
  const [query, setQuery] = useState("");
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null);

  const handleSearch = useCallback(
    (searchQuery: string) => {
      setQuery(searchQuery);

      if (timeoutId) clearTimeout(timeoutId);

      const newTimeoutId = setTimeout(() => {
        onSearch(searchQuery);
        analyticsApi.trackEvent("search_performed", { query: searchQuery });
      }, debounceMs);

      setTimeoutId(newTimeoutId);
    },
    [onSearch, debounceMs, timeoutId]
  );

  const reset = useCallback(() => {
    setQuery("");
    if (timeoutId) clearTimeout(timeoutId);
  }, [timeoutId]);

  return { query, handleSearch, reset };
}

/**
 * Hook for managing pagination
 */
export function usePagination(initialPage = 1, pageSize = 10) {
  const [page, setPage] = useState(initialPage);
  const [totalPages, setTotalPages] = useState(1);

  const goToPage = useCallback((newPage: number) => {
    const maxPage = Math.max(1, totalPages);
    if (newPage >= 1 && newPage <= maxPage) {
      setPage(newPage);
      analyticsApi.trackEvent("pagination", { page: newPage });
    }
  }, [totalPages]);

  const nextPage = useCallback(() => {
    goToPage(page + 1);
  }, [page, goToPage]);

  const prevPage = useCallback(() => {
    goToPage(page - 1);
  }, [page, goToPage]);

  const resetPagination = useCallback(() => {
    setPage(initialPage);
  }, [initialPage]);

  return {
    page,
    pageSize,
    totalPages,
    setTotalPages,
    goToPage,
    nextPage,
    prevPage,
    resetPagination,
  };
}
