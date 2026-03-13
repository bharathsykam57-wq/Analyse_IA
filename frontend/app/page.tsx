'use client'

import Link from 'next/link'
import { useState } from 'react'
import { t, Lang } from '@/lib/i18n'
import { Brain, FileSearch, Shield, Globe, BarChart3, Zap, Lock, ArrowRight, ChevronRight } from 'lucide-react'

export default function LandingPage() {
  const [lang, setLang] = useState<Lang>('fr')

  return (
    <div className="min-h-screen bg-[#0A1628] bg-grid text-white overflow-hidden">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-blue-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-blue-800/10 rounded-full blur-[100px]" />
      </div>

      {/* Navbar */}
      <nav className="relative z-10 border-b border-blue-500/10 bg-[#0A1628]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <Brain className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold tracking-tight">Analyse IA</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setLang(lang === 'fr' ? 'en' : 'fr')}
              className="text-xs text-blue-300/70 hover:text-blue-300 px-2 py-1 rounded border border-blue-500/20 hover:border-blue-500/40 transition-colors"
            >
              {lang === 'fr' ? 'FR' : 'EN'}
            </button>
            <Link href="/login" className="text-sm text-blue-200/70 hover:text-white transition-colors">
              {t(lang, 'login')}
            </Link>
            <Link href="/register" className="text-sm bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg transition-colors font-medium">
              {t(lang, 'getStarted')}
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-24 pb-20">
        <div className="max-w-4xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-600/10 border border-blue-500/20 text-blue-300 text-xs font-medium mb-8">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            mistral-nemo · nomic-embed · pgvector · LangGraph
          </div>
          <h1 className="text-5xl md:text-7xl font-bold leading-tight tracking-tight mb-6">
            <span className="text-white">{t(lang, 'heroTitle')}</span>
            <br />
            <span className="text-blue-400">{lang === 'fr' ? 'pour l\'entreprise' : 'for enterprise'}</span>
          </h1>
          <p className="text-lg md:text-xl text-blue-200/60 max-w-2xl mb-10 leading-relaxed">
            {t(lang, 'heroSubtitle')}
          </p>
          <div className="flex flex-col sm:flex-row gap-4">
            <Link href="/register" className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-lg font-medium transition-all hover:shadow-[0_0_20px_rgba(37,99,235,0.4)] group">
              {t(lang, 'getStarted')} <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link href="/login" className="inline-flex items-center gap-2 border border-blue-500/30 hover:border-blue-500/60 text-blue-200 hover:text-white px-6 py-3 rounded-lg font-medium transition-all">
              {t(lang, 'login')} <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Mock dashboard preview */}
        <div className="mt-16 rounded-2xl overflow-hidden border border-blue-500/15 shadow-[0_0_60px_rgba(37,99,235,0.1)] bg-[#0F1F3D]/60 backdrop-blur-sm">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-blue-500/10 bg-[#0A1628]/50">
            <div className="w-3 h-3 rounded-full bg-red-500/50" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/50" />
            <div className="w-3 h-3 rounded-full bg-emerald-500/50" />
            <span className="ml-4 text-xs text-blue-300/40 font-mono">Analyse IA · Dashboard</span>
          </div>
          <div className="p-6 grid grid-cols-4 gap-3">
            {[
              { label: 'Modèle', value: 'LightGBM', sub: 'AutoML' },
              { label: 'Score R²', value: '0.941', sub: '+2.3%' },
              { label: 'Anomalies', value: '12', sub: '1.2%' },
              { label: 'Précision', value: '94.1%', sub: '15 modèles' },
            ].map((m) => (
              <div key={m.label} className="bg-[#1B3A6B]/30 rounded-xl p-3 border border-blue-500/10">
                <div className="text-blue-400/60 text-xs mb-1">{m.label}</div>
                <div className="text-white font-semibold text-lg">{m.value}</div>
                <div className="text-emerald-400 text-xs">{m.sub}</div>
              </div>
            ))}
          </div>
          <div className="px-6 pb-6 grid grid-cols-3 gap-3">
            <div className="col-span-2 bg-[#1B3A6B]/20 rounded-xl p-4 border border-blue-500/10">
              <div className="text-xs text-blue-300/60 mb-3 font-medium">SHAP Feature Importance</div>
              {[['revenue', 88], ['churn_score', 72], ['sessions', 54], ['days_active', 41]].map(([n, v]) => (
                <div key={n} className="flex items-center gap-3 mb-2">
                  <div className="w-24 text-xs text-blue-300/50 font-mono text-right">{n}</div>
                  <div className="flex-1 h-1.5 bg-blue-900/40 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full" style={{ width: `${v}%` }} />
                  </div>
                  <div className="text-xs text-blue-300/50 w-8 text-right">{v}%</div>
                </div>
              ))}
            </div>
            <div className="bg-[#1B3A6B]/20 rounded-xl p-4 border border-blue-500/10">
              <div className="text-xs text-blue-300/60 mb-3 font-medium">Agent IA</div>
              <div className="space-y-2 text-xs">
                <div className="bg-blue-600/20 rounded-lg p-2 text-blue-200">Quelles variables influencent le churn ?</div>
                <div className="bg-[#0F1F3D]/60 rounded-lg p-2 text-blue-100 border border-blue-500/10">Le revenu mensuel est le facteur principal avec 88% d&apos;impact SHAP...</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center mb-4">{lang === 'fr' ? 'Tout ce dont vous avez besoin' : 'Everything you need'}</h2>
        <p className="text-blue-300/60 text-center mb-12">{lang === 'fr' ? 'Une plateforme complète pour le marché français' : 'A complete platform for the French market'}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: BarChart3, title: t(lang, 'feature1Title'), desc: t(lang, 'feature1Desc'), color: 'text-blue-400', bg: 'bg-blue-600/10' },
            { icon: FileSearch, title: t(lang, 'feature2Title'), desc: t(lang, 'feature2Desc'), color: 'text-purple-400', bg: 'bg-purple-600/10' },
            { icon: Shield, title: t(lang, 'feature3Title'), desc: t(lang, 'feature3Desc'), color: 'text-emerald-400', bg: 'bg-emerald-600/10' },
            { icon: Globe, title: t(lang, 'feature4Title'), desc: t(lang, 'feature4Desc'), color: 'text-amber-400', bg: 'bg-amber-600/10' },
          ].map((f) => (
            <div key={f.title} className="bg-[#0F1F3D]/60 border border-blue-500/10 rounded-xl p-6 hover:border-blue-500/25 transition-all">
              <div className={`w-10 h-10 rounded-lg ${f.bg} flex items-center justify-center mb-4`}>
                <f.icon className={`w-5 h-5 ${f.color}`} />
              </div>
              <h3 className="font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-blue-300/50 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech stack */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 py-12">
        <div className="text-xs text-blue-400/60 font-mono uppercase tracking-wider text-center mb-6">Stack technique</div>
        <div className="flex flex-wrap justify-center gap-2">
          {['mistral-nemo', 'nomic-embed-text', 'pgvector', 'LangGraph', 'PyCaret', 'SHAP', 'PyOD', 'FastAPI', 'Celery', 'Redis', 'PostgreSQL', 'Next.js 14', 'Docker'].map((t) => (
            <span key={t} className="px-3 py-1 rounded-full bg-[#1B3A6B]/30 border border-blue-500/15 text-blue-300/60 text-xs font-mono">{t}</span>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 py-20">
        <div className="rounded-2xl bg-gradient-to-r from-blue-900/30 to-blue-800/20 border border-blue-500/20 p-10 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Lock className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-emerald-400 font-medium">RGPD · Données hébergées en France</span>
          </div>
          <h2 className="text-3xl font-bold mb-4">{lang === 'fr' ? 'Prêt à analyser vos données ?' : 'Ready to analyze your data?'}</h2>
          <p className="text-blue-300/60 mb-8">{lang === 'fr' ? 'Démarrez gratuitement. Aucune carte requise.' : 'Start for free. No card required.'}</p>
          <Link href="/register" className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-lg font-medium transition-all hover:shadow-[0_0_24px_rgba(37,99,235,0.4)]">
            <Zap className="w-4 h-4" /> {t(lang, 'getStarted')}
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-blue-500/10 py-8">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center">
              <Brain className="w-3 h-3 text-white" />
            </div>
            <span className="text-blue-300/60 text-sm">Analyse IA © 2025</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-blue-300/40">
            <span>RGPD Compliant</span><span>·</span><span>Hébergement France</span><span>·</span><span>Open Source</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
