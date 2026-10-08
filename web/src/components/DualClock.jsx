import { useEffect, useState } from 'react'
import { nowIn, offsetMinutes, fmtOffset, sameZone, localTz, tzLabel } from '../lib/tz'
import PixelIcon from './PixelIcon'

/**
 * 雙時鐘（Dual Clock）
 * =====================
 *
 * ⚠️⚠️ 用戶問：
 *   「呢個時間係點樣抽取㗎？如果我正常去旅行我就會帶手機啦，
 *    咁係手機顯示咩時間你就顯示咩時間，定係點樣？
 *    因為你去旅行嘅話就會入唔同嘅時區呀嘛。」
 *
 * 答案：**兩個都要** —— 佢哋答緊唔同嘅問題：
 *
 *   ┌──────────────────┬─────────────────────────────────┐
 *   │ 手機時間          │ 你**身處**邊度嘅時間             │
 *   │ (= 你嘅錶)        │ 手機自己跟網絡／GPS 調整         │
 *   │                  │ → 「我而家幾點？」               │
 *   ├──────────────────┼─────────────────────────────────┤
 *   │ 目的地時間        │ 旅程城市嘅時間                   │
 *   │ (⚠️ 手機唔會話你知)│ → 「嗰度而家幾點？」            │
 *   └──────────────────┴─────────────────────────────────┘
 *
 * ⚠️ 為咩「目的地時間」重要：
 *   · 你喺香港計劃去東京 → 想知東京而家幾點（排行程／訂位）
 *   · 你喺東京想打返香港 → 想知香港而家幾點（唔好半夜打）
 *   · 行程寫「Day 3 早上 9 點」→ 係**嗰度**嘅 9 點
 *
 * ⚠️⚠️ 但如果兩邊**同一個時區**（例如香港 → 台北？唔係，
 *    但香港 → 澳門／深圳係）→ 唔應該顯示兩個一樣嘅鐘，
 *    否則用戶會以為自己睇錯。
 */
export default function DualClock({ timezone, label, compact = false }) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    // ⚠️ 30 秒更新一次就夠 —— 顯示到分鐘。每秒更新係浪費電。
    const t = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(t)
  }, [])

  const myTz = localTz()
  const destTz = timezone || null
  const same = !destTz || sameZone(myTz, destTz)

  const here = nowIn(myTz) || fmt(now)
  const there = destTz ? nowIn(destTz) : null

  const myOff = offsetMinutes(myTz)
  const destOff = offsetMinutes(destTz)
  const diffMin = (myOff != null && destOff != null) ? destOff - myOff : null

  // ══ 只有一個時區（或者同一個）→ 顯示單鐘 ══
  if (same || !there) {
    return (
      <div style={{ textAlign: 'center' }}>
        <div className="mono" style={{
          fontSize: compact ? 30 : 46, fontWeight: 900, lineHeight: 1,
          letterSpacing: -1, color: 'var(--fg)',
        }}>
          {here.hh}<span style={{ opacity: .4 }}>:</span>{here.mm}
        </div>
        {!compact && (
          <div className="sub" style={{ fontSize: 11, marginTop: 5 }}>
            {weekdayZh(here.weekday)} · {fmtDate(here.iso)}
          </div>
        )}
      </div>
    )
  }

  // ══ 兩個時區 → 雙鐘 ══
  return (
    <div style={{ textAlign: 'center' }}>
      {/* 目的地（大）*/}
      <div className="mono" style={{
        fontSize: compact ? 30 : 46, fontWeight: 900, lineHeight: 1,
        letterSpacing: -1,
        background: 'linear-gradient(100deg, var(--edge-purple-hi), var(--edge-cyan))',
        WebkitBackgroundClip: 'text', backgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      }}>
        {there.hh}<span style={{ opacity: .4 }}>:</span>{there.mm}
      </div>

      <div className="sub" style={{
        fontSize: 10.5, marginTop: 5,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
      }}>
        <PixelIcon name="globe" size={12} />
        <span>{label || tzLabel(destTz)}</span>
        <span style={{ opacity: .55 }}>{fmtOffset(destOff)}</span>
      </div>

      {/* 你身處嘅時間（細）*/}
      <div style={{
        marginTop: 9, paddingTop: 8,
        borderTop: '1px dashed var(--border)',
        fontSize: 11, color: 'var(--dim)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      }}>
        <span>你嗰邊</span>
        <span className="mono" style={{ color: 'var(--fg)', fontWeight: 800 }}>
          {here.hh}:{here.mm}
        </span>
        {diffMin != null && diffMin !== 0 && (
          <span style={{ opacity: .7 }}>
            （{diffMin > 0 ? '快' : '慢'}{fmtDiff(diffMin)}）
          </span>
        )}
      </div>
    </div>
  )
}

function fmt(d) {
  const p = (n) => String(n).padStart(2, '0')
  return {
    hh: p(d.getHours()), mm: p(d.getMinutes()),
    iso: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    weekday: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()],
  }
}

const WD = { Sun: '星期日', Mon: '星期一', Tue: '星期二', Wed: '星期三',
             Thu: '星期四', Fri: '星期五', Sat: '星期六' }
const weekdayZh = (w) => WD[w] || ''

function fmtDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '')
  if (!m) return ''
  return `${Number(m[2])}月${Number(m[3])}日`
}

/** 分鐘 → 「3 個鐘」「3 個半鐘」「45 分」。 */
function fmtDiff(min) {
  const a = Math.abs(min)
  const h = Math.floor(a / 60), m = a % 60
  if (h && m) return `${h} 個半鐘`
  if (h) return `${h} 個鐘`
  return `${m} 分`
}
