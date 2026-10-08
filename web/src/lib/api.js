/**
 * wander API client
 * 所有 fetch 集中喺呢度，方便統一處理 token 同錯誤。
 */

const TOKEN_KEY = 'wander.token'

export const auth = {
  get token() {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set token(v) {
    try { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY) } catch {}
  },
  clear() { this.token = null },
}

/**
 * ⚠️⚠️ 請求逾時（毫秒）
 *
 *   用戶報嘅 bug：
 *     「加唔到 item 入 shopping list」
 *     截圖見到：購物清單填好晒（名 + 價錢 + 相），
 *     撳「＋」→ **個掣變灰，郁都唔郁，清單仲係空嘅**。
 *
 *   ⚠️ 根因：`fetch` **冇 timeout**。
 *      用戶揀咗相 → `api.upload()` 上傳 4MB base64 →
 *      經 5G + cloudflared tunnel → **卡住** →
 *      `busy` 永遠 `true` → 個掣永遠 disabled →
 *      用戶以為「加唔到」，其實係**等緊一個永遠唔會完嘅請求**。
 *
 *   ✅ 修法：`AbortController` + timeout。
 *      正常請求（本地／4G）幾百 ms 完成，30 秒好夠。
 *      上傳相（base64 大 33%）畀多啲：60 秒。
 */
const TIMEOUT_MS = 30000
const UPLOAD_TIMEOUT_MS = 60000

async function req(method, path, { body, params, timeout = TIMEOUT_MS } = {}) {
  const url = new URL(path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v)
    })
  }
  const headers = { 'Content-Type': 'application/json' }
  const hadToken = !!auth.token
  if (hadToken) headers.Authorization = `Bearer ${auth.token}`

  // ⚠️ 一定要 `clearTimeout`（finally）—— 唔係嘅話每個請求都留一個 timer
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeout)

  let res
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctl.signal,
    })
  } catch (e) {
    // ⚠️ 分清「用戶自己取消」同「逾時」
    if (e.name === 'AbortError') {
      throw new Error(
        timeout >= UPLOAD_TIMEOUT_MS
          ? `上傳逾時（超過 ${timeout / 1000} 秒）—— 網絡太慢或者相太大，試下細啲嘅相`
          : `連接逾時（超過 ${timeout / 1000} 秒）—— 檢查網絡`
      )
    }
    throw new Error(e.message === 'Failed to fetch'
      ? '連唔到伺服器 —— 檢查網絡' : e.message)
  } finally {
    clearTimeout(timer)
  }

  // ⚠️⚠️ 401 唔一定係「session 過期」！
  //
  //    用戶報嘅 bug：
  //      「我登入嘅時候佢同我講『登入已過期，重新登入』…
  //        正常都係用 20 秒之內去登入，但佢同我講話過期唔得。」
  //
  //    原因：後端 `POST /api/auth/password` 用 **401** 表示
  //          「Email 或密碼唔啱」——
  //          而呢度**所有** 401 都當「過期」→ 清 token + 登出 +
  //          顯示「登入已過期」。用戶打錯密碼就見到「已過期」。
  //
  //    ⚠️ 判斷方法：**有冇帶 token**。
  //       · 有帶 token 而 401 → 真係 session 過期（token 唔再有效）
  //       · 冇帶 token 而 401 → 係「憑證唔啱」（登入 API）
  //         → 應該照樣拋後端嘅訊息（「Email 或密碼唔啱」）
  if (res.status === 401 && hadToken) {
    auth.clear()
    window.dispatchEvent(new Event('wander:logout'))
    throw new Error('登入已過期，請重新登入')
  }

  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = { detail: text } }

  if (!res.ok) {
    // ⚠️ FastAPI 嘅 `detail` 可以係**物件**（例如 register 回應
    //    `{detail: "...", needs_claim: true}`）。
    //    直接 `new Error(object)` 會變 `[object Object]` —— 用戶睇唔明，
    //    而且前端亦都冇辦法判斷 needs_claim。
    //    所以：抽字串訊息，其他欄位掛喺 error 上面。
    const d = data?.detail
    const msg = typeof d === 'string' ? d
      : (d && typeof d === 'object' && typeof d.detail === 'string') ? d.detail
      : (data?.message || `HTTP ${res.status}`)
    const err = new Error(msg)
    err.status = res.status
    if (data && typeof data === 'object') Object.assign(err, data)
    if (d && typeof d === 'object') Object.assign(err, d)
    throw err
  }
  return data
}

export const CATEGORY_LABELS = {
  food: '🍜 食', shopping: '🛍 購物', play: '🎡 玩',
  stay: '🏨 住', transport: '🚕 交通', other: '✦ 其他',
}

