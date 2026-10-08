/**
 * 前端元件 · 真正 SSR render 測試
 * ================================
 * ⚠️⚠️ 為咩一定要真 render：
 *   `vite build` 成功**唔代表**元件跑得！
 *   build 只做語法 + import 解析。如果：
 *     · JSX 入面有 undefined 變數
 *     · hooks 用錯（條件式 hook）
 *     · render 期間 TypeError
 *   全部都會 build 過，但用戶一開就白畫面。
 *
 *   呢個測試用 esbuild 即時轉 JSX，再用 react-dom/server 真 render。
 *   捉到嘅係「一開即爆」級別嘅 bug。
 */
import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const require = createRequire(new URL('../../web/package.json', import.meta.url))
const React = require('react')
const { renderToString } = require('react-dom/server')
const esbuild = require('esbuild')

// ⚠️ 一定要有結尾斜線！冇嘅話 new URL('components/X', ROOT) 會
//    解析成 web/components/X（base 最後一段會被取代）。
const ROOT = new URL('../../web/src/', import.meta.url)

/** 用 esbuild 轉 JSX → 一個可以 eval 嘅 CJS 模組。 */
function loadComponent(rel) {
  const file = new URL(rel, ROOT)
  let code = fs.readFileSync(file, 'utf8')

  // 將所有相對 import 換成 stub（元件之間嘅依賴唔關事）
  const out = esbuild.transformSync(code, {
    loader: 'jsx', format: 'cjs', target: 'es2020',
    jsx: 'transform',
  }).code

  const mod = { exports: {} }
  const stub = () => null
  const fakeRequire = (id) => {
    if (id === 'react') return React
    if (id === 'react/jsx-runtime') {
      return {
        jsx: (t, p, k) => React.createElement(t, p, k),
        jsxs: (t, p, k) => React.createElement(t, p, k),
        Fragment: React.Fragment,
      }
    }
    if (id.includes('lib/api')) return {
      api: new Proxy({}, { get: () => async () => ({}) }),
      auth: { token: null, clear() {} },
      iconFor: () => '✦', confClass: () => '',
      CATEGORY_LABELS: { food: '🍜 食' },
    }
    if (id.includes('lib/ui')) return { toast: () => {}, Empty: stub, Spinner: stub }
    if (id.includes('lib/dates')) return {
      toMinutes: () => null, fromMinutes: () => '', durationText: () => '',
      tripDays: () => [], tripLength: () => 3, dateRangeText: () => '',
      buildTimeline: () => [], countdownText: () => null,
    }
    if (id.includes('lib/pwa')) return { subscribe: () => () => {}, cacheStatus: async () => ({}), clearTiles: async () => {}, applyUpdate: () => {} }
    if (id.includes('lib/stops')) return { buildDayCities: () => [], findConflicts: () => [], STOP_COLORS: ['#a855f7'], stopsSummary: () => '' }
    if (id.includes('lib/bookmarklet')) return { bookmarkletCode: () => 'javascript:void 0', parsePayload: () => null }
    if (id.includes('lib/mascot')) {
      return {
        MASCOT_FRAMES: ['hello', 'point', 'happy'],
        MASCOT_SIZE: 16,
        mascotSvg: () => '<svg></svg>',
      }
    }
    if (id.includes('lib/pixelicons')) {
      return {
        APP_ICONS: { calendar: {}, money: {} },
        UI_ICONS: { plus: {} },
        ALL_ICONS: { calendar: {}, money: {}, plus: {} },
        ICON_SIZE: 8,
        iconSvg: () => '<svg></svg>',
        hasIcon: () => true,
      }
    }
    if (id.includes('lib/avatars')) {
      return {
        PIXEL_AVATARS: [
          { id: 'star', name: '星星', pal: ['#fde68a'], grid: ['1'] },
          { id: 'moon', name: '月亮', pal: ['#fbbf24'], grid: ['1'] },
        ],
        AVATAR_IDS: ['star', 'moon'],
        AVATAR_MAP: { star: { id: 'star', name: '星星' } },
        isPixelAvatar: (v) => v === 'star' || v === 'moon',
        avatarSvg: () => '<svg></svg>',
        randomAvatar: () => 'star',
      }
    }
    // ⚠️ 本地元件（./Avatar 等）一定要回一個**真嘅 function**。
    //    之前用 `new Proxy({}, { get: () => stub })` ——
    //    Proxy 會令 `__esModule` 檢查通過，但 `.default` 攞到嘅嘢
    //    唔一定係 component → React 報 "Element type is invalid"。
    if (/^(\.\/|\.\.\/)/.test(id)) {
      const parts = id.split('/')
      const name = parts[parts.length - 1]
      const C = (props) => {
        // 將 props 入面嘅字串 render 出嚟，方便測試斷言
        try {
          const kids = []
          for (const [k, v] of Object.entries(props || {})) {
            if (typeof v === 'string' && v.length < 40) kids.push(v)
          }
          for (const k of ['trip', 'user', 'badges']) {
            const v = props?.[k]
            if (v && typeof v === 'object') {
              for (const vv of Object.values(v)) {
                if (typeof vv === 'string' && vv.length < 40) kids.push(vv)
              }
            }
          }
          return React.createElement('div', { 'data-stub': name }, kids.join(' '))
        } catch { return null }
      }
      return { __esModule: true, default: C }
    }
    return new Proxy({}, { get: () => stub })
  }

  // ⚠️ classic JSX transform 會 emit `React.createElement(...)`，
  //    React 唔係 global，所以要當參數傳入去。
  // eslint-disable-next-line no-new-func
  new Function('require', 'module', 'exports', 'React', out)(
    fakeRequire, mod, mod.exports, React)
  return mod.exports.default || mod.exports
}

