import { useEffect, useMemo, useState } from 'react'
import PixelIcon from './PixelIcon'
import { api } from '../lib/api'
import { toast, Empty } from '../lib/ui'

/**
 * 分帳（Settlement）
 * ==================
 * 用戶要求（原文）：
 *   「同程 做一個 function like sette uppp。咁 計錢」
 *
 * 一班人去旅行，有人墊支，最後要計返邊個俾返幾多俾邊個。
 *
 * ⚠️ 為咩唔用 AI：
 *   分帳係**算術**。1 + 1 = 2，唔需要「理解」。
 *   用 AI 做算術係災難 —— 會出現「大概 $523 左右」，
 *   但分帳要**準確到仙**（差一蚊都會嘈交）。
 *
 * ⚠️ 核心價值係「最少轉帳次數」：
 *   4 個人互相欠，逐對計要 6 次轉帳；但實際 3 次就搞掂。
 *   呢個慳到嘅係時間同尷尬。
 */

const CATS = [
  // ⚠️ 唔再用 emoji —— 用像素圖示（`icon` 係 pixelicons 嘅 key）
  { k: 'food', label: '食', icon: 'food' },
  { k: 'transport', label: '交通', icon: 'transport' },
  { k: 'stay', label: '住宿', icon: 'hotel' },
  { k: 'ticket', label: '門票', icon: 'ticket' },
  { k: 'shop', label: '購物', icon: 'shopping' },
  { k: 'other', label: '✦ 其他' },
]

