'use client'

import { AnalysisResult } from '@/types'

export default function MetricsBar({ analysis, lang }: { analysis: AnalysisResult; lang: 'fr' | 'en' }) {
  if (!analysis.metrics && !analysis.model) return null

  const metrics = [
    { label: lang === 'fr' ? 'Modèle' : 'Model', value: analysis.model ?? '—', sub: 'AutoML' },
    { label: 'Accuracy', value: analysis.metrics ? `${(analysis.metrics.Accuracy * 100).toFixed(1)}%` : '—', sub: 'Score' },
    { label: 'AUC', value: analysis.metrics ? analysis.metrics.AUC.toFixed(3) : '—', sub: 'ROC' },
    { label: 'F1', value: analysis.metrics ? analysis.metrics.F1.toFixed(3) : '—', sub: 'Score' },
  ]

  if (analysis.rows) {
    metrics.push({ label: lang === 'fr' ? 'Lignes' : 'Rows', value: analysis.rows.toLocaleString(), sub: `${analysis.columns ?? '?'} cols` })
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full">
      {metrics.map((m) => (
        <div key={m.label} className="px-3 py-2.5 rounded-xl bg-[#0F1F3D]/80 border border-blue-500/15">
          <p className="text-[10px] text-blue-300/40 uppercase tracking-wide">{m.label}</p>
          <p className="text-base font-semibold text-white mt-0.5">{m.value}</p>
          <p className="text-[10px] text-emerald-400/70">{m.sub}</p>
        </div>
      ))}
    </div>
  )
}
