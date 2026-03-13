import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(dateStr: string, locale: 'fr' | 'en' = 'fr'): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale === 'fr' ? 'fr-FR' : 'en-US', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function generateId(): string {
  return Math.random().toString(36).slice(2, 11)
}

// Extract file_id and original_name from backend filename
// e.g. "febeb67d-348d-408f-bd8f-0f2c0d1deb0f_Telco-Customer-Churn.csv"
export function parseFilename(filename: string): { file_id: string; original_name: string } {
  const uuidRegex = /^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})_(.+)$/i
  const match = filename.match(uuidRegex)
  if (match) {
    return { file_id: match[1], original_name: match[2] }
  }
  return { file_id: filename, original_name: filename }
}

// Normalize file list from backend adding derived fields
export function normalizeFiles(raw: { filename: string; type: string; size_bytes: number; uploaded_at: string }[]): import('@/types').UploadedFile[] {
  return raw.map(f => ({
    ...f,
    type: f.type as 'csv' | 'pdf',
    ...parseFilename(f.filename),
  }))
}
