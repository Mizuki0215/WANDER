/**
 * 導航審計：每個 tab 真係 render 到嘢嗎？
 * ⚠️ 用戶要求：「每次你電完畢之後你都要確認返係唔係每個 Path
 *              都有對應嘅頁可以去到你想要嘅 page？」
 */
import { createRequire } from 'node:module'
import fs from 'node:fs'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const React = require('react')
const { renderToString } = require('react-dom/server')
const esbuild = require('esbuild')

const WEB = new URL('../../web/src/', import.meta.url)
function load(rel, extra = {}) {
  const code = fs.readFileSync(new URL(rel, WEB), 'utf8')
  const out = esbuild.buildSync({
    entryPoints: [new URL(rel, WEB).pathname], bundle: true, write: false,
    format: 'cjs', platform: 'node', target: 'es2020', jsx: 'transform',
    loader: { '.jsx': 'jsx', '.js': 'jsx' },
    external: ['react', 'react-dom', 'react/jsx-runtime'], logLevel: 'silent',
  })
  const mod = { exports: {} }
  new Function('require', 'module', 'exports', 'React', 'window', 'document',
    'localStorage', out.outputFiles[0].text)(
    require, mod, mod.exports, React,
    { location: { search: '', pathname: '/', origin: 'http://x' },
      addEventListener() {}, removeEventListener() {},
      matchMedia: () => ({ matches: false, addEventListener() {} }),
      innerWidth: 390, innerHeight: 844 },
    { documentElement: { setAttribute() {}, style: { setProperty() {}, removeProperty() {} } },
      addEventListener() {}, removeEventListener() {}, visibilityState: 'visible',
      querySelector: () => null, querySelectorAll: () => [] },
    { getItem: () => null, setItem() {}, removeItem() {} })
  return mod.exports.default || mod.exports
}

const TRIP = { id: 't1', name: '東京 5 日', days: 5, members: [{ display_name: '我' }],
               start_date: '2026-04-01', end_date: '2026-04-05', currency: 'HKD' }
const STOPS = [{ id: 's1', city: '東京', days: 5, timezone: 'Asia/Tokyo', lat: 35.68, lng: 139.76 }]
const ITEMS = [{ id: 'i1', name: '一蘭拉麵', category: 'food', confidence: 90,
                 location_path: ['東京都'], city: '東京都', day_index: 0, price: 1200, currency: 'JPY' }]

const COMPONENTS = {
  calendar: ['components/Calendar.jsx', { trip: TRIP, items: ITEMS, stops: STOPS, onRefresh(){}, onEditItem(){} }],
  discover: ['components/Discover.jsx', { trip: TRIP, items: ITEMS, onRefresh(){}, onEditItem(){} }],
  money:    ['components/Settlement.jsx', { trip: TRIP, members: ['我'] }],
  shopping: ['components/ShoppingList.jsx', { trip: TRIP, members: ['我'], onRefresh(){} }],
  saved:    ['components/Saved.jsx', { items: ITEMS, onEditItem(){} }],
  map:      ['components/MapView.jsx', { items: ITEMS, stops: STOPS, onRefresh(){}, onEditItem(){} }],
  friends:  ['components/Friends.jsx', { trip: TRIP, me: { display_name: '我', username: 'me1' }, onRefresh(){} }],
  settings: ['components/Settings.jsx', { user: { display_name: '我', email: 'a@b.c' }, theme: 'galaxy', setTheme(){}, onLogout(){}, onUserUpdate(){} }],
  trips:    ['components/Trips.jsx', { trips: [TRIP], onOpen(){}, onRefresh(){}, currentId: 't1' }],
}

