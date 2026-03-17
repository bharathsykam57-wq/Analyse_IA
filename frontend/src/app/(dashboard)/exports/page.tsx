"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import {
  Download,
  FileJson,
  FileText,
  Database,
  Settings,
  History,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { motion } from "framer-motion";
import { format } from "date-fns";

interface ExportOption {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  formats: ("csv" | "json" | "excel")[];
  dataSize?: string;
}

const exportOptions: ExportOption[] = [
  {
    id: "history",
    title: "Historique d'Analyse",
    description: "Exporte toutes vos requêtes et résultats d'analyse",
    icon: <History className="w-6 h-6" />,
    formats: ["csv", "json"],
    dataSize: "2.4 MB",
  },
  {
    id: "settings",
    title: "Paramètres",
    description: "Exporte vos préférences et configurations",
    icon: <Settings className="w-6 h-6" />,
    formats: ["json"],
    dataSize: "150 KB",
  },
  {
    id: "models",
    title: "Données des Modèles",
    description: "Exporte les résultats d'entraînement des modèles",
    icon: <Database className="w-6 h-6" />,
    formats: ["csv", "json"],
    dataSize: "5.1 MB",
  },
  {
    id: "results",
    title: "Résultats Détaillés",
    description: "Exporte tous les résultats d'analyse avec métadonnées",
    icon: <FileText className="w-6 h-6" />,
    formats: ["csv", "json", "excel"],
    dataSize: "8.7 MB",
  },
];

