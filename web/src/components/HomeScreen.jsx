import { useEffect, useState } from 'react'
import WorldClocks from './WorldClocks'
import Avatar from './Avatar'
import PixelIcon from './PixelIcon'

/**
 * 手機主畫面（Home Screen）
 * ========================
 * 用戶要求（原文）：
 *   「入到去係一部手機畫面，有 apps —— planner / Organize / Money」
 *
 * 所以 Wander 唔係「一個網站」，而係「一部旅行裝置」：
 *   開機動畫 → 主畫面 → 撳 icon 入 app
 *
 * ⚠️ 為咩用 icon 格而唔係底部 tab：
 *   · 用戶講明想要手機感覺
 *   · 旅行 app 嘅功能係「一啲獨立工具」（行程／整理／分帳／購物），
 *     唔係「一個 app 嘅幾個 tab」—— icon 格更貼合心理模型
 *   · 但底部 dock 保留（快速返回主畫面）
 */

/** App 定義：id, 名, 中文, emoji, 漸變色, 陰影光 */
export const APPS = [
  { id: 'calendar', label: 'Planner', zh: '行程', icon: '🗓',
    grad: 'linear-gradient(140deg,#a855f7,#7c3aed)', glow: '#a855f7' },
  { id: 'discover', label: 'Organize', zh: '整理', icon: '📥',
    grad: 'linear-gradient(140deg,#22d3ee,#0891b2)', glow: '#22d3ee' },
  { id: 'money', label: 'Money', zh: '分帳', icon: '💸',
    grad: 'linear-gradient(140deg,#34d399,#059669)', glow: '#34d399' },
  { id: 'shopping', label: 'Shopping', zh: '購物', icon: '🛒',
    grad: 'linear-gradient(140deg,#f472b6,#db2777)', glow: '#f472b6' },
  // ⚠️⚠️ 用戶要求：唔好叫 Zones，叫 **Saved**（收藏）
  //    入面係「你收藏咗嘅景點」+ 搜尋 + 地名 facet
  { id: 'saved', label: 'Saved', zh: '收藏', icon: '🔖',
    grad: 'linear-gradient(140deg,#fbbf24,#d97706)', glow: '#fbbf24' },
  { id: 'map', label: 'Map', zh: '地圖', icon: '🗺',
    grad: 'linear-gradient(140deg,#818cf8,#4f46e5)', glow: '#818cf8' },
  { id: 'friends', label: 'Friends', zh: '朋友', icon: '👥',
    grad: 'linear-gradient(140deg,#fb7185,#e11d48)', glow: '#fb7185' },
  { id: 'settings', label: 'Settings', zh: '設定', icon: '⚙️',
    grad: 'linear-gradient(140deg,#94a3b8,#475569)', glow: '#94a3b8' },
]

export function AppIcon({ app, onClick, badge }) {
  const [down, setDown] = useState(false)
  return (
    <button
      data-tour={app.id}
      onPointerDown={() => setDown(true)}
      onPointerUp={() => setDown(false)}
      onPointerLeave={() => setDown(false)}
      onClick={onClick}
      style={{
        background: 'none', border: 'none', padding: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7,
        cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
        // ⚠️ 像素風：唔用圓滑 scale，用硬位移（撳落去「沉一格」）
        transform: down ? 'translate(3px,3px)' : 'none',
        transition: 'transform .06s steps(2, end)',
      }}>
      {/* ⚠️⚠️ `data-app` 令 CSS 可以按主題上色（用戶要求 ③）：
             「因為我哋有唔同嘅主題啦，所以 Apps 嘅 icon
              應該都要跟返類似嗰個對應嘅主題，
              即係色調可能要改少少。」

             ⚠️ 為咩唔再用 inline `background: app.grad`：
               inline style 寫死咗色，CSS 主題變數蓋唔到。
               改用 CSS attribute selector 之後，每個主題
               只要定義 `--app-a`…`--app-g` 就得。
           */}
      <div className="app-ico" data-app={app.id} style={{
        // ⚠️ clamp 而唔係固定 62px
        width: 'clamp(52px, 14.5vw, 66px)',
        aspectRatio: '1',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
        // ⚠️ 硬陰影由 .app-ico 負責（唔可以有 blur）
        boxShadow: down ? 'none' : undefined,
      }}>
        {/* ⚠️ 像素圖示，唔再用 emoji ——
              emoji 每部機唔同樣，而且冇得控制線條粗細 */}
        <PixelIcon name={app.id} size={38} title={app.label} />
        {badge > 0 && (
          <span style={{
            position: 'absolute', top: -6, right: -6,
            minWidth: 20, height: 20, borderRadius: 2, padding: '0 5px',
            background: 'var(--bad)', color: '#fff',
            fontSize: 11, fontWeight: 900, lineHeight: '20px', textAlign: 'center',
            border: '2px solid #0b0518',
          }}>{badge > 99 ? '99+' : badge}</span>
        )}
      </div>
      <div style={{ textAlign: 'center', lineHeight: 1.25 }}>
        {/* ⚠️ 英文名用像素字體（Press Start 2P）——
              呢個字體冇中文字，所以中文名一定要留返系統字體，
              否則會出豆腐格。 */}
        <div className="pix" style={{ fontSize: 8.5, color: 'var(--fg)' }}>{app.label}</div>
        <div className="sub" style={{ fontSize: 9.5 }}>{app.zh}</div>
      </div>
    </button>
  )
}

