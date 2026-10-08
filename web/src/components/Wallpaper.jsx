import { useEffect, useState } from 'react'

/**
 * 🖼 自訂背景（Wallpaper）
 * ==========================
 *
 * ⚠️⚠️ 用戶要求：
 *   「我哋整一個 function 就係改 wallpaper？例如就係呢除咗用我哋
 *    一直用緊嗰張嘅背景之外，另外就係有個選項就係加咁樣嘅選項啦…
 *    可以自訂 wallpaper 咁然後你就可以加返自己嘅相上去。」
 *
 * ⚠️ 設計：
 *   · 兩種背景**可以並存**：
 *     ① 你嘅相（`/uploads/xxx.jpg`）
 *     ② 預設氛圍（光暈 + scanline + 星點）
 *   · ⚠️ 相片係**底**，氛圍係**面**（半透明）——
 *     咁樣就算放相都仲有 app 嘅質感，字仲睇得清。
 *   · ⚠️ 相上面一定要有**暗罩**（`scrim`）——
 *     唔係嘅話放一張白雲相，啲字（白色）會完全睇唔到。
 */

/** ⚠️ 內建背景（preset）—— 唔使上載都用得。 */
export const PRESETS = [
  { id: '', label: '預設', icon: '✦',
    css: null },
  { id: 'midnight', label: '午夜', icon: '🌌',
    css: 'radial-gradient(ellipse 120% 80% at 50% 0%, #1e1b4b 0%, #05010f 70%)' },
  { id: 'sunset', label: '日落', icon: '🌇',
    css: 'linear-gradient(180deg, #7c2d12 0%, #4c1d95 45%, #05010f 100%)' },
  { id: 'ocean', label: '深海', icon: '🌊',
    css: 'linear-gradient(180deg, #0c4a6e 0%, #082f49 50%, #05010f 100%)' },
  { id: 'forest', label: '森林', icon: '🌲',
    css: 'linear-gradient(180deg, #14532d 0%, #052e16 55%, #05010f 100%)' },
  { id: 'sakura', label: '櫻花', icon: '🌸',
    css: 'linear-gradient(180deg, #831843 0%, #4a044e 50%, #05010f 100%)' },
]

/** ⚠️ 由 id 攞 preset（搵唔到回預設）。 */
export function presetOf(id) {
  return PRESETS.find(p => p.id === (id || '')) || PRESETS[0]
}

/**
 * 背景圖層。
 *
 * ⚠️ 一定要放喺 `body::before` **之下**（z-index -1）——
 *    唔係嘅話會蓋住啲 card。
 */
/** ⚠️ 暗罩預設值 —— 相上面要有暗罩，唔係啲字睇唔到。 */
export const DEFAULT_DIM = 55

export default function Wallpaper({ value, dim }) {
  const [url, setUrl] = useState(null)

  useEffect(() => {
    const v = value || ''
    const isPhoto = v.startsWith('/uploads/')
    setUrl(isPhoto ? v : null)
    // ⚠️ 順便將 preset 寫入 CSS 變數（body 用）
    const p = presetOf(isPhoto ? '' : v)
    const el = document.documentElement
    if (p.css) el.style.setProperty('--wallpaper-preset', p.css)
    else el.style.removeProperty('--wallpaper-preset')

    // ⚠️⚠️ 用戶要求：暗罩要可以調 0–100
    //    「而家嘅透明度就會有啲低囉，即係睇唔到人哋嘅人樣，
    //      可唔可以整一個吧上去 tune 佢，
    //      由零透明度至到 100% 嘅透明度。」
    //
    //    ⚠️ 只喺**有相**嗰陣先套用 —— preset 本身已經夠暗，
    //       再加暗罩會變全黑。
    const d = isPhoto
      ? Math.max(0, Math.min(100, Number(dim ?? DEFAULT_DIM) || 0))
      : 0
    el.style.setProperty('--wall-dim', String(d))

    // ⚠️⚠️ 暗罩薄嗰陣，字會睇唔到 —— 用**文字陰影**補救。
    //    ⚠️ 為咩唔用更厚嘅暗罩：用戶明確話要睇到人樣。
    //       text-shadow 唔會遮住張相，係最好嘅折衷。
    const shadow = d < 45
      ? (d < 15
        // 幾乎冇暗罩 → 重陰影
        ? '0 1px 3px rgba(0,0,0,.95), 0 0 12px rgba(0,0,0,.85)'
        // 中等 → 輕陰影
        : '0 1px 2px rgba(0,0,0,.75)')
      : 'none'
    el.style.setProperty('--wall-shadow', shadow)

    // ⚠️ 記得標記「而家有背景相」—— CSS 靠呢個 selector
    if (isPhoto) document.body.setAttribute('data-wallpaper', '1')
    else document.body.removeAttribute('data-wallpaper')
  }, [value, dim])

  if (!url) return null

  return (
    <>
      {/* ⚠️⚠️ 兩層：
            ① `.wallpaper-img` —— 你張相
            ② `.wallpaper-scrim` —— 暗罩（令啲字睇得清）
          ⚠️ 暗罩唔可以冇 —— 放一張白雲相啲字會消失。 */}
      <div className="wallpaper-img" style={{ backgroundImage: `url("${url}")` }}
        aria-hidden />
      <div className="wallpaper-scrim" aria-hidden />
    </>
  )
}
