import type { Journey, OrderView } from './types'

export const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(API + path, {
    ...init,
    headers: init.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const body = await res.json()
      msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body ?? {}) })

export const api = {
  health: () => request<{ ok: boolean; llm_configured: boolean }>('/health'),
  start: (lang: string, partner_code?: string | null) => post<Journey>('/api/journeys', { lang, partner_code }),
  journey: (id: string) => request<Journey>(`/api/journeys/${id}`),
  resume: (id: string, value: Record<string, unknown>) => post<Journey>(`/api/journeys/${id}/resume`, { value }),
  setLang: (id: string, lang: string) => post<Journey>(`/api/journeys/${id}/lang`, { lang }),
  upload: (id: string, docType: string, file?: File, specimen?: string) => {
    const fd = new FormData()
    fd.append('doc_type', docType)
    if (file) fd.append('file', file)
    if (specimen) fd.append('specimen', specimen)
    return post<UploadResult>(`/api/journeys/${id}/documents`, fd)
  },
  digilocker: (id: string, gstin?: string, udyam_number?: string) =>
    post<{ documents: UploadResult[] }>(`/api/journeys/${id}/digilocker`, { gstin, udyam_number }),
  feedback: (id: string, rating: number, reason?: string, comment?: string) =>
    post<{ ok: boolean }>(`/api/journeys/${id}/feedback`, { rating, reason, comment }),
  withdraw: (id: string, purposes: string[]) =>
    post<{ withdrawn: string[]; documents_erased: number }>(`/api/journeys/${id}/consent/withdraw`, { purposes }),
  gstin: (g: string) => request<RegistryResult>(`/api/registry/gstin/${encodeURIComponent(g)}`),
  udyam: (u: string, gstin?: string) =>
    request<UdyamResult>(`/api/registry/udyam/${encodeURIComponent(u)}${gstin ? `?gstin=${encodeURIComponent(gstin)}` : ''}`),
  order: (id: string) => request<OrderView>(`/api/orders/${id}`),
  advance: (id: string) => post<OrderView>(`/api/orders/${id}/advance`),
  ask: (id: string, question: string, lang: string) =>
    post<{ answer: string; model: string }>(`/api/orders/${id}/ask`, { question, lang }),
  transcribe: (audio: Blob, lang: string) => {
    const fd = new FormData()
    fd.append('audio', audio, 'speech.webm')
    fd.append('lang', lang)
    return post<{ text: string }>('/api/voice/transcribe', fd)
  },
  backoffice: <T>(path: string, key: string, init: RequestInit = {}) =>
    request<T>(`/api/backoffice${path}`, { ...init, headers: { 'X-Backoffice-Key': key, 'Content-Type': 'application/json' } }),
}

export interface UploadResult {
  doc_type: string
  detected_type?: string
  fields: Record<string, string>
  checks: Check[]
  extractor?: string
  source: string
}

export interface RegistryResult {
  valid_format: boolean
  found: boolean
  problems?: string[]
  legal_name?: string
  trade_name?: string
  status?: string
  state?: string
  constitution?: string
}

export interface UdyamResult {
  valid_format: boolean
  found: boolean
  problems?: string[]
  enterprise_name?: string
  enterprise_type?: string
  major_activity?: string
  state?: string
  city?: string
  gst_match?: boolean
  gst_trade_name?: string
}

export interface Check {
  id: string
  status: 'pass' | 'warn' | 'fail'
  message: string
  doc?: string | null
}
