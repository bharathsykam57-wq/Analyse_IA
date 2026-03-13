'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { Brain, MessageSquare, Upload, History, Shield, LogOut, Globe, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useChatStore } from '@/store/chatStore'
import { logout, isAuthenticated } from '@/lib/auth'
import { t } from '@/lib/i18n'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, isLoading } = useAuthStore()
  const { language: lang, setLanguage } = useChatStore()
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    const checkAuth = () => {
      if (!isAuthenticated()) {
        router.replace('/login')
        return
      }
      setIsChecking(false)
    }
    checkAuth()
  }, [router])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  // Show spinner while auth is being verified — prevents flash of unauthenticated content
  if (isChecking) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0A1628]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
          <span className="text-xs text-blue-300/40">
            {lang === 'fr' ? 'Vérification...' : 'Checking auth...'}
          </span>
        </div>
      </div>
    )
  }

  const navItems = [
    { href: '/dashboard', icon: MessageSquare, label: t(lang, 'dashboard') },
    { href: '/upload',    icon: Upload,         label: t(lang, 'upload') },
    { href: '/history',  icon: History,         label: t(lang, 'history') },
    { href: '/rgpd',     icon: Shield,          label: t(lang, 'rgpd') },
  ]

  return (
    <div className="h-screen flex overflow-hidden bg-[#0A1628]">
      {/* Sidebar */}
      <aside className="w-56 flex flex-col border-r border-blue-500/10 bg-[#0A1628] flex-shrink-0">
        <div className="h-14 flex items-center gap-2.5 px-4 border-b border-blue-500/10">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-white text-sm">Analyse IA</span>
        </div>

        <nav className="flex-1 py-4 px-2 space-y-0.5">
          {navItems.map((item) => {
            const active = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all ${
                  active
                    ? 'bg-blue-600/15 text-white border-l-2 border-blue-500 pl-[10px]'
                    : 'text-blue-300/60 hover:text-blue-200 hover:bg-blue-600/8'
                }`}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="p-2 border-t border-blue-500/10 space-y-0.5">
          <button
            onClick={() => setLanguage(lang === 'fr' ? 'en' : 'fr')}
            className="flex items-center gap-2.5 px-3 py-2 w-full rounded-lg text-sm text-blue-300/60 hover:text-blue-200 hover:bg-blue-600/8 transition-all"
          >
            <Globe className="w-4 h-4" />
            {lang === 'fr' ? 'English' : 'Français'}
          </button>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 px-3 py-2 w-full rounded-lg text-sm text-blue-300/60 hover:text-red-400 hover:bg-red-500/8 transition-all"
          >
            <LogOut className="w-4 h-4" />
            {t(lang, 'logout')}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        <header className="h-14 flex items-center justify-between px-6 border-b border-blue-500/10 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-blue-300/50 font-mono">
              {lang === 'fr' ? 'Système opérationnel' : 'System operational'}
            </span>
          </div>
          <span className="text-xs text-blue-300/30 font-mono">mistral-nemo · Ollama</span>
        </header>
        <div className="flex-1 overflow-hidden">{children}</div>
      </main>
    </div>
  )
}
