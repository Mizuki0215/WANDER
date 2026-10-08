import { useCallback, useMemo, useRef, useState } from 'react'
import { api, iconFor, confClass } from '../lib/api'
import { toast, Empty } from '../lib/ui'
import { toMinutes, fromMinutes, durationText } from '../lib/dates'

/**
 * 時段格日曆（Day Grid）
 * =====================
 * 用戶要求（原文）：
 *   「我想可以好似呢種圖片咁，見到佢有唔同嘅格，唔同時段嘅。
 *     然後我可以放落去某一個時段格，然後撳入去之後仲可以調教
 *     究竟佢可以佔幾多個鐘頭。」
 *
 * 設計：
 *   · 左邊時間軸，每個鐘一格（可調 30 分鐘粒度）
 *   · 活動係絕對定位嘅 block，高度 = 時長
 *   · 撳空白格 → 揀一個未排嘅景點放落去
 *   · 拖 block 上下 → 改開始時間
 *   · 拖 block 底部 → 改時長（配合你「佔幾多個鐘頭」嘅要求）
 *   · 撳 block → 開詳情
 *
 * ⚠️ 用 Pointer Events 而唔用 HTML5 Drag & Drop
 *    （HTML5 DnD 喺手機完全唔 work）
 */

const HOUR_H = 62          // 每個鐘嘅像素高度
const SNAP = 15            // 分鐘對齊
const DAY_START = 6        // 由 6:00 開始
const DAY_END = 24         // 到 24:00

// 分類 → 顏色（配合霓虹主題）
const CAT_COLOR = {
  food: '#f472b6',
  shopping: '#22d3ee',
  play: '#a855f7',
  stay: '#34d399',
  transport: '#fbbf24',
  other: '#818cf8',
}

