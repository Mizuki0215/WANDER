import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { toast, Spinner, Empty } from '../lib/ui'
import PixelIcon from './PixelIcon'

/**
 * 開發版後台（Admin Dashboard）
 * ==============================
 *
 * ⚠️⚠️ 用戶要求：
 *   「我見其實而家整到都差唔多嘅話，其實我覺得另外仲要整一個
 *    叫做開發版，係放我自己睇啲人用呢個 App 嘅數據。」
 *
 * ⚠️ 為咩要「事件」而唔係由現有表反推：
 *   Items / Expenses 只記錄**結果**（加咗 3 個景點），唔記錄**過程**：
 *     · 邊個 app 最多人開？（Planner？Shopping？）
 *     · 用戶登入完有冇真係做嘢？（激活率）
 *     · 邊個功能**開過但冇用**？（= 唔知點用，要改 UI）
 *
 * ⚠️ 私隱原則：
 *   只記「事件類型 + 目標」，**唔記內容**。
 *   最近活動只顯示 email 前 3 個字 + …。
 *
 * ⚠️ 冇圖表 library —— 用純 CSS bar。
 *   加一個 chart library 落 bundle 唔值（呢頁只有你自己睇）。
 */
export default function Admin({ onBack }) {
  const [days, setDays] = useState(30)
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    setBusy(true); setErr('')
    api.adminOverview(days)
      .then(setD)
      .catch(e => setErr(e.message))
      .finally(() => setBusy(false))
  }, [days])

  if (busy && !d) {
    return (
      <div className="screen no-nav">
        <button className="btn sm ghost" onClick={onBack}>‹ 返去</button>
        <div style={{ marginTop: 30 }}><Spinner /></div>
      </div>
    )
  }

  if (err) {
    return (
      <div className="screen no-nav">
        <button className="btn sm ghost" onClick={onBack}>‹ 返去</button>
        <div className="card" style={{ marginTop: 14, borderColor: 'var(--bad)' }}>
          <div style={{ fontWeight: 900, color: 'var(--bad)' }}>⚠️ 睇唔到後台</div>
          <div className="sub" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.8 }}>
            {err}
            <br />
            ⚠️ 要將你嘅 email 加入 <code>server/.env</code> 嘅
            <code> WANDER_ADMIN_EMAILS</code>，然後重啟 server。
          </div>
        </div>
      </div>
    )
  }

  const u = d.users, a = d.active, c = d.content, e = d.events
  const maxDay = Math.max(1, ...e.by_day.map(x => x.n))
  const maxKind = Math.max(1, ...e.by_kind.map(x => x.n))

  return (
    <div style={{ paddingBottom: 40 }}>
      <div className="screen no-nav" style={{ paddingBottom: 6 }}>
        <button className="btn sm ghost" onClick={onBack}>‹ 返去</button>
        <div style={{ textAlign: 'right', flex: 1 }}>
          <div style={{ fontWeight: 900, fontSize: 15 }}>🛠 開發版後台</div>
          <div className="sub" style={{ fontSize: 10 }}>
            更新於 {fmtTime(d.generated_at)}
          </div>
        </div>
      </div>

      {/* ── 期間切換 ── */}
      <div className="chips" style={{ marginBottom: 12 }}>
        {[7, 14, 30, 90].map(n => (
          <button key={n} className={`chip ${days === n ? 'on' : ''}`}
            onClick={() => setDays(n)}>{n} 日</button>
        ))}
      </div>

      {/* ══ ① 用戶 ══ */}
      <Sec title="👥 用戶">
        <Grid items={[
          ['總數', u.total, ''],
          [`${days} 日新增`, u.new_period, u.new_7d ? `7日 ${u.new_7d}` : ''],
          ['睇過教學', u.onboarded, pct(u.onboarded, u.total)],
          ['設咗密碼', u.with_password, pct(u.with_password, u.total)],
          ['設咗 @名', u.with_username, pct(u.with_username, u.total)],
        ]} />
      </Sec>

      {/* ══ ② 活躍 ══ */}
      <Sec title="⚡ 活躍">
        <Grid items={[
          ['今日活躍', a.dau, 'DAU'],
          ['7 日活躍', a.wau, 'WAU'],
          [`${days} 日活躍`, a.period, '期間'],
          // ⚠️ 黏性 = DAU/WAU。>0.5 代表用戶好常返嚟。
          ['黏性 DAU/WAU', a.wau ? (a.dau / a.wau).toFixed(2) : '—', '>0.5 好'],
          ['有效 session', a.sessions_live, '未過期'],
        ]} />
        {u.total > 0 && (
          <Bar label="激活率（有活動 / 總用戶）"
            value={Math.min(u.total, a.period)} max={u.total}
            text={`${pct(a.period, u.total)}`} />
        )}
      </Sec>

      {/* ══ ③ 內容 ══ */}
      <Sec title="📦 內容">
        <Grid items={[
          ['旅程', c.trips, `${days}日 +${c.trips_period}`],
          ['城市', c.stops, d.distrib.avg_stops ? `平均 ${d.distrib.avg_stops}` : ''],
          ['景點／收藏', c.items, d.distrib.avg_items ? `平均 ${d.distrib.avg_items}` : ''],
          ['開支', c.expenses, ''],
          ['購物項', c.shopping, ''],
          ['多城市旅程', d.distrib.multi_city,
            pct(d.distrib.multi_city, c.trips || 1)],
        ]} />
        {d.distrib.empty_trips > 0 && (
          <div className="sub" style={{ fontSize: 10.5, marginTop: 8, lineHeight: 1.8 }}>
            ⚠️ 有 <b>{d.distrib.empty_trips}</b> 個旅程**一個景點都冇** ——
            可能係建立完唔知跟住做咩，值得睇下。
          </div>
        )}
      </Sec>

      {/* ══ ④ 每日活動 ══ */}
      <Sec title={`📈 每日活動（${days} 日）`}>
        {e.by_day.length === 0
          ? <div className="sub" style={{ fontSize: 11.5 }}>
              仲未有事件 —— 用戶一開 app 就會開始記錄。
            </div>
          : (
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2,
              height: 92, marginTop: 6 }}>
              {e.by_day.map(x => (
                <div key={x.d} title={`${x.d}：${x.n}`}
                  style={{
                    flex: 1, minWidth: 3,
                    height: `${Math.max(4, (x.n / maxDay) * 100)}%`,
                    background: 'linear-gradient(180deg, var(--neon), var(--cyan))',
                    borderRadius: 'var(--r-xs) var(--r-xs) 0 0',
                  }} />
              ))}
            </div>
          )}
        {e.by_day.length > 0 && (
          <div className="sub" style={{ fontSize: 10, marginTop: 6,
            display: 'flex', justifyContent: 'space-between' }}>
            <span>{e.by_day[0].d.slice(5)}</span>
            <span>最高 {maxDay}/日</span>
            <span>{e.by_day[e.by_day.length - 1].d.slice(5)}</span>
          </div>
        )}
      </Sec>

      {/* ══ ⑤ 功能使用 ══ */}
      <Sec title="🎯 邊個功能最多人用">
        {e.by_kind.length === 0
          ? <div className="sub" style={{ fontSize: 11.5 }}>仲未有數據</div>
          : e.by_kind.map(k => (
            <Bar key={k.kind} label={`${KIND_ZH[k.kind] || k.kind}`}
              value={k.n} max={maxKind} text={`${k.n}`} />
          ))}
      </Sec>

      {/* ══ ⑥ 新用戶走勢 ══ */}
      {d.signups.length > 0 && (
        <Sec title="🌱 每日新用戶">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
            {d.signups.map(s => (
              <span key={s.d} className="chip" style={{ fontSize: 10 }}>
                {s.d.slice(5)} · {s.n}
              </span>
            ))}
          </div>
        </Sec>
      )}

      {/* ══ ⑦ 最近活動 ══ */}
      <Sec title="🕐 最近活動（最新 40 條）">
        {d.recent.length === 0
          ? <div className="sub" style={{ fontSize: 11.5 }}>仲未有</div>
          : (
            <div className="mono" style={{ fontSize: 10.5, lineHeight: 2 }}>
              {d.recent.map((r, i) => (
                <div key={i} style={{ display: 'flex', gap: 8,
                  borderBottom: '1px dashed var(--border)', paddingBottom: 3 }}>
                  <span style={{ opacity: .55, flex: '0 0 74px' }}>
                    {fmtTime(r.at).slice(5, 16)}
                  </span>
                  <span style={{ flex: '0 0 42px' }}>{r.who}</span>
                  <span style={{ color: 'var(--cyan)', flex: 1 }}>
                    {KIND_ZH[r.kind] || r.kind}
                    {r.target ? ` · ${r.target}` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
      </Sec>

      {/* ══ ⑧ 註冊邀請碼 ══ */}
      {/*   ⚠️⚠️ 用戶問：「未設定 SMTP 你係諗住點搞？」
              答：冇 SMTP 就寄唔到驗證碼 → 用邀請碼。
              呢個就係產生邀請碼嘅地方。 */}
      <DataManager />

      <MailTest />

      <Invites />

      <div className="sub" style={{ fontSize: 10, marginTop: 16, lineHeight: 1.9 }}>
        ⚠️ 只記錄「事件類型 + 目標」，**唔記錄內容**（睇咗咩、打咗咩）。
        <br />
        ⚠️ 最近活動嘅用戶只顯示 email 前 3 個字。
      </div>
    </div>
  )
}

/**
 * 註冊邀請碼產生器。
 *
 * ⚠️⚠️ 用戶問：「未設定 SMTP 你係諗住點搞？」
 *   答：冇 SMTP 就寄唔到驗證碼 → 用**邀請碼**註冊。
 *   你產生條碼，親手畀朋友，佢用條碼註冊。
 *
 * ⚠️ 為咩邀請碼比 email 驗證更好（朋友之間）：
 *   · 冇成本、冇 rate limit、冇 spam 風險
 *   · 你親手畀條碼 = 你確定佢係邊個（email 只證明佢控制個信箱）
 *   · 一次性 + 有期限 → 流出咗都只可以用一次
 */
function Invites() {
  const [data, setData] = useState(null)
  const [n, setN] = useState(1)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [fresh, setFresh] = useState([])

  const load = () => api.adminInvites().then(setData).catch(() => {})
  useEffect(() => { load() }, [])

  async function gen() {
    setBusy(true)
    try {
      const r = await api.makeInvites(n, note, 30)
      setFresh(r.codes || [])
      setNote('')
      await load()
      toast(`整咗 ${(r.codes || []).length} 個邀請碼 ✓`)
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  const ok = (data?.invites || []).filter(x => x.state === 'ok')

  return (
    <Sec title="🔑 註冊邀請碼">
      <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
        而家模式：<b>{data?.mode === 'invite' ? '要邀請碼' :
          data?.mode === 'email' ? '要 email 驗證碼' : '公開註冊'}</b>
        {ok.length > 0 && <> · 仲有 <b>{ok.length}</b> 個未用</>}
      </div>

      <div className="row" style={{ gap: 8, marginTop: 10 }}>
        <input className="input" type="number" min="1" max="50" value={n}
          onChange={e => setN(e.target.value)}
          style={{ width: 66, textAlign: 'center', fontWeight: 700 }} />
        <input className="input" placeholder="備註（例：阿明）" value={note}
          onChange={e => setNote(e.target.value)} style={{ flex: 1 }} />
        <button className="btn primary" onClick={gen} disabled={busy}>
          {busy ? '…' : '產生'}
        </button>
      </div>

      {/* ⚠️ 啱啱產生嘅要**大字**顯示（可能要抄落紙／WhatsApp 畀人） */}
      {fresh.length > 0 && (
        <div className="card" style={{
          marginTop: 10, borderColor: 'var(--good)', background: 'transparent',
        }}>
          <div className="sub" style={{ fontSize: 10.5, marginBottom: 6 }}>
            ⚠️ 啱啱產生 —— 撳一下複製，跟住畀朋友
          </div>
          {fresh.map(c => (
            <div key={c} className="mono" onClick={() => {
              navigator.clipboard?.writeText(c).then(
                () => toast(`複製咗 ${c} ✓`), () => {})
            }} style={{
              fontSize: 22, fontWeight: 900, letterSpacing: 4,
              textAlign: 'center', padding: '7px 0', cursor: 'pointer',
              borderBottom: '1px dashed var(--border)',
            }}>{c}</div>
          ))}
        </div>
      )}

      {(data?.invites || []).length > 0 && (
        <div className="mono" style={{ fontSize: 10.5, lineHeight: 2, marginTop: 12 }}>
          {(data.invites || []).slice(0, 40).map(x => (
            <div key={x.code} style={{
              display: 'flex', gap: 8, borderBottom: '1px dashed var(--border)',
              opacity: x.state === 'ok' ? 1 : .45,
            }}>
              <span style={{ letterSpacing: 2, fontWeight: 800, flex: '0 0 82px' }}>
                {x.code}
              </span>
              <span style={{ flex: '0 0 46px', color:
                x.state === 'ok' ? 'var(--good)' :
                x.state === 'used' ? 'var(--dim)' : 'var(--warn)' }}>
                {x.state === 'ok' ? '未用' : x.state === 'used' ? '已用' : '過期'}
              </span>
              <span style={{ flex: 1, opacity: .7 }}>{x.note || '—'}</span>
            </div>
          ))}
        </div>
      )}
    </Sec>
  )
}

/**
 * 寄信測試。
 *
 * ⚠️⚠️ 用戶要求：「我係真係想我 email 收到有呢一封嘅 email。」
 *   → 設定完 SMTP 之後，要有一個掣即刻試下。
 *
 * ⚠️ 為咩唔可以「設定咗就當 work」：
 *   Gmail App Password 打錯、或者個 app password 被 revoke、
 *   或者寄件人同帳號唔一致 —— 全部都會**靜靜咁**失敗。
 *   唔試過係唔會知。
 */
function MailTest() {
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)

  useEffect(() => { api.adminMail().then(setSt).catch(() => {}) }, [])

  async function send() {
    setBusy(true); setRes(null)
    try {
      const r = await api.testMail('')
      setRes(r)
      toast(r.sent ? '寄咗！去 check email ✓' : `寄唔到：${r.error || '未知'}`)
    } catch (e) { setRes({ sent: false, error: e.message }) }
    finally { setBusy(false) }
  }

  const ok = st && st.mode !== 'console'

  return (
    <Sec title="📧 寄信" hint={ok ? st.mode : '未設定'}>
      {!ok ? (
        <>
          <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
            ⚠️ <b>未設定寄信</b> —— 而家驗證碼只會印喺 server 嘅 console，
            用戶**收唔到 email**。
          </div>
          <div className="card" style={{ marginTop: 9, background: 'var(--surface-2)' }}>
            <div className="sub mono" style={{ fontSize: 10.5, lineHeight: 2 }}>
              放落 server/.env，然後重啟：<br />
              WANDER_SMTP_HOST=smtp.gmail.com<br />
              WANDER_SMTP_PORT=587<br />
              WANDER_SMTP_USER=你@gmail.com<br />
              WANDER_SMTP_PASS=（16 位 App Password）<br />
              WANDER_MAIL_FROM=你@gmail.com
            </div>
          </div>
          <div className="sub" style={{ fontSize: 10.5, marginTop: 8, lineHeight: 1.8 }}>
            📄 詳細步驟：<code>docs/smtp/README.md</code>
          </div>
        </>
      ) : (
        <>
          <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
            ✅ 已設定（<b>{st.mode}</b>）
            {st.from && <><br />寄件人：{st.from}</>}
          </div>
          <button className="btn primary wide" style={{ marginTop: 10 }}
            onClick={send} disabled={busy}>
            {busy ? '寄緊…' : `寄一封測試信去 ${st.to || '我嘅 email'}`}
          </button>
        </>
      )}

      {res && (
        <div className="sub" style={{
          fontSize: 11, marginTop: 9, lineHeight: 1.8,
          color: res.sent ? 'var(--good)' : 'var(--bad)',
        }}>
          {res.sent
            ? <>✓ 已寄去 <b>{res.to}</b> —— 去 check 收件箱（同 spam）</>
            : <>✗ 寄唔到：{res.error || '未知原因'}</>}
        </div>
      )}
    </Sec>
  )
}

/**
 * 🗄️ 數據管理（用戶要求）
 * ========================
 *
 * ⚠️⚠️ 用戶原話：
 *   「同埋我想有個後台去管理數據喎，你幾時整呀？」
 *
 * ⚠️ 設計原則：
 *   ① **搜尋先** —— 119 個用戶／78 個旅程唔可以一次過列出嚟
 *   ② ⚠️⚠️ **刪除要打名確認** —— 唔可以撳一下就近冇
 *      （我今日已經試過兩次誤刪用戶資料）
 *   ③ ⚠️ **唔可以刪自己** —— 會將自己鎖出後台
 *   ④ 匯出**唔包** `password_hash`
 */
function DataManager() {
  const [tab, setTab] = useState('users')     // users | trips | export
  const [q, setQ] = useState('')
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)
  const [del, setDel] = useState(null)        // {kind, id, name, typed}

  async function load(which = tab, query = q) {
    setBusy(true)
    try {
      setD(which === 'users'
        ? await api.adminUsers(query)
        : which === 'trips' ? await api.adminTrips(query)
        : await api.adminExport('summary'))
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }
  useEffect(() => { load(tab, q) }, [tab])   // eslint-disable-line

  async function doDelete() {
    if (!del) return
    try {
      if (del.kind === 'user') await api.adminDeleteUser(del.id, del.typed)
      else await api.adminDeleteTrip(del.id, del.typed)
      toast(`已刪除「${del.name}」`)
      setDel(null)
      await load()
    } catch (e) { toast(e.message) }
  }

  async function download(what) {
    try {
      const r = await api.adminExport(what)
      const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `wander-${what}-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(a.href)
      toast(`匯出咗 ${r.count ?? ''} 筆`)
    } catch (e) { toast(e.message) }
  }

  return (
    <Sec title="🗄️ 數據管理">
      {/* ⚠️ 分頁 */}
      <div className="chips" style={{ marginBottom: 10 }}>
        {[['users', '👥 用戶'], ['trips', '🗂 旅程'], ['export', '📤 匯出']]
          .map(([k, label]) => (
            <button key={k} className={`chip ${tab === k ? 'on' : ''}`}
              style={{ fontSize: 11 }} onClick={() => setTab(k)}>{label}</button>
          ))}
      </div>

      {tab !== 'export' && (
        <div className="row" style={{ gap: 7, marginBottom: 10 }}>
          <input className="input" value={q} style={{ flex: 1 }}
            placeholder={tab === 'users' ? '搵 email / 帳號名 / 名' : '搵旅程名 / 目的地'}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load()} />
          <button className="btn sm" onClick={() => load()} disabled={busy}>
            {busy ? '…' : '搵'}
          </button>
        </div>
      )}

      {/* ══ 匯出 ══ */}
      {tab === 'export' && (
        <>
          <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
            ⚠️ 匯出係 JSON。**唔會**包含密碼 hash。
          </div>
          <div className="row" style={{ gap: 7, marginTop: 10, flexWrap: 'wrap' }}>
            {[['users', '👥 用戶'], ['trips', '🗂 旅程'],
              ['items', '📍 景點'], ['summary', '📊 統計']]
              .map(([k, label]) => (
                <button key={k} className="btn sm" onClick={() => download(k)}>
                  {label}
                </button>
              ))}
          </div>
          {d?.counts && (
            <div className="mono sub" style={{ fontSize: 11, marginTop: 12, lineHeight: 2 }}>
              {Object.entries(d.counts).map(([k, v]) =>
                <div key={k}>{k}: {v}</div>)}
            </div>
          )}
        </>
      )}

      {/* ══ 用戶 ══ */}
      {tab === 'users' && d?.users && (
        <>
          <div className="sub" style={{ fontSize: 10.5, marginBottom: 6 }}>
            共 {d.total} 個 · 顯示 {d.users.length}
          </div>
          {d.users.map(u => (
            <div key={u.id} className="item" style={{ alignItems: 'center' }}>
              <div className="ic">{u.avatar || '🙂'}</div>
              <div className="info">
                <h4>{u.display_name || u.email}
                  {u.is_admin ? <span className="chip" style={{ fontSize: 9, marginLeft: 5 }}>admin</span> : null}
                </h4>
                <p className="mono" style={{ fontSize: 10 }}>
                  {u.email}{u.username ? ` · @${u.username}` : ''}
                </p>
                <p style={{ fontSize: 10 }}>
                  擁有 {u.owned} 旅程 · 成員 {u.member_of} · 加過 {u.items_made} 景點
                </p>
              </div>
              <button className="btn sm ghost"
                style={{ padding: '4px 8px', fontSize: 11, color: 'var(--bad)' }}
                onClick={() => setDel({ kind: 'user', id: u.id,
                                        name: u.email, typed: '' })}>刪</button>
            </div>
          ))}
        </>
      )}

      {/* ══ 旅程 ══ */}
      {tab === 'trips' && d?.trips && (
        <>
          <div className="sub" style={{ fontSize: 10.5, marginBottom: 6 }}>
            共 {d.total} 個 · 顯示 {d.trips.length}
          </div>
          {d.trips.map(t => (
            <div key={t.id} className="item" style={{ alignItems: 'center' }}>
              <div className="ic">🗂</div>
              <div className="info">
                <h4>{t.name}</h4>
                <p style={{ fontSize: 10 }}>
                  {t.destination || '冇目的地'} · {t.days} 日 · {t.currency || 'HKD'}
                </p>
                <p className="mono" style={{ fontSize: 9.5 }}>
                  {t.owner_email} · 👥{t.members} 📍{t.items} 🛒{t.shopping} 💸{t.expenses}
                </p>
              </div>
              <button className="btn sm ghost"
                style={{ padding: '4px 8px', fontSize: 11, color: 'var(--bad)' }}
                onClick={() => setDel({ kind: 'trip', id: t.id,
                                        name: t.name, typed: '' })}>刪</button>
            </div>
          ))}
        </>
      )}

      {/* ══ ⚠️⚠️ 刪除確認（要打名）══ */}
      {del && (
        <div onClick={() => setDel(null)} style={{
          position: 'fixed', inset: 0, zIndex: 99, background: 'rgba(0,0,0,.72)',
          backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', padding: 18,
        }}>
          <div onClick={e => e.stopPropagation()} className="card"
            style={{ maxWidth: 420, width: '100%', borderColor: 'var(--bad)' }}>
            <div style={{ fontWeight: 900, fontSize: 15, color: 'var(--bad)' }}>
              ⚠️ 刪除{del.kind === 'user' ? '用戶' : '旅程'}
            </div>
            <div className="sub" style={{ fontSize: 12, marginTop: 8, lineHeight: 1.85 }}>
              呢個**唔可以復原**。<br />
              {del.kind === 'user'
                ? '佢嘅旅程會**轉移**畀其他成員；冇其他成員嘅旅程會連內容一齊刪。'
                : '旅程入面嘅景點、購物清單、開支**全部**會冇。'}
            </div>
            <div className="sub" style={{ fontSize: 11.5, marginTop: 12 }}>
              打「<b className="mono">{del.name}</b>」確認：
            </div>
            <input className="input" autoFocus value={del.typed}
              onChange={e => setDel({ ...del, typed: e.target.value })}
              style={{ marginTop: 6 }} />
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn ghost" style={{ flex: 1 }}
                onClick={() => setDel(null)}>取消</button>
              <button className="btn primary" style={{ flex: 1, background: 'var(--bad)' }}
                disabled={del.typed !== del.name}
                onClick={doDelete}>確定刪除</button>
            </div>
          </div>
        </div>
      )}
    </Sec>
  )
}

// ══════════════════════════════════════════════════════════════
// ⚠️ 呢啲一定要喺**模組層** —— 喺 component 入面定義會令
//    每次 render 都變成「新元件類型」→ 子樹 unmount/remount
//    → 入面嘅 input 每次打字都失焦（我哋試過呢個 bug）。
// ══════════════════════════════════════════════════════════════

function Sec({ title, children }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div className="sec">{title}</div>
      <div className="card" style={{ marginTop: 6 }}>{children}</div>
    </div>
  )
}

function Grid({ items }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(88px, 1fr))',
      gap: 10,
    }}>
      {items.map(([label, value, hint]) => (
        <div key={label}>
          <div className="sub" style={{ fontSize: 10 }}>{label}</div>
          <div className="mono" style={{ fontSize: 21, fontWeight: 900, lineHeight: 1.25 }}>
            {value ?? 0}
          </div>
          {hint ? <div className="sub" style={{ fontSize: 9.5 }}>{hint}</div> : null}
        </div>
      ))}
    </div>
  )
}

function Bar({ label, value, max, text }) {
  const w = max ? Math.min(100, (value / max) * 100) : 0
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
        <span>{label}</span>
        <span className="mono" style={{ opacity: .8 }}>{text}</span>
      </div>
      <div style={{
        height: 8, marginTop: 3, background: 'var(--surface-3)',
        borderRadius: 'var(--r-full)', overflow: 'hidden',
      }}>
        <div style={{
          width: `${Math.max(2, w)}%`, height: '100%',
          background: 'linear-gradient(90deg, var(--neon), var(--cyan))',
          borderRadius: 'var(--r-full)',
        }} />
      </div>
    </div>
  )
}

// ── 工具 ──

const KIND_ZH = {
  app_open: '開啟 app',
  login: '登入',
  register: '註冊',
  create_trip: '建立旅程',
  open_trip: '入旅程',
  add_item: '加景點',
  add_expense: '加開支',
  add_shopping: '加購物',
  share_import: '匯入連結',
  view_map: '睇地圖',
  settle: '分帳',
  onboard_done: '完成教學',
  qr_show: '睇 QR',
  qr_scan: '掃 QR',
}

const pct = (a, b) => (b ? `${Math.round((a / b) * 100)}%` : '—')

function fmtTime(iso) {
  if (!iso) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso)
  if (!m) return iso.slice(0, 16)
  return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`
}