export default function HomeScreen({ trip, items, stops, onOpen, onPickTrip, onNewTrip,
                                     trips = [], user, badges,
                                     wantPick = false, onPickDone }) {
  const [now, setNow] = useState(new Date())
  const [picking, setPicking] = useState(false)
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(t)
  }, [])

  // ⚠️⚠️ 用戶要求 ③：撳 app 但未有旅程 → 留喺主頁並自動打開選擇器
  //     （唔使令用戶自己搵邊度揀）
  useEffect(() => {
    if (wantPick) setPicking(true)
  }, [wantPick])

  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')

  return (
    <div style={{
      minHeight: '100%',
      // ⚠️ 用 clamp 而唔係固定 22px —— 320px 嘅機用 22px×2 = 44px 邊距，
      //    剩返 276px 放 4 個 icon（每個 62px + gap）→ 啱啱爆。
      padding: '0 clamp(14px, 5vw, 22px)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* ══ 時鐘 ══ */}
      {/*   ⚠️⚠️ 用戶要求（改過設計）：
             「Show 兩個時區囉，第一個最上面嗰個係**手機時間**，
              第二個就係有得比你揀 —— 你可以輸入嗰個城市嘅名，
              用英文或者中文都可以，之後呢例如你揀咗，
              然後就會有對應嘅時區。」

           ⚠️ 所以係（同之前**相反**）：
              · **上面大字 = 你手機嘅時間**（你身處嗰度）
              · **下面細字 = 你揀嘅城市**（可以改，用 CityPicker）
           ⚠️ 之前係反過嚟（目的地做大字），用戶話唔啱。
           ⚠️ 揀咗嘅城市記喺 localStorage，唔使每次再揀。 */}
      <div style={{ textAlign: 'center', paddingTop: 8, paddingBottom: 20 }}>
        <WorldClocks tripCity={stops?.[0]?.city}
          tripTz={stops?.[0]?.timezone} />
        <div className="row" style={{ justifyContent: 'center', gap: 7, marginTop: 10 }}>
          <Avatar id={user?.avatar} size={24} />
          <span className="sub" style={{ fontSize: 11.5 }}>
            {now.toLocaleDateString('zh-HK', { month: 'long', day: 'numeric', weekday: 'long' })}
            {user?.display_name ? ` · ${user.display_name}` : ''}
          </span>
        </div>
      </div>

      {/* ══ 好友請求通知 ══ */}
      {(badges?.friends || 0) > 0 && (
        <button onClick={() => onOpen('friends')} className="tap" style={{
          display: 'flex', alignItems: 'center', gap: 11, width: '100%',
          background: 'linear-gradient(100deg, rgba(251,113,133,.22), rgba(244,114,182,.12))',
          border: '1px solid var(--bad)', borderRadius: 'var(--r)',
          padding: '12px 14px', marginBottom: 12, textAlign: 'left',
          boxShadow: '0 4px 18px rgba(251,113,133,.22)',
        }}>
          <span style={{ fontSize: 22 }}>👥</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 900, fontSize: 13, color: 'var(--bad)' }}>
              你有一個交友邀請
            </div>
            <div className="sub" style={{ fontSize: 10.5, marginTop: 2 }}>
              {badges.friends} 個人想加你做朋友 · 撳入去睇
            </div>
          </div>
          <span style={{ color: 'var(--bad)', fontSize: 16 }}>›</span>
        </button>
      )}

      {/* ══ 當前旅程卡（app 內揀旅程）══ */}
      {trip ? (
        <button onClick={() => setPicking(v => !v)} className="tap" style={{
          background: 'linear-gradient(135deg, rgba(168,85,247,.20), rgba(34,211,238,.13))',
          border: '1px solid var(--border-hi)', borderRadius: 'var(--r)',
          padding: 15, marginBottom: 22, textAlign: 'left', width: '100%',
          boxShadow: 'var(--glow)',
        }}>
          <div className="sub" style={{ fontSize: 10, letterSpacing: 1.4 }}>當前旅程</div>
          <div style={{
            fontSize: 17, fontWeight: 900, marginTop: 5,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{trip.name}</div>
          <div className="row" style={{ marginTop: 5 }}>
            <div className="sub" style={{ fontSize: 11, flex: 1 }}>
              {trip.start_date || '未定日期'}
              {stops?.length > 0 && ` · ${stops.map(s => s.city).join(' → ')}`}
              {' · '}✦ {items.length}
            </div>
            <span className="sub" style={{ fontSize: 10.5 }}>
              {picking ? '收起 ▲' : `轉旅程 (${trips.length}) ▼`}
            </span>
          </div>
        </button>
      ) : (
        <button onClick={() => setPicking(v => !v)} className="tap" style={{
          background: 'var(--surface-2)', border: '1px dashed var(--border-hi)',
          borderRadius: 'var(--r)', padding: 18, marginBottom: 22, width: '100%',
          fontSize: 13, fontWeight: 700, color: 'var(--fg)',
        }}>
          ✈️ 未揀旅程 —— 撳呢度揀一個
        </button>
      )}

      {/* ══ 旅程選擇（app 內）══ */}
      {picking && (
        <div className="card" style={{ marginBottom: 18, padding: 8 }}>
          <div className="sub" style={{ fontSize: 10.5, padding: '4px 6px 8px' }}>
            揀一個旅程 —— 所有 app 都會跟住轉
          </div>
          {trips.map(t => (
            <button key={t.id} onClick={() => { setPicking(false); onPickTrip?.(t.id) }}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                padding: '10px 9px', borderRadius: 'var(--r-xs)', textAlign: 'left',
                background: t.id === trip?.id ? 'var(--surface-2)' : 'transparent',
                borderBottom: '1px dashed var(--border)',
              }}>
              <span style={{ fontSize: 17 }}>{t.id === trip?.id ? '✅' : '🗂'}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: 13 }}>{t.name}</div>
                <div className="sub" style={{ fontSize: 10.5 }}>
                  {t.start_date || '未定日期'} · {t.days || '?'} 日
                </div>
              </div>
            </button>
          ))}
          <button className="btn primary wide" style={{ marginTop: 9 }}
            onClick={() => { setPicking(false); onNewTrip?.() }}>＋ 開新旅程</button>
        </div>
      )}

      {/* ══ App 格 ══ */}
      {/* ⚠️⚠️ 用 .app-grid（百分比排版）而唔係寫死 px ——
             用戶要求：「唔建議用數量，應該用 percentage 表達」
             欄數由容器闊度自動決定，唔會喺窄機爆或者喺闊機太疏。 */}
      <div className="app-grid" style={{ marginBottom: '6%' }}>
        {APPS.map(a => (
          <AppIcon key={a.id} app={a} badge={badges?.[a.id]} onClick={() => onOpen(a.id)} />
        ))}
      </div>

      {/* ══ 快速統計 ══ */}
      <div className="stat-grid" style={{ marginTop: 'auto', paddingBottom: '3%' }}>
        {[
          ['景點', items.length],
          ['城市', stops?.length || 0],
          ['日數', trip?.days || 0],
        ].map(([k, v]) => (
          <div key={k} style={{
            background: 'var(--surface-2)', borderRadius: 'var(--r-sm)', padding: '9px 8px',
            textAlign: 'center', border: '1px solid var(--border)',
          }}>
            <div className="mono" style={{ fontSize: 17, fontWeight: 900, color: 'var(--cyan)' }}>{v}</div>
            <div className="sub" style={{ fontSize: 9.5, marginTop: 1 }}>{k}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
