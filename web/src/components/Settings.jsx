import { useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'
import Avatar from './Avatar'
import AvatarPicker from './AvatarPicker'
import MyQr from './MyQr'
import SettingsMore from './SettingsMore'

/**
 * 設定 = **個人檔案（Profile）**
 * ==============================
 * 用戶要求（原文）：
 *   「你要 del 不過個 setting 有睇唔到任何嘅嘢啦。
 *    其實 setting 好簡單，你只需要講嘅就係：
 *      ① 改名（有你個名喺度）
 *      ② 有你 icon
 *      ③ 就係 QR code —— 喺 setting 度整個 QR code
 *    朋友嘅呢啲係 **Profile** 嘅嘢嚟㗎嘛。」
 *
 * ⚠️⚠️ 為咩要重寫（之前 543 行、11 個區塊）：
 *
 *   舊版一開就見到：指導教學 / 頭像 / 帳號名 / QR / 顯示名 /
 *   Theme / 密碼 / 手機連線 / IG 匯入 / IG 自動抓取 /
 *   離線儲存 / 關於 —— 全部平鋪喺一頁。
 *
 *   結果：**用戶搵唔到佢想要嘅嘢**（「睇唔到任何嘅嘢」）。
 *
 *   ⚠️ 呢個係典型嘅「開發者盲點」：
 *      每一樣都係我親手加嘅，所以我知喺邊；
 *      但用戶只係想「改名 / 換 icon / 出 QR」——
 *      嗰 3 樣嘢散落喺 11 個區塊嘅 5 個位。
 *
 *   修法：**分層**
 *     第一層（預設見到）= 純 Profile：頭像 + 名 + @帳號名 + QR
 *     第二層（要撳「更多」）= 密碼 / 主題 / 教學 / 手機 / 進階
 */

export default function Settings({ user, theme, setTheme, onLogout, onUserUpdate,
                                   onReplayTour, isAdmin, onOpenAdmin, onRefresh }) {
  const [more, setMore] = useState(false)
  const [editName, setEditName] = useState(false)
  const [name, setName] = useState(user?.display_name || '')
  const [busy, setBusy] = useState(false)
  const [pickAvatar, setPickAvatar] = useState(false)
  const [editUname, setEditUname] = useState(false)
  const [uname, setUname] = useState(user?.username || '')

  const display = user?.display_name || user?.email?.split('@')[0] || '你'

  async function saveName() {
    const n = name.trim()
    if (!n) return toast('請填名')
    if (n === user?.display_name) { setEditName(false); return }
    setBusy(true)
    try {
      await api.updateMe({ display_name: n })
      onUserUpdate?.({ display_name: n })
      toast('改咗名 ✓')
      setEditName(false)
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  async function saveUname() {
    const u = uname.trim().toLowerCase().replace(/^@/, '')
    if (u === (user?.username || '')) { setEditUname(false); return }
    if (u.length < 3) return toast('帳號名最少 3 個字')
    if (!/^[a-z][a-z0-9_]*$/.test(u)) return toast('要字母開頭，只可以字母數字底線')
    if (!/[0-9]/.test(u)) return toast('要有埋數字（例如 alice99）')
    setBusy(true)
    try {
      await api.updateMe({ username: u })
      onUserUpdate?.({ username: u })
      toast(`帳號名係 @${u} ✓`)
      setEditUname(false)
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="screen">
      {/* ══════════════════════════════════════════════
          第一層：Profile（用戶要求嘅三樣嘢）
          ══════════════════════════════════════════════ */}

      {/* ── ① 頭像 + 名 + @帳號名 ── */}
      <div className="card glow" style={{ padding: '5% 4%' }}>
        <div className="row" style={{ gap: 14, alignItems: 'center' }}>
          <button onClick={() => setPickAvatar(v => !v)}
            style={{ background: 'none', border: 'none', padding: 0, flex: '0 0 auto' }}>
            <Avatar id={user?.avatar} size={72} ring />
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            {editName ? (
              <div className="row" style={{ gap: 6 }}>
                <input className="input" value={name} autoFocus maxLength={40}
                  placeholder="你嘅名"
                  onChange={e => setName(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') saveName()
                    if (e.key === 'Escape') {
                      setEditName(false); setName(user?.display_name || '')
                    }
                  }}
                  style={{ flex: 1, minWidth: 0 }} />
                <button className="btn sm primary" onClick={saveName} disabled={busy}>✓</button>
              </div>
            ) : (
              <button onClick={() => { setEditName(true); setName(user?.display_name || '') }}
                style={{
                  background: 'none', border: 'none', padding: 0, textAlign: 'left',
                  display: 'flex', alignItems: 'center', gap: 7, width: '100%',
                }}>
                <span style={{
                  fontWeight: 900, fontSize: 19, color: 'var(--fg)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{display}</span>
                <span style={{ fontSize: 13, opacity: .5, flex: '0 0 auto' }}>✏️</span>
              </button>
            )}

            {editUname ? (
              <div className="row" style={{ gap: 6, marginTop: 6 }}>
                <span className="mono" style={{ fontSize: 14, color: 'var(--cyan)' }}>@</span>
                <input className="input" value={uname} autoFocus
                  placeholder="alice99"
                  onChange={e => setUname(
                    e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                  onKeyDown={e => e.key === 'Enter' && saveUname()}
                  style={{ flex: 1, minWidth: 0 }} />
                <button className="btn sm primary" onClick={saveUname} disabled={busy}>✓</button>
              </div>
            ) : (
              <button onClick={() => { setEditUname(true); setUname(user?.username || '') }}
                style={{
                  background: 'none', border: 'none', padding: '4px 0 0',
                  textAlign: 'left', display: 'flex', alignItems: 'center', gap: 6,
                }}>
                <span className="mono" style={{
                  fontSize: 13, color: user?.username ? 'var(--cyan)' : 'var(--warn)',
                }}>
                  {user?.username ? `@${user.username}` : '未設帳號名'}
                </span>
                <span style={{ fontSize: 11, opacity: .5 }}>✏️</span>
              </button>
            )}
          </div>
        </div>

        <div className="sub" style={{ fontSize: 10.5, marginTop: 10, lineHeight: 1.75 }}>
          撳個頭像可以換 icon；撳個名可以改。
        </div>

        {pickAvatar && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px dashed var(--border)' }}>
            <AvatarPicker user={user} onUserUpdate={(u) => {
              onUserUpdate?.(u)
              setPickAvatar(false)
            }} />
          </div>
        )}
      </div>

      {/* ── ② QR Code（畀朋友加你）── */}
      <div className="sec">我嘅 QR Code</div>
      <div className="card">
        <MyQr user={user} onFound={(u) => {
          navigator.clipboard?.writeText('@' + u).catch(() => {})
          toast(`已複製 @${u} —— 去「朋友」度加`)
        }} />
      </div>

      {/* ══════════════════════════════════════════════
          第二層：其他嘢收埋（唔好再平鋪！）
          ══════════════════════════════════════════════ */}
      <button className="btn wide ghost" style={{ marginTop: 18 }}
        onClick={() => setMore(v => !v)}>
        {more ? '▲ 收埋其他設定' : '▼ 更多設定（密碼 · 主題 · 教學 · 進階）'}
      </button>

      {more && (
        <SettingsMore user={user}
          isAdmin={isAdmin} onOpenAdmin={onOpenAdmin} theme={theme} setTheme={setTheme}
          onLogout={onLogout} onReplayTour={onReplayTour} onRefresh={onRefresh} />
      )}
    </div>
  )
}
