import { useEffect, useState } from 'react'
import { api, auth } from '../lib/api'
import PasswordInput from './PasswordInput'
import { toast } from '../lib/ui'
import PixelIcon from './PixelIcon'

/**
 * 登入 / 註冊（兩頁互通）
 * ========================
 * 用戶要求（原文）：
 *   「login function plzzz。delete 驗證碼登入 function。
 *    要整兩版：第一個版就係如果你冇帳號你就要註冊啦，
 *    然後另外一個頁面就係有個 button 俾你去撳就會去到另一個頁面
 *    就係俾你去登入囉。應該一開始就係登入畫面，
 *    但如果你冇登入帳戶你就需要去註冊，
 *    所以就會有個 button 俾你去撳去註冊。
 *    總之兩頁啦，係應該有個 button 去互通嘅。」
 *
 * ⚠️⚠️ 為咩刪走驗證碼登入：
 *   · 「打 email → 收信 → 打 6 位數字」**每次**登入都要做一次，
 *     手機用戶要跳去郵件 app 再跳返嚟 —— 流失率好高
 *   · 驗證碼登入冇「密碼」概念 → 冇「改密碼」嘅需要，
 *     用戶亦都冇「帳號被盜」嘅意識
 *   · 密碼登入係用戶預期嘅標準做法
 *
 * ⚠️ 但驗證碼**冇完全刪** —— 保留做「認領舊帳號」：
 *    舊帳號（驗證碼年代開嘅）冇密碼。如果註冊時打嘅 email 已經存在
 *    但未設密碼，就要寄驗證碼去確認身份先可以設密碼。
 *
 *    **唔可以**「email 存在就當佢係本人」——
 *    咁樣任何人打你個 email 就搶到你個帳號。
 */

const T = {
  login: {
    title: '歡迎返嚟',
    sub: '用你嘅 email 同密碼登入',
    cta: '登入',
    switchQ: '仲未有帳號？',
    switchA: '註冊一個',
  },
  register: {
    title: '開一個帳號',
    sub: '只需要 email 同密碼',
    cta: '註冊',
    switchQ: '已經有帳號？',
    switchA: '去登入',
  },
}

