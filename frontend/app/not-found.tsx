import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0A1628] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <h1 className="text-6xl font-bold text-blue-400 mb-4">404</h1>
        <h2 className="text-2xl font-bold text-white mb-2">
          Page introuvable
        </h2>
        <p className="text-sm text-blue-300/60 mb-8">
          La page que vous recherchez n&apos;existe pas.
        </p>
        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all"
        >
          Retour à l&apos;accueil
        </Link>
      </div>
    </div>
  )
}
