import { useMemo, useState } from 'react'
import { iconFor, confClass } from '../lib/api'
import { toast } from '../lib/ui'
import PixelIcon from './PixelIcon'

/** ⚠️ Fallback：如果 App 冇傳 onBack，用 hash 令瀏覽器返主畫面。 */
function setTabHome() {
  try { window.location.hash = '' ; window.dispatchEvent(new HashChangeEvent('hashchange')) } catch {}
  try { window.location.assign('/') } catch {}
}

/**
 * 收藏（Saved）
 * ==============
 *
 * ⚠️⚠️ 用戶要求：
 *   「Zones 嘅 function 你唔好寫 Zone，寫 Saved。
 *    入面有一個 list 寫係你 saved 嘅景，仲可以上面有一個 bar
 *    for searching —— 有啲 search 字 like：如果有 saved 博多景，
 *    因為本身 address 有，佢會 show 福岡畀你 tick。」
 *
 * ⚠️ 為咩要「由地址抽出 facet」而唔係淨係一個搜尋框：
 *   · 用戶通常唔記得景點叫咩名，但記得「喺福岡嗰邊」
 *   · 打「福」可能想搵「福岡」又可能想搵「福砂屋」——
 *     分開「地名 facet」同「自由文字」就唔會撞
 *   · 一 tick 就係**精確**嘅地名過濾（唔係模糊匹配）
 *
 * ⚠️ 為咩 facet 由 `location_path` 抽：
 *   貼一條 Google Maps link 入嚟嗰陣，解析器已經拆咗
 *   地址層級（["福岡県","福岡市","博多区"]）——
 *   直接用，唔使自己再 parse 地址。
 *
 * ⚠️ 呢個 app **唔係**「分區規劃」——
 *   分區排行程已經搬入 Planner（編排）。
 *   呢度係「睇返 / 搵返你收藏咗嘅嘢」。
 */
