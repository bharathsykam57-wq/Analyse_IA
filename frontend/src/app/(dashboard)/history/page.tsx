"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { HistoryItem } from "@/shared/types/history";
import { useChatStore } from "@/features/agent/store/chatStore";
import { apiClient } from "@/shared/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/Card";
import {
  History,
  Search,
  RefreshCcw,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  Filter,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { motion } from "framer-motion";

interface HistoryResponse {
  queries: HistoryItem[];
  total_count: number;
  page: number;
  page_size: number;
}

type DateRangeFilter = "last_24h" | "last_7d" | "all";
type StatusFilter = "all" | "SUCCESS" | "FAILURE";

export default function HistoryPage() {
  const router = useRouter();
  const { addMessage, setIsProcessing } = useChatStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [dateRange, setDateRange] = useState<DateRangeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const pageSize = 10;
  
  // Client-side state for history data
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Load and filter history data on mount and when filters change
  useEffect(() => {
    const loadHistory = async () => {
      try {
        setIsLoading(true);

        const offset = (page - 1) * pageSize;
        const response = await apiClient.get('/agent/history', {
          params: { limit: pageSize, offset },
        });
        const raw = response.data;

        // Map backend fields to HistoryItem shape
        let items: HistoryItem[] = (raw.history || []).map(
          (row: Record<string, unknown>) => ({
            id: String(row.id ?? ''),
            query: String(row.question ?? ''),
            result: String(row.answer_preview ?? ''),
            timestamp: String(row.created_at ?? new Date().toISOString()),
            model_used: String(row.best_model ?? ''),
            confidence: Number(row.confidence_score ?? 0),
            status: row.answer_preview ? ('SUCCESS' as const) : ('FAILURE' as const),
            task_type: String(row.task_type ?? 'analysis'),
          })
        );

        // Client-side filtering
        if (searchQuery) {
          items = items.filter(
            (item) =>
              item.query.toLowerCase().includes(searchQuery.toLowerCase()) ||
              item.result.toLowerCase().includes(searchQuery.toLowerCase())
          );
        }

        if (statusFilter !== "all") {
          items = items.filter((item) => item.status === statusFilter);
        }

        if (dateRange !== "all") {
          const cutoffMs =
            dateRange === "last_24h" ? Date.now() - 86_400_000 : Date.now() - 7 * 86_400_000;
          items = items.filter(
            (item) => new Date(item.timestamp).getTime() >= cutoffMs
          );
        }

        setData({
          queries: items,
          total_count: raw.total ?? items.length,
          page,
          page_size: pageSize,
        });
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error("Failed to load history"));
      } finally {
        setIsLoading(false);
      }
    };

    loadHistory();
  }, [searchQuery, dateRange, statusFilter, page]);

  const refetch = async () => {
    setPage(1);
  };

  const handleRerunQuery = async (item: HistoryItem) => {
    try {
      addMessage({
        id: Date.now().toString(),
        role: "user",
        content: item.query,
        timestamp: new Date().toISOString(),
      });

      setIsProcessing(true, undefined);
      router.push("/dashboard");
    } catch (err) {
      console.error("Failed to rerun query:", err);
      alert("Impossible de relancer la requête");
    }
  };

  const totalPages = data ? Math.ceil(data.total_count / pageSize) : 0;

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold font-sans text-white mb-2 tracking-tight flex items-center gap-3">
          <History className="w-8 h-8 text-blue-500" />
          Historique d&apos;Analyse
        </h1>
        <p className="text-blue-300/60 leading-relaxed">
          Consultez et relancez vos requêtes d&apos;analyse précédentes
        </p>
      </div>

      {/* Filters Section */}
      <Card className="bg-white/[0.02] border-white/5">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Filter className="w-5 h-5 text-blue-400" />
            Filtres
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="md:col-span-2">
              <label className="text-sm font-medium text-gray-300 block mb-2">
                Rechercher
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Rechercher une requête..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setPage(1);
                  }}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Date Range */}
            <div>
              <label className="text-sm font-medium text-gray-300 block mb-2">
                Période
              </label>
              <select
                value={dateRange}
                onChange={(e) => {
                  setDateRange(e.target.value as DateRangeFilter);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
              >
                <option value="last_24h">Dernières 24h</option>
                <option value="last_7d">Derniers 7 jours</option>
                <option value="all">Tout</option>
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="text-sm font-medium text-gray-300 block mb-2">
                Statut
              </label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as StatusFilter);
                  setPage(1);
                }}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
              >
                <option value="all">Tous</option>
                <option value="SUCCESS">Réussites</option>
                <option value="FAILURE">Échecs</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Loading State */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Card key={i} className="bg-white/[0.02] border-white/5 animate-pulse">
              <CardContent className="p-5">
                <div className="h-4 bg-gray-700 rounded w-1/3 mb-3" />
                <div className="h-3 bg-gray-700 rounded w-2/3 mb-2" />
                <div className="h-3 bg-gray-700 rounded w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Error State */}
      {error && (
        <Card className="bg-red-500/5 border-red-500/20">
          <CardContent className="pt-6 flex items-center gap-4 justify-between">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <p className="text-red-400">Erreur lors du chargement de l&apos;historique</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="gap-2"
            >
              <RefreshCcw className="w-4 h-4" />
              Réessayer
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!isLoading && !error && (!data || data.queries.length === 0) && (
        <Card className="bg-white/[0.02] border-white/5">
          <CardContent className="pt-12 pb-12 flex flex-col items-center justify-center text-center">
            <History className="w-12 h-12 text-gray-600 mb-4" />
            <p className="text-gray-400 mb-2">Aucune requête trouvée</p>
            <p className="text-gray-500 text-sm">
              Vos requêtes d&apos;analyse apparaîtront ici une fois exécutées
            </p>
          </CardContent>
        </Card>
      )}

      {/* History List */}
      {!isLoading && data && data.queries.length > 0 && (
        <motion.div
          className="space-y-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.05 }}
        >
          {data.queries.map((item, index) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card className="hover:bg-white/[0.06] hover:-translate-y-0.5 transition-all duration-200 group cursor-pointer bg-white/[0.02] border-white/5">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      {/* Query */}
                      <p className="text-white font-medium mb-2 truncate group-hover:text-blue-300 transition-colors">
                        {item.query}
                      </p>

                      {/* Result Summary */}
                      <p className="text-gray-400 text-sm mb-3 line-clamp-2">
                        {item.result}
                      </p>

                      {/* Metadata */}
                      <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {formatDistanceToNow(new Date(item.timestamp), {
                            locale: fr,
                            addSuffix: true,
                          })}
                        </div>

                        <div className="flex items-center gap-1">
                          {item.status === "SUCCESS" ? (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                              Réussi
                            </>
                          ) : (
                            <>
                              <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                              Échec
                            </>
                          )}
                        </div>

                        {item.model_used && (
                          <div className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300">
                            {item.model_used}
                          </div>
                        )}

                        {item.confidence && (
                          <div className="text-gray-400">
                            Confiance: {(item.confidence * 100).toFixed(0)}%
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 flex-shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRerunQuery(item)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Relancer cette requête"
                      >
                        <RefreshCcw className="w-4 h-4" />
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.push(`/dashboard?result_id=${item.id}`)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Voir le résultat complet"
                      >
                        <ArrowRight className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Page {page} sur {totalPages} ({data.total_count} résultats total)
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="gap-2"
            >
              <ChevronLeft className="w-4 h-4" />
              Précédent
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="gap-2"
            >
              Suivant
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
