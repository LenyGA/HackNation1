// Hand-written mirror of backend/app/api/schemas.py. Change both sides together and tell the team.

export type SourceStatus = 'ok' | 'degraded' | 'missing'
export type Confidence = 'high' | 'medium' | 'low'

export interface Health {
  status: string
  app: string
  version: string
}

export type CropKind = 'arable' | 'grassland' | 'fruit'

export interface Crop {
  id: string
  name_pl: string
  kind: CropKind
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
  // Farm mode (G11): up to MAX_EXTRA_PARCELS more parcels within 2 km; omitted or [] = one parcel.
  extra_parcel_ids?: string[]
}

export const MAX_EXTRA_PARCELS = 5

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
  verdict_pl: string | null // one-sentence verdict for the basic report (null = not shown there)
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

/** now = act from the analysis date; season = before the next growing season (plan M3.5). */
export type Horizon = 'now' | 'season'
/** Basic = 1–2 pages (verdicts, actions, missing data, limitations, sources); full = every section. */
export type ReportVariant = 'basic' | 'full'

export interface ReportRecommendation {
  number: number
  id: string
  category: RecommendationCategory
  title_pl: string
  text_pl: string
  summary_pl: string // first sentence of text_pl (basic report)
  evidence: EvidenceItem[] // "Dlaczego?"
  locations: RecommendationLocation[]
  horizon: Horizon
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
  single_dose_mm: number | null // dose_mm / applications, rounded once in the backend
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
  severe_years: number // years with water stress on at least half of the days
  mean_stress_days: number | null
}

export interface StressRow {
  year: number
  stress_days: (number | null)[] // per month of StressHeatmap.months
  season_days: (number | null)[]
}

export interface StressHeatmap {
  months: number[]
  months_pl: string[]
  rows: StressRow[]
  source: string
}

export interface TrendYear {
  year: number
  value: number | null
}

export interface TrendMetric {
  key: string
  label_pl: string
  unit: string
  values: TrendYear[]
  mean_all: number | null
  mean_mid: number | null // last 3 seasons
  mean_recent: number | null // last 2 seasons
  slope_per_decade: number | null
  direction: 'worse' | 'stable' | 'better' | null
  recent: 'critical' | 'worse' | 'typical' | 'better' | null
  summary_pl: string
}

export type TrendLevel = 'critical' | 'worse' | 'stable' | 'better' | 'unknown'

export interface ClimateTrends {
  seasons: number[]
  level: TrendLevel
  label_pl: string
  verdict_pl: string[]
  metrics: TrendMetric[]
  source: string
  uncertainty_pl: string
}

export interface WaterPlanMonth {
  month: number
  month_pl: string
  years: number
  crop_need_mm: number | null
  precip_mm: number | null
  deficit_median_mm: number | null
  deficit_p80_mm: number | null
  deficit_p90_mm: number | null
  deficit_p80_m3_ha: number | null
  critical: boolean
}

export interface WaterPlan {
  method: 'root_zone' | 'crop_balance'
  years: number
  months: WaterPlanMonth[]
  season_median_mm: number | null
  season_p80_mm: number | null
  season_p90_mm: number | null
  season_p80_m3_parcel: number | null
  season_p80_m3_parcel_gross: number | null
  efficiency_pct: number
  technology?: 'reel' | 'pivot' | 'drip' | 'none' // absent in reports saved before G10
  critical_p80_mm: number | null
  critical_p80_m3_parcel_gross: number | null
  pond_side_m: number | null
  pond_depth_m: number
  text_pl: string[]
  source: string
}

export type RetentionMethodStatus = 'recommended' | 'conditional' | 'not_recommended' | 'no_data'

/** G9: how much of the dry-year irrigation need the main depression on the parcel could hold. */
export interface RetentionCoverage {
  status: 'ok' | 'no_terrain' | 'no_depression' | 'no_plan' | 'no_need'
  volume_m3: number | null
  full_need_m3: number | null
  rescue_need_m3: number | null
  full_pct: number | null
  rescue_pct: number | null
  text_pl: string
  source: string
}

export interface RetentionMethod {
  id: 'pond' | 'weir' | 'rainwater' | 'well' | 'tree_belts'
  label_pl: string
  status: RetentionMethodStatus
  status_pl: string
  reason_pl: string
  legal_pl: string | null
  evidence: EvidenceItem[]
}

export interface RetentionPlan {
  coverage: RetentionCoverage
  methods: RetentionMethod[]
  legal_basis_pl: string
}

export type IrrigationTechnology = 'reel' | 'pivot' | 'drip' | 'none'
export type EconomicsStatus = 'ok' | 'no_balance' | 'no_crop_data' | 'no_price' | 'not_needed'
export type EconomicsVerdict = 'profitable' | 'borderline' | 'unprofitable' | 'unknown'

/** G10: defaults the farmer can change in the browser; ranges low–high. */
export interface EconomicsAssumptions {
  yield_t_ha: number | null
  price_zl_t_low: number | null
  price_zl_t_high: number | null
  ky: number | null
  capex_zl_ha_low: number | null
  capex_zl_ha_high: number | null
  lifetime_years: number | null
  water_source_zl_low: number
  water_source_zl_high: number
  water_source_lifetime_years: number
  operating_zl_m3_low: number
  operating_zl_m3_high: number
}

export interface EconomicsSeason {
  year: number
  loss_pct: number
}

