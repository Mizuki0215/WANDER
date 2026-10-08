import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import Avatar from './Avatar'
import { readForQr } from '../lib/image'
import { isSelf, SELF_MSG, SELF_HINT } from '../lib/selfcheck'
import { toast, Empty, Spinner } from '../lib/ui'

/**
 * 朋友 / 邀請
 *
 * ⚠️ 核心設計：**加朋友要對方 accept**。
 *    · 發請求 → 對方收到「待確認」→ accept 之後**雙方**清單都更新
 *    · 如果對方已經向我發過請求，我一發就自動互相加（唔使等）
 *    · 行程邀請都一樣要 accept（唔可以無聲無息塞個 trip 俾人）
 */
export default function Friends({ trip, me, onRefresh, onTripsChanged, prefill, onPrefillDone }) {
  const [data, setData] = useState({ friends: [], incoming: [], outgoing: [] })
  const [email, setEmail] = useState('')
  const [note, setNote] = useState('')
  const [inviting, setInviting] = useState(false)
  const [uname, setUname] = useState('')
  const [found, setFound] = useState(null)
  const lookupTimer = useRef(null)
  const qrFileRef = useRef(null)
  const [qrScan, setQrScan] = useState(false)
  const [invites, setInvites] = useState([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [f, i] = await Promise.all([api.friends(), api.invites()])
      setData(f)
      setInvites(i.invites || [])
    } catch (e) { toast(e.message) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // 由 QR 連結嚟嘅 @名 → 自動查 + 預填
  useEffect(() => {
    if (!prefill) return
    checkName(prefill)
    onPrefillDone?.()
  }, [prefill])   // eslint-disable-line

  /**
   * 加朋友（用 @帳號名，唔使 email）。
   *
   * ⚠️ 為咩改用 @帳號名：
   *   · 唔使記人哋 email（私隱 + 難記）
   *   · email 邀請要對方收信、撳連結、再註冊 → 3 步
   *   · @名 一打就搵到，而且有 lookup 預覽（睇下係唔係嗰個人）
   *
   * 三種結果：
   *   pending         對方收到請求，等佢 accept
   *   accepted_mutual 對方之前請求過你 → 即刻互相加
   *   already_friends / already_pending
   */
  async function send() {
    const u = uname.trim().replace(/^@/, '')
    if (!u) return toast('請輸入對方嘅 @帳號名')
    setBusy(true)
    try {
      const r = await api.requestFriendByName(u)
      const msg = {
        pending: `請求已送出畀 @${u} ✓ 等對方確認`,
        accepted_mutual: `@${u} 之前請求過你 → 已自動成為朋友 ✓`,
        already_pending: `已經送過請求畀 @${u}`,
        already_friends: `你哋已經係朋友`,
      }[r.status] || '已處理'
      toast(msg)
      setUname(''); setFound(null)
      await load()
    } catch (e) { toast(e.message) } finally { setBusy(false) }
  }

  /**
   * 打字時查下 @名 有冇人用（即時預覽）。
   *
   * ⚠️⚠️ 打自己個 @名 都要即刻話你知 ——
   *    唔好等撳「加」先由後端回 400。
   */
  async function checkName(v) {
    const u = v.trim().replace(/^@/, '')
    setUname(v)
    setFound(null)
    // ⚠️⚠️ 打自己個 @名 → 即刻話你知，唔好等撳「加」
    //    先由後端回 400。用戶要求：「唔可以加自己做朋友」。
    if (isSelf(u, me)) {
      setFound({ username: u, display_name: SELF_MSG, self: true })
      return
    }
    if (u.length < 3 || lookupTimer.current) clearTimeout(lookupTimer.current)
    if (u.length < 3) return
    lookupTimer.current = setTimeout(async () => {
      try {
        const r = await api.lookupUser(u)
        setFound(r.is_self ? { ...r.user, self: true } : r.user)
      } catch { setFound(null) }
    }, 320)
  }

  /** 上傳一張 QR 圖 → 後端解 → 自動填入 @名。 */
  async function scanQrPic(e) {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    setQrScan(true)
    try {
      const img = await readForQr(f)
      const r = await api.decodeQr(img.data)
      if (!r.username) {
        toast(r.text ? `解到「${r.text.slice(0, 26)}」但唔係 Wander QR` : '搵唔到 QR Code')
        return
      }

      // ⚠️⚠️ 掃到自己 —— 用戶要求要話「唔可以加自己做朋友」
      if (isSelf(r.username, me)) {
        setFound({ username: r.username, display_name: SELF_MSG, self: true, selfHit: true })
        toast(`⚠️ ${SELF_MSG}`)
        return
      }

      await checkName(r.username)
      toast(`搵到 @${r.username} ✓`)
    } catch (err) { toast(err.message) }
    finally { setQrScan(false) }
  }

  async function acceptFriend(req) {
    try {
      await api.acceptFriend(req.request_id)
      toast(`已同 ${req.display_name || req.email} 成為朋友 ✓`)
      await load()
    } catch (e) { toast(e.message) }
  }
  async function rejectFriend(req) {
    try {
      await api.rejectFriend(req.request_id)
      toast('已拒絕')
      await load()
    } catch (e) { toast(e.message) }
  }
  async function removeFriend(f) {
    if (!confirm(`刪除好友「${f.display_name || f.email}」？`)) return
    try { await api.removeFriend(f.id); toast('已刪除好友'); await load() }
    catch (e) { toast(e.message) }
  }

  async function inviteToTrip(f) {
    if (!trip) return
    try {
      const r = await api.inviteToTrip(trip.id, f.email)
      toast(r.status === 'already_member'
        ? '對方已經喺呢個旅程'
        : `已邀請 ${f.display_name || f.email}，等對方確認 ✓`)
      await onRefresh?.()
    } catch (e) { toast(e.message) }
  }

  async function handleInvite(inv, accept) {
    try {
      if (accept) {
        const r = await api.acceptInvite(inv.invite_id)
        toast(`已加入「${r.trip?.name || inv.trip_name}」✓`)
        await onTripsChanged?.()
      } else {
        await api.rejectInvite(inv.invite_id)
        toast('已拒絕邀請')
      }
      await load()
    } catch (e) { toast(e.message) }
  }

  async function copy(text, label) {
    try { await navigator.clipboard.writeText(text); toast(`${label} 已複製 ✓`) }
    catch { prompt('手動複製：', text) }
  }

  const memberIds = new Set((trip?.members || []).map(m => m.id))
  const inviteUrl = trip ? `${window.location.origin}/join/${trip.invite_code}` : ''

  return (
    <div className="screen">
      <div className="h1">朋友</div>
      <div className="sub">加朋友要對方確認；邀請入旅程都一樣</div>

      {trip && (
        <div className="card glow" style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 700, fontSize: 12.5 }}>🔗 分享「{trip.name}」邀請 link</div>
          <div className="mono sub" style={{ fontSize: 10, marginTop: 5, wordBreak: 'break-all' }}>
            {inviteUrl}
          </div>
          <div className="sub" style={{ fontSize: 10.5, marginTop: 6 }}>
            對方撳 link 就即刻加入（唔使確認）
          </div>
          <div style={{ display: 'flex', gap: 7, marginTop: 10, flexWrap: 'wrap' }}>
            <button className="btn sm" onClick={() => copy(inviteUrl, 'Link')}>複製 link</button>
            <button className="btn sm ghost" onClick={() => copy(trip.invite_code, '邀請碼')}>
              邀請碼 {trip.invite_code}
            </button>
          </div>
        </div>
      )}

      {/* ═══ 待處理行程邀請 ═══ */}
      {invites.length > 0 && (
        <>
          <div className="sec">行程邀請 · {invites.length}</div>
          {invites.map(inv => (
            <div key={inv.invite_id} className="card"
              style={{ marginBottom: 8, borderColor: 'var(--neon)' }}>
              <div style={{ fontWeight: 800, fontSize: 13.5 }}>{inv.trip_name}</div>
              <div className="sub" style={{ fontSize: 11, marginTop: 3 }}>
                {inv.from_name || inv.from_email} 邀請你加入
                {inv.destination ? ` · 📍 ${inv.destination}` : ''}
              </div>
              <div style={{ display: 'flex', gap: 7, marginTop: 10 }}>
                <button className="btn sm primary" onClick={() => handleInvite(inv, true)}>接受</button>
                <button className="btn sm ghost" onClick={() => handleInvite(inv, false)}>拒絕</button>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ═══ 待確認好友請求 ═══ */}
      {data.incoming.length > 0 && (
        <>
          <div className="sec">好友請求 · {data.incoming.length}</div>
          {data.incoming.map(r => (
            <div key={r.request_id} className="card"
              style={{ marginBottom: 8, borderColor: 'var(--neon)' }}>
              <div className="row">
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 0 }}>
                  <span style={{ fontSize: 20 }}>{r.avatar || '🙂'}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>{r.display_name || r.email}</div>
                    <div className="sub" style={{ fontSize: 11 }}>{r.email}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn sm primary" onClick={() => acceptFriend(r)}>接受</button>
                  <button className="btn sm ghost" onClick={() => rejectFriend(r)}>拒絕</button>
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ═══ 加朋友（@帳號名 + QR）═══ */}
      <div className="sec">加朋友</div>
      <div className="card glow">
        <div className="row" style={{ gap: 7 }}>
          <span className="mono" style={{ fontSize: 16, color: 'var(--cyan)', flex: '0 0 auto' }}>@</span>
          <input className="input" placeholder="對方嘅帳號名（例如 alice_99）"
            value={uname}
            onChange={e => checkName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
            style={{ flex: 1 }} />
          <button className="btn primary" onClick={send} disabled={busy}>
            {busy ? <Spinner /> : '加'}
          </button>
        </div>

        {/* 即時預覽：睇下係唔係嗰個人 */}
        {found && (
          <div className="card" style={{
            marginTop: 10, padding: 10, background: 'var(--surface-2)',
            borderColor: found.self ? 'var(--warn)' : 'var(--good)',
          }}>
            <div className="row" style={{ alignItems: 'center', gap: 10 }}>
              <Avatar id={found.avatar} size={38} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: 13 }}>
                  {found.display_name || `@${found.username}`}
                </div>
                <div className="mono sub" style={{ fontSize: 11 }}>@{found.username}</div>
              </div>
              {found.self ? (
                <span className="chip" style={{ color: 'var(--warn)', borderColor: 'var(--warn)' }}>
                  ⚠️ 係你自己
                </span>
              ) : (
                <button className="btn sm" onClick={send} disabled={busy}>加好友</button>
              )}
            </div>
            {/* ⚠️ 用戶要求：掃到自己要明確講「唔可以加自己做朋友」*/}
            {found.self && (
              <div className="sub" style={{
                fontSize: 11, marginTop: 8, color: 'var(--warn)', lineHeight: 1.8,
              }}>
                <b>{SELF_MSG}</b>
                <br />
                {SELF_HINT}。將你嘅 QR 畀<b>朋友</b>掃，
                或者叫佢喺佢部機打你嘅 @名。
              </div>
            )}
          </div>
        )}
        {!found && uname.trim().length >= 3 && (
          <div className="sub" style={{ fontSize: 10.5, marginTop: 8, color: 'var(--dim)' }}>
            搵唔到 @{uname.trim().replace(/^@/, '')}
          </div>
        )}

        {/* 掃 QR */}
        <input ref={qrFileRef} type="file" accept="image/*"
          onChange={scanQrPic} style={{ display: 'none' }} />
        <button className="btn wide" style={{ marginTop: 10 }}
          onClick={() => qrFileRef.current?.click()} disabled={qrScan}>
          📷 {qrScan ? '解碼緊…' : '掃 QR Code（揀一張圖）'}
        </button>
        <div className="sub" style={{ fontSize: 10.5, marginTop: 9, lineHeight: 1.8 }}>
          💡 唔想打 @名？叫對方開佢嘅「我嘅 QR」（設定頁）→ 你影低或者截圖
          → 撳上面「掃 QR Code」揀嗰張圖 → 自動填返 @名。
        </div>
      </div>

      {/* ═══ 已送出 ═══ */}
      {data.outgoing.length > 0 && (
        <>
          <div className="sec">等對方確認 · {data.outgoing.length}</div>
          {data.outgoing.map(r => (
            <div key={r.request_id} className="item" style={{ alignItems: 'center' }}>
              <Avatar id={r.avatar} size={38} />
              <div className="info">
                <h4>{r.display_name || r.email}</h4>
                <p>{r.email}</p>
              </div>
              <span className="chip" style={{ color: 'var(--warn)', borderColor: 'var(--warn)' }}>
                待確認
              </span>
            </div>
          ))}
        </>
      )}

      {/* ═══ 旅程成員 ═══ */}
      {trip && (trip.members || []).length > 0 && (
        <>
          <div className="sec">喺「{trip.name}」 · {trip.members.length}</div>
          {trip.members.map(m => (
            <div key={m.id} className="item" style={{ alignItems: 'center' }}>
              <Avatar id={m.avatar} size={38} />
              <div className="info">
                <h4>{m.display_name || m.email}</h4>
                <p>{m.email}</p>
              </div>
              <span className={`chip ${m.role === 'owner' ? 'on' : ''}`}>{m.role}</span>
            </div>
          ))}
        </>
      )}

      {/* ═══ 我嘅朋友 ═══ */}
      <div className="sec">我嘅朋友 · {data.friends.length}</div>
      {loading ? (
        <div className="sub" style={{ padding: 12 }}><Spinner /> 載入中…</div>
      ) : data.friends.length === 0 ? (
        <Empty icon="👥" title="仲未有朋友"
          hint="上面輸入對方 email 送出請求，等對方撳「接受」" />
      ) : data.friends.map(f => {
        const already = trip ? memberIds.has(f.id) : true
        return (
          <div key={f.id} className="item" style={{ alignItems: 'center' }}>
            <Avatar id={f.avatar} size={38} />
            <div className="info">
              <h4>{f.display_name || f.email}</h4>
              <p>{f.email}</p>
            </div>
            <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
              {trip && (already
                ? <span className="chip on">已加入</span>
                : <button className="btn sm" onClick={() => inviteToTrip(f)}>邀請入旅程</button>)}
              <button className="btn sm ghost" style={{ fontSize: 10, padding: '6px 8px' }}
                onClick={() => removeFriend(f)}>✕</button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
