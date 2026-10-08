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
/**
 * ⚠️ 預設**清晰度**（0–100）。
 *
 *   ⚠️⚠️ 用戶要求：「嗰個槓桿應該 100% 係 show 得最清楚，
 *      0% 係黑色」+「真係要完全擺上去要清晰」。
 *
 *   ⚠️ 所以預設 **80**（好清，睇到人樣）——
 *      唔係最初嘅 45（太暗，睇唔到人）。
 *   ⚠️ 剩返嘅可讀性由 **text-shadow** 補救（dim 20 < 45 → 有陰影）。
 */
export const DEFAULT_CLARITY = 80

/**
 * ⚠️ DB 存嘅係**暗罩強度**（100 = 最黑）。
 *   ⚠️ 第一次寫入嘅係 55（暗罩），而家 UI 用清晰度 —— 要反轉。
 */
export const DEFAULT_DIM = DEFAULT_CLARITY

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
    // ⚠️⚠️⚠️ 用戶報：「你仲係搞唔清楚最清晰同埋最黑係相反咗啊，
    //    即係話呢咁你應該要將個功能掉轉返囉」
    //
    //    🚨 根因：**雙重反轉**！
    //
    //    ⚠️ 呢個 prop（`dim`）由 App 傳入嘅係
    //       `user.wallpaper_dim` —— 即係**已經係暗罩強度**。
    //       但我當咗佢係「清晰度」再反轉一次：
    //         clarity = dim          ← 錯（dim 唔係 clarity）
    //         d = 100 - clarity      ← 再反轉 → 雙重反轉
    //
    //       → 用戶拉 100%（最清）→ 存 dim=0 → render 時
    //         d = 100 - 0 = 100 → **全黑**（完全相反）
    //
    //    ✅ 修法：**反轉只喺 Picker 做一次**（UI 清晰度 → 存 dim）。
    //       呢度 `dim` 已經係最終暗罩強度 → **直接用**。
    const d = isPhoto
      ? Math.max(0, Math.min(100, Number(dim ?? (100 - DEFAULT_CLARITY)) || 0))
      : 0
    el.style.setProperty('--wall-dim', String(d))

    // ⚠️ 除錯用：喺 console 睇得到實際值
    if (isPhoto && typeof console !== 'undefined') {
      // eslint-disable-next-line no-console
      console.debug?.('[wallpaper] dim =', d, '→ 清晰度', 100 - d)
    }

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
