'use client'

import Link from 'next/link'
import { AlertCircle } from 'lucide-react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="min-h-screen bg-[#0A1628] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-6">
          <AlertCircle className="w-8 h-8 text-red-400" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">
          Une erreur est survenue
        </h1>
        <p className="text-sm text-blue-300/60 mb-6">
          {error?.message || 'Something went wrong. Please try again.'}
        </p>
        <div className="flex flex-col gap-3">
          <button
            onClick={reset}
            className="inline-flex items-center justify-center px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all"
          >
            Réessayer
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center px-6 py-2.5 rounded-lg border border-blue-500/20 hover:border-blue-500/40 text-blue-300 hover:text-blue-200 font-medium transition-all"
          >
            Accueil
          </Link>
        </div>
      </div>
    </div>
  )
}
