import type { AnalysisCreate, AnalysisCreated, AnalysisStatus, Crop, Parcel, Place, Report, ReportVariant } from './types'

export class ApiRequestError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown }
      if (typeof first.msg === 'string') return first.msg.replace(/^Value error, /, '')
    }
  }
  return status >= 500 ? 'Serwer chwilowo nie odpowiada. Spróbuj ponownie za chwilę.' : 'Nieprawidłowe zapytanie.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body: unknown = await resp.json().catch(() => null)
  if (!resp.ok) throw new ApiRequestError(resp.status, errorMessage(body, resp.status))
  return body as T
}

/** Time range of the water chart chosen on the page; passed to the full PDF and the print view. */
export interface ChartRangeQuery {
  key: string
  start?: string
  end?: string
}

function reportQuery(variant: ReportVariant, range?: ChartRangeQuery): string {
  const q = new URLSearchParams({ variant })
  if (range && variant === 'full') {
    q.set('range', range.key)
    if (range.key === 'custom' && range.start && range.end) {
      q.set('start', range.start)
      q.set('end', range.end)
    }
  }
  return q.toString()
}

export const api = {
  crops: () => request<Crop[]>('/crops'),
  parcelById: (id: string) => request<Parcel>(`/parcels?id=${encodeURIComponent(id)}`),
  parcelByPoint: (lat: number, lon: number) => request<Parcel>(`/parcels?lat=${lat}&lon=${lon}`),
  places: (q: string) => request<Place[]>(`/places?q=${encodeURIComponent(q)}`),
  createAnalysis: (body: AnalysisCreate) =>
    request<AnalysisCreated>('/analyses', { method: 'POST', body: JSON.stringify(body) }),
  analysis: (id: string) => request<AnalysisStatus>(`/analyses/${encodeURIComponent(id)}`),
  report: (id: string) => request<Report>(`/reports/${encodeURIComponent(id)}`),
  reportPdfUrl: (id: string, variant: ReportVariant, range?: ChartRangeQuery) =>
    `/api/reports/${encodeURIComponent(id)}.pdf?${reportQuery(variant, range)}`,
  reportPrintUrl: (id: string, variant: ReportVariant, range?: ChartRangeQuery) =>
    `/api/reports/${encodeURIComponent(id)}.html?${reportQuery(variant, range)}`,
}
