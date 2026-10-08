import { useCallback, useEffect, useRef, useState } from 'react'
import { api, auth } from './lib/api'
import { Toast, Stars, toast, Spinner } from './lib/ui'
import Wallpaper from './components/Wallpaper'
import { tripLength } from './lib/dates'
import Login from './components/Login'
import Discover from './components/Discover'
import MapView from './components/MapView'
import Calendar from './components/Calendar'
import Saved from './components/Saved'
import Trips from './components/Trips'
import BootScreen from './components/BootScreen'
import HomeScreen, { APPS } from './components/HomeScreen'
import ShoppingList from './components/ShoppingList'
import Settlement from './components/Settlement'
import AddPlace from './components/AddPlace'
import Friends from './components/Friends'
import Settings from './components/Settings'
import PixelIcon from './components/PixelIcon'
import Onboarding from './components/Onboarding'
import Admin from './components/Admin'
import { isSelf, SELF_MSG } from './lib/selfcheck'
import ItemDetail from './components/ItemDetail'
import PwaBar from './components/PwaBar'

const THEME_KEY = 'wander.theme'

/**
 * ⚠️⚠️ 邊啲 app **需要**一個旅程先用到。
 *
 * 用戶報嘅 bug 就係因為冇呢個清單 —— 用 `tab !== 'trips'` 做閘，
 * 連 ⚙️ 設定、👥 朋友 都被擋 → 撳「設定」出「先揀一個旅程」。
 *
 * ⚠️ 呢個清單係**唯一真相來源** —— 兩處用：
 *   ① `openApp()` 撳 app icon 嗰陣
 *   ② render 嗰陣決定要唔要出「先揀一個旅程」
 *    如果兩處各寫一份，將來一定會唔同步。
 */
const TRIP_APPS = ['discover', 'calendar', 'money', 'shopping', 'saved', 'map']

/**
 * 記住「上次揀嘅旅程」。
 *
 * ⚠️⚠️ 為咩要存 localStorage：
 *   用戶報：「揀咗旅程之後…再出返去…佢就同我講未揀旅程」。
 *   其中一個原因係 tripId 只係 `useState(null)` ——
 *   一 refresh（或者喺手機被系統殺 app 之後重開）就冇咗。
 *
 * ⚠️ 為咩唔存後端：
 *   「而家揀邊個旅程」係**呢部機**嘅狀態（好似瀏覽器分頁），
 *   唔係帳號狀態。用同一帳號喺兩部機會想睇唔同旅程。
 *
 * ⚠️ 讀嘅時候一定要 try/catch ——
 *   無痕模式 / 停用 cookie 之下 localStorage 會拋。
 */
const TRIP_KEY = 'wander_trip'

function saveTrip(id) {
  try {
    if (id) localStorage.setItem(TRIP_KEY, id)
    else localStorage.removeItem(TRIP_KEY)
  } catch {}
}

function readSavedTrip() {
  try { return localStorage.getItem(TRIP_KEY) || null } catch { return null }
}

