import { useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'
import { PIXEL_AVATARS } from '../lib/avatars'
import Avatar from './Avatar'

/**
 * 像素頭像選擇器
 * ==============
 * 用戶要求：
 *   「setting 可以改自己嘅 icon（畀啲像素 style 佢哋選）
 *    （同 animation 個 style 一樣，可以 choose moon / star / cloud / flower / ring …）」
 */
export default function AvatarPicker({ user, onUserUpdate }) {
  const [sel, setSel] = useState(user?.avatar || '')
  const [busy, setBusy] = useState(false)

  async function pick(id) {
    if (busy || id === sel) return
    setSel(id)
    setBusy(true)
    try {
      await api.updateMe({ avatar: id })
      onUserUpdate?.({ avatar: id })
      toast(`換咗「${PIXEL_AVATARS.find(a => a.id === id)?.name}」✓`)
    } catch (e) { toast(e.message); setSel(user?.avatar || '') }
    finally { setBusy(false) }
  }

  return (
    <div>
      <div className="row" style={{ marginBottom: 11 }}>
        <Avatar id={sel} size={64} ring />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 900, fontSize: 14 }}>
            {PIXEL_AVATARS.find(a => a.id === sel)?.name || '未揀'}
          </div>
          <div className="sub" style={{ fontSize: 10.5, marginTop: 2 }}>
            {PIXEL_AVATARS.length} 個可以揀 · 撳一下即刻換
          </div>
        </div>
      </div>

      <div style={{
        // ⚠️ 由 54px 加到 62px —— 16×16 嘅頭像需要更大先睇到細節
        //    （8×8 年代 54px 就夠，16×16 太細會睇唔出眼同腮紅）
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(62px, 1fr))',
        gap: 10,
      }}>
        {PIXEL_AVATARS.map(a => {
          const on = sel === a.id
          return (
            <button key={a.id} onClick={() => pick(a.id)} title={a.name}
              style={{
                background: on ? 'var(--surface-2)' : 'transparent',
                border: on ? '2px solid var(--cyan)' : '2px solid transparent',
                borderRadius: 'var(--r-sm)', padding: 4, cursor: 'pointer',
                boxShadow: on ? '0 0 14px rgba(34,211,238,.4)' : 'none',
                transform: on ? 'scale(1.06)' : 'scale(1)',
                transition: 'transform .15s cubic-bezier(.34,1.56,.64,1)',
                WebkitTapHighlightColor: 'transparent',
              }}>
              <Avatar id={a.id} size={52} />
              <div className="sub" style={{ fontSize: 8.5, marginTop: 3, textAlign: 'center' }}>
                {a.name}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
