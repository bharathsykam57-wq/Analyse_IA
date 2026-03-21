"use client";

import { useEffect, useRef, useState } from "react";
import { useChatStore } from "@/features/agent/store/chatStore";
import { askAgent, checkTaskStatus } from "@/features/agent/api/agentApi";
import { DashboardMetrics } from "@/features/agent/components/DashboardMetrics";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { Send, Bot, User, Loader2, Play, Sparkles, Shield, RefreshCcw, Database, Plus } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { fetchFiles, rgpdScan, UploadedFile, RgpdScanResult } from "@/features/upload/api/upload";
import { useRouter } from "next/navigation";

const UUID_PREFIX_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/gi;

function getCleanFilename(text: string): string {
  return text.replace(UUID_PREFIX_RE, "");
}

function renderMarkdown(text: string) {
  return text
    .split('\n')
    .map((line, i) => {
      const parts = line.split('**');
      return (
        <span key={i}>
          {parts.map((part, j) =>
            j % 2 === 1
              ? <strong key={j} className="text-white font-semibold">{part}</strong>
              : <span key={j}>{part}</span>
          )}
          <br />
        </span>
      );
    });
}

export default function AgentChatPage() {
  const router = useRouter();
  const { messages, addMessage, isProcessing, setIsProcessing, currentTaskId, removeLoading, clearMessages } = useChatStore();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string>("");
  const [isLoadingFiles, setIsLoadingFiles] = useState(true);

  // RGPD scanner state
  const [showRgpdModal, setShowRgpdModal] = useState(false);
  const [rgpdResult, setRgpdResult] = useState<RgpdScanResult | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string>("");

  // Fetch files on mount
  useEffect(() => {
    fetchFiles().then(res => {
      setFiles(res);
      if (res.length > 0) setActiveFileId(res[0].file_id);
      setIsLoadingFiles(false);
    }).catch(err => {
      console.error(err);
      setIsLoadingFiles(false);
    });
  }, []);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Task Polling Loop
  useEffect(() => {
    let pollInterval: NodeJS.Timeout;

    if (isProcessing && currentTaskId) {
      pollInterval = setInterval(async () => {
        try {
          const statusResult = await checkTaskStatus(currentTaskId);
          
          if (statusResult.status === 'SUCCESS') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            removeLoading();
            
            // Add the final response message
            addMessage({
              id: Date.now().toString(),
              role: 'assistant',
              content: statusResult.answer || statusResult.result?.answer || "L'analyse est terminée. Voici les résultats.",
              timestamp: new Date().toISOString(),
              analysisData: statusResult.result?.result || undefined
            });
          } else if (statusResult.status === 'FAILURE') {
             clearInterval(pollInterval);
             setIsProcessing(false);
             removeLoading();
             addMessage({
               id: Date.now().toString(),
               role: 'assistant',
               content: "Erreur lors du traitement. Veuillez réessayer.",
               timestamp: new Date().toISOString()
             });
          }
          // If PENDING, loop continues
        } catch (pollingError) {
          console.error("Polling error:", pollingError);
          clearInterval(pollInterval);
          setIsProcessing(false);
        }
      }, 2000); // Poll every 2 seconds
    }

    return () => clearInterval(pollInterval);
  }, [isProcessing, currentTaskId, addMessage, setIsProcessing, removeLoading]);

  // Core analysis dispatch — called directly or after RGPD confirmation
  const proceedWithAnalysis = async (prompt: string) => {
    setShowRgpdModal(false);

    // 1. Add user message
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString()
    });

    try {
      setIsProcessing(true);

      // 2. Add temporary "polling" message
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "Analyse en cours...",
        timestamp: new Date().toISOString(),
        isPolling: true
      });

      // 3. Initiate Task
      const response = await askAgent(prompt, activeFileId);

      // 4. Update store to begin polling that specific task id
      setIsProcessing(true, response.task_id);
    } catch {
      setIsProcessing(false);
      removeLoading();
      addMessage({
        id: Date.now().toString(),
        role: 'assistant',
        content: "Désolé, je ne parviens pas à contacter le serveur. Le modèle est peut-être hors-ligne.",
        timestamp: new Date().toISOString()
      });
    }
  };

  const handleSend = async (e?: React.FormEvent, textOverride?: string) => {
    e?.preventDefault();
    const userPrompt = textOverride ?? input;
    if (!userPrompt.trim() || isProcessing) return;

    setInput("");

    // RGPD pre-flight scan: only for CSV files with an active file selected
    if (activeFileId) {
      try {
        const scan = await rgpdScan(activeFileId);
        if (scan.risk_level === 'high' || scan.risk_level === 'medium') {
          // Pause: show modal, wait for user confirmation
          setRgpdResult(scan);
          setPendingPrompt(userPrompt);
          setShowRgpdModal(true);
          return;
        }
      } catch (scanErr) {
        // Non-blocking: if scan fails, proceed with analysis anyway
        console.warn("RGPD scan failed, proceeding:", scanErr);
      }
    }

    // Safe / no file → proceed directly
    await proceedWithAnalysis(userPrompt);
  };

  return (
    <div className="flex flex-col min-h-full bg-[#050A15] relative">

      {/* ── RGPD Warning Modal ─────────────────────────────────────────────── */}
      {showRgpdModal && rgpdResult && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#0B1A2F] border border-white/10 rounded-2xl p-6 max-w-lg w-full shadow-2xl shadow-blue-900/30 animate-in fade-in zoom-in-95 duration-300">

            {/* Header */}
            <div className="flex items-start gap-3 mb-4">
              <span className="text-2xl mt-0.5">⚠️</span>
              <div>
                <h2 className="text-white font-bold text-lg leading-tight">
                  Données personnelles détectées
                </h2>
                <p className="text-gray-400 text-sm mt-1">
                  Nous avons détecté des données potentiellement personnelles dans votre fichier&nbsp;:
                </p>
              </div>
            </div>

            {/* Column list */}
            <div className="space-y-2 mb-4 max-h-40 overflow-y-auto pr-1">
              {rgpdResult.columns.map((col) => (
                <div key={col.name} className="flex items-start gap-2 text-sm bg-white/[0.03] border border-white/5 rounded-lg px-3 py-2">
                  <span className="flex-shrink-0 mt-0.5">{col.risk === 'high' ? '🔴' : '🟡'}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-white font-semibold">{col.name}</span>
                      {col.confidence !== undefined && (
                        <span className="text-gray-500 text-xs">{Math.round(col.confidence * 100)}% confiance</span>
                      )}
                    </div>
                    <span className="text-gray-400">{col.reason}</span>
                    {col.article && (
                      <span className="ml-1 text-blue-400 text-xs">({col.article})</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* User rights */}
            <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl px-4 py-3 mb-5 text-xs text-gray-400 space-y-1">
              <p className="text-blue-300 font-semibold mb-1.5">Vos droits :</p>
              <p>✅ Analyse anonymisée (recommandé)</p>
              <p>✅ Données supprimées après analyse</p>
              <p>✅ Audit trail RGPD généré</p>
            </div>

            {/* Recommendation */}
            <p className="text-xs text-amber-400/80 mb-5 leading-relaxed">
              {rgpdResult.recommendation}
            </p>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => proceedWithAnalysis(pendingPrompt)}
                className="flex-1 bg-blue-600 hover:bg-blue-500 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors"
              >
                Continuer l&apos;analyse
              </button>
              <button
                onClick={() => { setShowRgpdModal(false); setPendingPrompt(""); }}
                className="flex-1 border border-white/10 text-gray-400 hover:text-white hover:border-white/30 rounded-xl py-2.5 text-sm transition-colors"
              >
                Annuler
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Decorative ambient backgrounds - Enterprise Premium */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />
      <div className="absolute left-0 top-0 w-[800px] h-[800px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute right-0 bottom-0 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Header */}
      <div className="sticky top-0 p-3 border-b border-white/5 bg-[#050A15]/80 backdrop-blur-xl z-30 shadow-sm flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 min-w-0">
          <div className="p-1.5 bg-blue-500/10 rounded-lg border border-blue-500/20 shadow-inner flex-shrink-0">
            <Sparkles className="w-4 h-4 text-blue-400" />
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight whitespace-nowrap">
            Assistant Analyste <span className="text-blue-500 font-black text-sm">PRO</span>
          </h1>
          <span className="text-gray-500 text-xs hidden lg:inline truncate">— RAG &amp; AutoML</span>
        </div>

        {messages.length > 0 && (
          <Button
            onClick={clearMessages}
            variant="outline"
            className="border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 text-gray-200 gap-2 font-medium flex-shrink-0 text-sm py-1.5 h-auto"
          >
            <RefreshCcw className="w-3.5 h-3.5 text-blue-400" />
            Nouvelle analyse
          </Button>
        )}
      </div>

      {/* Chat Messages Area */}
      <div className="flex-1 p-4 md:p-8 space-y-8 z-10 pb-[200px]">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-start pt-4 md:pt-12 pb-10 text-center max-w-3xl mx-auto space-y-8 animate-in fade-in zoom-in-95 duration-700">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500/30 rounded-full blur-2xl animate-pulse" />
              <div className="relative w-24 h-24 bg-gradient-to-tr from-blue-900 to-indigo-600 rounded-3xl flex items-center justify-center border border-white/10 shadow-2xl shadow-blue-900/50 rotate-3 hover:rotate-0 transition-transform duration-500">
                <Bot className="w-12 h-12 text-white drop-shadow-lg" />
              </div>
            </div>
            <div className="space-y-4">
              <h2 className="text-4xl md:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-white via-gray-200 to-gray-500 tracking-tight pb-2">
                Comment puis-je vous aider ?
              </h2>
              
              {isLoadingFiles ? (
                 <div className="flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-blue-500" /></div>
              ) : files.length > 0 ? (
                 <div className="max-w-md mx-auto bg-white/[0.03] border border-white/10 rounded-xl p-4 flex flex-col gap-3 shadow-2xl">
                   <div className="flex items-center justify-between gap-4">
                     <label className="text-xs text-gray-400 font-bold uppercase tracking-wider flex items-center gap-2">
                       <Database className="w-3.5 h-3.5 text-blue-400" />
                       Données Actives
                     </label>
                     <button 
                       onClick={() => router.push('/upload')}
                       className="text-[11px] font-bold flex items-center gap-1.5 text-blue-400 hover:text-white bg-blue-500/10 hover:bg-blue-600 transition-all px-2.5 py-1.5 rounded-lg border border-blue-500/20"
                     >
                       <Plus className="w-3 h-3" />
                       NOUVEAU
                     </button>
                   </div>
                   <select 
                     value={activeFileId} 
                     onChange={(e) => setActiveFileId(e.target.value)}
                     className="bg-black/60 border border-white/5 text-white rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none w-full shadow-inner appearance-none cursor-pointer"
                   >
                     {files.map(f => (
                       <option key={f.file_id} value={f.file_id} className="bg-[#050A15] p-2">
                         {getCleanFilename(f.filename)}
                       </option>
                     ))}
                   </select>
                 </div>
              ) : (
                 <div className="max-w-md mx-auto bg-blue-500/10 border border-blue-500/20 rounded-xl p-6 flex flex-col items-center gap-4">
                   <p className="text-blue-200 text-sm">Vous n&apos;avez pas encore de données à analyser.</p>
                   <Button onClick={() => router.push('/upload')} className="bg-blue-600 hover:bg-blue-500 text-white w-full">
                     Téléverser un fichier
                   </Button>
                 </div>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full pt-6">
               {(files.length > 0 
                  ? [
                     `Lance l'AutoML sur ${files.find(f => f.file_id === activeFileId)?.filename || 'vos données'}`, 
                     `Quelles sont les anomalies dans ${files.find(f => f.file_id === activeFileId)?.filename || 'ce fichier'} ?`, 
                     "Génère le dashboard complet de mon jeu de données",
                     "Fais une synthèse de l'historique de cette analyse"
                    ]
                  : [
                     "Expliquez-moi comment importer des données",
                     "Quels types de fichiers sont supportés ?",
                     "Qu'est-ce que l'AutoML ?",
                     "Affichez-moi un exemple de dashboard"
                  ]
                ).map((suggestion, i) => (
                 <button
                  key={`suggestion-${files.length > 0 ? 'with-files' : 'no-files'}-${i}`}
                  onClick={() => handleSend(undefined, suggestion)}
                  className="px-6 py-5 text-sm text-left bg-white/[0.03] backdrop-blur-md border border-white/5 hover:bg-white/5 hover:border-blue-500/30 rounded-2xl transition-all duration-300 text-gray-300 hover:text-white flex items-center gap-4 group shadow-xl shadow-black/20"
                  style={{ animationDelay: `${i * 100}ms` }}
                 >
                   <div className="p-2.5 rounded-full bg-blue-500/10 group-hover:bg-blue-500/20 transition-colors">
                     <Play className="w-4 h-4 text-blue-400 group-hover:scale-110 transition-transform" />
                   </div>
                   <span className="font-medium leading-tight">{suggestion}</span>
                 </button>
               ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div 
              key={msg.id} 
              className={cn(
                "flex w-full animate-in fade-in slide-in-from-bottom-4 duration-500",
                msg.role === 'user' ? "justify-end" : "justify-start"
              )}
            >
              <div className={cn(
                "flex gap-4 max-w-[85%] md:max-w-[75%]",
                msg.role === 'user' ? "flex-row-reverse" : "flex-row"
              )}>
                
                <div className="flex-shrink-0 mt-1">
                  {msg.role === 'user' ? (
                    <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-900/40 ring-2 ring-blue-500/20">
                      <User className="w-5 h-5 text-white" />
                    </div>
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-900 to-blue-900 flex items-center justify-center border border-blue-500/30 shadow-lg shadow-blue-900/20">
                      <Bot className="w-5 h-5 text-blue-300" />
                    </div>
                  )}
                </div>

                <div className={cn(
                  "p-5 rounded-3xl shadow-lg",
                  msg.role === 'user' 
                    ? "bg-blue-600 text-white rounded-tr-sm" 
                    : "bg-white/[0.04] backdrop-blur-md border border-white/5 text-gray-200 rounded-tl-sm w-full"
                )}>
                  <div className="prose prose-invert max-w-none text-[15px] leading-relaxed font-normal">
                    {msg.isPolling ? (
                       <div className="flex items-center gap-3 text-blue-400">
                         <Loader2 className="w-5 h-5 animate-spin" />
                         <span className="animate-pulse">{msg.content}</span>
                       </div>
                    ) : (
                      <div className="text-[15px] leading-relaxed">
                        {renderMarkdown(getCleanFilename(msg.content))}
                      </div>
                    )}
                  </div>
                  
                  {/* Rich Metrics Dashboard Injection */}
                  {msg.analysisData && (
                    <div className="pt-6 mt-4 border-t border-white/10">
                      <DashboardMetrics data={msg.analysisData} className="!bg-black/20" />
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} className="h-4" />
      </div>

      {/* Input Form Premium */}
      <div className="sticky bottom-0 z-30 p-2 pt-4 pb-4 bg-gradient-to-t from-[#050A15] via-[#050A15]/95 to-transparent">
        <div className="max-w-3xl mx-auto flex flex-col items-center">
          <form 
            onSubmit={(e) => handleSend(e)}
            className="flex items-center gap-2 bg-black/40 backdrop-blur-2xl border border-white/10 hover:border-white/20 rounded-full p-1.5 pl-6 shadow-2xl shadow-blue-900/10 focus-within:border-blue-500/50 focus-within:ring-4 focus-within:ring-blue-500/10 transition-all duration-300 w-full"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isProcessing}
              placeholder="Saisissez votre prompt analytique..."
              className="flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 px-0 h-10 text-[15px] text-gray-100 placeholder:text-gray-500 font-medium"
            />
            <Button 
              type="submit" 
              disabled={!input.trim() || isProcessing}
              size="icon"
              className="rounded-full h-10 w-10 bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/40 flex-shrink-0 transition-transform active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
            >
              {isProcessing ? (
                <Loader2 className="w-5 h-5 animate-spin text-white" />
              ) : (
                <Send className="w-4 h-4 text-white ml-[2px]" />
              )}
            </Button>
          </form>
          <div className="text-center mt-3 space-y-1">
            <span className="text-[11px] text-gray-500 flex items-center justify-center gap-1.5 font-medium">
              <Shield className="w-3 h-3 text-blue-500/70" />
              Vérifiez toujours les algorithmes générés avant la production.
            </span>
            <span className="text-[11px] text-gray-600 flex items-center justify-center gap-1.5 font-medium">
              <Shield className="w-3 h-3 text-emerald-500/70" />
              RGPD Compliant — Art. 25 Privacy by Design
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
