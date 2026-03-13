'use client'

import { TopFeature } from '@/types'

export default function ShapChart({ shapValues, lang }: { shapValues: TopFeature[]; lang: 'fr' | 'en' }) {
  if (!shapValues || shapValues.length === 0) return null
  const max = Math.max(...shapValues.map(s => s.importance_percentage))

  return (
    <div className="w-full rounded-xl bg-[#0F1F3D]/80 border border-blue-500/15 p-4">
      <p className="text-xs font-medium text-blue-200/70 mb-3 uppercase tracking-wide">
        {lang === 'fr' ? 'Importance des variables (SHAP)' : 'Feature Importance (SHAP)'}
      </p>
      <div className="space-y-2">
        {shapValues.slice(0, 8).map((s) => (
          <div key={s.feature} className="flex items-center gap-3">
            <span className="text-xs text-blue-200/60 w-32 truncate flex-shrink-0">{s.feature}</span>
            <div className="flex-1 h-1.5 bg-blue-900/40 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-500 to-blue-400 transition-all"
                style={{ width: `${(s.importance_percentage / max) * 100}%` }}
              />
            </div>
            <span className="text-xs text-blue-300/50 w-10 text-right flex-shrink-0">
              {s.importance_percentage.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
