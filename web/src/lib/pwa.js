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

    // 每小時查一次更新
    setInterval(() => reg.update().catch(() => {}), 3600_000)
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
  navigator.serviceWorker.addEventListener('controllerchange', () => window.location.reload(), { once: true })
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
