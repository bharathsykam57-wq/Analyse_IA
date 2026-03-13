'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, Download, Trash2, ScrollText, AlertTriangle, CheckCircle, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import { t } from '@/lib/i18n'
import { useChatStore } from '@/store/chatStore'
import { RgpdConsent, AuditEntry } from '@/types'
import { formatDate } from '@/lib/utils'

export default function RgpdPage() {
  const { language: lang } = useChatStore()
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteSuccess, setDeleteSuccess] = useState(false)
  const [exportSuccess, setExportSuccess] = useState(false)

  const { data: consent } = useQuery<RgpdConsent>({
    queryKey: ['rgpd-consent'],
    queryFn: async () => (await api.get('/rgpd/consent')).data,
  })

  const { data: auditLog = [] } = useQuery<AuditEntry[]>({
    queryKey: ['rgpd-audit'],
    queryFn: async () => (await api.get('/rgpd/audit')).data,
  })

  const consentMutation = useMutation({
    mutationFn: (data: Partial<RgpdConsent>) => api.post('/rgpd/consent', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rgpd-consent'] }),
  })

  const handleExport = async () => {
    try {
      const res = await api.get('/rgpd/export', { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `analyse-ia-export-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      setExportSuccess(true)
      setTimeout(() => setExportSuccess(false), 3000)
    } catch { /* ignore */ }
  }

  const handleDelete = async () => {
    try {
      await api.delete('/rgpd/erasure')
      setDeleteSuccess(true)
      setShowDeleteConfirm(false)
    } catch { /* ignore */ }
  }

  const consents = [
    { key: 'analytics' as const, label: t(lang, 'analyticsConsent'), desc: lang === 'fr' ? 'Analyse statistique de vos données' : 'Statistical analysis of your data' },
    { key: 'storage' as const, label: t(lang, 'storageConsent'), desc: lang === 'fr' ? 'Stockage sécurisé de vos fichiers' : 'Secure storage of your files' },
    { key: 'ai_processing' as const, label: t(lang, 'aiConsent'), desc: lang === 'fr' ? 'Traitement par les modèles IA locaux' : 'Processing by local AI models' },
  ]

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-600/15 flex items-center justify-center">
              <Shield className="w-4 h-4 text-emerald-400" />
            </div>
            <h1 className="text-xl font-semibold text-white">{t(lang, 'rgpdTitle')}</h1>
          </div>
          <p className="text-sm text-blue-300/50 ml-11">{t(lang, 'rgpdSubtitle')}</p>
        </div>

        <div className="space-y-4">
          {/* Consents */}
          <Section title={t(lang, 'consentTitle')} icon={CheckCircle}>
            <div className="space-y-4">
              {consents.map(({ key, label, desc }) => {
                const active = consent?.[key] ?? false
                return (
                  <div key={key} className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm text-white font-medium">{label}</p>
                      <p className="text-xs text-blue-300/40 mt-0.5">{desc}</p>
                    </div>
                    <button
                      onClick={() => consentMutation.mutate({ [key]: !active })}
                      className={`relative w-10 h-5 rounded-full transition-all flex-shrink-0 ${active ? 'bg-emerald-500' : 'bg-blue-900/60'}`}>
                      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${active ? 'left-5' : 'left-0.5'}`} />
                    </button>
                  </div>
                )
              })}
            </div>
          </Section>

          {/* Rights */}
          <Section title={lang === 'fr' ? 'Vos droits' : 'Your rights'} icon={ScrollText}>
            <div className="space-y-2">
              <ActionRow icon={Download} label={t(lang, 'exportData')}
                desc={lang === 'fr' ? 'Téléchargez toutes vos données au format JSON' : 'Download all your data as JSON'}
                iconColor="text-blue-400" iconBg="bg-blue-600/10"
                onClick={handleExport} success={exportSuccess} />
              <ActionRow icon={Trash2} label={t(lang, 'deleteData')}
                desc={lang === 'fr' ? 'Suppression définitive et irrévocable' : 'Permanent and irreversible deletion'}
                iconColor="text-red-400" iconBg="bg-red-600/10"
                onClick={() => setShowDeleteConfirm(true)} danger />
            </div>

            {showDeleteConfirm && (
              <div className="mt-4 p-4 rounded-xl bg-red-500/8 border border-red-500/20">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-white">{t(lang, 'confirmDelete')}</p>
                    <p className="text-xs text-red-400/70 mt-1">{t(lang, 'deleteWarning')}</p>
                    <div className="flex gap-2 mt-3">
                      <button onClick={handleDelete}
                        className="px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-medium transition-all">
                        {t(lang, 'confirm')}
                      </button>
                      <button onClick={() => setShowDeleteConfirm(false)}
                        className="px-4 py-1.5 rounded-lg border border-blue-500/20 hover:border-blue-500/40 text-blue-300 text-xs font-medium transition-all">
                        {t(lang, 'cancel')}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {deleteSuccess && (
              <div className="mt-3 flex items-center gap-2 text-emerald-400 text-sm">
                <CheckCircle className="w-4 h-4" />
                {lang === 'fr' ? 'Données supprimées avec succès' : 'Data deleted successfully'}
              </div>
            )}
          </Section>

          {/* Audit log */}
          <Section title={t(lang, 'auditLog')} icon={ScrollText}>
            {auditLog.length === 0 ? (
              <p className="text-sm text-blue-300/30">{lang === 'fr' ? 'Aucune entrée dans le journal' : 'No audit entries'}</p>
            ) : (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {auditLog.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3 py-2 border-b border-blue-500/5 last:border-0">
                    <span className="text-[10px] font-mono text-blue-300/30 flex-shrink-0 mt-0.5 whitespace-nowrap">
                      {formatDate(entry.timestamp, lang)}
                    </span>
                    <span className="text-xs text-blue-300/60">{entry.action}</span>
                    {entry.details && (
                      <span className="text-[10px] text-blue-300/30 truncate ml-auto">{entry.details}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* Legal notice */}
          <div className="px-4 py-3 rounded-xl bg-blue-600/5 border border-blue-500/10">
            <p className="text-xs text-blue-300/40 leading-relaxed">
              {lang === 'fr'
                ? "Vos données sont stockées sur des serveurs sécurisés en France. Conformément au RGPD (UE) 2016/679, vous disposez de droits d'accès (Art. 15), de rectification (Art. 16), d'effacement (Art. 17) et de portabilité (Art. 20)."
                : 'Your data is stored on secure servers in France. Under GDPR (EU) 2016/679, you have rights of access (Art. 15), rectification (Art. 16), erasure (Art. 17), and portability (Art. 20).'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-[#0F1F3D]/60 border border-blue-500/10 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-blue-400/60" />
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      {children}
    </div>
  )
}

function ActionRow({ icon: Icon, label, desc, iconColor, iconBg, onClick, danger, success }: {
  icon: React.ElementType; label: string; desc: string
  iconColor: string; iconBg: string; onClick: () => void
  danger?: boolean; success?: boolean
}) {
  return (
    <button onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-all text-left ${
        danger
          ? 'border-red-500/10 hover:border-red-500/25 hover:bg-red-500/5'
          : 'border-blue-500/10 hover:border-blue-500/25 hover:bg-blue-500/5'
      }`}>
      <div className={`w-8 h-8 rounded-lg ${iconBg} flex items-center justify-center flex-shrink-0`}>
        {success
          ? <CheckCircle className="w-4 h-4 text-emerald-400" />
          : <Icon className={`w-4 h-4 ${iconColor}`} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">{label}</p>
        <p className="text-xs text-blue-300/40">{desc}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-blue-300/30 flex-shrink-0" />
    </button>
  )
}
