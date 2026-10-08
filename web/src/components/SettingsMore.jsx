import { useEffect, useState } from 'react'
import PasswordInput from './PasswordInput'
import { api, auth } from '../lib/api'
import { toast } from '../lib/ui'
import { subscribe, cacheStatus, clearTiles, applyUpdate } from '../lib/pwa'
import { bookmarkletCode } from '../lib/bookmarklet'
import WallpaperPicker from './WallpaperPicker'

/**
 * 「更多設定」—— Settings 嘅第二層
 * ==================================
 * ⚠️⚠️ 為咩要拆出嚟：
 *
 *   用戶原話：「你要 del 不過個 setting 有睇唔到任何嘅嘢啦。
 *              其實 setting 好簡單…朋友嘅呢啲係 Profile 嘅嘢嚟㗎嘛。」
 *
 *   舊版 `Settings.jsx` 543 行、11 個區塊**全部平鋪**：
 *   教學 / 頭像 / 帳號名 / QR / 顯示名 / 主題 / 密碼 /
 *   手機連線 / IG 匯入 / IG 抓取 / 快取 / 關於 / 登出
 *
 *   用戶要嘅 3 樣嘢（改名、換 icon、出 QR）散落喺其中 5 個位，
 *   中間隔住一堆佢未需要嘅設定 → **搵唔到**。
 *
 *   呢個檔案收埋所有「唔係 Profile」嘅嘢，
 *   要撳「更多設定」先展開。
 */

const THEMES = [
  { k: 'galaxy',  name: '銀河紫藍', sw: 'linear-gradient(100deg,#a855f7,#22d3ee)' },
  { k: 'tech',    name: '黑白科技', sw: 'linear-gradient(100deg,#fff,#71717a)' },
  { k: 'minimal', name: '簡約',     sw: 'linear-gradient(100deg,#1c1917,#a8a29e)' },
  { k: 'khaki',   name: '卡其',     sw: 'linear-gradient(100deg,#8a7048,#c4a878)' },
  { k: 'macaron', name: '馬卡龍',   sw: 'linear-gradient(100deg,#f9a8d4,#a5b4fc,#7dd3fc)' },
  { k: 'wafu',    name: '和風',     sw: 'linear-gradient(100deg,#b03a48,#2f4b4e)' },
]

/**
 * 摺疊區塊。
 *
 * ⚠️⚠️ 一定要定義喺**模組層**，唔可以喺 SettingsMore 入面定義！
 *
 *    用戶報嘅 bug：
 *      「當我用電腦打一個 Password 嘅時候…我打緊嘅同時
 *       我要點擊佢先至可以打下一個」—— 即係**每打一個字就失焦**。
 *
 *    原因：`const Sec = (...) => ...` 寫喺 render 入面 →
 *          每次 re-render 都係一個**全新嘅元件類型** →
 *          React 唯有 unmount + remount 成個子樹 →
 *          入面嘅 <input> 被拆走重建 → **focus 消失**。
 *
 *    ⚠️ 呢個係 React 嘅經典陷阱，而且 build 完全唔會警告。
 *       規則：**永遠唔好喺 render 入面定義元件**。
 *
 *    ⚠️ 為咩要「摺疊」而唔係平鋪：設定項目多，平鋪要碌好耐。
 */
function Sec({ k, open, onToggle, title, hint, children }) {
  return (
    <>
      <button className="btn wide ghost" style={{
        marginTop: 8, justifyContent: 'space-between', textAlign: 'left',
      }} onClick={() => onToggle(k)}>
        <span>{open === k ? '▾' : '▸'} {title}</span>
        {hint && <span className="sub" style={{ fontSize: 10 }}>{hint}</span>}
      </button>
      {open === k && <div className="card" style={{ marginTop: 6 }}>{children}</div>}
    </>
  )
}