let ok = 0, fail = 0
console.log('═'.repeat(64))
console.log('  導航審計：每個 tab 真係 render 到嘢嗎？')
console.log('═'.repeat(64))
for (const [tab, [rel, props]] of Object.entries(COMPONENTS)) {
  try {
    const C = load(rel)
    const html = renderToString(React.createElement(C, props))
    const text = html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim()
    const bytes = html.length
    // ⚠️ 唔可以係空白（> 200 bytes 同有文字）
    const good = bytes > 200 && text.length > 10
    console.log(`  ${good ? '✓' : '✗'} ${tab.padEnd(10)} ${String(bytes).padStart(6)} bytes  「${text.slice(0, 42)}」`)
    good ? ok++ : fail++
  } catch (e) {
    console.log(`  ✗ ${tab.padEnd(10)} 爆: ${e.message.split('\n')[0].slice(0, 50)}`)
    fail++
  }
}
console.log()
console.log('─'.repeat(64))
console.log('  ⚠️ 空狀態都要 render 到（唔可以白畫面）')
console.log('─'.repeat(64))
for (const [tab, [rel, props]] of Object.entries(COMPONENTS)) {
  try {
    const C = load(rel)
    // ⚠️ 空 items / 冇旅程
    const empty = { ...props, items: [], stops: [], trips: [], trip: null }
    const html = renderToString(React.createElement(C, empty))
    const bytes = html.length
    const good = bytes > 100
    console.log(`  ${good ? '✓' : '✗'} ${tab.padEnd(10)} 空狀態 ${String(bytes).padStart(6)} bytes`)
    good ? ok++ : fail++
  } catch (e) {
    console.log(`  ✗ ${tab.padEnd(10)} 空狀態爆: ${e.message.split('\n')[0].slice(0, 44)}`)
    fail++
  }
}
// ══════════════════════════════════════════════════════════════
console.log()
console.log('─'.repeat(64))
console.log('  靜態：每個導航目標都有 render 分支嗎？')
console.log('─'.repeat(64))
{
  const app = fs.readFileSync(new URL('../../web/src/App.jsx', import.meta.url), 'utf8')
  const home = fs.readFileSync(new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')

  const targets = new Set([...app.matchAll(/setTab\('([a-z]+)'\)/g)].map(m => m[1]))
  const appIds = [...home.matchAll(/id: '([a-z]+)'/g)].map(m => m[1])
  const branches = new Set([...app.matchAll(/tab === '([a-z]+)'/g)].map(m => m[1]))

  const missing = [...new Set([...targets, ...appIds])].filter(t => !branches.has(t))
  const good = missing.length === 0
  console.log(`  ${good ? '✓' : '✗'} 每個導航目標都有 render 分支（${branches.size} 個 tab）`)
  if (!good) console.log(`      ⚠️ 冇 render 分支: ${missing.join(', ')}`)
  good ? ok++ : fail++

  // ⚠️⚠️ 唔可以用 `history.back()` 做「返去」——
  //    因為 tab 唔係 route，會跳咗出 app（實測捉到嘅 bug）。
  const files = []
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const f = new URL(e.name + (e.isDirectory() ? '/' : ''), dir)
      if (e.isDirectory()) walk(f)
      else if (/\.jsx?$/.test(e.name)) files.push(f)
    }
  }
  walk(new URL('../../web/src/components/', import.meta.url))
  walk(new URL('../../web/src/lib/', import.meta.url))
  const bad = []
  for (const f of files) {
    const raw = fs.readFileSync(f, 'utf8')
    // ⚠️⚠️ 一定要去**所有**註解先檢查 ——
    //    包括 JSX 註解 `{/* ... */}`（我嘅解釋註解入面有
    //    `history.back()` 呢個字，唔去就會 match 到自己）。
    const body = raw
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
      .replace(/^\s*\*.*$/gm, '')
      .replace(/(?<![:'"`])\/\/.*$/gm, '')
    if (/history\.back\(\)/.test(body)) bad.push(f.pathname.split('/').pop())
  }
  const noHist = bad.length === 0
  console.log(`  ${noHist ? '✓' : '✗'} 冇用 history.back() 做「返去」`)
  if (!noHist) console.log(`      ⚠️ 用咗: ${bad.join(', ')}（tab 唔係 route，會跳出 app）`)
  noHist ? ok++ : fail++

  const m = app.match(/const TRIP_APPS = \[([^\]]+)\]/)
  const tripApps = m ? [...m[1].matchAll(/'([a-z]+)'/g)].map(x => x[1]) : []
  const missTrip = tripApps.filter(t => !branches.has(t))
  const goodTrip = missTrip.length === 0
  console.log(`  ${goodTrip ? '✓' : '✗'} TRIP_APPS 全部有 render 分支（${tripApps.length} 個）`)
  missTrip.length && console.log(`      ⚠️ 冇: ${missTrip.join(', ')}`)
  goodTrip ? ok++ : fail++
}

console.log()
console.log('═'.repeat(64))
console.log(`  ${ok} 通過 / ${fail} 失敗`)
console.log('═'.repeat(64))
process.exit(fail ? 1 : 0)
