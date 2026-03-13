'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Brain, Mail, Lock, AlertCircle, Globe } from 'lucide-react'
import { login } from '@/lib/auth'
import { useAuthStore } from '@/store/authStore'
import { useChatStore } from '@/store/chatStore'
import { t, Lang } from '@/lib/i18n'

export default function LoginPage() {
  const router = useRouter()
  const { setAuthenticated } = useAuthStore()
  const { setLanguage } = useChatStore()
  // Local lang state — page always loads in FR regardless of store
  const [lang, setLang] = useState<Lang>('fr')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLangToggle = () => {
    const next: Lang = lang === 'fr' ? 'en' : 'fr'
    setLang(next)
    setLanguage(next) // sync store so dashboard opens in same language
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login({ email, password })
      setAuthenticated(true)
      router.push('/dashboard')
    } catch {
      setError(t(lang, 'loginError'))
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    background: 'rgba(15,31,61,0.8)',
    border: '1px solid rgba(37,99,235,0.15)',
    color: '#E8F0FB',
  }

  return (
    <div className="min-h-screen bg-[#0A1628] bg-grid flex items-center justify-center px-4">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-blue-600/8 rounded-full blur-[100px]" />
      </div>

      {/* Language toggle — top right */}
      <button
        onClick={handleLangToggle}
        className="fixed top-4 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0F1F3D]/80 border border-blue-500/15 text-blue-300/60 hover:text-blue-300 text-xs transition-all"
      >
        <Globe className="w-3.5 h-3.5" />
        {lang === 'fr' ? 'EN' : 'FR'}
      </button>

      <div className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 mb-4">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">{t(lang, 'loginTitle')}</h1>
          <p className="text-blue-300/60 text-sm mt-1">{t(lang, 'loginSubtitle')}</p>
        </div>

        <div className="bg-[#0F1F3D]/70 backdrop-blur-sm border border-blue-500/15 rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm text-blue-200/70 mb-1.5 font-medium">
                {t(lang, 'email')}
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400/40" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="vous@entreprise.fr"
                  required
                  style={inputStyle}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-blue-200/70 mb-1.5 font-medium">
                {t(lang, 'password')}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400/40" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={inputStyle}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-sm transition-all hover:shadow-[0_0_16px_rgba(37,99,235,0.3)]"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {lang === 'fr' ? 'Connexion...' : 'Signing in...'}
                </span>
              ) : (
                t(lang, 'login')
              )}
            </button>
          </form>

          <p className="text-center text-sm text-blue-300/50 mt-6">
            {t(lang, 'noAccount')}{' '}
            <Link href="/register" className="text-blue-400 hover:text-blue-300 transition-colors">
              {t(lang, 'register')}
            </Link>
          </p>
        </div>

        {/* RGPD note */}
        <div className="mt-4 flex items-center justify-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <p className="text-xs text-emerald-400/60">
            {lang === 'fr'
              ? 'Données hébergées en France · RGPD conforme'
              : 'Data hosted in France · GDPR compliant'}
          </p>
        </div>
      </div>
    </div>
  )
}
