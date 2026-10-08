/**
 * ⚠️⚠️ 「加完景點 → 即刻更新，但唔播開機動畫」
 *
 *   用戶要求：
 *     「有冇得可以就係更新完之後即刻 refresh 一次，
 *      但係 refresh 一次呢…如果係每次更新數據一次嘅話
 *      就唔需要有一個 Animation 囉」
 *
 *   ⚠️ 兩個要同時成立：
 *     ① 加完 → 清單**即刻**有嘢（唔使 reload）
 *     ② 更新嗰陣**唔會**播 WANDER OS 開機動畫
 */
import { createRequire } from 'node:module'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { JSDOM } = require('jsdom')
const esbuild = require('esbuild')
const fs = require('node:fs')

const B = 'http://127.0.0.1:8787'
const TOKEN = process.env.WANDER_TEST_TOKEN || ''
if (!TOKEN) { console.log('  ⚠️ 要 WANDER_TEST_TOKEN'); process.exit(0) }

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',
  { url: B + '/', pretendToBeVisual: true })
const { window } = dom
for (const [k, v] of [['window', window], ['document', window.document],
  ['HTMLElement', window.HTMLElement], ['Element', window.Element], ['Node', window.Node]]) {
  globalThis[k] = v
}
Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true })
globalThis.getComputedStyle = window.getComputedStyle.bind(window)
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = clearTimeout
globalThis.IS_REACT_ACT_ENVIRONMENT = true
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

const NODE_FETCH = globalThis.fetch
let calls = []
globalThis.fetch = async (url, opt = {}) => {
  const u = String(url).startsWith('http') ? String(url) : B + String(url)
  const h = { ...(opt.headers || {}) }
  if (!h.Authorization) h.Authorization = `Bearer ${TOKEN}`
  const r = await NODE_FETCH(u, { method: opt.method || 'GET', body: opt.body || undefined, headers: h })
  calls.push(`${opt.method || 'GET'} ${u.replace(B, '').split('?')[0]} ${r.status}`)
  const text = await r.text()
  return { ok: r.ok, status: r.status, json: async () => JSON.parse(text), text: async () => text }
}
window.fetch = globalThis.fetch

const React = require('react')
const { createRoot } = require('react-dom/client')
const { act } = require('react-dom/test-utils')

let pass = 0, fail = 0
const check = (l, c, e = '') => {
  console.log(`  ${c ? '✓' : '✗'} ${l}${e ? '  ' + e : ''}`); c ? pass++ : fail++ }
const sleep = (ms) => new Promise(r => setTimeout(r, ms))

const out = esbuild.buildSync({
  entryPoints: [new URL('../../web/src/App.jsx', import.meta.url).pathname],
  bundle: true, write: false, format: 'cjs', platform: 'node', target: 'es2020',
  jsx: 'transform', loader: { '.jsx': 'jsx', '.js': 'jsx' },
  external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'], logLevel: 'silent' })
const mod = { exports: {} }
new Function('require', 'module', 'exports', 'process', 'React', out.outputFiles[0].text)(
  require, mod, mod.exports, process, React)
const App = mod.exports.default || mod.exports

const root = createRoot(window.document.getElementById('root'))
const html = () => window.document.getElementById('root').innerHTML
const text = () => html().replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
const hasBoot = () => /WANDER OS|初始化|TRAVEL SYSTEM v/.test(text())

console.log('═'.repeat(64))
console.log('  加完景點 → 即刻更新（唔播動畫）')
console.log('═'.repeat(64))

await act(async () => { root.render(React.createElement(App)) })
// ⚠️ 開機動畫要時間
let sawBoot = false
for (let i = 0; i < 12; i++) {
  await act(async () => { await sleep(1000) })
  if (hasBoot()) sawBoot = true
  if (window.document.querySelector('[data-tour]')) break
}
check('① 開機**有**播動畫（正確）', sawBoot, sawBoot ? '' : '⚠️ 從來冇播')

// 去收藏頁
const icon = window.document.querySelector('[data-tour="saved"]')
if (icon) {
  await act(async () => { icon.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { await sleep(1500) })
}
const before = text()

// ⚠️ 撳 Discover 嘅 refresh（模擬加完之後嘅 onRefresh）
calls = []
const discover = window.document.querySelector('[data-tour="discover"]')
if (discover) {
  await act(async () => { discover.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { await sleep(1500) })
}
check('② 去整理頁', text().includes('整理') || text().includes('Organize'))

// ⚠️⚠️ ③ `refreshTrip()` 唔可以係 no-op
//
//   實測捉到嘅 bug：`refreshTrip(id)` 內部寫 `const tid = id; if (!tid) return`，
//   但 7 個 `onRefresh={() => refreshTrip()}` **冇傳 id** →
//   全部變咗空操作 → 加完景點**清單唔更新**（用戶報「冇即時更新」）。
//
//   ⚠️ 呢個一定要用**原始碼**檢查 —— 因為 UI 上睇唔出（refresh 掣撳完
//      好似冇事，其實冇打 API）。
{
  const appSrc = fs.readFileSync(
    new URL('../../web/src/App.jsx', import.meta.url), 'utf8')
  const noArg = [...appSrc.matchAll(/refreshTrip\(\)/g)]
  check('③ 冇 `refreshTrip()` 空參數（會變 no-op）',
    noArg.length === 0,
    noArg.length ? `⚠️ 有 ${noArg.length} 個 —— 加完景點清單唔會更新` : '')
  const withArg = [...appSrc.matchAll(/refreshTrip\(tripId\)/g)]
  check('③ onRefresh 全部有傳 tripId',
    withArg.length >= 7, `得 ${withArg.length} 個（應該 >= 7）`)
}

check('④ 更新期間**冇**播開機動畫', !hasBoot(),
  hasBoot() ? '⚠️ 更新數據唔應該播動畫' : '')

console.log()
console.log('═'.repeat(64))
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(64))
process.exit(fail ? 1 : 0)
