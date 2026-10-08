/**
 * 影 app 畫面（用真 SSR render）
 * ==================================
 *
 * ⚠️⚠️ 為咩唔用 headless Chrome 直接連 server：
 *   · 要登入 → localStorage token 跨 Chrome 執行唔持久
 *   · 開機動畫用 rAF + performance.now() → virtual time 追唔到
 *   · Chrome 快取 screenshot → 出嚟永遠一樣
 *
 * ✅ 改用 app 自己嘅 SSR renderer（同 `ssr.test.mjs` 一樣）：
 *   真元件 → 真 HTML → 加真 CSS → headless Chrome 影一張靜態 PNG。
 *   ⚠️ 呢個係「真元件輸出」，唔係假圖。
 *
 * 用法：
 *     cd web && node tools/shoot.mjs
 */
import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(new URL('../../web/package.json', import.meta.url))
const React = require('react')
const { renderToString } = require('react-dom/server')
const esbuild = require('esbuild')

const ROOT = new URL('../../web/src/', import.meta.url)
const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.resolve(HERE, '../../docs/shots')

/**
 * ⚠️⚠️ 唔用 stub —— 用 esbuild **真 bundle**。
 *
 *   為咩：stub 版嘅 `PixelIcon` 只係一個空 function →
 *   影出嚟冇晒啲像素圖示（成個 app 嘅重點）。
 *
 *   ✅ 真 bundle → 真 PixelIcon / 真頭像 / 真圖示。
 *   ⚠️ `useEffect` 喺 SSR 唔會跑 → 唔會發網絡請求。
 */
function loadComponent(rel) {
  const out = esbuild.buildSync({
    entryPoints: [fileURLToPath(new URL(rel, ROOT))],
    bundle: true,
    write: false,
    format: 'cjs',
    platform: 'node',
    target: 'es2020',
    jsx: 'transform',
    loader: { '.jsx': 'jsx', '.js': 'jsx' },
    // ⚠️ react 要 external —— 唔係嘅話 bundle 兩個 React instance
    //    會爆 "Invalid hook call"。
    external: ['react', 'react-dom', 'react/jsx-runtime'],
    logLevel: 'silent',
  })
  const code = out.outputFiles[0].text
  const mod = { exports: {} }
  new Function('require', 'module', 'exports', 'React', code)(
    require, mod, mod.exports, React)
  return mod.exports.default || mod.exports
}

// ── 假資料 ──
const TRIP = {
  id: 'trip_demo', name: '東京 5 日', days: 5, start_date: '2026-04-01',
  members: ['旅行者'], owner_id: 'u1',
}
const STOPS = [
  { id: 's1', city: '東京', days: 3, timezone: 'Asia/Tokyo', lat: 35.68, lng: 139.76 },
  { id: 's2', city: '箱根', days: 2, timezone: 'Asia/Tokyo', lat: 35.23, lng: 139.10 },
]
const ITEMS = [
  { id: 'i1', name: '一蘭拉麵 本店', category: 'food', confidence: 92,
    location_path: ['福岡県', '福岡市', '博多区'], city: '福岡市', district: '博多区',
    day_index: 0, lat: 33.59, lng: 130.40 },
  { id: 'i2', name: 'teamLab Planets', category: 'play', confidence: 88,
    location_path: ['東京都', '江東区'], city: '江東区', day_index: 1,
    lat: 35.649, lng: 139.79 },
  { id: 'i3', name: '築地場外市場', category: 'food', confidence: 90,
    location_path: ['東京都', '中央区'], city: '中央区', day_index: 1,
    lat: 35.665, lng: 139.77 },
  { id: 'i4', name: '東京鐵塔', category: 'play', confidence: 85,
    location_path: ['東京都', '港区'], city: '港区', day_index: 2,
    lat: 35.658, lng: 139.745 },
  { id: 'i5', name: '箱根神社', category: 'play', confidence: 83,
    location_path: ['神奈川県', '足柄下郡', '箱根町'], city: '箱根町',
    day_index: 3, lat: 35.2049, lng: 139.0257 },
  { id: 'i6', name: '大涌谷', category: 'play', confidence: 80,
    location_path: ['神奈川県', '足柄下郡', '箱根町'], city: '箱根町',
    day_index: 4, lat: 35.2444, lng: 139.0197 },
]

const SHOTS = [
  {
    name: 'app-home',
    comp: 'components/HomeScreen.jsx',
    props: { trip: TRIP, items: ITEMS, stops: STOPS, trips: [TRIP],
             user: { display_name: '旅行者', avatar: 'star' }, badges: {},
             onOpen: () => {}, onPickTrip: () => {}, onNewTrip: () => {} },
  },
  {
    name: 'app-saved',
    comp: 'components/Saved.jsx',
    props: { items: ITEMS, onEditItem: () => {} },
  },
]

const CSS = fs.readFileSync(new URL('../../web/src/styles.css', import.meta.url), 'utf8')

fs.mkdirSync(OUT, { recursive: true })

for (const s of SHOTS) {
  let body = ''
  try {
    const C = loadComponent(s.comp)
    body = renderToString(React.createElement(C, s.props))
  } catch (e) {
    console.log(`  ✗ ${s.name}: ${e.message.split('\n')[0]}`)
    continue
  }
  const html = `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=390,initial-scale=1">
<style>${CSS}
html,body{margin:0;background:#0b0518}
.app{min-height:100vh}
</style></head>
<body><div class="app" data-theme="galaxy">${body}</div></body></html>`
  const f = path.join(OUT, `${s.name}.html`)
  fs.writeFileSync(f, html)
  console.log(`  ✓ ${s.name}.html  (${html.length} bytes)`)
}
