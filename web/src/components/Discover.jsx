import { useMemo, useState } from 'react'
import { api, iconFor, confClass } from '../lib/api'
import { toast, Empty, Spinner } from '../lib/ui'
import { parsePayload } from '../lib/bookmarklet'

const CATS = [
  { k: 'all', label: '全部' },
  { k: 'food', label: '🍜 美食' },
  { k: 'shopping', label: '🛍 購物' },
  { k: 'play', label: '🎡 玩樂' },
  { k: 'stay', label: '🏨 住宿' },
  { k: 'transport', label: '🚇 交通' },
  { k: 'other', label: '📍 其他' },
]

export default function Discover({ tripId, items, onRefresh, onOpenMap, onEditItem }) {
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [mode, setMode] = useState('link')       // link | text
  const [busy, setBusy] = useState(false)
  /**
   * ⚠️⚠️ 加嘅時候就要揀 public／private（用戶要求）
   *    「景點 list 都要」
   *
   *    ⚠️ 預設 `private`（只有自己見到）——
   *       唔會唔小心公開。
   */
  const [vis, setVis] = useState('private')
  const [steps, setSteps] = useState([])
  const [needCaption, setNeedCaption] = useState(null)   // {url, reason}
  const [cat, setCat] = useState('all')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('added')     // added | votes | conf | name

  const filtered = useMemo(() => {
    let list = cat === 'all' ? [...items] : items.filter(i => i.category === cat)
    const kw = q.trim().toLowerCase()
    if (kw) {
      list = list.filter(i => [
        i.name, i.address, i.district, i.city, i.country,
        i.category_label, i.notes?.join(' '), i.tags?.join(' '),
      ].filter(Boolean).join(' ').toLowerCase().includes(kw))
    }
    const cmp = {
      added: (a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')),
      votes: (a, b) => (b.votes || 0) - (a.votes || 0),
      conf:  (a, b) => (b.confidence || 0) - (a.confidence || 0),
      name:  (a, b) => String(a.name || '～').localeCompare(String(b.name || '～'), 'zh-Hant'),
    }[sort]
    return list.sort(cmp)
  }, [items, cat, q, sort])
  const grouped = useMemo(() => {
    const g = {}
    filtered.forEach(i => {
      const key = i.district || i.city || i.country || '未分類'
      ;(g[key] ||= []).push(i)
    })
    return Object.entries(g).sort((a, b) => b[1].length - a[1].length)
  }, [filtered])

  /**
   * ⚠️⚠️ 存入收藏 —— **一定要報實情**。
   *
   *   ⚠️ 唔可以 `catch {}` —— 咁樣加失敗都會顯示「已加入 0 個 ✓」，
   *      用戶以為成功但收藏度冇嘢（用戶報嘅 bug）。
   *
   *   ⚠️ 後端會回 `duplicate: true`（同一個地方已經喺收藏度）——
   *      呢個**唔係**錯誤，要分開講。
   */
  /**
   * ⚠️⚠️ 可見度掣（用戶要求）
   *    「加嘅時候順便有個 button set public 定 private」
   *
   *    ⚠️ 用**兩個掣**而唔係 toggle —— 一眼睇到而家係邊個。
   */
  function VisPicker() {
    return (
      <div className="chips" style={{ marginTop: 9 }}>
        <button className={`chip ${vis === 'private' ? 'on' : ''}`}
          style={{ fontSize: 10.5 }} onClick={() => setVis('private')}
          title="只有你見到">
          🔒 私人
        </button>
        <button className={`chip ${vis === 'public' ? 'on' : ''}`}
          style={{ fontSize: 10.5 }} onClick={() => setVis('public')}
          title="全 group 都見到">
          🌍 公開
        </button>
        <span className="sub" style={{ fontSize: 10, alignSelf: 'center', marginLeft: 4 }}>
          {vis === 'private' ? '只有你見到' : '全 group 都見到'}
        </span>
      </div>
    )
  }

  async function saveAll(found) {
    let added = 0, dup = 0
    const errs = []
    for (const it of found) {
      try {
        // ⚠️⚠️ 加嘅時候就決定可見度（用戶要求）
        const r = await api.addItem(tripId, { ...it, visibility: vis })
        if (r?.duplicate) dup++
        else added++
      } catch (e) {
        errs.push(`${it.name || '（無名）'}：${e.message}`)
      }
    }
    const parts = []
    if (added) parts.push(`新增 ${added} 個`)
    if (dup) parts.push(`${dup} 個已經喺收藏度`)
    if (errs.length) parts.push(`${errs.length} 個失敗`)
    if (!parts.length) parts.push('冇嘢可以加')
    // ⚠️ 全部失敗 / 冇新增 → 唔好用 ✓（會誤導）
    const ok = added > 0
    toast(`${ok ? '✓ ' : '⚠️ '}${parts.join(' · ')}`)
    if (errs.length) setSteps(prev => [...prev,
      ...errs.slice(0, 3).map(e => ({ t: e, k: 'err' }))])
    return { added, dup, errs }
  }

  async function runParse() {
    // ⚠️ 先檢查係唔係書籤小工具嘅 payload（用戶貼上嚟嘅）
    const bm = parsePayload(text) || parsePayload(url)
    let payload
    if (bm && bm.caption) {
      payload = { url: bm.url || undefined, text: bm.caption }
      setText(''); setUrl('')
      toast('認得書籤小工具嘅內容 ✓')
    } else {
      payload = mode === 'link' ? { url: url.trim() } : { text: text.trim() }
      if (mode === 'link' && !payload.url) return toast('請貼一條 link')
      if (mode === 'text' && !payload.text) return toast('請貼文字')
    }

    setBusy(true); setSteps([{ t: '解析中…', k: 'run' }])
    try {
      const r = await api.parse(payload)
      const found = r.items || []
      setSteps([
        ...r.trace.slice(0, 14).map(x => ({ t: `${x.rule} — ${String(x.match).slice(0, 70)}`, k: 'ok' })),
        { t: `抽出 ${found.length} 個項目`, k: 'ok' },
      ])

      // ⚠️ IG / 小紅書封鎖 → 唔好當失敗，而係叫用戶貼 caption
      const blocked = found.find(i => i.needs_input === 'caption')
      if (blocked) {
        setNeedCaption({ url: payload.url, reason: blocked.blocked_reason })
        setSteps(prev => [...prev, {
          t: 'IG 封鎖咗自動讀取 → 請貼 caption（下面）', k: 'warn',
        }])
        toast('IG 封鎖咗，請貼 caption 落嚟')
        return
      }

      // ⚠️⚠️ 自動存入 trip —— **一定要報實情**
      //
      //   用戶報：「我擺咗條 link 上去，但係唔知點解佢冇新增落去
      //            嗰個已收藏景點度」
      //
      //   ⚠️ 根因：原本寫 `try { await addItem(...); saved++ } catch {}`
      //      —— **錯誤被靜靜食咗**，然後照樣 toast「已加入 0 個收藏 ✓」，
      //      個 ✓ 令用戶以為成功。加上後端嗰時冇去重，
      //      用戶見唔到就再撳 → 加咗兩次。
      //
      //   ✅ 而家：
      //      · 收集真錯誤，唔再 `catch {}`
      //      · 分辨「新增」／「已經喺收藏度」（後端回 duplicate）
      //      · 0 個成功 → **紅色警告**，唔係 ✓
      const res = await saveAll(found)
      setUrl(''); setText('')
      await onRefresh()
    } catch (e) {
      setSteps([{ t: e.message, k: 'err' }])
      toast(e.message)
    } finally { setBusy(false) }
  }

  /** 用戶補完 caption → 解析 + 保留原 link。 */
  async function submitCaption(captionText) {
    if (!captionText.trim()) return toast('請貼 caption 文字')
    setBusy(true)
    try {
      const r = await api.parse({ url: needCaption?.url, text: captionText.trim() })
      const found = r.items || []
      // ⚠️ 同上面一樣 —— 用 saveAll()，唔好 `catch {}` 食咗錯誤
      await saveAll(found)
      setNeedCaption(null); setUrl(''); setText('')
      setSteps([])
      await onRefresh()
    } catch (e) {
      toast(e.message)
    } finally { setBusy(false) }
  }

  async function pasteFromClipboard() {
    try {
      const t = await navigator.clipboard.readText()
      if (!t) return toast('剪貼簿係空嘅')
      submitCaption(t)
    } catch {
      toast('讀唔到剪貼簿 —— 請手動長按貼上')
    }
  }

  return (
    <div className="screen">
      <div className="h1">加入收藏</div>
      <div className="sub">貼 IG / 小紅書 / Google Maps link，或者貼 caption 文字</div>
      <div className="sub" style={{ fontSize: 10.5, marginTop: 4 }}>
        💡 用「🔖 書籤小工具」（設定頁）複製咗嘅內容，貼落呢度會自動識別
      </div>

      <div className="chips" style={{ margin: '12px 0 10px' }}>
        <button className={`chip ${mode === 'link' ? 'on' : ''}`} onClick={() => setMode('link')}>🔗 貼 link</button>
        <button className={`chip ${mode === 'text' ? 'on' : ''}`} onClick={() => setMode('text')}>📝 貼文字</button>
      </div>

      {/* ⚠️⚠️ 可見度（用戶要求）——
             「加嘅時候順便要有個 button set public 定 private」
             「景點 list 都要」

          ⚠️⚠️ 一定要放喺**解析掣之前**（即係輸入框**上面**）——
             因為 `runParse()` 解析完會**自動存入**（`saveAll`），
             唔係只得預覽。用戶如果解析完先揀就太遲。
          （實測：我第一版放喺解析掣之後 → 用戶根本冇機會揀。） */}
      <VisPicker />

      {mode === 'link' ? (
        <div className="row" style={{ gap: 7 }}>
          <input className="input mono" placeholder="https://maps.app.goo.gl/… 或 IG link"
            value={url} onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runParse()} />
          <button className="btn primary" onClick={runParse} disabled={busy}>
            {busy ? <Spinner /> : '解析'}
          </button>
        </div>
      ) : (
        <>
          <textarea className="input" rows={5} placeholder="貼 IG / 小紅書 caption 落嚟…"
            value={text} onChange={e => setText(e.target.value)}
            style={{ resize: 'vertical', lineHeight: 1.7 }} />
          <button className="btn primary wide" style={{ marginTop: 8 }}
            onClick={runParse} disabled={busy}>
            {busy ? <Spinner /> : '解析文字'}
          </button>
        </>
      )}

      {needCaption && (
        <CaptionPrompt
          url={needCaption.url}
          busy={busy}
          onSubmit={submitCaption}
          onPaste={pasteFromClipboard}
          onCancel={() => setNeedCaption(null)}
        />
      )}

      {/* ⚠️⚠️ 可見度（用戶要求）——
             「加嘅時候順便要有個 button set public 定 private」
             「景點 list 都要」
          ⚠️ 放喺**解析掣之前** —— 因為解析完會**自動存入**，
             所以一定要解析之前揀好。 */}
      {steps.length > 0 && !needCaption && (
        <div className="card" style={{ marginTop: 12, borderColor: 'var(--cyan)' }}>
          <div className="steps">
            {steps.map((s, i) => (
              <div key={i}>
                <span style={{
                  color: s.k === 'err' ? 'var(--bad)'
                    : s.k === 'warn' ? 'var(--warn)' : 'var(--cyan)',
                }}>
                  {s.k === 'err' ? '✗' : s.k === 'warn' ? '⚠' : s.k === 'run' ? '◌' : '▸'}
                </span>
                <span>{s.t}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {items.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <input className="input" placeholder="🔍 搵店名、地區、標籤…" value={q}
            onChange={e => setQ(e.target.value)} />
          <div className="scroll-x" style={{ marginTop: 8 }}>
            {[['added', '最新加入'], ['votes', '最多票'], ['conf', '最高信心'], ['name', '名稱']].map(([k, l]) => (
              <button key={k} className={`chip ${sort === k ? 'on' : ''}`}
                onClick={() => setSort(k)}>{l}</button>
            ))}
          </div>
        </div>
      )}

      <div className="scroll-x" style={{ marginTop: 14 }}>
        {CATS.map(c => {
          const n = c.k === 'all' ? items.length : items.filter(i => i.category === c.k).length
          return (
            <button key={c.k} className={`chip ${cat === c.k ? 'on' : ''}`} onClick={() => setCat(c.k)}>
              {c.label} {n}
            </button>
          )
        })}
      </div>

      {items.length === 0 ? (
        <Empty icon="sparkle" title="仲未有收藏" hint="貼一條 link 或者 caption 試下" />
      ) : filtered.length === 0 ? (
        <Empty icon="🔍" title="搵唔到" hint={q ? `冇結果符合「${q}」` : '呢個分類未有項目'} />
      ) : (
        <>
          {grouped.map(([place, list]) => (
            <div key={place}>
              <div className="sec">{place} · {list.length}</div>
              {list.map(it => <ItemRow key={it.id} item={it} onRefresh={onRefresh} onEdit={onEditItem} />)}
            </div>
          ))}
          {items.some(i => i.lat && i.lng) && (
            <button className="btn wide" style={{ marginTop: 10 }} onClick={onOpenMap}>
              🗺 去地圖睇分佈 →
            </button>
          )}
        </>
      )}
    </div>
  )
}

/** IG / 小紅書封鎖 → 引導用戶貼 caption。 */
function CaptionPrompt({ url, busy, onSubmit, onPaste, onCancel }) {
  const [txt, setTxt] = useState('')
  const isIG = /instagram\.com/.test(url || '')
  const isXHS = /xiaohongshu|xhslink/.test(url || '')

  return (
    <div className="card glow" style={{
      marginTop: 12, borderColor: 'var(--warn)', borderWidth: 1.5,
    }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <span style={{ fontSize: 22 }}>🔒</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 900, fontSize: 13.5, color: 'var(--warn)' }}>
            {isIG ? 'Instagram' : isXHS ? '小紅書' : '呢個網站'} 封鎖咗自動讀取
          </div>
          <div className="sub" style={{ fontSize: 11.5, marginTop: 5, lineHeight: 1.75 }}>
            唔係你嘅問題 —— IG 對所有未登入嘅程式請求都回傳登入頁，<b>零資料</b>。
            <br />
            <b>解決方法：撳兩下就搞掂</b>
          </div>
        </div>
      </div>

      {/* 步驟指示 */}
      <div className="card" style={{ marginTop: 11, padding: 11, background: 'var(--surface-2)' }}>
        <div className="sub" style={{ fontSize: 11.5, lineHeight: 2 }}>
          {isIG ? (
            <>
              <div><b>1.</b> 返去 Instagram App，開嗰個帖</div>
              <div><b>2.</b> 撳右上角 <b>⋯</b>（或者長按文字）</div>
              <div><b>3.</b> 揀 <b>「複製文字」</b></div>
              <div><b>4.</b> 返嚟撳下面「📋 從剪貼簿貼上」</div>
            </>
          ) : isXHS ? (
            <>
              <div><b>1.</b> 返去小紅書，開嗰個帖</div>
              <div><b>2.</b> 長按內文 → <b>全選 → 複製</b></div>
              <div><b>3.</b> 返嚟撳下面「📋 從剪貼簿貼上」</div>
            </>
          ) : (
            <>
              <div><b>1.</b> 去嗰個網站，全選內容複製</div>
              <div><b>2.</b> 返嚟撳「📋 從剪貼簿貼上」</div>
            </>
          )}
        </div>
      </div>

      <div className="sec" style={{ marginTop: 12 }}>或者直接貼落嚟</div>
      <textarea
        className="input"
        rows={6}
        placeholder="長按呢度 → 貼上（caption 文字）"
        value={txt}
        onChange={e => setTxt(e.target.value)}
        style={{ resize: 'vertical', lineHeight: 1.75, fontSize: 13 }}
      />

      <button className="btn primary wide" style={{ marginTop: 10 }}
        onClick={onPaste} disabled={busy}>
        {busy ? '解析緊…' : '📋 從剪貼簿貼上並解析'}
      </button>

      <div style={{ display: 'flex', gap: 7, marginTop: 8 }}>
        <button className="btn" style={{ flex: 1 }} onClick={() => onSubmit(txt)}
          disabled={busy || !txt.trim()}>
          用上面文字解析
        </button>
        <button className="btn ghost" onClick={onCancel}>取消</button>
      </div>

      <div className="sub" style={{ fontSize: 10.5, marginTop: 10, lineHeight: 1.7 }}>
        ✅ 你嘅原 link 會保留喺記錄
        <br />✅ caption 文字係最齊嘅來源（地址、時間、價錢全部有）
        <br />✅ 完全冇 scraping，法律上最乾淨
      </div>
    </div>
  )
}

function ItemRow({ item, onRefresh, onEdit }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  async function vote(e) {
    e.stopPropagation()
    setBusy(true)
    try { await api.vote(item.id); await onRefresh() }
    catch (err) { toast(err.message) } finally { setBusy(false) }
  }
  async function del(e) {
    e.stopPropagation()
    if (!confirm(`刪除「${item.name || '呢個項目'}」？`)) return
    try { await api.deleteItem(item.id); toast('已刪除'); await onRefresh() }
    catch (err) { toast(err.message) }
  }
  const addr = (item.location_path || []).join(' › ')

  return (
    <div className={`item ${item.needs_review ? 'low' : ''}`}
      style={{ flexDirection: 'column', gap: 0 }}>
      <div style={{ display: 'flex', gap: 11, width: '100%', cursor: 'pointer' }}
        onClick={() => onEdit && onEdit(item)}>
        <div className="ic">
          {item.raw_image ? <img src={item.raw_image} alt="" loading="lazy" /> : iconFor(item)}
        </div>
        <div className="info">
          <h4>{item.name || '（未有名稱）'}</h4>
          <p>{addr || '未分類'}{item.address ? ` · ${item.address}` : ''}</p>
          <div className="chips" style={{ marginTop: 6 }}>
            <span className="chip cat">{iconFor(item)} {item.category_label || item.category || '未分類'}</span>
            <span className="chip">{item.source_name || item.source}</span>
            {item.brand_from && <span className="chip" style={{ color: 'var(--warn)' }}>品牌來自 {item.brand_from}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          <span className={`conf ${confClass(item.confidence)}`}>{item.confidence}%</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="btn sm ghost" onClick={vote} disabled={busy}
              style={{ fontSize: 11, padding: '6px 8px' }}>▲ {item.votes || 0}</button>
            <button className="btn sm ghost" style={{ fontSize: 11, padding: '6px 8px' }}
              onClick={() => setOpen(v => !v)}>{open ? '▲' : '▼'}</button>
          </div>
        </div>
      </div>

      {open && (
        <div style={{ width: '100%', marginTop: 11, paddingTop: 11, borderTop: '1px dashed var(--border)' }}>
          {item.hours && <div className="sub">🕐 {item.hours}</div>}
          {item.phone && <div className="sub">☎️ {item.phone}</div>}
          {item.price && <div className="sub">💰 {item.price}</div>}
          {item.dates?.length > 0 && <div className="sub">📅 {item.dates.map(d => d.display || d.date_from).join('　|　')}</div>}
          {item.tags?.length > 0 && <div className="sub">#️⃣ {item.tags.slice(0, 8).join(' ')}</div>}
          {item.lat != null && (
            <div className="sub mono" style={{ fontSize: 10 }}>🗺 {item.lat.toFixed(5)}, {item.lng.toFixed(5)}</div>
          )}
          {item.notes?.length > 0 && item.notes.map((n, i) => (
            <div key={i} className="sub" style={{ color: 'var(--warn)' }}>ℹ️ {n}</div>
          ))}
          <div style={{ display: 'flex', gap: 7, marginTop: 10, flexWrap: 'wrap' }}>
            {item.google_maps_url && (
              <a className="btn sm" href={item.google_maps_url} target="_blank" rel="noreferrer">🗺 開地圖</a>
            )}
            {item.url && (
              <a className="btn sm ghost" href={item.url} target="_blank" rel="noreferrer">🔗 原 link</a>
            )}
            <button className="btn sm ghost" onClick={del} style={{ color: 'var(--bad)' }}>刪除</button>
          </div>
        </div>
      )}
    </div>
  )
}
