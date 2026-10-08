import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { toast, Empty } from '../lib/ui'
import { readAndResize, dataUrlBytes, fmtBytes } from '../lib/image'
import Lightbox from './Lightbox'

/**
 * 購物清單（Shopping List）
 * ========================
 * 用戶要求：「希望仲有一個 Shopping List」
 *
 * 旅行買嘢同平時買嘢唔同：
 *   · 要分「邊個負責買」（一班人去，分工）
 *   · 要記「邊度買」（藥妝／手信／機場）
 *   · 要估預算（單價 × 數量）
 *   · 買完要剔，唔好買雙份
 */

const CATS = [
  { k: 'souvenir', label: '🎁 手信' },
  { k: 'drug', label: '💊 藥妝' },
  { k: 'food', label: '🍫 食品' },
  { k: 'cloth', label: '👕 衣物' },
  { k: 'electronics', label: '🔌 電器' },
  { k: 'other', label: '✦ 其他' },
]

const catIcon = (k) => (CATS.find(c => c.k === k)?.label || '✦').split(' ')[0]

/**
 * 貨幣揀選 —— 用戶要求：
 *   「有時你去旅行如果唔係都係用港幣㗎嘛，所以你要 mark 低返
 *    嗰個嘅價錢係有得揀嗰個 Yen or KRW or EUR、HKD 定係點樣？」
 *
 * ⚠️ 用 `<select>` 而唔係自製 dropdown ——
 *    手機原生 picker 好好用（唔使自己處理 scroll / 遮蓋）。
 * ⚠️ 常用幣排前面（`optgroup`），全部 340 個喺後面。
 */
// ⚠️ 貨幣符號（同 engine/wander/currency.py 嘅 _SYMBOLS 一致）
//    ⚠️ 前端唔 import 得到 Python —— 呢度要有一份。
const SYMBOLS = {
  HKD: 'HK$', JPY: '¥', KRW: '₩', TWD: 'NT$', CNY: 'CN¥',
  USD: '$', EUR: '€', GBP: '£', THB: '฿', SGD: 'S$',
  MYR: 'RM', VND: '₫', PHP: '₱', IDR: 'Rp', INR: '₹',
  AUD: 'A$', CAD: 'C$', CHF: 'CHF', NZD: 'NZ$', AED: 'د.إ',
}

function CurrencyPicker({ value, onChange, currencies, style }) {
  const common = currencies?.common || []
  const all = currencies?.all || []
  const commonCodes = new Set(common.map(c => c.code))
  const rest = all.filter(c => !commonCodes.has(c.code))

  return (
    <select className="input" value={value || ''} onChange={e => onChange(e.target.value)}
      style={{ flex: '0 0 auto', width: 92, fontWeight: 700, ...style }}
      title="呢項嘅貨幣">
      {common.length > 0 && (
        <optgroup label="常用">
          {common.map(c => (
            <option key={c.code} value={c.code}>{c.symbol} {c.code}</option>
          ))}
        </optgroup>
      )}
      {rest.length > 0 && (
        <optgroup label="全部">
          {rest.map(c => <option key={c.code} value={c.code}>{c.code}</option>)}
        </optgroup>
      )}
      {common.length === 0 && all.length === 0 && (
        <option value="">HKD</option>
      )}
    </select>
  )
}