export const api = {
  // ── auth ──
  requestCode: (email) => req('POST', '/api/auth/request-code', { body: { email } }),
  verify: (email, code) => req('POST', '/api/auth/verify', { body: { email, code } }),
  passwordLogin: (email, password) =>
    req('POST', '/api/auth/password', { body: { email, password } }),
  me: () => req('GET', '/api/me'),
  updateMe: (patch) => req('PATCH', '/api/me', { body: patch }),
  finishOnboard: (display_name) =>
    req('POST', '/api/me/onboard', { body: { display_name } }),
  // ⚠️ 重看教學**唔會**改 onboarded ——
  //    呢個只係「我想再睇一次」，唔應該影響「第一次」嘅狀態。
  //    所以前端直接開 overlay，唔使 API。


  // ── trips ──
  createTrip: (trip) => req('POST', '/api/trips', { body: trip }),
  getTrip: (id) => req('GET', `/api/trips/${id}`),
  updateTrip: (id, patch) => req('PATCH', `/api/trips/${id}`, { body: patch }),
  joinTrip: (code) => req('POST', `/api/trips/join/${code}`),
  deleteTrip: (id) => req('DELETE', `/api/trips/${id}`),
  leaveTrip: (id) => req('POST', `/api/trips/${id}/leave`),
  addMember: (id, email) => req('POST', `/api/trips/${id}/members`, { body: { email } }),
  listItems: (id) => req('GET', `/api/trips/${id}/items`),
  stops: (id) => req('GET', `/api/trips/${id}/stops`),
  searchCities: (q, limit = 12) => req('GET', '/api/cities', { params: { q, limit } }),
  geocode: (q) => req('GET', '/api/geocode', { params: { q } }),
  igProvider: () => req('GET', '/api/ig-provider'),
  qr: (url) => req('GET', '/api/qr', { params: url ? { url } : {} }),

  // ── @帳號名 / 加朋友 / 個人 QR ──
  //   ⚠️⚠️ 呢四個一度**完全冇定義**，但元件照叫 ——
  //      `MyQr` 喺 useEffect 入面叫 `api.myQr()` →
  //      TypeError → React unmount 成棵樹 → **白畫面**。
  //      用戶報：「朋友 QR code 嗰度…生成嗰陣時…個畫面一路之後就冇咗」
  //
  //      點解測試捉唔到：舊測試只檢查「**呼叫方**有冇寫 api.myQr」，
  //      冇檢查「**定義方**有冇 api.myQr」。
  //      而家加咗自動交叉檢查（見 tests/web/api.test.mjs）。
  // ── Auth（登入 / 註冊）──
  // ⚠️ `inviteCode` 係 optional —— 只有 `invite` 模式先要
  register: (email, password, inviteCode) =>
    req('POST', '/api/auth/register', {
      body: { email, password, invite_code: inviteCode || null },
    }),
  claimAccount: (email, code, password) =>
    req('POST', '/api/auth/claim', { body: { email, code, password } }),

  lookupUser: (username) =>
    req('GET', '/api/users/lookup', { params: { username } }),
  requestFriendByName: (username) =>
    req('POST', '/api/friends/requests', { body: { username } }),
  // ── 開發版後台 ──
  adminMe: () => req('GET', '/api/admin/me'),
  adminMail: () => req('GET', '/api/admin/mail'),
  testMail: (to) => req('POST', '/api/admin/test-mail', { body: { to } }),
  // ⚠️ 註冊模式（公開 endpoint，未登入都用得）
  signupMode: () => req('GET', '/api/auth/signup-mode'),
  /** ⚠️ 檢查邀請碼（公開，未登入都用得）—— 撳「驗證」掣會叫。 */
  checkInvite: (code) => req('POST', '/api/auth/check-invite', { body: { code } }),
  adminInvites: () => req('GET', '/api/admin/signup-invites'),
  makeInvites: (count = 1, note = '', days = 30) =>
    req('POST', '/api/admin/signup-invites', { body: { count, note, days } }),
  adminOverview: (days = 30) => req('GET', '/api/admin/overview', { params: { days } }),

  // ── 後台：數據管理（用戶要求「我想有個後台去管理數據」）──
  /** ⚠️ Dashboard：幾多數據 + 邊個用戶用緊 */
  adminActiveUsers: (days = 30, limit = 40) =>
    req('GET', '/api/admin/active-users', { params: { days, limit } }),
  adminUsers: (q = '', limit = 50, offset = 0) =>
    req('GET', '/api/admin/users', { params: { q, limit, offset } }),
  adminTrips: (q = '', limit = 50, offset = 0) =>
    req('GET', '/api/admin/trips', { params: { q, limit, offset } }),
  adminExport: (what = 'summary') =>
    req('GET', '/api/admin/export', { params: { what } }),
  // ⚠️⚠️ 刪除功能**已經刪走** ——
  //    用戶澄清：「我淨係想整嘅係有幾多數據？有啲咩用戶用緊。」
  //    → Dashboard 應該係**唯讀**（少一個誤刪風險）。
  //    真係要刪嘅話用 server/tools/manage_account.py。
  /** ⚠️ 回報使用事件 —— 一定要 catch，唔可以影響主流程。 */
  track: (kind, target) => req('POST', '/api/events', { body: { kind, target } })
    .catch(() => {}),

  myQr: () => req('GET', '/api/me/qr'),
  decodeQr: (data) => req('POST', '/api/qr/decode', { body: { data } }),

  // ⚠️⚠️ 私隱（用戶要求）
  //    · 購物清單：預設 private（自己睇），可以 group（全組）
  //    · 收藏景點：預設 private，可以 public
  setItemVisibility: (itemId, visibility) =>
    req('PATCH', `/api/item/${itemId}/visibility`, { body: { visibility } }),

  zones: (id, days) => req('GET', `/api/trips/${id}/zones`, { params: days ? { days } : {} }),
  listShopping: (id) => req('GET', `/api/trips/${id}/shopping`),
  addShopping: (id, body) => req('POST', `/api/trips/${id}/shopping`, { body }),
  /** ⚠️ 匯率（有快取 6 個鐘，唔係每次查 API） */
  rates: (base = 'HKD') => req('GET', '/api/rates', { params: { base } }),
  /** 揀貨幣用嘅清單（常用 + 全部） */
  currencies: () => req('GET', '/api/currencies'),
  updateShopping: (sid, body) => req('PATCH', `/api/shopping/${sid}`, { body }),
  deleteShopping: (sid) => req('DELETE', `/api/shopping/${sid}`),
  clearDoneShopping: (id) => req('POST', `/api/trips/${id}/shopping/clear-done`),
  nearby: (id, item, radius) => req('GET', `/api/trips/${id}/nearby`,
    { params: { item, ...(radius ? { radius } : {}) } }),
  /** ⚠️ 上傳用 60 秒（base64 大 33%，手機網絡慢） */
  upload: (data) => req('POST', '/api/upload', {
    body: { data }, timeout: UPLOAD_TIMEOUT_MS,
  }),
  /** ⚠️ 自訂背景（用戶要求）—— `/uploads/x.jpg` 或 preset key，空字串 = 清走 */
  setWallpaper: (wallpaper) => req('PATCH', '/api/me', { body: { wallpaper } }),
  setPassword: (password, current) => req('POST', '/api/me/password', { body: { password, current } }),
  listExpenses: (id) => req('GET', `/api/trips/${id}/expenses`),
  addExpense: (id, body) => req('POST', `/api/trips/${id}/expenses`, { body }),
  updateExpense: (eid, body) => req('PATCH', `/api/expenses/${eid}`, { body }),
  deleteExpense: (eid) => req('DELETE', `/api/expenses/${eid}`),
  setStops: (id, stops) => req('PUT', `/api/trips/${id}/stops`, { body: { stops } }),

  // ── parse / lookup ──
  parse: (payload) => req('POST', '/api/parse', { body: payload }),
  lookup: (name, hint) => req('GET', '/api/lookup', { params: { name, hint } }),
  /** ⚠️ 城市 → 時區（世界時鐘用，唔使有旅程） */
  tz: (city) => req('GET', '/api/tz', { params: { city } }),

  // ── items ──
  addItem: (tripId, parsed) => req('POST', '/api/items', { body: parsed, params: { trip_id: tripId } }),
  patchItem: (id, patch) => req('PATCH', `/api/items/${id}`, { body: patch }),
  deleteItem: (id) => req('DELETE', `/api/items/${id}`),
  vote: (id) => req('POST', `/api/items/${id}/vote`),
  reorder: (tripId, layout) => req('POST', '/api/items/reorder', {
    body: { trip_id: tripId, layout },
  }),

  // ── friends ──
  friends: () => req('GET', '/api/friends'),
  requestFriend: (email) => req('POST', '/api/friends/requests', { body: { email } }),
  acceptFriend: (id) => req('POST', `/api/friends/requests/${id}/accept`),
  rejectFriend: (id) => req('POST', `/api/friends/requests/${id}/reject`),
  removeFriend: (id) => req('DELETE', `/api/friends/${id}`),
  invites: () => req('GET', '/api/invites'),
  inviteToTrip: (tripId, email) => req('POST', `/api/trips/${tripId}/invite`, { body: { email } }),
  acceptInvite: (id) => req('POST', `/api/invites/${id}/accept`),
  rejectInvite: (id) => req('POST', `/api/invites/${id}/reject`),
}

export const CATEGORY_ICON = {
  food: '🍜', shopping: '🛍', play: '🎡', stay: '🏨', transport: '🚇', other: '📍',
}

export function iconFor(item) {
  if (item.category && CATEGORY_ICON[item.category]) return CATEGORY_ICON[item.category]
  return '📍'
}

export function confClass(c) {
  const n = Number(c) || 0
  return n >= 85 ? 'hi' : n >= 65 ? 'md' : 'lo'
}
