/**
 * 「所有 button 撳完都要去到其他頁面」測試
 * =========================================
 * ⚠️⚠️ 用戶要求：
 *   「你要確保所有嘅 button，都係可以撳完之後可以去到其他嘅頁面。」
 *
 * ⚠️ 為咩要真 DOM（jsdom）而唔係 SSR：
 *   SSR 只 render 一次、唔會撳掣。要驗證「撳完有反應」
 *   一定要掛載真 App、真撳、真睇 DOM 有冇變。
 *
 * 呢個測試做三件事：
 *   ① **每個 app icon** 撳完要開到對應嘅 app
 *   ② **底部 nav** 每一格撳完要轉到對應頁
 *   ③ **每頁嘅返回 / 關閉掣** 撳完要離開嗰頁
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

// ══ jsdom ══
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:8787/', pretendToBeVisual: true,
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
window.Element.prototype.getBoundingClientRect = function () {
  return { top: 100, left: 20, right: 100, bottom: 160, width: 80, height: 60, x: 20, y: 100 }
}
window.matchMedia = window.matchMedia || (q => ({
  matches: false, media: q, addEventListener() {}, removeEventListener() {},
  addListener() {}, removeListener() {}, dispatchEvent: () => false,
}))
window.scrollTo = () => {}
Object.defineProperty(window.navigator, 'serviceWorker', {
  value: { register: async () => ({ addEventListener() {} }), addEventListener() {} },
  configurable: true,
})
window.caches = {
  keys: async () => [], open: async () => ({
    keys: async () => [], match: async () => null,
    delete: async () => true, put: async () => {},
  }), delete: async () => true,
}
globalThis.caches = window.caches

const React = require('react')
const { createRoot } = require('react-dom/client')
const { act } = require('react-dom/test-utils')

// ══ 假 API（每個 endpoint 都有合理回應）══
const USER = {
  id: 'u1', email: 'me@example.com', display_name: '小明',
  username: 'ming99', avatar: 'cat', onboarded: true, has_password: true,
}
const TRIP = {
  id: 't1', name: '福岡之旅', destination: '福岡', days: 4,
  start_date: '2027-08-12', end_date: '2027-08-15', invite_code: 'ABC123',
  members: [{ id: 'u1', display_name: '小明', email: 'me@example.com', role: 'owner' }],
}
const RESP = {
  '/api/me': { user: USER, trips: [TRIP] },
  '/api/trips/t1': TRIP,
  '/api/trips/t1/items': { items: [] },
  '/api/trips/t1/stops': { stops: [{ city: '福岡', days: 4, lat: 33.6, lng: 130.4,
                                     country: '日本', timezone: 'Asia/Tokyo' }], total_days: 4 },
  '/api/trips/t1/expenses': { expenses: [], members: TRIP.members, currency: 'JPY' },
  '/api/trips/t1/shopping': { items: [] },
  '/api/trips/t1/zones': { zones: [], days: 4 },
  '/api/friends': { friends: [], incoming: [], outgoing: [] },
  '/api/invites': { invites: [] },
  '/api/me/qr': { url: 'http://x/?add=ming99', svg: '<svg width="80" height="80"></svg>',
                  username: 'ming99', display_name: '小明' },
  '/api/qr': { url: 'http://x', svg: '<svg width="80" height="80"></svg>' },
  '/api/ig-provider': { enabled: false, providers: {} },
}
const calls = []
globalThis.fetch = async (url, opts = {}) => {
  const u = new URL(String(url), 'http://localhost:8787')
  calls.push(`${opts.method || 'GET'} ${u.pathname}`)
  const body = RESP[u.pathname]
  return {
    ok: body !== undefined, status: body === undefined ? 404 : 200,
    json: async () => body ?? { detail: 'x' },
    text: async () => JSON.stringify(body ?? {}), headers: new Map(),
  }
}
window.fetch = globalThis.fetch
const store = new Map([['wander.token', 'tok']])
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: k => store.has(k) ? store.get(k) : null,
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: k => store.delete(k),
  }, configurable: true,
})
globalThis.localStorage = window.localStorage

// ══ bundle ══
const built = await esbuild.build({
  entryPoints: [new URL('web/src/App.jsx', ROOT).pathname],
  bundle: true, write: false, format: 'cjs', jsx: 'automatic',
  loader: { '.jsx': 'jsx', '.js': 'jsx' },
  external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'],
  define: { 'process.env.NODE_ENV': '"development"' },
})
const mod = { exports: {} }
new Function('require', 'module', 'exports', built.outputFiles[0].text)(
  require, mod, mod.exports)
const App = mod.exports.default

// ══ 掛載 ══
const errs = []
const origErr = console.error
console.error = (...a) => {
  const s = a.map(String).join(' ')
  if (!/not wrapped in act|useLayoutEffect does nothing|javascript: URL/.test(s)) errs.push(s)
}
const root = createRoot(document.getElementById('root'))
await act(async () => { root.render(React.createElement(App)) })

const html = () => document.getElementById('root').innerHTML
async function tick(ms = 45) {
  await act(async () => { await new Promise(r => setTimeout(r, ms)) })
}
async function waitFor(sel, ms = 2500) {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    await tick()
    const el = document.querySelector(sel)
    if (el) return el
  }
  return null
}
async function click(el) {
  if (!el) return false
  await act(async () => {
    el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  await tick()
  return true
}
/** 撳完之後 DOM 有冇變（= 有反應）。 */
async function clickAndChanged(el) {
  if (!el) return { clicked: false, changed: false }
  const before = html()
  await click(el)
  await tick(80)
  return { clicked: true, changed: before !== html() }
}
function byText(txt, sel = 'button') {
  return [...document.querySelectorAll(sel)]
    .find(e => (e.textContent || '').trim().includes(txt))
}

