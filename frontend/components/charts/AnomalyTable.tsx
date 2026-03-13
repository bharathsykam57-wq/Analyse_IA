'use client'

import { BackendAnomalies } from '@/types'

export default function AnomalyTable({ anomalies, lang }: { anomalies: BackendAnomalies; lang: 'fr' | 'en' }) {
  if (!anomalies || anomalies.total === 0) return null

  return (
    <div className="w-full rounded-xl bg-[#0F1F3D]/80 border border-blue-500/15 p-4">
      <p className="text-xs font-medium text-blue-200/70 mb-3 uppercase tracking-wide">
        {lang === 'fr' ? 'Anomalies détectées' : 'Detected Anomalies'}
      </p>
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
          <p className="text-lg font-bold text-red-400">{anomalies.high}</p>
          <p className="text-[10px] text-red-400/60">{lang === 'fr' ? 'Critiques' : 'Critical'}</p>
        </div>
        <div className="text-center px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <p className="text-lg font-bold text-amber-400">{anomalies.medium}</p>
          <p className="text-[10px] text-amber-400/60">{lang === 'fr' ? 'Moyennes' : 'Medium'}</p>
        </div>
        <div className="text-center px-3 py-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <p className="text-lg font-bold text-blue-400">{anomalies.low}</p>
          <p className="text-[10px] text-blue-400/60">{lang === 'fr' ? 'Faibles' : 'Low'}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-blue-300/40">
        <span>Total: <span className="text-white font-medium">{anomalies.total}</span></span>
        <span>{anomalies.percentage.toFixed(1)}% {lang === 'fr' ? 'des données' : 'of data'}</span>
      </div>
    </div>
  )
}