export default function Settlement({ trip, user, onRefresh }) {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = async () => {
    try { setData(await api.listExpenses(trip.id)) }
    catch (e) { toast(e.message) }
  }
  useEffect(() => { if (trip?.id) load() }, [trip?.id])   // eslint-disable-line

  const st = data?.settlement
  const symbol = data?.symbol || '$'
  const me = user?.display_name || user?.email

  async function remove(id) {
    if (!confirm('刪除呢筆開支？')) return
    try { await api.deleteExpense(id); toast('已刪除'); await load() }
    catch (e) { toast(e.message) }
  }

  return (
    <div>
      {/* ── 總額 ── */}
      <div className="card glow" style={{ padding: 14 }}>
        <div className="sub" style={{ fontSize: 11 }}>總開支</div>
        <div className="mono" style={{ fontSize: 26, fontWeight: 900, marginTop: 3 }}>
          {st?.total_text || `${symbol}0.00`}
        </div>
        <div className="sub" style={{ fontSize: 11, marginTop: 5 }}>
          {st?.count || 0} 筆 · {(data?.members || []).length} 人
          {me && <span> · 你係 {me}</span>}
        </div>
        {st?.per_category_labels && Object.keys(st.per_category_labels).length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
            {Object.entries(st.per_category_labels).map(([k, v]) => (
              <span key={k} className="chip" style={{ fontSize: 10 }}>
                {k} {symbol}{Number(v).toLocaleString()}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ══ 你嘅狀況（最大嗰個 corner）══ */}
      {me && st && (() => {
        const my = st.shares.find(x => x.person === me)
        if (!my) return null
        const win = my.net > 0
        return (
          <div className="card" style={{
            marginTop: 12, padding: 15,
            borderColor: my.net === 0 ? 'var(--border)' : win ? 'var(--good)' : 'var(--bad)',
            borderWidth: 2,
            background: my.net === 0 ? 'var(--surface)'
              : win ? 'color-mix(in srgb, var(--good) 10%, var(--surface))'
                    : 'color-mix(in srgb, var(--bad) 10%, var(--surface))',
          }}>
            <div className="sub" style={{ fontSize: 10.5, letterSpacing: 1 }}>
              你嘅狀況
            </div>
            <div className="mono" style={{
              fontSize: 'clamp(22px, 6.6vw, 28px)', fontWeight: 900, marginTop: 5,
              color: my.net === 0 ? 'var(--dim)' : win ? 'var(--good)' : 'var(--bad)',
            }}>
              {my.net === 0 ? '打和' : `${win ? '應收' : '應俾'} ${symbol}${Math.abs(my.net).toLocaleString()}`}
            </div>
            <div className="sub" style={{ fontSize: 11, marginTop: 6, lineHeight: 1.8 }}>
              你墊支咗 {my.paid_text} · 你應該分擔 {my.owes_text}
            </div>
          </div>
        )
      })()}

      <button className="btn primary wide" style={{ marginTop: 12 }}
        onClick={() => { setEditing(null); setOpen(true) }}>
        ＋ 加一筆開支
      </button>

      {/* ── 每人結算 ── */}
      {(st?.shares || []).length > 0 && (
        <>
          <div className="sec">每人結算</div>
          {st.shares.map(s => (
            <div key={s.person} className="card" style={{ marginBottom: 7 }}>
              <div className="row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 800, fontSize: 13 }}>
                    {s.person}
                    {s.person === me && (
                      <span className="sub" style={{ fontSize: 10, marginLeft: 6 }}>（你）</span>
                    )}
                  </div>
                  <div className="sub" style={{ fontSize: 10.5, marginTop: 3 }}>
                    墊支 {s.paid_text} · 應付 {s.owes_text}
                  </div>
                </div>
                <div className="mono" style={{
                  fontWeight: 900, fontSize: 13.5,
                  color: s.net > 0 ? 'var(--good)' : s.net < 0 ? 'var(--bad)' : 'var(--dim)',
                }}>
                  {s.net > 0 ? `收 ${s.net_text}` : s.net < 0 ? `俾 ${s.net_text}` : '打和'}
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ── 最少轉帳 ── */}
      {(st?.transfers || []).length > 0 && (
        <>
          <div className="sec">
            💸 邊個要比錢邊個 · {st.transfer_count} 次
          </div>
          <div className="sub" style={{ fontSize: 11, marginBottom: 8, lineHeight: 1.7 }}>
            如果逐對計要 {(data.members || []).length * ((data.members || []).length - 1) / 2} 次，
            但其實 <b style={{ color: 'var(--cyan)' }}>{st.transfer_count} 次</b> 就搞掂 ✓
          </div>
          {st.transfers.map((t, i) => (
            <div key={i} className="card" style={{
              marginBottom: 7,
              borderColor: t.to === me || t.from === me ? 'var(--border-hi)' : 'var(--border)',
              boxShadow: t.to === me || t.from === me ? 'var(--glow)' : 'none',
            }}>
              <div className="row">
                <span style={{ fontWeight: 800, fontSize: 13 }}>{t.from}</span>
                <span style={{ color: 'var(--cyan)', fontSize: 15 }}>→</span>
                <span style={{ fontWeight: 800, fontSize: 13 }}>{t.to}</span>
                <div style={{ flex: 1 }} />
                <span className="mono" style={{ fontWeight: 900, fontSize: 14, color: 'var(--cyan)' }}>
                  {t.amount_text}
                </span>
              </div>
              {(t.from === me || t.to === me) && (
                <div className="sub" style={{ fontSize: 10, marginTop: 5 }}>
                  {t.from === me ? '你要俾呢筆' : '你要收呢筆'}
                </div>
              )}
            </div>
          ))}
        </>
      )}

      {/* ── 開支清單 ── */}
      <div className="sec">開支記錄</div>
      {!data?.expenses?.length ? (
        <Empty icon="💸" title="仲未有開支"
          hint="有人墊支就記落嚟，最後自動計返邊個俾幾多" />
      ) : (
        data.expenses.map(e => (
          <div key={e.id} className="item" style={{ cursor: 'default' }}>
            <div className="ic" style={{ fontSize: 17 }}>
              {(CATS.find(c => c.k === e.category)?.label || '✦').split(' ')[0]}
            </div>
            <div className="info">
              <h4>{e.title}</h4>
              <p>
                {e.payer} 墊支 · {(e.participants || []).length} 人分
                {e.day_index ? ` · Day ${e.day_index}` : ''}
              </p>
              <p style={{ fontSize: 10, marginTop: 2 }}>
                {(e.participants || []).join('、')}
              </p>
            </div>
            <div style={{ textAlign: 'right', flex: '0 0 auto' }}>
              <div className="mono" style={{ fontWeight: 900, fontSize: 13 }}>
                {symbol}{Number(e.amount).toLocaleString()}
              </div>
              <div style={{ display: 'flex', gap: 4, marginTop: 6, justifyContent: 'flex-end' }}>
                <button className="btn sm ghost" style={{ padding: '3px 7px', fontSize: 10 }}
                  onClick={() => { setEditing(e); setOpen(true) }}>改</button>
                <button className="btn sm ghost" style={{ padding: '3px 7px', fontSize: 10 }}
                  onClick={() => remove(e.id)}>✕</button>
              </div>
            </div>
          </div>
        ))
      )}

      {open && (
        <ExpenseSheet
          trip={trip}
          members={data?.members || []}
          symbol={symbol}
          me={me}
          editing={editing}
          onClose={() => setOpen(false)}
          onSaved={async () => { setOpen(false); await load(); onRefresh?.() }}
        />
      )}
    </div>
  )
}

/** 加／改一筆開支。 */
function ExpenseSheet({ trip, members, symbol, me, editing, onClose, onSaved }) {
  const [title, setTitle] = useState(editing?.title || '')
  const [amount, setAmount] = useState(editing?.amount ?? '')
  const [payer, setPayer] = useState(editing?.payer || me || members[0] || '')
  const [parts, setParts] = useState(
    editing?.participants?.length ? editing.participants : (members.length ? members : [me]))
  const [category, setCategory] = useState(editing?.category || 'food')
  const [note, setNote] = useState(editing?.note || '')
  const [busy, setBusy] = useState(false)

  const all = members.length ? members : [me]
  const per = useMemo(() => {
    const n = Number(amount)
    if (!n || !parts.length) return null
    return n / parts.length
  }, [amount, parts])

  function toggle(p) {
    setParts(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p])
  }

  async function save() {
    if (!title.trim()) return toast('請填項目名稱')
    const amt = Number(amount)
    if (!amt || amt <= 0) return toast('金額要大過 0')
    if (!parts.length) return toast('揀返邊幾個分')
    setBusy(true)
    try {
      const body = { title: title.trim(), amount: amt, payer, participants: parts, category, note }
      if (editing) await api.updateExpense(editing.id, body)
      else await api.addExpense(trip.id, body)
      toast(editing ? '已更新 ✓' : '已加入 ✓')
      await onSaved()
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 90, background: 'rgba(0,0,0,.68)',
      backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'flex-end',
    }}>
      <div onClick={e => e.stopPropagation()} className="card" style={{
        width: '100%', maxWidth: 640, margin: '0 auto', maxHeight: '90vh', overflowY: 'auto',
        borderRadius: 'var(--r) var(--r) 0 0', borderColor: 'var(--border-hi)',
        paddingBottom: 'calc(20px + var(--safe-b))',
      }}>
        <div className="row" style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 900, fontSize: 15 }}>
            {editing ? '改開支' : '加一筆開支'}
          </div>
          <button className="btn sm ghost" onClick={onClose}>✕</button>
        </div>

        <div className="sec" style={{ marginTop: 4 }}>項目</div>
        <input className="input" value={title} placeholder="例：一蘭拉麵"
          onChange={e => setTitle(e.target.value)} autoFocus />

        <div className="sec">金額</div>
        <div className="row" style={{ gap: 8 }}>
          <input className="input" type="number" inputMode="decimal" min="0" step="1"
            value={amount} placeholder="0"
            onChange={e => setAmount(e.target.value)} style={{ flex: 1 }} />
          {per != null && (
            <span className="sub" style={{ fontSize: 11.5, flex: '0 0 auto' }}>
              每人 {symbol}{per.toFixed(2)}
            </span>
          )}
        </div>

        <div className="sec">邊個墊支</div>
        <div className="chips">
          {all.map(p => (
            <button key={p} className={`chip ${payer === p ? 'on' : ''}`}
              onClick={() => setPayer(p)}>{p}</button>
          ))}
        </div>

        <div className="row" style={{ marginTop: 4 }}>
          <div className="sec" style={{ flex: 1, margin: 0 }}>邊幾個分（{parts.length}）</div>
          <button className="btn sm ghost" style={{ fontSize: 10 }}
            onClick={() => setParts(parts.length === all.length ? [] : [...all])}>
            {parts.length === all.length ? '全唔揀' : '全揀'}
          </button>
        </div>
        <div className="chips" style={{ marginTop: 7 }}>
          {all.map(p => (
            <button key={p} className={`chip ${parts.includes(p) ? 'on' : ''}`}
              onClick={() => toggle(p)}>{p}</button>
          ))}
        </div>
        <div className="sub" style={{ fontSize: 10.5, marginTop: 6, lineHeight: 1.7 }}>
          冇分嘅人唔使夾呢筆（例如有人冇搭的士）
        </div>

        <div className="sec">分類</div>
        <div className="chips">
          {CATS.map(c => (
            <button key={c.k} className={`chip ${category === c.k ? 'on' : ''}`}
              onClick={() => setCategory(c.k)}>
              {c.icon && <PixelIcon name={c.icon} size={15} />}
              <span>{c.label}</span>
            </button>
          ))}
        </div>

        <div className="sec">備註（可選）</div>
        <input className="input" value={note} placeholder="例：機場巴士"
          onChange={e => setNote(e.target.value)} />

        <button className="btn primary wide" style={{ marginTop: 16 }}
          onClick={save} disabled={busy}>
          {busy ? '儲存緊…' : editing ? '儲存' : '加入'}
        </button>
      </div>
    </div>
  )
}
