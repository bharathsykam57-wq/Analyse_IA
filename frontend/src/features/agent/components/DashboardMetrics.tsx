import { AnalysisResult } from "@/shared/types/agent";
import { Card, CardHeader, CardTitle, CardContent } from "@/shared/components/ui/Card";
import { Activity, Database, AlertTriangle, TrendingUp, BarChart4 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/shared/lib/utils";

const MODEL_SPECIAL_CASES: Record<string, string> = {
  lightgbm: "LightGBM",
  lgbm: "LightGBM",
  xgboost: "XGBoost",
  xgb: "XGBoost",
  svm: "SVM",
  knn: "KNN",
  mlp: "MLP",
};

function formatModelName(name: string): string {
  if (!name || name === "N/A") return name;
  const lower = name.toLowerCase().replace(/_/g, "");
  if (MODEL_SPECIAL_CASES[lower]) return MODEL_SPECIAL_CASES[lower];
  return name
    .replace(/_/g, " ")
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

interface DashboardMetricsProps {
  data: AnalysisResult;
  className?: string;
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  colorClass: string;
  cardClassName?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, colorClass, cardClassName }: StatCardProps) {
  return (
    <Card className={cn("border-border/50 bg-black/20 backdrop-blur-sm group hover:-translate-y-1 hover:shadow-lg hover:shadow-blue-900/20 hover:border-blue-500/30 transition-all duration-300 cursor-default", cardClassName)}>
      <CardContent className="p-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-white/0 via-white/5 to-white/0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
        <div className="flex items-center justify-between space-y-0 pb-2 relative z-10">
          <p className="text-sm font-medium text-gray-400 group-hover:text-gray-300 transition-colors">{title}</p>
          <div className={cn("p-2 rounded-lg group-hover:scale-110 transition-transform duration-300", colorClass)}>
            <Icon className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-2 relative z-10">
          <p className="text-2xl font-bold text-white tracking-tight">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardMetrics({ data, className }: DashboardMetricsProps) {
  
  // Safely extract data with fallbacks for actual backend structure
  const rows = data?.rows || 0;
  const columns = data?.columns || 0;
  const anomalies = data?.anomalies || { high: 0, medium: 0, low: 0, total: 0, percentage: 0 };
  const best_model = data?.best_model || data?.model || "N/A";
  const metrics = data?.metrics || {};
  const baseMetrics = data?.base_metrics || {};
  const tunedMetrics = data?.tuned_metrics || {};
  const tuningApplied = Boolean(data?.tuning_applied);
  const baseModelName = data?.base_model_name;
  const comparison = data?.comparison || [];
  const top_features = data?.top_features || [];

  const pickMetric = (bucket: Record<string, number>, keys: string[]) => {
    for (const key of keys) {
      const value = bucket?.[key];
      if (typeof value === "number" && Number.isFinite(value)) {
        return value;
      }
    }
    return undefined;
  };

  const selectedScore =
    pickMetric(metrics, ["Accuracy", "accuracy", "R2", "r2", "AUC", "auc", "F1", "f1"]) ?? 0;
  const selectedMetricLabel =
    pickMetric(metrics, ["Accuracy", "accuracy"]) !== undefined
      ? "Accuracy"
      : pickMetric(metrics, ["R2", "r2"]) !== undefined
      ? "R²"
      : pickMetric(metrics, ["AUC", "auc"]) !== undefined
      ? "AUC"
      : pickMetric(metrics, ["F1", "f1"]) !== undefined
      ? "F1"
      : "Score";

  const baseScore = pickMetric(baseMetrics, ["Accuracy", "accuracy", "R2", "r2"]);
  const tunedScore = pickMetric(tunedMetrics, ["Accuracy", "accuracy", "R2", "r2"]);
  
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* 1. Top Level Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Modèle Optimal"
          value={formatModelName(best_model)}
          subtitle={
            tuningApplied
              ? `Tuning appliqué${baseModelName ? ` (base: ${baseModelName})` : ""}`
              : `Sélectionné via Auto-ML`
          }
          icon={Activity}
          colorClass="bg-blue-500/10 text-blue-500"
          cardClassName={className}
        />
        <StatCard
          title="Volume de Données"
          value={rows.toLocaleString?.() || rows}
          subtitle={`${columns} variables analysées`}
          icon={Database}
          colorClass="bg-emerald-500/10 text-emerald-500"
          cardClassName={className}
        />
        <StatCard
          title="Taux d'Anomalies"
          value={`${anomalies?.percentage || 0}%`}
          subtitle={`${anomalies?.total || 0} détectées au total`}
          icon={AlertTriangle}
          colorClass="bg-amber-500/10 text-amber-500"
          cardClassName={className}
        />
        <StatCard
          title="Performance"
          value={(selectedScore * 100).toFixed(1) + "%"}
          subtitle={`Métrique principale (${selectedMetricLabel})`}
          icon={TrendingUp}
          colorClass="bg-indigo-500/10 text-indigo-500"
          cardClassName={className}
        />
      </div>

      {(baseScore !== undefined || tunedScore !== undefined || comparison.length > 0) && (
        <Card className="border-border/50 bg-black/20">
          <CardHeader className="pb-2 text-white">
            <CardTitle className="text-lg">AutoML — Base vs Tuned</CardTitle>
          </CardHeader>
          <CardContent className="pt-2 text-sm text-gray-300 space-y-2">
            {baseScore !== undefined && <p>Base score: {(baseScore * 100).toFixed(1)}%</p>}
            {tunedScore !== undefined && <p>Tuned score: {(tunedScore * 100).toFixed(1)}%</p>}
            {comparison.length > 0 && <p>Modèles comparés: {comparison.length}</p>}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* 2. Feature Importance Chart (Mocked UI visualization) */}
        <Card className="border-border/50 bg-black/20 group hover:border-blue-500/20 transition-all duration-300 hover:shadow-xl hover:shadow-blue-900/10">
          <CardHeader className="pb-2 text-white">
            <CardTitle className="text-lg flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <BarChart4 className="w-5 h-5 text-blue-400" />
                Facteurs d’Influence Clés
              </div>
              <button className="text-xs font-normal text-blue-400 hover:text-white px-2 py-1 rounded-md hover:bg-blue-500/20 transition-colors">
                Explorer
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            {(top_features || []).map((feature, i) => {
              const featureName = feature.feature ?? feature.name ?? "—";
              const pct = typeof feature.importance === "number"
                ? parseFloat((feature.importance * 100).toFixed(1))
                : (feature.importance_percentage ?? 0);
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-32 text-xs text-gray-400 truncate flex-shrink-0" title={featureName}>
                    {featureName}
                  </span>
                  <div className="flex-1 bg-white/10 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all duration-700"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-10 text-xs text-gray-400 text-right flex-shrink-0">{pct}%</span>
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* 3. Distribution of Anomalies */}
        <Card className="border-border/50 bg-black/20 group hover:border-amber-500/20 transition-all duration-300 hover:shadow-xl hover:shadow-amber-900/10 cursor-default">
          <CardHeader className="pb-2 text-white">
            <CardTitle className="text-lg flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                 <AlertTriangle className="w-5 h-5 text-amber-400" />
                 Sévérité des Anomalies
              </div>
              <button className="text-xs font-normal text-gray-400 hover:text-white px-2 py-1 rounded-md hover:bg-white/10 transition-colors">
                Détails
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
             <div className="flex h-32 items-end justify-center gap-8">
                
                <div className="flex flex-col items-center gap-2 group/bar">
                   <span className="text-xs text-gray-500 font-medium font-mono group-hover/bar:text-red-400 transition-colors group-hover/bar:-translate-y-1">{anomalies?.high || 0}</span>
                   <div 
                     className="w-16 bg-red-500/80 rounded-t-md group-hover/bar:bg-red-400 transition-all duration-500 ease-out group-hover/bar:w-20 cursor-pointer shadow-[0_0_15px_rgba(239,68,68,0)] group-hover/bar:shadow-[0_0_15px_rgba(239,68,68,0.5)]"
                     style={{ height: `${Math.max(20, ((anomalies?.high || 0) / (anomalies?.total || 1)) * 100)}%` }}
                   />
                   <span className="text-sm font-medium text-red-500 group-hover/bar:text-red-400">Haute</span>
                </div>

                <div className="flex flex-col items-center gap-2 group/bar">
                   <span className="text-xs text-gray-500 font-medium font-mono group-hover/bar:text-amber-400 transition-colors group-hover/bar:-translate-y-1">{anomalies?.medium || 0}</span>
                   <div 
                     className="w-16 bg-amber-500/80 rounded-t-md group-hover/bar:bg-amber-400 transition-all duration-500 ease-out group-hover/bar:w-20 cursor-pointer shadow-[0_0_15px_rgba(245,158,11,0)] group-hover/bar:shadow-[0_0_15px_rgba(245,158,11,0.5)]"
                     style={{ height: `${Math.max(20, ((anomalies?.medium || 0) / (anomalies?.total || 1)) * 100)}%` }}
                   />
                   <span className="text-sm font-medium text-amber-500 group-hover/bar:text-amber-400">Moyenne</span>
                </div>

                <div className="flex flex-col items-center gap-2 group/bar">
                   <span className="text-xs text-gray-500 font-medium font-mono group-hover/bar:text-emerald-400 transition-colors group-hover/bar:-translate-y-1">{anomalies?.low || 0}</span>
                   <div 
                     className="w-16 bg-emerald-500/80 rounded-t-md group-hover/bar:bg-emerald-400 transition-all duration-500 ease-out group-hover/bar:w-20 cursor-pointer shadow-[0_0_15px_rgba(16,185,129,0)] group-hover/bar:shadow-[0_0_15px_rgba(16,185,129,0.5)]"
                     style={{ height: `${Math.max(20, ((anomalies?.low || 0) / (anomalies?.total || 1)) * 100)}%` }}
                   />
                   <span className="text-sm font-medium text-emerald-500 group-hover/bar:text-emerald-400">Faible</span>
                </div>

             </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