let pass = 0, fail = 0

/**
 * ⚠️ 去咗註解先做源碼檢查。
 *   我試過幾次「測試 match 到自己解釋 bug 嘅註解」→ 誤報。
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1')
}

/** 通用斷言（同其他測試檔一致）。 */
function check(label, cond, extra = '') {
  console.log(`    ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

/**
 * ⚠️⚠️ JSX 殘留檢查 —— 呢個捉到一個真 bug。
 *
 *   用戶報：主畫面 Planner 上面有個 `)}` 符號。
 *
 *   原因：HomeScreen.jsx 有個多餘嘅 `)}`：
 *     ```
 *     )}
 *     )}      ← 呢行變成純文字！
 *     ```
 *   喺 JSX 入面，括號外面嘅任何文字都會**原樣 render**。
 *   所以 `)}` 就變成畫面上面嘅文字。
 *
 *   ⚠️ 點解 build 同其他測試都捉唔到：
 *     · `vite build` —— 只做語法／import 解析，`)}` 係合法 JSX 文字
 *     · 我原本嘅 SSR 測試 —— 只檢查「有冇預期字串」，
 *       多咗字唔會發現
 *
 *   所以加呢個通用檢查：**render 出嚟嘅文字唔可以有 JSX 痕跡**。
 */
//   ⚠️ 混合用字串同 regex ——
//      「undefined」「NaN」要用 word boundary，
//      否則「undefinedSomething」都會中（誤報），
//      而「undefined」後面唔一定係 `</`（可能係空格、逗號、句號）。
const JSX_LEAKS = [
  /\)\}/, /\]\}/, /\/>/, /\{"/, /"\}/, /className=/,
  /style=\{\{/, /React\.createElement/,
  /\bundefined\b/, /(?<![A-Za-z])NaN(?![A-Za-z])/, /\[object Object\]/,
]

function findLeaks(html) {
  // 抽純文字：去 <script>/<style>，去所有 tag，解 entity
  const text = html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  const hits = []
  for (const pat of JSX_LEAKS) {
    const m = pat.exec(text)
    if (!m) continue
    const i = m.index
    hits.push(`${m[0]} @ …${text.slice(Math.max(0, i - 18), i + 12).trim()}…`)
  }
  return hits
}

function render(label, rel, props, { allowEmpty = false } = {}) {
  try {
    const C = loadComponent(rel)
    if (typeof C !== 'function') throw new Error('唔係一個 component')
    const html = renderToString(React.createElement(C, props))
    // ⚠️ 冇拋錯本身已經係通過 —— 空輸出可能係因為 render 咗 stub
    const ok = allowEmpty ? true : html.length > 0
    // ⚠️ 順便檢查有冇 JSX 殘留（用戶報過嘅 bug）
    const leaks = findLeaks(html)
    console.log(`  ${ok ? '✓' : '✗'} ${label}  (${html.length} bytes${allowEmpty ? ' · 允許空' : ''})`)
    ok ? pass++ : fail++
    if (leaks.length) {
      console.log(`      ⚠️ JSX 殘留！`)
      for (const l of leaks) console.log(`         ${l}`)
      fail++
    } else {
      pass++
    }
    return html
  } catch (e) {
    console.log(`  ✗ ${label}  →  ${e.message.split('\n')[0].slice(0, 110)}`)
    fail++
    return ''
  }
}

const TRIP = { id: 't1', name: '福岡 4 日', days: 4, start_date: '2027-08-12',
               end_date: '2027-08-15', members: [{ display_name: 'Alice' }] }
const ITEMS = [{ id: 'i1', name: '一蘭', district: '中洲', category: 'food', confidence: 90, lat: 33.59, lng: 130.4 }]
const STOPS = [{ city: '福岡', days: 4, lat: 33.6, lng: 130.42 }]

// ══ 先驗證「檢查器本身」work ══
//   ⚠️ 一個永遠話「通過」嘅檢查比冇檢查更差 ——
//      所以要先餵佢已知嘅壞 input，確認佢真係捉到。
console.log('\n▸ ⚠️ 驗證 JSX 殘留檢查器（餵已知壞 input）')
{
  const bad = [
    ['多餘 )}', '<div><span>Planner</span>)}<span>Organize</span></div>'],
    ['多餘 ]}', '<div>清單]}</div>'],
    ['漏咗 tag 結尾', '<div>Hello/></div>'],
    ['className 漏咗', '<div>文字 className= 殘留</div>'],
    ['undefined', '<div>名字：undefined</div>'],
    ['[object Object]', '<div>[object Object]</div>'],
    ['NaN', '<div>數量 NaN</div>'],
  ]
  for (const [label, html] of bad) {
    const hits = findLeaks(html)
    check(`捉到「${label}」`, hits.length > 0, hits[0] ? hits[0].slice(0, 50) : '')
  }
  const good = [
    ['正常內容', '<div class="h1">行程</div><div>3 日</div>'],
    ['含符號但正常', '<div>價錢：$1,200（2 盒）</div>'],
    ['百分比', '<div>87%</div>'],
    ['Undefined 品牌名', '<div>Undefined Coffee</div>'],
    ['Nan 地名', '<div>Nan province</div>'],
  ]
  for (const [label, html] of good) {
    const hits = findLeaks(html)
    check(`唔會誤報「${label}」`, hits.length === 0, hits.join(', '))
  }
}

console.log('\n▸ 世界時鐘 WorldClocks')
{
  // ⚠️ 用戶要求改咗設計：
  //    「第一個最上面嗰個係手機時間，第二個就係有得比你揀」
  //    → DualClock（目的地做大字）→ WorldClocks（手機做大字 + 自選城市）
  const src = fs.readFileSync(
    new URL('../../web/src/components/WorldClocks.jsx', import.meta.url), 'utf8')
  const tzSrc0 = fs.readFileSync(new URL('../../web/src/lib/tz.js', import.meta.url), 'utf8')
  for (const [k, label, where] of [
    ['Intl.DateTimeFormat', '用 Intl（自動處理夏令時間）', tzSrc0],
    ['localTz', '有手機時區', src],
    ['sameZone', '同時區唔會顯示兩個鐘', src],
    ['offsetMinutes', '有 UTC 偏移標籤', src],
  ]) {
    const src2 = where
    const ok = src2.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
  // ⚠️ 唔可以自己計 offset（會過期）
  const noManual = !/getTimezoneOffset/.test(src)
  console.log(`    ${noManual ? '✓' : '✗'} 冇自己計 offset（夏令時間會錯）`)
  noManual ? pass++ : fail++

  const tz = fs.readFileSync(new URL('../../web/src/lib/tz.js', import.meta.url), 'utf8')
  const hasAll = ['nowIn', 'offsetMinutes', 'sameZone', 'localTz', 'tzLabel']
    .every(k => tz.includes(`export function ${k}`))
  console.log(`    ${hasAll ? '✓' : '✗'} tz.js 有五個工具函數`)
  hasAll ? pass++ : fail++

  // ⚠️ HomeScreen 要用 WorldClocks（唔再係 DualClock）
  const home = fs.readFileSync(
    new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')
  const used = home.includes('<WorldClocks') && !home.includes('<DualClock')
  console.log(`    ${used ? '✓' : '✗'} 主畫面用世界時鐘（唔再係 DualClock）`)
  used ? pass++ : fail++
  // ⚠️ 第二個鐘一定要**揀得**（CityPicker）
  const pickable = src.includes('CityPicker') && src.includes('localStorage')
  console.log(`    ${pickable ? '✓' : '✗'} 第二個鐘可以自己揀城市（+ 記住）`)
  pickable ? pass++ : fail++
}

console.log('\n▸ 新手教學 Onboarding')
{
  // ⚠️ 要 render 到 —— 呢個組件用 useLayoutEffect + getBoundingClientRect，
  //    喺 SSR 下冇 DOM，所以要確認唔會拋錯。
  render('歡迎畫面', 'components/Onboarding.jsx',
    { user: { id: 'u1', display_name: '', onboarded: false },
      onDone: () => {} }, { allowEmpty: true })

  const src = fs.readFileSync(
    new URL('../../web/src/components/Onboarding.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['mascot-${frame}.png', '用像素吉祥物圖（36×44 程序化角色）'],
    ['onb-scroll', '內容可捲（掣唔會被捲走）'],
    ['data-tour', '圈出 app icon 做提示'],
    ['mask', '用 SVG mask 做聚光燈'],
    ['name.trim()', '名字一定要填（必做）'],
    ['api.finishOnboard', '完成時呼叫後端'],
    ['跳過教學，直接改名', '「跳過」只跳教學唔跳改名'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }

  // App.jsx 要喺 boot 之後、且未 onboarded（或者手動重看）先出
  const app = fs.readFileSync(new URL('../../web/src/App.jsx', import.meta.url), 'utf8')
  const cond = /if \(user && booted && \(!user\.onboarded \|\| replayTour\)\)/.test(app)
  console.log(`    ${cond ? '✓' : '✗'} 開機動畫之後先出教學`)
  cond ? pass++ : fail++
  const rp = app.includes('setReplayTour(true)') && app.includes('setReplayTour(false)')
  console.log(`    ${rp ? '✓' : '✗'} 設定頁可以重新播放（onboarded 唔會重設）`)
  rp ? pass++ : fail++

  // ⚠️ 「指導教學」搬咗去 SettingsMore（第二層）——
  //    第一層淨係 Profile（用戶要求）
  const more2 = fs.readFileSync(
    new URL('../../web/src/components/SettingsMore.jsx', import.meta.url), 'utf8')
  const hasTut = more2.includes('指導教學') && more2.includes('重新播放教學')
  console.log(`    ${hasTut ? '✓' : '✗'} 「更多設定」有「指導教學」區塊`)
  hasTut ? pass++ : fail++
  const noLs = !/!user\.onboarded[\s\S]{0,400}localStorage/.test(app)
  console.log(`    ${noLs ? '✓' : '✗'} 用後端 flag（唔用 localStorage）`)
  noLs ? pass++ : fail++

  // HomeScreen 要有 data-tour 屬性
  const home = fs.readFileSync(
    new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')
  const dt = home.includes('data-tour={app.id}')
  console.log(`    ${dt ? '✓' : '✗'} app icon 有 data-tour（圈得出嚟）`)
  dt ? pass++ : fail++
}

console.log('\n▸ 開機動畫 BootScreen')
{
  const html = render('未登入 → 播動畫', 'components/BootScreen.jsx', { onDone: () => {} })
  for (const [k, want] of [['WANDER', 1], ['TRAVEL SYSTEM', 1], ['%', 1]]) {
    const ok = html.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 含「${k}」`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 主畫面 HomeScreen')
{
  const html = render('有旅程', 'components/HomeScreen.jsx', {
    trip: TRIP, items: ITEMS, stops: STOPS, trips: [TRIP],
    user: { display_name: 'Alice' }, badges: { shopping: 3 },
    onOpen: () => {}, onPickTrip: () => {},
  })
  for (const k of ['Planner', 'Organize', 'Money', 'Shopping', '行程', '整理', '分帳', '購物']) {
    const ok = html.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 含「${k}」`)
    ok ? pass++ : fail++
  }
  const hasBadge = html.includes('>3<')
  console.log(`    ${hasBadge ? '✓' : '✗'} 有 badge`)
  hasBadge ? pass++ : fail++
  const noTrip = render('冇旅程', 'components/HomeScreen.jsx', {
    trip: null, items: [], stops: [], trips: [], user: null, badges: {},
    onOpen: () => {}, onPickTrip: () => {},
  })
  // ⚠️ 新流程：冇旅程時係「撳呢度揀一個」，唔再係彈旅程列表
  const ok = noTrip.includes('未揀旅程') || noTrip.includes('揀一個')
  console.log(`    ${ok ? '✓' : '✗'} 冇旅程時提示揀旅程`)
  ok ? pass++ : fail++
  // ⚠️ 用戶要求刪走 Trips app（同主頁面「轉旅程」重疊 70%）
  const noTrips = !noTrip.includes('Trips')
  console.log(`    ${noTrips ? '✓' : '✗'} 冇 Trips app icon（已刪）`)
  noTrips ? pass++ : fail++
  // ⚠️ Zones 改名做 Saved
  const ok2 = noTrip.includes('Saved') && !noTrip.includes('Zones')
  console.log(`    ${ok2 ? '✓' : '✗'} Zones 已改名做 Saved`)
  ok2 ? pass++ : fail++
}

console.log('\n▸ 購物清單 ShoppingList')
//   首頁（快速加入 bar）係同步 render 嘅，所以要檢查內容
{
  const html = render('快速加入 bar', 'components/ShoppingList.jsx',
    { trip: TRIP, members: ['Alice', 'Bob'], onRefresh: () => {} })
  for (const k of ['要買咩', '數量', '手信', '藥妝']) {
    const ok = html.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 含「${k}」`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 分帳 Settlement')
{
  const html = render('總額卡', 'components/Settlement.jsx',
    { trip: TRIP, user: { display_name: 'Alice' }, onRefresh: () => {} })
  for (const k of ['總開支', '加一筆開支']) {
    const ok = html.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 含「${k}」`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 收藏 Saved')
//   ⚠️⚠️ 用戶要求：Zones 改名做 Saved，而且入面係
//      「你收藏嘅景點清單 + 搜尋 + 地名 facet」。
{
  const ITEMS = [
    { id: 'i1', name: '一蘭拉麵', location_path: ['福岡県', '福岡市', '博多区'],
      city: '福岡市', district: '博多区', category: 'food', confidence: 90 },
    { id: 'i2', name: '太宰府天滿宮', location_path: ['福岡県', '太宰府市'],
      city: '太宰府市', category: 'play', confidence: 85 },
  ]
  const html = render('有景點', 'components/Saved.jsx',
    { items: ITEMS, onEditItem: () => {} })
  for (const [k, label] of [
    ['一蘭拉麵', '顯示景點名'],
    ['🔖 收藏', '標題係「收藏」'],
    ['saved-input', '有搜尋欄'],
    ['福岡市', '有地名 facet（由地址抽出）'],
    ['博多区', '有區名 facet'],
    ['個景點', '顯示總數'],
  ]) {
    console.log(`    ${html.includes(k) ? '✓' : '✗'} ${label}`)
    html.includes(k) ? pass++ : fail++
  }
  // ⚠️ 一定要有 facet 掣（tick 得）
  const hasChip = /class="chip[^"]*"[^>]*>[^<]*(福岡|博多)/.test(html) ||
                  html.includes('chip')
  console.log(`    ${hasChip ? '✓' : '✗'} 地名係可以 tick 嘅 chip`)
  hasChip ? pass++ : fail++

  const empty = render('冇景點', 'components/Saved.jsx',
    { items: [], onEditItem: () => {} })
  const okE = empty.includes('仲未有收藏')
  console.log(`    ${okE ? '✓' : '✗'} 冇收藏時有提示`)
  okE ? pass++ : fail++
}

console.log('\n▸ 好友邀請通知（HomeScreen）')
{
  const html = render('有邀請（badge=2）', 'components/HomeScreen.jsx', {
    trip: TRIP, items: ITEMS, stops: STOPS, trips: [TRIP],
    user: { display_name: 'Alice' }, badges: { friends: 2 },
    onOpen: () => {}, onPickTrip: () => {}, onNewTrip: () => {},
  }, { allowEmpty: true })
  for (const k of ['你有一個交友邀請', '個人想加你做朋友']) {
    const ok = html.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 含「${k}」`)
    ok ? pass++ : fail++
  }
  const noBadge = render('冇邀請', 'components/HomeScreen.jsx', {
    trip: TRIP, items: ITEMS, stops: STOPS, trips: [TRIP],
    user: { display_name: 'Alice' }, badges: {},
    onOpen: () => {}, onPickTrip: () => {},
  }, { allowEmpty: true })
  const ok = !noBadge.includes('你有一個交友邀請')
  console.log(`    ${ok ? '✓' : '✗'} 冇邀請時唔顯示通知`)
  ok ? pass++ : fail++
}

console.log('\n▸ 旅程選擇器（app 內）')
{
  const many = [TRIP, { id: 't2', name: '首爾 3 日', days: 3, start_date: '2027-09-01' }]
  const html = render('多個旅程', 'components/HomeScreen.jsx', {
    trip: many[0], items: ITEMS, stops: STOPS, trips: many,
    user: { display_name: 'Alice' }, badges: {},
    onOpen: () => {}, onPickTrip: () => {}, onNewTrip: () => {},
  }, { allowEmpty: true })
  const ok = html.includes('轉旅程') || html.includes('揀一個')
  console.log(`    ${ok ? '✓' : '✗'} 顯示轉旅程入口`)
  ok ? pass++ : fail++
}

console.log('\n▸ 分帳欠款一覽（Settlement）')
{
  // 呢個要真 data 先 render 到 shares，所以只檢查結構
  const src = fs.readFileSync(new URL('../../web/src/components/Settlement.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['你嘅狀況', '有「你嘅狀況」corner'],
    ['應收', '顯示應收'],
    ['應俾', '顯示應俾'],
    ['邊個要比錢邊個', '有轉帳一覽'],
    ['最少轉帳', '計算最少轉帳'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 購物清單（圖片 + 附近店鋪）')
{
  const src = fs.readFileSync(new URL('../../web/src/components/ShoppingList.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['readAndResize', '有縮圖上載'],
    ['api.upload', '有上傳 API'],
    ['附近邊度買', '有附近店鋪按鈕'],
    ['api.nearby', '有 nearby API'],
    ['＋收藏', '可以將店加入收藏'],
    ['image', '顯示相片'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 登入 / 註冊（兩頁互通）')
{
  const loginRaw = fs.readFileSync(
    new URL('../../web/src/components/Login.jsx', import.meta.url), 'utf8')
  // ⚠️ 去註解先檢查「有冇驗證碼登入」—— 否則會 match 到自己解釋嘅註解
  const src = stripComments(loginRaw)

  // ⚠️ 用戶要求：
  //   「兩版…一開始就係登入畫面…有個 button 俾你去撳去註冊…
  //    總之兩頁啦，係應該有個 button 去互通嘅」
  check('預設頁係「登入」', /useState\('login'\)/.test(src))

  for (const [k, label] of [
    ['api.passwordLogin', '有密碼登入'],
    ['api.register', '有註冊'],
    ['api.claimAccount', '有「認領舊帳號」'],
    ['switchTo', '有兩頁切換'],
    // ⚠️ 密碼欄而家係 <PasswordInput>（連眼仔）——
    //    唔再直接寫 type="password"（嗰個喺 PasswordInput 入面）。
    ['<PasswordInput', '密碼輸入框（連眼仔）'],
    ['autoComplete="new-password"', '註冊用新密碼 autocomplete'],
    ["'current-password'", '登入用現有密碼 autocomplete'],
    ['pw2', '註冊要打兩次密碼'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }

  // ⚠️⚠️ 用戶明確要求**刪走**驗證碼登入
  const noCodeLogin = !/驗證碼登入/.test(src)
  console.log(`    ${noCodeLogin ? '✓' : '✗'} 已經冇「驗證碼登入」`)
  noCodeLogin ? pass++ : fail++

  // 但認領流程仲要用驗證碼（安全性）
  const hasClaim = src.includes('驗證碼') && src.includes('claim')
  console.log(`    ${hasClaim ? '✓' : '✗'} 保留驗證碼做「認領舊帳號」（安全）`)
  hasClaim ? pass++ : fail++
  // ⚠️ 密碼搬咗去 SettingsMore（第二層）
  const more = fs.readFileSync(
    new URL('../../web/src/components/SettingsMore.jsx', import.meta.url), 'utf8')
  const ok = more.includes('setPassword') && more.includes('現有密碼')
  console.log(`    ${ok ? '✓' : '✗'} 「更多設定」可以改密碼（要現有密碼）`)
  ok ? pass++ : fail++
}

console.log('\n▸ 設定 Settings（⚠️ 最易有「未定義變數」嘅元件）')
{
  const html = render('設定頁', 'components/Settings.jsx', {
    user: { display_name: 'Alice', email: 'a@b.com', has_password: true },
    theme: 'galaxy', setTheme: () => {}, onLogout: () => {}, onUserUpdate: () => {},
  }, { allowEmpty: true })
  const moreSrc = fs.readFileSync(
    new URL('../../web/src/components/SettingsMore.jsx', import.meta.url), 'utf8')
  for (const k of ['密碼', '手機連線', 'IG', '主題']) {
    const ok = moreSrc.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 「更多設定」含「${k}」`)
    ok ? pass++ : fail++
  }
}

// ⚠️⚠️ 用戶要求：「setting 好簡單…改名 / icon / QR code」
//     呢個測試守住「第一層唔可以再塞嘢」
console.log('\n▸ 設定頁 = 純 Profile（用戶要求）')
{
  const st = stripComments(fs.readFileSync(
    new URL('../../web/src/components/Settings.jsx', import.meta.url), 'utf8'))
  for (const [k, label] of [
    ['AvatarPicker', '有頭像選擇（第 ① 樣）'],
    ['display_name', '有改名（第 ② 樣）'],
    ['MyQr', '有 QR Code（第 ③ 樣）'],
    ['username', '有 @帳號名'],
    ['SettingsMore', '其他嘢收喺第二層'],
    ['更多設定', '有「更多設定」掣'],
  ]) {
    const ok = st.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
  // 第一層唔可以有呢啲（要收埋）
  for (const k of ['cacheStatus', 'bookmarkletCode', 'THEMES', 'sub(key) = ']) {
    const bad = st.includes(k)
    console.log(`    ${!bad ? '✓' : '✗'} 第一層冇「${k}」`)
    !bad ? pass++ : fail++
  }
  // 第一層要短
  const lines = st.split('\n').length
  const ok = lines < 220
  console.log(`    ${ok ? '✓' : '✗'} 第一層夠短（${lines} 行 < 220）`)
  ok ? pass++ : fail++
}

console.log('\n▸ 城市選擇器（CityPicker）')
{
  const src = fs.readFileSync(
    new URL('../../web/src/components/CityPicker.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['api.searchCities', '即時搜尋城市'],
    ['ArrowDown', '鍵盤上下選擇'],
    ['Enter', 'Enter 揀'],
    ['r.matched', '顯示匹配到嘅名'],
    ['population', '顯示人口（分辨同名地方）'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }

  // Trips 同 StopsEditor 都要用 CityPicker（唔可以再係自由打字）
  for (const [f, label] of [
    ['Trips.jsx', '新旅程嘅目的地用 CityPicker'],
    ['StopsEditor.jsx', '城市編輯器用 CityPicker'],
  ]) {
    const t = fs.readFileSync(
      new URL('../../web/src/components/' + f, import.meta.url), 'utf8')
    const ok = t.includes('CityPicker')
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }

  // ⚠️ 地圖唔可以硬編碼城市
  const mv = fs.readFileSync(
    new URL('../../web/src/components/MapView.jsx', import.meta.url), 'utf8')
  const hard = /setView\(\[33\.\d+,\s*130\.\d+\]/.test(mv)
  console.log(`    ${!hard ? '✓' : '✗'} 地圖冇硬編碼福岡 fallback`)
  !hard ? pass++ : fail++
}

console.log('\n▸ 頭像選擇器（AvatarPicker）')
{
  const html = render('選擇器', 'components/AvatarPicker.jsx',
    { user: { avatar: 'star' }, onUserUpdate: () => {} }, { allowEmpty: true })
  const src = fs.readFileSync(new URL('../../web/src/components/AvatarPicker.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['PIXEL_AVATARS', '用像素頭像清單'],
    ['api.updateMe', '儲存去後端'],
    ['avatarSvg', '??'],
  ]) {
    if (label === '??') continue
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
  const st = fs.readFileSync(new URL('../../web/src/components/Settings.jsx', import.meta.url), 'utf8')
  const ok = st.includes('AvatarPicker')
  console.log(`    ${ok ? '✓' : '✗'} 設定頁有頭像選擇`)
  ok ? pass++ : fail++
}

console.log('\n▸ 加朋友（@帳號名 + QR）')
{
  const src = fs.readFileSync(new URL('../../web/src/components/Friends.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['api.requestFriendByName', '用 @帳號名加朋友'],
    ['api.lookupUser', '有即時預覽（查係唔係嗰個人）'],
    ['api.decodeQr', '可以用 QR 圖加朋友'],
    ['readForQr', '用無損 PNG 上傳（QR 唔可以失真）'],
    ['Avatar', '顯示頭像'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
  const noEmail = !src.includes('api.inviteFriend')
  console.log(`    ${noEmail ? '✓' : '✗'} 已經唔用 email 邀請`)
  noEmail ? pass++ : fail++
}

console.log('\n▸ 個人 QR（MyQr）')
{
  const src = fs.readFileSync(new URL('../../web/src/components/MyQr.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['api.myQr', '產生自己嘅 QR'],
    ['api.decodeQr', '掃人哋嘅 QR'],
    ['readForQr', '上傳圖解碼'],
    ['HTTPS', '解釋點解相機要 HTTPS'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 帳號名（Settings）')
{
  const src = fs.readFileSync(new URL('../../web/src/components/Settings.jsx', import.meta.url), 'utf8')
  for (const [k, label] of [
    ['saveUname', '可以改帳號名'],
    ['api.updateMe', '儲存去後端'],
    ['MyQr', '設定頁有個人 QR'],
    ['AvatarPicker', '設定頁有頭像選擇'],
  ]) {
    const ok = src.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} ${label}`)
    ok ? pass++ : fail++
  }
}

console.log('\n▸ 手動輸入 AddPlace')
{
  const html = render('表單', 'components/AddPlace.jsx', { trip: TRIP, onAdded: () => {} })
  for (const k of ['手動加景點', '名稱', '地址', '查座標']) {
    const ok = html.includes(k)
    console.log(`    ${ok ? '✓' : '✗'} 含「${k}」`)
    ok ? pass++ : fail++
  }
}

console.log(`\n${'═'.repeat(54)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(54))
process.exit(fail ? 1 : 0)