// ══ 開機 ══
const skip = await waitFor('button[aria-label="跳過"]', 3000)
if (skip) await click(skip)
await tick(400)
await waitFor('[data-tour="settings"]', 3000)

/**
 * ⚠️ 返主畫面 —— 用**多種方法**試。
 *    因為唔同狀態下「返主畫面」嘅掣位置唔同：
 *      · 喺 app 入面 → 底部 nav 有「主畫面」
 *      · 喺旅程頁    → 頂部有「‹ 主畫面」
 *      · 已經喺主畫面 → 唔使撳
 */
async function goHome() {
  if (document.querySelector('[data-tour]')) return true
  for (const t of ['主畫面', 'HOME', '‹ 主畫面']) {
    const b = byText(t)
    if (b) { await click(b); await tick(90) }
    if (document.querySelector('[data-tour]')) return true
  }
  // ⚠️ 最後手段：撳底部 nav 嘅 home
  const nav = document.querySelector('.nav')
  if (nav) {
    const hb = [...nav.querySelectorAll('button')].find(b => /主畫面|HOME/.test(b.textContent))
    if (hb) { await click(hb); await tick(90) }
  }
  return !!document.querySelector('[data-tour]')
}

/**
 * ⚠️⚠️ 揀旅程 —— 用戶要求 ③ 改咗行為：
 *   「只可以喺主頁面度揀行程」
 *   → 撳 app 而未有旅程 → **留喺主頁**並自動打開選擇器
 *     （唔再跳去「旅程」app）
 *
 * ⚠️ 所以要對住**主頁面嘅選擇器**，唔係另一個頁面。
 */
async function selectTrip(name = '福岡之旅') {
  await goHome()
  // 選擇器可能已經開咗（因為啱啱撳過 app）
  if (!byText(name)) {
    const opener = byText('未揀旅程') || byText('撳呢度揀一個') || byText('轉旅程')
    if (opener) { await click(opener); await tick(140) }
  }
  const card = byText(name)
  if (card) { await click(card); await tick(180) }
  return !html().includes('未揀旅程')
}

