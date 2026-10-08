import { useEffect, useState } from 'react'
import { subscribe, applyUpdate } from '../lib/pwa'

/**
 * 頂部狀態條：離線提示 / 更新提示 / 安裝提示
 * 只在有嘢要講嘅時候先出現，唔阻住 UI。
 */
export default function PwaBar() {
  const [s, setS] = useState({ online: true, updateReady: false })
  const [installEvt, setInstallEvt] = useState(null)
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem('wander.hideInstall') === '1' } catch { return false }
  })
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
  const standalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true

  useEffect(() => subscribe(setS), [])

  useEffect(() => {
    const h = (e) => { e.preventDefault(); setInstallEvt(e) }
    window.addEventListener('beforeinstallprompt', h)
    return () => window.removeEventListener('beforeinstallprompt', h)
  }, [])

  function hideInstall() {
    setDismissed(true)
    try { sessionStorage.setItem('wander.hideInstall', '1') } catch {}
  }

  // ① 離線
  if (!s.online) {
    return (
      <Bar tone="warn" icon="📴">
        離線模式 — 睇得到已快取嘅行程同地圖圖磚
      </Bar>
    )
  }

  // ② 有新版本
  if (s.updateReady) {
    return (
      <Bar tone="neon" icon="sparkle" action={{ label: '更新', onClick: applyUpdate }}>
        有新版本
      </Bar>
    )
  }

  // ③ 安裝提示（未安裝 + 未關閉）
  if (!standalone && !dismissed) {
    if (installEvt) {
      return (
        <Bar tone="cyan" icon="📲"
          action={{ label: '安裝', onClick: async () => {
            installEvt.prompt()
            const r = await installEvt.userChoice
            if (r?.outcome === 'accepted') hideInstall()
            setInstallEvt(null)
          } }}
          onClose={hideInstall}>
          加到主畫面，離線都用得
        </Bar>
      )
    }
    if (isIOS) {
      return (
        <Bar tone="cyan" icon="📲" onClose={hideInstall}>
          撳「分享」→「加到主畫面」就有離線功能
        </Bar>
      )
    }
  }

  return null
}

function Bar({ tone, icon, children, action, onClose }) {
  const color = { warn: 'var(--warn)', neon: 'var(--neon)', cyan: 'var(--cyan)' }[tone] || 'var(--cyan)'
  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 60,
      display: 'flex', alignItems: 'center', gap: 9,
      padding: '9px 14px calc(9px + 0px)',
      background: 'color-mix(in srgb, var(--surface-2) 96%, transparent)',
      borderBottom: `1px solid ${color}`,
      backdropFilter: 'blur(12px)', fontSize: 12, fontWeight: 600,
    }}>
      <span>{icon}</span>
      <span style={{ flex: 1, minWidth: 0 }}>{children}</span>
      {action && (
        <button className="btn sm" style={{ borderColor: color, color }} onClick={action.onClick}>
          {action.label}
        </button>
      )}
      {onClose && (
        <button onClick={onClose} style={{ color: 'var(--dim)', fontSize: 15, padding: '0 4px' }}>✕</button>
      )}
    </div>
  )
}
