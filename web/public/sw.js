/* ═══════════════════════════════════════════════════════════
   Wander Service Worker
   ═══════════════════════════════════════════════════════════

   策略（按資源類型分開，唔可以一刀切）：

   ┌─────────────────┬──────────────────┬──────────────────────────────┐
   │ 資源            │ 策略              │ 原因                          │
   ├─────────────────┼──────────────────┼──────────────────────────────┤
   │ app shell (js/css)│ cache-first    │ 檔名有 hash，永不變            │
   │ 導航 (/...)      │ network-first    │ 要拎到最新版本，離線先食 cache │
   │ OSM 圖磚         │ cache-first+LRU  │ 去旅行最需要 —— 離線睇地圖     │
   │ /api/…           │ network-only     │ 資料要即時，唔可以俾舊 cache   │
   │ 外部 CDN (字體等) │ stale-while-revalidate │ 有就用，冇就用舊            │
   └─────────────────┴──────────────────┴──────────────────────────────┘

   ⚠️ 重點決定：**API 一定要 network-only（唔快取）**。
      如果快取 API 回應，A 用戶嘅行程資料可能會出現喺 B 用戶嘅畫面 —— 私隱災難。
      （寫 `**` + `/` 會提早閂咗註解區塊 —— 呢個坑踩過，見下方 fetch handler。）

   ⚠️ 圖磚一定要有上限。OSM 圖磚每塊 ~15KB，行一次地圖就幾百塊。
      冇上限嘅話 cache 會爆（瀏覽器 quota 通常 50–100MB）。
   ⚠️ 只快取「成功 + 唔透明」嘅回應。opaque response 睇唔到 status，
      快取咗就冇得判斷好壞。
*/

const VERSION = 'wander-v1'
const SHELL = `${VERSION}-shell`
const TILES = `${VERSION}-tiles`
const EXT = `${VERSION}-ext`

const TILE_LIMIT = 800          // 約 12MB
const EXT_LIMIT = 120

// ── 工具 ──────────────────────────────────────────────────

/**
 * 將 cache 限制喺 max 個 entry 之內（由最舊開始刪）。
 *
 * ⚠️ 踩過嘅坑：`trimCache` 一定要 **await**。
 *    最初寫成 `trimCache(...)` 冇 await → 多個並發 put 同時跑 trim，
 *    互相覆蓋計算結果，最後超額（實測 801 > 800）。
 *    呢個係典型 race condition，喺單線程 JS 都會發生
 *    （因為 await cache.keys() 之後先 delete）。
 */
async function trimCache(name, max) {
  const cache = await caches.open(name)
  const keys = await cache.keys()
  const over = keys.length - max
  if (over <= 0) return
  for (const k of keys.slice(0, over)) {
    await cache.delete(k)
  }
}

async function networkFirst(req, cacheName, { put = true } = {}) {
  const cache = await caches.open(cacheName)
  try {
    const res = await fetch(req)
    // ⚠️ 只快取成功嘅基本回應（唔要 opaque / 206 partial）
    if (put && res && res.status === 200 && res.type === 'basic') {
      cache.put(req, res.clone())
    }
    return res
  } catch (err) {
    const hit = await cache.match(req)
    if (hit) return hit
    // 導航請求：離線都俾個殼，等 SPA 自己決定顯示咩
    if (req.mode === 'navigate') {
      const shell = await caches.open(SHELL)
      const idx = await shell.match('/index.html') || await shell.match('/')
      if (idx) return idx
    }
    throw err
  }
}

async function cacheFirst(req, cacheName, { limit, put = true } = {}) {
  const cache = await caches.open(cacheName)
  const hit = await cache.match(req)
  if (hit) return hit
  const res = await fetch(req)
  if (put && res && res.status === 200 && res.type === 'basic') {
    await cache.put(req, res.clone())
    if (limit) await trimCache(cacheName, limit)     // ⚠️ 必須 await
  }
  return res
}

async function staleWhileRevalidate(req, cacheName, { limit } = {}) {
  const cache = await caches.open(cacheName)
  const hit = await cache.match(req)
  const fetching = fetch(req).then(async (res) => {
    if (res && res.status === 200) {
      await cache.put(req, res.clone())
      if (limit) await trimCache(cacheName, limit)
    }
    return res
  }).catch(() => null)
  return hit || (await fetching) || Response.error()
}

// ── install：precache app shell ───────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL)
    // 攞 index.html，解析出入面引用嘅 assets 一齊 precache
    try {
      const res = await fetch('/index.html', { cache: 'reload' })
      const html = await res.clone().text()
      await cache.put('/index.html', res)
      const refs = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map(m => m[1])
      if (refs.length) await cache.addAll(refs)
    } catch {
      // 離線安裝（罕有）—— 唔緊要，之後 runtime cache 會補
    }
    await self.skipWaiting()
  })())
})

// ── activate：清走舊版本 ──────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(
      keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))
    )
    // 令新 SW 即刻接管（唔使等所有 tab 關閉）
    await self.clients.claim()
  })())
})

// ── fetch ────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  const same = url.origin === self.location.origin

  // ① API：永遠上網，唔快取（私隱 + 即時性）
  //    ⚠️ 唔快取 API 係刻意嘅：如果快取，A 嘅行程資料可能出現喺 B 嘅畫面。
  if (same && url.pathname.startsWith('/api/')) return

  // ② OSM 圖磚（去旅行嘅救命功能）
  if (/tile\.openstreetmap\.org$/.test(url.hostname)) {
    event.respondWith(cacheFirst(req, TILES, { limit: TILE_LIMIT }))
    return
  }

  // ③ 導航：network-first（拎最新版，離線食 cache）
  if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req, SHELL))
    return
  }

  // ④ 同源 assets（js/css/圖示）：cache-first（檔名有 hash）
  if (same) {
    event.respondWith(cacheFirst(req, SHELL))
    return
  }

  // ⑤ 外部（Google Fonts、Leaflet CDN）：stale-while-revalidate
  event.respondWith(staleWhileRevalidate(req, EXT, { limit: EXT_LIMIT }))
})

// ── 俾前端查詢離線狀態 / 清 cache ─────────────────────────
self.addEventListener('message', (event) => {
  const { type, id } = event.data || {}
  if (type === 'PING') {
    event.source?.postMessage({ type: 'PONG', id, version: VERSION })
  }
  if (type === 'CACHE_STATUS') {
    event.waitUntil((async () => {
      const [shell, tiles, ext] = await Promise.all(
        [SHELL, TILES, EXT].map(async n => (await caches.open(n)).keys().then(k => k.length))
      )
      event.source?.postMessage({ type: 'CACHE_STATUS', id, shell, tiles, ext, version: VERSION })
    })())
  }
  if (type === 'CLEAR_TILES') {
    event.waitUntil(caches.delete(TILES).then(() =>
      event.source?.postMessage({ type: 'CLEARED', id })))
  }
  if (type === 'SKIP_WAITING') self.skipWaiting()
})
