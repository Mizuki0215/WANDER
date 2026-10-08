/**
 * 用戶報嘅 4 個問題 —— 回歸測試
 * =================================
 * ⚠️ 呢啲係**用戶親手報**嘅問題，一定要有測試守住，
 *    否則將來改嘢好易改返轉頭。
 */
import fs from 'node:fs'
import path from 'node:path'

const ROOT = new URL('../../', import.meta.url)
const SRC = new URL('web/src/', ROOT)
let pass = 0, fail = 0
const check = (l, c, e = '') => {
  console.log(`  ${c ? '✓' : '✗'} ${l}${e ? '  ' + e : ''}`)
  c ? pass++ : fail++
}
const read = (p) => fs.readFileSync(new URL(p, SRC), 'utf8')
/** ⚠️ 去註解 —— 我試過 match 到自己解釋 bug 嘅註解。 */
const code = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '')
  .split('\n').filter(l => !l.trim().startsWith('//')).join('\n')

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ① 旅程選擇要記住')
//   用戶：「揀咗旅程之後…整理 organize 呢啲…再出返去撳返旅程
//          出返去個 Home 度…佢就同我講未揀旅程」
// ══════════════════════════════════════════════════════════════
{
  const app = code(read('App.jsx'))

  // ⚠️ 一定要 persist（唔係只係 useState）
  check('有 localStorage 儲存旅程', /localStorage\.setItem\(TRIP_KEY/.test(app))
  check('有讀返上次旅程', /readSavedTrip\(\)/.test(app))

  // ⚠️⚠️ 核心 bug：backToTrips 唔可以清空 tripId
  // ⚠️ 只切到 backToTrips **自己**嘅結尾 ——
  //    之前切 700 字，食埋後面嘅 exitTrip（佢先至有 setTripId(null)）
  //    → 假失敗。
  const i = app.indexOf('const backToTrips')
  const j = app.indexOf('}, [refreshTrips])', i)
  const blk = app.slice(i, j + 20)
  check('backToTrips 唔會清空 tripId',
    !/setTripId\(null\)/.test(blk), '⚠️ 就係呢個清空造成個 bug')
  check('backToTrips 去旅程清單', /setTab\('trips'\)/.test(blk))

  // ⚠️ 但要有真正「退出」嘅方法
  check('有獨立嘅 exitTrip()', /const exitTrip/.test(app))
  check('exitTrip 先至清空', /const exitTrip[\s\S]{0,400}setTripId\(null\)/.test(app))

  // ⚠️ 只有一個旅程就自動揀
  check('refreshTrips 會還原／自動揀',
    /setTripId\(prev =>/.test(app) && /list\.length === 1/.test(app))

  // 清單要標示「當前」
  const trips = code(read('components/Trips.jsx'))
  check('旅程清單標示「當前」', /currentId === t\.id/.test(trips))
  check('trips 頁有當前旅程橫幅', /當前旅程/.test(app))
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ② 密碼欄打字唔可以斷')
//   用戶：「打 Password 嘅時候…我打緊嘅同時我要點擊佢
//          先至可以打下一個」= 每打一個字就失焦
//   原因：`const Sec = (...) => ...` 寫喺 render 入面
//        → 每次 render 都係新元件類型 → unmount/remount → 失焦
// ══════════════════════════════════════════════════════════════
{
  const sm = code(read('components/SettingsMore.jsx'))
  check('Sec 定義喺模組層（唔喺 render 入面）',
    /^function Sec\(/m.test(sm), '⚠️ 呢個就係失焦嘅原因')
  check('render 入面冇 const Sec =', !/^\s+const Sec\s*=/m.test(sm))
  check('Sec 收到 open / onToggle', /function Sec\(\{\s*k,\s*open,\s*onToggle/.test(sm))
  check('所有 <Sec> 都有傳 open',
    (sm.match(/<Sec open=\{open\}/g) || []).length >= 5)

  // ⚠️ 全 codebase 掃：唔可以再有 render 入面定義嘅元件
  const dir = new URL('web/src/components/', ROOT)
  const bad = []
  for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.jsx'))) {
    const s = code(fs.readFileSync(new URL(f, dir), 'utf8'))
    // 大寫開頭嘅 const 箭頭函數 = 元件
    for (const m of s.matchAll(/^\s{2,}const ([A-Z]\w*)\s*=\s*\([^)]*\)\s*=>\s*[\(<]/gm)) {
      bad.push(`${f}: ${m[1]}`)
    }
  }
  check('冇任何「render 入面定義元件」', bad.length === 0,
    bad.length ? bad.join(', ') : '')
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ③ App icon 跟主題色調')
//   用戶：「我哋有唔同嘅主題啦，所以 Apps 嘅 icon 應該都要
//          跟返類似嗰個對應嘅主題，即係色調可能要改少少」
// ══════════════════════════════════════════════════════════════
{
  const home = code(read('components/HomeScreen.jsx'))
  const css = read('styles.css')

  check('app icon 用 data-app（唔係 inline 死色）',
    /data-app=\{app\.id\}/.test(home))
  check('冇再 inline background: app.grad',
    !/background:\s*app\.grad/.test(home))

  // ⚠️⚠️ 每個主題都要有色位。
  //    ⚠️ 一定要用 matchAll 而唔係 match ——
  //       同一個主題喺檔案入面有**兩段**（原本嘅 + 我加嘅色位），
  //       `match` 只會攞第一段（冇 --app-a）→ 假失敗。
  const blocksFor = (re) => [...css.matchAll(re)].map(m => m[1])
  const themes = ['tech', 'minimal', 'khaki', 'macaron', 'wafu']
  for (const t of themes) {
    const blocks = blocksFor(
      new RegExp(`\\[data-theme='${t}'\\]\\s*\\{([^}]*)\\}`, 'gs'))
    check(`[data-theme=${t}] 有 app 色位`,
      blocks.some(b => b.includes('--app-a')), `${blocks.length} 段`)
  }
  // :root（galaxy）
  const roots = blocksFor(/:root\s*\{([^}]*)\}/gs)
  check(':root（galaxy）有預設 app 色位',
    roots.some(b => b.includes('--app-a')), `${roots.length} 段`)

  // 7 個色位 a-g + 中性 n
  for (const k of ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'n']) {
    check(`有 --app-${k}`, css.includes(`--app-${k}:`))
  }
  // 每個 app 都要揀到色位
  // ⚠️ 用戶要求：Trips 刪走、Zones 改名做 saved
  for (const id of ['calendar', 'discover', 'money', 'shopping',
                    'saved', 'map', 'friends', 'settings']) {
    check(`app-ico[data-app=${id}] 有規則`,
      css.includes(`[data-app='${id}']`))
  }
  check('用 color-mix 由單色推漸變', css.includes('color-mix'))
  // ⚠️ 單色／淺底主題要有 filter 調整圖示
  check('tech 有灰階 filter', /data-theme='tech'[\s\S]{0,200}grayscale/.test(css))
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ④ Shopping list 相框')
//   用戶：「我想有一個框架…upload 相之後有一個框架咁
//          然後會 show 個相出嚟…一碌落去你就知道嗰個商品
//          係有乜嘢圖案係點嘅樣，而唔係剩係得個名」
// ══════════════════════════════════════════════════════════════
{
  const shop = code(read('components/ShoppingList.jsx'))
  const css = read('styles.css')

  // ⚠️⚠️ 冇相都要出框（提示影相 + 一致左邊距）
  check('冇相都出框（empty）', /item\.image \? '' : 'empty'/.test(shop))
  check('空框有提示圖示', /thumb-ph/.test(shop))
  check('空框撳得開去加相', /else onDetail\?\.\(\)/.test(shop))

  // ⚠️ 相框要比以前大
  const m = css.match(/\.thumb\s*\{([^}]*)\}/)
  check('搵到 .thumb 規則', !!m)
  if (m) {
    check('.thumb 用 --r-sm（統一圓角）', m[1].includes('var(--r-sm)'))
    check('.thumb 有雙層框（inset box-shadow）', m[1].includes('inset'))
    const size = m[1].match(/clamp\((\d+)px,\s*[\d.]+vw,\s*(\d+)px\)/)
    check('.thumb 夠大（≥ 60px）', size && Number(size[1]) >= 60,
      size ? `${size[1]}-${size[2]}px` : '搵唔到大細')
  }

  // 詳情頁大相框
  check('有 .frame-lg 大相框', /\.frame-lg\s*\{/.test(css))
  check('編輯表有大相框', /frame-lg/.test(shop))
  check('大框用 contain（唔裁走）',
    /\.frame-lg img\s*\{[\s\S]{0,200}object-fit:\s*contain/.test(css))

  // ⚠️⚠️ ::after 相撞 bug（一個元素得一個 ::after）
  check('完成 ✓ 用 ::before（唔同 ⤢ 撞）',
    /\.thumb\.done::before/.test(css))
  // ⚠️ 要去註解先檢查 —— 我解釋 bug 嘅註解入面有寫住呢個字串
  const cssCode = code(css)
  check('唔再用 .thumb.done::after', !/\.thumb\.done::after/.test(cssCode))
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑤ 新增旅程時就可以加多個城市')
//   用戶：「新增旅程嘅時候…應該有一個 button 俾你去加城市，
//          而唔係當你去編輯嘅時候先至可以加新增多於一個城市，
//          而係你一開行程就已經有得加多於一個城市」
// ══════════════════════════════════════════════════════════════
{
  const trips = code(read('components/Trips.jsx'))

  // ⚠️ 要有城市清單（唔係得一個 destination 欄）
  check('有 cities 清單 state', /const \[cities, setCities\] = useState\(\[\]\)/.test(trips))
  check('有加城市嘅 function', /function addCityRow/.test(trips))
  check('有移除城市', /function removeCityRow/.test(trips))

  // ⚠️⚠️ 核心：建立旅程嘅時候就要寫入城市
  check('submit 建立後寫入城市', /api\.setStops\(t\.id, stops\)/.test(trips))
  // ⚠️ 但唔可以因為城市失敗就當建立失敗
  check('城市寫入失敗唔會當建立失敗',
    /旅程已建立，但城市未寫入/.test(trips))

  // ⚠️ 編輯時要載入現有城市（否則一儲存就清走晒）
  check('編輯時載入現有城市', /api\.stops\(t\.id\)/.test(trips))
  check('用 setCities 載入', /setCities\(\(r\.stops \|\| \[\]\)\.map/.test(trips))

  // ⚠️ 目的地同清單唔可以唔一致
  check('目的地用清單第一個', /stops\[0\]\?\.city \|\| form\.destination/.test(trips))
  // ⚠️ 總日數要用清單
  check('日數用清單總和', /stops\.reduce\(\(a, b\) => a \+ b\.days, 0\)/.test(trips))

  // ⚠️ 要有「加」掣同 CityPicker
  check('UI 有「＋ 加」掣', /＋ 加\s*<\/button>/.test(trips))
  check('UI 用 CityPicker', /<CityPicker[\s\S]{0,200}addCityRow/.test(trips))
  check('第一個城市順便填目的地', /if \(!form\.destination\) setForm/.test(trips))

  // ⚠️ 重複城市唔可以加兩次
  check('擋重複城市', /cities\.some\(x => x\.city === c\)/.test(trips))
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑥ 登入「已過期」誤報（401 唔一定係過期）')
//   用戶：「我登入嘅時候佢同我講登入已過期重新登入…
//          正常都係用 20 秒之內去登入，但佢同我講話過期」
//   ⚠️ 原因：`POST /api/auth/password` 用 401 表示「密碼唔啱」，
//      而前端**所有** 401 都當「session 過期」→ 清 token + 登出。
// ══════════════════════════════════════════════════════════════
{
  const api = code(read('lib/api.js'))
  // ⚠️⚠️ 核心：只有「有帶 token」嘅 401 才當過期
  check('只有帶 token 嘅 401 當過期', /res\.status === 401 && hadToken/.test(api))
  check('有記錄有冇帶 token', /const hadToken = !!auth\.token/.test(api))
  check('冇 token 嘅 401 照拋後端訊息',
    !/if \(res\.status === 401\) \{\s*auth\.clear\(\)/.test(api))

  // 後端要分開「未設密碼」
  const srv = fs.readFileSync(new URL('server/app/main.py', ROOT), 'utf8')
  check('後端有「未設密碼」', /raise HTTPException\(401, "未設密碼"\)/.test(srv))
  check('後端仍然有「Email 或密碼唔啱」', /Email 或密碼唔啱/.test(srv))
  // ⚠️ 「未設密碼」要喺「Email 或密碼唔啱」**之前**判斷
  const iNp = srv.indexOf('"未設密碼"')
  const iBad = srv.indexOf('raise HTTPException(401, "Email 或密碼唔啱")')
  check('「未設密碼」判斷喺前面', iNp > 0 && iBad > 0 && iNp < iBad)
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑦ 開發版後台')
//   用戶：「整一個叫開發版，係放我自己睇啲人用呢個 App 嘅數據」
// ══════════════════════════════════════════════════════════════
{
  const admin = code(read('components/Admin.jsx'))
  const app = code(read('App.jsx'))
  const api = code(read('lib/api.js'))

  check('有 Admin.jsx', admin.length > 1000)
  check('Admin 有總覽 API', /api\.adminOverview/.test(admin))
  check('api 有 adminMe', /adminMe:/.test(api))
  check('api 有 adminOverview', /adminOverview:/.test(api))
  check('api 有 track', /track:/.test(api))

  // ⚠️ App 要問權限 + 記錄事件
  check('App 問 admin 權限', /api\.adminMe\(\)/.test(app))
  check('App 記 login 事件', /api\.track\('login'\)/.test(app))
  check('App 記 app_open 事件', /api\.track\('app_open', id\)/.test(app))

  // ⚠️ 只有 admin 見到
  check('後台入口只喺 isAdmin 顯示', /showAdmin && isAdmin &&/.test(app))
  check('Settings 傳 isAdmin', /isAdmin=\{isAdmin\}/.test(app))

  // ⚠️⚠️ 為咩 isHome/inTrip 要收埋（否則後台下面會有主畫面）
  check('isHome 收埋', /tab === 'home' && !showAdmin/.test(app))
  check('inTrip 收埋', /!!tripId && !showAdmin/.test(app))

  // ⚠️ 唔可以喺 render 入面定義元件（會令 input 失焦）
  check('Sec/Grid/Bar 都喺模組層',
    /^function Sec\(/m.test(admin) && /^function Grid\(/m.test(admin)
    && /^function Bar\(/m.test(admin))
  check('冇 render 入面定義元件',
    !/^\s{2,}const [A-Z]\w*\s*=\s*\([^)]*\)\s*=>\s*[\(<]/m.test(admin))
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑧ 未設定 SMTP → 邀請碼註冊')
//   用戶：「未設定 SMTP 你係諗住點搞？」
//   ⚠️ 答：冇 SMTP 寄唔到驗證碼 → 用邀請碼（朋友之間更實在）
// ══════════════════════════════════════════════════════════════
{
  const login = code(read('components/Login.jsx'))
  const admin = code(read('components/Admin.jsx'))
  const api = code(read('lib/api.js'))

  // ⚠️ 前端要問模式（唔可以假設）
  check('Login 問註冊模式', /api\.signupMode\(\)/.test(login))
  // ⚠️⚠️ 用戶要求：「only email password no verify」
  //    → open 模式唔出邀請碼欄（唔好煩用戶）
  //    ⚠️ 但後端照樣接受邀請碼（安全網，見 test_mail_setup）
  check('只有 need_invite 先出邀請碼欄',
    /page === 'register' && signup\?\.need_invite && \(/.test(login))
  check('⚠️ 唔可以喺 open 模式提「會寄確認信」',
    /signup\?\.mail_configured/.test(login))
  check('register 傳邀請碼', /api\.register\(em, pw, invite\)/.test(login))
  check('邀請碼自動轉大寫', /toUpperCase\(\)/.test(login))
  check('api.register 收第三個參數', /register: \(email, password, inviteCode\)/.test(api))
  check('api 傳 invite_code', /invite_code: inviteCode/.test(api))

  // 後台要產生到邀請碼
  check('Admin 有邀請碼產生器', /function Invites\(\)/.test(admin))
  check('Admin 用 makeInvites', /api\.makeInvites/.test(admin))
  check('Admin 列出邀請碼', /api\.adminInvites/.test(admin))
  check('啱啱產生嘅碼大字顯示', /fontSize: 22/.test(admin))
  check('可以撳一下複製', /navigator\.clipboard/.test(admin))
  check('Invites 喺模組層', /^function Invites\(/m.test(admin))

  // ⚠️ 指引文件
  const doc = fs.readFileSync(new URL('docs/smtp/README.md', ROOT), 'utf8')
  check('有 SMTP 指引', doc.length > 1500)
  check('指引有 Gmail App Password', /App Password|apppasswords/.test(doc))
  check('指引有 Resend', /Resend|resend\.com/.test(doc))
  check('指引有 Brevo', /Brevo|brevo/.test(doc))
  check('指引講邀請碼', /邀請碼/.test(doc))
  check('指引老實講安全洞', /安全洞|危險/.test(doc))
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑨ 密碼眼仔（顯示／隱藏）')
//   用戶：「設定密碼嗰個應該係隔離正常係會有一個眼仔，
//          俾你去睇個密碼係咪正確？撳一下就會 show 密碼，
//          再撳多一下就會唔 show。」
// ══════════════════════════════════════════════════════════════
{
  const pw = code(read('components/PasswordInput.jsx'))
  const login = code(read('components/Login.jsx'))
  const sm = code(read('components/SettingsMore.jsx'))
  const icons = read('lib/pixelicons.js')
  const css = read('styles.css')

  // ① 元件本身
  check('有 PasswordInput.jsx', pw.length > 500)
  check('有兩個狀態（show）', /const \[show, setShow\]/.test(pw))
  check('撳一下切換', /setShow\(s => !s\)/.test(pw))
  check('type 跟 show 轉', /type=\{show \? 'text' : 'password'\}/.test(pw))
  check('有眼仔圖示', /name=\{show \? 'eyeoff' : 'eye'\}/.test(pw))

  // ⚠️⚠️ 一定要 type="button" —— 喺 <form> 入面撳眼仔會提交表單
  check('眼仔係 type="button"（唔會誤提交）', /type="button"/.test(pw))
  check('有 aria-label（讀屏）', /aria-label=/.test(pw))
  check('有 aria-pressed', /aria-pressed=/.test(pw))

  // ⚠️ 密碼唔可以俾輸入法自動大寫
  check('關閉自動大寫', /autoCapitalize="off"/.test(pw))
  check('關閉自動修正', /autoCorrect="off"/.test(pw))

  // ⚠️⚠️ 一定要喺模組層（喺 render 入面定義會令每次打字失焦）
  check('PasswordInput 喺模組層', /^export default function PasswordInput\(/m.test(pw))

  // ② 眼仔圖示
  check('有 eye 圖示', /eye: P\(/.test(icons))
  check('有 eyeoff 圖示', /eyeoff: P\(/.test(icons))

  // ③ 所有密碼欄都要用佢（唔可以漏）
  check('Login 全部用 PasswordInput', (login.match(/<PasswordInput/g) || []).length === 3,
    `${(login.match(/<PasswordInput/g) || []).length}/3`)
  check('Login 冇淨低裸 password input', !/type="password"/.test(login))
  check('SettingsMore 全部用 PasswordInput',
    (sm.match(/<PasswordInput/g) || []).length === 3,
    `${(sm.match(/<PasswordInput/g) || []).length}/3`)
  check('SettingsMore 冇淨低裸 password input', !/type="password"/.test(sm))

  // ④ CSS
  check('有 .pw-wrap（relative）', /\.pw-wrap\s*\{[\s\S]{0,200}position:\s*relative/.test(css))
  check('有 .pw-eye 絕對定位', /\.pw-eye\s*\{[\s\S]{0,200}position:\s*absolute/.test(css))
  check('輸入框右邊留位畀眼仔', /\.pw-input\s*\{[\s\S]{0,200}padding-right/.test(css))
  check('眼仔夠大（≥36px，手指撳得中）',
    /\.pw-eye\s*\{[\s\S]{0,300}width:\s*(\d+)px/.test(css) &&
    Number(css.match(/\.pw-eye\s*\{[\s\S]{0,300}width:\s*(\d+)px/)[1]) >= 36)

  // ⚠️ 全 codebase 掃：唔可以有裸 password input
  const dir = new URL('web/src/', ROOT)
  const bare = []
  for (const f of fs.readdirSync(new URL('components/', dir))) {
    if (!f.endsWith('.jsx') || f === 'PasswordInput.jsx') continue
    const s2 = code(fs.readFileSync(new URL('components/' + f, dir), 'utf8'))
    if (/type="password"/.test(s2)) bare.push(f)
  }
  check('全 codebase 冇裸 password input', bare.length === 0, bare.join(', '))
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑩ Planner 合併 + 三個 view 同步時間')
//   用戶：「三個 function 都要同步更新活動時間」
//         「擺活動上去 + 拖去唔同時間 —— 兩個 combine 埋一個」
// ══════════════════════════════════════════════════════════════
{
  const cal = code(read('components/Calendar.jsx'))
  const grid = code(read('components/DayGrid.jsx'))

  // ⚠️⚠️ 核心 bug：day mode 只寫 day_index/sort_order，**冇寫時間** →
  //    喺嗰度拖完，去時段格睇 → 時間冇變。
  check('day mode 已刪走（HTML5 DnD、手機用唔到、唔寫時間）',
    !/mode === 'day'/.test(cal))
  check('冇咗「逐日編排」掣', !/逐日編排/.test(cal))
  // ⚠️ 要數**唔同嘅 mode 值**，唔係呼叫次數
  //    （`setMode('grid')` 出現 3 次係正常 —— 有幾個入口指去同一頁）
  const modes = new Set([...cal.matchAll(/setMode\('(\w+)'/g)].map(m => m[1]))
  check('只剩 2 個 mode（總覽 + 編排）', modes.size === 2,
    [...modes].join(' / '))
  check('有總覽', modes.has('overview'))
  check('有編排', modes.has('grid'))

  // ⚠️ 唯一寫時間嘅地方：DayGrid 嘅 place()
  check('DayGrid 寫 start_time', /parsed: \{ start_time: fromMinutes\(minutes\)/.test(grid))
  check('DayGrid 寫 duration', /duration \}/.test(grid))

  // ⚠️⚠️ 合併：托盤拖入格
  check('有底部托盤', /未排入行程/.test(grid))
  check('托盤用 Pointer Events（手機都用得）',
    /onPointerDown=\{e => startTrayDrag/.test(grid))
  check('唔用 HTML5 DnD（draggable）', !/draggable/.test(grid))
  check('托盤有 touchAction: none（唔會當捲動）', /touchAction: 'none'/.test(grid))
  check('拖入格有鬼影預覽', /tray\?\.minutes != null/.test(grid))
  check('鬼影 pointerEvents none（唔會擋 move）',
    /pointerEvents: 'none', zIndex: 8/.test(grid))
  check('冇拖入格就唔做嘢', /if \(d\.minutes == null\) return/.test(grid))

  // ⚠️ 計時間嘅邏輯要共用（唔可以兩處各寫一份）
  check('用 lib/dates 嘅 toMinutes/fromMinutes',
    /from '..\/lib\/dates'/.test(grid) && /toMinutes/.test(grid))
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑪ 行程選擇只喺主頁面')
//   用戶：「只可以喺主頁面度揀…唔需要令我開一個頁面就係話你要揀一個行程」
// ══════════════════════════════════════════════════════════════
{
  const app = code(read('App.jsx'))
  const home = code(read('components/HomeScreen.jsx'))

  // ⚠️⚠️ 未揀旅程撳 app → 留喺主頁 + 開選擇器（唔跳頁）
  check('冇旅程唔跳去 trips', !/toast\('先揀一個旅程'\)\s*\n\s*setTab\('trips'\)/.test(app))
  check('改為留喺主頁', /setTab\('home'\)\s*\n\s*setWantPick\(true\)/.test(app))
  check('有 wantPick state', /const \[wantPick, setWantPick\]/.test(app))
  check('HomeScreen 收 wantPick', /wantPick = false, onPickDone/.test(home))
  check('wantPick 自動打開選擇器', /if \(wantPick\) setPicking\(true\)/.test(home))

  // ⚠️ 主頁面一定要有「轉旅程」入口（否則改唔到旅程）
  check('主頁面有「轉旅程」', /轉旅程/.test(home))
  check('主頁面有「未揀旅程」提示', /未揀旅程/.test(home))
  check('主頁面可以開新旅程', /開新旅程/.test(home))
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑫ 重看教學要跳過「改名」')
//   用戶：「第一次創建 Account 嘅時候你先至叫你去改名。
//          所以之後喺 setting 嗰度再想睇多次示範教學，
//          係唔需要再 show 叫你去打自己個名嗰一版。
//          淨係教佢啲 Apps 點用就 OK。」
// ══════════════════════════════════════════════════════════════
{
  const onb = code(read('components/Onboarding.jsx'))
  const app = code(read('App.jsx'))

  // ① 要有 replay prop
  check('Onboarding 收 replay prop', /onDone, replay = false \}/.test(onb))
  check('App 傳 replay={replayTour}', /replay=\{replayTour\}/.test(app))

  // ② ⚠️⚠️ 核心：用「明確步驟清單」而唔係索引算術
  check('用 steps 清單', /const steps = useMemo\(/.test(onb))
  check('replay 時唔加 welcome', /if \(!replay\) out\.push\('welcome'\)/.test(onb))
  check('replay 時唔加 name', /if \(!replay\) out\.push\('name'\)/.test(onb))
  check('一定有 done', /out\.push\('done'\)/.test(onb))
  check('tour 一定加', /TOUR\.forEach\(\(_, i\) => out\.push\(`tour:\$\{i\}`\)\)/.test(onb))

  // ③ 唔應該再有舊嘅索引算術
  check('冇 NAME_STEP 算術', !/const NAME_STEP = TOUR\.length/.test(onb))
  check('冇 DONE_STEP 算術', !/const DONE_STEP = TOUR\.length/.test(onb))

  // ④ 用 kind 判斷（唔再用 step === 數字）
  for (const [k, label] of [['isWelcome', '歡迎'], ['isTour', '導覽'],
                            ['isName', '改名'], ['isDone', '完成']]) {
    check(`有 ${k}（${label}）判斷`, new RegExp(`const ${k} =`).test(onb))
  }
  check('render 用 isName 而唔係 step === NAME_STEP',
    /\{isName && \(/.test(onb) && !/step === NAME_STEP/.test(onb))

  // ⑤ ⚠️⚠️ replay 完成時**唔可以**再叫 finishOnboard
  //     （會用輸入框嘅舊值蓋返用戶喺設定改過嘅名）
  check('replay 完成唔寫名', /if \(replay\) \{ onDone\?\.\(name\.trim\(\)\); return \}/.test(onb))

  // ⑥ 跳過掣文案要跟
  check('replay 時跳過掣寫「跳過教學」', /replay \? '跳過教學' : '跳過教學，直接改名'/.test(onb))

  // ⑦ 模擬步驟清單
  const TOUR = new Array(9).fill(0)
  const stepsFor = (replay) => {
    const out = []
    if (!replay) out.push('welcome')
    TOUR.forEach((_, i) => out.push(`tour:${i}`))
    if (!replay) out.push('name')
    out.push('done')
    return out
  }
  const first = stepsFor(false), again = stepsFor(true)
  check('第一次有 welcome + name', first.includes('welcome') && first.includes('name'))
  check('重看冇 welcome', !again.includes('welcome'))
  check('重看冇 name ← 用戶要求', !again.includes('name'))
  check('重看仲有全部 app 導覽', again.filter(x => x.startsWith('tour')).length === 9)
  check('重看冇少到 tour', again.filter(x => x.startsWith('tour')).length ===
    first.filter(x => x.startsWith('tour')).length)
}



// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑬ 邀請碼：窄欄 + 「驗證」掣')
//   用戶：「你真係要搞邀請碼個位，應該係一欄 —— 寫邀請碼
//          嗰欄應該係冇咁闊，然後旁邊落返一個掣叫做『驗證』。」
// ══════════════════════════════════════════════════════════════
{
  const login = code(read('components/Login.jsx'))
  const api = code(read('lib/api.js'))
  // ⚠️ 去 CSS 註解 —— 我喺註解入面解釋「為咩唔用 flex:1」，
  //    唔去嘅話會 match 到自己嘅解釋（今日第 N 次中招）
  const css = read('styles.css').replace(/\/\*[\s\S]*?\*\//g, '')
  const srv = fs.readFileSync(new URL('server/app/main.py', ROOT), 'utf8')

  // ① 窄欄 + 掣
  check('有 .invite-row（flex）', /\.invite-row\s*\{[\s\S]{0,120}display:\s*flex/.test(css))
  check('輸入框窄（fixed width）', /\.invite-input\s*\{[\s\S]{0,300}width:\s*\d+px/.test(css))
  const w = (css.match(/\.invite-input\s*\{[\s\S]{0,300}width:\s*(\d+)px/) || [])[1]
  check('闊度 ≤ 160px（唔係成行）', w && Number(w) <= 160, w ? `${w}px` : '搵唔到')
  // ⚠️ 要**準確抽 .invite-input 嘅 block** ——
  //    用 `[\s\S]{0,300}` 會跨越到下一個 rule（.invite-btn 有 flex:1）
  const blockOf = (sel) => {
    const i = css.indexOf(sel + ' {')
    if (i < 0) return ''
    const j = css.indexOf('}', i)
    return css.slice(i, j)
  }
  const inBlk = blockOf('.invite-input')
  check('⚠️ 唔用 flex:1（會撐到滿）', !/flex:\s*1\b/.test(inBlk), inBlk ? '' : '搵唔到 block')
  check('用 flex: 0 0 auto', /flex:\s*0\s+0\s+auto/.test(inBlk))
  check('掣食剩低嘅位（大手位）', /\.invite-btn\s*\{[\s\S]{0,120}flex:\s*1/.test(css))
  check('窄機有 media query 再收窄', /@media \(max-width: 360px\)[\s\S]{0,160}invite-input/.test(css))

  // ② 有「驗證」掣（type=button！唔可以誤提交表單）
  check('有「驗證」掣', /驗證<\/button>/.test(login) || /'驗證'/.test(login))
  check('⚠️ 驗證掣係 type="button"', /type="button" className="btn invite-btn"/.test(login))
  check('有 checkInvite()', /async function checkInvite\(\)/.test(login))
  check('api 有 checkInvite', /checkInvite:/.test(api))
  check('冇輸入就撳唔到', /disabled=\{busy \|\| inviteBusy \|\| !invite\.trim\(\)\}/.test(login))

  // ③ ⚠️ 改咗碼要重新驗（唔可以沿用舊結果）
  check('改碼重設驗證結果', /setInviteChk\(null\)\s*\/\/ ⚠️ 改咗就要重新驗/.test(login))
  // ④ Enter 都可以驗
  check('Enter 可以驗證', /e\.key === 'Enter'.{0,40}checkInvite\(\)/s.test(login))
  // ⑤ 有成功／失敗提示
  check('顯示「邀請碼有效」', /邀請碼有效/.test(login))
  check('顯示失敗原因', /inviteChk\.reason/.test(login))
  // ⑥ ⚠️ 邀請碼要喺 email 之前（先驗證後填）
  // ⚠️ 用戶要求次序：email → 驗證 → password → password again
  check('邀請碼喺 email 之後',
    login.indexOf('invite-row') > login.indexOf('type="email"'))

  // ⑦ 後端 endpoint
  check('後端有 check-invite', /@app\.post\("\/api\/auth\/check-invite"\)/.test(srv))
  check('⚠️ 公開（唔要登入）', (() => {
    const i = srv.indexOf('def check_invite(')
    return i > 0 && !srv.slice(i, i + 900).includes('Depends(current_user)')
  })())
  check('檢查用咗', /already|已經用咗/.test(srv))
  check('檢查過期', /已經過期/.test(srv))
  check('⚠️ 唔洩漏「邊個產生」', (() => {
    const i = srv.indexOf('def check_invite(')
    const blk = srv.slice(i, i + 1600)
    return !/created_by/.test(blk)
  })())
  // ⑧ route 次序
  const stripped = srv.split('\n').filter(l => !l.trim().startsWith('#')).join('\n')
  check('check-invite 喺 SPA catch-all 之前',
    stripped.indexOf('@app.post("/api/auth/check-invite")') <
    stripped.indexOf('@app.get("/{full_path:path}")'))
}




// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑭ Zones → Saved、刪 Trips')
//   用戶：「Trips（同主頁重疊 70%）delete」
//         「Zones 嘅 function 你唔好寫 Zone，寫 Saved。
//          入面有一個 list 寫係你 saved 嘅景，上面有一個 bar
//          for searching…如果有 saved 博多景，因為本身 address
//          有，佢會 show 福岡畀你 tick。」
// ══════════════════════════════════════════════════════════════
{
  const home = code(read('components/HomeScreen.jsx'))
  const app = code(read('App.jsx'))
  const saved = code(read('components/Saved.jsx'))
  const css = read('styles.css')

  // ① 刪 Trips
  check('主頁面冇 Trips app', !/id: 'trips'/.test(home))
  check('nav 冇「旅程」tab', !/'trips', 'trips', '旅程'/.test(app))
  check('冇咗 ZonePlanner.jsx',
    !fs.existsSync(new URL('web/src/components/ZonePlanner.jsx', ROOT)))

  // ② Zones → Saved
  check('主頁面有 Saved app', /id: 'saved'/.test(home))
  check('Saved 標籤正確', /label: 'Saved'/.test(home))
  check('TRIP_APPS 用 saved', /'saved'/.test(app) && !/'zones'/.test(app))
  check('App render 用 <Saved>', /<Saved items=\{items\}/.test(app))
  check('主題色位改咗 saved', /data-app='saved'/.test(css))

  // ③ Saved 要有搜尋
  check('有搜尋 state', saved.includes('const [q, setQ] = useState('))
  check('有搜尋輸入框', /className="saved-input"/.test(saved))
  check('有清除掣', /saved-clear/.test(saved))
  check('CSS 有 .saved-search', /\.saved-search\s*\{/.test(css))

  // ④ ⚠️⚠️ 核心：地名 facet 由地址抽出
  check('有 facet state', /const \[picked, setPicked\]/.test(saved))
  check('由 location_path 抽 facet', /it\.location_path \|\| \[\]/.test(saved))
  check('facet 有計數', /count\.set\(n, \(count\.get\(n\) \|\| 0\) \+ 1\)/.test(saved))
  check('facet 按次數排序', /sort\(\(a, b\) => b\.n - a\.n/.test(saved))
  check('可以 tick', /function toggleFacet/.test(saved))
  check('用 Set 去重（同一景點唔加兩次）',
    /const names = new Set\(\)/.test(saved))
  check('篩選要中晒所有 tick 咗嘅', /picked\.every\(p =>/.test(saved))

  // ⑤ 有清單
  check('有清單 render', /filtered\.map\(it =>/.test(saved))
  check('顯示篩選結果數', /filtered\.length\} \/ \{items\.length/.test(saved))
  check('有「仲未有收藏」提示', /仲未有收藏/.test(saved))

  // ⑥ ⚠️ 搜尋要同時中名／地址／備註／分類
  for (const f of ['it.name', 'it.note', 'it.category', 'it.district']) {
    check(`搜尋包括 ${f}`, saved.includes(f))
  }
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑮ 註冊表單次序：email → 驗證 → password ×2')
//   用戶：「UI -> 1. email 2.『驗證』 3. password 4 password again」
// ══════════════════════════════════════════════════════════════
{
  const login = code(read('components/Login.jsx'))
  const iEm = login.indexOf('type="email"')
  const iInv = login.indexOf('invite-row')
  const iPw = login.indexOf('<PasswordInput', iInv)
  const iPw2 = login.indexOf('<PasswordInput', iPw + 10)
  check('email 最先', iEm > 0)
  check('驗證喺 email 之後', iInv > iEm, `${iEm} → ${iInv}`)
  check('password 喺驗證之後', iPw > iInv, `${iInv} → ${iPw}`)
  check('密碼確認喺最後', iPw2 > iPw)
  check('次序完全正確', iEm < iInv && iInv < iPw && iPw < iPw2)
}

// ══════════════════════════════════════════════════════════════
console.log('\n▸ ⑯ 真 email（歡迎信 + 測試掣）')
//   用戶：「我係真係想我 email 收到有呢一封嘅 email。」
// ══════════════════════════════════════════════════════════════
{
  const m = fs.readFileSync(new URL('server/app/mailer.py', ROOT), 'utf8')
  const srv = fs.readFileSync(new URL('server/app/main.py', ROOT), 'utf8')
  const admin = code(read('components/Admin.jsx'))
  const api = code(read('lib/api.js'))

  check('有 send_welcome_email', /def send_welcome_email\(/.test(m))
  check('有 send_test_email', /def send_test_email\(/.test(m))
  check('註冊會寄歡迎信', /send_welcome_email\(email/.test(srv))
  check('⚠️ 寄信喺 DB commit 之後（唔霸住 connection）',
    srv.indexOf('send_welcome_email') > srv.indexOf('with db.connect()', srv.indexOf('def register(')))
  check('寄信失敗唔會令註冊爆', /歡迎信例外/.test(srv))
  check('有 /api/admin/test-mail', /@app\.post\("\/api\/admin\/test-mail"\)/.test(srv))
  check('測試寄信要 admin', (() => {
    const i = srv.indexOf('def admin_test_mail(')
    return srv.slice(i, i + 500).includes('admin_user')
  })())
  check('status 有 from/to', /"from":/.test(m) && /"to":/.test(m))
  check('⚠️ status 唔洩漏密碼', !/mail_status[\s\S]{0,600}WANDER_SMTP_PASS/.test(m))
  check('Admin 有 MailTest 元件', /function MailTest\(\)/.test(admin))
  check('Admin 有寄測試信掣', /api\.testMail/.test(admin))
  check('api 有 testMail', /testMail:/.test(api))
  check('api 有 adminMail', /adminMail:/.test(api))
  check('MailTest 喺模組層', /^function MailTest\(/m.test(admin))
}

console.log(`\n${'═'.repeat(56)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(56))
process.exit(fail ? 1 : 0)
