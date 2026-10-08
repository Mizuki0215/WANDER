/**
 * ⚠️⚠️ 用**真實 API 數據**驗證 Shopping 入得到
 * =============================================
 *
 * ⚠️ 用戶報：「shopping list 入唔到去睇」（報咗兩次）
 *
 * ⚠️ 為咩 SSR 測試捉唔到：
 *   SSR 只 render component，唔會：
 *     · 行 `useEffect`（唔會 fetch）
 *     · 撳掣
 *     · 行 App 嘅 tab 切換
 *
 * ✅ 呢個測試：
 *   ① 掛載**真 App**
 *   ② 用**真 fetch**（打 127.0.0.1:8787 真實 server）
 *   ③ 用真帳號 session
 *   ④ 撳 Shopping icon → 睇 DOM 真係有咩
 */
import { createRequire } from 'node:module'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { JSDOM } = require('jsdom')
const esbuild = require('esbuild')
const fs = require('fs')

const B = 'http://127.0.0.1:8787'
const TOKEN = process.env.WANDER_TEST_TOKEN || ''

if (!TOKEN) {
  console.log('  ⚠️ 要 WANDER_TEST_TOKEN（跳過）')
  process.exit(0)
}

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: B + '/', pretendToBeVisual: true,
})
const { window } = dom
globalThis.window = window
globalThis.document = window.document
Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true })
globalThis.HTMLElement = window.HTMLElement
globalThis.Element = window.Element
globalThis.Node = window.Node
globalThis.getComputedStyle = window.getComputedStyle.bind(window)
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = clearTimeout
globalThis.IS_REACT_ACT_ENVIRONMENT = true
// ⚠️ localStorage 要有 token
// ⚠️⚠️ `localStorage` 一定要掛上 **globalThis** ——
//    bundle 入面嘅 `localStorage.getItem()` 係 resolve 去 globalThis，
//    唔係 window。只設 `window.localStorage` 嘅話，
//    api.js 嘅 `try { localStorage.getItem() } catch { return null }`
//    會 ReferenceError → 當「冇登入」→ 只 call signup-mode
//    （實測捉到：/api/me 完全冇 call）。
//
// ⚠️ 真 key 係 'wander.token'（睇 web/src/lib/api.js）—— 純字串唔係 JSON
window.localStorage.setItem('wander.token', TOKEN)
globalThis.localStorage = window.localStorage
window.Element.prototype.getBoundingClientRect = () => ({
  top: 100, left: 20, right: 100, bottom: 160, width: 80, height: 60, x: 20, y: 100 })
window.matchMedia = window.matchMedia || (q => ({
  matches: false, media: q, addEventListener() {}, removeEventListener() {},
  addListener() {}, removeListener() {}, dispatchEvent: () => false }))
window.scrollTo = () => {}
Object.defineProperty(window.navigator, 'serviceWorker', {
  value: { register: async () => ({ addEventListener() {} }), addEventListener() {} },
  configurable: true })
window.caches = { keys: async () => [], open: async () => ({
  keys: async () => [], match: async () => null, delete: async () => true, put: async () => {} }),
  delete: async () => true }
globalThis.caches = window.caches
// ⚠️⚠️ 一定要**先捕捉** Node 原本嘅 fetch ——
//    唔係嘅話下面 `fetch(...)` 會 call 自己 → 無限遞迴
//    （實測：RangeError: Maximum call stack size exceeded）
const NODE_FETCH = globalThis.fetch

globalThis.fetch = async (url, opt = {}) => {
  const u = String(url).startsWith('http') ? String(url) : B + String(url)
  // ⚠️ localStorage 嘅 token 要加落 header
  const h = { ...(opt.headers || {}) }
  if (!h.Authorization) h.Authorization = `Bearer ${TOKEN}`
  const r = await NODE_FETCH(u, { ...opts(opt), headers: h })
  // ⚠️ log 每個 call（debug 用）
  if (process.env.WANDER_TEST_VERBOSE) {
    console.log(`     → ${opt.method || 'GET'} ${u.replace(B, '')}  ${r.status}`)
  }
  const text = await r.text()
  return { ok: r.ok, status: r.status,
    json: async () => JSON.parse(text), text: async () => text }
}
/** ⚠️ jsdom 嘅 Request 唔食得 —— 拆返淨低 method/body。 */
function opts(o) {
  return { method: o.method || 'GET', body: o.body || undefined }
}
window.fetch = globalThis.fetch

const React = require('react')
const { createRoot } = require('react-dom/client')
const { act } = require('react-dom/test-utils')

let pass = 0, fail = 0
const check = (l, c, e = '') => {
  console.log(`  ${c ? '✓' : '✗'} ${l}${e ? '  ' + e : ''}`); c ? pass++ : fail++ }

// ══ 建真 App bundle ══
const out = esbuild.buildSync({
  entryPoints: [new URL('../../web/src/App.jsx', import.meta.url).pathname],
  bundle: true, write: false, format: 'cjs', platform: 'node', target: 'es2020',
  jsx: 'transform', loader: { '.jsx': 'jsx', '.js': 'jsx' },
  external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'],
  logLevel: 'silent',
})
const mod = { exports: {} }
// ⚠️ `jsx: 'transform'` 出 `React.createElement` —— 一定要注入 React
new Function('require', 'module', 'exports', 'process', 'React', out.outputFiles[0].text)(
  require, mod, mod.exports, process, React)
const App = mod.exports.default || mod.exports

const root = createRoot(window.document.getElementById('root'))
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const html = () => window.document.getElementById('root').innerHTML
const text = () => html().replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')

console.log('═'.repeat(64))
console.log('  Shopping 真實數據測試（真 server）')
console.log('═'.repeat(64))

await act(async () => { root.render(React.createElement(App)) })
for (let i = 0; i < 8; i++) {
  await act(async () => { await sleep(1200) })
  if (window.document.querySelector('[data-tour]')) break
}

check('App boot 完成', html().length > 500, `${html().length} bytes`)
// ⚠️ 主畫面特徵：有 app icon + 時間
check('有主畫面', window.document.querySelectorAll('[data-tour]').length >= 6)

// ⚠️ 搵 Shopping icon
// ⚠️ 睇下主畫面實際 render 咩（唔好淨係話「搵唔到」）
const mainText = text()
console.log(`\n  ── App boot 之後嘅畫面 ──`)
console.log(`  ${mainText.slice(0, 260)}`)
console.log()
const tours = [...window.document.querySelectorAll('[data-tour]')]
  .map(e => e.getAttribute('data-tour'))
console.log(`  data-tour 元素: ${tours.length ? tours.join(', ') : '（冇）'}`)
console.log(`  畫面 bytes: ${html().length}`)
console.log()
const icon = window.document.querySelector('[data-tour="shopping"]')
check('搵到 Shopping icon', !!icon)
if (icon) {
  await act(async () => {
    icon.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  })
  for (let i = 0; i < 8; i++) {
  await act(async () => { await sleep(1200) })
  if (window.document.querySelector('[data-tour]')) break
}
  const t = text()
  console.log('\n  ── 撳完之後嘅 DOM ──')
  console.log(`  ${t.slice(0, 300)}`)
  console.log()
  check('去到購物頁', t.includes('購物'))
  check('唔係白畫面', html().length > 300, `${html().length} bytes`)
  check('唔係「先揀一個旅程」', !t.includes('先揀一個旅程'))
  check('見到「衫」或者其他 item',
    t.includes('衫') || t.includes('藥') || t.includes('買'))
}

console.log()
console.log('═'.repeat(64))
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(64))
process.exit(fail ? 1 : 0)
