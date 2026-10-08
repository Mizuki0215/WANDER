/**
 * 真 DOM 測試（jsdom）
 * ====================
 * ⚠️⚠️ 為咩要有呢個（SSR 捉唔到嘅嘢）：
 *
 *   SSR 只 render 一次、唔會行 useEffect、冇 layout。
 *   但呢兩類 bug 一定要真 DOM 先捉到：
 *     ① **點擊之後**嘅狀態（例如撳「產生 QR」之後畫面有冇嘢）
 *     ② **z-index 疊層**（底部 nav 蓋住彈出嘅 sheet）
 *
 *   用戶報：
 *     「朋友 QR code 嗰度…生成嗰陣時…佢個畫面一路之後就冇咗」
 *     「你見到擺位有啲怪怪地」（截圖見到 nav 壓住個 sheet）
 */
import { createRequire } from 'node:module'
import fs from 'node:fs'

const ROOT = new URL('../../', import.meta.url)
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { JSDOM } = require('jsdom')
const esbuild = require('esbuild')

let pass = 0, fail = 0
const check = (label, cond, extra = '') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

// ══ jsdom 環境 ══
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:8787/',
  pretendToBeVisual: true,
})
const { window } = dom
globalThis.window = window
globalThis.document = window.document
Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true })
globalThis.HTMLElement = window.HTMLElement
globalThis.Element = window.Element
globalThis.Node = window.Node
globalThis.getComputedStyle = window.getComputedStyle.bind(window)
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
// ⚠️ jsdom 冇 matchMedia / serviceWorker / caches —— PwaBar 會用到
window.matchMedia = window.matchMedia || (q => ({
  matches: false, media: q, onchange: null,
  addEventListener() {}, removeEventListener() {},
  addListener() {}, removeListener() {}, dispatchEvent: () => false,
}))
Object.defineProperty(window.navigator, 'serviceWorker', {
  value: { register: async () => ({ addEventListener() {} }),
           addEventListener() {}, ready: Promise.resolve({ addEventListener() {} }) },
  configurable: true,
})
window.caches = { keys: async () => [], open: async () => ({ keys: async () => [], match: async () => null, delete: async () => true, put: async () => {} }), delete: async () => true }
globalThis.caches = window.caches
globalThis.cancelAnimationFrame = clearTimeout
globalThis.IS_REACT_ACT_ENVIRONMENT = true
// getBoundingClientRect 喺 jsdom 永遠回 0 → 補一個合理嘅
window.Element.prototype.getBoundingClientRect = function () {
  return { top: 100, left: 20, right: 100, bottom: 160, width: 80, height: 60, x: 20, y: 100 }
}

const React = require('react')
const { createRoot } = require('react-dom/client')
const { act } = require('react-dom/test-utils')

// ══ 假 API ══
const USER = {
  id: 'u1', email: 'me@example.com', display_name: 'ic yyy',
  username: 'icyyy1', avatar: 'star', onboarded: true,
}
const TRIP = {
  id: 't1', name: '首爾行', destination: 'Seoul', days: 28,
  start_date: '2026-11-19', end_date: '2026-12-16',
  invite_code: 'ABC123', members: [{ id: 'u1', display_name: 'ic yyy', email: 'me@example.com', role: 'owner' }],
}
const QR_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">' +
  '<rect width="200" height="200" fill="#fff"/><rect x="20" y="20" width="40" height="40" fill="#000"/></svg>'

const RESPONSES = {
  '/api/me': { user: USER, trips: [TRIP] },
  '/api/trips/t1': TRIP,
  '/api/trips/t1/items': { items: [] },
  '/api/trips/t1/stops': { stops: [], total_days: 0 },
  '/api/trips/t1/expenses': { expenses: [], members: TRIP.members, currency: 'JPY' },
  '/api/trips/t1/shopping': { items: [] },
  '/api/trips/t1/zones': { zones: [] },
  '/api/friends': { friends: [], incoming: [], outgoing: [] },
  '/api/invites': { invites: [] },
  '/api/me/qr': { url: 'http://192.168.1.83:8787/?add=icyyy1', svg: QR_SVG,
                  username: 'icyyy1', display_name: 'ic yyy' },
  '/api/qr': { url: 'http://192.168.1.83:8787', svg: QR_SVG },
  '/api/ig-provider': { enabled: false },
  '/api/health': { ok: true },
}

