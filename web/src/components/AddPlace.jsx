import { useMemo, useState } from 'react'
import { api, CATEGORY_LABELS } from '../lib/api'
import { toast } from '../lib/ui'

/**
 * 手動輸入景點
 * ============
 * 用戶要求（原文）：
 *   「人哋入 information like address name etc」
 *
 * ⚠️ 呢個係**一等公民**，唔係 fallback。
 *    原因（老實講）：
 *      · IG 封鎖 server 抓取（法律 + 技術都係死路）
 *      · 用戶自己知得最清楚：佢去過、佢想去、佢有地址
 *      · 手動入一次 = 100% 準，唔會有「抽錯店名」問題
 *      · 而且手動入嘅嘢，App 可以幫你**自動補座標**
 *        （本地城市庫 134,655 個名，0.03ms）
 *
 * 所以流程係：你入名 + 地址 → App 幫你查座標、分類、分區。
 */

const CATS = Object.entries(CATEGORY_LABELS || {}).map(([k, v]) => ({ k, v }))
const FALLBACK_CATS = [
  { k: 'food', v: '🍜 食' }, { k: 'shopping', v: '🛍 購物' },
  { k: 'play', v: '🎡 玩' }, { k: 'stay', v: '🏨 住' },
  { k: 'transport', v: '🚕 交通' }, { k: 'other', v: '✦ 其他' },
]

