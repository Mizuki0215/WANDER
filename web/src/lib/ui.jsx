import PixelIcon from '../components/PixelIcon'
import { hasIcon } from '../lib/pixelicons'
import { useEffect, useState } from 'react'

/** 全 App 共用嘅 toast。 */
let toastFn = null
export function Toast() {
  const [msg, setMsg] = useState('')
  const [show, setShow] = useState(false)
  useEffect(() => {
    toastFn = (m) => {
      setMsg(m); setShow(true)
      clearTimeout(window.__wt)
      window.__wt = setTimeout(() => setShow(false), 1800)
    }
    return () => { toastFn = null }
  }, [])
  return <div className={`toast ${show ? 'show' : ''}`}>{msg}</div>
}
export const toast = (m) => toastFn && toastFn(m)

/** 星星背景（銀河主題用） */
export function Stars({ count = 50 }) {
  const [dots] = useState(() =>
    Array.from({ length: count }, () => ({
      l: Math.random() * 100, t: Math.random() * 100,
      s: Math.random() < .16 ? 2 : 1,
      c: ['#fff', '#c4b5fd', '#67e8f9', '#f9a8d4'][Math.floor(Math.random() * 4)],
      d: (Math.random() * 3.4).toFixed(2), u: (2.4 + Math.random() * 2.6).toFixed(2),
    })))
  return (
    <div className="stars" aria-hidden>
      {dots.map((d, i) => (
        <i key={i} style={{
          left: `${d.l}%`, top: `${d.t}%`, width: d.s, height: d.s,
          background: d.c, animationDelay: `${d.d}s`, animationDuration: `${d.u}s`,
        }} />
      ))}
    </div>
  )
}

export function Spinner() { return <span className="spin" /> }

export function Confidence({ value }) {
  const n = Number(value) || 0
  const cls = n >= 85 ? 'hi' : n >= 65 ? 'md' : 'lo'
  return <span className={`conf ${cls}`}>{n}%</span>
}

/**
 * ⚠️ icon 可以係：
 *   · 像素圖示名（"sparkle"、"calendar"）→ 用 PixelIcon 畫
 *   · 任何其他字串（emoji / 文字）→ 直接顯示
 * 咁樣舊嘅呼叫唔會爛，新嘅可以用像素圖。
 */
export function Empty({ icon = 'sparkle', title, hint }) {
  const isPixel = typeof icon === 'string' && hasIcon(icon)
  return (
    <div className="empty">
      {isPixel
        ? <span className="big"><PixelIcon name={icon} size={44} /></span>
        : <span className="big">{icon}</span>}
      <div style={{ fontWeight: 700, color: 'var(--text)' }}>{title}</div>
      {hint && <div style={{ marginTop: 6 }}>{hint}</div>}
    </div>
  )
}
