import { iconSvg, hasIcon } from '../lib/pixelicons'

/**
 * 像素圖示元件
 * ============
 * ⚠️ 用 SVG 而唔用 emoji ——
 *   emoji 每部機唔同樣，而且冇得控制線條，做唔到像素風。
 *
 * ⚠️ `shape-rendering: crispEdges` 由 iconSvg 內部設定；
 *    呢度再加 `imageRendering: 'pixelated'` 防止瀏覽器喺
 *    非整數倍縮放時做插值（會令格邊變灰）。
 */
export default function PixelIcon({
  name, size = 28, color, className = '', style, title,
}) {
  if (!hasIcon(name)) {
    // ⚠️ 唔可以靜靜咁唔顯示 —— 出一個明顯嘅問號，方便發現打錯 id
    return (
      <span title={`冇呢個圖示：${name}`} style={{
        display: 'inline-block', width: size, height: size, lineHeight: `${size}px`,
        textAlign: 'center', color: 'var(--warn)', fontSize: size * 0.6,
        ...style,
      }}>?</span>
    )
  }
  const svg = iconSvg(name, { size })
  return (
    <span
      className={`pxi ${className}`}
      title={title}
      aria-label={title || name}
      style={{
        display: 'inline-block',
        width: size, height: size,
        lineHeight: 0,
        // ⚠️ 防止插值造成灰邊
        imageRendering: 'pixelated',
        ...(color ? { color } : null),
        ...style,
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
