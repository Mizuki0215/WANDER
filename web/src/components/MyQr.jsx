import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'
import Avatar from './Avatar'
import { readForQr } from '../lib/image'
import { isSelf, SELF_MSG, SELF_HINT } from '../lib/selfcheck'

/**
 * 個人 QR Code + 掃描
 * ===================
 * 用戶要求（原文）：
 *   「或者做一個自己嘅 QR code → invite 時可以 scan 人哋個 code
 *     或者 upload 個 QR code 去 detect」
 *
 * 兩個方向：
 *   ① 我嘅 QR   —— 畀人掃
 *   ② 掃人哋    —— 上傳一張 QR 圖，後端用 OpenCV 解
 *
 * ⚠️⚠️ 為咩用「上傳圖」而唔用「即時相機」：
 *     `getUserMedia`（相機）**需要 secure context（HTTPS）**。
 *     而 http://192.168.x.x 唔算 secure context → 開唔到相機。
 *
 *     但「影相 → 上傳」完全冇呢個限制：
 *     用手機原生相機影（或者揀相簿入面嘅圖），再上傳。
 *
 *     ⚠️ 之後如果部署上 HTTPS，可以加即時相機（用 BarcodeDetector）。
 */
export default function MyQr({ user, onFound }) {
  const [qr, setQr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState('mine')     // mine | scan
  const [scanning, setScanning] = useState(false)
  // ⚠️ 掃到自己嘅 QR → 記住個 username，顯示明確訊息
  //    （用戶要求：「唔可以加自己做朋友」）
  const [selfHit, setSelfHit] = useState(null)
  const fileRef = useRef(null)

  async function loadMine() {
    setBusy(true)
    try { setQr(await api.myQr()) }
    catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  /**
   * ⚠️⚠️ 自動載入 —— 呢個係用戶報嘅 bug：
   *   「Save 咗帳號名同顯示名之後，QR code 冇 show 出嚟」
   *
   *   原因：原本只有撳「產生我嘅 QR Code」個掣先會 load。
   *   用戶改完帳號名之後，以為 QR 會自動出，但其實要再撳一次。
   *
   *   修法：username 一有就自動產生；username 一變就重新產生
   *        （舊 QR 編碼舊 username，一定要換）。
   */
  const uname = user?.username || ''
  useEffect(() => {
    if (mode !== 'mine') return
    if (!uname) { setQr(null); return }        // 冇帳號名 → 清走舊 QR
    let dead = false
    setBusy(true)
    api.myQr()
      .then(r => { if (!dead) setQr(r) })
      .catch(() => { if (!dead) setQr(null) })
      .finally(() => { if (!dead) setBusy(false) })
    return () => { dead = true }
  }, [uname, mode])

  /** 上傳一張 QR 圖 → 後端 OpenCV 解。 */
  async function scan(e) {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    setScanning(true)
    try {
      const img = await readForQr(f)
      const r = await api.decodeQr(img.data)
      if (!r.username) {
        toast(r.text ? `解到「${r.text.slice(0, 30)}」但唔係 Wander 邀請` : '解唔到 QR')
        return
      }

      // ⚠️⚠️ 掃到自己 —— 用戶明確要求要話「唔可以加自己做朋友」
      //    ⚠️ 一定要喺呼叫 onFound **之前**檢查，
      //       否則會照樣複製 @自己 然後叫你去加自己。
      if (isSelf(r.username, user)) {
        setSelfHit(r.username)
        setScanning(false)
        toast(`⚠️ ${SELF_MSG}`)
        return
      }

      setSelfHit(null)
      toast(`搵到 @${r.username} ✓`)
      onFound?.(r.username)
    } catch (err) {
      toast(err.message)
    } finally { setScanning(false) }
  }

  return (
    <div>
      <div className="chips" style={{ marginBottom: 12 }}>
        <button className={`chip ${mode === 'mine' ? 'on' : ''}`}
          onClick={() => { setMode('mine'); if (!qr) loadMine() }}>
          📤 我嘅 QR
        </button>
        <button className={`chip ${mode === 'scan' ? 'on' : ''}`}
          onClick={() => setMode('scan')}>
          📷 掃人哋
        </button>
      </div>

      {mode === 'mine' ? (
        <>
          {!user?.username ? (
            <div className="card" style={{ borderColor: 'var(--warn)' }}>
              <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.85 }}>
                ⚠️ 要先設定<b>帳號名</b>先有個人 QR。
                <br />去上面「帳號名」設定一個（例如 @alice）。
              </div>
            </div>
          ) : !qr ? (
            <button className="btn primary wide" onClick={loadMine} disabled={busy}>
              {busy ? '產生緊…' : '產生我嘅 QR Code'}
            </button>
          ) : (
            <>
              <div style={{
                padding: 14, background: '#fff', borderRadius: 'var(--r)',
                display: 'flex', justifyContent: 'center',
                boxShadow: '0 4px 22px rgba(0,0,0,.35)',
              }} dangerouslySetInnerHTML={{ __html: qr.svg }} />

              <div className="row" style={{ justifyContent: 'center', gap: 9, marginTop: 12 }}>
                <Avatar id={user.avatar} size={38} />
                <div>
                  <div style={{ fontWeight: 900, fontSize: 14 }}>
                    {qr.display_name || user.display_name}
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: 'var(--cyan)' }}>
                    @{qr.username}
                  </div>
                </div>
              </div>

              <div className="sub" style={{
                fontSize: 11, marginTop: 12, textAlign: 'center', lineHeight: 1.85,
              }}>
                畀朋友掃呢個 QR —— 佢會自動加到 @{qr.username}
                <br />
                <span style={{ opacity: .7 }}>用手機原生相機掃都可以（會開個 app）</span>
              </div>

              <div className="row" style={{ gap: 7, marginTop: 11, justifyContent: 'center' }}>
                <button className="btn sm" onClick={() => {
                  const svg = new Blob([qr.svg], { type: 'image/svg+xml' })
                  const url = URL.createObjectURL(svg)
                  const a = document.createElement('a')
                  a.href = url; a.download = `wander-${qr.username}.svg`; a.click()
                  setTimeout(() => URL.revokeObjectURL(url), 1000)
                }}>下載 QR</button>
                <button className="btn sm ghost" onClick={() => {
                  navigator.clipboard?.writeText(qr.url)
                    .then(() => toast('已複製連結 ✓'))
                    .catch(() => toast('複製唔到'))
                }}>複製連結</button>
              </div>
            </>
          )}
        </>
      ) : (
        <>
          <input ref={fileRef} type="file" accept="image/*"
            onChange={scan} style={{ display: 'none' }} />
          <button className="btn primary wide" onClick={() => fileRef.current?.click()}
            disabled={scanning}>
            {scanning ? '解碼緊…' : '📷 揀一張 QR 圖'}
          </button>

          {/* ⚠️ 掃到自己嘅提示（用戶要求）*/}
          {selfHit && (
            <div className="card" style={{
              marginTop: 12, padding: 12,
              borderColor: 'var(--warn)',
              background: 'color-mix(in srgb, var(--warn) 12%, transparent)',
            }}>
              <div style={{ fontWeight: 900, fontSize: 13.5, color: 'var(--warn)' }}>
                ⚠️ {SELF_MSG}
              </div>
              <div className="sub" style={{ fontSize: 11.5, marginTop: 5, lineHeight: 1.8 }}>
                {SELF_HINT}（<b className="mono">@{selfHit}</b>）。
                <br />
                將你嘅 QR 畀<b>朋友</b>掃，佢就可以加到你好友。
              </div>
              <button className="btn sm ghost" style={{ marginTop: 9 }}
                onClick={() => setSelfHit(null)}>知道</button>
            </div>
          )}

          <div className="card" style={{
            marginTop: 12, padding: 12, background: 'var(--surface-2)',
          }}>
            <div className="sub" style={{ fontSize: 11, lineHeight: 1.9 }}>
              <b>點用：</b>
              <br />
              ① 叫朋友開佢嘅「我嘅 QR」
              <br />
              ② 你用手機<b>原生相機</b>影佢個 QR（或者截圖）
              <br />
              ③ 返嚟撳上面「揀一張 QR 圖」→ 揀啱啱嗰張
              <br />
              ④ 自動解出 @帳號名 → 直接發請求
            </div>
          </div>

          <div className="card" style={{
            marginTop: 10, padding: 11, borderColor: 'var(--warn)',
          }}>
            <div className="sub" style={{ fontSize: 10.5, lineHeight: 1.85 }}>
              ⚠️ <b>點解唔可以直接開相機？</b>
              <br />
              瀏覽器規定相機（getUserMedia）只喺 <b>HTTPS</b> 先用得。
              而家係 http:// 區網 IP → 開唔到。
              <br />
              「影相 → 上傳」冇呢個限制，所以用呢個方法。
              <br />
              （部署上 HTTPS 之後就可以加即時掃描）
            </div>
          </div>
        </>
      )}
    </div>
  )
}
