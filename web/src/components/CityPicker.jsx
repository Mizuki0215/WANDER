import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'

/**
 * 城市選擇器（CityPicker）
 * ========================
 * 用戶要求（原文）：
 *   「會唔會你個 planner 你嘅城市係俾人選擇而唔係打字入去囉。
 *    例如你可以列晒全球所有嘅城市，然後你可以打英文或者打中文繁中，
 *    然後打某些字就會出對應近似嘅答案俾你，咁你就去撳佢囉。
 *    例如你打到 Hong Kong，打到個 hong 呢個字之後就可能會出現到
 *    原來有香港呢個城市」
 *
 * ⚠️⚠️ 為咩一定要「揀」而唔係「打字」：
 *   用戶報嘅真 bug —— 佢打「香港」落 trip 嘅「目的地」欄，
 *   但地圖只讀 🧭「城市」編輯器（空嘅）→ 地圖跌落福岡 fallback。
 *
 *   打字入城市有幾個問題：
 *     ① 打錯字／簡繁／英文拼法唔同 → 查唔到座標
 *     ② 同名地方好多（Springfield、San José）→ 用戶唔知揀邊個
 *     ③ 冇即時反饋 → 用戶以為設定咗，但其實冇
 *
 *   所以我哋用**本地 134,655 個城市名索引**（中／英／日／韓／諺文）
 *   即時搜尋，用戶撳一下就揀實，座標即刻有（0.03ms）。
 */

/** 人口 → 「740萬人」 */
function popText(n) {
  if (!n) return ''
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}億人`
  if (n >= 1e4) return `${Math.round(n / 1e4)}萬人`
  return `${n}人`
}

export default function CityPicker({
  value = '', onChange, onPick, placeholder = '打城市名（中文／英文都得）',
  autoFocus = false, hideList = false,
}) {
  const [q, setQ] = useState(value)
  const [list, setList] = useState([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [hi, setHi] = useState(0)              // 鍵盤選擇
  const timer = useRef(null)
  const boxRef = useRef(null)

  // 外部改 value → 同步
  useEffect(() => { setQ(value) }, [value])

  /** 打字 → debounce 搜尋（本地庫 0.03ms，但打字太快都唔想每個字都 render）。 */
  useEffect(() => {
    clearTimeout(timer.current)
    const s = q.trim()
    if (!s) { setList([]); setOpen(false); return }
    setBusy(true)
    timer.current = setTimeout(async () => {
      try {
        const r = await api.searchCities(s, 12)
        setList(r.results || [])
        setOpen(true)
        setHi(0)
      } catch { setList([]) }
      finally { setBusy(false) }
    }, 110)
    return () => clearTimeout(timer.current)
  }, [q])

  // 撳外面收埋
  useEffect(() => {
    const h = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', h)
    return () => document.removeEventListener('pointerdown', h)
  }, [])

  function pick(r) {
    setQ(r.query)
    setOpen(false)
    onChange?.(r.query)
    onPick?.(r)          // ⚠️ 連座標一齊交出去，唔使再查一次
    toast(`揀咗「${r.query}」${r.country ? ` · ${r.country}` : ''}`)
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi(h => Math.min(h + 1, list.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi(h => Math.max(h - 1, 0)) }
    else if (e.key === 'Enter') {
      if (open && list[hi]) { e.preventDefault(); pick(list[hi]) }
    } else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div ref={boxRef} style={{ position: 'relative', flex: 1, minWidth: 0 }}>
      <div className="row" style={{ gap: 6 }}>
        <span style={{ fontSize: 14, flex: '0 0 auto', opacity: .65 }}>🌏</span>
        <input className="input" value={q} placeholder={placeholder}
          autoFocus={autoFocus}
          onChange={e => { setQ(e.target.value); onChange?.(e.target.value) }}
          onFocus={() => list.length && setOpen(true)}
          onKeyDown={onKey}
          style={{ flex: 1, minWidth: 0 }} />
        {busy && <span className="spin" style={{ flex: '0 0 auto' }} />}
      </div>

      {open && !hideList && (
        <div className="card" style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 60,
          marginTop: 5, padding: 5, maxHeight: 300, overflowY: 'auto',
          boxShadow: '0 14px 40px rgba(0,0,0,.5)', borderColor: 'var(--border-hi)',
        }}>
          {list.length === 0 ? (
            <div className="sub" style={{ padding: '10px 9px', fontSize: 11.5, lineHeight: 1.75 }}>
              搵唔到「{q}」<br />
              <span style={{ opacity: .75 }}>試下打英文（Tokyo）或者中文（東京）</span>
            </div>
          ) : (
            list.map((r, i) => (
              <button key={`${r.query}-${r.lat}-${i}`}
                onPointerEnter={() => setHi(i)}
                onClick={() => pick(r)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 9, width: '100%',
                  padding: '9px 9px', borderRadius: 'var(--r-xs)', textAlign: 'left',
                  background: i === hi ? 'var(--surface-2)' : 'transparent',
                  borderBottom: i < list.length - 1 ? '1px dashed var(--border)' : 'none',
                }}>
                <span style={{ fontSize: 15, flex: '0 0 auto' }}>📍</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 800, fontSize: 13,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {r.query}
                    {/* ⚠️ 顯示「匹配到嘅名」——用戶打「香港」但 canonical 係
                        "Hong Kong"，唔顯示就唔知揀啱咗未 */}
                    {r.matched && r.matched !== r.query.toLowerCase() && (
                      <span className="sub" style={{ fontSize: 11, fontWeight: 400, marginLeft: 7 }}>
                        {r.matched}
                      </span>
                    )}
                  </div>
                  <div className="sub" style={{ fontSize: 10.5 }}>
                    {r.country}{r.population ? ` · ${popText(r.population)}` : ''}
                  </div>
                </div>
                {i === hi && (
                  <span className="sub" style={{ fontSize: 10, flex: '0 0 auto' }}>Enter ↵</span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
