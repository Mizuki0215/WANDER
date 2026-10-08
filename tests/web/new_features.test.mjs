/**
 * 4 個新功能真瀏覽器驗證
 * =========================
 * ⚠️ 用戶要求：自訂背景 · 相機掃 QR · 購物私人 · 收藏公開/私人
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
  ['HTMLElement', window.HTMLElement], ['Element', window.Element], ['Node', window.Node]]) globalThis[k] = v
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
  value: { register: async () => ({ addEventListener() {} }), addEventListener() {} }, configurable: true })
window.caches = { keys: async () => [], open: async () => ({
  keys: async () => [], match: async () => null, delete: async () => true, put: async () => {} }),
  delete: async () => true }
globalThis.caches = window.caches
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
console.log('  4 個新功能（真瀏覽器）')
console.log('═'.repeat(64))

await act(async () => { root.render(React.createElement(App)) })
for (let i = 0; i < 12; i++) {
  await act(async () => { await sleep(1000) })
  if (window.document.querySelector('[data-tour]')) break
}
check('App boot', !!window.document.querySelector('[data-tour]'))

/** ⚠️ 每次撳之前一定要返主畫面 —— 唔係嘅話搵唔到 app icon。 */
async function goHome() {
  const nav = window.document.querySelector('.nav')
  if (nav) {
    const hb = [...nav.querySelectorAll('button')]
      .find(b => /主畫面|HOME/.test(b.textContent || ''))
    if (hb) { await act(async () => { hb.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) }); await act(async () => { await sleep(900) }) }
  }
  return window.document.querySelector('[data-tour]')
}
/** ⚠️ 撳一個 app icon（自動先返主畫面）。 */
async function openApp(id) {
  await goHome()
  const icon = window.document.querySelector(`[data-tour="${id}"]`)
  if (!icon) return false
  await act(async () => { icon.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { await sleep(2000) })
  return true
}

// ⚠️ ① 收藏頁要有 🔒／🌍 badge
if (await openApp('saved')) {
  const t = text()
  check('① 收藏頁有 🔒私人 或 🌍公開 badge',
    t.includes('🔒 私人') || t.includes('🌍 公開'), t.slice(0, 60))
}

// ⚠️ ② 購物頁要有 badge
if (await openApp('shopping')) {
  const t = text()
  check('② 購物頁有 🔒私人 或 👥共用 badge',
    t.includes('🔒 私人') || t.includes('👥 共用'), t.slice(0, 60))
}

// ⚠️ ③ 設定頁要有背景揀選
if (await openApp('settings')) {
  // ⚠️ 背景 section 收埋喺「更多設定」
  const more = [...window.document.querySelectorAll('button')]
    .find(b => /更多設定/.test(b.textContent || ''))
  if (more) {
    await act(async () => { more.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) })
    await act(async () => { await sleep(900) })
  }
  const t = text()
  check('③ 設定有「背景圖」section', t.includes('背景圖'), t.slice(0, 80))
  // ⚠️ `Sec` 係 accordion（一次開一個）—— 要撳個 title 先見到內容
  // ⚠️ `Sec` 嘅文字係 `▸ 🖼 背景圖`（前面有箭嘴）——
  //    唔可以用 `startsWith('🖼')`（實測捉到）
  const sec = [...window.document.querySelectorAll('button')]
    .find(e => (e.textContent || '').includes('背景圖'))
  if (sec) {
    await act(async () => { sec.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) })
    await act(async () => { await sleep(700) })
  }
  const t2 = text()
  check('③ 有 preset 揀（午夜/日落…）',
    t2.includes('午夜') || t2.includes('日落') || t2.includes('櫻花'),
    t2.slice(0, 90))
  // ⚠️ 已經有相嗰陣個掣係「換相」—— 兩個都要接受
  check('③ 有「我嘅相」上載選項',
    t2.includes('我嘅相') || t2.includes('換相'), t2.slice(0, 90))
  // ⚠️⚠️ 有相嗰陣一定要有清晰度滑桿
  if (t2.includes('換相')) {
    check('③ 有「相片清晰度」滑桿', t2.includes('相片清晰度'))
    check('③ 標籤係「0% 黑色 / 100% 睇得最清」',
      t2.includes('0% 黑色') && t2.includes('100% 睇得最清'))
  }
}

// ⚠️ ④ 朋友頁要有相機掣
if (await openApp('friends')) {
  const t = text()
  check('④ 朋友頁有「開相機掃」掣', t.includes('開相機掃'), t.slice(0, 80))
}

console.log()
console.log('═'.repeat(64))
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(64))
process.exit(fail ? 1 : 0)
