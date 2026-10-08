import { useEffect, useMemo, useState } from 'react'
import { nowIn, offsetMinutes, sameZone, localTz, tzLabel } from '../lib/tz'
import CityPicker from './CityPicker'

/**
 * 世界時鐘（主畫面）
 * ====================
 *
 * ⚠️⚠️ 用戶要求（我原本做錯方向，佢糾正咗）：
 *   「Show 兩個時區囉，第一個最上面嗰個係**手機時間**，
 *    第二個就係有得比你揀 —— 你可以輸入嗰個城市嘅名，
 *    用英文或者中文都可以，之後呢例如你揀咗，
 *    然後就會有對應嘅時區。」
 *
 * ⚠️ 所以係：
 *    ┌─────────────────────┐
 *    │   14:30  ← 大字      │  你手機嘅時間（你身處嗰度）
 *    │   星期一 · 10/8      │
 *    ├─────────────────────┤
 *    │   15:30  ← 細啲      │  你揀嘅城市
 *    │   🇯🇵 福岡      [改]  │
 *    └─────────────────────┘
 *
 * ⚠️ 之前係**反過嚟**（目的地做大字）—— 用戶話唔啱。
 *
 * ⚠️ 為咩要保留第二個鐘（就算你身處嗰度）：
 *    · 打電話返屋企要知香港幾點
 *    · 同朋友約時間要對時
 *   ⚠️ 但如果兩個時區**一樣**，就唔顯示第二個（唔好重複）。
 *
 * ⚠️ 揀咗嘅城市記喺 localStorage —— 唔使每次再揀。
 */

/**
 * 本地城市→時區資料檔（用戶要求）。
 *
 * ⚠️⚠️ 為咩要：
 *   「整一個 File for 放低城市時間呢一啲嘅 data，
 *    佢感應到原來係另一個時區就將你而家嘅時間做加減。」
 *
 * ⚠️ 格式：`{"v":1,"tz":["Asia/Tokyo",...],"cities":{"福岡":[12,"日本"],...}}`
 *    · `tz` 係時區名嘅表（唔好每個城市重複寫 20 次）
 *    · `cities` 嘅值係 `[tz 索引, 中文國名]`
 *
 * ⚠️ 載入一次就 cache 喺 module 變數（唔使每次查）。
 */
let _cityTz = null
let _cityTzLoading = null

function loadCityTz() {
  if (_cityTz) return Promise.resolve(_cityTz)
  if (_cityTzLoading) return _cityTzLoading
  _cityTzLoading = fetch('/city-tz.json')
    .then(r => (r.ok ? r.json() : null))
    .then(d => { _cityTz = d; return d })
    .catch(() => null)
  return _cityTzLoading
}

/** ⚠️ 查本地檔（搵唔到回 null，唔會拋錯）。 */
async function localTzOf(name) {
  const d = await loadCityTz()
  if (!d?.cities) return null
  const key = String(name || '').trim().toLowerCase()
  if (!key) return null
  const hit = d.cities[key]
  if (!hit) return null
  return d.tz?.[hit[0]] || null
}

const KEY = 'wander.worldclock'      // { city, timezone }

function readSaved() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function save(v) {
  try { v ? localStorage.setItem(KEY, JSON.stringify(v)) : localStorage.removeItem(KEY) }
  catch { /* private mode */ }
}

/** 兩個位。 */
function pad(n) { return String(n).padStart(2, '0') }

/**
 * 由 `nowIn()` 攞 HH:MM。
 *
 * ⚠️⚠️ 用戶報：「你仲冇拎到個時間」
 *
 * ⚠️ 根因：`nowIn()` 回嘅係 **`hh` / `mm`**（兩個位字串），
 *    但我寫咗 `d.hours` / `d.minutes` —— **兩個都唔存在** →
 *    `pad(undefined)` → 顯示 `undefined:undefined`。
 *
 *    而且 fallback（`nowIn` 回 null 嗰陣）我用咗 `hours`/`minutes`
 *    —— 同 `nowIn` 嘅 shape **唔一致**，即係兩邊都錯。
 */