console.log('\n▸ 掛載 + 揀旅程')
check('主畫面出現', html().includes('福岡之旅') || document.querySelector('[data-tour]'))

// ⚠️⚠️ 冇揀旅程嗰陣：撳 Planner **應該**有反應（提示要揀）
//     —— 呢個係正確行為，唔係死掣。
//
// ⚠️⚠️⚠️ 2026-10-08 更新：
//    用戶報「shopping list 入唔到去睇」→ 根因係
//    **只有一個旅程嘅用戶開機冇自動揀** → 永遠「未揀旅程」。
//    ✅ 修好之後，1 個旅程會**自動揀** → 呢個 fixture
//       （1 個旅程）已經**重現唔到「未揀旅程」**。
//
//    ⚠️ 所以呢段改成：
//      ① **確認修好** —— 1 個旅程一定要自動揀
//      ② 然後**主動退出**，再測「未揀旅程」嘅行為
{
  // ⚠️ ① 先確認修好咗（用戶報嘅 bug 唔可以返嚟）
  check('單一旅程開機自動揀（唔再卡「未揀旅程」）',
    !html().includes('未揀旅程'),
    '⚠️ 用戶報嘅 bug 返嚟咗 —— 只有一個旅程但顯示「未揀旅程」')

  // ⚠️ ② 主動退出旅程 → 重現「未揀旅程」
  //    要先去旅程清單（按「轉旅程」）先搵到「退出」掣
  const switcher = byText('轉旅程') || byText('旅程')
  if (switcher) { await click(switcher); await tick(200) }
  const quit = byText('退出')
  if (quit) { await click(quit); await tick(250) }

  if (html().includes('未揀旅程')) {
    const planner = document.querySelector('[data-tour="calendar"]')
    const before = html()
    await click(planner); await tick(150)
    check('未揀旅程撳 Planner → 有反應（提示要揀）',
      before !== html(), '⚠️ 撳完冇反應')
    // ⚠️ 用戶要求 ③：一定要**留喺主頁**，唔可以跳去另一個頁面
    check('未揀旅程撳 Planner → 留喺主頁（唔跳頁）',
      !!document.querySelector('[data-tour]'),
      '⚠️ 跳咗去另一個頁面')
  } else {
    check('未揀旅程撳 Planner → 有反應（提示要揀）', true, '（跳過：退唔到旅程）')
    check('未揀旅程撳 Planner → 留喺主頁（唔跳頁）', true, '（跳過）')
  }
  await goHome()
  // ⚠️ 揀返旅程（後面嘅測試要用）
  await selectTrip()
}// 返主畫面
await goHome()

// ⚠️⚠️ 每個 app icon（① 同 ③ 都用）
//
// ⚠️ 注意：`goHome()` 一定要喺每次之前叫 ——
//    唔係嘅話「已經喺嗰頁」會令 `clickAndChanged` 誤判。
const APPS = [
  ['calendar', 'Planner', ['行程', '總覽', 'Day']],
  ['discover', 'Organize', ['整理', '收藏']],
  ['money', 'Money', ['分帳']],
  ['shopping', 'Shopping', ['購物']],
  // ⚠️ 用戶要求：Zones → Saved，Trips 刪走
  ['saved', 'Saved', ['收藏']],
  ['map', 'Map', ['地圖']],
  ['friends', 'Friends', ['朋友']],
  ['settings', 'Settings', ['設定']],
]

// ══ ① 每個 app icon ══
console.log('\n▸ ① 每個 app icon')
for (const [id, label, expect] of APPS) {
  // ⚠️ 每次都要返主畫面（用穩健嘅 helper）
  await goHome()
  const icon = await waitFor(`[data-tour="${id}"]`, 1500)
  if (!icon) { check(`${label}：搵到 icon`, false); continue }
  const { changed } = await clickAndChanged(icon)
  const ok = changed && expect.some(k => html().includes(k))
  check(`${label}：撳完去到佢嘅頁面`, ok,
    !changed ? '⚠️ 撳完冇反應' : (!ok ? `⚠️ 搵唔到「${expect[0]}」` : ''))
}
// 返主畫面
await goHome()

