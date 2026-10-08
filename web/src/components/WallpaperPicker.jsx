import { useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'
import { PRESETS, DEFAULT_CLARITY, clarityToDim, dimToClarity } from './Wallpaper'

/**
 * 🖼 揀背景
 * ==========
 *
 * ⚠️⚠️ 用戶要求：
 *   「我哋整一個 function 就係改 wallpaper…可以自訂 wallpaper
 *    咁然後你就可以加返自己嘅相上去。」
 *
 * ⚠️ 兩個來源：
 *   ① 內建 preset（唔使上載，即刻有）
 *   ② 自己張相（會縮圖先上載 —— 手機影相 4MB 直接上傳會好慢）
 */
export default function WallpaperPicker({ user, onChanged }) {
  const [cur, setCur] = useState(user?.wallpaper || '')
  const [busy, setBusy] = useState(false)
  // ⚠️⚠️ 背景清晰度（用戶要求）
  //    「嗰個槓桿應該 100% 係 show 得最清楚，0% 係黑色咁樣囉。」
  //    ⚠️ UI 用**清晰度**（100 = 最清）——
  //       DB 存 `wallpaper_dim`（暗罩強度）→ 儲存時反轉。
  const [clarity, setClarity] = useState(
    user?.wallpaper_dim == null
      ? DEFAULT_CLARITY
      : dimToClarity(user.wallpaper_dim))
  const curIsPhoto = (cur || '').startsWith('/uploads/')

  async function save(value) {
    setBusy(true)
    try {
      await api.setWallpaper(value)
      setCur(value)
      onChanged?.({ wallpaper: value })
      toast(value ? '背景換好咗 ✓' : '用返預設背景')
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  /**
   * ⚠️ 儲存暗罩。
   *
   *   ⚠️ 拖滑桿嗰陣**唔好**每個 pixel 都打 API ——
   *      用 `onChange` 更新畫面（即時預覽）+ `onPointerUp` 才儲存。
   */
  async function saveDim(clarityVal) {
    // ⚠️⚠️ 清晰度 → 暗罩（**二次曲線**）——
    //    唔可以用線性，唔係清晰度 80% 都會明顯變暗（實測 200 → 144）
    const dimVal = clarityToDim(clarityVal)
    try {
      await api.setWallpaperDim(dimVal)
      onChanged?.({ wallpaper_dim: dimVal })
    } catch (e) { toast(e.message) }
  }

  /**
   * ⚠️⚠️ 上載之前一定要**縮圖**。
   *
   *   手機影相郁啲就 4–8 MB，base64 之後再大 33% →
   *   上傳要好耐（用戶以為壞咗）。
   *
   *   ✅ 最長邊 1600px（背景夠用）+ JPEG 0.82 品質。
   *   ⚠️ 用 canvas 而唔係原檔 —— 原檔 8MB 縮完通常 < 400KB。
   */
  async function pickPhoto(file) {
    if (!file) return
    if (!/^image\//.test(file.type)) return toast('要揀圖片')
    setBusy(true)
    try {
      const dataUrl = await shrink(file, 1600, 0.82)
      const r = await api.upload(dataUrl)
      await save(r.url)
    } catch (e) { toast(`上載失敗：${e.message}`) }
    finally { setBusy(false) }
  }

  return (
    <div>
      <div className="wall-grid">
        {PRESETS.map(p => (
          <div key={p.id || 'default'}
            className={`wall-cell ${cur === p.id ? 'on' : ''}`}
            style={{ background: p.css || 'var(--bg)' }}
            onClick={() => !busy && save(p.id)}>
            <span>{p.icon} {p.label}</span>
          </div>
        ))}

        {/* ⚠️ 自己張相 —— 已經有就用佢做預覽 */}
        <label className={`wall-cell ${curIsPhoto ? 'on' : ''}`}
          style={{
            background: curIsPhoto ? `url("${cur}") center/cover` : 'var(--surface-2)',
            display: 'grid', placeItems: 'center',
            color: 'var(--dim)', fontSize: 20, cursor: busy ? 'wait' : 'pointer',
          }}>
          <span style={{ background: 'none', padding: 0 }}>
            {busy ? '…' : (curIsPhoto ? '換相' : '📷 我嘅相')}
          </span>
          <input type="file" accept="image/*" style={{ display: 'none' }}
            disabled={busy}
            onChange={e => pickPhoto(e.target.files?.[0])} />
        </label>
      </div>

      {/* ⚠️⚠️ 暗罩滑桿（用戶要求）
             「可唔可以整一個吧上去 tune 佢，
              由零透明度至到 100% 嘅透明度。」 */}
      {curIsPhoto && (
        <div className="card" style={{ marginTop: 12, padding: '10px 12px' }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 800, fontSize: 12 }}>☀️ 相片清晰度</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--cyan)' }}>
              {clarity}%
            </span>
          </div>
          <input type="range" className="wall-slider" min="0" max="100" step="5"
            value={clarity}
            onChange={e => setClarity(Number(e.target.value))}
            onPointerUp={() => saveDim(clarity)}
            onTouchEnd={() => saveDim(clarity)}
            onKeyUp={() => saveDim(clarity)}
            aria-label="相片清晰度" />
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="sub" style={{ fontSize: 9.5 }}>0% 黑色</span>
            <span className="sub" style={{ fontSize: 9.5 }}>100% 睇得最清</span>
          </div>
          <div className="sub" style={{ fontSize: 10, marginTop: 6, lineHeight: 1.75 }}>
            ✅ <b>100% = 完全冇暗罩</b>（睇得最清）
            <br />
            ⚠️ 調得太高（相太光），啲字可能會睇唔到 ——
            我會自動加**文字陰影**補救（唔會遮住你張相）。
            <br />
            ⚠️ 曲線係**二次**嘅 —— 80% 以上幾乎唔覺暗。
          </div>
        </div>
      )}

      {curIsPhoto && (
        <button className="btn sm ghost" style={{ marginTop: 8 }}
          disabled={busy} onClick={() => save('')}>
          清走我張相
        </button>
      )}

      <div className="sub" style={{ fontSize: 10.5, marginTop: 8, lineHeight: 1.8 }}>
        ⚠️ 相片只會縮到 1600px 先上載（唔會用你原檔）。
        {curIsPhoto && <><br />⚠️ 背景上面有暗罩 —— 唔係嘅話啲字會睇唔到。</>}
      </div>
    </div>
  )
}

/**
 * ⚠️ 用 canvas 縮圖。
 *
 *   ⚠️ 一定要**同時**限制最長邊 —— 横相同直相都要。
 *   ⚠️ 用 `toDataURL('image/jpeg', q)` 而唔係 PNG ——
 *      相片用 PNG 會大 5–10 倍。
 */
function shrink(file, maxSide, quality) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const { width: w, height: h } = img
      const scale = Math.min(1, maxSide / Math.max(w, h))
      const cw = Math.round(w * scale), ch = Math.round(h * scale)
      const c = document.createElement('canvas')
      c.width = cw; c.height = ch
      const ctx = c.getContext('2d')
      ctx.drawImage(img, 0, 0, cw, ch)
      resolve(c.toDataURL('image/jpeg', quality))
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('讀唔到張相')) }
    img.src = url
  })
}
