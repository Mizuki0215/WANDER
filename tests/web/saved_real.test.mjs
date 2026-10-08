/**
 * ⚠️⚠️ 用真數據驗證「已收藏」頁
 *
 *   用戶報：「我擺咗條 link 上去，但係唔知點解佢冇新增落去
 *            嗰個已收藏景點度」
 *
 *   ⚠️ DB 明明有 BOOKOFF（加咗兩次）→ 所以問題係**顯示**。
 */
import { createRequire } from 'node:module'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { JSDOM } = require('jsdom')
const esbuild = require('esbuild')

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

// ⚠️ 捕捉 Node 原本嘅 fetch（唔係會無限遞迴）
const NODE_FETCH = globalThis.fetch
globalThis.fetch = async (url, opt = {}) => {
  const u = String(url).startsWith('http') ? String(url) : B + String(url)
  const h = { ...(opt.headers || {}) }
  if (!h.Authorization) h.Authorization = `Bearer ${TOKEN}`
  const r = await NODE_FETCH(u, { method: opt.method || 'GET', body: opt.body || undefined, headers: h })
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

console.log('═'.repeat(64))
console.log('  已收藏（Saved）真數據測試')
console.log('═'.repeat(64))

await act(async () => { root.render(React.createElement(App)) })
for (let i = 0; i < 10; i++) {
  await act(async () => { await sleep(1200) })
  if (window.document.querySelector('[data-tour]')) break
}
check('App boot', !!window.document.querySelector('[data-tour]'))

const icon = window.document.querySelector('[data-tour="saved"]')
check('搵到 Saved icon', !!icon)
if (icon) {
  await act(async () => { icon.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { await sleep(2500) })
  const t = text()
  console.log('\n  ── 已收藏頁面 ──')
  console.log(`  ${t.slice(0, 380)}`)
  console.log()
  check('去到已收藏', t.includes('收藏'))
  check('見到 BOOKOFF', t.includes('BOOKOFF'), '⚠️ 加咗但顯示唔到')
  check('唔係白畫面', html().length > 400, `${html().length} bytes`)
}

console.log()
console.log('═'.repeat(64))
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(64))
process.exit(fail ? 1 : 0)
