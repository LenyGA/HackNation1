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

export interface Period {
  start: string // ISO date
  end: string
}

export interface Uncertainty {
  level: Confidence
  reason_pl: string
}

export interface EvidenceItem {
  key: string
  label_pl: string
  value: number | null
  value_pl: string // formatted for the farmer, with unit
  unit: string
  source: string
  period: Period | null
  uncertainty: Uncertainty
}

export type HeadlineLevel = 'none' | 'light' | 'moderate' | 'severe' | 'unknown'

export interface Headline {
  level: HeadlineLevel
  label_pl: string
  sentence_pl: string
  confidence: Confidence
  confidence_pl: string
}

export type SectionId =
  | 'summary'
  | 'current'
  | 'vulnerability'
  | 'causes'
  | 'retention'
  | 'agrotech'
  | 'irrigation'
  | 'sources'
  | 'limitations'

export interface ReportSection {
  id: SectionId
  number: number
  title_pl: string
  paragraphs_pl: string[]
  details_pl: string[] // "Szczegóły dla zainteresowanych" (technical terms allowed)
  indicators: EvidenceItem[]
  recommendation_numbers: number[]
}

export type RecommendationCategory = 'retention' | 'agrotech' | 'irrigation'
export type LocationKind = 'ditch' | 'depression' | 'flow_path' | 'outlet' | 'wetland' | 'water_body'

export interface RecommendationLocation {
  kind: LocationKind
  geometry: GeoJsonGeometry
}

export interface ReportRecommendation {
  number: number
  id: string
  category: RecommendationCategory
  title_pl: string
  text_pl: string
  evidence: EvidenceItem[] // "Dlaczego?"
  locations: RecommendationLocation[]
}

export type IrrigationStatus =
  | 'no_assessment'
  | 'off_season'
  | 'no_crop'
  | 'late_stage'
  | 'no_balance'
  | 'not_needed'
  | 'wait_for_rain'
  | 'irrigate'
  | 'irrigate_soon'

export interface ProjectedDay {
  day: string
  precip_mm: number
  et0_mm: number
  depletion_mm: number
}

export interface ReportIrrigation {
  status: IrrigationStatus
  applicable: boolean
  title_pl: string
  text_pl: string
  caveats_pl: string[]
  dose_mm: number | null
  single_dose_max_mm: number | null
  applications: number | null
  volume_m3: number | null
  within_days: number | null
  irrigate_by: string | null
  forecast: 'used' | 'historical' | 'unavailable'
  projection: ProjectedDay[]
  evidence: EvidenceItem[]
}

export interface MonthRisk {
  month: number
  month_pl: string
  years_with_data: number
  deficit_years: number
  frequency_pct: number | null
  risk: boolean
  critical: boolean
}

export interface ChartPoint {
  day: string
  precip_mm: number | null // cumulative from chart start
  crop_need_mm: number | null // cumulative crop water need
  precip_hist_median_mm: number | null
  precip_hist_min_mm: number | null
  precip_hist_max_mm: number | null
}

export interface SeasonChart {
  start: string
  end: string
  years: number
  source: string
  points: ChartPoint[]
}

export type MapFeatureKind =
  | 'depression'
  | 'flow_path'
  | 'outlet'
  | 'ditch'
  | 'watercourse'
  | 'water_body'
  | 'wetland'
  | 'trees'

export interface MapFeature {
  kind: MapFeatureKind
  label_pl: string
  geometry: GeoJsonGeometry
  recommendation_numbers: number[]
}

export interface ReportMap {
  parcel: GeoJsonGeometry
  features: MapFeature[]
  legend_pl: Partial<Record<MapFeatureKind, string>>
}

export interface SourceEntry {
  name: string
  label_pl: string
  status: SourceStatus
  source: string
  license: string
  fetched_at: string
  period: Period | null
  uncertainty: Uncertainty
  message_pl: string | null
}

export interface Report {
  id: string
  created_at: string
  app: string
  version: string
  parcel: Parcel
  crop: Crop
  analysis_date: string
  complete: boolean
  headline: Headline
  sections: ReportSection[]
  recommendations: ReportRecommendation[]
  irrigation: ReportIrrigation
  months: MonthRisk[]
  chart: SeasonChart | null
  map: ReportMap
  sources: SourceEntry[]
  limitations_pl: string[]
  missing_data_pl: string[]
}

export interface ApiError {
  detail: string
}