function hhmm(d) {
  if (!d) return '--:--'
  // ⚠️ 兩個 shape 都食：`nowIn()` 嘅 {hh,mm} 同 fallback 嘅 {hours,minutes}
  const h = d.hh != null ? d.hh : d.hours
  const m = d.mm != null ? d.mm : d.minutes
  if (h == null || m == null) return '--:--'
  return `${pad(h)}:${pad(m)}`
}

/**
 * 星期（中文）。
 *
 * ⚠️⚠️ 同一個 bug：`nowIn()` 回嘅 `weekday` 係 **英文短名**
 *    （`'Mon'`、`'Tue'`…，因為 Intl 用咗 `weekday: 'short'`）。
 *    我寫咗 `WEEKDAY[here.weekday]` —— `WEEKDAY['Mon']` 係 `undefined`。
 *
 * ✅ 修法：用一個英文 → 中文嘅對照表（唔靠 index）。
 */
const WD_EN = { Sun: '日', Mon: '一', Tue: '二', Wed: '三', Thu: '四', Fri: '五', Sat: '六' }
const WD_ZH = ['日', '一', '二', '三', '四', '五', '六']

function weekdayZh(d) {
  if (!d) return ''
  if (typeof d.weekday === 'string') return WD_EN[d.weekday] || ''
  if (typeof d.weekday === 'number') return WD_ZH[d.weekday] || ''
  return ''
}

