/**
 * 時區工具（前端）
 * =================
 *
 * ⚠️⚠️ 用戶問嘅問題：
 *   「呢個時間係點樣抽取㗎？如果我正常去旅行我就會帶手機啦，
 *    咁係手機顯示咩時間你就顯示咩時間，定係點樣？
 *    因為你去旅行嘅話就會入唔同嘅時區呀嘛。」
 *
 * 答案：**兩個都要**，因為佢哋答緊唔同嘅問題。
 *
 *   ① 手機時間（`new Date()`）
 *      = 你**身處**邊度嘅時間。手機自己會跟網絡／GPS 調整，
 *        所以去到東京會自動變 UTC+9。
 *      → 答「我而家幾點？」
 *
 *   ② 目的地時間（`Intl.DateTimeFormat` + IANA 時區）
 *      ⚠️ 呢個**手機唔會話你知**：
 *        · 你喺香港計劃去東京 → 想知東京而家幾點（排行程）
 *        · 你喺東京想打返香港 → 想知香港而家幾點（唔好半夜打）
 *        · 行程寫「Day 3」→ 係**目的地**嘅 Day 3
 *      → 答「嗰度而家幾點？」
 *
 * ⚠️⚠️ 為咩一定要用 `Intl.DateTimeFormat` 而唔係自己計 offset：
 *   · 夏令時間（DST）每年唔同日子轉，而且各國規則唔一樣
 *     （歐盟同美國差幾個禮拜、澳洲南半球反轉）
 *   · 有啲時區唔係整點（印度 +5:30、尼泊爾 +5:45、南澳 +9:30）
 *   · 自己寫 offset 表一定會過期
 *   `Intl` 由瀏覽器處理，永遠最新。
 */

/** 拎某個 IANA 時區而家嘅 {hh, mm, date, weekday, offsetMin}。 */
export function nowIn(tz) {
  const d = new Date()
  if (!tz) return null
  try {
    const f = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      hour: '2-digit', minute: '2-digit', hour12: false,
      year: 'numeric', month: '2-digit', day: '2-digit',
      weekday: 'short',
    })
    const parts = Object.fromEntries(
      f.formatToParts(d).map(p => [p.type, p.value]))
    return {
      hh: parts.hour === '24' ? '00' : parts.hour,
      mm: parts.minute,
      iso: `${parts.year}-${parts.month}-${parts.day}`,
      weekday: parts.weekday,
      tz,
    }
  } catch {
    // ⚠️ 無效嘅 IANA 名（或者舊瀏覽器唔支援）→ 回 null，唔好拋錯
    return null
  }
}

/** 某個時區而家同 UTC 差幾分鐘（用嚟顯示 +9:00 呢類標籤）。 */
export function offsetMinutes(tz) {
  const d = new Date()
  if (!tz) return null
  try {
    const f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, timeZoneName: 'longOffset',
    })
    const name = f.formatToParts(d).find(p => p.type === 'timeZoneName')?.value
    // "GMT+09:00" / "GMT-05:00" / "GMT"
    const m = /GMT([+-])(\d{2}):(\d{2})/.exec(name || '')
    if (!m) return name === 'GMT' ? 0 : null
    const sign = m[1] === '-' ? -1 : 1
    return sign * (Number(m[2]) * 60 + Number(m[3]))
  } catch { return null }
}

/** 分鐘 → "UTC+9" / "UTC+5:30" / "UTC-3:30"。 */
export function fmtOffset(min) {
  if (min == null) return ''
  const sign = min < 0 ? '-' : '+'
  const a = Math.abs(min)
  const h = Math.floor(a / 60), m = a % 60
  return `UTC${sign}${h}${m ? ':' + String(m).padStart(2, '0') : ''}`
}

/** 兩個時區係唔係同一個（同 offset 就當同）。 */
export function sameZone(a, b) {
  if (!a || !b) return false
  if (a === b) return true
  const oa = offsetMinutes(a), ob = offsetMinutes(b)
  return oa != null && oa === ob
}

/** 瀏覽器／手機自己嘅 IANA 時區。 */
export function localTz() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || null }
  catch { return null }
}

/** 簡短地名：'Asia/Tokyo' → '東京'。 */
const CITY_ZH = {
  'Asia/Tokyo': '東京', 'Asia/Seoul': '首爾', 'Asia/Taipei': '台北',
  'Asia/Hong_Kong': '香港', 'Asia/Macau': '澳門', 'Asia/Shanghai': '中國',
  'Asia/Bangkok': '曼谷', 'Asia/Singapore': '新加坡', 'Asia/Kuala_Lumpur': '吉隆坡',
  'Asia/Ho_Chi_Minh': '胡志明市', 'Asia/Manila': '馬尼拉',
  'Asia/Jakarta': '雅加達', 'Asia/Bali': '峇里',
  'Asia/Dubai': '杜拜', 'Asia/Kolkata': '印度',
  'Europe/London': '倫敦', 'Europe/Paris': '巴黎', 'Europe/Berlin': '柏林',
  'Europe/Rome': '羅馬', 'Europe/Madrid': '馬德里', 'Europe/Amsterdam': '阿姆斯特丹',
  'Europe/Zurich': '蘇黎世', 'Europe/Vienna': '維也納', 'Europe/Lisbon': '里斯本',
  'Europe/Istanbul': '伊斯坦堡', 'Europe/Moscow': '莫斯科',
  'America/New_York': '紐約', 'America/Los_Angeles': '洛杉磯',
  'America/Chicago': '芝加哥', 'America/Denver': '丹佛',
  'America/Vancouver': '溫哥華', 'America/Toronto': '多倫多',
  'Australia/Sydney': '悉尼', 'Australia/Melbourne': '墨爾本',
  'Australia/Perth': '珀斯', 'Pacific/Auckland': '奧克蘭',
  'Africa/Cairo': '開羅', 'Africa/Johannesburg': '約翰內斯堡',
}
export function tzLabel(tz) {
  if (!tz) return ''
  if (CITY_ZH[tz]) return CITY_ZH[tz]
  // 'America/Argentina/Buenos_Aires' → 'Buenos Aires'
  const last = tz.split('/').pop() || tz
  return last.replace(/_/g, ' ')
}