export default function DayGrid({ trip, items, stops = [], day, onRefresh, onEditItem, onSetDay }) {
  const [dayStart, setDayStart] = useState('08:00')
  const [showPicker, setShowPicker] = useState(null)   // 撳咗空白格 → {minutes}
  const [drag, setDrag] = useState(null)               // {id, mode, ...}
  /**
   * ⚠️⚠️ 用戶要求 ①（合併）：
   *   「我哋可以擺一啲活動上去，同埋將啲活動拖去唔同時間 ——
   *    呢兩個其實可以 combine 埋其中一個，即係你將啲活動
   *    擺喺最下低嘅，然後可以直接拖上去嗰個 timeslot 度
   *    更改時間。」
   *
   *   → 底部托盤（未排入行程）嘅活動可以直接**拖上時段格**。
   *     唔使再行「撳空白格 → 彈層 → 揀活動 → 揀時長」四步。
   *
   * ⚠️ 用 Pointer Events 而唔用 HTML5 Drag & Drop ——
   *    HTML5 DnD 喺手機**完全唔 work**
   *    （原本「逐日編排」就係因為咁而死）。
   */
  const [tray, setTray] = useState(null)               // {item, minutes|null}
  const trayRef = useRef(null)
  const gridRef = useRef(null)
  const dragRef = useRef(null)

  const dayItems = useMemo(
    () => items.filter(i => Number(i.day_index) === Number(day)),
    [items, day])
  const pool = useMemo(() => items.filter(i => i.day_index == null), [items])

  /** 將 items 砌成有 start/duration 嘅 block（冇 start_time 就自動接落去）。 */
  const blocks = useMemo(() => {
    let cursor = toMinutes(dayStart)
    const sorted = [...dayItems].sort((a, b) => {
      const sa = toMinutes(a.start_time), sb = toMinutes(b.start_time)
      if (sa != null && sb != null) return sa - sb
      if (sa != null) return -1
      if (sb != null) return 1
      return (a.sort_order ?? 0) - (b.sort_order ?? 0)
    })
    return sorted.map(it => {
      const explicit = toMinutes(it.start_time)
      const start = explicit != null ? explicit : cursor
      const dur = Number(it.duration) > 0 ? Number(it.duration) : 60
      cursor = start + dur
      return { item: it, start, duration: dur, auto: explicit == null }
    })
  }, [dayItems, dayStart])

  const totalMin = (DAY_END - DAY_START) * 60
  const hours = Array.from({ length: DAY_END - DAY_START + 1 }, (_, i) => DAY_START + i)

  const yOf = (minutes) => ((minutes - DAY_START * 60) / 60) * HOUR_H
  const minutesOfY = (y) => {
    const raw = DAY_START * 60 + (y / HOUR_H) * 60
    return Math.max(DAY_START * 60, Math.min(DAY_END * 60, Math.round(raw / SNAP) * SNAP))
  }

  // ══ 儲存 ══
  const save = useCallback(async (item, patch) => {
    try {
      await api.patchItem(item.id, { parsed: patch })
      await onRefresh()
    } catch (e) { toast(e.message) }
  }, [onRefresh])

  // ══ 拖動 / 拉長短 ══
  const dragMove = useCallback((e) => {
    const d = dragRef.current
    if (!d) return
    const rect = gridRef.current.getBoundingClientRect()
    const y = e.clientY - rect.top + gridRef.current.scrollTop
    if (d.mode === 'move') {
      const newStart = minutesOfY(y - d.grabOffset)
      dragRef.current = { ...d, preview: { start: newStart, duration: d.duration } }
      setDrag({ ...dragRef.current })
    } else {
      const newDur = Math.max(SNAP, Math.round((minutesOfY(y) - d.start) / SNAP) * SNAP)
      dragRef.current = { ...d, preview: { start: d.start, duration: newDur } }
      setDrag({ ...dragRef.current })
    }
  }, [])

  const dragEnd = useCallback(() => {
    const d = dragRef.current
    dragRef.current = null
    setDrag(null)
    window.removeEventListener('pointermove', dragMove)
    window.removeEventListener('pointerup', dragEnd)
    if (!d || !d.preview) return
    const { start, duration } = d.preview
    if (start === d.start && duration === d.duration) return
    save(d.item, { start_time: fromMinutes(start), duration })
    toast(d.mode === 'move'
      ? `改為 ${fromMinutes(start)} 開始`
      : `改為 ${durationText(duration)}`)
  }, [dragMove, save])

  function startDrag(e, blk, mode) {
    e.stopPropagation()
    e.preventDefault()
    const rect = gridRef.current.getBoundingClientRect()
    const y = e.clientY - rect.top + gridRef.current.scrollTop
    dragRef.current = {
      id: blk.item.id, item: blk.item, mode,
      start: blk.start, duration: blk.duration,
      grabOffset: y - yOf(blk.start),
      preview: { start: blk.start, duration: blk.duration },
    }
    setDrag({ ...dragRef.current })
    window.addEventListener('pointermove', dragMove)
    window.addEventListener('pointerup', dragEnd)
  }

  // ══ 撳空白格 ══
  function onGridClick(e) {
    if (dragRef.current) return
    const rect = gridRef.current.getBoundingClientRect()
    const y = e.clientY - rect.top + gridRef.current.scrollTop
    const m = minutesOfY(y)
    // 撳嘅位置已經有 block 就唔開 picker
    const hit = blocks.find(b => m >= b.start && m < b.start + b.duration)
    if (hit) { onEditItem?.(hit.item); return }
    setShowPicker({ minutes: m })
  }

  /** 放一個 item 落某個時間。 */
  async function place(item, minutes, duration = 60) {
    try {
      await api.patchItem(item.id, {
        day_index: day,
        parsed: { start_time: fromMinutes(minutes), duration },
      })
      toast(`已放喺 ${fromMinutes(minutes)}`)
      setShowPicker(null)
      await onRefresh()
    } catch (e) { toast(e.message) }
  }

  // ══════════════════════════════════════════════════════════════
  // 托盤拖入時段格（用戶要求 ①）
  // ══════════════════════════════════════════════════════════════
  //
  // ⚠️ 同「格入面拖 block」唔同：呢個由**格外面**開始拖。
  //   所以要自己判斷 pointer 有冇進入格嘅範圍。
  //
  // ⚠️ 唔可以用 `setPointerCapture` —— 一格住 pointer 之後
  //    `pointermove` 就唔會再喺格上面觸發，判斷唔到位置。

  const trayMove = useCallback((e) => {
    const d = trayRef.current
    if (!d || !gridRef.current) return
    const r = gridRef.current.getBoundingClientRect()
    const inside = e.clientX >= r.left && e.clientX <= r.right &&
                   e.clientY >= r.top && e.clientY <= r.bottom
    if (!inside) {
      if (d.minutes != null) {
        trayRef.current = { ...d, minutes: null }
        setTray({ ...trayRef.current })
      }
      return
    }
    const y = e.clientY - r.top + gridRef.current.scrollTop
    const m = minutesOfY(y)
    if (m !== d.minutes) {
      trayRef.current = { ...d, minutes: m }
      setTray({ ...trayRef.current })
    }
  }, [])

  const trayUp = useCallback(() => {
    const d = trayRef.current
    trayRef.current = null
    setTray(null)
    window.removeEventListener('pointermove', trayMove)
    window.removeEventListener('pointerup', trayUp)
    window.removeEventListener('pointercancel', trayUp)
    if (!d) return
    // ⚠️ 冇拖入格 → 唔做嘢（唔好當「撳一下」就亂放）
    if (d.minutes == null) return
    place(d.item, d.minutes, 60)
  }, [trayMove])   // eslint-disable-line react-hooks/exhaustive-deps

  function startTrayDrag(e, it) {
    e.preventDefault()
    trayRef.current = { item: it, minutes: null }
    setTray({ ...trayRef.current })
    window.addEventListener('pointermove', trayMove)
    window.addEventListener('pointerup', trayUp)
    window.addEventListener('pointercancel', trayUp)
  }

  const nowLine = useMemo(() => {
    const d = new Date()
    const m = d.getHours() * 60 + d.getMinutes()
    return m >= DAY_START * 60 && m <= DAY_END * 60 ? m : null
  }, [])

  return (
    <div>
      {/* 工具列 */}
      <div className="row" style={{ marginBottom: 10 }}>
        <div className="sub" style={{ fontSize: 11 }}>由</div>
        <input className="input" type="time" value={dayStart}
          onChange={e => setDayStart(e.target.value)}
          style={{ width: 116, padding: '7px 10px', fontSize: 12 }} />
        <div className="sub" style={{ fontSize: 11, flex: 1, textAlign: 'right' }}>
          {blocks.length} 個活動 · 共 {durationText(blocks.reduce((n, b) => n + b.duration, 0)) || '0'}
        </div>
      </div>

      {/* ══ 時段格 ══ */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex' }}>
          {/* 時間軸 */}
          <div style={{
            flex: '0 0 50px', borderRight: '1px solid var(--border)',
            background: 'var(--surface-2)',
          }}>
            {hours.map(h => (
              <div key={h} style={{
                height: HOUR_H, position: 'relative',
                borderTop: h === DAY_START ? 'none' : '1px solid var(--border)',
              }}>
                <span className="mono" style={{
                  position: 'absolute', top: 4, right: 6, fontSize: 9.5, color: 'var(--dim)',
                }}>{String(h).padStart(2, '0')}:00</span>
              </div>
            ))}
          </div>

          {/* 內容區 */}
          <div ref={gridRef} onClick={onGridClick} style={{
            flex: 1, position: 'relative', height: (DAY_END - DAY_START) * HOUR_H,
            background: 'var(--surface)', touchAction: 'pan-y',
          }}>
            {/* 橫線 */}
            {hours.slice(0, -1).map((h, i) => (
              <div key={h} style={{
                position: 'absolute', left: 0, right: 0, top: (i + 1) * HOUR_H,
                borderTop: '1px solid var(--border)', pointerEvents: 'none',
              }} />
            ))}
            {/* 半小時虛線 */}
            {hours.slice(0, -1).map((h, i) => (
              <div key={`hh${h}`} style={{
                position: 'absolute', left: 0, right: 0, top: i * HOUR_H + HOUR_H / 2,
                borderTop: '1px dashed color-mix(in srgb, var(--border) 55%, transparent)',
                pointerEvents: 'none',
              }} />
            ))}

            {/* 現在時間線 */}
            {nowLine != null && Number(day) === 1 && (
              <div style={{
                position: 'absolute', left: 0, right: 0, top: yOf(nowLine),
                borderTop: '2px solid var(--bad)', pointerEvents: 'none', zIndex: 6,
              }}>
                <span style={{
                  position: 'absolute', left: 2, top: -7, fontSize: 8.5, fontWeight: 900,
                  background: 'var(--bad)', color: '#fff', padding: '1px 5px', borderRadius: 'var(--r-xs)',
                }}>{fromMinutes(nowLine)}</span>
              </div>
            )}

            {/* ⚠️⚠️ 托盤拖入時嘅**鬼影**（用戶要求 ①）——
                   唔顯示嘅話用戶唔知會放喺邊。
                   ⚠️ `pointerEvents: 'none'` 一定要有 ——
                      否則鬼影會擋住 pointermove。 */}
            {tray?.minutes != null && (
              <div style={{
                position: 'absolute', left: 6, right: 6,
                top: yOf(tray.minutes), height: HOUR_H,
                border: '2px dashed var(--cyan)',
                borderRadius: 'var(--r-xs)',
                background: 'color-mix(in srgb, var(--cyan) 20%, transparent)',
                pointerEvents: 'none', zIndex: 8,
                display: 'flex', alignItems: 'center', paddingLeft: 10,
                fontSize: 11.5, fontWeight: 800, color: 'var(--fg)',
              }}>
                {iconFor(tray.item)} {tray.item.name || '（未有名稱）'}
                <span className="mono" style={{ marginLeft: 8, fontSize: 10.5 }}>
                  {fromMinutes(tray.minutes)}
                </span>
              </div>
            )}

            {/* 活動 block */}
            {blocks.map(blk => {
              const it = blk.item
              const dragging = drag?.id === it.id
              const start = dragging ? drag.preview.start : blk.start
              const dur = dragging ? drag.preview.duration : blk.duration
              const color = CAT_COLOR[it.category] || CAT_COLOR.other
              const top = yOf(start)
              const h = Math.max(24, (dur / 60) * HOUR_H - 3)
              // 超出範圍就唔顯示
              if (top + h < 0 || top > (DAY_END - DAY_START) * HOUR_H) return null
              return (
                <div key={it.id}
                  onPointerDown={e => {
                    // 撳底部 14px = 拉長短；其餘 = 移動
                    const rect = e.currentTarget.getBoundingClientRect()
                    const nearBottom = (e.clientY - rect.top) > rect.height - 16
                    startDrag(e, blk, nearBottom ? 'resize' : 'move')
                  }}
                  style={{
                    position: 'absolute', left: 4, right: 6, top, height: h,
                    background: `linear-gradient(100deg, ${color}, color-mix(in srgb, ${color} 55%, var(--surface-2)))`,
                    border: `1px solid ${color}`,
                    borderRadius: 'var(--r-sm)', padding: '5px 8px', overflow: 'hidden',
                    cursor: dragging ? 'grabbing' : 'grab',
                    zIndex: dragging ? 8 : 4,
                    boxShadow: dragging ? `0 6px 20px ${color}66` : '0 2px 6px rgba(0,0,0,.22)',
                    touchAction: 'none', userSelect: 'none',
                    opacity: dragging ? .92 : 1,
                  }}>
                  <div style={{
                    fontSize: 11.5, fontWeight: 800, color: '#0b0518',
                    lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {iconFor(it)} {it.name || '（未有名稱）'}
                  </div>
                  {h > 34 && (
                    <div className="mono" style={{
                      fontSize: 9.5, color: '#0b0518', opacity: .8, marginTop: 2,
                    }}>
                      {fromMinutes(start)}–{fromMinutes(start + dur)}
                      {blk.auto ? ' · 估算' : ` · ${durationText(dur)}`}
                    </div>
                  )}
                  {/* 拉長短 handle */}
                  <div style={{
                    position: 'absolute', left: 0, right: 0, bottom: 0, height: 13,
                    cursor: 'ns-resize', display: 'flex', alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <div style={{
                      width: 26, height: 3, borderRadius: 2,
                      background: 'rgba(11,5,24,.42)',
                    }} />
                  </div>
                </div>
              )
            })}

            {/* 空狀態 */}
            {blocks.length === 0 && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                pointerEvents: 'none', color: 'var(--dim)', fontSize: 12,
                textAlign: 'center', lineHeight: 1.9,
              }}>
                撳任何一格放景點入去<br />
                <span style={{ fontSize: 10.5 }}>拖 block 可以改時間／拉長短</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══ 未排入行程 ══ */}
      <div className="sec">未排入行程 · {pool.length}</div>
      {pool.length === 0 ? (
        <div className="sub" style={{ padding: '6px 0', fontSize: 11.5 }}>
          {dayItems.length ? '全部景點都排好 ✓' : '冇景點可以排'}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 7, overflowX: 'auto', paddingBottom: 6 }}>
          {pool.map(it => (
            <button key={it.id} className="card tap"
              onClick={() => setShowPicker({ minutes: toMinutes(dayStart), item: it })}
              style={{
                flex: '0 0 auto', minWidth: 130, maxWidth: 160, padding: 10, textAlign: 'left',
              }}>
              <div style={{ fontSize: 17 }}>{iconFor(it)}</div>
              <div style={{
                fontSize: 11.5, fontWeight: 700, marginTop: 4,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{it.name || '（未有名稱）'}</div>
              <div className="sub" style={{ fontSize: 10 }}>
                {(it.district || it.city || '未分類')}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          未排入行程托盤（用戶要求 ①：合併「加活動」同「拖時間」）
          ══════════════════════════════════════════════════════════
          ⚠️ 用戶原話：
            「你將啲活動擺喺最下低嘅，然後你可以直接拖上去
             嗰個 timeslot 度，咁就可以更改時間。」

          ⚠️ 兩種操作都保留：
            · **拖**上格 → 自己揀時間（桌面 + 手機都用 Pointer Events）
            · **撳** → 開彈層揀時長（手機單手用，唔使拖）
          ⚠️ 唔可以淨係靠拖 —— 手機拖落一個 62px 高嘅格好易失手。
      */}
      <div ref={trayRef} style={{ marginTop: 16 }}>
        <div className="sec">
          未排入行程 · {pool.length}
          {pool.length > 0 && (
            <span className="sub" style={{ fontSize: 10, fontWeight: 400, marginLeft: 6 }}>
              拖上格 → 排時間
            </span>
          )}
        </div>
        {pool.length === 0 ? (
          <div className="sub" style={{ fontSize: 11.5, padding: '6px 0' }}>
            {dayItems.length > 0 ? '全部景點都已經排好 ✓' : '冇景點可以排'}
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
            gap: 8,
          }}>
            {pool.map(it => {
              const dragging = tray?.item?.id === it.id
              return (
                <div key={it.id}
                  className="stop"
                  onPointerDown={e => startTrayDrag(e, it)}
                  onClick={() => setShowPicker({ minutes: null, item: it })}
                  style={{
                    cursor: 'grab',
                    touchAction: 'none',      // ⚠️ 唔係嘅話手機當佢係捲動
                    marginBottom: 0,
                    opacity: dragging ? .45 : 1,
                    borderColor: dragging ? 'var(--cyan)' : undefined,
                    userSelect: 'none',
                  }}>
                  <span style={{ fontSize: 16 }}>{iconFor(it)}</span>
                  <div className="d">
                    <h4 style={{ fontSize: 12.5 }}>{it.name || '（未有名稱）'}</h4>
                    <p style={{ fontSize: 10 }}>
                      {(it.district || it.city || '未分類')}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: 14, borderColor: 'var(--border-hi)' }}>
        <div className="sub" style={{ fontSize: 11, lineHeight: 1.85 }}>
          💡 <b>拖托盤上格</b> → 排時間 · <b>拖 block</b> → 改開始時間 ·
          <b> 拖底部橫線</b> → 改佔幾多個鐘 · <b>撳空白格</b> → 揀景點
        </div>
      </div>

      {/* ══ 揀景點彈層 ══ */}
      {showPicker && (
        <PickerSheet
          minutes={showPicker.minutes}
          presets={[30, 60, 90, 120, 180]}
          items={showPicker.item ? [showPicker.item] : pool}
          dayLabel={day}
          onClose={() => setShowPicker(null)}
          onPick={(it, dur) => place(it, showPicker.minutes, dur)}
        />
      )}
    </div>
  )
}

/** 揀景點 + 揀時長。 */
function PickerSheet({ minutes, presets, items, dayLabel, onClose, onPick }) {
  const [sel, setSel] = useState(items.length === 1 ? items[0] : null)
  const [dur, setDur] = useState(60)
  const [custom, setCustom] = useState('')

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 88, background: 'rgba(0,0,0,.66)',
      backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'flex-end',
    }}>
      <div onClick={e => e.stopPropagation()} className="card" style={{
        width: '100%', maxWidth: 640, margin: '0 auto', maxHeight: '86vh', overflowY: 'auto',
        borderRadius: 'var(--r) var(--r) 0 0', borderColor: 'var(--border-hi)',
        paddingBottom: 'calc(20px + var(--safe-b))',
      }}>
        <div className="row" style={{ marginBottom: 4 }}>
          <div>
            <div style={{ fontWeight: 900, fontSize: 15 }}>放喺 Day {dayLabel} · {fromMinutes(minutes)}</div>
            <div className="sub" style={{ fontSize: 11 }}>揀一個景點，再揀佔幾多個鐘</div>
          </div>
          <button className="btn sm ghost" onClick={onClose}>✕</button>
        </div>

        {items.length === 0 ? (
          <Empty icon="sparkle" title="冇未排嘅景點" hint="去「收藏」加多啲先" />
        ) : (
          <>
            <div className="sec">揀景點</div>
            <div style={{ maxHeight: 250, overflowY: 'auto' }}>
              {items.map(it => (
                <button key={it.id} onClick={() => setSel(it)}
                  className="item"
                  style={{
                    width: '100%', textAlign: 'left', alignItems: 'center',
                    borderColor: sel?.id === it.id ? 'var(--border-hi)' : 'var(--border)',
                    boxShadow: sel?.id === it.id ? 'var(--glow)' : 'none',
                    cursor: 'pointer',
                  }}>
                  <div className="ic" style={{ fontSize: 18 }}>{iconFor(it)}</div>
                  <div className="info">
                    <h4>{it.name || '（未有名稱）'}</h4>
                    <p>{(it.location_path || []).join(' › ') || '未分類'}</p>
                  </div>
                  <span className={`conf ${confClass(it.confidence)}`}>{it.confidence}%</span>
                </button>
              ))}
            </div>

            <div className="sec">佔幾多個鐘</div>
            <div className="chips">
              {presets.map(p => (
                <button key={p} className={`chip ${dur === p ? 'on' : ''}`}
                  onClick={() => { setDur(p); setCustom('') }}>
                  {durationText(p)}
                </button>
              ))}
            </div>
            <div className="row" style={{ gap: 8, marginTop: 9 }}>
              <input className="input" type="number" min="15" max="720" step="15"
                placeholder="自訂（分鐘）" value={custom}
                onChange={e => {
                  setCustom(e.target.value)
                  const n = Number(e.target.value)
                  if (n >= 15) setDur(n)
                }} />
              <span className="sub" style={{ fontSize: 12, flex: '0 0 auto' }}>
                = {durationText(dur) || '—'}
              </span>
            </div>

            <button className="btn primary wide" style={{ marginTop: 15 }} disabled={!sel}
              onClick={() => sel && onPick(sel, dur)}>
              {sel ? `放「${sel.name || '呢個景點'}」落去` : '先揀一個景點'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
