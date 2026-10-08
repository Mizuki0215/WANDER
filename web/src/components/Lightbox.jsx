import { useEffect } from 'react'

/**
 * 全圖檢視（Lightbox）
 * ====================
 * ⚠️ 為咩需要呢個：
 *   列表用正方形縮圖（每行高度一致，列表整齊），
 *   但正方形裁切會切走直向相嘅上下部分。
 *   所以一定要有個「撳一下睇全圖」嘅出口 ——
 *   否則用戶上傳咗相但睇唔到成張。
 *
 * ⚠️ 用 object-fit: contain 而唔係 cover —— 全圖唔可以再裁。
 */
export default function Lightbox({ src, title, subtitle, onClose }) {
  // 撳 Esc 關閉（桌面）
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', h)
    // 鎖住背景捲動
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', h)
      document.body.style.overflow = prev
    }
  }, [onClose])

  if (!src) return null

  return (
    <div className="lightbox" onClick={onClose}>
      <button className="lb-x" onClick={onClose} aria-label="關閉">✕</button>
      <img src={src} alt={title || ''} onClick={e => e.stopPropagation()} />
      {(title || subtitle) && (
        <div onClick={e => e.stopPropagation()}>
          {title && <div className="lb-cap">{title}</div>}
          {subtitle && <div className="lb-sub" style={{ textAlign: 'center' }}>{subtitle}</div>}
        </div>
      )}
      <div className="lb-sub" style={{
        position: 'absolute', bottom: 'calc(14px + var(--safe-b))', textAlign: 'center',
      }}>
        撳畫面任何位置關閉
      </div>
    </div>
  )
}