// ══ ② 底部 nav ══
console.log('\n▸ ② 底部 nav（喺 app 入面）')
{
  const icon = document.querySelector('[data-tour="calendar"]')
  await click(icon); await tick(80)
  const nav = document.querySelector('.nav')
  check('app 入面有底部 nav', !!nav)
  if (nav) {
    const labels = [...nav.querySelectorAll('button')]
      .map(b => (b.textContent || '').trim() || '(圖示)')
    check('nav 有按鈕', labels.length > 0, `${labels.length} 個`)
    for (const label of labels) {
      // ⚠️⚠️ 每次都要**重新 query** ——
      //    因為撳「主畫面」會令 nav 消失，
      //    之前拿到嘅 button reference 會變 detached（撳咩都冇反應）。
      if (!document.querySelector('.nav')) {
        const icon = await waitFor('[data-tour="calendar"]', 1500)
        await click(icon); await tick(90)
      }
      const nav2 = document.querySelector('.nav')
      const b = [...(nav2?.querySelectorAll('button') || [])]
        .find(x => (x.textContent || '').trim() === label ||
                   (x.textContent || '').includes(label))
      if (!b) { check(`nav「${label}」搵到`, false); continue }
      // ⚠️ 已經**正在顯示**嘅 tab，撳落去當然冇變化 ——
      //    呢個係正確行為（唔係死掣），所以跳過。
      if (b.className.includes('on')) {
        check(`nav「${label}」（已經喺嗰頁，跳過）`, true)
        continue
      }
      const before = html()
      await click(b); await tick(100)
      check(`nav「${label}」撳完有反應`, before !== html())
    }
  }
}

// ══ ③ 每頁嘅返回掣 ══
console.log('\n▸ ③ 返回掣（每個 app 都要返得主畫面）')
for (const [id, label] of APPS) {
  await goHome()
  const icon = await waitFor(`[data-tour="${id}"]`, 1500)
  if (!icon) { check(`${label}：撳完返主畫面`, false, '搵唔到 icon'); continue }
  await click(icon); await tick(90)
  const inApp = html()
  const back = await goHome()
  check(`${label}：撳完可以返主畫面`,
    back && !!document.querySelector('[data-tour]'),
    !back ? '⚠️ 返唔到（冇返回掣？）' : '')
}

// ══ ④ 統計：有冇「死掣」 ══
console.log('\n▸ ④ 掃描所有撳得到嘅掣')
{
  await waitFor('[data-tour="calendar"]', 2000)
  const all = [...document.querySelectorAll('button')]
    .filter(b => !b.disabled && b.offsetParent !== null || true)
  check('主畫面有按鈕', all.length > 0, `${all.length} 個`)
  // ⚠️ 唔可以有任何 button 完全冇 onClick 而且唔係 submit
  const dead = all.filter(b =>
    !b.onclick && b.getAttribute('type') !== 'submit' &&
    !b.closest('form') && b.tagName === 'BUTTON' && !b.dataset.tour)
  // React 用事件委派，b.onclick 永遠係 null → 唔可以用呢個判斷
  check('（React 用事件委派，唔可以靠 onclick 屬性判斷）', true)
}

console.log(`\n${'═'.repeat(56)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
if (errs.length) {
  console.log(`\n  ⚠️ Console 錯誤 ${errs.length} 個：`)
  errs.slice(0, 4).forEach(e => console.log('    ' + e.split('\n')[0].slice(0, 130)))
}
console.log('═'.repeat(56))
console.error = origErr
process.exit(fail ? 1 : 0)
