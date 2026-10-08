import { useEffect, useRef, useState } from 'react'

/**
 * 開機動畫（Boot Screen）
 * =======================
 * 用戶要求（原文）：
 *   「登入後有 animation like 一個畫面 loading（扮的）
 *     我要素象 style，有一個 bar show loading，
 *     下面有一個素象 style 字體 show percentage」
 *
 * ⚠️ 老實講：呢個係**扮嘅** loading —— 冇真正嘢喺度載入。
 *    但佢有真實作用：
 *      · 遮住 app 初始化（讀 /api/me、攞 trips）嘅空窗
 *      · 建立「呢個係一部裝置」嘅心理暗示
 *      · 睇落專業（產品感）
 *
 *    所以個進度係**故意設計過嘅節奏**，唔係隨機：
 *      0   → 12   開機自檢
 *      12  → 34   連線
 *      34  → 58   同步旅程
 *      58  → 82   準備地圖
 *      82  → 100  完成
 *    每段速度唔同，開頭慢（似真）、中段快、結尾微慢（等一等再彈入）。
 */

const STEPS = [
  { at: 0, text: 'WANDER OS 初始化' },
  { at: 14, text: '連線到伺服器' },
  { at: 34, text: '同步旅程資料' },
  { at: 58, text: '準備離線地圖' },
  { at: 82, text: '就緒' },
]

export default function BootScreen({ onDone, minMs = 2400 }) {
  const [pct, setPct] = useState(0)
  const [leaving, setLeaving] = useState(false)
  const fired = useRef(false)

  useEffect(() => {
    const start = performance.now()
    let raf = 0

    // 進度曲線：開頭慢、中間快、結尾微慢
    const curve = (t) => {
      if (t < 0.15) return (t / 0.15) * 14                      // 0-14  慢
      if (t < 0.55) return 14 + ((t - 0.15) / 0.40) * 44        // 14-58 快
      if (t < 0.85) return 58 + ((t - 0.55) / 0.30) * 34        // 58-92 中
      return 92 + ((t - 0.85) / 0.15) * 8                       // 92-100 微慢
    }

    const tick = (now) => {
      const t = Math.min(1, (now - start) / minMs)
      setPct(curve(t))
      if (t < 1) {
        raf = requestAnimationFrame(tick)
      } else if (!fired.current) {
        fired.current = true
        setPct(100)
        setTimeout(() => {
          setLeaving(true)
          setTimeout(() => onDone?.(), 420)
        }, 260)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [minMs, onDone])

  const shown = Math.floor(pct)
  const step = [...STEPS].reverse().find(s => shown >= s.at) || STEPS[0]
  const blocks = 28
  const filled = Math.round((shown / 100) * blocks)

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 999,
      background: 'radial-gradient(120% 90% at 50% 0%, #1a0f35 0%, #0b0518 60%, #06030e 100%)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '0 28px', gap: 0,
      opacity: leaving ? 0 : 1,
      transform: leaving ? 'scale(1.06)' : 'scale(1)',
      transition: 'opacity .42s ease, transform .42s ease',
    }}>
      {/* 背景掃描線 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.16,
        background: 'repeating-linear-gradient(0deg, transparent 0 2px, #a855f7 2px 3px)',
      }} />

      {/* LOGO */}
      <div style={{
        fontFamily: '"Press Start 2P", ui-monospace, monospace',
        fontSize: 30, fontWeight: 400, letterSpacing: 3,
        background: 'linear-gradient(100deg,#a855f7,#22d3ee 60%,#f472b6)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        backgroundClip: 'text', marginBottom: 6, lineHeight: 1,
      }}>WANDER</div>
      <div className="mono" style={{
        fontSize: 10, letterSpacing: 4.5, color: '#7c6bb0', marginBottom: 40,
        fontFamily: '"Press Start 2P", ui-monospace, monospace',
      }}>TRAVEL SYSTEM v2.0</div>

      {/* ══ 像素進度條 ══ */}
      <div style={{
        display: 'flex', gap: 3, marginBottom: 18,
        filter: 'drop-shadow(0 0 12px rgba(168,85,247,.5))',
      }}>
        {Array.from({ length: blocks }, (_, i) => {
          const on = i < filled
          const isHead = i === filled - 1
          return (
            <div key={i} style={{
              width: 9, height: 26, borderRadius: 1.5,
              background: on
                ? (isHead ? '#22d3ee' : '#a855f7')
                : 'rgba(168,85,247,.13)',
              boxShadow: on ? `0 0 ${isHead ? 14 : 6}px ${isHead ? '#22d3ee' : '#a855f7'}` : 'none',
              transition: 'background .09s linear, box-shadow .09s linear',
            }} />
          )
        })}
      </div>

      {/* ══ 像素字體百分比 ══ */}
      {/* ⚠️ 用「Press Start 2P」像素字體 —— 佢喺 index.html 已經 preload 咗
          （之前 preload 咗但冇用到，浪費）。像素字體好闊，所以 font-size 要細啲。 */}
      <div style={{
        fontFamily: '"Press Start 2P", "SF Mono", ui-monospace, monospace',
        fontSize: 30, lineHeight: 1.45,
        color: '#22d3ee', letterSpacing: 1,
        textShadow: '0 0 18px rgba(34,211,238,.7), 0 0 48px rgba(34,211,238,.35), '
                  + '2px 2px 0 rgba(168,85,247,.5)',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {String(shown).padStart(3, '0')}<span style={{ fontSize: 16, opacity: .75 }}>%</span>
      </div>

      {/* 狀態文字 */}
      <div className="mono" style={{
        fontSize: 11, color: '#8b7cc0', marginTop: 12, letterSpacing: 1.6,
        minHeight: 16,
      }}>
        {step.text}
        <span style={{ animation: 'blink 1s steps(1) infinite' }}>_</span>
      </div>

      {/* 底部細節 */}
      <div className="mono" style={{
        position: 'absolute', bottom: 30, fontSize: 9, color: '#4a3d70',
        letterSpacing: 1.4, textAlign: 'center', lineHeight: 2,
      }}>
        MEM 128MB OK · NET OK · GEO 134655 CITIES<br />
        <span style={{ opacity: .6 }}>撳畫面可以跳過</span>
      </div>

      {/* 撳一下就跳過 */}
      <button onClick={() => { if (!fired.current) { fired.current = true; setLeaving(true); setTimeout(() => onDone?.(), 300) } }}
        aria-label="跳過"
        style={{ position: 'absolute', inset: 0, background: 'none', border: 'none', cursor: 'pointer' }} />
    </div>
  )
}