let fetchLog = []
globalThis.fetch = async (url, opts = {}) => {
  const u = new URL(String(url), 'http://localhost:8787')
  fetchLog.push(`${opts.method || 'GET'} ${u.pathname}`)
  const body = RESPONSES[u.pathname]
  return {
    ok: body !== undefined,
    status: body === undefined ? 404 : 200,
    json: async () => body ?? { detail: 'not found' },
    text: async () => JSON.stringify(body ?? {}),
    headers: new Map(),
  }
}
window.fetch = globalThis.fetch
// ⚠️ key 要同 api.js 嘅 TOKEN_KEY 一致
const store = new Map([['wander_token', 'tok'], ['wander.token', 'tok'], ['token', 'tok']])
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: k => store.has(k) ? store.get(k) : null,
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: k => store.delete(k),
  }, configurable: true,
})
globalThis.localStorage = window.localStorage

// ══ 建 bundle ══
const result = await esbuild.build({
  entryPoints: [new URL('web/src/App.jsx', ROOT).pathname],
  bundle: true, write: false, format: 'cjs', jsx: 'automatic',
  loader: { '.jsx': 'jsx', '.js': 'jsx' },
  external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'],
  define: { 'process.env.NODE_ENV': '"development"' },
})
const mod = { exports: {} }
new Function('require', 'module', 'exports', result.outputFiles[0].text)(
  require, mod, mod.exports)
const App = mod.exports.default

// ══ 掛載 ══
const errors = []
const origErr = console.error
console.error = (...a) => {
  const s = a.map(String).join(' ')
  if (!/not wrapped in act|useLayoutEffect does nothing/.test(s)) errors.push(s)
}

// 確認 localStorage 真係通
console.log('  · localStorage 測試:', window.localStorage.getItem('wander_token'))
console.log('  · globalThis.localStorage 存在:', typeof globalThis.localStorage)

const root = createRoot(document.getElementById('root'))
await act(async () => { root.render(React.createElement(App)) })

/** ⚠️ 等某個 selector 出現（React 非同步 render 要靠咁樣等）。 */
async function waitFor(sel, ms = 3000) {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    await act(async () => { await new Promise(r => setTimeout(r, 40)) })
    const el = document.querySelector(sel)
    if (el) return el
  }
  return null
}

