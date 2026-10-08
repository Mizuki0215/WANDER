import { useMemo, useRef, useState } from 'react'
import PixelIcon from './PixelIcon'
import { api, iconFor, confClass } from '../lib/api'
import { toast, Empty } from '../lib/ui'
import { tripDays, tripLength, countdownText, dateRangeText, buildTimeline } from '../lib/dates'
import { buildDayCities, findConflicts, STOP_COLORS, stopsSummary } from '../lib/stops'
import StopsEditor from './StopsEditor'
import DayGrid from './DayGrid'

/**
 * 月曆 / 行程總覽
 *
 * 兩個模式：
 *   · overview  全部日子一齊睇（有真實日期，可以一眼睇完成個 trip）
 *   · day       單日編排（拖拽排序、加減景點）
 *
 * 編排存 DB：(day_index, sort_order)，day_index = NULL 代表未排。
 */
export default function Calendar({ trip, items, stops = [], onRefresh, onEditItem }) {
  const [editStops, setEditStops] = useState(false)
  const days = useMemo(() => tripDays(trip), [trip])
  const [mode, setMode] = useState('overview')      // overview | grid
  const [active, setActive] = useState(1)
  const [dropTarget, setDropTarget] = useState(null)
  const [dayStart, setDayStart] = useState('09:00')
  const dragId = useRef(null)

  const scheduled = useMemo(() => items.filter(i => i.day_index != null), [items])
  const pool = useMemo(() => items.filter(i => i.day_index == null), [items])

  // 城市 ↔ 日子對應（含過渡日）
  const dayCities = useMemo(
    () => new Map(buildDayCities(stops, tripLength(trip)).map(d => [d.day, d])), [stops, trip])

  // ⚠️ 衝突：該日城市同景點城市唔夾，但**過渡日唔算**（用戶要求）
  const conflicts = useMemo(
    () => findConflicts(items, stops, tripLength(trip)), [items, stops, trip])
  const conflictIds = useMemo(() => new Set(conflicts.map(c => c.item.id)), [conflicts])

  // 城市 → 顏色
  const cityColor = useMemo(() => {
    const m = new Map()
    ;(stops || []).forEach((s, i) => {
      if (s.city) m.set(s.city.trim(), STOP_COLORS[i % STOP_COLORS.length])
    })
    return m
  }, [stops])

  function colorForDay(day) {
    const info = dayCities.get(day)
    if (!info || !info.cities.length) return null
    return cityColor.get(info.cities[0]) || null
  }

  const byDay = (d) => scheduled
    .filter(i => Number(i.day_index) === d)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))

  const totalPinned = scheduled.length
  const pct = items.length ? Math.round((totalPinned / items.length) * 100) : 0
  const countdown = countdownText(trip)

  async function persist(list) {
    const layout = list.map((i, idx) => ({
      id: i.id, day_index: i.day_index ?? null, sort_order: idx,
    }))
    try { await api.reorder(trip.id, layout); await onRefresh() }
    catch (e) { toast(e.message) }
  }

  function moveTo(itemId, dayIndex, beforeId = null) {
    const item = items.find(i => i.id === itemId)
    if (!item) return
    let list = dayIndex == null ? [] : byDay(dayIndex).filter(i => i.id !== itemId)
    const moved = { ...item, day_index: dayIndex }
    if (beforeId) {
      const at = list.findIndex(i => i.id === beforeId)
      list = at >= 0 ? [...list.slice(0, at), moved, ...list.slice(at)] : [...list, moved]
    } else {
      list = [...list, moved]
    }
    const others = scheduled.filter(i =>
      i.id !== itemId && (dayIndex == null || Number(i.day_index) !== dayIndex))
    persist([...others, ...list])
    toast(dayIndex == null ? '已移出行程' : `已排入 Day ${dayIndex} ✓`)
  }

  async function changeLength(delta) {
    const next = Math.max(1, Math.min(30, tripLength(trip) + delta))
    if (next === tripLength(trip)) return
    // 有 start_date 就同步推 end_date，冇就改 days
    const patch = { days: next }
    if (trip?.start_date) {
      const s = new Date(trip.start_date + 'T00:00:00')
      const e = new Date(s); e.setDate(e.getDate() + next - 1)
      const p = (n) => String(n).padStart(2, '0')
      patch.end_date = `${e.getFullYear()}-${p(e.getMonth() + 1)}-${p(e.getDate())}`
    }
    try { await api.updateTrip(trip.id, patch); await onRefresh(); toast(`改為 ${next} 日`) }
    catch (e) { toast(e.message) }
  }

  return (
    <div className="screen">
      {/* ═══ Trip header ═══ */}
      <div className="card glow" style={{ marginBottom: 14 }}>
        <div className="row" style={{ alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 900, fontSize: 17 }}>{trip?.name}</div>
            <div className="sub">
              {trip?.destination ? `📍 ${trip.destination} · ` : ''}
              {tripLength(trip)} 日
              {trip?.members?.length ? ` · 👥 ${trip.members.length}` : ''}
            </div>
            {dateRangeText(trip) && (
              <div className="sub mono" style={{ fontSize: 11, marginTop: 3 }}>
                {dateRangeText(trip)}
              </div>
            )}
            {stopsSummary(stops) && (
              <div className="sub" style={{ fontSize: 11, marginTop: 4 }}>
                🧭 {stopsSummary(stops)}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            {countdown && <span className="conf hi" style={{ fontSize: 8 }}>{countdown}</span>}
            <button className="btn sm ghost" style={{ fontSize: 10 }}
              onClick={() => setEditStops(true)}>🧭 城市</button>
          </div>
        </div>

        {conflicts.length > 0 && (
          <div className="card" style={{
            marginTop: 11, padding: 10, borderColor: 'var(--warn)', background: 'transparent',
          }}>
            <div className="sub" style={{ fontSize: 11.5, color: 'var(--warn)', lineHeight: 1.7 }}>
              ⚠️ 有 {conflicts.length} 個行程同城市安排唔夾（已標記 warning）。
              撳「🧭 城市」可以改，或者逐個搬去正確嘅日子。
            </div>
          </div>
        )}

        <div className="bar" style={{
          height: 4, background: 'var(--surface-3)', borderRadius: 99,
          marginTop: 12, overflow: 'hidden',
        }}>
          <i style={{
            display: 'block', height: '100%', width: `${pct}%`,
            background: 'var(--grad)', borderRadius: 99, transition: 'width .4s',
          }} />
        </div>
        <div className="row" style={{ marginTop: 6 }}>
          <span className="sub" style={{ fontSize: 10.5 }}>
            已排入行程 {totalPinned} / {items.length}
          </span>
          <div style={{ display: 'flex', gap: 5 }}>
            <button className="btn sm ghost" onClick={() => changeLength(-1)}>－1 日</button>
            <button className="btn sm ghost" onClick={() => changeLength(1)}>＋1 日</button>
          </div>
        </div>
      </div>

      {/* ═══ 模式切換 ═══ */}
      <div className="chips" style={{ marginBottom: 12 }}>
        <button className={`chip ${mode === 'overview' ? 'on' : ''}`}
          onClick={() => setMode('overview')}><PixelIcon name="list" size={15} /> 總覽</button>
        <button className={`chip ${mode === 'grid' ? 'on' : ''}`}
          onClick={() => setMode('grid')}><PixelIcon name="clock" size={15} /> 編排</button>
      </div>

      {items.length === 0 && (
        <Empty icon="🗓" title="仲未有收藏" hint="去「收藏」貼一條 link 開始計劃" />
      )}

      {/* ═══════════════ 總覽 ═══════════════ */}
      {mode === 'overview' && items.length > 0 && (
        <>
          {days.map(d => {
            const list = byDay(d.day)
            return (
              <div key={d.day} className="card" style={{ marginBottom: 10, padding: 0, overflow: 'hidden' }}>
                <div className="row" style={{
                  padding: '11px 14px', borderBottom: list.length ? '1px solid var(--border)' : 'none',
                  background: 'var(--surface-2)', cursor: 'pointer',
                }} onClick={() => { setActive(d.day); setMode('grid') }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, minWidth: 0 }}>
                    <span style={{
                      width: 4, height: 16, borderRadius: 2, flex: '0 0 4px',
                      background: colorForDay(d.day) || 'var(--border)',
                    }} />
                    <span className="mono" style={{ color: 'var(--cyan)', fontWeight: 900, fontSize: 13 }}>
                      DAY {d.day}
                    </span>
                    <span style={{ fontWeight: 700, fontSize: 12.5, whiteSpace: 'nowrap' }}>{d.full}</span>
                    {dayCities.get(d.day)?.cities?.length > 0 && (
                      <span className="chip" style={{ fontSize: 9, padding: '2px 7px' }}>
                        {dayCities.get(d.day).cities.join(' → ')}
                        {dayCities.get(d.day).transition ? ' 🔄' : ''}
                      </span>
                    )}
                  </div>
                  <span className={`conf ${list.length ? 'hi' : ''}`}>{list.length} 個</span>
                </div>
                {list.length > 0 ? (
                  <div style={{ padding: '4px 0' }}>
                    {buildTimeline(list, { dayStart }).map((row, i) => {
                      const it = row.item
                      const bad = conflictIds.has(it.id)
                      return (
                      <div key={it.id} className="ov-row"
                        onClick={() => onEditItem && onEditItem(it)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          padding: '9px 14px', cursor: 'pointer',
                          borderTop: i ? '1px dashed color-mix(in srgb, var(--border) 60%, transparent)' : 'none',
                          background: bad ? 'color-mix(in srgb, var(--warn) 14%, transparent)' : 'none',
                          borderLeft: bad ? '3px solid var(--warn)' : '3px solid transparent',
                        }}>
                        <span className="mono" style={{
                          fontSize: 11, fontWeight: 900, flex: '0 0 46px',
                          color: row.auto ? 'var(--dim)' : 'var(--cyan)',
                        }}>
                          {row.start}
                        </span>
                        <span style={{ fontSize: 16 }}>{iconFor(it)}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: 13, fontWeight: 600,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>{it.name || '（未有名稱）'}</div>
                          <div className="sub" style={{ fontSize: 10.5 }}>
                            {(it.location_path || []).join(' › ') || '未分類'}
                            {` · ${row.start}–${row.end}`}
                            {row.auto ? '（估算）' : ''}
                          </div>
                        </div>
                        {bad
                          ? <span className="conf" style={{ color: 'var(--warn)', borderColor: 'var(--warn)' }}>⚠️</span>
                          : <span className={`conf ${confClass(it.confidence)}`}>{it.confidence}%</span>}
                      </div>
                    )})}
                  </div>
                ) : (
                  <div style={{ padding: '11px 14px' }} className="sub">
                    未安排 — 撳呢度開始排
                  </div>
                )}
              </div>
            )
          })}

          {pool.length > 0 && (
            <>
              <div className="sec">未排入行程 · {pool.length}</div>
              <div className="sub" style={{ marginBottom: 8, fontSize: 11 }}>
                切去「編排」就可以拖上時段格
                <button className="btn sm ghost" style={{ marginLeft: 8, fontSize: 10.5 }}
                  onClick={() => setMode('grid')}>去編排 →</button>
              </div>
              {pool.map(it => (
                <div key={it.id} className="item" onClick={() => onEditItem && onEditItem(it)}>
                  <div className="ic">{it.raw_image ? <img src={it.raw_image} alt="" loading="lazy" /> : iconFor(it)}</div>
                  <div className="info">
                    <h4>{it.name || '（未有名稱）'}</h4>
                    <p>{(it.location_path || []).join(' › ') || '未分類'}</p>
                  </div>
                  <span className={`conf ${confClass(it.confidence)}`}>{it.confidence}%</span>
                </div>
              ))}
            </>
          )}
        </>
      )}

      {/* ═══════════════ 編排（時段格 —— 唯一可以改時間嘅地方）═══════════════ */}
      {mode === 'grid' && (
        <>
          <div className="days">
            {days.map(d => (
              <button key={d.day} className={`day ${active === d.day ? 'on' : ''}`}
                onClick={() => setActive(d.day)}>
                <div className="dw">{d.weekday ? `星期${d.weekday}` : 'DAY'}</div>
                <div className="dn">{d.day}</div>
                <div className="dw" style={{ marginTop: 3 }}>
                  {d.date ? d.label : `${byDay(d.day).length} 個`}
                </div>
              </button>
            ))}
          </div>

          <div className="sub" style={{ marginBottom: 8, fontWeight: 700 }}>
            {days.find(d => d.day === active)?.full}
            {dayCities.get(active)?.cities?.length > 0 && (
              <span className="chip" style={{ marginLeft: 8, fontSize: 10 }}>
                {dayCities.get(active).cities.join(' → ')}
                {dayCities.get(active).transition ? ' 🔄 過渡日' : ''}
              </span>
            )}
          </div>

          <DayGrid trip={trip} items={items} stops={stops} day={active}
            onRefresh={onRefresh} onEditItem={onEditItem} />
        </>
      )}

      {editStops && (
        <StopsEditor trip={trip} items={items} stops={stops}
          onRefresh={onRefresh} onClose={() => setEditStops(false)} />
      )}
    </div>
  )
}
