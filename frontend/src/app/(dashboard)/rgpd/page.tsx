"use client";

import { useEffect, useState } from "react";
import { Shield, Database, Trash2, Check, Clock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { exportUserData, eraseUserData, fetchAuditLog, fetchConsents } from "@/features/rgpd/api/rgpdApi";

export default function RGPDPage() {
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [consentCount, setConsentCount] = useState(0);
  const [auditCount, setAuditCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const loadRgpdStats = async () => {
      try {
        setIsLoadingStats(true);
        const [consents, audit] = await Promise.all([fetchConsents(), fetchAuditLog()]);
        setConsentCount(consents.length);
        setAuditCount(audit.length);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Impossible de charger les informations RGPD.");
      } finally {
        setIsLoadingStats(false);
      }
    };

    loadRgpdStats();
  }, []);

  const handleExport = async () => {
    try {
      setIsExporting(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      const data = await exportUserData();
      const payload = JSON.stringify(data, null, 2);
      const blob = new Blob([payload], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `rgpd_export_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);

      setSuccessMessage("Export RGPD généré et téléchargé.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Échec de l'export RGPD.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleErasure = async () => {
    const confirmed = window.confirm("Confirmez-vous la suppression définitive de votre compte ? Cette action est irréversible.");
    if (!confirmed) return;

    try {
      setIsDeleting(true);
      setErrorMessage(null);
      setSuccessMessage(null);
      const response = await eraseUserData();
      setSuccessMessage(response.message);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Échec de la suppression des données.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="p-6 md:p-10 max-w-4xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      <div>
        <h1 className="text-3xl font-bold font-sans text-white mb-2 tracking-tight flex items-center gap-3">
          <Shield className="w-8 h-8 text-emerald-500" />
          Confidentialité & RGPD
        </h1>
        <p className="text-blue-300/60 leading-relaxed max-w-2xl">
          Gérez vos données personnelles, l’historique d’analyse de vos IA et vos droits d’accès conformément au Règlement Général sur la Protection des Données.
        </p>
      </div>

      {(errorMessage || successMessage) && (
        <Card className={errorMessage ? "bg-red-500/5 border-red-500/20" : "bg-emerald-500/5 border-emerald-500/20"}>
          <CardContent className="pt-6 text-sm">
            <p className={errorMessage ? "text-red-300" : "text-emerald-300"}>{errorMessage || successMessage}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6">
        
        {/* Compliance Status */}
        <Card className="bg-emerald-500/5 border-emerald-500/20 backdrop-blur-md relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/0 via-emerald-500/5 to-emerald-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-1000 animate-pulse" />
          <CardHeader>
             <CardTitle className="text-emerald-400 flex items-center gap-2">
               <div className="p-2 bg-emerald-500/10 rounded-lg">
                 <Check className="w-5 h-5 text-emerald-400" />
               </div>
               Statut de Conformité
             </CardTitle>
          </CardHeader>
          <CardContent>
             <p className="text-sm text-gray-300 leading-relaxed">
               Vos données sont hébergées sur des serveurs sécurisés situés en France métropolitaine. 
               Les modèles d’Intelligence Artificielle utilisés opèrent en environnement clos : vos données 
               <strong className="text-emerald-400 font-medium"> ne s’entraînent sur aucun modèle public</strong>.
             </p>
             <div className="mt-4 text-xs text-gray-400 space-y-1">
               <p>Consents actifs: {isLoadingStats ? "..." : consentCount}</p>
               <p>Entrées d’audit: {isLoadingStats ? "..." : auditCount}</p>
             </div>
          </CardContent>
        </Card>

        {/* Data Export */}
        <Card className="bg-white/[0.02] border-white/5 backdrop-blur-md hover:bg-white/[0.04] transition-colors">
          <CardHeader>
            <CardTitle className="text-lg text-white flex items-center gap-2">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <Database className="w-5 h-5 text-blue-400" />
              </div>
              Exporter vos données
            </CardTitle>
            <CardDescription className="text-gray-400">
              Téléchargez une copie complète de vos informations (fichiers, historique d’analyse).
            </CardDescription>
          </CardHeader>
          <CardContent>
             <Button
               variant="outline"
               onClick={handleExport}
               disabled={isExporting}
               className="w-full sm:w-auto mt-2 bg-transparent border-blue-500/30 text-blue-400 hover:bg-blue-500/10 hover:text-blue-300"
             >
               {isExporting ? "Export en cours..." : "Télécharger mes données (JSON)"}
             </Button>
             <p className="text-xs text-gray-500 mt-4 flex items-center gap-2">
               <Clock className="w-3.5 h-3.5" />
               Export instantané conforme aux articles 15 et 20 du RGPD.
             </p>
          </CardContent>
        </Card>

        {/* Account Deletion */}
        <Card className="bg-white/[0.02] border-red-500/20 backdrop-blur-md">
          <CardHeader>
            <CardTitle className="text-lg text-red-500 flex items-center gap-2">
              <div className="p-2 bg-red-500/10 rounded-lg">
                <Trash2 className="w-5 h-5" />
              </div>
              Zone de Danger - Suppression
            </CardTitle>
            <CardDescription className="text-red-400/80">
              Fermeture définitive de votre espace et effacement de toutes vos métadonnées.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-red-500/5 p-5 rounded-xl border border-red-500/10 mb-6">
               <p className="text-sm text-red-300/90 leading-relaxed">
                 <strong className="text-red-400 font-medium">Attention:</strong> Cette action effacera irréversiblement tous vos documents téléversés et historiques d’analyse.
               </p>
            </div>
            <Button
              variant="destructive"
              onClick={handleErasure}
              disabled={isDeleting}
              className="w-full sm:w-auto bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-900/20"
            >
               {isDeleting ? "Suppression en cours..." : "Supprimer mon compte définitivement"}
            </Button>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