export default function SettingsMore({ user, theme, setTheme, onLogout, onReplayTour, isAdmin, onOpenAdmin, onRefresh }) {
  const [pwa, setPwa] = useState({ online: true, registered: false, updateReady: false })
  const [cache, setCache] = useState(null)
  const [checking, setChecking] = useState(false)
  const [igProv, setIgProv] = useState(null)
  const [qr, setQr] = useState(null)
  const [pw0, setPw0] = useState('')
  const [pw1, setPw1] = useState('')
  const [pw2, setPw2] = useState('')
  const [pwBusy, setPwBusy] = useState(false)
  const [open, setOpen] = useState('')          // 邊個摺疊開咗

  const toggle = (k) => setOpen(o => (o === k ? '' : k))

  useEffect(() => subscribe(setPwa), [])
  useEffect(() => {
    api.igProvider().then(setIgProv).catch(() => {})
    api.qr().then(setQr).catch(() => {})
  }, [])
  useEffect(() => { if (pwa.registered) cacheStatus().then(setCache) }, [pwa.registered])

  async function savePassword() {
    if (pw1.length < 6) return toast('密碼最少 6 個字')
    if (pw1 !== pw2) return toast('兩次密碼唔一樣')
    setPwBusy(true)
    try {
      await api.setPassword(pw1, pw0 || undefined)
      toast('密碼已儲存 ✓')
      setPw0(''); setPw1(''); setPw2('')
      // ⚠️⚠️ 一定要重新攞 `/api/me` ——
      //    舊 bug：`/api/me` 冇回 `has_password` →
      //    改完密碼之後個 UI **仲係**顯示「未設定」。
      onRefresh?.()
    } catch (e) {
      // ⚠️⚠️ Fallback：如果後端話「現有密碼唔啱」但我哋以為冇密碼，
      //    即係 `has_password` 同後端唔一致（例如舊 session）。
      //    → 強制 refresh 一次，個「現有密碼」欄就會出返。
      //    （唔係嘅話用戶會卡住：見到「未設定」但點改都話密碼唔啱。）
      if (/現有密碼/.test(e.message || '')) {
        onRefresh?.()
        toast('呢個帳號已經有密碼 —— 請填「現有密碼」再試')
      } else {
        toast(e.message)
      }
    }
    finally { setPwBusy(false) }
  }

  async function saveTheme(k) {
    setTheme(k)
    try { await api.updateMe({ theme: k }) } catch {}
  }

  async function refreshCache() {
    setChecking(true); setCache(await cacheStatus()); setChecking(false)
  }
  async function wipeTiles() {
    if (!confirm('清走已快取嘅地圖圖磚？（下次睇地圖要重新下載）')) return
    await clearTiles(); toast('已清走圖磚快取'); refreshCache()
  }


  return (
    <div style={{ marginTop: 10 }}>
      {/* ── 帳號安全（密碼）── */}
      <Sec open={open} onToggle={toggle} k="pw" title="🔑 密碼"
        hint={user?.has_password ? '已設定' : '未設定'}>
        <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85, marginBottom: 10 }}>
          {user?.has_password
            ? '改密碼要填現有密碼 —— 防止有人偷到你部手機就鎖你出嚟。'
            : '⚠️ 你而家未有密碼。設定之後就可以用 email + 密碼登入。'}
        </div>
        <PasswordInput value={pw1}
          placeholder={user?.has_password ? '新密碼（最少 6 個字）' : '設定密碼（最少 6 個字）'}
          autoComplete="new-password"
          onChange={e => setPw1(e.target.value)} />
        <PasswordInput value={pw2} autoComplete="new-password"
          placeholder="再打一次" onChange={e => setPw2(e.target.value)}
          style={{ marginTop: 8 }} />
        {user?.has_password && (
          <PasswordInput value={pw0} autoComplete="current-password"
            placeholder="現有密碼" onChange={e => setPw0(e.target.value)}
            style={{ marginTop: 8 }} />
        )}
        <button className="btn primary wide" style={{ marginTop: 10 }}
          onClick={savePassword} disabled={pwBusy || !pw1 || pw1 !== pw2}>
          {pwBusy ? '儲存緊…' : user?.has_password ? '更改密碼' : '設定密碼'}
        </button>
        {pw1 && pw2 && pw1 !== pw2 && (
          <div className="sub" style={{ fontSize: 10.5, color: 'var(--bad)', marginTop: 7 }}>
            兩次密碼唔一樣
          </div>
        )}
      </Sec>

      {/* ── 外觀（主題）── */}
      <Sec open={open} onToggle={toggle} k="theme" title="🎨 主題">
        <div className="themes">
          {THEMES.map(t => (
            <button key={t.k} className={`theme-opt ${theme === t.k ? 'on' : ''}`}
              onClick={() => saveTheme(t.k)}>
              <div className="sw" style={{ background: t.sw }} />
              {t.name}
            </button>
          ))}
        </div>
      </Sec>

      {/* ⚠️⚠️ 自訂背景（用戶要求）
             「我哋整一個 function 就係改 wallpaper…可以自訂
              wallpaper 咁然後你就可以加返自己嘅相上去。」 */}
      <Sec open={open} onToggle={toggle} k="wallpaper"
        title="🖼 背景圖" hint="預設或者自己嘅相">
        <WallpaperPicker user={user} onChanged={onRefresh} />
      </Sec>

      {/* ── 指導教學 ── */}
      <Sec open={open} onToggle={toggle} k="tour" title="▶️ 指導教學">
        <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85, marginBottom: 10 }}>
          新手教學只會喺<b>第一次登入</b>嗰陣出一次。想再睇一次點用？撳下面。
        </div>
        <button className="btn wide" onClick={() => onReplayTour?.()}>
          重新播放教學
        </button>
      </Sec>

      {/* ── 手機連線 ── */}
      <Sec open={open} onToggle={toggle} k="phone" title="📱 手機連線">
        <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
          手機同電腦要連<b>同一個 WiFi</b>，然後用手機相機掃下面個 QR。
        </div>
        {qr?.svg ? (
          <>
            <div style={{
              marginTop: 12, padding: 12, background: '#fff', borderRadius: 'var(--r-sm)',
              display: 'flex', justifyContent: 'center',
            }} dangerouslySetInnerHTML={{ __html: qr.svg }} />
            <div className="mono" style={{
              fontSize: 12, marginTop: 10, textAlign: 'center',
              color: 'var(--cyan)', wordBreak: 'break-all',
            }}>{qr.url}</div>
          </>
        ) : (
          <div className="sub" style={{ fontSize: 11, marginTop: 10 }}>產生緊…</div>
        )}
        <div className="sub" style={{ fontSize: 10.5, marginTop: 10, lineHeight: 1.9 }}>
          <b>⚠️ http:// 嘅限制</b>
          <br />· 加到主畫面 ✅
          <br />· 離線功能 ❌（service worker 要 HTTPS）
          <br />· 剪貼簿 API ❌ 可能唔得
          <br /><b>想全部功能 → 要 HTTPS</b>（cloudflared / ngrok 免費 tunnel）
        </div>
      </Sec>

      {/* ── IG / 小紅書 匯入 ── */}
      <Sec open={open} onToggle={toggle} k="ig" title="🔖 IG / 小紅書 匯入">
        <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
          IG / 小紅書封鎖咗自動讀取（server 請求一律回傳登入頁，零資料）。
          <br />
          呢個小工具用<b>你自己嘅瀏覽器、你自己嘅登入狀態</b>，
          喺你開住個帖嗰陣一撳就抽到內文 —— 免費、唔會被鎖、唔會洩漏密碼。
        </div>
        <div style={{
          marginTop: 12, padding: 14, textAlign: 'center',
          border: '2px dashed var(--border-hi)', borderRadius: 'var(--r-sm)',
          background: 'var(--surface-2)',
        }}>
          <a href={bookmarkletCode()} draggable
            onClick={e => { e.preventDefault(); toast('拖呢個掣去書籤欄（唔係撳）') }}
            style={{
              display: 'inline-block', padding: '11px 20px', borderRadius: 'var(--r-xs)',
              background: 'var(--grad)', color: '#0b0518', fontWeight: 900,
              fontSize: 14, cursor: 'grab', textDecoration: 'none', userSelect: 'none',
            }}>🔖 匯入到 Wander</a>
          <div className="sub" style={{ fontSize: 10.5, marginTop: 9, lineHeight: 1.7 }}>
            ⬆️ <b>用滑鼠拖呢個掣去書籤欄</b>（唔係撳佢）
          </div>
        </div>
        <button className="btn sm" style={{ marginTop: 10 }} onClick={async () => {
          try {
            await navigator.clipboard.writeText(bookmarkletCode())
            toast('已複製書籤碼')
          } catch { toast('複製失敗') }
        }}>複製書籤碼（手機用手動新增）</button>
        <details style={{ marginTop: 10 }}>
          <summary className="sub" style={{ fontSize: 11.5, cursor: 'pointer' }}>
            見唔到書籤欄？或者想用手機？
          </summary>
          <div className="sub" style={{ fontSize: 11, lineHeight: 1.9, marginTop: 8 }}>
            <b>顯示書籤欄：</b> Mac / Windows 都係 <b>⌘/Ctrl + Shift + B</b>
            <br /><br />
            <b>手機：</b>
            <br />① 撳「複製書籤碼」
            <br />② 加一個任意書籤
            <br />③ 將嗰個書籤嘅網址改成啱啱複製嘅一段
            <br />④ 之後喺 IG 開帖 → 撳網址欄打「Wander」→ 揀嗰個書籤
          </div>
        </details>

        {igProv?.providers && (
          <>
            <div className="sub" style={{ fontSize: 11, marginTop: 14, lineHeight: 1.8 }}>
              <b>或者</b>配置第三方抓取服務（IG link 一貼就自動抽出）：
            </div>
            <div className="card" style={{
              marginTop: 8, padding: 10, background: 'var(--surface-2)',
              borderColor: igProv.enabled ? 'var(--good)' : 'var(--border)',
            }}>
              <div className="sub" style={{ fontSize: 11.5 }}>
                {igProv.enabled
                  ? <span style={{ color: 'var(--good)' }}>✓ 已啟用：{igProv.label}</span>
                  : '⚪ 未啟用 —— 用緊免費方法'}
              </div>
            </div>
            {!igProv.enabled && Object.entries(igProv.providers).map(([k, v]) => (
              <div key={k} className="card" style={{
                marginTop: 7, padding: 10, background: 'var(--surface-2)',
              }}>
                <div style={{ fontWeight: 800, fontSize: 12.5 }}>{v.label}</div>
                <div className="sub" style={{ fontSize: 10.5, marginTop: 3, lineHeight: 1.7 }}>
                  🎁 {v.free}<br />💰 {v.pricing}
                </div>
                <a href={v.signup} target="_blank" rel="noreferrer" className="btn sm"
                  style={{ marginTop: 7, display: 'inline-block' }}>去拎 key →</a>
              </div>
            ))}
            {!igProv.enabled && (
              <div className="sub" style={{ fontSize: 10.5, marginTop: 10, lineHeight: 1.85 }}>
                <b style={{ color: 'var(--warn)' }}>⚠️ 老實講</b>
                <br />
                · 喺 <span className="mono">server/.env</span> 填
                <span className="mono"> WANDER_IG_PROVIDER </span>同
                <span className="mono"> WANDER_IG_KEY</span>
                <br />· 呢啲服務喺 IG ToS 嘅<b>灰色地帶</b>，合規責任喺你身上
                <br />· <b>零成本零風險</b> → 用上面嘅書籤小工具
              </div>
            )}
          </>
        )}
      </Sec>

      {/* ── 離線 / 儲存 ── */}
      <Sec open={open} onToggle={toggle} k="cache" title="💾 離線 / 儲存"
        hint={pwa.registered ? '已啟用' : '未啟用'}>
        <div className="sub" style={{ lineHeight: 2, fontSize: 12 }}>
          <div>{pwa.online ? '🌐 網上' : '📴 離線'}</div>
          {cache && (
            <div className="mono" style={{ fontSize: 11 }}>
              快取：程式 {cache.shell} · 圖磚 {cache.tiles} · 其他 {cache.ext}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 7, marginTop: 11, flexWrap: 'wrap' }}>
          <button className="btn sm" onClick={refreshCache} disabled={checking}>
            {checking ? '檢查緊…' : '重新檢查'}
          </button>
          {cache?.tiles > 0 && (
            <button className="btn sm ghost" onClick={wipeTiles}>清圖磚快取</button>
          )}
          {pwa.updateReady && (
            <button className="btn sm" onClick={applyUpdate}>立即更新</button>
          )}
        </div>
        {!pwa.registered && (
          <div className="sub" style={{ fontSize: 11, marginTop: 9, lineHeight: 1.7 }}>
            💡 手機用區網 IP（http://192.168.x.x）註冊唔到 service worker ——
            呢個係瀏覽器安全限制。要離線功能，請「分享 → 加到主畫面」，
            之後由主畫面圖示開啟。
          </div>
        )}
      </Sec>

      {/* ── 關於 ── */}
      {/* ⚠️ 開發版後台（用戶要求）—— 只有 admin 見到 */}
        {isAdmin && (
          <Sec open={open} onToggle={toggle} k="admin" title="🛠 開發版後台"
            hint="睇使用數據">
            <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
              睇下啲人點用呢個 App：活躍用戶、邊個功能最多人用、
              邊個功能開咗但冇用、旅程規模…
            </div>
            <button className="btn primary wide" style={{ marginTop: 10 }}
              onClick={onOpenAdmin}>開啟後台 →</button>
          </Sec>
        )}

        <Sec open={open} onToggle={toggle} k="about" title="ℹ️ 關於">
        {/* ⚠️⚠️ 版本 + 強制重新載入
               ────────────────────────────────
               用戶報：「shopping list 入唔到去睇」

               ⚠️ 呢類問題**九成係快取舊版**（service worker）——
                 所以要有：
                 ① 睇得到自己跑緊邊個版本
                 ② 一個掣可以清晒 cache 再 reload（唔使教佢去
                    Safari 設定度撳六層） */}
        <div className="row" style={{ gap: 8, alignItems: 'center', marginBottom: 10 }}>
          <span className="sub mono" style={{ fontSize: 10, flex: 1 }}>
            版本 {typeof __BUILD_ID__ !== 'undefined' ? __BUILD_ID__ : 'dev'}
          </span>
          <button className="btn sm ghost" style={{ fontSize: 11 }}
            onClick={async () => {
              const { hardReload } = await import('../lib/pwa')
              try { await hardReload() } catch { window.location.reload() }
            }}>
            ↻ 強制重新載入
          </button>
        </div>
        <div className="sub" style={{ lineHeight: 2 }}>
          <div>Wander · 旅行規劃 App</div>
          <div className="mono" style={{ fontSize: 10, opacity: .75 }}>
            engine 0.1.0 · 完全免費版
          </div>
          <div style={{ marginTop: 8, fontSize: 11 }}>
            解析引擎、地圖、搜尋全部用免費服務：<br />
            OpenStreetMap · Photon · Nominatim · DuckDuckGo · Leaflet
          </div>
        </div>
      </Sec>

      {/* ── 登出 ── */}
      <div style={{ marginTop: 20 }}>
        <button className="btn wide ghost" style={{ color: 'var(--bad)' }}
          onClick={() => { auth.clear(); onLogout?.() }}>登出</button>
      </div>
    </div>
  )
}
