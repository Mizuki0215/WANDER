/**
 * Service Worker 測試
 * ===================
 * ⚠️ 呢個唔係「睇下語法有冇錯」——係喺 Node 入面用假 CacheStorage / fetch
 *    **真正執行** cache 策略，確認：
 *      · API 唔會被快取（私隱）
 *      · 圖磚會被快取（離線睇地圖）而且有上限（唔會爆 quota）
 *      · 導航 network-first + 離線 fallback
 *      · 舊版本 cache 會被清走
 *
 * 跑法：
 *     node tests/web/sw.test.mjs        # 由 workspace 根目錄
 */
import fs from 'node:fs'
import vm from 'node:vm'

const src = fs.readFileSync(new URL('../../web/public/sw.js', import.meta.url), 'utf8')

// ── 假 Cache ─────────────────────────────────────────────
class FakeCache {
  constructor(name) { this.name = name; this.map = new Map() }
  async put(req, res) { this.map.set(String(req.url ?? req), res) }
  async match(req) { return this.map.get(String(req.url ?? req)) ?? undefined }
  async addAll(urls) { for (const u of urls) this.map.set(u, { url: u }) }
  async keys() { return [...this.map.keys()] }
  async delete(req) { return this.map.delete(String(req.url ?? req)) }
}
const cachesMap = new Map()
const caches = {
  async open(n) { if (!cachesMap.has(n)) cachesMap.set(n, new FakeCache(n)); return cachesMap.get(n) },
  async keys() { return [...cachesMap.keys()] },
  async delete(n) { return cachesMap.delete(n) },
}

// ── 記錄 fetch 行為 ───────────────────────────────────────
const fetched = []
let online = true
const HTML = `<!DOCTYPE html><html><head>
<link rel="stylesheet" href="/assets/index-test.css">
</head><body><script type="module" src="/assets/index-test.js"><\/script></body></html>`
function makeRes(url, body = '') {
  const res = {
    status: 200, type: 'basic', url,
    async text() { return body },
    clone() { return makeRes(url, body) },
  }
  return res
}
async function fetchStub(req) {
  const url = typeof req === 'string' ? req : req.url
  fetched.push(url)
  if (!online) throw new Error('offline')
  return makeRes(url, url.endsWith('/index.html') ? HTML : '')
}

// ── 假 self ──────────────────────────────────────────────
const handlers = {}
const messages = []
const self = {
  location: { origin: 'http://127.0.0.1:8787' },
  addEventListener: (t, fn) => { handlers[t] = fn },
  skipWaiting: async () => { messages.push('skipWaiting') },
  clients: { claim: async () => { messages.push('claim') } },
}

const sandbox = { self, caches, fetch: fetchStub, Response, URL, console, setTimeout, clearTimeout }
sandbox.globalThis = sandbox
vm.createContext(sandbox)
vm.runInContext(src, sandbox)

const ok = (c) => c ? '✓' : '✗'
let pass = 0, fail = 0
function check(label, cond, extra='') {
  console.log(`  ${ok(cond)} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

// ══ 執行 install ══
console.log('\n▸ install')
let installPromise
handlers.install({ waitUntil: (p) => { installPromise = p } })
await installPromise
check('註冊咗 install handler', !!handlers.install)
check('precache 咗 index.html', cachesMap.get('wander-v1-shell')?.map.has('/index.html'))
check('叫咗 skipWaiting', messages.includes('skipWaiting'))

// ══ 執行 activate ══
console.log('\n▸ activate')
// 加個舊版本 cache 睇下會唔會被清
cachesMap.set('wander-v0-shell', new FakeCache('wander-v0-shell'))
let actPromise
handlers.activate({ waitUntil: (p) => { actPromise = p } })
await actPromise
check('清走舊版本 cache', !cachesMap.has('wander-v0-shell'))
check('保留新版本 cache', cachesMap.has('wander-v1-shell'))
check('叫咗 clients.claim', messages.includes('claim'))

// ══ fetch 分派 ══
console.log('\n▸ fetch 分派')
function runFetch(url, opts = {}) {
  const req = { url, method: 'GET', mode: opts.mode || 'cors', ...opts }
  let responded = null
  handlers.fetch({ request: req, respondWith: (p) => { responded = p } })
  return responded
}

// ① API 唔應該被攔截（respondWith 唔會被叫）
fetched.length = 0
const apiResp = runFetch('http://127.0.0.1:8787/api/trips')
check('API 唔攔截（network-only）', apiResp === null)
check('API 唔會入 cache', !cachesMap.get('wander-v1-shell')?.map.has('http://127.0.0.1:8787/api/trips'))

// ② OSM 圖磚 → cache-first
fetched.length = 0
const tileUrl = 'https://a.tile.openstreetmap.org/13/7000/3400.png'
const t1 = runFetch(tileUrl)
check('圖磚有攔截', t1 !== null)
await t1
check('圖磚第一次會上網', fetched.includes(tileUrl))
check('圖磚入咗 tile cache', cachesMap.get('wander-v1-tiles')?.map.has(tileUrl))
// 第二次應該唔上網
fetched.length = 0
await runFetch(tileUrl)
check('圖磚第二次食 cache（唔上網）', fetched.length === 0)

// ③ 同源 asset → cache-first
fetched.length = 0
const asset = 'http://127.0.0.1:8787/assets/index-abc.js'
await runFetch(asset)
fetched.length = 0
await runFetch(asset)
check('同源 asset 第二次食 cache', fetched.length === 0)

// ④ 外部 CDN → stale-while-revalidate
const cdn = 'https://fonts.googleapis.com/css2?family=Noto+Sans+TC'
const c = runFetch(cdn)
check('外部 CDN 有攔截', c !== null)
await c

// ⑤ 導航 → network-first
fetched.length = 0
await runFetch('http://127.0.0.1:8787/some/route', { mode: 'navigate' })
check('導航會上網拎最新', fetched.length === 1)

// ⑥ 離線導航 → 食 index.html fallback
online = false
fetched.length = 0
let navResp = null, navErr = null
try {
  navResp = await runFetch('http://127.0.0.1:8787/offline-route', { mode: 'navigate' })
} catch (e) { navErr = e }
check('離線導航有 fallback（唔會爆）', navResp != null, navErr ? `err=${navErr.message}` : '')
online = true

// ══ 圖磚上限（LRU trim）══
console.log('\n▸ 圖磚上限')
const tiles = cachesMap.get('wander-v1-tiles')
check('圖磚 cache 存在', !!tiles)
// 直接測 trimCache 行為：塞 850 塊
for (let i = 0; i < 850; i++) {
  await runFetch(`https://b.tile.openstreetmap.org/13/${i}/1.png`)
}
const count = (await cachesMap.get('wander-v1-tiles').keys()).length
check('圖磚數量受上限控制', count <= 800, `實際 ${count}`)

// ══ message handler ══
console.log('\n▸ message handler')
let replied = null
handlers.message({
  data: { type: 'CACHE_STATUS', id: 'x1' },
  source: { postMessage: (m) => { replied = m } },
  waitUntil: (p) => p,
})
await new Promise(r => setTimeout(r, 50))
check('CACHE_STATUS 有回應', replied?.type === 'CACHE_STATUS')
check('回應含圖磚數', typeof replied?.tiles === 'number', `tiles=${replied?.tiles}`)

console.log(`\n${'═'.repeat(50)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(50))
process.exit(fail ? 1 : 0)
