import { useEffect, useState } from 'react'
import { api, iconFor, confClass } from '../lib/api'
import { toast, Spinner } from '../lib/ui'
import { tripDays } from '../lib/dates'

/**
 * 收藏詳情 / 編輯彈層
 *
 * 可以做：
 *  · 補名稱（最常用 —— caption 冇店名時）
 *  · 補完資料（用名稱去搜尋引擎 + OSM 反查）
 *  · 改分類 / 改地區
 *  · 排入某一日
 *  · 刪除
 */
const CATS = [
  ['food', '🍜 美食'], ['shopping', '🛍 購物'], ['play', '🎡 玩樂'],
  ['stay', '🏨 住宿'], ['transport', '🚇 交通'], ['other', '📍 其他'],
]

export default function ItemDetail({ item, trip, onClose, onRefresh }) {
  const [name, setName] = useState(item.name || '')
  const [district, setDistrict] = useState(item.district || '')
  const [category, setCategory] = useState(item.category || 'other')
  const [startTime, setStartTime] = useState(item.start_time || '')
  const [duration, setDuration] = useState(item.duration || '')
  const [busy, setBusy] = useState(false)
  const [enriching, setEnriching] = useState(false)

  useEffect(() => {
    setName(item.name || ''); setDistrict(item.district || '')
    setCategory(item.category || 'other')
    setStartTime(item.start_time || ''); setDuration(item.duration || '')
  }, [item.id])

  const changed = name !== (item.name || '') || district !== (item.district || '')
    || category !== (item.category || 'other')

  async function save() {
    setBusy(true)
    try {
      const patch = {
        name: name.trim() || null, district: district.trim() || null, category,
        start_time: startTime || null,
        duration: duration ? Number(duration) : null,
      }
      // 有 name 但冇座標 → 順便用搜尋補完
      if (name.trim() && item.lat == null) {
        setEnriching(true)
        try {
          const r = await api.lookup(name.trim(), district.trim() || item.city || null)
          Object.assign(patch, r.item)
          patch.name = name.trim()
          toast('已用搜尋補完資料 ✓')
        } catch { toast('搜尋補完失敗，已儲存基本資料') }
        setEnriching(false)
      }
      await api.patchItem(item.id, {
        name: patch.name, district: patch.district, category: patch.category,
        parsed: { start_time: patch.start_time, duration: patch.duration },
      })
      // 分類要經 parsed 更新 → 用 addItem 唔啱，直接重新解析唔值得。
      // 簡單做法：patch item 支援 extended fields（後端會處理）
      await onRefresh()
      onClose()
    } catch (e) { toast(e.message) } finally { setBusy(false) }
  }

  async function moveTo(day) {
    try { await api.patchItem(item.id, { day_index: day }); toast(`已排入 Day ${day}`); await onRefresh(); onClose() }
    catch (e) { toast(e.message) }
  }
  async function unschedule() {
    try { await api.patchItem(item.id, { clear_day: true }); toast('已移出行程'); await onRefresh(); onClose() }
    catch (e) { toast(e.message) }
  }
  async function del() {
    if (!confirm(`刪除「${item.name || '呢個項目'}」？`)) return
    try { await api.deleteItem(item.id); toast('已刪除'); await onRefresh(); onClose() }
    catch (e) { toast(e.message) }
  }

  const days = tripDays(trip)

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,.62)',
      backdropFilter: 'blur(3px)', display: 'flex', alignItems: 'flex-end',
    }}>
      <div onClick={e => e.stopPropagation()} className="card" style={{
        width: '100%', maxWidth: 640, margin: '0 auto', maxHeight: '88vh', overflowY: 'auto',
        borderRadius: 'var(--r) var(--r) 0 0', paddingBottom: 'calc(20px + var(--safe-b))',
        borderColor: 'var(--border-hi)', boxShadow: '0 -10px 40px rgba(0,0,0,.5)',
      }}>
        <div className="row" style={{ alignItems: 'flex-start', marginBottom: 12 }}>
          <div style={{ display: 'flex', gap: 11, minWidth: 0 }}>
            <div className="ic" style={{ width: 42, height: 42, flex: '0 0 42px', fontSize: 20 }}>
              {item.raw_image ? <img src={item.raw_image} alt="" /> : iconFor(item)}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 900, fontSize: 15 }}>
                {item.name || '（未有名稱）'}
              </div>
              <div className="sub" style={{ fontSize: 11 }}>
                {(item.location_path || []).join(' › ') || '未分類'}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <span className={`conf ${confClass(item.confidence)}`}>{item.confidence}%</span>
            <button className="btn sm ghost" onClick={onClose}>✕</button>
          </div>
        </div>

        {item.needs_review && (
          <div className="card" style={{ borderColor: 'var(--warn)', marginBottom: 12, padding: 10 }}>
            <div className="sub" style={{ color: 'var(--warn)', fontSize: 11.5 }}>
              ⚠️ 呢個項目資料唔夠完整 —— 補個名稱就可以自動搜尋補齊座標同電話
            </div>
          </div>
        )}

        {/* ── 編輯 ── */}
        <div className="sec" style={{ marginTop: 4 }}>名稱</div>
        <input className="input" placeholder="例：一蘭 本社総本店" value={name}
          onChange={e => setName(e.target.value)} />

        <div className="sec">地區</div>
        <input className="input" placeholder="例：博多 / 明洞 / 銅鑼灣" value={district}
          onChange={e => setDistrict(e.target.value)} />

        <div className="sec">分類</div>
        <div className="chips">
          {CATS.map(([k, label]) => (
            <button key={k} className={`chip ${category === k ? 'on' : ''}`}
              onClick={() => setCategory(k)}>{label}</button>
          ))}
        </div>

        <button className="btn primary wide" style={{ marginTop: 16 }} onClick={save} disabled={busy}>
          {busy ? <Spinner /> : (item.lat == null && name.trim() ? '儲存 + 搜尋補完' : '儲存')}
        </button>
        {enriching && <div className="sub" style={{ textAlign: 'center', marginTop: 8 }}>搜尋緊…</div>}

        {/* ── 時間 ── */}
        <div className="sec">時間</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1 }}>
            <div className="sub" style={{ fontSize: 10.5, marginBottom: 4, fontWeight: 700 }}>開始</div>
            <input className="input" type="time" value={startTime}
              onChange={e => setStartTime(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="sub" style={{ fontSize: 10.5, marginBottom: 4, fontWeight: 700 }}>停留（分鐘）</div>
            <input className="input" type="number" min="5" max="600" step="5"
              placeholder="60" value={duration}
              onChange={e => setDuration(e.target.value)} />
          </div>
        </div>
        <div className="sub" style={{ fontSize: 10.5, marginTop: 5 }}>
          留空會自動由上一個景點接落去（預設 60 分鐘）
        </div>

        {/* ── 排入行程 ── */}
        <div className="sec">排入行程</div>
        <div className="chips">
          {days.map(d => (
            <button key={d.day}
              className={`chip ${Number(item.day_index) === d.day ? 'on' : ''}`}
              onClick={() => moveTo(d.day)}>
              {d.date ? `${d.label}（Day ${d.day}）` : `Day ${d.day}`}
            </button>
          ))}
          {item.day_index != null && (
            <button className="chip" onClick={unschedule}>移出</button>
          )}
        </div>

        {/* ── 詳細資料 ── */}
        <div className="sec">資料</div>
        <div className="card" style={{ background: 'var(--surface-2)' }}>
          <div className="sub" style={{ lineHeight: 2, fontSize: 12 }}>
            {item.address && <div>🏠 {item.address}{item.postal_code ? ` 〒${item.postal_code}` : ''}</div>}
            {item.lat != null && <div className="mono" style={{ fontSize: 10.5 }}>🗺 {item.lat.toFixed(5)}, {item.lng.toFixed(5)}</div>}
            {item.start_time && <div>⏱ 行程時間 {item.start_time}{item.duration ? ` · 停 ${item.duration} 分` : ''}</div>}
            {item.hours && <div>🕐 營業時間 {item.hours}</div>}
            {item.phone && <div>☎️ {item.phone}</div>}
            {item.price && <div>💰 {item.price}</div>}
            {item.dates?.length > 0 && <div>📅 {item.dates.map(d => d.display || d.date_from).join('　|　')}</div>}
            {item.brand_from && <div style={{ color: 'var(--warn)' }}>⚠️ 品牌來自 {item.brand_from}</div>}
            {item.tags?.length > 0 && <div>#️⃣ {item.tags.slice(0, 8).join(' ')}</div>}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 7, marginTop: 14, flexWrap: 'wrap' }}>
          {item.google_maps_url && (
            <a className="btn sm" href={item.google_maps_url} target="_blank" rel="noreferrer">🗺 開地圖</a>
          )}
          {item.url && (
            <a className="btn sm ghost" href={item.url} target="_blank" rel="noreferrer">🔗 原 link</a>
          )}
          <button className="btn sm ghost" style={{ color: 'var(--bad)', marginLeft: 'auto' }} onClick={del}>
            刪除
          </button>
        </div>
      </div>
    </div>
  )
}
