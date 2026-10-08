import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import CityPicker from './CityPicker'
import { toast, Empty, Spinner } from '../lib/ui'
import { STOP_COLORS } from '../lib/stops'
import { daysBetween, tripLength, countdownText, dateRangeText, addDays, toISO, parseDate } from '../lib/dates'

export default function Trips({ trips, onOpen, onRefresh, currentId = null,
                                autoNew = false, onAutoNewDone }) {
  const [view, setView] = useState(null)       // null | 'new' | 'join' | 'edit'
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', destination: '', start_date: '', end_date: '' })
  const [code, setCode] = useState('')
  // ⚠️⚠️ 用戶要求：
  //   「旅程嘅時候呢新增旅程嘅時候，咁其實係應該有一個 button
  //    俾你去加城市，而唔係當你去編輯嘅時候先至可以加新增多於
  //    一個城市，而係你一開行程就已經有得加多於一個城市。」
  //
  //   ⚠️ 之前嘅流程：建立旅程 → 入 Planner → 撳城市編輯器 → 加城市。
  //      即係**要行三個步驟**先加到第二個城市，好易以為「唔支援」。
  const [cities, setCities] = useState([])      // [{ city, days }]
  const [newCity, setNewCity] = useState('')
  const [busy, setBusy] = useState(false)

  // 由主畫面撳「＋ 開新旅程」→ 自動打開表單
  useEffect(() => {
    if (autoNew) { setView('new'); onAutoNewDone?.() }
  }, [autoNew])   // eslint-disable-line

  const days = useMemo(
    () => daysBetween(form.start_date, form.end_date),
    [form.start_date, form.end_date]
  )

  function reset() {
    setView(null); setEditing(null); setCode('')
    setForm({ name: '', destination: '', start_date: '', end_date: '' })
    setCities([]); setNewCity('')
  }

  /** 加一個城市落清單（重複就唔加）。 */
  function addCityRow(name) {
    const c = String(name || '').trim()
    if (!c) return
    if (cities.some(x => x.city === c)) { toast(`「${c}」已經加咗`); return }
    setCities(list => [...list, { city: c, days: 2 }])
    // ⚠️ 第一個城市順便填「目的地」—— 好多其他功能靠 destination
    //    （地圖中心、行程標題、天氣…），唔填就會唔一致。
    if (!form.destination) setForm(f => ({ ...f, destination: c }))
  }

  function removeCityRow(i) {
    setCities(list => list.filter((_, k) => k !== i))
  }

  function setCityDays(i, v) {
    const n = Math.max(1, Math.min(60, Number(v) || 1))
    setCities(list => list.map((x, k) => (k === i ? { ...x, days: n } : x)))
  }

  /** 城市清單嘅總日數（如果有城市，就用佢做旅程長度）。 */
  const cityDays = cities.reduce((a, b) => a + (Number(b.days) || 0), 0)

  function openNew() {
    reset(); setView('new')
  }

  function openEdit(t, e) {
    e.stopPropagation()
    setEditing(t)
    setForm({
      name: t.name || '', destination: t.destination || '',
      start_date: t.start_date || '', end_date: t.end_date || '',
    })
    setView('edit')
    // ⚠️ 載入現有城市 —— 唔係嘅話編輯一個多城市旅程會
    //    顯示空清單，跟住一撳儲存就會**清走晒**所有城市。
    setCities([])
    api.stops(t.id)
      .then(r => setCities((r.stops || []).map(x => ({
        city: x.city, days: Number(x.days) || 1,
      }))))
      .catch(() => {})
  }

  /** 改 start_date 就自動推 end_date（保持原本日數）。 */
  function onStartChange(v) {
    const prevLen = daysBetween(form.start_date, form.end_date) || 3
    const s = parseDate(v)
    setForm(f => ({
      ...f, start_date: v,
      end_date: s ? toISO(addDays(s, prevLen - 1)) : f.end_date,
    }))
  }
  function setLength(n) {
    const s = parseDate(form.start_date)
    setForm(f => ({ ...f, end_date: s ? toISO(addDays(s, Math.max(1, n) - 1)) : f.end_date }))
  }

  async function submit() {
    if (!form.name.trim()) return toast('請輸入旅程名')
    if (form.start_date && form.end_date && !days) return toast('完結日期要遲過開始日期')
    // ⚠️ 城市清單唔可以全部係空格
    const stops = cities.filter(c => c.city.trim())
    setBusy(true)
    try {
      const payload = {
        name: form.name.trim(),
        // ⚠️ 有城市清單就以**第一個城市**做目的地 ——
        //    唔可以同清單唔一致（地圖會用 destination 做中心）。
        destination: (stops[0]?.city || form.destination).trim() || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        // ⚠️ 有城市清單就用清單嘅總日數做旅程長度，
        //    唔係嘅話會出現「4 日行程但城市加埋 6 日」。
        days: stops.length ? stops.reduce((a, b) => a + b.days, 0) : (days || 3),
      }
      if (view === 'edit' && editing) {
        await api.updateTrip(editing.id, payload)
        // ⚠️ 編輯嗰陣如果有城市清單，一樣寫入
        if (stops.length) {
          try { await api.setStops(editing.id, stops) } catch {}
        }
        toast('已更新 ✓')
      } else {
        const t = await api.createTrip(payload)
        // ⚠️⚠️ 用戶要求嘅重點：**建立旅程嘅時候**就寫入城市，
        //     唔使再入 Planner 撳幾層先加到第二個城市。
        if (stops.length) {
          try {
            await api.setStops(t.id, stops)
          } catch (e) {
            // ⚠️ 唔可以因為城市寫入失敗就當成個建立失敗 ——
            //    旅程已經建立咗，用戶入到去仲可以再加。
            toast('旅程已建立，但城市未寫入：' + e.message)
          }
        }
        toast('旅程已建立 ✓')
        await onRefresh()
        reset()
        onOpen(t.id)
        return
      }
      await onRefresh(); reset()
    } catch (e) { toast(e.message) } finally { setBusy(false) }
  }

  async function join() {
    if (!code.trim()) return toast('請輸入邀請碼')
    setBusy(true)
    try {
      const t = await api.joinTrip(code.trim())
      toast(`已加入「${t.name}」✓`)
      await onRefresh(); reset(); onOpen(t.id)
    } catch (e) { toast(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="screen">
      <div className="row" style={{ alignItems: 'flex-start', marginBottom: 4 }}>
        <div>
          <div className="h1">我嘅旅程</div>
          <div className="sub">{trips.length} 個旅程</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn sm ghost" onClick={() => { reset(); setView(v => v === 'join' ? null : 'join') }}>加入</button>
          <button className="btn sm" onClick={openNew}>＋ 新旅程</button>
        </div>
      </div>

      {(view === 'new' || view === 'edit') && (
        <div className="card glow col" style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 800, fontSize: 13 }}>
            {view === 'edit' ? `編輯「${editing?.name}」` : '新旅程'}
          </div>
          <input className="input" placeholder="旅程名（例：福岡 2027）" value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          {/* ⚠️⚠️ 目的地一定要「揀」而唔係「打字」——
                 用戶報嘅真 bug：佢打「香港」落呢個欄，
                 但地圖只讀 🧭 城市編輯器（空嘅）→ 地圖跌落福岡。
                 而家用 134k 本地城市庫即時搜尋，撳一下就揀實（有座標）。 */}
          <CityPicker value={form.destination}
            placeholder="目的地（打中文／英文，撳一下揀）"
            onChange={v => setForm(f => ({ ...f, destination: v }))}
            onPick={r => setForm(f => ({ ...f, destination: r.query }))} />

          {/* ══════════════════════════════════════════════════════
              多城市清單（用戶要求）
              ══════════════════════════════════════════════════════
              ⚠️ 用戶原話：
                「新增旅程嘅時候…應該有一個 button 俾你去加城市，
                 而唔係當你去編輯嘅時候先至可以加新增多於一個城市，
                 而係你一開行程就已經有得加多於一個城市。」

              ⚠️ 為咩要擺喺**建立**而唔係編輯：
                用戶喺心入面已經知去邊幾個城市（福岡 → 由布院 → 熊本），
                佢想一次過講晒。要佢建立完再入 Planner 撳三層先加到
                第二個城市 → 佢會以為「唔支援多城市」。
              */}
          <div>
            <div className="sub" style={{
              fontSize: 10.5, marginBottom: 6, fontWeight: 700,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span>去邊幾個城市</span>
              <span style={{ opacity: .6, fontWeight: 400 }}>
                （唔加就淨係用上面嗰個目的地）
              </span>
            </div>

            {/* 已加嘅城市 */}
            {cities.map((c, i) => (
              <div key={c.city} style={{
                display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8,
                paddingLeft: 10,
                borderLeft: `3px solid ${STOP_COLORS[i % STOP_COLORS.length]}`,
              }}>
                <span className="mono" style={{
                  fontSize: 10, flex: '0 0 20px',
                  color: STOP_COLORS[i % STOP_COLORS.length],
                }}>{i + 1}</span>
                <span style={{ flex: 1, fontWeight: 700, fontSize: 13.5, minWidth: 0,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.city}
                </span>
                <input className="input" type="number" min="1" max="60" value={c.days}
                  onChange={e => setCityDays(i, e.target.value)}
                  style={{ width: 62, textAlign: 'center', fontWeight: 700 }} />
                <span className="sub" style={{ fontSize: 11 }}>日</span>
                <button className="btn sm ghost"
                  style={{ padding: '6px 9px', fontSize: 12 }}
                  onClick={() => removeCityRow(i)}>✕</button>
              </div>
            ))}

            {/* 加城市 */}
            <div className="row" style={{ gap: 7 }}>
              <CityPicker value={newCity} placeholder="加城市（打中文／英文）"
                onChange={setNewCity}
                onPick={r => { addCityRow(r.query); setNewCity('') }} />
              <button className="btn" onClick={() => { addCityRow(newCity); setNewCity('') }}>
                ＋ 加
              </button>
            </div>

            {cities.length > 0 && (
              <div className="sub" style={{ fontSize: 10.5, marginTop: 7, lineHeight: 1.75 }}>
                共 <b>{cities.length}</b> 個城市 · <b>{cityDays}</b> 日
                {form.destination && cities[0]?.city !== form.destination && (
                  <> · 目的地會用「{cities[0].city}」</>
                )}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <div className="sub" style={{ fontSize: 10.5, marginBottom: 4, fontWeight: 700 }}>出發</div>
              <input className="input" type="date" value={form.start_date}
                onChange={e => onStartChange(e.target.value)} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="sub" style={{ fontSize: 10.5, marginBottom: 4, fontWeight: 700 }}>回程</div>
              <input className="input" type="date" value={form.end_date} min={form.start_date || undefined}
                onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} />
            </div>
          </div>

          {/* 天數快捷 */}
          <div>
            <div className="sub" style={{ fontSize: 10.5, marginBottom: 6, fontWeight: 700 }}>
              日數 {days ? `· 共 ${days} 日` : '（揀咗日期就自動計）'}
            </div>
            <div className="chips">
              {[2, 3, 4, 5, 7, 10].map(n => (
                <button key={n} className={`chip ${days === n ? 'on' : ''}`}
                  onClick={() => setLength(n)} disabled={!form.start_date}
                  style={!form.start_date ? { opacity: .45 } : undefined}>{n} 日</button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 7 }}>
            <button className="btn primary" style={{ flex: 1 }} onClick={submit} disabled={busy}>
              {busy ? <Spinner /> : (view === 'edit' ? '儲存' : '建立旅程')}
            </button>
            <button className="btn ghost" onClick={reset}>取消</button>
          </div>
          {view === 'edit' && (
            <button className="btn wide ghost" style={{ color: 'var(--bad)', marginTop: 4 }}
              onClick={async () => {
                if (!confirm(`確定刪除「${editing.name}」？所有收藏都會一齊消失。`)) return
                try { await api.deleteTrip(editing.id); toast('已刪除旅程'); reset(); await onRefresh() }
                catch (e) { toast(e.message) }
              }}>刪除旅程</button>
          )}
        </div>
      )}

      {view === 'join' && (
        <div className="card glow col" style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 800, fontSize: 13 }}>用邀請碼加入</div>
          <input className="input mono" placeholder="6 位邀請碼" value={code}
            style={{ textTransform: 'uppercase', letterSpacing: 6, fontWeight: 900, textAlign: 'center', fontSize: 18 }}
            onChange={e => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))}
            onKeyDown={e => e.key === 'Enter' && join()} />
          <div style={{ display: 'flex', gap: 7 }}>
            <button className="btn primary" style={{ flex: 1 }} onClick={join} disabled={busy}>
              {busy ? <Spinner /> : '加入'}
            </button>
            <button className="btn ghost" onClick={reset}>取消</button>
          </div>
        </div>
      )}

      <div style={{ height: 14 }} />

      {trips.length === 0 && !view && (
        <Empty icon="🗂" title="仲未有旅程" hint="撳「＋ 新旅程」開一個，再邀請朋友加入" />
      )}

      {trips.map(t => {
        const cd = countdownText(t)
        const count = t.item_count || 0
        const members = t.member_count || 0
        return (
          <div key={t.id} className="card tap" onClick={() => onOpen(t.id)}
            style={{ marginBottom: 10, position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute', inset: 0, opacity: .28, pointerEvents: 'none',
              background: 'radial-gradient(circle at 86% 8%, var(--neon), transparent 55%), radial-gradient(circle at 4% 96%, var(--cyan), transparent 55%)',
            }} />
            <div style={{ position: 'relative' }}>
              <div className="row" style={{ alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 7, alignItems: 'center' }}>
                    <div style={{ fontWeight: 900, fontSize: 16.5 }}>{t.name}</div>
                    {/* ⚠️ 標示「當前旅程」——
                        用戶撳「‹ 旅程」入嚟嗰陣要一眼睇到
                        自己而家喺邊個旅程（唔係退出咗）。 */}
                    {currentId === t.id && (
                      <span className="chip" style={{
                        fontSize: 9.5, color: 'var(--neon)',
                        borderColor: 'var(--neon)',
                      }}>✓ 當前</span>
                    )}
                  </div>
                  <div className="sub" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
                    {t.destination && <span>📍 {t.destination}</span>}
                    <span>🗓 {tripLength(t)} 日</span>
                    <span>👥 {members}</span>
                    <span>✦ {count} 個收藏</span>
                  </div>
                  {dateRangeText(t) && (
                    <div className="mono sub" style={{ fontSize: 10.5, marginTop: 4 }}>
                      {dateRangeText(t)}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                  {cd && (
                    <span className="conf hi" style={{ fontSize: 8 }}>{cd}</span>
                  )}
                  <button className="btn sm ghost" onClick={e => openEdit(t, e)} style={{ fontSize: 10 }}>
                    編輯
                  </button>
                </div>
              </div>

              <div style={{
                height: 3, background: 'var(--surface-3)', borderRadius: 99,
                marginTop: 11, overflow: 'hidden',
              }}>
                <i style={{
                  display: 'block', height: '100%',
                  width: `${Math.min(100, count * 8)}%`,
                  background: 'var(--grad)', borderRadius: 99,
                }} />
              </div>

              <div className="mono sub" style={{ marginTop: 8, fontSize: 10, opacity: .75 }}>
                邀請碼 {t.invite_code}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
