'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Brain, Mail, Lock, User, AlertCircle, CheckCircle, Globe } from 'lucide-react'
import { register, login } from '@/lib/auth'
import { useAuthStore } from '@/store/authStore'
import { useChatStore } from '@/store/chatStore'
import { t, Lang } from '@/lib/i18n'

export default function RegisterPage() {
  const router = useRouter()
  const { setAuthenticated } = useAuthStore()
  const { setLanguage } = useChatStore()
  // Local lang state — page always loads in FR
  const [lang, setLang] = useState<Lang>('fr')
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleLangToggle = () => {
    const next: Lang = lang === 'fr' ? 'en' : 'fr'
    setLang(next)
    setLanguage(next)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register(form)
      setSuccess(true)
      await login({ email: form.email, password: form.password })
      setAuthenticated(true)
      setTimeout(() => router.push('/dashboard'), 800)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || t(lang, 'serverError'))
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

      {/* Language toggle */}
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
          <h1 className="text-2xl font-bold text-white">{t(lang, 'registerTitle')}</h1>
          <p className="text-blue-300/60 text-sm mt-1">{t(lang, 'registerSubtitle')}</p>
        </div>

        <div className="bg-[#0F1F3D]/70 backdrop-blur-sm border border-blue-500/15 rounded-2xl p-8">
          {success ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <CheckCircle className="w-10 h-10 text-emerald-400" />
              <p className="text-white font-medium">{t(lang, 'registerSuccess')}</p>
              <p className="text-blue-300/50 text-sm">
                {lang === 'fr' ? 'Redirection vers le tableau de bord...' : 'Redirecting to dashboard...'}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm text-blue-200/70 mb-1.5 font-medium">
                  {t(lang, 'fullName')}
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400/40" />
                  <input
                    type="text"
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    placeholder={lang === 'fr' ? 'Jean Dupont' : 'John Doe'}
                    style={inputStyle}
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-blue-200/70 mb-1.5 font-medium">
                  {t(lang, 'email')}
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400/40" />
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
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
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    placeholder="••••••••"
                    required
                    minLength={8}
                    style={inputStyle}
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none"
                  />
                </div>
                <p className="text-[11px] text-blue-300/30 mt-1">
                  {lang === 'fr' ? 'Minimum 8 caractères' : 'Minimum 8 characters'}
                </p>
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
                    {lang === 'fr' ? 'Création...' : 'Creating...'}
                  </span>
                ) : (
                  t(lang, 'register')
                )}
              </button>
            </form>
          )}

          {!success && (
            <p className="text-center text-sm text-blue-300/50 mt-6">
              {t(lang, 'hasAccount')}{' '}
              <Link href="/login" className="text-blue-400 hover:text-blue-300 transition-colors">
                {t(lang, 'login')}
              </Link>
            </p>
          )}
        </div>

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
