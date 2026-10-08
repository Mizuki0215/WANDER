import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'

import PixelIcon from './PixelIcon'

/**
 * 新手教學（Onboarding）
 * =======================
 * 用戶要求：
 *   「如果你去註冊一個新用戶，首先登入咗之後出現咗個 Animation 之後呢，
 *    然後就會第一次用嘅話呢係可以會有一個示範教學點樣去用嘅，
 *    就例如你可能有一個提示啊，例如圈出嚟點樣去用啊，
 *    或者可能你可以用嗰「Pixel 風」風格嘅人物去介紹呢個 Apps 係點用啦，
 *    咁然後之後呢佢就會同你講話你叫乜嘢名，咁呢個時候呢你就可以改你嘅名叫乜嘢名，
 *    呢個係必做嘅。」
 *
 * 流程：
 *   ① 吉祥物打招呼，自我介紹
 *   ② 逐個 app「圈出嚟」講解（Planner / Money / Shopping / Friends）
 *   ③ **一定要填名**（唔可以跳過）
 *   ④ 完成
 *
 * ⚠️⚠️ 為咩「圈出嚟」而唔係彈一段文字：
 *    手機用戶唔會睇文字教學。但如果我哋**指出實際嗰粒掣**，
 *    用戶一眼就知邊度撳 —— 呢個係最有效嘅引導方式。
 *
 * ⚠️⚠️ 為咩最後一定要填名：
 *    冇名嘅話，行程度顯示「you@example.com」、
 *    分帳度顯示「usr_x7Kd9」—— 完全唔知邊個係邊個。
 *    所以寧願喺呢一步逼一逼，都好過之後成個 app 都顯示亂碼 ID。
 */

const TOUR = [
  { target: 'calendar', frame: 'point', title: 'Planner 行程',
    body: '貼咗 link 或者加咗景點之後，呢度會幫你按區域自動排好每日去邊。' },
  { target: 'money', frame: 'point', title: 'Money 分帳',
    body: '邊個墊支就記落嚟，最後自動計返「邊個要比錢邊個」，最少轉帳次數。' },
  { target: 'shopping', frame: 'point', title: 'Shopping 購物',
    body: '分工買嘢 —— 買完剔咗就唔會買雙份。可以加相、寫價錢。' },
  { target: 'friends', frame: 'point', title: 'Friends 朋友',
    body: '用 @帳號名加朋友，或者互相掃 QR。一齊計劃同一個旅程。' },
]

