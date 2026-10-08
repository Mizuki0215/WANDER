import { useEffect, useMemo, useRef, useState } from 'react'
import CityPicker from './CityPicker'
import { api, iconFor } from '../lib/api'
import { toast, Spinner } from '../lib/ui'
import { STOP_COLORS, findConflicts, stopsSummary } from '../lib/stops'

/**
 * 城市規劃編輯器
 * ==============
 *
 * 用戶要求（原文）：
 *   「plan 旅行可以選由幾多日去幾多日：先 type 去嘅地方（city），
 *     會有一個 ＋ button 加其他城市。如多於一個 city →
 *     寫低幾多日 for 某 city。呢啲之前可以有一個 edit button 之後修改。」
 *
 *   「如果改了 like 首爾 → 改做仲留在福岡。then 呢一日首爾嘅行程
 *     → 有一個 notification（window）似電腦 style 同你講有 conflict →
 *     由於地區改變了有行程有衝突，是否幫你 delete 佢？
 *     揀 Yes 就 delete，揀 No 就唔 delete 但用另一隻顏色 highlight 話係 warning。」
 */
export default function StopsEditor({ trip, items, stops, onRefresh, onClose }) {
  const [draft, setDraft] = useState(() => {
    const init = (stops || []).map(s => ({ city: s.city, days: Number(s.days) || 1 }))
    return init.length ? init : [{ city: trip?.destination || '', days: trip?.days || 3 }]
  })
  const [busy, setBusy] = useState(false)
  const [conflict, setConflict] = useState(null)   // { list, preview }
  const [newCity, setNewCity] = useState('')
  const [sug, setSug] = useState([])               // 城市建議
  const [sugFor, setSugFor] = useState(null)       // 邊個輸入框（index | 'new'）
  const sugTimer = useRef(null)

  const totalDays = useMemo(
    () => draft.reduce((n, s) => n + (Number(s.days) || 0), 0), [draft])

  /** 城市自動完成（用本地城市庫，0ms）。 */
  function onCityType(v, idx) {
    setSugFor(idx)
    if (idx === 'new') setNewCity(v)
    else setCity(idx, v)
    clearTimeout(sugTimer.current)
    if (!v || v.trim().length < 1) { setSug([]); return }
    sugTimer.current = setTimeout(async () => {
      try {
        const r = await api.searchCities(v.trim(), 6)
        setSug(r.results || [])
      } catch { setSug([]) }
    }, 140)
  }
  function pickSug(s) {
    if (sugFor === 'new') { setDraft(d => [...d, { city: s.query, days: 2 }]); setNewCity('') }
    else setCity(sugFor, s.query)
    setSug([]); setSugFor(null)
  }

  function addCity() {
    const c = newCity.trim()
    if (!c) return toast('請輸入城市名')
    setDraft(d => [...d, { city: c, days: 2 }])
    setNewCity('')
    setSug([])
  }
  function removeCity(i) {
    setDraft(d => (d.length <= 1 ? d : d.filter((_, k) => k !== i)))
  }
  function setDays(i, v) {
    setDraft(d => d.map((s, k) => (k === i ? { ...s, days: Math.max(1, Math.min(60, Number(v) || 1)) } : s)))
  }
  function setCity(i, v) {
    setDraft(d => d.map((s, k) => (k === i ? { ...s, city: v } : s)))
  }

  /** 計出改咗之後會有咩衝突（未存之前先睇）。 */
  function previewConflicts() {
    const nextStops = draft.map((s, i) => ({ ...s, position: i }))
    return findConflicts(items, nextStops, totalDays)
  }

  async function save({ deleteConflicts = false } = {}) {
    if (!draft.some(s => s.city.trim())) return toast('至少要填一個城市')
    setBusy(true)
    try {
      const nextStops = draft
        .filter(s => s.city.trim())
        .map((s, i) => ({ city: s.city.trim(), days: Number(s.days) || 1, position: i }))
      const conflicts = findConflicts(items, nextStops, totalDays)

      await api.setStops(trip.id, nextStops)

      if (deleteConflicts && conflicts.length) {
        for (const c of conflicts) {
          try { await api.deleteItem(c.item.id) } catch {}
        }
        toast(`已刪除 ${conflicts.length} 個衝突行程`)
      } else if (conflicts.length) {
        toast(`已儲存 · ${conflicts.length} 個行程有衝突（已標記 warning）`)
      } else {
        toast('城市規劃已儲存 ✓')
      }
      await onRefresh()
      onClose?.()
    } catch (e) { toast(e.message) } finally { setBusy(false) }
  }

  /** 撳「儲存」時：有衝突就先彈窗問。 */
  function submit() {
    const conflicts = previewConflicts()
    if (conflicts.length === 0) return save()
    setConflict(conflicts)
  }

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 85, background: 'rgba(0,0,0,.66)',
      backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'flex-end',
    }}>
      <div onClick={e => e.stopPropagation()} className="card" style={{
        width: '100%', maxWidth: 640, margin: '0 auto', maxHeight: '90vh', overflowY: 'auto',
        borderRadius: 'var(--r) var(--r) 0 0', borderColor: 'var(--border-hi)',
        paddingBottom: 'calc(20px + var(--safe-b))', boxShadow: '0 -10px 40px rgba(0,0,0,.5)',
      }}>
        {/* 標題 */}
        <div className="row" style={{ marginBottom: 4 }}>
          <div>
            <div style={{ fontWeight: 900, fontSize: 16 }}>城市規劃</div>
            <div className="sub" style={{ fontSize: 11 }}>
              總共 {totalDays} 日
              {trip?.start_date ? ` · ${trip.start_date} 起` : ''}
            </div>
          </div>
          <button className="btn sm ghost" onClick={onClose}>✕</button>
        </div>

        {stopsSummary(stops) && (
          <div className="sub" style={{ fontSize: 11, marginTop: 6 }}>
            而家：{stopsSummary(stops)}
          </div>
        )}

        {/* 城市列 */}
        <div className="sec">去邊幾個城市 · 每個幾多日</div>
        {draft.map((s, i) => (
          <div key={i} style={{
            display: 'flex', gap: 8, alignItems: 'center', marginBottom: 9,
            paddingLeft: 10, borderLeft: `3px solid ${STOP_COLORS[i % STOP_COLORS.length]}`,
          }}>
            <span className="mono" style={{
              fontSize: 10, color: STOP_COLORS[i % STOP_COLORS.length], flex: '0 0 22px',
            }}>{i + 1}</span>
            <CityPicker value={s.city} hideList
              placeholder="城市（打中文／英文）"
              onChange={v => setCity(i, v)}
              onPick={r => { setSug(r.matched ? `${r.query}（${r.matched}）` : r.query); setSugFor(i) }} />
            <input className="input" type="number" min="1" max="60" value={s.days}
              onChange={e => setDays(i, e.target.value)}
              style={{ width: 66, textAlign: 'center', fontWeight: 700 }} />
            <span className="sub" style={{ fontSize: 11, flex: '0 0 auto' }}>日</span>
            <button className="btn sm ghost" style={{ padding: '6px 9px', fontSize: 12 }}
              onClick={() => removeCity(i)} disabled={draft.length <= 1}>✕</button>
          </div>
        ))}

        {/* 城市建議 */}
        {sug.length > 0 && sugFor !== null && (
          <div className="card" style={{ marginBottom: 10, padding: 6 }}>
            {sug.map((r, i) => (
              <button key={i} onClick={() => pickSug(r)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '8px 10px', borderRadius: 'var(--r-xs)', fontSize: 13,
                  borderBottom: i < sug.length - 1 ? '1px dashed var(--border)' : 'none',
                }}>
                <b>{r.query}</b>
                <span className="sub" style={{ fontSize: 11, marginLeft: 8 }}>
                  {r.country}{r.population ? ` · ${(r.population / 10000).toFixed(0)}萬人` : ''}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* 加城市 */}
        <div className="row" style={{ gap: 7, marginTop: 4 }}>
          <CityPicker value={newCity} placeholder="加另一個城市…"
            onChange={setNewCity}
            onPick={r => {
              setDraft(d => [...d, { city: r.query, days: 2 }])
              setNewCity(''); setSug([])
              toast(`加咗「${r.query}」`)
            }} />
          <button className="btn" onClick={addCity}>＋ 加城市</button>
        </div>

        {/* 日子預覽 */}
        <div className="sec">日子分配</div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(() => {
            const arr = []
            let day = 1
            draft.forEach((s, i) => {
              const n = Number(s.days) || 0
              for (let k = 0; k < n; k++, day++) {
                arr.push(
                  <span key={day} title={`Day ${day} · ${s.city}`} style={{
                    fontSize: 10, fontWeight: 800, padding: '4px 7px', borderRadius: 'var(--r-xs)',
                    background: STOP_COLORS[i % STOP_COLORS.length], color: '#0b0518',
                  }}>{day}</span>
                )
              }
            })
            return arr
          })()}
        </div>
        <div className="sub" style={{ fontSize: 10.5, marginTop: 7, lineHeight: 1.7 }}>
          💡 兩邊城市交界嘅一日叫「**過渡日**」—— 例如 Day 4 由福岡去首爾，
          兩邊嘅行程都當合理，唔會報衝突。
        </div>
        <div className="sub" style={{ fontSize: 10.5, marginTop: 5, lineHeight: 1.7 }}>
          🗺 儲存之後會自動查城市座標（本地城市庫，即時），
          地圖就會定位去你嘅目的地。
        </div>

        <button className="btn primary wide" style={{ marginTop: 16 }} onClick={submit} disabled={busy}>
          {busy ? <Spinner /> : '儲存城市規劃'}
        </button>

        {/* ═══ 衝突對話框（電腦 style）═══ */}
        {conflict && (
          <div style={{
            position: 'fixed', inset: 0, zIndex: 95, background: 'rgba(0,0,0,.55)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
          }}>
            <div className="card glow" style={{
              maxWidth: 460, width: '100%', borderColor: 'var(--warn)',
              borderWidth: 2, boxShadow: '0 20px 60px rgba(0,0,0,.6)',
            }}>
              <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 26 }}>⚠️</span>
                <div>
                  <div style={{ fontWeight: 900, fontSize: 15, color: 'var(--warn)' }}>
                    行程有衝突
                  </div>
                  <div className="sub" style={{ fontSize: 12, marginTop: 5, lineHeight: 1.75 }}>
                    因為地區改變咗，有 <b>{conflict.length}</b> 個行程同新嘅城市安排唔夾。
                    <br />要幫你刪除佢哋嗎？
                  </div>
                </div>
              </div>

              <div style={{
                marginTop: 13, maxHeight: 190, overflowY: 'auto',
                border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: 10,
                background: 'var(--surface-2)',
              }}>
                {conflict.slice(0, 12).map((c, i) => (
                  <div key={c.item.id} style={{
                    fontSize: 12, padding: '6px 0',
                    borderTop: i ? '1px dashed var(--border)' : 'none',
                  }}>
                    <div style={{ fontWeight: 700 }}>
                      Day {c.day} · {iconFor(c.item)} {c.item.name || '（未有名稱）'}
                    </div>
                    <div className="sub" style={{ fontSize: 10.5, color: 'var(--warn)' }}>
                      {c.reason}
                    </div>
                  </div>
                ))}
                {conflict.length > 12 && (
                  <div className="sub" style={{ fontSize: 11, marginTop: 6 }}>
                    …仲有 {conflict.length - 12} 個
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 15, flexWrap: 'wrap' }}>
                <button className="btn primary" style={{ flex: 1, background: 'var(--bad)', color: '#fff', borderColor: 'transparent' }}
                  onClick={() => { setConflict(null); save({ deleteConflicts: true }) }}>
                  係，刪除佢哋
                </button>
                <button className="btn" style={{ flex: 1 }}
                  onClick={() => { setConflict(null); save({ deleteConflicts: false }) }}>
                  唔使，標記做 warning
                </button>
              </div>
              <button className="btn ghost wide sm" style={{ marginTop: 8 }}
                onClick={() => setConflict(null)}>取消，繼續編輯</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