export default function ShoppingList({ trip, members, onRefresh , onToggleVis }) {
  const [data, setData] = useState(null)
  const [currencies, setCurrencies] = useState(null)
  const [text, setText] = useState('')
  const [qty, setQty] = useState('')
  const [cat, setCat] = useState('souvenir')
  const [price, setPrice] = useState('')
  const [cur, setCur] = useState('')          // ⚠️ 空 = 用旅程貨幣
  const [assignee, setAssignee] = useState('')
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState(null)
  const [view, setView] = useState(null)      // 全圖檢視
  const [showDone, setShowDone] = useState(true)
  const [photo, setPhoto] = useState(null)       // { data, width, height }
  const [uploading, setUploading] = useState(false)
  const [near, setNear] = useState(null)         // 附近店鋪結果
  const [nearBusy, setNearBusy] = useState(false)
  const fileRef = useRef(null)

  const load = async () => {
    try { setData(await api.listShopping(trip.id)) }
    catch (e) { toast(e.message) }
  }
  useEffect(() => { if (trip?.id) load() }, [trip?.id])   // eslint-disable-line

  const pending = useMemo(() => (data?.items || []).filter(i => !i.done), [data])
  const done = useMemo(() => (data?.items || []).filter(i => i.done), [data])
  // ⚠️⚠️ 注意：`budget` 係**未換算**嘅原始數 ——
  //    日元同港幣加埋一齊係**冇意義**嘅。
  //    ⚠️ 所以**唔可以**用佢做總額顯示。
  //    總額用後端嘅 `data.total`（已經按匯率換算好）。
  const budgetRaw = useMemo(
    () => pending.reduce((n, i) => n + (Number(i.price) || 0), 0), [pending])

  /** 揀相 → 縮圖 → 準備上傳。 */
  async function pickPhoto(e) {
    const f = e.target.files?.[0]
    e.target.value = ''        // 令同一個檔案可以再揀
    if (!f) return
    try {
      const r = await readAndResize(f)
      setPhoto(r)
      toast(`已縮圖：${fmtBytes(dataUrlBytes(r.data))}`)
    } catch (err) { toast(err.message) }
  }

  /** 查附近邊度買得到。 */
  async function findNear(item) {
    const q = (item || text).trim()
    if (!q) return toast('先打要買咩')
    setNearBusy(true)
    try {
      setNear(await api.nearby(trip.id, q))
    } catch (e) { toast(e.message) }
    finally { setNearBusy(false) }
  }

  /**
   * 加入一項購物。
   *
   * ⚠️⚠️ 用戶報嘅 bug：
   *   「加唔到 item 入 shopping list」——
   *   截圖見到清單填好晒，撳「＋」個掣變灰，清單仲係空。
   *
   *   ⚠️ 根因有兩個：
   *     ① `fetch` 冇 timeout → 上傳相卡住 → `busy` 永遠 true
   *        → 個掣永遠 disabled（已喺 api.js 加 AbortController）
   *     ② 呢個 function **等相上傳完先加 item** ——
   *        4MB 相經 5G + tunnel 要成分鐘，
   *        用戶以為壞咗，其實只係等緊。
   *
   *   ✅ 新流程：**先加 item（即刻見到）→ 之後再補相**。
   *      · 個 item 1 秒內出現，用戶即刻有反應
   *      · 相上傳成功 → patch 返個 item
   *      · 相上傳失敗 → item 照樣喺度（只係冇相），
   *        而且**明確講**點解（唔係靜靜咁冇咗）
   */
  async function add() {
    const t = text.trim()
    if (!t) return
    setBusy(true)
    const hadPhoto = !!photo?.data

    // ① 先加 item —— 唔等相
    let item = null
    try {
      const r = await api.addShopping(trip.id, {
        title: t, qty: qty.trim(), category: cat,
        price: price === '' ? null : Number(price),
        assignee: assignee.trim(),
        // ⚠️ 空字串 = 用旅程嘅記帳貨幣（後端會處理）
        currency: cur || null,
      })
      item = r?.item || null
      setText(''); setQty(''); setPrice(''); setPhoto(null); setNear(null); setCur('')
      await load(); onRefresh?.()
    } catch (e) {
      toast(e.message)
      setBusy(false)
      return              // ⚠️ item 都加唔到就唔好上傳相
    } finally {
      // ⚠️ 掣要即刻解鎖 —— 唔可以等上傳
      setBusy(false)
    }

    // ② 補相（背景進行，唔阻住用戶）
    if (hadPhoto && item?.id) {
      setUploading(true)
      try {
        const { url } = await api.upload(photo?.data || '')
        await api.updateShopping(item.id, { image: url })
        await load()
      } catch (e) {
        // ⚠️ 要用「item 已經加咗，只係相冇」呢個講法 ——
        //    唔係嘅話用戶會以為成項都冇加到
        toast(`「${t}」加咗，但相片上傳失敗：${e.message}`)
      } finally { setUploading(false) }
    }
  }

  async function toggle(it) {
    // 樂觀更新（撳剔要即刻有反應）
    setData(d => ({ ...d, items: d.items.map(x =>
      x.id === it.id ? { ...x, done: it.done ? 0 : 1 } : x) }))
    try { await api.updateShopping(it.id, { done: !it.done }); await load() }
    catch (e) { toast(e.message); await load() }
  }

  async function quickAdd(line) {
    // 貼一串清單（每行一個）
    const lines = line.split('\n').map(s => s.trim()).filter(Boolean)
    if (!lines.length) return
    setBusy(true)
    try {
      for (const l of lines) {
        await api.addShopping(trip.id, { title: l.replace(/^[-•*\d.]+\s*/, ''), category: cat })
      }
      setText(''); await load(); toast(`加入咗 ${lines.length} 項 ✓`)
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div>
      {/* ── 快速加入 ── */}
      <div className="card glow" style={{ padding: 13 }}>
        <div className="row" style={{ gap: 7 }}>
          <input className="input" value={text} placeholder="要買咩？（可貼多行）"
            onChange={e => setText(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (text.includes('\n')) quickAdd(text); else add()
              }
            }}
            style={{ flex: 1 }} />
          <input className="input" value={qty} placeholder="數量"
            onChange={e => setQty(e.target.value)}
            style={{ width: 'clamp(52px, 15vw, 70px)', flex: '0 0 auto' }} />
          {/* ⚠️ 掣嘅狀態要清楚：
                 · busy    → 「…」（請求進行中）
                 · text 空 → disabled（冇嘢加）
                 ⚠️ 上傳相**唔會**令呢個掣 disabled ——
                    因為 item 已經加咗（見 `add()`）。 */}
          <button className="btn primary"
            onClick={() => text.includes('\n') ? quickAdd(text) : add()}
            disabled={busy || !text.trim()}
            title={busy ? '加緊…' : '加入'}>
            {busy ? '…' : '＋'}
          </button>
        </div>

        <div className="chips" style={{ marginTop: 9 }}>
          {CATS.map(c => (
            <button key={c.k} className={`chip ${cat === c.k ? 'on' : ''}`}
              style={{ fontSize: 10.5 }} onClick={() => setCat(c.k)}>{c.label}</button>
          ))}
        </div>

        <div className="row" style={{ gap: 7, marginTop: 9 }}>
          <input className="input" type="number" inputMode="decimal"
            value={price} placeholder="單價（可選）"
            onChange={e => setPrice(e.target.value)} style={{ flex: 1 }} />
          {/* ⚠️⚠️ 用戶要求：價錢要可以揀貨幣（去日本買嘢用 JPY）。
                 ⚠️ 預設跟旅程嘅記帳貨幣（`cur` 空 = 跟旅程）。 */}
          <CurrencyPicker value={cur} onChange={setCur} currencies={currencies} />
        </div>

        <div className="row" style={{ gap: 7, marginTop: 9 }}>
          <select className="input" value={assignee} onChange={e => setAssignee(e.target.value)}
            style={{ flex: 1 }}>
            <option value="">邊個買（可選）</option>
            {(members || []).map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        {/* ══ 相片 ══ */}
        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <input ref={fileRef} type="file" accept="image/*" capture="environment"
            onChange={pickPhoto} style={{ display: 'none' }} />
          <button className="btn sm" onClick={() => fileRef.current?.click()}>
            📷 {uploading ? '上傳緊…' : photo ? '換相' : '加相'}
          </button>
          <button className="btn sm ghost" onClick={() => findNear()}
            disabled={nearBusy || !text.trim()}>
            🏪 {nearBusy ? '搵緊…' : '附近邊度買'}
          </button>
          {photo && (
            <div className="photo-pick">
              <img src={photo.data} alt="" onClick={() => setView({ image: photo.data, title: '新相預覽' })} />
              <button onClick={() => setPhoto(null)} title="移除">✕</button>
            </div>
          )}
        </div>
      </div>

      {/* ══ 附近邊度買得到 ══ */}
      {near && (
        <div className="card glow" style={{ marginTop: 12, borderColor: 'var(--cyan)' }}>
          <div className="row">
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 900, fontSize: 13 }}>
                🏪 「{near.item}」附近邊度買得到
              </div>
              <div className="sub" style={{ fontSize: 10.5, marginTop: 3 }}>
                {near.total} 間 · 半徑 {near.radius_m}m
                {near.region && ` · ${near.region.toUpperCase()}`}
                {near.saved ? ` · ${near.saved} 間你收藏咗` : ''}
              </div>
            </div>
            <button className="btn sm ghost" onClick={() => setNear(null)}>✕</button>
          </div>

          {near.shops.length === 0 ? (
            <div className="sub" style={{ fontSize: 11, marginTop: 10, lineHeight: 1.8 }}>
              附近搵唔到。試下<b>改個講法</b>（例如「藥妝」「手信」「電器」），
              或者加大範圍。
            </div>
          ) : (
            <div style={{ marginTop: 9 }}>
              {near.shops.slice(0, 10).map((sh, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 9, padding: '8px 4px',
                  borderBottom: i < Math.min(9, near.shops.length - 1)
                    ? '1px dashed var(--border)' : 'none',
                }}>
                  <span style={{ fontSize: 15 }}>{sh.label.split(' ')[0]}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 12, fontWeight: 700,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{sh.name}</div>
                    <div className="sub" style={{ fontSize: 10 }}>
                      {sh.label.replace(/^\S+\s/, '')} · {sh.distance_m < 1000
                        ? `${sh.distance_m}m` : `${(sh.distance_m / 1000).toFixed(1)}km`}
                      {sh.hours ? ` · ${sh.hours}` : ''}
                    </div>
                  </div>
                  {sh.lat != null && (
                    <button className="btn sm ghost" style={{ fontSize: 10, padding: '3px 7px' }}
                      onClick={() => {
                        // 加到收藏（變景點）
                        api.addItem(trip.id, {
                          name: sh.name, lat: sh.lat, lng: sh.lng,
                          category: 'shopping', address: sh.address,
                          source: 'nearby', confidence: 90,
                        }).then(() => { toast('已加入收藏 ✓'); onRefresh?.() })
                          .catch(e => toast(e.message))
                      }}>＋收藏</button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="row" style={{ gap: 7, marginTop: 11 }}>
            {[800, 1500, 3000].map(r => (
              <button key={r} className={`chip ${near.radius_m === r ? 'on' : ''}`}
                style={{ fontSize: 10 }}
                onClick={() => findNear(near.item)}>
                {r < 1000 ? `${r}m` : `${r / 1000}km`}
              </button>
            ))}
            <button className="btn sm ghost" style={{ fontSize: 10, marginLeft: 'auto' }}
              onClick={async () => {
                // 直接將呢件貨加入清單（連第一間店名做備註）
                const shop = near.shops[0]
                setText(near.item)
                toast(shop ? `最近：${shop.name}` : '附近搵唔到')
              }}>用呢個名</button>
          </div>
        </div>
      )}

      {/* ── 統計 ── */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginTop: 12 }}>
          {[
            ['要買', data.pending_count],
            ['買咗', data.done_count],
            // ⚠️ 用後端換算好嘅總額（`budgetRaw` 係未換算嘅原始數）
            ['預算', `${SYMBOLS[data?.currency] || data?.currency || ''}${Number(data?.total || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`],
          ].map(([k, v]) => (
            <div key={k} className="card" style={{ padding: '9px 8px', textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 16, fontWeight: 900, color: 'var(--cyan)' }}>{v}</div>
              <div className="sub" style={{ fontSize: 9.5, marginTop: 1 }}>{k}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── 要買 ── */}
      {/* ⚠️⚠️ 總額 —— 用戶要求：「根據匯率去轉返嗰個你想要嘅錢」
              ⚠️ 總額一定要用**一個貨幣**先有意義（旅程嘅記帳貨幣）。
              ⚠️ 換唔到嘅項要**明確講**（唔可以靜靜咁唔計）。 */}
      <div className="sec" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span>要買 · {pending.length}</span>
        {/* ⚠️ 用**後端換算好嘅** `data.total`（已經按匯率加好）——
            唔可以用 `budget`（嗰個係**未換算**嘅原始數加埋一齊，
            日元同港幣加埋係冇意義嘅）。 */}
        {data?.total > 0 && (
          <span className="mono" style={{ fontSize: 12, fontWeight: 900, color: 'var(--cyan)' }}>
            {SYMBOLS[data.currency] || data.currency || ''}
            {Number(data.total).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
        )}
        {data?.unconverted > 0 && (
          <span className="sub" style={{ fontSize: 10, color: 'var(--warn)' }}>
            ⚠️ {data.unconverted} 項換唔到匯率（未計入總額）
          </span>
        )}
        {data?.rates_stale && (
          <span className="sub" style={{ fontSize: 10, color: 'var(--warn)' }}>
            ⚠️ 匯率可能舊咗
          </span>
        )}
      </div>
      {!pending.length ? (
        <Empty icon="🛒" title="購物清單空嘅" hint="上面入一項，或者貼一整份清單落去" />
      ) : (
        pending.map(it => (
          <ShopRow key={it.id} item={it} tripCurrency={data?.currency} onToggleVis={onToggleVis} onToggle={() => toggle(it)}
            onDetail={() => setDetail(it)} onChanged={load} onView={setView} />
        ))
      )}

      {/* ── 買咗 ── */}
      {done.length > 0 && (
        <>
          <div className="row" style={{ marginTop: 18 }}>
            <div className="sec" style={{ flex: 1, margin: 0 }}>買咗 · {done.length}</div>
            <button className="btn sm ghost" style={{ fontSize: 10 }}
              onClick={() => setShowDone(v => !v)}>{showDone ? '收起' : '展開'}</button>
            <button className="btn sm ghost" style={{ fontSize: 10, marginLeft: 5 }}
              onClick={async () => {
                if (!confirm(`清走 ${done.length} 項買咗嘅嘢？`)) return
                try { const r = await api.clearDoneShopping(trip.id); toast(`清走咗 ${r.deleted} 項`); await load() }
                catch (e) { toast(e.message) }
              }}>清走</button>
          </div>
          {showDone && done.map(it => (
            <ShopRow key={it.id} item={it} tripCurrency={data?.currency} onToggleVis={onToggleVis} onToggle={() => toggle(it)}
              onDetail={() => setDetail(it)} onChanged={load} onView={setView} />
          ))}
        </>
      )}

      {view && (
        <Lightbox src={view.image} title={view.title}
          subtitle={view.qty ? `${view.qty}${view.assignee ? ` · ${view.assignee} 買` : ''}` : undefined}
          onClose={() => setView(null)} />
      )}

      {detail && (
        <ShopSheet item={detail} members={members}
          onClose={() => setDetail(null)} onView={setView}
          onSaved={async () => { setDetail(null); await load() }} />
      )}
    </div>
  )
}

function ShopRow({ item, onToggle, onDetail, onChanged, onView, tripCurrency,
                   onToggleVis }) {
  return (
    <div className="item" style={{
      alignItems: 'center', cursor: 'default',
      opacity: item.done ? 0.5 : 1,
    }}>
      <button onClick={onToggle} style={{
        width: 25, height: 25, borderRadius: 'var(--r-xs)', flex: '0 0 25px',
        border: `2px solid ${item.done ? 'var(--good)' : 'var(--border-hi)'}`,
        background: item.done ? 'var(--good)' : 'transparent',
        color: '#0b0518', fontWeight: 900, fontSize: 13,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>{item.done ? '✓' : ''}</button>

      {/* ⚠️ 用 .thumb class（clamp 尺寸）而唔係固定 px ——
             固定 44px 喺 320px 機同 430px 機睇落差好遠。
             撳一下開全圖（正方形縮圖會裁走直向相嘅上下）。 */}
      {/* ⚠️⚠️ 相框（用戶要求 ④）：
             「upload 相之後有一個框架…一碌落去你就知道
              嗰個商品係有乜嘢圖案係點嘅樣，而唔係剩係得個名。」

             ⚠️ 為咩**冇相都要出個框**：
               · 有框 = 一眼知「呢度應該有張相」→ 提示你影相
               · 有一致嘅左邊距 → 一碌落去唔會參差不齊
               · 有空框先知「呢件仲未影相」，唔會以為係設計
           */}
      <div className={`thumb ${item.done ? 'done' : ''} ${item.image ? '' : 'empty'}`}
        onClick={(e) => {
          e.stopPropagation()
          if (item.image) onView?.(item)
          else onDetail?.()
        }}
        title={item.image ? '撳一下睇全圖' : '撳一下加相'}>
        {item.image
          ? <img src={item.image} alt={item.title} loading="lazy" />
          : <span className="thumb-ph">📷</span>}
      </div>

      <div className="info" onClick={onDetail} style={{ cursor: 'pointer' }}>
        <h4 style={{ textDecoration: item.done ? 'line-through' : 'none' }}>
          {catIcon(item.category)} {item.title}
            {/* ⚠️⚠️ 私人／共用（用戶要求）
                   「shopping list 係自己嘅，就算人哋加落去…佢哋應該係睇唔到嘅。」
                ⚠️ 只有自己加嘅先可以撳（後端都會擋） */}
            <span
              role={item.mine ? 'button' : undefined}
              title={item.visibility === 'group'
                ? '全組都見到' : '只有你見到'}
              onClick={e => {
                if (!item.mine) return
                e.stopPropagation()
                onToggleVis?.(item)
              }}
              style={{
                marginLeft: 5, padding: '1px 5px', borderRadius: 999,
                fontSize: 9, fontWeight: 700, verticalAlign: 'middle',
                border: '1px solid ' + (item.visibility === 'group'
                  ? 'var(--cyan)' : 'var(--border)'),
                color: item.visibility === 'group' ? 'var(--cyan)' : 'var(--dim)',
                cursor: item.mine ? 'pointer' : 'default',
                opacity: item.mine ? 1 : .6,
              }}>
              {item.visibility === 'group' ? '👥 共用' : '🔒 私人'}
            </span>
          {item.qty && <span className="sub" style={{ fontSize: 11, fontWeight: 400 }}> × {item.qty}</span>}
        </h4>
        <p>
          {item.assignee ? `${item.assignee} 買` : '未指派'}
          {/* ⚠️⚠️ 原本硬編碼 `¥` —— 用戶報「有時唔係用港幣㗎嘛」。
                 而家顯示**該項自己嘅貨幣**，如果同旅程貨幣唔同
                 就順便顯示換算後嘅數。 */}
          {item.price ? ` · ${SYMBOLS[item.currency] || item.currency || ''}${Number(item.price).toLocaleString()}` : ''}
          {item.price && item.price_trip != null && item.currency !== tripCurrency
            ? ` (≈ ${SYMBOLS[tripCurrency] || tripCurrency || ''}${Number(item.price_trip).toLocaleString()})`
            : ''}
          {item.note ? ` · ${item.note}` : ''}
        </p>
      </div>

      <button className="btn sm ghost" style={{ padding: '4px 8px', fontSize: 11 }}
        onClick={async () => {
          if (!confirm(`刪除「${item.title}」？`)) return
          try { await api.deleteShopping(item.id); await onChanged() } catch {}
        }}>✕</button>
    </div>
  )
}

function ShopSheet({ item, members, onClose, onSaved, onView }) {
  const [title, setTitle] = useState(item.title || '')
  const [qty, setQty] = useState(item.qty || '')
  const [note, setNote] = useState(item.note || '')
  const [price, setPrice] = useState(item.price ?? '')
  const [category, setCategory] = useState(item.category || 'souvenir')
  const [assignee, setAssignee] = useState(item.assignee || '')
  const [busy, setBusy] = useState(false)

  async function save() {
    if (!title.trim()) return toast('請填名稱')
    setBusy(true)
    try {
      await api.updateShopping(item.id, {
        title: title.trim(), qty, note, category, assignee,
        price: price === '' ? null : Number(price),
      })
      toast('已更新 ✓'); await onSaved()
    } catch (e) { toast(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 90, background: 'rgba(0,0,0,.68)',
      backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'flex-end',
    }}>
      <div onClick={e => e.stopPropagation()} className="card" style={{
        width: '100%', maxWidth: 640, margin: '0 auto', maxHeight: '88vh', overflowY: 'auto',
        borderRadius: 'var(--r) var(--r) 0 0', borderColor: 'var(--border-hi)',
        paddingBottom: 'calc(20px + var(--safe-b))',
      }}>
        <div className="row" style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 900, fontSize: 15 }}>改購物項目</div>
          <button className="btn sm ghost" onClick={onClose}>✕</button>
        </div>

        {/* ⚠️⚠️ 大相框（用戶要求 ④）：
               「upload 相之後有一個框架咁然後會 show 個相出嚟」
               編輯嗰陣要**大張**睇得到圖案 —— 縮圖太細認唔到。 */}
        <div className="sec" style={{ marginTop: 4 }}>相</div>
        <div className="frame-lg" onClick={() => item.image && onView?.(item)}>
          {item.image
            ? <img src={item.image} alt={title} />
            : <span className="thumb-ph">📷 未有相 —— 喺下面加</span>}
        </div>

        <div className="sec" style={{ marginTop: 12 }}>名稱</div>
        <input className="input" value={title} onChange={e => setTitle(e.target.value)} autoFocus />

        <div className="row" style={{ gap: 8, marginTop: 11 }}>
          <div style={{ flex: 1 }}>
            <div className="sec">數量</div>
            <input className="input" value={qty} placeholder="2 盒"
              onChange={e => setQty(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="sec">單價</div>
            <input className="input" type="number" value={price}
              onChange={e => setPrice(e.target.value)} />
          </div>
        </div>

        <div className="sec">分類</div>
        <div className="chips">
          {CATS.map(c => (
            <button key={c.k} className={`chip ${category === c.k ? 'on' : ''}`}
              onClick={() => setCategory(c.k)}>{c.label}</button>
          ))}
        </div>

        <div className="sec">邊個買</div>
        <div className="chips">
          <button className={`chip ${!assignee ? 'on' : ''}`} onClick={() => setAssignee('')}>未指派</button>
          {(members || []).map(m => (
            <button key={m} className={`chip ${assignee === m ? 'on' : ''}`}
              onClick={() => setAssignee(m)}>{m}</button>
          ))}
        </div>

        <div className="sec">相片</div>
        {item.image ? (
          <div className="thumb" style={{
            width: 'clamp(76px, 22vw, 96px)', height: 'clamp(76px, 22vw, 96px)',
            flex: '0 0 auto',
          }} onClick={() => onView?.(item)}>
            <img src={item.image} alt={item.title} />
          </div>
        ) : (
          <div className="sub" style={{ fontSize: 11 }}>呢件貨冇相</div>
        )}

        <div className="sec">備註</div>
        <input className="input" value={note} placeholder="例：機場免稅店買"
          onChange={e => setNote(e.target.value)} />

        <button className="btn primary wide" style={{ marginTop: 16 }} onClick={save} disabled={busy}>
          {busy ? '儲存緊…' : '儲存'}
        </button>
      </div>
    </div>
  )
}