/** 量度目標元素喺畫面嘅位置。 */
function useTargetRect(id, on) {
  const [rect, setRect] = useState(null)
  const measure = useCallback(() => {
    if (!id || !on) { setRect(null); return null }
    const el = document.querySelector(`[data-tour="${id}"]`)
    if (!el) { setRect(null); return null }
    const r = el.getBoundingClientRect()
    const pad = 8
    const out = {
      top: r.top - pad, left: r.left - pad,
      width: r.width + pad * 2, height: r.height + pad * 2,
      cx: r.left + r.width / 2, cy: r.top + r.height / 2,
    }
    setRect(out)
    return out
  }, [id, on])

  useLayoutEffect(() => { measure() }, [measure])
  useEffect(() => {
    if (!on) return
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [measure, on])
  return rect
}

export default function Onboarding({ user, onDone, replay = false }) {
  /**
   * ⚠️⚠️ 用戶要求：
   *   「因為你係第一次創建呢個 Account 嘅時候，你先至叫你去改名。
   *    所以之後呢…喺 setting 嗰度如果你再想睇多次嗰個示範教學，
   *    係唔需要再 show 多次叫你去打自己個名嘅嗰一版。
   *    淨係教佢啲 Apps 點用就 OK。」
   *
   * → `replay = true`（由設定頁重看）時：
   *      · **跳過「改名」** —— 個名第一次已經填咗
   *      · **亦都跳過「歡迎」** —— 用戶唔係第一次，唔需要再自我介紹
   *      · 只淨低 app 導覽 + 完成
   *
   * ⚠️⚠️ 為咩改用「明確步驟清單」而唔係索引算術：
   *    舊版係 `NAME_STEP = TOUR.length + 1` 呢種…
   *    一改步驟數就要改好多處（total / 每個條件 / 進度 %），
   *    而且 replay 要跳步 → 算術即刻變地獄。
   *    用清單就只需要改一個地方，`total` 自動跟。
   */
  const steps = useMemo(() => {
    const out = []
    if (!replay) out.push('welcome')
    TOUR.forEach((_, i) => out.push(`tour:${i}`))
    if (!replay) out.push('name')
    out.push('done')
    return out
  }, [replay])

  const [step, setStep] = useState(0)
  const [name, setName] = useState(user?.display_name || '')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef(null)

  const total = steps.length
  const kind = steps[Math.min(step, total - 1)]
  const isWelcome = kind === 'welcome'
  // ⚠️ `tour:` 前綴令「邊一步」同「邊個 app」都一目了然
  const isTour = kind.startsWith('tour')
  const tourIdx = isTour ? Number(kind.slice(5)) : -1
  const isName = kind === 'name'
  const isDone = kind === 'done'

  const current = isTour ? TOUR[tourIdx] : null
  const rect = useTargetRect(current?.target, isTour)

  // ⚠️ 如果搵唔到目標（例如用戶唔喺主畫面）→ 自動跳過嗰一步，
  //    唔好停喺一個空白嘅黑幕（用戶會以為壞咗）。
  useEffect(() => {
    if (!isTour) return
    if (rect) return
    // ⚠️ 搵唔到目標 → 跳去下一步（唔好停喺空白黑幕）
    const t = setTimeout(() => {
      setStep(s2 => {
        const k = steps[Math.min(s2, steps.length - 1)]
        if (!k?.startsWith('tour')) return s2
        const idx = Number(k.slice(5))
        return document.querySelector(`[data-tour="${TOUR[idx]?.target}"]`)
          ? s2 : Math.min(s2 + 1, steps.length - 1)
      })
    }, 420)
    return () => clearTimeout(t)
  }, [isTour, rect, steps])

  useEffect(() => {
    if (isName) setTimeout(() => inputRef.current?.focus(), 220)
  }, [isName])

  /**
   * ⚠️ 完成。
   *   · 第一次 → 要寫名（`finishOnboard`）
   *   · 重看   → **唔使寫名**，直接閂咗個 overlay
   *     （唔可以喺重看嗰陣再叫 `finishOnboard` —— 咁樣會將
   *      用戶喺設定改過嘅名蓋返做輸入框嗰個舊值）
   */
  async function finish() {
    if (replay) { onDone?.(name.trim()); return }
    const n = name.trim()
    if (!n) return toast('請填你嘅名（呢個係必填）')
    setBusy(true)
    try {
      const r = await api.finishOnboard(n)
      toast(`你好，${r.display_name}！`)
      onDone?.(r.display_name)
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  function next() {
    // ⚠️ 改名嗰步唔可以「下一步」跳過 —— 一定要撳「開始用」
    if (isName || isDone) return finish()
    setStep(s2 => Math.min(s2 + 1, total - 1))
  }
  function back() { if (step > 0) setStep(s => s - 1) }

  // ⚠️ 呢啲名要對應 web/public/mascot-*.png
  const frame = isWelcome ? 'hello'
    : (isTour ? 'point' : 'happy')
  const pct = Math.round((step / Math.max(1, total - 1)) * 100)

  return (
    <div className="onb">
      {/* ══ 聚光燈：遮住全部，淨係露目標出嚟 ══ */}
      {isTour && rect && (
        <svg className="onb-mask" width="100%" height="100%">
          <defs>
            <mask id="onb-hole">
              <rect width="100%" height="100%" fill="white" />
              {/* 挖一個方角窿（像素風唔用圓角） */}
              <rect x={rect.left} y={rect.top}
                width={rect.width} height={rect.height} fill="black" />
            </mask>
          </defs>
          <rect width="100%" height="100%" fill="rgba(4,2,10,.86)" mask="url(#onb-hole)" />
          {/* 像素風外框：硬邊、兩層 */}
          <rect x={rect.left} y={rect.top} width={rect.width} height={rect.height}
            fill="none" stroke="#22d3ee" strokeWidth="3" />
          <rect x={rect.left - 4} y={rect.top - 4}
            width={rect.width + 8} height={rect.height + 8}
            fill="none" stroke="#a855f7" strokeWidth="2" />
        </svg>
      )}
      {/* 唔喺導覽嗰陣，用普通黑幕 */}
      {!isTour && <div className="onb-dim" />}

      <div className="onb-box" style={{
        // ⚠️⚠️ 用 `align` 而唔係**負 margin** ——
        //    第一版用 marginTop:-120px 推個盒，內容長嗰陣
        //    會推出畫面外面，個掣就撳唔到。
        //    改用 flex alignment，永遠留喺畫面內。
        alignSelf: (isTour && rect && rect.cy < window.innerHeight * 0.5)
          ? 'flex-end' : 'flex-start',
      }}>
        {/* ══ 吉祥物 ══ */}
        {/*   ⚠️⚠️ 兩層來源（用戶揀咗「A 方案」：佢自己生成角色圖）：
               ① `/mascot-X.png`      —— 用戶自己生成嗰張（如果有）
               ② `/proc/mascot-X.png` —— 我程序化畫嗰張（fallback）

               ⚠️ 為咩唔喺 build 時決定：
                  因為用戶可以**隨時**放圖入 public/ 而唔使重新 build。
                  用 `onError` 喺 runtime fallback 就最簡單又最穩。

               ⚠️ 一定要 `onError` 而唔係判斷檔案存在 ——
                  瀏覽器冇同步方法可以「檢查檔案存在」。 */}
        <div className="onb-mascot">
          <img className="onb-bubble" alt=""
            src={`/mascot-${frame}.png`}
            onError={(e) => {
              // ⚠️ 防止無限迴圈：fallback 都失敗就唔再試
              if (e.currentTarget.dataset.fb) return
              e.currentTarget.dataset.fb = '1'
              e.currentTarget.src = `/proc/mascot-${frame}.png`
            }} />
        </div>

        {/* ══ 內容（可滾動）══ */}
        {/*   ⚠️⚠️ 用戶報嘅 bug：
                「撳到去第一版佢介紹 planner 嗰陣時候呢，
                  冇一個 button 或者個 bug 太下面啦，
                  所以導致到你撳唔到之後介紹嘅嘢」
              原因：個盒 max-height 82vh + overflow-y auto，
                    但**掣都喺同一個滾動區**→ 內容長就捲走咗個掣。
              修法：內容同掣分開 —— 內容可捲，掣永遠固定喺盒底。 */}
        <div className="onb-scroll">
        {isWelcome && (
          <>
            <div className="onb-title">你好！我係嚮導</div>
            <div className="onb-body">
              Wander 幫你<b>計劃旅行</b>：貼 link、分區排行程、
              分帳、購物清單，仲可以同朋友一齊夾。
              <br /><br />我用 30 秒帶你睇下有咩玩 👇
            </div>
          </>
        )}

        {isTour && current && (
          <>
            <div className="onb-badge">
              <PixelIcon name={current.target} size={16} />
              第 {tourIdx + 1} / {TOUR.length} 個 app
            </div>
            <div className="onb-title">{current.title}</div>
            <div className="onb-body">{current.body}</div>
            {!rect && (
              <div className="onb-body" style={{ color: 'var(--warn)', fontSize: 11 }}>
                （搵唔到嗰粒掣，跳過…）
              </div>
            )}
          </>
        )}

        {isName && (
          <>
            <div className="onb-title">你叫乜嘢名？</div>
            <div className="onb-body">
              呢個係<b>必填</b> —— 因為行程、分帳、購物清單都會顯示你個名。
              <br />
              <span style={{ opacity: .75, fontSize: 11 }}>
                （唔填嘅話，朋友只會見到你嘅 email）
              </span>
            </div>
            <input ref={inputRef} className="input onb-input" value={name}
              placeholder="例如：小明、Alice"
              maxLength={40}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && finish()} />
            {!name.trim() && (
              <div className="onb-body" style={{ color: 'var(--warn)', fontSize: 11, marginTop: 6 }}>
                ⚠️ 一定要填先可以繼續
              </div>
            )}
          </>
        )}

        {isDone && (
          <>
            <div className="onb-title">搞掂！</div>
            <div className="onb-body">
              你好 <b>{name.trim()}</b> 👋
              <br /><br />
              而家去<b>旅程</b>開一個，就可以開始計劃啦。
            </div>
          </>
        )}

        </div>

        {/* ══ 進度 ══ */}
        <div className="onb-bar">
          <div className="onb-bar-fill" style={{ width: `${pct}%` }} />
        </div>

        {/* ══ 掣 ══ */}
        <div className="onb-actions">
          {!isWelcome && !isDone && (
            <button className="btn ghost" onClick={back}>‹ 上一步</button>
          )}
          {!isWelcome && (
            <span className="onb-count pix">{step + 1}/{total}</span>
          )}
          {/* ⚠️ replay（重看）冇「改名」步 → 唔會有「開始用」呢個特別掣 */}
          {(!isName && !isDone) ? (
            <button className="btn primary" onClick={next}>
              下一步 ›
            </button>
          ) : isName ? (
            <button className="btn primary" onClick={finish} disabled={busy || !name.trim()}>
              {busy ? '儲存緊…' : '開始用 Wander'}
            </button>
          ) : (
            <button className="btn primary" onClick={() => onDone?.(name.trim())}>
              {replay ? '完成 ✓' : '開始用 Wander'}
            </button>
          )}
        </div>

        {/* ⚠️ 只有中間嘅導覽步驟可以先跳過 —— 改名嗰步唔可以 */}
        {isTour && (
          <button className="onb-skip"
            onClick={() => setStep(steps.findIndex(k => k === 'name' || k === 'done'))}>
            {replay ? '跳過教學' : '跳過教學，直接改名'}
          </button>
        )}
      </div>
    </div>
  )
}