export default function ExportsPage() {
  const [selectedFormat, setSelectedFormat] = useState<Record<string, string>>({});
  const [exportedItems, setExportedItems] = useState<Set<string>>(new Set());
  const [isExporting, setIsExporting] = useState<Set<string>>(new Set());
  
  // Client-side state for export stats
  const [stats, setStats] = useState<any | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Load export stats on mount
  useEffect(() => {
    const loadStats = async () => {
      try {
        setStatsLoading(true);
        await new Promise((resolve) => setTimeout(resolve, 300));
        setStats({
          total_queries: 42,
          total_models: 15,
          total_results: 127,
          last_export: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
          storage_used: "16.2 MB",
        });
      } catch (error) {
        console.error("Failed to load export stats:", error);
      } finally {
        setStatsLoading(false);
      }
    };

    loadStats();
  }, []);

  const handleExport = async (optionId: string, format: string) => {
    setIsExporting((prev) => new Set(prev).add(`${optionId}-${format}`));

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Trigger download
    const now = new Date();
    const timestamp = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}-${String(now.getMinutes()).padStart(2, "0")}-${String(now.getSeconds()).padStart(2, "0")}`;
    const filename = `${optionId}_export_${timestamp}.${format}`;
    const blob = new Blob([`Export data for ${optionId}`], {
      type: format === "json" ? "application/json" : "text/csv",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);

    setExportedItems((prev) => new Set(prev).add(`${optionId}-${format}`));
    setIsExporting((prev) => {
      const next = new Set(prev);
      next.delete(`${optionId}-${format}`);
      return next;
    });

    // Clear success indicator after 3 seconds
    setTimeout(() => {
      setExportedItems((prev) => {
        const next = new Set(prev);
        next.delete(`${optionId}-${format}`);
        return next;
      });
    }, 3000);
  };

  const handleExportAll = async () => {
    // Export all formats for all options
    for (const option of exportOptions) {
      for (const format of option.formats) {
        await handleExport(option.id, format);
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
    }
  };

  return (
    <div className="p-6 md:p-10 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold font-sans text-white mb-2 tracking-tight flex items-center gap-3">
          <Download className="w-8 h-8 text-blue-500" />
          Exporter vos Données
        </h1>
        <p className="text-blue-300/60 leading-relaxed">
          Téléchargez vos données dans différents formats pour sauvegarde ou analyse externe
        </p>
      </div>

      {/* Stats Section */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-white/[0.02] border-white/5">
            <CardContent className="pt-6 pb-4">
              <div className="text-gray-400 text-sm mb-1">Requêtes</div>
              <div className="text-2xl font-bold text-white">{stats.total_queries}</div>
            </CardContent>
          </Card>

          <Card className="bg-white/[0.02] border-white/5">
            <CardContent className="pt-6 pb-4">
              <div className="text-gray-400 text-sm mb-1">Modèles</div>
              <div className="text-2xl font-bold text-white">{stats.total_models}</div>
            </CardContent>
          </Card>

          <Card className="bg-white/[0.02] border-white/5">
            <CardContent className="pt-6 pb-4">
              <div className="text-gray-400 text-sm mb-1">Résultats</div>
              <div className="text-2xl font-bold text-white">{stats.total_results}</div>
            </CardContent>
          </Card>

          <Card className="bg-white/[0.02] border-white/5">
            <CardContent className="pt-6 pb-4">
              <div className="text-gray-400 text-sm mb-1">Stock</div>
              <div className="text-2xl font-bold text-white">{stats.storage_used}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Export Options Grid */}
      <div className="space-y-4">
        {/* Action Buttons */}
        <div className="flex gap-2 item-center">
          <Button
            onClick={handleExportAll}
            className="gap-2 bg-blue-600 hover:bg-blue-700"
          >
            <Download className="w-4 h-4" />
            Tout Exporter
          </Button>
        </div>

        {/* Export Cards */}
        <motion.div
          className="grid md:grid-cols-2 gap-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1 }}
        >
          {exportOptions.map((option, index) => (
            <motion.div
              key={option.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="bg-white/[0.02] border-white/5 hover:bg-white/[0.04] transition-all duration-200 group h-full">
                <CardHeader>
                  <div className="flex items-start justify-between mb-3">
                    <div className="text-blue-400">{option.icon}</div>
                    {option.dataSize && (
                      <span className="text-xs text-gray-500">{option.dataSize}</span>
                    )}
                  </div>
                  <CardTitle className="text-lg text-white">{option.title}</CardTitle>
                  <CardDescription className="text-gray-400 text-sm">
                    {option.description}
                  </CardDescription>
                </CardHeader>

                <CardContent>
                  <div className="space-y-3">
                    {/* Format Buttons */}
                    <div className="flex flex-wrap gap-2">
                      {option.formats.map((fmt) => {
                        const key = `${option.id}-${fmt}`;
                        const isCurrentlyExporting = isExporting.has(key);
                        const hasBeenExported = exportedItems.has(key);

                        return (
                          <Button
                            key={key}
                            variant={hasBeenExported ? "default" : "outline"}
                            size="sm"
                            onClick={() => handleExport(option.id, fmt)}
                            disabled={isCurrentlyExporting}
                            className={`gap-1.5 transition-all duration-200 ${
                              hasBeenExported
                                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                                : ""
                            }`}
                          >
                            {isCurrentlyExporting ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                {fmt.toUpperCase()}
                              </>
                            ) : hasBeenExported ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                {fmt.toUpperCase()}
                              </>
                            ) : (
                              <>
                                {fmt === "json" && <FileJson className="w-3.5 h-3.5" />}
                                {fmt === "csv" && <FileText className="w-3.5 h-3.5" />}
                                {fmt === "excel" && <Database className="w-3.5 h-3.5" />}
                                {fmt.toUpperCase()}
                              </>
                            )}
                          </Button>
                        );
                      })}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Info Section */}
      <Card className="bg-blue-500/5 border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-blue-400" />
            Information sur les Exports
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-400">
          <div>
            <p className="font-medium text-gray-300 mb-1">Format CSV</p>
            <p>Idéal pour les analyses dans Excel ou d'autres outils tableur. Données tabulaires.</p>
          </div>
          <div>
            <p className="font-medium text-gray-300 mb-1">Format JSON</p>
            <p>Format structuré avec métadonnées complètes. Meilleur pour l'intégration avec d'autres systèmes.</p>
          </div>
          <div>
            <p className="font-medium text-gray-300 mb-1">Format Excel</p>
            <p>Fichier .xlsx avec mise en forme, graphiques et plusieurs feuilles (si applicable).</p>
          </div>
          <div className="pt-2 border-t border-white/10">
            <p>
              <span className="text-gray-500">Dernier export:</span>{" "}
              <span className="text-gray-300 font-medium">
                {stats ? format(new Date(stats.last_export), "d MMMM yyyy à HH:mm") : "Jamais"}
              </span>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* GDPR Compliance Note */}
      <Card className="bg-green-500/5 border-green-500/20">
        <CardContent className="pt-6 flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-green-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <p className="text-green-300 font-medium mb-1">Conformité RGPD</p>
            <p className="text-gray-400">
              Vous pouvez à tout moment exporter ou supprimer vos données. Ces exports contiennent toutes vos
              données personnelles au format machine-readable comme exigé par le RGPD.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
