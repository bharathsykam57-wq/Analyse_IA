'use client'

import { useState, useRef, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Upload, FileSpreadsheet, FileText, CheckCircle, AlertCircle, Loader2, Clock } from 'lucide-react'
import api from '@/lib/api'
import { UploadedFile } from '@/types'
import { t, Lang } from '@/lib/i18n'
import { useChatStore } from '@/store/chatStore'
import { formatFileSize, formatDate, normalizeFiles } from '@/lib/utils'

type UType = 'csv' | 'pdf'

function useUpload(type: UType, lang: Lang, onSuccess: () => void) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const upload = useCallback(async (file: File) => {
    setError(''); setSuccess('')
    const max = type === 'csv' ? 50 * 1024 * 1024 : 20 * 1024 * 1024
    if (file.size > max) { setError(t(lang, 'fileTooLarge')); return }
    const form = new FormData()
    form.append('file', file)
    setUploading(true); setProgress(0)
    try {
      await api.post(`/files/upload/${type}`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      setSuccess(t(lang, 'uploadSuccess'))
      onSuccess()
    } catch {
      setError(t(lang, 'uploadError'))
    } finally {
      setUploading(false); setProgress(0)
    }
  }, [type, lang, onSuccess])

  return { uploading, progress, error, success, upload }
}

export default function UploadPage() {
  const { language: lang } = useChatStore()
  const queryClient = useQueryClient()
  const refetch = useCallback(() => queryClient.invalidateQueries({ queryKey: ['files'] }), [queryClient])

  const csv = useUpload('csv', lang, refetch)
  const pdf = useUpload('pdf', lang, refetch)
  const csvRef = useRef<HTMLInputElement>(null)
  const pdfRef = useRef<HTMLInputElement>(null)

  const { data: files = [], isLoading } = useQuery<UploadedFile[]>({
    queryKey: ['files'],
    queryFn: async () => {
      try {
        const res = await api.get('/files/list')
        const raw = Array.isArray(res.data) ? res.data : (res.data.files ?? []); return normalizeFiles(raw)
      } catch {
        return []
      }
    },
    refetchInterval: 5000,
  })

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-white">{t(lang, 'uploadTitle')}</h1>
          <p className="text-sm text-blue-300/50 mt-1">{t(lang, 'uploadSubtitle')}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <DropZone type="csv" lang={lang} state={csv} inputRef={csvRef}
            onDrop={(e) => { const f = e.dataTransfer.files[0]; if (f) csv.upload(f) }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) csv.upload(f) }} />
          <DropZone type="pdf" lang={lang} state={pdf} inputRef={pdfRef}
            onDrop={(e) => { const f = e.dataTransfer.files[0]; if (f) pdf.upload(f) }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) pdf.upload(f) }} />
        </div>
        <h2 className="text-sm font-medium text-blue-200/70 mb-3">{t(lang, 'fileList')}</h2>
        {isLoading ? (
          <div className="flex items-center gap-2 text-blue-300/50 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            {lang === 'fr' ? 'Chargement...' : 'Loading...'}
          </div>
        ) : files.length === 0 ? (
          <p className="text-sm text-blue-300/30 py-8 text-center">{t(lang, 'noFiles')}</p>
        ) : (
          <div className="space-y-2">
            {files.map((f) => <FileRow key={f.file_id} file={f} lang={lang} />)}
          </div>
        )}
      </div>
    </div>
  )
}

function DropZone({ type, lang, state, inputRef, onDrop, onChange }: {
  type: UType; lang: Lang
  state: ReturnType<typeof useUpload>
  inputRef: React.RefObject<HTMLInputElement>
  onDrop: (e: React.DragEvent) => void
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
}) {
  const [over, setOver] = useState(false)
  const isCSV = type === 'csv'
  const color = isCSV ? 'text-emerald-400' : 'text-blue-400'
  const bg = isCSV ? 'bg-emerald-600/10' : 'bg-blue-600/10'
  const Icon = isCSV ? FileSpreadsheet : FileText

  return (
    <div
      className={`rounded-xl border-2 border-dashed transition-all cursor-pointer ${over ? `${isCSV ? 'border-emerald-500/40' : 'border-blue-500/40'} bg-blue-500/5` : 'border-blue-500/15 hover:border-blue-500/30'}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { setOver(false); onDrop(e) }}
      onClick={() => inputRef.current?.click()}
    >
      <input ref={inputRef} type="file" accept={isCSV ? '.csv' : '.pdf'} className="hidden" onChange={onChange} />
      <div className="p-8 flex flex-col items-center text-center">
        <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center mb-4`}>
          {state.uploading ? <Loader2 className={`w-6 h-6 ${color} animate-spin`} /> : <Icon className={`w-6 h-6 ${color}`} />}
        </div>
        <p className="font-medium text-white text-sm mb-1">
          {state.uploading ? t(lang, 'uploading') : (isCSV ? t(lang, 'dropCSV') : t(lang, 'dropPDF'))}
        </p>
        <p className="text-xs text-blue-300/40">{isCSV ? t(lang, 'csvLimit') : t(lang, 'pdfLimit')}</p>
        {state.uploading && (
          <div className="w-full mt-4">
            <div className="h-1 bg-blue-900/40 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${isCSV ? 'bg-emerald-500' : 'bg-blue-500'}`} style={{ width: `${state.progress}%` }} />
            </div>
            <p className="text-xs text-blue-300/40 mt-1">{state.progress}%</p>
          </div>
        )}
        {state.error && <div className="flex items-center gap-1.5 mt-3 text-red-400 text-xs"><AlertCircle className="w-3.5 h-3.5" />{state.error}</div>}
        {state.success && <div className="flex items-center gap-1.5 mt-3 text-emerald-400 text-xs"><CheckCircle className="w-3.5 h-3.5" />{state.success}</div>}
        {!state.uploading && !state.error && !state.success && (
          <button className="mt-4 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600/15 hover:bg-blue-600/25 border border-blue-500/20 text-blue-300 text-xs transition-all">
            <Upload className="w-3 h-3" />{lang === 'fr' ? 'Parcourir' : 'Browse'}
          </button>
        )}
      </div>
    </div>
  )
}

function FileRow({ file, lang }: { file: UploadedFile; lang: Lang }) {
  const isCSV = file.type === 'csv'
  const Icon = isCSV ? FileSpreadsheet : FileText
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#0F1F3D]/60 border border-blue-500/10 hover:border-blue-500/20 transition-all">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${isCSV ? 'bg-emerald-600/10' : 'bg-blue-600/10'}`}>
        <Icon className={`w-4 h-4 ${isCSV ? 'text-emerald-400' : 'text-blue-400'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate font-medium">{file.original_name}</p>
        <p className="text-xs text-blue-300/40">{formatFileSize(file.size_bytes)} · {formatDate(file.uploaded_at, lang)}</p>
      </div>
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border bg-amber-500/10 border-amber-500/20 text-amber-400 flex-shrink-0">
        <Clock className="w-3 h-3" />{t(lang, 'statusPending')}
      </span>
    </div>
  )
}
