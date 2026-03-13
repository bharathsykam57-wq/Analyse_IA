'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, FileSearch, Code2, Loader2, Search } from 'lucide-react'
import api from '@/lib/api'
import { HistoryItem } from '@/types'
import { t, Lang } from '@/lib/i18n'
import { useChatStore } from '@/store/chatStore'
import { formatDate } from '@/lib/utils'

type FilterType = 'all' | 'analyse' | 'rag' | 'code'

export default function HistoryPage() {
  const { language: lang } = useChatStore()
  const [filter, setFilter] = useState<FilterType>('all')
  const [search, setSearch] = useState('')

  const { data: history = [], isLoading } = useQuery<HistoryItem[]>({
    queryKey: ['history'],
    queryFn: async () => {
      try {
        const res = await api.get('/agent/history')
        return Array.isArray(res.data) ? res.data : []
      } catch {
        // Endpoint may not exist yet — return empty, never crash
        return []
      }
    },
    refetchInterval: 30000,
  })

  const filtered = history.filter((item) => {
    const matchType = filter === 'all' || item.type === filter
    const matchSearch =
      !search ||
      item.query.toLowerCase().includes(search.toLowerCase()) ||
      item.response_preview.toLowerCase().includes(search.toLowerCase())
    return matchType && matchSearch
  })

  const filters: { key: FilterType; label: string }[] = [
    { key: 'all', label: t(lang, 'allTypes') },
    { key: 'analyse', label: t(lang, 'analyse') },
    { key: 'rag', label: t(lang, 'rag') },
    { key: 'code', label: t(lang, 'code') },
  ]

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-white">{t(lang, 'historyTitle')}</h1>
          <p className="text-sm text-blue-300/50 mt-1">
            {history.length} {lang === 'fr' ? 'entrées' : 'entries'}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400/40" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={lang === 'fr' ? 'Rechercher...' : 'Search...'}
              className="w-full pl-9 pr-4 py-2 rounded-lg text-sm outline-none"
              style={{ background: 'rgba(15,31,61,0.8)', border: '1px solid rgba(37,99,235,0.15)', color: '#E8F0FB' }}
            />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {filters.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  filter === key
                    ? 'bg-blue-600 text-white'
                    : 'bg-[#0F1F3D]/60 border border-blue-500/10 text-blue-300/60 hover:text-blue-200 hover:border-blue-500/25'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 text-blue-300/50 text-sm py-12">
            <Loader2 className="w-4 h-4 animate-spin" />
            {lang === 'fr' ? 'Chargement...' : 'Loading...'}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-blue-300/30 text-sm">{t(lang, 'noHistory')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((item) => (
              <HistoryRow key={item.id} item={item} lang={lang} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function HistoryRow({ item, lang }: { item: HistoryItem; lang: Lang }) {
  const cfg =
    {
      analyse: { icon: BarChart3,  color: 'text-blue-400',    bg: 'bg-blue-600/10',    label: 'Analyse' },
      rag:     { icon: FileSearch, color: 'text-purple-400',  bg: 'bg-purple-600/10',  label: 'RAG' },
      code:    { icon: Code2,      color: 'text-emerald-400', bg: 'bg-emerald-600/10', label: 'Code' },
    }[item.type] ?? { icon: BarChart3, color: 'text-blue-400', bg: 'bg-blue-600/10', label: item.type }

  const Icon = cfg.icon

  return (
    <div className="px-4 py-3 rounded-xl bg-[#0F1F3D]/60 border border-blue-500/10 hover:border-blue-500/20 transition-all">
      <div className="flex items-start gap-3">
        <div className={`w-7 h-7 rounded-lg ${cfg.bg} flex items-center justify-center flex-shrink-0 mt-0.5`}>
          <Icon className={`w-3.5 h-3.5 ${cfg.color}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm font-medium text-white truncate">{item.query}</p>
            <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] ${cfg.bg} ${cfg.color}`}>
              {cfg.label}
            </span>
          </div>
          <p className="text-xs text-blue-300/40 truncate">{item.response_preview}</p>
        </div>
        <span className="text-[10px] text-blue-300/30 flex-shrink-0 mt-1 whitespace-nowrap">
          {formatDate(item.created_at, lang)}
        </span>
      </div>
    </div>
  )
}