export default function App() {
  const [booting, setBooting] = useState(true)
  const [user, setUser] = useState(null)
  const [trips, setTrips] = useState([])
  const [tripId, setTripId] = useState(null)
  // ⚠️ 開發版後台（用戶要求）—— 只有 admin 見到入口
  const [isAdmin, setIsAdmin] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)
  const [trip, setTrip] = useState(null)
  const [items, setItems] = useState([])
  const [stops, setStops] = useState([])
  const [tab, setTab] = useState('home')
  const [booted, setBooted] = useState(false)
  /**
   * ⚠️⚠️ 底部導航嘅**真實高度** → 寫入 `--nav-h`。
   *
   *   用戶報：「UI scroll 有啲怪」+ 截圖見到
   *   **最底嘅「未排入行程」托盤被導航切走**。
   *
   *   ⚠️ 根因：CSS 寫死 `--nav-h: 62px`，但實際高度喺手機上會變：
   *      · 「HOME」+「主畫面」兩個 span → **兩行**（截圖證實）
   *      · 用戶調大系統字體（iOS 動態字體）
   *      · 窄機（320px）label 換行
   *      · 瀏海機嘅 safe-area
   *     → 實際 ~80px 但 padding 只留 62px → 內容被切。
   *
   *   ✅ 修法：`ResizeObserver` 量度真實高度。
   *      ⚠️ 唔可以「改成 80px」—— 另一部機會再錯。
   *
   *   ⚠️⚠️ 為咩用**回呼 ref** 而唔係 `useRef` + `useEffect`：
   *
   *      呢個 component 有**條件 return**（`if (booting)` / `if (!user)`）。
   *      React 規則：**所有 hook 都要喺條件 return 之前**。
   *      但 `isHome`（決定有冇 nav）喺條件 return **之後**才定義 ——
   *      擺前面會爆 `Cannot access 'isHome' before initialization`，
   *      擺後面會爆 `Rendered more hooks than during the previous render`。
   *
   *      ✅ 回呼 ref 完全唔使 hook —— React 喺**掛載／卸載**時叫佢，
   *         冇次序問題，而且天然處理「nav 出現／消失」。
   *
   *   ⚠️ React 18 嘅回呼 ref **唔支援 return cleanup**（React 19 才有），
   *      所以 cleanup 自己存喺 `navCleanup`。
   */
  const navCleanup = useRef(null)

  const navRef = useCallback((el) => {
    const root = document.documentElement

    // ① 先清走上一次（nav 卸載，或者重新掛載）
    if (navCleanup.current) {
      try { navCleanup.current() } catch {}
      navCleanup.current = null
    }

    // ② 冇 nav（主畫面）→ --nav-h = 0
    //    ⚠️ 唔清走嘅話會留一段空白（原本 62px 嘅 padding）
    if (!el) {
      root.style.setProperty('--nav-h', '0px')
      return
    }

    const apply = () => {
      const h = el.getBoundingClientRect().height
      if (h > 0) root.style.setProperty('--nav-h', `${Math.round(h)}px`)
    }
    apply()

    // ⚠️ 一定要 observe —— 字體載入、label 換行、轉向都會改高度
    //
    //   ⚠️⚠️ 但一定要**檢查存在**：
    //      · Safari < 13.1 冇 `ResizeObserver`
    //      · jsdom（測試環境）都冇
    //      冇檢查就會爆 `ReferenceError` → **成個 app 白畫面**。
    //      （實測：dom.test.mjs 即刻爆咗。）
    const onOrient = () => apply()

    if (typeof ResizeObserver === 'undefined') {
      // ⚠️ 退化：只聽 resize / orientationchange
      window.addEventListener('resize', apply)
      window.addEventListener('orientationchange', onOrient)
      navCleanup.current = () => {
        window.removeEventListener('resize', apply)
        window.removeEventListener('orientationchange', onOrient)
        root.style.removeProperty('--nav-h')
      }
      return
    }

    const ro = new ResizeObserver(apply)
    ro.observe(el)
    window.addEventListener('orientationchange', onOrient)

    navCleanup.current = () => {
      ro.disconnect()
      window.removeEventListener('orientationchange', onOrient)
      root.style.removeProperty('--nav-h')
    }
  }, [])
  const [shopBadge, setShopBadge] = useState(0)
  const [friendBadge, setFriendBadge] = useState(0)
  const [friendToken, setFriendToken] = useState(null)
  const [pendingAdd, setPendingAdd] = useState(null)
  // ⚠️ 重看教學：**唔會**改 onboarded ——
  //    呢個只係「想再睇一次」，同「第一次」係兩件事。
  //    如果重看會將 onboarded 設返 0，用戶中途閂咗 app
  //    下次登入又會強制彈教學。
  const [replayTour, setReplayTour] = useState(false)
  const [newTrip, setNewTrip] = useState(false)
  // ⚠️⚠️ 用戶要求 ③：
  //   「只會喺主頁面嗰度揀你想要嘅行程…需要唔需要令我開一個頁面
  //    就係話你要揀一個行程？」
  //   → **唔要**。撳 app 而未有旅程 → 留喺主頁，將旅程選擇器打開。
  //     （原本係跳去「旅程」app = 一個獨立嘅「請揀旅程」頁。）
  const [wantPick, setWantPick] = useState(false)

  /** 撳 app icon：需要旅程嘅 app 而未有旅程 → 彈旅程選擇。 */
  const openApp = useCallback((id) => {
    // ⚠️ 記「開啟邊個 app」—— 後台最重要嘅一個數字
    //    （睇得出邊個功能最多人用、邊個開咗但冇用）
    api.track('app_open', id)
    if (TRIP_APPS.includes(id) && !tripId) {
      // ⚠️ 留喺主頁 + 打開旅程選擇器 —— 唔跳去另一個頁面
      toast('先揀一個旅程')
      setTab('home')
      setWantPick(true)
      return
    }
    setTab(id)
  }, [tripId])
  const [detail, setDetail] = useState(null)
  const [theme, setThemeState] = useState(() => {
    try { return localStorage.getItem(THEME_KEY) || 'galaxy' } catch { return 'galaxy' }
  })
  const bootRef = useRef(false)

  const setTheme = useCallback((t) => {
    setThemeState(t)
    try { localStorage.setItem(THEME_KEY, t) } catch {}
  }, [])

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme) }, [theme])

  useEffect(() => {
    const onLogout = () => { setUser(null); setTripId(null); setTrip(null); setItems([]) }
    window.addEventListener('wander:logout', onLogout)
    return () => window.removeEventListener('wander:logout', onLogout)
  }, [])

  /**
   * ⚠️⚠️ 查我係唔係 admin（決定要唔要顯示後台入口）。
   *
   *   ⚠️⚠️ 用戶報：「入到 Dashboard 未？nooo」
   *
   *   ⚠️ 根因：呢個檢查原本**只喺 mount 嗰陣叫一次**，而且
   *      `if (!auth.token) return` ——
   *      即係「**登入**入去」嘅用戶**永遠** `isAdmin = false`！
   *      （只有「一開 app 已經有 token」嘅舊 session 先叫得到。）
   *
   *   ✅ 修法：抽做 `checkAdmin()`，喺**登入之後**都叫。
   *      ⚠️ 亦都加入 `refreshMe()`，咁改權限之後 refresh 就生效。
   */
  const checkAdmin = useCallback(async () => {
    // ⚠️ 冇 token 就唔好問（會 401）
    if (!auth.token) { setIsAdmin(false); return }
    try {
      const x = await api.adminMe()
      setIsAdmin(!!x?.admin)
    } catch {
      // ⚠️ 403 = 唔係 admin（正常）；其他錯都當唔係
      setIsAdmin(false)
    }
  }, [])

  /**
   * ⚠️⚠️ 揀「而家嘅旅程」—— 開機同 refresh 都要行。
   *
   *   🚨 用戶報（報咗兩次）：「shopping list 入唔到去睇」
   *
   *   ⚠️ 根因：呢段邏輯原本**只喺 `refreshTrips()` 入面**，
   *      但**開機嗰陣從來冇 call `refreshTrips()`** ——
   *      開機係行另一條路（直接 `api.me()` + `setTrips()`）。
   *
   *      → 用戶明明有旅程「Fukuoka」，但 `tripId` 永遠 `null`
   *      → 主畫面顯示「✈️ 未揀旅程」
   *      → 撳 Shopping → 彈「先揀一個旅程」+ 旅程選擇器
   *      → 用戶以為「入唔到去睇」
   *
   *   ⚠️ 而且**只有一個旅程**嘅用戶最容易被咬 ——
   *      因為佢哋預期「得一個就梗係自動入去」。
   *
   *   ✅ 修法：抽做一個 `pickTrip()`，開機**同** refresh 都叫。
   */
  const pickTrip = useCallback((list) => {
    setTripId(prev => {
      const arr = list || []
      // ① 而家揀嘅仲喺度 → 保留
      if (prev && arr.some(t => t.id === prev)) return prev
      // ② 還原上次揀嘅（localStorage）
      const saved = readSavedTrip()
      if (saved && arr.some(t => t.id === saved)) return saved
      // ③ ⚠️ 只有一個旅程 → **自動揀**（用戶最常撞到嘅情況）
      if (arr.length === 1) return arr[0].id
      return prev
    })
  }, [])

  // 啟動
  useEffect(() => {
    if (bootRef.current) return
    bootRef.current = true
    ;(async () => {
      if (!auth.token) { setBooting(false); return }
      try {
        const r = await api.me()
        setUser(r.user); setTrips(r.trips)
        // ⚠️⚠️ 開機一定要揀旅程 —— 唔係嘅話「只有一個旅程」嘅
        //    用戶會見到「未揀旅程」→ 撳任何 app 都話「先揀一個旅程」
        //    （用戶報「shopping list 入唔到去睇」嘅真正原因）
        pickTrip(r.trips)
        if (r.user.theme) setTheme(r.user.theme)
        checkAdmin()
        // ⚠️ 記一個事件（後台數據來源）。失敗唔緊要。
        api.track('login')
      } catch { auth.clear() } finally { setBooting(false) }
    })()
  }, [setTheme, pickTrip])   // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * ⚠️⚠️ 重新攞自己嘅 user（`/api/me`）。
   *
   *   為咩要：用戶報「我個帳號本身 set 咗密碼，但 setting 話我
   *   仲未有密碼」—— 根因係 `/api/me` 冇回 `has_password`。
   *   修好之後，改完密碼要即刻 refresh 一次，個 UI 先會跟。
   *   ⚠️ 另外做 fallback：如果後端話「現有密碼唔啱」但前端以為
   *      冇密碼 → refresh 就出返個「現有密碼」欄。
   */
  const refreshMe = useCallback(async () => {
    try {
      const r = await api.me()
      if (r?.user) setUser(r.user)
      if (r?.trips) setTrips(r.trips)
      // ⚠️ 順便重新檢查 admin（改咗 WANDER_ADMIN_EMAILS 之後 refresh 就生效）
      checkAdmin()
    } catch {}
  }, [checkAdmin])

  const refreshTrips = useCallback(async () => {
    const r = await api.me()
    setTrips(r.trips)
    pickTrip(r.trips)
    return r.trips
  }, [pickTrip])

  const refreshBadges = useCallback(async () => {
    try {
      const f = await api.friends()
      const n = (f.incoming || []).length
      setFriendBadge(n)
    } catch {}
  }, [])

  const refreshTrip = useCallback(async (id) => {
    const tid = id
    if (!tid) return
    try {
      const [t, it, st] = await Promise.all([
        api.getTrip(tid), api.listItems(tid), api.stops(tid),
      ])
      setTrip(t); setItems(it.items); setStops(st.stops || [])
      setDetail(d => (d ? (it.items.find(x => x.id === d.id) || d) : null))
      api.listShopping(tid)
        .then(r => setShopBadge(r.pending_count || 0))
        .catch(() => {})
      refreshBadges()
    } catch (e) { toast(e.message) }
    // ⚠️⚠️ deps **一定唔可以**有 `tripId` ——
    //    上面嘅 effect 依賴 `refreshTrip`，如果 `refreshTrip`
    //    每次 `tripId` 變都重新 create，effect 就會無限 loop。
    //    ✅ `tripId` 由 caller 傳入（`refreshTrip(tripId)`）。
  }, [refreshBadges])

  const openTrip = useCallback(async (id) => {
    setTripId(id); setTab('home')
    saveTrip(id)
    try {
      const [t, it, st] = await Promise.all([
        api.getTrip(id), api.listItems(id), api.stops(id),
      ])
      setTrip(t); setItems(it.items); setStops(st.stops || [])
      api.listShopping(id).then(r => setShopBadge(r.pending_count || 0)).catch(() => {})
    } catch (e) { toast(e.message) }
  }, [])

  /**
   * 去旅程清單（**保留**已揀嘅旅程）。
   *
   * ⚠️⚠️ 之前呢個 function 會 `setTripId(null)` —— 就係用戶報嘅 bug：
   *   「揀咗旅程之後…整理 organize 呢啲…再出返去撳返旅程出返去個
   *     Home 度…佢就同我講未揀旅程。」
   *
   *   ⚠️ 為咩「去清單」唔應該等於「退出旅程」：
   *      用戶嘅心智模型係「我而家喺福岡之旅入面」——
   *      撳「旅程」只係**睇下我仲有咩旅程**，唔係放棄福岡。
   *      清單會標示邊個係「當前」，返 Home 就返到福岡。
   *
   *   ⚠️ 真正要退出 → 用 `exitTrip()`（清單入面有明確嘅掣）。
   */
  const backToTrips = useCallback(() => {
    setDetail(null)
    setTab('trips')
    refreshTrips()
  }, [refreshTrips])

  /**
   * ⚠️⚠️ `tripId` 一變就 load 該旅程嘅資料。
   *
   *   🚨 用戶報（報咗兩次）：「shopping list 入唔到去睇」
   *
   *   ⚠️ 根因（**兩個疊埋**）：
   *     ① 開機從來冇「揀旅程」→ `tripId` 永遠 null
   *        （已修：抽 `pickTrip()`，開機都叫）
   *     ② ⚠️ 就算 `tripId` 有值，**都冇 effect 去 load 旅程**——
   *        `refreshTrip(tripId)` 只喺用戶撳「refresh」或者 `openTrip()` 嗰陣叫。
   *
   *        → 結果：旅程 header 顯示「0 日 · 👥 0 · ✦ 0」，
   *          購物清單永遠「空嘅」、行程永遠空白。
   *
   *   ✅ 修法：加呢個 effect —— `tripId` 一變就 `refreshTrip(tripId)`。
   *
   *   ⚠️ 一定要傳 `tripId` 入去（唔係靠 closure 嘅 `tripId`）——
   *      因為 `refreshTrip` 嘅 closure 可能係舊嗰個。
   */
  useEffect(() => {
    if (!tripId) { setTrip(null); setItems([]); setStops([]); return }
    refreshTrip(tripId)
  }, [tripId, refreshTrip])

  /** 真正退出旅程（清空揀選）。 */
  const exitTrip = useCallback(() => {
    saveTrip(null)
    setTripId(null); setTrip(null); setItems([]); setStops([])
    setDetail(null); setTab('trips')
    refreshTrips()
  }, [refreshTrips])

  // ⚠️ Web Share Target：用戶喺 IG / 小紅書撳「分享 → Wander」
  //    只有 PWA 安裝 + HTTPS 先 work。收到 title/text/url 就直接解析。
  useEffect(() => {
    if (!user) return
    if (!/^\/share/.test(window.location.pathname)) return
    const q = new URLSearchParams(window.location.search)
    const shared = [q.get('text'), q.get('url'), q.get('title')].filter(Boolean).join('\n')
    window.history.replaceState({}, '', '/')
    if (!shared.trim()) return
    ;(async () => {
      try {
        toast('收到分享，解析緊…')
        const r = await api.parse({ text: shared, url: q.get('url') || undefined })
        const found = r.items || []
        if (!found.length) return toast('解析唔到內容')
        // 存入第一個 trip（或者叫用戶揀）
        const list = await refreshTrips()
        const tid = list[0]?.id
        if (!tid) return toast('請先開一個旅程')
        let n = 0
        for (const it of found) { try { await api.addItem(tid, it); n++ } catch {} }
        toast(`已加入 ${n} 個收藏（${list[0].name}）✓`)
        if (tripId) await refreshTrip(tripId)
      } catch (e) { toast(e.message) }
    })()
  }, [user])   // eslint-disable-line

  /** 好友請求 + 購物 badge（主畫面顯示）。 */

  // ⚠️ 個人 QR 連結：/?add=<username>
  //    對方用手機原生相機掃我嘅 QR → 開到 app 並帶住 ?add=alice
  //    → 我哋記住，等佢登入之後自動跳去朋友頁並預填 @名
  useEffect(() => {
    const q = new URLSearchParams(window.location.search)
    const add = q.get('add')
    if (!add) return
    try { localStorage.setItem('wander_add_user', add) } catch {}
    window.history.replaceState({}, '', window.location.pathname)
    setPendingAdd(add)
  }, [])

  // ⚠️ 交友邀請連結：/?friend=<token>
  //    對方撳 email 連結 → 我哋記住個 token → 佢登入／註冊之後自動做朋友
  //    （後端 _auto_accept_invites 會憑 email 對返個邀請）
  useEffect(() => {
    const q = new URLSearchParams(window.location.search)
    const tok = q.get('friend')
    if (!tok) return
    try { localStorage.setItem('wander_friend_token', tok) } catch {}
    window.history.replaceState({}, '', window.location.pathname)
    setFriendToken(tok)
  }, [])

  // 掃咗 QR 之後登入 → 自動跳去朋友頁
  useEffect(() => {
    if (!user || !pendingAdd) return
    // ⚠️ users 自己用相機掃自己嘅 QR → 開 app 帶住 ?add=自己
    //    用戶要求：「唔可以加自己做朋友」
    if (isSelf(pendingAdd, user)) {
      toast(`⚠️ ${SELF_MSG} —— 呢個係你自己嘅 QR Code`)
      setPendingAdd(null)
      setTab('home')
      return
    }
    setTab('friends')
  }, [user, pendingAdd])

  // 深層連結 /join/CODE
  useEffect(() => {
    if (!user) return
    const m = window.location.pathname.match(/^\/join\/([A-Za-z0-9]{4,12})$/)
    if (!m) return
    api.joinTrip(m[1])
      .then(async (t) => {
        toast(`已加入「${t.name}」✓`)
        window.history.replaceState({}, '', '/')
        await refreshTrips()
        openTrip(t.id)
      })
      .catch(e => toast(e.message))
  }, [user, refreshTrips, openTrip])

  if (booting) {
    return (
      <div className="app"><Stars />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                      height: '100vh', gap: 10 }}>
          <Spinner /> <span className="dim">載入中…</span>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="app"><Stars />
        <PwaBar />
        <Login onLogin={async (u) => {
          setUser(u)
          if (u.theme) setTheme(u.theme)
          // ⚠️⚠️ 一定要喺**登入之後**檢查 admin ——
          //    原本呢個檢查只喺 mount 嗰陣做，而且未登入就 return，
          //    所以「登入入去」嘅用戶永遠見唔到後台入口。
          checkAdmin()
          await refreshTrips()
        }} />
        <Toast />
      </div>
    )
  }

  const inTrip = !!tripId && !showAdmin
  /**
   * ⚠️⚠️ `showAdmin` 要**包埋落 isHome 度**。
   *
   *    為咩：成個畫面嘅 render 都靠 `isHome` / `inTrip` 判斷，
   *    如果只係喺 admin 嗰段加 `!showAdmin`，其他區塊
   *    （HomeScreen / app header / nav）一樣會照 render →
   *    後台下面會出現主畫面，好亂。
   *
   *    ⚠️ 另一個做法係 `if (showAdmin) return <Admin/>` 提早 return ——
   *       但咁樣會跳過所有 hooks 之後嘅 effect，唔安全。
   */
  const isHome = tab === 'home' && !showAdmin
  // ⚠️ 主畫面係「手機 OS」感覺 —— 唔顯示底部 tab，
  //    因為 app icon 格本身就係導航。
  // ⚠️ 第二個元素係**像素圖示 id**（唔再係 emoji）——
  //    emoji 每部機唔同樣，做唔到像素風。
  const TABS = inTrip
    ? (isHome
        ? []
        : [['home', 'home', '主畫面'], ['calendar', 'calendar', '行程'],
           ['discover', 'discover', '整理'], ['money', 'money', '分帳'],
           ['shopping', 'shopping', '購物'], ['friends', 'friends', '朋友'],
           ['settings', 'settings', '設定']])
    // ⚠️ 用戶要求刪走 Trips app —— nav 唔應該再有「旅程」。
    //    但仍然要有路徑返主畫面（揀旅程唯一嘅地方）。
    : [['home', 'home', '主畫面'], ['friends', 'friends', '朋友'],
       ['settings', 'settings', '設定']]

  const dayCount = trip ? tripLength(trip) : 0

  // ⚠️ 開機動畫：只喺登入之後播一次（唔會每次切 tab 都彈）
  // ⚠️ `?noboot=1` —— 跳過開機動畫。
  //
  //   為咩要：開機動畫用 `requestAnimationFrame` + `performance.now()`，
  //   **headless 截圖追唔到**（virtual time 唔會推 rAF）→
  //   影出嚟永遠都係「000% 初始化」。
  //
  //   ⚠️ 亦都對真用戶有用：機慢嘅時候可以跳過。
  //      預設**唔會**跳（唔改變任何正常行為）。
  const NO_BOOT = typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).has('noboot')

  if (user && !booted && !NO_BOOT) {
    return <BootScreen onDone={() => setBooted(true)} />
  }

  // ⚠️⚠️ 新手教學：開機動畫之後、**第一次用**先出。
  //    判斷條件用 `user.onboarded`（後端欄位）而唔係 localStorage ——
  //    因為 localStorage 一換機／一清 cache 就冇，用戶會**再睇一次**教學。
  //    用後端欄位就跨機都準確。
  //
  //    ⚠️ 一定要 `booted` 之後先出 —— 唔可以同開機動畫同時，
  //       否則兩個全螢幕組件會疊埋一齊。
  // ⚠️⚠️ 兩個情況會出教學：
  //    ① 第一次：`user.onboarded === 0`（後端欄位，DB 預設 0，
  //       完成之後設 1 → 之後**永遠唔會再自動出**）
  //    ② 用戶喺設定頁撳「重新播放教學」→ replayTour = true
  if (user && booted && (!user.onboarded || replayTour)) {
    return (
      <div className="app">
        <Wallpaper value={user?.wallpaper} dim={user?.wallpaper_dim} />
      <Stars />
        <HomeScreen
          trips={trips} trip={trip} items={items} stops={stops} user={user}
          badges={{ shopping: shopBadge, friends: friendBadge }}
          onOpen={openApp} onPickTrip={openTrip}
          onNewTrip={() => { setTab('trips'); setNewTrip(true) }}
        />
        <Onboarding user={user} replay={replayTour} onDone={(name) => {
          setUser(prev => ({ ...prev, display_name: name, onboarded: true }))
          if (replayTour) {
            // 重看：淨係閂咗個 overlay，唔改 onboarded、唔跳去開新旅程
            setReplayTour(false)
            setTab('settings')
          } else {
            // 第一次：引導去開第一個旅程
            setTab('trips'); setNewTrip(true)
          }
        }} />
      </div>
    )
  }

  return (
    <div className="app">
      <Wallpaper value={user?.wallpaper} dim={user?.wallpaper_dim} />
      <Stars />
      <PwaBar />

      {showAdmin && isAdmin && (
        <Admin onBack={() => setShowAdmin(false)} />
      )}

      {!showAdmin && tab === 'trips' && (
        <>
          <div className="screen no-nav" style={{ paddingBottom: 4 }}>
            <button className="btn sm ghost" onClick={() => setTab('home')}>‹ 主畫面</button>
          </div>
          {/* ⚠️ 「當前旅程」橫幅 ——
              用戶撳「‹ 旅程」入嚟嗰陣，一定要睇到「你而家喺邊個旅程」，
              否則佢會以為已經退出咗（就係之前個 bug 嘅來源）。 */}
          {trip && (
            <div className="screen no-nav" style={{ paddingTop: 6, paddingBottom: 0 }}>
              <div className="card" style={{
                borderColor: 'var(--neon)', padding: 11,
              }}>
                <div className="row" style={{ alignItems: 'center', gap: 9 }}>
                  <PixelIcon name="sparkle" size={16} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="sub" style={{ fontSize: 10 }}>當前旅程</div>
                    <div style={{
                      fontWeight: 900, fontSize: 14.5,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{trip.name}</div>
                  </div>
                  <button className="btn sm primary"
                    onClick={() => setTab('home')}>返去 →</button>
                  <button className="btn sm ghost" onClick={exitTrip}
                    title="清空揀選（所有 app 會變返「未揀旅程」）">退出</button>
                </div>
              </div>
            </div>
          )}

          <Trips trips={trips} onOpen={openTrip} onRefresh={refreshTrips}
            currentId={tripId}
            autoNew={newTrip} onAutoNewDone={() => setNewTrip(false)} />
        </>
      )}

      {isHome && friendToken && (
        <div className="screen no-nav" style={{ paddingTop: 10, paddingBottom: 0 }}>
          <div className="card" style={{
            borderColor: 'var(--good)', background: 'transparent', padding: 12,
          }}>
            <div className="sub" style={{ fontSize: 11.5, lineHeight: 1.8 }}>
              🎉 你係經朋友邀請嚟嘅 —— 登入之後會<b>自動成為朋友</b>。
              <button className="btn sm ghost" style={{ marginLeft: 8, fontSize: 10 }}
                onClick={() => setFriendToken(null)}>知道</button>
            </div>
          </div>
        </div>
      )}

      {isHome && (
        <div style={{ minHeight: '100vh', paddingBottom: 20 }}>
          <HomeScreen
            trips={trips} trip={trip} items={items} stops={stops} user={user}
            badges={{ shopping: shopBadge, friends: friendBadge }}
            onOpen={openApp}
            onPickTrip={(id) => { setWantPick(false); openTrip(id) }}
            wantPick={wantPick}
            onPickDone={() => setWantPick(false)}
            onNewTrip={() => { setTab('trips'); setNewTrip(true) }}
          />
        </div>
      )}

      {/*
        ⚠️⚠️ 「先揀一個旅程」只可以擋**真正需要旅程**嘅 app。

        呢個係用戶報嘅 bug：
          「點解撳入去 setting 都係冇嘢嘅？」
        因為原本條件係 `tab !== 'trips' && !inTrip` ——
        連 ⚙️ 設定、👥 朋友 都會被擋 → 用戶撳「設定」
        見到「先揀一個旅程」，以為個 app 壞咗。

        設定同朋友**完全唔需要旅程**（改頭像、加朋友、改密碼
        全部都係帳號層面嘅事）→ 一定要排除。

        ⚠️ 用一個清單而唔係 `tab !== 'settings' && tab !== 'friends'` ——
           將來加新 app 嘅時候，一眼睇到邊啲需要旅程。
      */}
      {!isHome && !inTrip && TRIP_APPS.includes(tab) && (
        <div className="screen">
          <div className="h1">先揀一個旅程</div>
          <div className="sub" style={{ marginBottom: 14 }}>
            呢個功能要喺一個旅程入面先用得
          </div>
          {trips.map(t => (
            <button key={t.id} className="item tap" onClick={() => openTrip(t.id)}>
              <div className="ic">🗂</div>
              <div className="info">
                <h4>{t.name}</h4>
                <p>{t.start_date || '未定日期'} · {t.days || '?'} 日</p>
              </div>
            </button>
          ))}
          <button className="btn primary wide" style={{ marginTop: 14 }}
            onClick={() => setTab('trips')}>＋ 開新旅程</button>
        </div>
      )}

      {inTrip && !isHome && (
        <>
          {/* Trip header bar */}
          <div className="screen no-nav" style={{ paddingBottom: 8, paddingTop: 12 }}>
            <div className="row">
              <button className="btn sm ghost" onClick={backToTrips}>‹ 旅程</button>
              <div style={{ textAlign: 'right', minWidth: 0, flex: 1 }}>
                <div style={{
                  fontWeight: 900, fontSize: 15,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{trip?.name || '…'}</div>
                <div className="sub" style={{ fontSize: 10.5 }}>
                  {trip?.destination ? `${trip.destination} · ` : ''}
                  {dayCount} 日 · 👥 {trip?.members?.length || 0} · ✦ {items.length}
                </div>
              </div>
            </div>
          </div>

          {tab === 'shopping' && (
            <div className="screen">
              <div className="h1">🛒 購物清單</div>
              <div className="sub" style={{ marginBottom: 12 }}>
                分工買嘢，買完剔咗就唔會買雙份
              </div>
              <ShoppingList trip={trip} members={trip?.members?.map(m => m.display_name || m.email) || []}
                onRefresh={() => refreshTrip(tripId)}
                /* ⚠️⚠️ 私人／共用（用戶要求）
                       「shopping list 係自己嘅，就算人哋加落去呢個
                         planner 度呢，佢哋應該係睇唔到嘅。」 */
                onToggleVis={async (it) => {
                  const next = it.visibility === 'group' ? 'private' : 'group'
                  try {
                    await api.updateShopping(it.id, { visibility: next })
                    toast(next === 'group' ? '👥 全組都見到' : '🔒 只有你見到')
                    refreshTrip(tripId)
                  } catch (e) { toast(e.message) }
                }} />
              <div style={{ height: 40 }} />
            </div>
          )}
          {tab === 'discover' && (
            <Discover tripId={tripId} items={items}
              onRefresh={() => refreshTrip(tripId)} onOpenMap={() => setTab('map')}
              onEditItem={setDetail} />
          )}
          {tab === 'saved' && (
            /* ⚠️⚠️ 用戶要求：唔好叫 Zone，叫 **Saved**。
               入面係「你收藏咗嘅景點」清單 + 搜尋 + 地名 facet。
               （分區排行程已經搬入 Planner 嘅「編排」。） */
            <Saved items={items} onEditItem={setDetail}
              onBack={() => setTab('home')}
              /* ⚠️⚠️ public／private（用戶要求）—— 樂觀更新，即刻見到 */
              onToggleVis={async (it) => {
                const next = it.visibility === 'public' ? 'private' : 'public'
                setItems(prev => prev.map(x =>
                  x.id === it.id ? { ...x, visibility: next } : x))
                try {
                  await api.setItemVisibility(it.id, next)
                  toast(next === 'public' ? '🌍 全 group 都見到' : '🔒 只有你見到')
                } catch (e) {
                  // ⚠️ 失敗要**彈返轉頭**（唔好靜靜呃用戶）
                  setItems(prev => prev.map(x =>
                    x.id === it.id ? { ...x, visibility: it.visibility } : x))
                  toast(e.message)
                }
              }} />
          )}
          {tab === 'money' && (
            <div className="screen">
              <div className="h1">分帳</div>
              <div className="sub" style={{ marginBottom: 12 }}>
                有人墊支就記落嚟，最後自動計返最少轉帳次數
              </div>
              <Settlement trip={trip} user={user}
                onRefresh={() => refreshTrip(tripId)} />
              <div style={{ height: 40 }} />
            </div>
          )}
          {tab === 'calendar' && (
            <Calendar trip={trip} items={items} stops={stops}
              onRefresh={() => refreshTrip(tripId)} onEditItem={setDetail} />
          )}
          {tab === 'map' && (
            <MapView items={items} stops={stops}
              onRefresh={() => refreshTrip(tripId)} onEditItem={setDetail} />
          )}
          {tab === 'friends' && (
            <Friends trip={trip} me={user} onRefresh={() => refreshTrip(tripId)}
              prefill={pendingAdd} onPrefillDone={() => setPendingAdd(null)}
              onTripsChanged={refreshTrips} />
          )}
          {tab === 'settings' && (
            <Settings user={user} theme={theme} setTheme={setTheme}
              isAdmin={isAdmin} onOpenAdmin={() => setShowAdmin(true)}
              onUserUpdate={(u) => setUser(prev => ({ ...prev, ...u }))}
              onReplayTour={() => setReplayTour(true)}
              onRefresh={refreshMe}
              onLogout={() => { auth.clear(); setUser(null); setTripId(null) }} />
          )}
        </>
      )}

      {!inTrip && tab === 'friends' && (
        <Friends trip={null} me={user} onRefresh={() => {}}
          onTripsChanged={refreshTrips} />
      )}
      {/* ⚠️ 呢個分支一度漏咗 onUserUpdate ——
          改頭像／帳號名會靜靜咁失敗（叫 onUserUpdate?.() 但係 undefined） */}
      {!inTrip && tab === 'settings' && (
        <Settings user={user} theme={theme} setTheme={setTheme}
              isAdmin={isAdmin} onOpenAdmin={() => setShowAdmin(true)}
          onUserUpdate={(u) => setUser(prev => ({ ...prev, ...u }))}
          onReplayTour={() => setReplayTour(true)}
          onRefresh={refreshMe}
          onLogout={() => { auth.clear(); setUser(null); setTripId(null) }} />
      )}

      {detail && (
        <ItemDetail item={detail} trip={trip}
          onClose={() => setDetail(null)} onRefresh={() => refreshTrip(tripId)} />
      )}

      {!isHome && <nav className="nav" ref={navRef}>
        {TABS.map(([k, icon, label]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
            <span className="i"><PixelIcon name={icon} size={20} /></span>
            <span className="pix" style={{ fontSize: 6 }}>{label === '主畫面' ? 'HOME' : ''}</span>
            <span style={{ fontSize: 9.5 }}>{label}</span>
          </button>
        ))}
      </nav>}

      <Toast />
    </div>
  )
}
