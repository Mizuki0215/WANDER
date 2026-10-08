import { avatarSvg, isPixelAvatar, AVATAR_MAP } from '../lib/avatars'

/**
 * 頭像元件。
 *
 * ⚠️ 支援兩種格式：
 *   · 像素 id（"star"）→ 用 SVG 畫
 *   · URL（舊資料 / 上傳相）→ <img>
 *   唔可以假設一定係其中一種 —— 舊用戶嘅資料可能係 URL。
 */
export default function Avatar({ id, size = 36, ring = false, style }) {
  const px = isPixelAvatar(id)
  const a = px ? AVATAR_MAP[id] : null

  const base = {
    width: size, height: size, flex: `0 0 ${size}px`,
    borderRadius: Math.round(size * 0.24),
    background: px ? '#241b45' : 'var(--surface-2)',
    border: ring ? '2px solid var(--border-hi)' : '1px solid var(--border)',
    overflow: 'hidden',
    display: 'block',
    ...style,
  }

  if (px) {
    return (
      <span style={base} title={a.name}
        dangerouslySetInnerHTML={{ __html: avatarSvg(id, { size }) }} />
    )
  }
  if (id) {
    return <img src={id} alt="" style={{ ...base, objectFit: 'cover' }} />
  }
  return (
    <span style={{ ...base, display: 'flex', alignItems: 'center',
                   justifyContent: 'center', fontSize: size * 0.5 }}>✦</span>
  )
}