export default function Saved({ trip, items, onEditItem, onBack, onToggleVis }) {
  const [q, setQ] = useState('')
  const [picked, setPicked] = useState([])        // 已 tick 嘅地名

  /**
   * ⚠️ 由所有景點嘅地址層級抽出「地名 facet」。
   *
   * 例：博多嘅 location_path = ['福岡県','福岡市','博多区']
   *     → 福岡県 / 福岡市 / 博多区 各 +1
   *
   * ⚠️ 只顯示**出現過**嘅地名（唔可以列出全世界城市）。
   * ⚠️ 按出現次數排序 —— 最多嘢喺嗰區就排最前。
   */
  const facets = useMemo(() => {
    const count = new Map()
    for (const it of items) {
      // ⚠️ 用 Set 去重：同一個景點唔應該將「福岡市」加兩次
      const names = new Set()
      for (const p of (it.location_path || [])) {
        const t = String(p || '').trim()
        if (t) names.add(t)
      }
      for (const k of ['city', 'district', 'country']) {
        const t = String(it[k] || '').trim()
        if (t) names.add(t)
      }
      for (const n of names) count.set(n, (count.get(n) || 0) + 1)
    }
    return [...count.entries()]
      .map(([name, n]) => ({ name, n }))
      .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name))
      .slice(0, 24)          // ⚠️ 最多 24 個 chip —— 再多就逼爆畫面
  }, [items])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return items.filter(it => {
      // ① 地名 facet：tick 咗嘅**全部**都要中
      if (picked.length) {
        const hay = [
          ...(it.location_path || []),
          it.city, it.district, it.country,
        ].filter(Boolean).map(s => String(s))
        const ok = picked.every(p =>
          hay.some(h => h === p || h.includes(p) || p.includes(h)))
        if (!ok) return false
      }
      // ② 自由文字：名 / 地址 / 分類
      if (!needle) return true
      const text = [
        it.name, ...(it.location_path || []), it.city, it.district,
        it.country, it.note, it.category,
      ].filter(Boolean).join(' ').toLowerCase()
      return text.includes(needle)
    })
  }, [items, q, picked])

  function toggleFacet(name) {
    setPicked(p => p.includes(name) ? p.filter(x => x !== name) : [...p, name])
  }

  const hasFilter = picked.length > 0 || q.trim()

  return (
    <div style={{ paddingBottom: 30 }}>
      <div className="screen no-nav" style={{ paddingBottom: 6 }}>
        {/* ⚠️⚠️ 用戶報：「撳返去 shopping 啦，又冇嘢睇啦」
                ⚠️ 根因：呢度寫 `history.back()` ——
                   但 Saved 係一個 **tab**（唔係 route）→
                   `history.back()` 會跳咗**出 app**（或者去上一頁），
                   用戶就見到一片空白。
                ✅ 修法：用 `onBack` callback（App 話俾我哋知返去邊）。 */}
        <button className="btn sm ghost"
          onClick={() => (onBack ? onBack() : setTabHome())}>‹ 返去</button>
        <div style={{ textAlign: 'right', flex: 1 }}>
          <div style={{ fontWeight: 900, fontSize: 15 }}>🔖 收藏</div>
          <div className="sub" style={{ fontSize: 10 }}>
            {items.length} 個景點
          </div>
        </div>
      </div>

      {/* ══ 搜尋欄 ══ */}
      <div className="saved-search">
        <PixelIcon name="list" size={16} />
        <input className="saved-input" value={q}
          placeholder="搵景點、地址、備註…"
          onChange={e => setQ(e.target.value)} />
        {q && (
          <button className="saved-clear" onClick={() => setQ('')}
            aria-label="清除搜尋">✕</button>
        )}
      </div>

      {/* ══ 地名 facet（由地址抽出）══ */}
      {/*   ⚠️ 用戶要求：「如果有 saved 博多景，因為本身 address 有，
             佢會 show 福岡畀你 tick」 */}
      {facets.length > 0 && (
        <>
          <div className="sec" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>📍 地名</span>
            {picked.length > 0 && (
              <button className="btn sm ghost" style={{ fontSize: 10, padding: '2px 7px' }}
                onClick={() => setPicked([])}>清除 {picked.length} 個</button>
            )}
          </div>
          <div className="chips">
            {facets.map(f => (
              <button key={f.name}
                className={`chip ${picked.includes(f.name) ? 'on' : ''}`}
                onClick={() => toggleFacet(f.name)}>
                {picked.includes(f.name) ? '✓ ' : ''}{f.name}
                <span className="sub" style={{ fontSize: 9.5, marginLeft: 4 }}>
                  {f.n}
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {/* ══ 清單 ══ */}
      <div className="sec" style={{
        marginTop: 14, display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span>{hasFilter ? '篩選結果' : '全部收藏'}</span>
        <span className="sub" style={{ fontSize: 10.5, fontWeight: 400 }}>
          {filtered.length} / {items.length}
        </span>
      </div>

      {items.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 22 }}>
          <div style={{ fontSize: 30, marginBottom: 8 }}>🔖</div>
          <div style={{ fontWeight: 800, fontSize: 14 }}>仲未有收藏</div>
          <div className="sub" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.8 }}>
            去「<b>整理</b>」貼一條 Google Maps / IG link 開始
          </div>
        </div>
      )}

      {items.length > 0 && filtered.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 18 }}>
          <div className="sub" style={{ fontSize: 12 }}>
            冇嘢中 —— 試下其他字，或者清除篩選
          </div>
          {hasFilter && (
            <button className="btn sm ghost" style={{ marginTop: 9 }}
              onClick={() => { setQ(''); setPicked([]) }}>清除全部篩選</button>
          )}
        </div>
      )}

      {filtered.map(it => (
        <div key={it.id} className="item tap" onClick={() => onEditItem?.(it)}>
          <div className="ic">
            {it.raw_image
              ? <img src={it.raw_image} alt="" loading="lazy" />
              : iconFor(it)}
          </div>
          <div className="info">
            <h4>{it.name || '（未有名稱）'}</h4>
            <p>
              {/* ⚠️⚠️ public／private（用戶要求）
                     「Save 低嘅景點應該分 public 同 Private。
                       Public = 全 group 見到，Private = 得自己睇到。」
                  ⚠️ 只有**我加嘅**（`it.mine`）先可以撳 ——
                     唔可以改朋友嘅可見度（後端都會擋）。 */}
              <span
                role={it.mine ? 'button' : undefined}
                title={it.visibility === 'public'
                  ? '全 group 都見到' : '只有你見到'}
                onClick={e => {
                  if (!it.mine) return
                  e.stopPropagation()
                  onToggleVis?.(it)
                }}
                style={{
                  display: 'inline-block', marginRight: 5, padding: '1px 6px',
                  borderRadius: 999, fontSize: 9.5, fontWeight: 700,
                  border: '1px solid ' + (it.visibility === 'public'
                    ? 'var(--cyan)' : 'var(--border)'),
                  color: it.visibility === 'public' ? 'var(--cyan)' : 'var(--dim)',
                  cursor: it.mine ? 'pointer' : 'default',
                  opacity: it.mine ? 1 : .6,
                }}>
                {it.visibility === 'public' ? '🌍 公開' : '🔒 私人'}
              </span>
              {(it.location_path || []).join(' › ') || it.city || '未分類'}
              {it.day_index != null && (
                <span className="chip" style={{ fontSize: 9, marginLeft: 6 }}>
                  Day {it.day_index}
                </span>
              )}
            </p>
          </div>
          {it.confidence != null && (
            <span className={`conf ${confClass(it.confidence)}`}>{it.confidence}%</span>
          )}
        </div>
      ))}
    </div>
  )
}
