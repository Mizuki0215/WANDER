/**
 * PWA 工具：service worker 註冊、離線狀態、安裝提示、cache 管理
 *
 * ⚠️ 註冊 service worker 有三個坑：
 *   1. 一定要 https 或者 localhost。用手機連 `http://192.168.x.x` 係
 *      **唔會**註冊到（browser 安全限制）→ 所以手機要「加到主畫面」先有離線。
 *   2. sw.js 一定要喺 root scope（/sw.js），唔可以放 /assets/。
 *   3. 更新之後要 skipWaiting，否則用戶要關閉所有 tab 先見到新版。
 */

let reg = null
const listeners = new Set()
const state = {
  supported: 'serviceWorker' in navigator,
  registered: false,
  online: navigator.onLine,
  updateReady: false,
  cache: null,
}

function emit() { listeners.forEach(fn => fn({ ...state })) }

export function subscribe(fn) {
  listeners.add(fn)
  fn({ ...state })
  return () => listeners.delete(fn)
}

export async function registerSW() {
  if (!state.supported) return null

  window.addEventListener('online', () => { state.online = true; emit() })
  window.addEventListener('offline', () => { state.online = false; emit() })

  try {
    reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
    state.registered = true
    emit()

    // 有新版本 → 提示用戶
    reg.addEventListener('updatefound', () => {
      const nw = reg.installing
      if (!nw) return
      nw.addEventListener('statechange', () => {
        if (nw.state === 'installed' && navigator.serviceWorker.controller) {
          state.updateReady = true
          emit()
        }
      })
    })

    // ⚠️⚠️ 用戶報：「shopping list 入唔到去睇」
    //
    //   ⚠️ 根因之一：`sw.js` 嘅 `VERSION` 從來冇改 → 瀏覽器
    //      永遠話「冇更新」→ 用戶一直跑舊版。
    //      （已修：vite build 時會換 VERSION）
    //
    //   ✅ 但**檢查時機**都要夠密：
    //      · 每隔 5 分鐘（原本一個鐘太疏）
    //      · **每次切返 app**（PWA 由背景返嚟 —— 用戶最常咁做）
    setInterval(() => reg.update().catch(() => {}), 5 * 60_000)

    // ⚠️ 切返 app 就查（`visibilitychange` 唔會晒電）
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') reg.update().catch(() => {})
    })
    return reg
  } catch (e) {
    console.warn('[wander] SW 註冊失敗', e)
    state.registered = false
    emit()
    return null
  }
}

export function applyUpdate() {
  if (!reg?.waiting) { window.location.reload(); return }
  reg.waiting.postMessage({ type: 'SKIP_WAITING' })
  navigator.serviceWorker.addEventListener(
    'controllerchange', () => window.location.reload(), { once: true })
  // ⚠️ Fallback：`controllerchange` 唔一定觸發（舊瀏覽器 / race）——
  //    1.5 秒後強制 reload，唔好卡死喺舊版。
  setTimeout(() => window.location.reload(), 1500)
}

/**
 * ⚠️⚠️ 清晒所有 cache + 登出 service worker，然後 reload。
 *
 *   為咩要：用戶報「入唔到去睇」呢類問題，**九成係快取舊版**。
 *   一般 `applyUpdate()` 唔夠 —— 要連 cache 都清。
 *
 *   ⚠️ 唔會清 localStorage（唔想登出用戶）。
 */
export async function hardReload() {
  try {
    const keys = await caches.keys()
    await Promise.all(keys.map(k => caches.delete(k)))
  } catch {}
  try {
    const rs = await navigator.serviceWorker.getRegistrations()
    await Promise.all(rs.map(r => r.unregister()))
  } catch {}
  // ⚠️ cache-busting query（唔係嘅話可能攞返 HTTP cache）
  const u = new URL(window.location.href)
  u.searchParams.set('_r', Date.now().toString(36))
  window.location.replace(u.toString())
}

/** 問 service worker 拎 cache 狀況。 */
export function cacheStatus() {
  return new Promise((resolve) => {
    if (!navigator.serviceWorker?.controller) return resolve(null)
    const id = Math.random().toString(36).slice(2)
    const onMsg = (e) => {
      if (e.data?.type === 'CACHE_STATUS' && e.data.id === id) {
        navigator.serviceWorker.removeEventListener('message', onMsg)
        resolve(e.data)
      }
    }
    navigator.serviceWorker.addEventListener('message', onMsg)
    navigator.serviceWorker.controller.postMessage({ type: 'CACHE_STATUS', id })
    setTimeout(() => resolve(null), 2500)
  })
}

/** 清走地圖圖磚快取（慳位）。 */
export function clearTiles() {
  return new Promise((resolve) => {
    if (!navigator.serviceWorker?.controller) return resolve(false)
    const id = Math.random().toString(36).slice(2)
    const onMsg = (e) => {
      if (e.data?.type === 'CLEARED' && e.data.id === id) {
        navigator.serviceWorker.removeEventListener('message', onMsg)
        resolve(true)
      }
    }
    navigator.serviceWorker.addEventListener('message', onMsg)
    navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_TILES', id })
    setTimeout(() => resolve(false), 2500)
  })
}

/** 清 app 資料（登出時用）。 */
export async function clearAppCaches() {
  if (!('caches' in window)) return
  const keys = await caches.keys()
  await Promise.all(keys.map(k => caches.delete(k)))
}
