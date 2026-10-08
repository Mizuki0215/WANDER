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

/** 由 nowIn() 攞 HH:MM。 */
function hhmm(d) {
  return d ? `${pad(d.hours)}:${pad(d.minutes)}` : '--:--'
}

const WEEKDAY = ['日', '一', '二', '三', '四', '五', '六']

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
  const here = nowIn(myTz) || {
    hours: now.getHours(), minutes: now.getMinutes(),
    weekday: now.getDay(), iso: now.toISOString().slice(0, 10),
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
    try {
      const { api } = await import('../lib/api')
      const d = await api.tz(q)
      if (d?.tz) {
        const v = { city: d.matched || q, timezone: d.tz,
                    country: d.country, confident: d.confident }
        setPicked(v); save(v)
      } else {
        setPicked(null); save(null)
        ;(await import('../lib/ui')).toast(`「${q}」冇時區資料`)
      }
    } catch (e) {
      setPicked(null); save(null)
      ;(await import('../lib/ui')).toast(`搵唔到時區：${e.message}`)
    }
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
        {WEEKDAY[here.weekday] != null ? `星期${WEEKDAY[here.weekday]}` : ''}
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
