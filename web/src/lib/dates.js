/**
 * 日期工具
 *
 * ⚠️ 設計原則：trip 嘅日子長度以「start_date → end_date」為準，
 *   `days` 只係 fallback（用戶未填日期時用）。
 *   每次改日期就自動重算 days，唔會出現「4 日行程但月曆得 3 格」呢種不一致。
 */

export const WEEKDAY_ZH = ['日', '一', '二', '三', '四', '五', '六']
export const MONTH_ZH = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

/** 將 'YYYY-MM-DD' 轉做 local Date（避免 UTC 時區偏移一日）。 */
export function parseDate(s) {
  if (!s) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s))
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return isNaN(d) ? null : d
}

export function toISO(d) {
  if (!d) return null
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function addDays(d, n) {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

/** 兩個日期相差幾日（含頭含尾：8/12 → 8/14 係 3 日）。 */
export function daysBetween(a, b) {
  const s = parseDate(a), e = parseDate(b)
  if (!s || !e) return null
  const n = Math.round((e - s) / 86400000) + 1
  return n > 0 ? n : null
}

/** 旅程總日數：日期優先，冇日期就用 days。 */
export function tripLength(trip) {
  const n = daysBetween(trip?.start_date, trip?.end_date)
  if (n) return n
  return Math.max(1, Number(trip?.days) || 3)
}

/**
 * 產生逐日資料：Day 1..N，每日有真實日期（如果有 start_date）。
 * 回傳 [{ day, date|null, weekday, label, short, iso }]
 */
export function tripDays(trip) {
  const len = tripLength(trip)
  const start = parseDate(trip?.start_date)
  const out = []
  for (let i = 0; i < len; i++) {
    const d = start ? addDays(start, i) : null
    out.push({
      day: i + 1,
      date: d,
      iso: d ? toISO(d) : null,
      weekday: d ? WEEKDAY_ZH[d.getDay()] : null,
      label: d ? `${d.getMonth() + 1}/${d.getDate()}` : `Day ${i + 1}`,
      full: d ? `${d.getMonth() + 1}月${d.getDate()}日（${WEEKDAY_ZH[d.getDay()]}）` : `第 ${i + 1} 日`,
    })
  }
  return out
}

/** 倒數：正數=仲有幾日，0=今日，負數=已過。 */
export function daysUntil(dateStr) {
  const d = parseDate(dateStr)
  if (!d) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((d - today) / 86400000)
}

export function countdownText(trip) {
  const n = daysUntil(trip?.start_date)
  if (n === null) return null
  if (n > 1) return `仲有 ${n} 日`
  if (n === 1) return '聽日出發！'
  if (n === 0) return '今日出發 🎉'
  const end = daysUntil(trip?.end_date)
  if (end !== null && end < 0) return '已完成'
  return '旅程進行中'
}

/** Trip 嘅完整日期範圍文字。 */
export function dateRangeText(trip) {
  const s = parseDate(trip?.start_date)
  const e = parseDate(trip?.end_date)
  if (!s && !e) return null
  const f = (d) => `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
  if (s && e) return `${f(s)} – ${f(e)}`
  return f(s || e)
}


// ══════════════════════════════════════════════════════════
// 行程時間計算
// ══════════════════════════════════════════════════════════

/** 'HH:MM' → 分鐘數（由 00:00 起）。 */
export function toMinutes(hhmm) {
  if (!hhmm) return null
  const m = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm).trim())
  if (!m) return null
  const h = Number(m[1]), min = Number(m[2])
  if (h > 23 || min > 59) return null
  return h * 60 + min
}

/** 分鐘數 → 'HH:MM'。 */
export function fromMinutes(total) {
  if (total == null) return null
  const t = ((total % 1440) + 1440) % 1440
  const h = Math.floor(t / 60), m = t % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/**
 * 由停靠點嘅 start_time + duration 推算每日時間表。
 *
 * 有 start_time 嘅會顯示真實時間；冇嘅會由上一個停靠點接落去
 * （用 defaultDuration 補）。第一次遇到冇時間嘅，由 dayStart 開始。
 */
export function buildTimeline(stops, { dayStart = '09:00', defaultDuration = 60 } = {}) {
  let cursor = toMinutes(dayStart)
  return stops.map((it, i) => {
    const explicit = toMinutes(it.start_time)
    const start = explicit != null ? explicit : cursor
    const dur = Number(it.duration) > 0 ? Number(it.duration) : defaultDuration
    const end = start + dur
    cursor = end
    return {
      item: it,
      index: i,
      start: fromMinutes(start),
      end: fromMinutes(end),
      duration: dur,
      explicit: explicit != null,
      auto: explicit == null,
    }
  })
}

/** 兩個停靠點之間嘅空檔（分鐘）。 */
export function gapBetween(prevEnd, nextStart) {
  const a = toMinutes(prevEnd), b = toMinutes(nextStart)
  if (a == null || b == null) return null
  return b - a
}

export function durationText(minutes) {
  if (minutes == null || minutes <= 0) return ''
  const h = Math.floor(minutes / 60), m = minutes % 60
  if (h && m) return `${h} 小時 ${m} 分`
  if (h) return `${h} 小時`
  return `${m} 分鐘`
}
