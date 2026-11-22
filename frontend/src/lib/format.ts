// Formatting and input rules shared by the pages. Texts of the report come ready from the backend;
// here we only format dates and mirror the input validation of backend/app/core/models.py.

const HISTORY_YEARS = 10

// WWPPGG_R.OOOO.NR — mirror of PARCEL_ID_RE in backend/app/core/models.py.
const PARCEL_ID_RE = /^\d{6}_\d\.\d{4}(\.[0-9A-Za-z_]+)*\.[0-9A-Za-z]+(\/[0-9A-Za-z]+)*$/

export const PARCEL_ID_EXAMPLE = '141201_1.0001.6509'

export function parcelIdError(value: string): string | null {
  const v = value.trim()
  if (!v) return 'Wpisz numer działki albo wskaż działkę na mapie.'
  if (v.length > 64 || !PARCEL_ID_RE.test(v)) {
    return `To nie wygląda na pełny numer działki. Oczekiwany format: ${PARCEL_ID_EXAMPLE} (kod gminy, obręb, numer).`
  }
  return null
}

function isoLocal(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayIso(): string {
  return isoLocal(new Date())
}

export function minAnalysisDateIso(): string {
  // Same as dateutil's relativedelta(years=10) in the backend: 29 February falls back to 28 February.
  const now = new Date()
  const y = now.getFullYear() - HISTORY_YEARS
  const lastDay = new Date(y, now.getMonth() + 1, 0).getDate()
  return isoLocal(new Date(y, now.getMonth(), Math.min(now.getDate(), lastDay)))
}

export function analysisDateError(value: string): string | null {
  if (!value) return 'Wybierz datę analizy.'
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'Podaj datę w formacie RRRR-MM-DD.'
  const lo = minAnalysisDateIso()
  const hi = todayIso()
  if (value < lo || value > hi) return `Data musi być z ostatnich 10 lat: od ${formatDatePl(lo)} do ${formatDatePl(hi)}.`
  return null
}

function parseIsoDate(iso: string): Date {
  // Date-only strings are parsed as local dates (not UTC) so the day never shifts.
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function formatDatePl(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })
}

export function formatShortDatePl(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })
}

export function formatMonthPl(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('pl-PL', { month: 'short' })
}

export function formatDateTimePl(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', { dateStyle: 'long', timeStyle: 'short' })
}

export function formatNumberPl(value: number, maxFractionDigits = 0): string {
  return value.toLocaleString('pl-PL', { maximumFractionDigits: maxFractionDigits })
}

export function formatAreaHa(areaHa: number): string {
  return `${formatNumberPl(areaHa, areaHa < 10 ? 2 : 1)} ha`
}

/** '2019-07-15' → '15.07.2019' — the analysis date in headers ("na dzień …"), never "today". */
export function formatDateDmy(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}.${m}.${y}`
}

/** Polish noun form after a parcel count: 1 działka, 2 działki, 5 działek (G11). */
export function parcelsPl(n: number): string {
  if (n === 1) return 'działka'
  return n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14) ? 'działki' : 'działek'
}

/** Whom an m³ volume is for: "na działkę" or, in farm mode, "na 3 działki gospodarstwa" (G11). */
export function m3WherePl(farmCount: number | null | undefined, single = 'na działkę'): string {
  if (!farmCount || farmCount <= 1) return single
  const form = parcelsPl(farmCount) === 'działki' ? 'działki' : 'działek'
  return `na ${farmCount} ${form} gospodarstwa`
}