export default function WorldClocks({ tripCity, tripTz }) {
  const [now, setNow] = useState(() => new Date())
  const [picked, setPicked] = useState(() => readSaved())
  const [editing, setEditing] = useState(false)

  // ⚠️ 每秒 tick —— 但 `now` 只係用嚟觸發 re-render，
  //    真正嘅時間由 `nowIn(tz)` 計（唔會受手機時區影響）。
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const myTz = localTz()

  /**
   * ⚠️ 第二個鐘嘅時區（優先次序）：
   *   ① 用戶**自己揀**咗嘅（localStorage）—— 最高優先
   *   ② 旅程嘅第一個城市（有旅程嗰陣自動填）
   *   ③ 冇 → 唔顯示第二個鐘
   */
  const target = useMemo(() => {
    if (picked?.timezone) return picked
    if (tripTz) return { city: tripCity || '', timezone: tripTz, fromTrip: true }
    return null
  }, [picked, tripTz, tripCity])

  const same = !target?.timezone || sameZone(myTz, target.timezone)
  const there = target?.timezone ? nowIn(target.timezone) : null
  // ⚠️ fallback 嘅 shape 一定要同 `nowIn()` **一致**（hh/mm/weekday）
  //    —— 之前用咗 hours/minutes，兩邊都攞唔到。
  const here = nowIn(myTz) || {
    hh: pad(now.getHours()), mm: pad(now.getMinutes()),
    weekday: WD_ZH[now.getDay()],
    iso: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    tz: myTz,
  }

  const myOff = offsetMinutes(myTz)
  const theirOff = offsetMinutes(target?.timezone)
  const diffMin = (myOff != null && theirOff != null) ? theirOff - myOff : null

  function pick(r) {
    // ⚠️ CityPicker 回 { query, matched, country, lat, lng, timezone? }
    //    ⚠️ 但 CityPicker 唔一定回 timezone —— 要由 API 攞。
    const city = (r.matched || r.query || '').trim()
    setEditing(false)
    if (!city) return
    // ⚠️ 先用 localTzSafe 估（同一個 offset 當自己）——
    //    真正嘅時區由 `api.tz` 攞（非同步）。
    fetchTz(city, r)
  }

  /**
   * ⚠️ 攞城市嘅時區（`GET /api/tz`）。
   *
   *   ⚠️ 為咩唔用 `/api/lookup`：嗰個係「店名反查完整資料」，
   *      貴好多（會打 Photon / Nominatim）。世界時鐘只需要時區，
   *      `/api/tz` 用本機 134k 城市庫，**唔使網絡、快好多**。
   *
   *   ⚠️ 用戶唔應該等 —— 先顯示城市名（時區空 = `--:--`），
   *      攞到先補上。
   */
  async function fetchTz(city, r) {
    const q = (r?.matched || city || '').trim()
    setPicked({ city: q, timezone: '', pending: true })

    // ⚠️⚠️ ① 先用**本地資料檔**（`/city-tz.json`）——
    //    用戶要求：「整一個 File for 放低城市時間呢一啲嘅 data，
    //              佢感應到原來係另一個時區就將你而家嘅時間做加減」
    //
    //    ⚠️ 為咩本地檔優先：
    //       · **唔使網絡** —— 飛機上／地鐵／外國漫遊都用得
    //       · **即時** —— 唔使等 server round-trip
    //       · 947 KB（gzip ~270 KB），載入一次就 cache 喺瀏覽器
    let tzName = await localTzOf(q)
    let matched = q, country = ''

    // ⚠️ ② 本地檔搵唔到 → 才問後端（134k 城市，但慢啲）
    if (!tzName) {
      try {
        const { api } = await import('../lib/api')
        const d = await api.tz(q)
        tzName = d?.tz
        matched = d?.matched || q
        country = d?.country || ''
      } catch (e) {
        setPicked(null); save(null)
        ;(await import('../lib/ui')).toast(`搵唔到「${q}」嘅時區`)
        return
      }
    }

    if (!tzName) {
      setPicked(null); save(null)
      ;(await import('../lib/ui')).toast(`「${q}」冇時區資料`)
      return
    }
    // ⚠️⚠️ 由**現在嘅時間**加減（`nowIn()` 用 Intl 自己計）——
    //    唔使記住 offset，夏令時間都會自動跟。
    const v = { city: matched, timezone: tzName, country }
    setPicked(v); save(v)
  }

  function clear() {
    setPicked(null); save(null); setEditing(false)
  }

  return (
    <div style={{ textAlign: 'center' }}>
      {/* ══ ① 大字：我嘅時間（手機）══ */}
      <div className="mono" style={{
        fontSize: 46, fontWeight: 900, lineHeight: 1, letterSpacing: -1,
        color: 'var(--text)',
      }}>
        {hhmm(here)}
      </div>
      <div className="sub" style={{ fontSize: 11, marginTop: 5 }}>
        {weekdayZh(here) ? `星期${weekdayZh(here)}` : ''}
        {myTz ? ` · ${tzLabel(myTz)}` : ''}
        {' · 你嘅時間'}
      </div>

      {/* ══ ② 細字：我揀嘅城市 ══ */}
      {target && !editing && (
        <button onClick={() => setEditing(true)} className="tap" style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          marginTop: 14, padding: '7px 12px',
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 'var(--r-full)',
        }}>
          {same ? (
            <span className="sub" style={{ fontSize: 11.5 }}>
              ⚠️ 同你同一個時區
            </span>
          ) : (
            <>
              <span className="mono" style={{
                fontSize: 17, fontWeight: 900,
                background: 'linear-gradient(100deg, var(--edge-purple-hi), var(--edge-cyan))',
                WebkitBackgroundClip: 'text', backgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}>
                {target.pending ? '--:--' : hhmm(there)}
              </span>
              <span style={{ fontSize: 12, fontWeight: 700 }}>
                {target.city || tzLabel(target.timezone)}
              </span>
              {diffMin != null && (
                <span className="sub" style={{ fontSize: 10 }}>
                  {diffMin > 0 ? `快 ${diffMin / 60} 個鐘` : `慢 ${-diffMin / 60} 個鐘`}
                </span>
              )}
            </>
          )}
          <span className="sub" style={{ fontSize: 10, opacity: .6 }}>✎</span>
        </button>
      )}

      {/* ⚠️ 冇揀城市 → 一個「加世界時鐘」掣（唔好逼用戶睇空位） */}
      {!target && !editing && (
        <button onClick={() => setEditing(true)} className="btn sm ghost" style={{
          marginTop: 12, fontSize: 11.5,
        }}>
          🌍 加世界時鐘
        </button>
      )}

      {/* ══ 揀城市（用 134k 本地城市庫）══ */}
      {editing && (
        <div style={{ marginTop: 12, textAlign: 'left' }}>
          <CityPicker value="" autoFocus
            placeholder="城市名（中文／英文都可以）"
            onChange={() => {}}
            onPick={pick} />
          <div className="row" style={{ gap: 7, marginTop: 8, justifyContent: 'center' }}>
            <button className="btn sm ghost" onClick={() => setEditing(false)}>取消</button>
            {picked && (
              <button className="btn sm ghost" onClick={clear}>移除</button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
