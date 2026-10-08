/**
 * 多城市行程：日子 ↔ 城市對應 + 衝突偵測
 * =========================================
 *
 * 概念：
 *   一個 trip 可以去多個城市，例如
 *       福岡 4 日 → 首爾 3 日
 *   就會有 7 日：
 *       Day 1-4  福岡
 *       Day 5-7  首爾
 *
 * ⚠️⚠️ 最重要嘅規則（用戶明確指出）：
 *   **「中間重疊嘅一日」係可以接受嘅，唔應該當衝突。**
 *
 *   例：福岡 4 日 + 首爾 3 日
 *       Day 4 = 福岡最後一日
 *       Day 5 = 首爾第一日
 *       但如果係「福岡 4 日、首爾 3 日」而用戶安排 Day 4 晚上飛去首爾，
 *       咁 Day 4／Day 5 之間就係**過渡**，兩邊嘅行程都合理。
 *
 *   所以判定規則係：
 *       · 一日只屬於一個城市 → 該城市嘅行程 OK，其他城市嘅行程 = 衝突
 *       · 一日橫跨兩個城市（過渡日）→ **兩邊都接受，唔報衝突**
 */

/**
 * 由 stops 砌出逐日嘅城市歸屬。
 *
 * 回傳 [{ day, cities: [...], transition: bool }]
 *   · cities 只有一個元素 → 正常日
 *   · cities 有兩個元素   → 過渡日（可以接受兩邊行程）
 */
export function buildDayCities(stops, totalDays) {
  const list = (stops || []).filter(s => s && s.city && Number(s.days) > 0)
  const total = totalDays || list.reduce((n, s) => n + Number(s.days), 0) || 1

  // 逐日展開：每個 stop 佔 days 日
  const raw = []          // [{day, city}]
  let day = 1
  for (const s of list) {
    const d = Number(s.days) || 1
    for (let i = 0; i < d && day <= total; i++, day++) {
      raw.push({ day, city: s.city.trim() })
    }
  }
  // 如果 stops 總日數少過 total，補最後一個城市
  while (day <= total) {
    raw.push({ day, city: list.length ? list[list.length - 1].city.trim() : null })
    day++
  }

  // 收集每日嘅城市（去重）
  const map = new Map()
  for (const r of raw) {
    if (!map.has(r.day)) map.set(r.day, new Set())
    if (r.city) map.get(r.day).add(r.city)
  }

  // ⚠️ 標記過渡日：連續兩日嘅城市有變 → 交界嘅一日／兩日都算過渡
  const out = []
  for (let d = 1; d <= total; d++) {
    const cities = [...(map.get(d) || [])]
    const prev = [...(map.get(d - 1) || [])]
    const next = [...(map.get(d + 1) || [])]
    // 同前一日或後一日有唔同城市 = 處於交界
    const transition =
      (prev.length && cities.length && prev.some(c => !cities.includes(c))) ||
      (next.length && cities.length && next.some(c => !cities.includes(c))) ||
      cities.length > 1
    out.push({ day: d, cities, transition })
  }
  return out
}

/** 由 item 嘅地區資料猜佢屬於邊個城市。 */
export function itemCity(item) {
  const parts = [
    item?.city, item?.district, item?.prefecture, item?.country,
    ...(item?.location_path || []),
    item?.address,
  ].filter(Boolean).map(s => String(s))
  return parts
}

/**
 * 兩個城市名有冇關係（寬鬆比對 —— 唔可以太嚴，否則誤報）。
 *   「福岡」vs「福岡市」          → true
 *   「首爾」vs「ソウル」          → false（要靠 alias）
 *   「福岡県」vs「福岡」          → true
 */
export function cityMatches(a, b) {
  if (!a || !b) return false
  const norm = (s) => String(s)
    .replace(/[縣県]/g, '県').replace(/[區区]/g, '区')
    .replace(/[臺台]/g, '台').replace(/市$|県$|区$|道$|府$|郡$|町$|村$/g, '')
    .trim().toLowerCase()
  const x = norm(a), y = norm(b)
  if (!x || !y) return false
  return x === y || x.includes(y) || y.includes(x)
}

/**
 * 檢查一個已排入行程嘅 item 喺某一日有冇城市衝突。
 *
 * 回傳 { conflict: bool, reason: string|null, dayCities: [...], transition }
 */
export function checkItemConflict(item, dayInfo, stops) {
  if (!dayInfo) return { conflict: false, reason: null, dayCities: [], transition: false }

  // ⚠️ 過渡日：兩邊城市都可以，唔算衝突（用戶明確要求）
  if (dayInfo.transition) {
    return { conflict: false, reason: null, dayCities: dayInfo.cities, transition: true }
  }
  if (!dayInfo.cities.length) {
    return { conflict: false, reason: null, dayCities: [], transition: false }
  }

  const cities = dayInfo.cities
  const itemParts = itemCity(item)

  // item 有冇任何一個地區欄位對得上當日城市？
  const hit = itemParts.some(p => cities.some(c => cityMatches(p, c)))
  if (hit) {
    return { conflict: false, reason: null, dayCities: cities, transition: false }
  }

  // item 完全冇地區資料 → 唔可以斷定衝突
  if (!itemParts.length) {
    return { conflict: false, reason: null, dayCities: cities, transition: false }
  }

  return {
    conflict: true,
    reason: `呢日喺「${cities.join(' / ')}」，但呢個景點喺「${item.district || item.city || item.country}」`,
    dayCities: cities,
    transition: false,
  }
}

/** 一次過檢查每日嘅所有衝突。 */
export function findConflicts(items, stops, totalDays) {
  const dayMap = new Map(buildDayCities(stops, totalDays).map(d => [d.day, d]))
  const out = []
  for (const it of items) {
    if (it.day_index == null) continue
    const info = dayMap.get(Number(it.day_index))
    const r = checkItemConflict(it, info, stops)
    if (r.conflict) out.push({ item: it, ...r, day: Number(it.day_index) })
  }
  return out
}

/** 城市清單字串（顯示用）。 */
export function stopsSummary(stops) {
  const list = (stops || []).filter(s => s?.city)
  if (!list.length) return null
  return list.map(s => `${s.city} ${s.days}日`).join(' → ')
}

export const STOP_COLORS = [
  '#a855f7', '#22d3ee', '#f472b6', '#fbbf24',
  '#34d399', '#fb923c', '#818cf8', '#f87171',
]