/** G10: irrigation technology for the parcel's area and shape, and whether it pays off. */
export interface IrrigationEconomics {
  technology: IrrigationTechnology
  technology_pl: string
  technology_text_pl: string[]
  efficiency_pct: number
  length_m: number | null
  width_m: number | null
  status: EconomicsStatus
  verdict: EconomicsVerdict
  verdict_pl: string
  text_pl: string[]
  area_ha: number
  mean_loss_share: number | null
  seasons: EconomicsSeason[]
  critical_deficit_years: number | null
  years_counted: number | null
  water_m3_ha: number | null
  benefit_zl_ha_low: number | null
  benefit_zl_ha_high: number | null
  cost_zl_ha_low: number | null
  cost_zl_ha_high: number | null
  break_even_area_ha: number | null
  break_even_never: boolean
  assumptions: EconomicsAssumptions
  assumptions_pl: string[]
  source: string
}

export interface ProfilePoint {
  distance_m: number
  elevation_m: number
  hollow: boolean
}

export interface SlopeProfile {
  points: ProfilePoint[]
  length_m: number
  drop_m: number
  mean_slope_pct: number
  direction_pl: string | null
  along_long_axis: boolean
  resolution_m: number
  text_pl: string
  source: string
}

export interface StrategyYear {
  year_ahead: number
  stress_days_median: number | null
  stress_days_p80: number | null
  irrigation_mm_median: number | null
  irrigation_mm_p80: number | null
  irrigation_m3_parcel_p80: number | null
  taw_mm: number
  evaporation_saved_mm_median: number | null
  evaporation_saved_m3_parcel_median: number | null
}

export type StrategyId = 'none' | 'rescue' | 'full' | 'retention' | 'retention_rescue'

export interface Strategy {
  id: StrategyId
  label_pl: string
  description_pl: string
  years: StrategyYear[]
}

export interface Simulation {
  strategies: Strategy[]
  members: number
  et0_change_pct_per_decade: number | null
  tmean_change_c_per_decade: number | null
  taw_now_mm: number
  taw_gain_5y_mm: number
  spring_storage_none_mm: number | null
  spring_storage_full_mm: number | null
  text_pl: string[]
  assumptions_pl: string[]
  source: string
}

export type TileStatus = 'good' | 'warn' | 'bad' | 'unknown'

export interface Gauge {
  value: number
  max: number
  threshold: number | null
  unit: string
}

export interface SummaryTile {
  id: 'water_now' | 'flood' | 'climate' | 'action' | 'dry_year'
  label_pl: string
  value_pl: string
  detail_pl: string
  status: TileStatus
  gauge: Gauge | null
  link_section: SectionId | null
}

export interface SatellitePoint {
  year: number
  day: string
  ndvi: number
  ndmi: number | null
  current: boolean
}

export interface SatelliteSeries {
  points: SatellitePoint[]
  history_median: number | null
  history_min: number | null
  history_max: number | null
  applicable: boolean
  text_pl: string
  source: string
}

export interface FloodZone {
  id: string
  label_pl: string
  hit: boolean | null
}

/** Flood-zone image in EPSG:2180 with its corners in lon/lat (top-left, top-right, bottom-right, bottom-left). */
export interface FloodOverlay {
  url: string
  corners: [number, number][]
}

export interface FloodInfo {
  status: SourceStatus
  level: 'high' | 'medium' | 'low' | 'none' | 'unknown'
  label_pl: string
  sentence_pl: string
  zones: FloodZone[]
  wms_url: string | null
  wms_layers: string[]
  /** Missing in reports saved before the overlay existed. */
  overlay?: FloodOverlay | null
  source: string
}

export interface GroundwaterInfo {
  status: SourceStatus
  station_pl: string | null
  distance_km: number | null
  trend: 'falling' | 'stable' | 'rising' | null
  change_m: number | null
  period: Period | null
  sentence_pl: string
  source: string
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
  | 'depression_minor'
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

export interface FarmParcel {
  id: string
  number: string | null
  precinct: string | null
  commune: string | null
  area_ha: number
  distance_m: number | null // shortest distance to the main parcel, 0 = touching
  geometry: GeoJsonGeometry
}

// Farm mode (G11): only the m³ volumes and the irrigation economics are sums over all parcels.
export interface Farm {
  count: number // all parcels, the main one included
  total_area_ha: number
  parcels: FarmParcel[] // extra parcels only
  text_pl: string[]
  source: string
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
  farm?: Farm | null
  crop: Crop
  analysis_date: string
  complete: boolean
  headline: Headline
  sections: ReportSection[]
  recommendations: ReportRecommendation[]
  irrigation: ReportIrrigation
  months: MonthRisk[]
  chart: SeasonChart | null
  summary_tiles: SummaryTile[]
  stress_heatmap: StressHeatmap | null
  trends: ClimateTrends | null
  water_plan: WaterPlan | null
  retention_plan?: RetentionPlan | null // absent in reports saved before G9
  irrigation_economics?: IrrigationEconomics | null // absent in reports saved before G10
  profile: SlopeProfile | null
  simulation: Simulation | null
  satellite: SatelliteSeries | null
  flood: FloodInfo | null
  groundwater: GroundwaterInfo | null
  map: ReportMap
  sources: SourceEntry[]
  limitations_pl: string[]
  missing_data_pl: string[]
}

/** Address search result (GUGiK UUG): a point to fly the map to; an address with a number also picks a parcel. */
export interface Place {
  kind: 'address' | 'street' | 'city'
  label_pl: string
  detail_pl: string
  lat: number
  lon: number
}

export interface ApiError {
  detail: string
}