export default function AddPlace({ trip, onAdded, onClose }) {
  const cats = CATS.length ? CATS : FALLBACK_CATS
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [district, setDistrict] = useState('')
  const [category, setCategory] = useState('food')
  const [duration, setDuration] = useState('')
  const [note, setNote] = useState('')
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)
  const [geo, setGeo] = useState(null)          // { lat, lng, country, canonical }
  const [geoBusy, setGeoBusy] = useState(false)
  const [sug, setSug] = useState([])

  const hasInput = name.trim() || address.trim()

  /** 查座標 —— 用本地城市庫（0.03ms，唔使上網）。 */
  async function lookup(q) {
    const query = (q || district || address || '').trim()
    if (!query) return
    setGeoBusy(true); setSug([])
    try {
      // 先試成個地址，唔得就試入面嘅地區名
      for (const cand of [query, district, name].filter(Boolean)) {
        try {
          const r = await api.geocode(cand)
          if (r?.lat) {
            setGeo(r)
            // 地址抽到地區名就自動填
            if (!district && r.district) setDistrict(r.district)
            toast(`座標：${r.district || r.canonical || cand}`)
            break
          }
        } catch {}
      }
    } catch (e) { toast(e.message) }
    finally { setGeoBusy(false) }
  }

  /** 打字時自動建議地區。 */
  async function onDistrictType(v) {
    setDistrict(v)
    if (v.trim().length < 2) { setSug([]); return }
    try {
      const r = await api.searchCities(v.trim(), 5)
      setSug(r.results || [])
    } catch { setSug([]) }
  }

  async function save() {
    if (!name.trim()) return toast('最起碼要填名稱')
    setBusy(true)
    try {
      const item = {
        name: name.trim(),
        address: address.trim() || null,
        district: district.trim() || null,
        category,
        duration: duration ? Number(duration) : null,
        note: note.trim() || null,
        url: link.trim() || null,
        source: 'manual',
        source_name: '手動輸入',
        confidence: 100,
        location_path: district.trim() ? [district.trim()] : [],
      }
      // 有座標就一齊存
      if (geo?.lat) {
        item.lat = geo.lat; item.lng = geo.lng; item.country = geo.country
        if (!item.district && geo.district) {
          item.district = geo.district
          item.location_path = [geo.district]
        }
      }

      // 冇座標但有名／地址 → 後端補
      const saved = await api.addItem(trip.id, item)
      const sid = saved?.id || saved?.item?.id

      // 冇座標就試下補
      if (!item.lat && sid) {
        try {
          const r = await api.geocode(district || address || name)
          if (r?.lat) {
            await api.patchItem(sid, { lat: r.lat, lng: r.lng })
            toast(`已加入並補到座標 ✓`)
          } else toast('已加入（未有座標）')
        } catch { toast('已加入（未有座標）') }
      } else {
        toast('已加入 ✓')
      }

      setName(''); setAddress(''); setDistrict(''); setDuration(''); setNote(''); setLink('')
      setGeo(null)
      await onAdded?.()
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="card glow" style={{ padding: 14 }}>
      <div className="row" style={{ marginBottom: 4 }}>
        <div>
          <div style={{ fontWeight: 900, fontSize: 14 }}>✍️ 手動加景點</div>
          <div className="sub" style={{ fontSize: 10.5, marginTop: 3 }}>
            入名 + 地址就得，App 自動幫你查座標、分類、分區
          </div>
        </div>
        {onClose && <button className="btn sm ghost" onClick={onClose}>✕</button>}
      </div>

      <div className="sec">名稱 *</div>
      <input className="input" value={name} placeholder="例：一蘭本社総本店"
        onChange={e => setName(e.target.value)} />

      <div className="sec">地址（可選，但填咗就自動定位）</div>
      <textarea className="input" rows={2} value={address}
        placeholder="例：福岡県福岡市博多区中洲5-3-2"
        onChange={e => setAddress(e.target.value)}
        style={{ resize: 'vertical', lineHeight: 1.7 }} />

      <div className="sec">地區（可選 —— 打兩個字就有建議）</div>
      <input className="input" value={district} placeholder="例：博多 / 明洞 / 銅鑼灣"
        onChange={e => onDistrictType(e.target.value)} />
      {sug.length > 0 && (
        <div className="card" style={{ marginTop: 7, padding: 5 }}>
          {sug.map((r, i) => (
            <button key={i} onClick={() => { setDistrict(r.query); setSug([]) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '7px 9px', borderRadius: 'var(--r-xs)', fontSize: 12.5,
                borderBottom: i < sug.length - 1 ? '1px dashed var(--border)' : 'none',
              }}>
              <b>{r.query}</b>
              <span className="sub" style={{ fontSize: 10.5, marginLeft: 7 }}>{r.country}</span>
            </button>
          ))}
        </div>
      )}

      <div className="row" style={{ gap: 8, marginTop: 11 }}>
        <button className="btn sm" onClick={() => lookup()} disabled={geoBusy}>
          {geoBusy ? '查緊…' : '📍 查座標'}
        </button>
        {geo?.lat && (
          <span className="sub" style={{ fontSize: 10.5, flex: 1, lineHeight: 1.6 }}>
            ✓ {geo.lat.toFixed(4)}, {geo.lng.toFixed(4)}
            {geo.canonical && ` · ${geo.canonical}`}
            {geo.country && ` · ${geo.country}`}
          </span>
        )}
      </div>

      <div className="sec">分類</div>
      <div className="chips">
        {cats.map(c => (
          <button key={c.k} className={`chip ${category === c.k ? 'on' : ''}`}
            onClick={() => setCategory(c.k)}>{c.v}</button>
        ))}
      </div>

      <div className="sec">停留時間（分鐘，可選）</div>
      <div className="chips">
        {[30, 60, 90, 120, 180, 240].map(m => (
          <button key={m} className={`chip ${String(duration) === String(m) ? 'on' : ''}`}
            onClick={() => setDuration(String(duration) === String(m) ? '' : String(m))}>
            {m < 60 ? `${m}分` : `${m / 60} 小時`}
          </button>
        ))}
      </div>
      <input className="input" type="number" min="0" step="15" value={duration}
        placeholder="或者自己填分鐘" onChange={e => setDuration(e.target.value)}
        style={{ marginTop: 8 }} />

      <div className="sec">連結（可選）</div>
      <input className="input" value={link} placeholder="IG / Google Maps / 官網"
        onChange={e => setLink(e.target.value)} />

      <div className="sec">備註（可選）</div>
      <input className="input" value={note} placeholder="例：要訂位 / 逢星期一休"
        onChange={e => setNote(e.target.value)} />

      <button className="btn primary wide" style={{ marginTop: 16 }}
        onClick={save} disabled={busy || !hasInput}>
        {busy ? '加入緊…' : '＋ 加入收藏'}
      </button>
    </div>
  )
}