/** ⚠️ 撳一個元素（要用 act 包住先 flush 到 React 更新）。 */
async function click(el) {
  if (!el) return false
  await act(async () => {
    el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  await act(async () => { await new Promise(r => setTimeout(r, 40)) })
  return true
}

// ⚠️ BootScreen 要等 /api/me 完成之後先出現（booting → booted）
const skipBtn = await waitFor('button[aria-label="跳過"]')
if (skipBtn) await click(skipBtn)
// onDone 之後仲有 300ms 離場動畫
await act(async () => { await new Promise(r => setTimeout(r, 400)) })
// 等到主畫面出嚟
await waitFor('[data-tour="settings"]', 3000)

const html = () => document.getElementById('root').innerHTML
const has = (s) => html().includes(s)

console.log('\n▸ 掛載 App')
check('有 render 嘢', html().length > 500, `${html().length} bytes`)
check('已經過咗開機動畫（booted）', !has('PRESS START') && !has('press-start'),
  has('載入中') ? '⚠️ 仲喺載入中' : '')

// ══ 撳去 Settings ══
console.log('\n▸ 撳「設定」')
async function clickByText(text) {
  const el = [...document.querySelectorAll('button, [role="button"]')]
    .find(e => (e.textContent || '').includes(text))
  return click(el)
}
// 主畫面 app icon 係按 data-tour
const settingsIcon = document.querySelector('[data-tour="settings"]')
check('搵到設定 app icon', !!settingsIcon)
if (!settingsIcon) {
  console.log('      ── 實際 render 咗（頭 400 字）──')
  console.log('      ' + html().slice(0, 400).replace(/</g, '‹').replace(/\n/g, ' '))
  console.log('      ── fetch 記錄 ──')
  console.log('      ' + (fetchLog.join(', ') || '(冇)').slice(0, 300))
  console.log('      ── 有冇 BootScreen ──')
  console.log('      z-index 999 存在:', html().includes('z-index: 999'))
}
if (settingsIcon) {
  await act(async () => {
    settingsIcon.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  })
  await act(async () => { await new Promise(r => setTimeout(r, 60)) })
}
check('入到設定頁', has('我嘅 QR Code'))
check('設定頁有 QR 區', has('我嘅 QR Code'))
check('第一層係 Profile（有頭像）', has('未設帳號名') || has('@'))
check('其他設定收埋（有「更多設定」掣）', has('更多設定'))

// ══ ⭐ 撳「重新播放教學」 ══
console.log('\n▸ ⭐ 設定頁嘅「重新播放教學」')
// ⚠️ 「重新播放教學」而家喺「更多設定」>「指導教學」兩個摺疊入面
await clickByText('更多設定')
await clickByText('指導教學')
const clicked = await clickByText('重新播放教學')
await act(async () => { await new Promise(r => setTimeout(r, 80)) })
check('撳到「重新播放教學」', clicked)
check('教學彈咗出嚟', has('你好！我係嚮導') || has('onb-box'))
check('教學有掣（下一步）', has('下一步'))
const onbActions = document.querySelector('.onb-actions')
check('.onb-actions 存在', !!onbActions)
const onbScroll = document.querySelector('.onb-scroll')
check('.onb-scroll 存在', !!onbScroll)
if (onbActions && onbScroll) {
  // ⚠️ 掣一定要喺滾動區**外面**
  check('掣唔喺滾動區入面', !onbScroll.contains(onbActions))
}

console.log('\n▸ 走完教學（⚠️ 呢個係**重看**流程）')
// ⚠️⚠️ 用戶要求：
//   「第一次創建 Account 嘅時候你先至叫你去改名。所以之後喺
//    setting 嗰度再想睇多次示範教學，係唔需要再 show 叫你去
//    打自己個名嗰一版。淨係教佢啲 Apps 點用就 OK。」
//
//   → 呢個測試係行**重看**流程（user.onboarded = true +
//     撳「重新播放教學」）→ **應該完全冇改名步**。
//
//   ⚠️ 之前呢度係 expect「去到改名嗰步」—— 即係測緊舊行為。
//      改咗 replay 之後就應該**冇**改名步。
{
  // 記錄行過嘅步驟標題（證明真係行過導覽）
  const seen = []
  for (let i = 0; i < 16; i++) {
    const t = document.querySelector('.onb-title')?.textContent || ''
    if (t) seen.push(t)
    // ⚠️ 重看流程冇「下一步」嘅時候就係完成咗
    if (!document.querySelector('.onb-actions button.btn.primary')) break
    const btn = [...document.querySelectorAll('.onb-actions button')]
      .find(x => /下一步|完成/.test(x.textContent || ''))
    if (!btn) break
    if (/完成/.test(btn.textContent)) break
    await click(btn)
    await act(async () => { await new Promise(r => setTimeout(r, 40)) })
  }
  check('行過導覽步驟', seen.length >= 2, `${seen.length} 步：${seen.slice(0,3).join(' / ')}…`)
  // ⚠️⚠️ 核心斷言：重看**唔應該**出改名步
  check('⚠️ 重看冇改名步 ← 用戶要求', !has('你叫乜嘢名'),
    has('你叫乜嘢名') ? '⚠️ 仲出緊叫用戶打名' : '')
  check('重看冇「必填」提示', !has('必填'))
  check('重看冇歡迎步（唔係第一次）', !seen.includes('你好！我係嚮導'))
  check('重看行到尾（搞掂！）', has('搞掂'))
  check('重看完成掣寫「完成」', has('完成 ✓'))
}

// ══ ⭐ 檢查 z-index 疊層 ══
console.log('\n▸ ⚠️ CSS 疊層（用戶報「nav 壓住個 sheet」）')
const cssRaw = fs.readFileSync(new URL('web/src/styles.css', ROOT), 'utf8')
// ⚠️ 去註解先檢查 —— 否則會 match 到我自己解釋 bug 嘅註解
const css = cssRaw.replace(/\/\*[\s\S]*?\*\//g, '')
const navZ = (css.match(/\.nav\s*\{[^}]*z-index:\s*(\d+)/) || [])[1]
check('nav 有 z-index', !!navZ, `z-index: ${navZ}`)
// ⚠️ 唔可以有 `.app > *` 呢種「一刀切」嘅 z-index 規則
const blanket = /\.app\s*>\s*\*[^{]*\{[^}]*z-index/.test(css)
check('冇「.app > * { z-index }」一刀切規則', !blanket,
  blanket ? '⚠️ 呢個會令 nav 同內容同層 → 後者蓋前者' : '')
// 星雲背景要用 z-index:-1
const neb = css.match(/\.app::before\s*\{[^}]*z-index:\s*(-?\d+)/)
check('星雲背景 z-index = -1（唔搶疊層）', !!neb && neb[1] === '-1',
  neb ? `實際 ${neb[1]}` : '（冇設）')
// ⚠️ 只有一個 .app::after（掃描線）—— 重複規則會令樣式難追
// ⚠️ 只計**設定背景**嘅規則 —— `@media (prefers-reduced-motion)` 入面
//    嗰個 `{ display: none }` 係合理嘅，唔算重複。
const afterBg = (css.match(/\.app::after\s*\{[^}]*background/g) || []).length
check('只有一個 .app::after 設定背景', afterBg === 1, `實際 ${afterBg}`)

console.log(`\n${'═'.repeat(54)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
if (errors.length) {
  console.log(`\n  ⚠️ Console 錯誤 ${errors.length} 個:`)
  errors.slice(0, 4).forEach(e => console.log('    ' + e.split('\n')[0].slice(0, 130)))
}
console.log('═'.repeat(54))
console.error = origErr
process.exit(fail ? 1 : 0)
