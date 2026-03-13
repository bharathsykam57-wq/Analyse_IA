'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Plus, Bot, User, Loader2, Paperclip, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useChatStore } from '@/store/chatStore'
import { t } from '@/lib/i18n'
import api from '@/lib/api'
import { BackendResult, ChatMessage, UploadedFile, AnalysisResult } from '@/types'
import { parseFilename } from '@/lib/utils'
import ShapChart from '@/components/charts/ShapChart'
import AnomalyTable from '@/components/charts/AnomalyTable'
import MetricsBar from '@/components/charts/MetricsBar'

function mapAnalysis(r: BackendResult): AnalysisResult | undefined {
  if (!r.result) return undefined
  const d = r.result
  return {
    model: d.best_model,
    rows: d.rows,
    columns: d.columns,
    metrics: d.metrics,
    top_features: d.top_features,
    anomalies: d.anomalies,
    eda_insights: d.eda_insights,
  }
}

export default function DashboardPage() {
  const {
    messages, language: lang, isProcessing,
    addMessage, appendToMessage, updateMessage,
    setProcessing, setCurrentTaskId, clearMessages,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null)
  const [showFilePicker, setShowFilePicker] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const { data: files = [] } = useQuery<UploadedFile[]>({
    queryKey: ['files'],
    queryFn: async () => {
      try {
        const res = await api.get('/files/list')
        const raw = Array.isArray(res.data) ? res.data : (res.data.files ?? [])
        return raw.map(f => ({
          ...f,
          ...parseFilename(f.filename),
        }))
      } catch {
        return []
      }
    },
  })

  const selectedFile = files.find(f => f.file_id === selectedFileId)

  const handleSend = useCallback(async () => {
    if (!input.trim() || isProcessing) return
    const userMessage = input.trim()
    setInput('')
    setShowFilePicker(false)

    addMessage({ role: 'user', content: userMessage, language: lang })
    const assistantId = addMessage({
      role: 'assistant',
      content: '',
      language: lang,
      isStreaming: true,
    })
    setProcessing(true)

    try {
      const payload: Record<string, string> = { query: userMessage, language: lang }
      if (selectedFileId) payload.file_id = selectedFileId

      const res = await api.post('/agent/ask', payload)
      const { task_id } = res.data
      setCurrentTaskId(task_id)

      // Polling with 3 second interval, max 20 polls (60 seconds total)
      let pollCount = 0
      const maxPolls = 20

      const poll = async () => {
        pollCount++
        try {
          const s = await api.get(`/agent/status/${task_id}`)
          if (s.data.status === 'SUCCESS' && s.data.result) {
            const r: BackendResult = s.data.result
            updateMessage(assistantId, {
              isStreaming: false,
              content: r.answer ?? '',
              analysis: mapAnalysis(r),
            })
            setProcessing(false)
            setCurrentTaskId(null)
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current)
          } else if (s.data.status === 'FAILURE') {
            updateMessage(assistantId, {
              isStreaming: false,
              content: t(lang, 'serverError'),
            })
            setProcessing(false)
            setCurrentTaskId(null)
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current)
          } else if (pollCount >= maxPolls) {
            updateMessage(assistantId, {
              isStreaming: false,
              content: t(lang, 'networkError'),
            })
            setProcessing(false)
            setCurrentTaskId(null)
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current)
          }
        } catch {
          if (pollCount >= maxPolls) {
            updateMessage(assistantId, {
              isStreaming: false,
              content: t(lang, 'networkError'),
            })
            setProcessing(false)
            setCurrentTaskId(null)
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current)
          }
        }
      }

      pollingIntervalRef.current = setInterval(poll, 3000)
    } catch {
      updateMessage(assistantId, {
        isStreaming: false,
        content: t(lang, 'serverError'),
      })
      setProcessing(false)
    }
  }, [input, isProcessing, lang, selectedFileId, addMessage, updateMessage, setProcessing, setCurrentTaskId])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <EmptyState lang={lang} onSuggestion={(s) => setInput(s)} />
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} lang={lang} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {showFilePicker && (
        <div className="px-4 mb-2">
          <div className="max-w-3xl mx-auto rounded-xl border border-blue-500/20 bg-[#0F1F3D]/90 backdrop-blur overflow-hidden">
            <p className="px-4 py-2 text-xs text-blue-300/50 border-b border-blue-500/10">
              {lang === 'fr' ? 'Sélectionner un fichier' : 'Select a file'}
            </p>
            {files.length === 0 ? (
              <p className="px-4 py-3 text-xs text-blue-300/30">
                {lang === 'fr' ? 'Aucun fichier importé' : 'No files uploaded'}
              </p>
            ) : (
              files.map(f => (
                <button
                  key={f.file_id}
                  onClick={() => { setSelectedFileId(f.file_id); setShowFilePicker(false) }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-blue-600/10 transition-all text-left"
                >
                  <span className={`text-xs px-1.5 py-0.5 rounded ${f.type === 'csv' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-blue-500/15 text-blue-400'}`}>
                    {f.type.toUpperCase()}
                  </span>
                  <span className="text-sm text-blue-100 truncate">{f.original_name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      <div className="flex-shrink-0 border-t border-blue-500/10 p-4">
        <div className="max-w-3xl mx-auto">
          {selectedFile && (
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-blue-600/15 border border-blue-500/20 text-blue-300">
                <span className={selectedFile.type === 'csv' ? 'text-emerald-400' : 'text-blue-400'}>
                  {selectedFile.type.toUpperCase()}
                </span>
                {selectedFile.original_name}
                <button onClick={() => setSelectedFileId(null)} className="ml-1 hover:text-red-400 transition-colors">
                  <X className="w-3 h-3" />
                </button>
              </span>
            </div>
          )}
          <div className="flex items-end gap-3">
            <button onClick={clearMessages} className="flex-shrink-0 w-9 h-9 rounded-lg border border-blue-500/20 hover:border-blue-500/40 flex items-center justify-center text-blue-400/60 hover:text-blue-400 transition-all">
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowFilePicker(!showFilePicker)}
              className={`flex-shrink-0 w-9 h-9 rounded-lg border flex items-center justify-center transition-all ${
                selectedFileId ? 'border-blue-500/40 text-blue-400 bg-blue-600/10' : 'border-blue-500/20 hover:border-blue-500/40 text-blue-400/60 hover:text-blue-400'
              }`}
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t(lang, 'chatPlaceholder')}
                rows={1}
                disabled={isProcessing}
                className="w-full px-4 py-2.5 pr-12 rounded-xl text-sm resize-none outline-none disabled:opacity-50"
                style={{ background: 'rgba(15,31,61,0.8)', border: '1px solid rgba(37,99,235,0.2)', color: '#E8F0FB', minHeight: '44px', maxHeight: '200px' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isProcessing}
                className="absolute right-2 bottom-2 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-30 flex items-center justify-center transition-all"
              >
                {isProcessing ? <Loader2 className="w-3.5 h-3.5 text-white animate-spin" /> : <Send className="w-3.5 h-3.5 text-white" />}
              </button>
            </div>
          </div>
          <p className="text-xs text-blue-300/30 text-center mt-2">
            {lang === 'fr' ? 'Entrée pour envoyer · Maj+Entrée pour nouvelle ligne' : 'Enter to send · Shift+Enter for new line'}
          </p>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ lang, onSuggestion }: { lang: 'fr' | 'en'; onSuggestion: (s: string) => void }) {
  const suggestions = lang === 'fr'
    ? ['Analyse ce dataset et identifie les anomalies', 'Quelles variables influencent le plus la cible ?', 'Explique les résultats SHAP en détail', 'Compare les modèles disponibles']
    : ['Analyze this dataset and identify anomalies', 'Which variables influence the target most?', 'Explain the SHAP results in detail', 'Compare the available models']

  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-4 py-12">
      <div className="w-12 h-12 rounded-2xl bg-blue-600/15 border border-blue-500/20 flex items-center justify-center mb-4">
        <Bot className="w-6 h-6 text-blue-400" />
      </div>
      <h2 className="text-lg font-semibold text-white mb-1">{lang === 'fr' ? 'Analyste IA prêt' : 'AI Analyst ready'}</h2>
      <p className="text-sm text-blue-300/50 mb-8 max-w-sm">
        {lang === 'fr' ? 'Importez un fichier CSV ou PDF via la page Import, puis posez vos questions.' : 'Upload a CSV or PDF via the Import page, then ask your questions.'}
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
        {suggestions.map((s) => (
          <button key={s} onClick={() => onSuggestion(s)}
            className="text-left px-4 py-3 rounded-xl bg-[#0F1F3D]/60 border border-blue-500/10 hover:border-blue-500/25 text-sm text-blue-200/60 hover:text-blue-200 transition-all">
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({ message, lang }: { message: ChatMessage; lang: 'fr' | 'en' }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${isUser ? 'bg-blue-600' : 'bg-[#1B3A6B] border border-blue-500/20'}`}>
        {isUser ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5 text-blue-400" />}
      </div>
      <div className={`max-w-[75%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-4 py-2.5 text-sm leading-relaxed ${isUser ? 'bg-gradient-to-br from-blue-700 to-blue-600 text-white rounded-2xl rounded-tr-md' : 'bg-[#0F1F3D]/80 border border-blue-500/15 text-blue-100 rounded-2xl rounded-tl-md'}`}>
          {message.isStreaming && !message.content ? (
            <div className="flex items-center gap-1 py-0.5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="w-1.5 h-1.5 rounded-full bg-blue-400/60 typing-dot" style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
          ) : (
            <span className="whitespace-pre-wrap">{message.content}</span>
          )}
          {message.isStreaming && message.content && <span className="inline-block w-1 h-3.5 bg-blue-400 ml-0.5 animate-pulse" />}
        </div>
        {message.analysis && !message.isStreaming && (
          <div className="w-full space-y-3">
            <MetricsBar analysis={message.analysis} lang={lang} />
            {message.analysis.top_features && message.analysis.top_features.length > 0 && (
              <ShapChart shapValues={message.analysis.top_features} lang={lang} />
            )}
            {message.analysis.anomalies && message.analysis.anomalies.total > 0 && (
              <AnomalyTable anomalies={message.analysis.anomalies} lang={lang} />
            )}
          </div>
        )}
        <span className="text-[10px] text-blue-300/30 px-1">
          {message.timestamp.toLocaleTimeString(lang === 'fr' ? 'fr-FR' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  )
}