export default function Login({ onLogin }) {
  const [page, setPage] = useState('login')      // login | register
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  // 認領舊帳號（email 已存在但未設密碼）
  const [claim, setClaim] = useState(null)       // { email }
  const [code, setCode] = useState('')
  const [devCode, setDevCode] = useState(null)
  // ⚠️⚠️ 用戶問：「未設定 SMTP 你係諗住點搞？」
  //    答：冇 SMTP 就寄唔到驗證碼 → 改用**邀請碼**註冊。
  //    你親手畀條碼朋友，比寄 email 更實在（朋友之間用）。
  const [signup, setSignup] = useState(null)     // { mode, need_invite }
  const [invite, setInvite] = useState('')
  // ⚠️⚠️ 用戶要求：邀請碼要有**獨立「驗證」掣**，而且欄要窄。
  //    null = 未驗  ·  {valid, reason, note} = 驗完
  const [inviteChk, setInviteChk] = useState(null)
  const [inviteBusy, setInviteBusy] = useState(false)

  const cfg = T[page]

  // ⚠️ 問後端「註冊要咩」—— 決定要唔要顯示邀請碼欄
  useEffect(() => {
    api.signupMode().then(setSignup).catch(() => {})
  }, [])

  function switchTo(p) {
    setPage(p); setErr(null); setPw(''); setPw2('')
    setClaim(null); setCode(''); setDevCode(null)
  }

  /** ⚠️ 撳「驗證」掣 —— 只檢查邀請碼，唔提交表單。 */
  async function checkInvite() {
    const c = invite.trim().toUpperCase()
    if (!c) return setInviteChk({ valid: false, reason: '請輸入邀請碼' })
    setInviteBusy(true)
    try {
      const r = await api.checkInvite(c)
      setInviteChk(r)
      if (r.valid) setInvite(c)     // 順便正規化做大寫
    } catch (e) {
      setInviteChk({ valid: false, reason: e.message })
    } finally { setInviteBusy(false) }
  }

  async function submit(e) {
    e?.preventDefault?.()
    setErr(null)
    const em = email.trim().toLowerCase()
    if (!em) return setErr('請填 email')
    if (!em.includes('@')) return setErr('Email 格式唔啱')
    if (!pw) return setErr('請填密碼')
    if (pw.length < 6) return setErr('密碼最少 6 個字')
    if (page === 'register' && pw !== pw2) return setErr('兩次密碼唔一樣')

    setBusy(true)
    try {
      const r = page === 'login'
        ? await api.passwordLogin(em, pw)
        : await api.register(em, pw, invite)
      auth.token = r.token
      onLogin?.(r.user)
    } catch (e2) {
      const msg = e2.message || '失敗'
      // ⚠️ 舊帳號（未設密碼）→ 轉去「認領」流程
      if (/未設密碼|needs_claim/.test(msg)) {
        setClaim({ email: em })
        await sendCode(em)
      } else {
        setErr(msg)
      }
    } finally { setBusy(false) }
  }

  /** 認領流程：寄驗證碼去該 email。 */
  async function sendCode(em) {
    try {
      const r = await api.requestCode(em)
      setDevCode(r.dev_code || null)
      if (r.dev_code) setCode(r.dev_code)
      toast('驗證碼已寄去你個 email')
    } catch (e) { setErr(e.message) }
  }

  async function doClaim(e) {
    e?.preventDefault?.()
    setErr(null)
    if (!code.trim()) return setErr('請填驗證碼')
    setBusy(true)
    try {
      const r = await api.claimAccount(claim.email, code.trim(), pw)
      auth.token = r.token
      onLogin?.(r.user)
    } catch (e2) { setErr(e2.message) }
    finally { setBusy(false) }
  }

  // ══ 認領舊帳號畫面 ══
  if (claim) {
    return (
      <div className="login">
        <Logo />
        <div className="card" style={{ borderColor: 'var(--warn)' }}>
          <div style={{ fontWeight: 900, fontSize: 15, marginBottom: 6 }}>
            呢個 email 已經有帳號
          </div>
          <div className="sub" style={{ fontSize: 12, lineHeight: 1.85, marginBottom: 12 }}>
            <b className="mono">{claim.email}</b> 係舊帳號（未設密碼）。
            <br />
            我哋寄咗個驗證碼去呢個 email —— 打返落嚟就可以設定新密碼。
          </div>

          {devCode && (
            <div className="card" style={{
              marginBottom: 10, padding: 10, background: 'var(--surface-2)',
              borderColor: 'var(--warn)',
            }}>
              <div className="sub" style={{ fontSize: 11 }}>
                ⚠️ 未設定 SMTP → 驗證碼喺度：<b className="mono">{devCode}</b>
              </div>
            </div>
          )}

          <form onSubmit={doClaim}>
            <input className="input" inputMode="numeric" autoComplete="one-time-code"
              placeholder="6 位驗證碼" value={code} maxLength={8}
              onChange={e => setCode(e.target.value)} />
            <PasswordInput style={{ marginTop: 8 }}
              placeholder="設定新密碼（最少 6 個字）"
              autoComplete="new-password" value={pw}
              onChange={e => setPw(e.target.value)} />
            {err && <Err msg={err} />}
            <button className="btn primary wide" type="submit" disabled={busy}
              style={{ marginTop: 12 }}>
              {busy ? '處理緊…' : '確認並登入'}
            </button>
          </form>

          <button className="btn wide ghost" style={{ marginTop: 8 }}
            onClick={() => switchTo('login')}>
            ‹ 返去登入
          </button>
        </div>
      </div>
    )
  }

  // ══ 登入 / 註冊 ══
  return (
    <div className="login">
      <Logo />

      <div className="card">
        <div style={{ fontWeight: 900, fontSize: 16 }}>{cfg.title}</div>
        <div className="sub" style={{ fontSize: 11.5, marginTop: 4, marginBottom: 14 }}>
          {cfg.sub}
        </div>

        <form onSubmit={submit}>
          <input className="input" type="email" inputMode="email"
            autoComplete="email" placeholder="you@example.com"
            value={email} onChange={e => setEmail(e.target.value)}
            disabled={busy} />
          {/* ⚠️⚠️ 用戶要求：「only email password no verify」
      → **open 模式唔出邀請碼欄**（唔好煩用戶）。
      ⚠️ 但後端**照樣接受**邀請碼（安全網）——
         如果將來 SMTP 設定錯，管理員仍然可以用邀請碼解鎖。 */}
          {page === 'register' && signup?.need_invite && (
            <div style={{ marginTop: 8 }}>
              {/* ⚠️⚠️ 用戶要求：
                     「寫邀請碼嗰欄應該係冇咁闊，然後旁邊落返
                      一個掣叫做『驗證』。」
                   ⚠️ 為咩要窄：6 個字嘅碼用成行闊度好浪費，
                      而且睇落似「要打好多嘢」。
                   ⚠️ 為咩要有獨立「驗證」掣：打錯一個字就要填晒
                      email + 密碼 + 確認密碼先知道錯 → 好蝕。 */}
              <div className="invite-row">
                <input className="input mono invite-input"
                  placeholder="邀請碼"
                  autoCapitalize="characters" autoCorrect="off" spellCheck={false}
                  maxLength={12} value={invite}
                  onChange={e => {
                    setInvite(e.target.value.toUpperCase())
                    setInviteChk(null)      // ⚠️ 改咗就要重新驗
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') { e.preventDefault(); checkInvite() }
                  }}
                  disabled={busy || inviteBusy} />
                <button type="button" className="btn invite-btn"
                  onClick={checkInvite}
                  disabled={busy || inviteBusy || !invite.trim()}>
                  {inviteBusy ? '…' : '驗證'}
                </button>
              </div>

              {/* 驗證結果 */}
              {inviteChk && (
                <div className="sub" style={{
                  fontSize: 11, marginTop: 7, lineHeight: 1.7,
                  color: inviteChk.valid ? 'var(--good)' : 'var(--bad)',
                }}>
                  {inviteChk.valid
                    ? <>✓ 邀請碼有效{inviteChk.note ? `（${inviteChk.note}）` : ''} —— 可以繼續註冊</>
                    : <>✗ {inviteChk.reason || '邀請碼唔啱'}</>}
                </div>
              )}
              {!inviteChk && (
                <div className="sub" style={{ fontSize: 10.5, marginTop: 6, lineHeight: 1.7 }}>
                  🔑 呢個 app 要邀請碼先註冊得到。問下邀請你嘅朋友攞，打完撳「驗證」。
                </div>
              )}
            </div>
          )}

          <PasswordInput
            style={{ marginTop: 8 }}
            autoComplete={page === 'login' ? 'current-password' : 'new-password'}
            placeholder={page === 'login' ? '密碼' : '設定密碼（最少 6 個字）'}
            value={pw} onChange={e => setPw(e.target.value)} disabled={busy} />

          {page === 'register' && (
            <PasswordInput
              style={{ marginTop: 8 }}
              autoComplete="new-password" placeholder="再打一次密碼"
              value={pw2} onChange={e => setPw2(e.target.value)} disabled={busy} />
          )}

          {/* ══════════════════════════════════════════════════════
              邀請碼（`invite` 模式）
              ══════════════════════════════════════════════════════
              ⚠️⚠️ 用戶問：「未設定 SMTP 你係諗住點搞？」

              答：冇 SMTP 就寄唔到驗證碼。所以改用**邀請碼** ——
                  · 完全唔使 email、冇成本、冇 spam 風險
                  · 而且係更好嘅「驗證」：你親手畀條碼佢，
                    比寄 email 更確定佢係邊個
                  · 你喺「設定 → 開發版後台」可以產生
              */}

          {/* ⚠️ 只有真係設定咗寄信先講「會寄確認信」——
                 唔係嘅話係假承諾。 */}
          {page === 'register' && signup?.mail_configured &&
           !signup.need_invite && (
            <div className="sub" style={{ fontSize: 10.5, marginTop: 7 }}>
              📧 註冊之後會寄一封確認信去你嘅 email。
            </div>
          )}

          {err && <Err msg={err} />}

          <button className="btn primary wide" type="submit"
            disabled={busy} style={{ marginTop: 14 }}>
            {busy ? '處理緊…' : cfg.cta}
          </button>
        </form>

        {/* ══ 兩頁互通 ══ */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: 6, marginTop: 14, paddingTop: 12,
          borderTop: '1px dashed var(--border)',
        }}>
          <span className="sub" style={{ fontSize: 12 }}>{cfg.switchQ}</span>
          <button className="btn sm"
            onClick={() => switchTo(page === 'login' ? 'register' : 'login')}
            disabled={busy}>
            {cfg.switchA}
          </button>
        </div>
      </div>

      <div className="sub" style={{
        fontSize: 10.5, textAlign: 'center', marginTop: 14, lineHeight: 1.9, opacity: .7,
      }}>
        密碼用 PBKDF2 加鹽雜湊儲存，我哋睇唔到你嘅密碼。
      </div>
    </div>
  )
}

function Logo() {
  return (
    <div className="logo">
      <div className="mark">
        <PixelIcon name="sparkle" size={40} />
      </div>
      <h1>WANDER</h1>
      <p>計劃旅行 · 分區行程 · 分帳 · 購物清單</p>
    </div>
  )
}

function Err({ msg }) {
  return (
    <div className="sub" style={{
      marginTop: 10, padding: '9px 11px', fontSize: 11.5, lineHeight: 1.7,
      color: 'var(--bad)', background: 'color-mix(in srgb, var(--bad) 12%, transparent)',
      border: '2px solid color-mix(in srgb, var(--bad) 45%, transparent)',
      borderRadius: 'var(--r-sm)', whiteSpace: 'pre-wrap',
    }}>{msg}</div>
  )
}
