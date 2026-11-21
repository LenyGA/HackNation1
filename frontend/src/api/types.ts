// Hand-written mirror of backend/app/api/schemas.py. Change both sides together and tell the team.

export type SourceStatus = 'ok' | 'degraded' | 'missing'
export type Confidence = 'high' | 'medium' | 'low'

export interface Health {
  status: string
  app: string
  version: string
}

export interface Crop {
  id: string
  name_pl: string
}

export interface GeoJsonGeometry {
  type: string
  coordinates: unknown
}

export interface Parcel {
  id: string
  voivodeship: string | null
  county: string | null
  commune: string | null
  precinct: string | null
  number: string | null
  area_ha: number
  centroid_lat: number
  centroid_lon: number
  geometry: GeoJsonGeometry
}

export interface AnalysisCreate {
  parcel_id: string
  crop_id: string
  analysis_date: string // ISO date YYYY-MM-DD
}

export interface AnalysisCreated {
  id: string
}

export type AnalysisState = 'queued' | 'running' | 'done' | 'failed'
export type SourceProgressState = 'pending' | SourceStatus

export interface SourceProgress {
  name: string
  label_pl: string
  status: SourceProgressState
}

export interface AnalysisStatus {
  id: string
  status: AnalysisState
  sources: SourceProgress[]
  report_id: string | null
  error_pl: string | null
}

export interface ReportSection {
  id: string
  title_pl: string
  paragraphs_pl: string[]
}

export interface Report {
  id: string
  created_at: string
  app: string
  parcel: Parcel
  crop: Crop
  analysis_date: string
  sections: ReportSection[]
}

export interface ApiError {
  detail: string
}
