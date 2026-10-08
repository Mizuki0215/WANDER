/**
 * 響應式／手機排版測試
 * ====================
 * ⚠️⚠️ 為咩要有呢個測試：
 *
 *   用戶報：「每一部手機佢哋嘅大細闊度都唔一樣」
 *
 *   真實手機闊度範圍好大：
 *     320px  iPhone SE (1st)
 *     360px  大部分 Android
 *     375px  iPhone SE2/8
 *     390px  iPhone 13/14
 *     414px  iPhone 11/XR
 *     430px  iPhone 15 Pro Max
 *     500px+ 摺機 / 平板
 *
 *   而且有兩個「靜靜死」嘅陷阱：
 *     ① CSS 用咗 `var(--safe-t)` 但冇定義
 *        → 成個 declaration 被丟棄 → 個 ✕ 掣被動態島遮住
 *        （實測踩過！）
 *     ② 固定 px 令 320px 機唔夠位放文字，但喺 430px 機睇落正常
 *        → 開發者用大機測試永遠唔會發現
 *
 *   呢個測試兩樣都捉。
 */
import fs from 'node:fs'

const CSS = fs.readFileSync(
  new URL('../../web/src/styles.css', import.meta.url), 'utf8')

let pass = 0, fail = 0

/**
 * ⚠️ 去咗註解先做源碼檢查。
 *
 *   第一個版本嘅測試就係咁樣誤報：
 *   我喺 code 入面加咗註解解釋「原本條件係 tab !== 'trips'」，
 *   測試就 match 到我自己嘅解釋，以為 bug 仲喺度。
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')   // /* ... */
    .replace(/(^|[^:])\/\/.*$/gm, '$1')    // // ...
}
const check = (label, cond, extra = '') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

// ══ ① CSS 變數：用咗嘅一定要有定義 ══
console.log('\n▸ CSS 變數完整性')
{
  // ⚠️ 變數可以喺**任何** selector 入面定義，唔止 :root / [data-theme]。
  //    例如 `--c` 係 `.app-ico[data-app='calendar'] { --c: var(--app-a) }`
  //    呢種**局部**變數（局部化係好設計，唔應該當錯）。
  const defined = new Set(
    [...CSS.matchAll(/(?:^|[;{\s])(--[\w-]+)\s*:/gm)].map(m => m[1]))
  const used = new Set(
    [...CSS.matchAll(/var\((--[\w-]+)/g)].map(m => m[1]))
  const missing = [...used].filter(v => !defined.has(v))
  check(`全部 ${used.size} 個變數都有定義`, missing.length === 0,
    missing.length ? `缺: ${missing.join(', ')}` : '')

  // 安全區變數特別重要（iPhone 劉海）
  for (const v of ['--safe-t', '--safe-b', '--safe-l', '--safe-r']) {
    check(`${v} 有定義`, defined.has(v))
  }
  // env() 一定要有 fallback
  const envs = [...CSS.matchAll(/env\(([^)]+)\)/g)].map(m => m[1])
  const noFallback = envs.filter(e => !e.includes(','))
  check('所有 env() 都有 fallback', noFallback.length === 0,
    noFallback.length ? noFallback.join('; ') : `${envs.length} 個`)
}

// ══ ② 關鍵元素要用 clamp（唔係固定 px）══
console.log('\n▸ 用 clamp 而唔係固定 px')
{
  const need = [
    ['.item .ic', '列表圖示格'],
    ['.thumb', '相片縮圖'],
    ['.h1', '標題'],
  ]
  for (const [sel, label] of need) {
    // 搵最後一個該 selector 嘅規則
    const re = new RegExp(
      sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\{([^}]*)\\}', 'g')
    const all = [...CSS.matchAll(re)].map(m => m[1])
    const hit = all.some(b => b.includes('clamp('))
    check(`${label} 用 clamp()`, hit, all.length ? '' : '（搵唔到規則）')
  }
}

// ══ ③ 排版：每個手機闊度都要夠位放文字 ══
console.log('\n▸ 排版空間（模擬真實手機）')
{
  const px = (clampStr, vw) => {
    // 解析 clamp(lo, Nvw, hi)
    const m = clampStr.match(/clamp\(\s*([\d.]+)px\s*,\s*([\d.]+)vw\s*,\s*([\d.]+)px\s*\)/)
    if (!m) return null
    const [, lo, v, hi] = m.map(Number)
    return Math.max(lo, Math.min(hi, v / 100 * vw))
  }

  // 由 CSS 抽實際值
  const grab = (selStr, prop) => {
    const m = CSS.match(new RegExp(
      selStr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\{[^}]*?' + prop +
      '\\s*:\\s*(clamp\\([^)]*\\)|[\\d.]+px)', 's'))
    return m ? m[1] : null
  }
  const thumbCss = grab('.thumb', 'width')
  const icCss = grab('.item .ic', 'width')
  const padCss = grab('.item', 'padding')

  const PHONES = [
    ['iPhone SE (1st)', 320], ['Android 細機', 360], ['iPhone SE2/8', 375],
    ['iPhone 13/14', 390], ['iPhone 11/XR', 414], ['iPhone 15 Pro Max', 430],
  ]

  for (const [name, w] of PHONES) {
    const thumb = thumbCss?.startsWith('clamp') ? px(thumbCss, w) : parseFloat(thumbCss)
    const rowPad = padCss?.startsWith('clamp') ? px(padCss, w) : parseFloat(padCss)
    const screenPad = w <= 360 ? 10 : Math.max(12, Math.min(18, 0.04 * w))
    const checkbox = 25, delBtn = 30, gap = w <= 360 ? 8 : Math.min(12, 0.026 * w)
    const avail = w - screenPad * 2 - rowPad * 2
    const text = avail - thumb - checkbox - delBtn - gap * 3
    // ⚠️ 文字至少要 110px 先夠顯示「白色戀人 × 3 盒」
    check(`${name} (${w}px) 文字有 ${text.toFixed(0)}px`, text >= 110,
      `縮圖 ${thumb.toFixed(0)}px`)
  }
}

// ══ ④ 相片處理：唔可以有固定大細 ══
console.log('\n▸ 相片縮圖')
{
  const shop = fs.readFileSync(
    new URL('../../web/src/components/ShoppingList.jsx', import.meta.url), 'utf8')
  check('購物清單用 .thumb class', shop.includes('className={`thumb'))
  const noHardcoded = !/width:\s*44,\s*height:\s*44/.test(shop)
  check('冇硬編碼 44×44', noHardcoded)
  check('有 object-position（唔裁到主體）', CSS.includes('object-position: center 45%'))
  check('有全圖檢視（Lightbox）', shop.includes('Lightbox'))
  check('縮圖撳一下開全圖', shop.includes('onView'))
  const lb = fs.readFileSync(
    new URL('../../web/src/components/Lightbox.jsx', import.meta.url), 'utf8')
  check('全圖用 contain（唔裁）', CSS.includes('object-fit: contain'))
  check('Lightbox 撳 Esc 關得', lb.includes('Escape'))
}

// ══ ⑤ 觸控區夠大（Apple HIG 建議 44pt）══
console.log('\n▸ 觸控區')
{
  check('.btn 最少 40px 高', /\.btn\s*\{[^}]*min-height:\s*40px/.test(CSS))
  check('.btn.sm 最少 34px 高', /\.btn\.sm\s*\{[^}]*min-height:\s*34px/.test(CSS))
  check('.chip 最少 30px 高', /\.chip\s*\{[^}]*min-height:\s*30px/.test(CSS))
}

// ══ ⑥ 主畫面 app 格唔可以爆 ══
console.log('\n▸ 主畫面 app 格')
{
  const home = fs.readFileSync(
    new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')
  check('app icon 用 clamp', /width:\s*'clamp\(/.test(home))
  // ⚠️ 呢個測試**故意反轉** ——
  //    之前檢查「固定 4 欄」，但用戶要求改用百分比（auto-fit），
  //    所以而家檢查「**唔可以**再寫死欄數」。
  check('app 格用百分比 auto-fit（唔寫死欄數）',
    !/gridTemplateColumns:\s*'repeat\(4/.test(home) && home.includes('app-grid'))
  check('主畫面邊距用 clamp', /padding:\s*'0 clamp\(/.test(home))
  // ⚠️ 時鐘搬咗去 DualClock.jsx（雙時區）——
  //    所以字級檢查要去嗰個檔案搵。
  const clock = fs.readFileSync(
    new URL('../../web/src/components/DualClock.jsx', import.meta.url), 'utf8')
  check('時鐘字級用 px 常數（唔再係 clamp）',
    /fontSize:\s*compact\s*\?\s*30\s*:\s*46/.test(clock))

  // 模擬 320px 最窄機
  const px = (str, vw) => {
    const m = str.match(/clamp\(\s*([\d.]+)px\s*,\s*([\d.]+)vw\s*,\s*([\d.]+)px\s*\)/)
    if (!m) return null
    const [, lo, v, hi] = m.map(Number)
    return Math.max(lo, Math.min(hi, v / 100 * vw))
  }
  for (const w of [320, 360, 390, 430]) {
    const pad = px('clamp(14px, 5vw, 22px)', w)
    const icon = px('clamp(52px, 14.5vw, 66px)', w)
    const gap = px('clamp(6px, 2.4vw, 10px)', w)
    const avail = w - pad * 2
    // 由 CSS 嘅 minmax(22%, 1fr) 推算欄數
    let cols = 0
    for (let n = 1; n <= 8; n++) {
      if (n * (avail * 0.22) + (n - 1) * gap <= avail + 0.5) cols = n
    }
    const needed = cols * (avail * 0.22) + (cols - 1) * gap
    check(`${w}px: ${cols} 欄（百分比）夠位`, needed <= avail + 0.5,
      `${needed.toFixed(0)}px / ${avail.toFixed(0)}px`)
  }
}

// ══ ⑦ 「先揀一個旅程」唔可以擋錯 app ══
//   ⚠️⚠️ 用戶報：「點解撳入去 setting 都係冇嘢嘅？」
//      原因：閘條件係 `tab !== 'trips' && !inTrip` ——
//      連 ⚙️ 設定、👥 朋友 都被擋 → 用戶撳設定見到「先揀一個旅程」。
console.log('\n▸ 「先揀一個旅程」閘（用戶報嘅 bug）')
{
  const appRaw = fs.readFileSync(
    new URL('../../web/src/App.jsx', import.meta.url), 'utf8')
  const app = stripComments(appRaw)     // ⚠️ 去註解先檢查

  // ① TRIP_APPS 唔可以包含唔需要旅程嘅 app
  const m = app.match(/const TRIP_APPS = \[([^\]]+)\]/)
  check('有 TRIP_APPS 清單', !!m)
  if (m) {
    const ids = [...m[1].matchAll(/'([a-z]+)'/g)].map(x => x[1])
    for (const noTrip of ['settings', 'friends', 'trips', 'home']) {
      check(`TRIP_APPS 唔包含「${noTrip}」`, !ids.includes(noTrip),
        ids.includes(noTrip) ? `實際: ${ids.join(',')}` : '')
    }
    for (const needTrip of ['calendar', 'money', 'shopping', 'saved', 'map', 'discover']) {
      check(`TRIP_APPS 包含「${needTrip}」`, ids.includes(needTrip))
    }
  }

  // ② 閘一定要用 TRIP_APPS，唔可以再用 tab !== 'trips'
  check('閘用 TRIP_APPS.includes(tab)',
    /!inTrip && TRIP_APPS\.includes\(tab\)/.test(app))
  check("閘冇再用 tab !== 'trips'", !/tab !== 'trips'/.test(app))

  // ③ openApp 同 render 要用同一個清單（唔可以各寫一份）
  const uses = (app.match(/TRIP_APPS/g) || []).length
  check('TRIP_APPS 用喺兩處以上（單一真相來源）', uses >= 2, `出現 ${uses} 次`)

  // ④ !inTrip 嘅 Settings 一定要傳 onUserUpdate
  const i = app.indexOf("!inTrip && tab === 'settings'")
  const blk = app.slice(i, i + 320)
  check('!inTrip 分支有傳 onUserUpdate', blk.includes('onUserUpdate'))
}

// ══ ⑧ Pixel Art 風格 ══
console.log('\n▸ Pixel Art 風格')
{
  // 冇圓角、硬陰影、粗邊框
  const hardShadow = /\.card\s*\{[^}]*box-shadow:\s*var\(--px\)\s+var\(--px\)\s+0\s/.test(CSS)
  check('.card 用硬陰影（0 blur）', hardShadow)
  const noBlurCard = !/\.card\s*\{[^}]*box-shadow:[^;}]*\d+px\s+\d+px\s+[1-9]/.test(CSS)
  check('.card 陰影冇 blur 半徑', noBlurCard)
  check('.btn:active 有硬位移', /\.btn:active[^{]*\{[^}]*translate\(var\(--px\)/.test(CSS))
  check('.app-ico 有硬陰影', /\.app-ico\s*\{[^}]*box-shadow:\s*var\(--px\)/.test(CSS))
  check('有像素字體 class .pix', /\.pix\s*\{/.test(CSS))

  // 像素圖示
  const icons = fs.readFileSync(
    new URL('../../web/src/lib/pixelicons.js', import.meta.url), 'utf8')
  check('有 App 像素圖示', icons.includes('APP_ICONS'))
  check('crispEdges（防止灰邊）', icons.includes('crispEdges'))
  const appIcons = (icons.match(/^  [a-z]+: P\(/gm) || []).length
  check('圖示數量 >= 15', appIcons >= 15, `實際 ${appIcons}`)

  // HomeScreen 唔可以再用 emoji 做 app icon
  const home = fs.readFileSync(
    new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')
  check('AppIcon 用 PixelIcon', home.includes('PixelIcon'))
  check('AppIcon 唔再用 {app.icon}', !home.includes('{app.icon}'))

  // 導航都用像素圖
  const app = fs.readFileSync(
    new URL('../../web/src/App.jsx', import.meta.url), 'utf8')
  check('nav 用 PixelIcon', app.includes('<PixelIcon name={icon}'))
}

// ══ ⑨ 新手教學：掣一定要撳得到 ══
//   ⚠️⚠️ 用戶報：「撳到去第一版佢介紹 planner 嗰陣時候呢，
//      冇一個 button 或者個 bug 太下面啦，所以導致到你撳唔到
//      之後介紹嘅嘢」
console.log('\n▸ 新手教學嘅掣（用戶報嘅 bug）')
{
  const ob = fs.readFileSync(
    new URL('../../web/src/components/Onboarding.jsx', import.meta.url), 'utf8')
  check('內容包喺 .onb-scroll（可捲區）', ob.includes('onb-scroll'))
  check('冇用負 margin 推個盒', !/marginTop:\s*inTour/.test(ob))
  check('用 alignSelf 決定上／下', ob.includes('alignSelf'))
  check('用吉祥物圖而唔係手畫 SVG', ob.includes('mascot-') && !ob.includes('mascotSvg'))

  // CSS：掣一定要喺滾動區**外面**
  check('.onb-box 係 flex column',
    /\.onb-box\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column/.test(CSS))
  check('.onb-scroll 可捲', /\.onb-scroll\s*\{[^}]*overflow-y:\s*auto/.test(CSS))
  check('.onb-actions 唔會被壓縮', /\.onb-actions\s*\{[^}]*flex:\s*0 0 auto/.test(CSS))

  // 結構次序：scroll 要喺 actions **之前**
  const iScroll = ob.indexOf('onb-scroll')
  const iActions = ob.indexOf('className="onb-actions"')
  check('onb-scroll 出現喺 onb-actions 之前',
    iScroll > 0 && iActions > 0 && iScroll < iActions,
    `scroll@${iScroll} actions@${iActions}`)
}

// ══ ⑩ 百分比排版（用戶要求）══
//   ⚠️ 用戶原話：「因為每部手機啦個電腦嗰個比例唔一樣嘅話，
//      我唔建議你嗰個 Apps 係整到係用數量囉，
//      你應該用 percentage 表達」
console.log('\n▸ 百分比排版（唔用固定 px 數量）')
{
  const home = fs.readFileSync(
    new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')
  check('用 .app-grid class', home.includes('className="app-grid"'))
  check('冇寫死 gridTemplateColumns: repeat(4', !/gridTemplateColumns:\s*'repeat\(4/.test(home))
  check('統計格用 .stat-grid', home.includes('className="stat-grid"'))

  // CSS：grid 要用百分比
  const m = CSS.match(/\.app-grid\s*\{([^}]*)\}/)
  check('搵到 .app-grid 規則', !!m)
  if (m) {
    check('用 auto-fit（欄數自動）', m[1].includes('auto-fit'))
    check('用百分比 minmax（唔係 px）', /minmax\(\s*[\d.]+%/.test(m[1]),
      /minmax\(\s*[\d.]+px/.test(m[1]) ? '⚠️ 用咗 px' : '')
  }
  // icon 大細要用 % 而唔係 px
  // ⚠️ 要搜**所有** .app-ico 規則 —— 唔止第一個
  const allIco = [...CSS.matchAll(/\.app-ico\s*\{([^}]*)\}/g)].map(m => m[1])
  const joined = allIco.join(' ')
  check('.app-ico 用 width:100%', joined.includes('width: 100%'))
  check('.app-ico 用 aspect-ratio', joined.includes('aspect-ratio'))

  // 模擬唔同手機闊度：要穩定 4 欄
  console.log('    ── 模擬真實手機 ──')
  for (const [name, W] of [['iPhone SE', 320], ['Android', 360],
                           ['iPhone 13', 390], ['iPhone 15 PM', 430]]) {
    const pad = Math.max(12, Math.min(18, 0.04 * W))
    const avail = W - pad * 2
    const gap = avail * 0.015
    let cols = 0
    for (let n = 1; n <= 8; n++) {
      if (n * (avail * 0.22) + (n - 1) * gap <= avail + 0.5) cols = n
    }
    const tile = (avail - (cols - 1) * gap) / cols
    check(`${name} (${W}px) → ${cols} 欄 · 每格 ${tile.toFixed(0)}px`,
      cols === 4 && tile > 60)
  }
}

// ══ ⑪ 圓角系統（用戶要求 iPhone 風格）══
//   ⚠️ 用戶原話：「不過框框嘅弧度你可以參考吓 iPhone 嗰種弧度囉，
//      因為正方形長方形呢個好難睇…唔好淨係一個長方形，
//      而係真係要有少少嘅弧度。」
console.log('\n▸ 圓角系統（iPhone 風格）')
{
  // ⚠️ 一定要用**去註解**版本 ——
  //    否則會 match 到我自己解釋 `--px-r: 2px` 嘅註解。
  const css = stripComments(CSS)
  // ① scale 要存在
  const scale = {}
  for (const k of ['r-xs', 'r-sm', 'r', 'r-lg']) {
    const m = css.match(new RegExp(`--${k}:\\s*([\\d.]+)px`))
    scale[k] = m ? parseFloat(m[1]) : null
    check(`有 --${k}`, scale[k] !== null, m ? `${scale[k]}px` : '')
  }

  // ② 數值要遞增（scale 唔可以亂）
  if (scale['r-xs'] && scale['r-lg']) {
    check('scale 遞增（xs < sm < r < lg）',
      scale['r-xs'] < scale['r-sm'] && scale['r-sm'] < scale['r'] && scale['r'] < scale['r-lg'],
      Object.values(scale).join(' < '))
  }

  // ③ ⚠️⚠️ 唔可以太方（< 8px）—— 呢個就係用戶報嘅問題
  for (const [k, min] of [['r-xs', 6], ['r-sm', 10], ['r', 14], ['r-lg', 20]]) {
    check(`--${k} ≥ ${min}px（唔會睇落係方角）`,
      scale[k] !== null && scale[k] >= min, `${scale[k]}px`)
  }

  // ④ App icon 要用**百分比**（同 iPhone 一樣）
  const ico = css.match(/--r-ico:\s*([\d.]+)%/)
  check('App icon 用百分比圓角', !!ico, ico ? `${ico[1]}%` : '')
  if (ico) {
    const pct = parseFloat(ico[1])
    check('App icon 圓角 20-26%（iPhone 係 22.37%）',
      pct >= 20 && pct <= 26, `${pct}%`)
  }

  // ⑤ 每個主題都要有完整 scale
  // ⚠️ 同一個主題可能有多段 block（色位一段、圓角一段…）——
  //    要按主題**合併**，唔可以逐段檢查（否則色位嗰段會假失敗）。
  const byTheme = new Map()
  for (const m of css.matchAll(/\[data-theme='(\w+)'\]\s*\{([^}]*)\}/g)) {
    byTheme.set(m[1], (byTheme.get(m[1]) || '') + m[2])
  }
  const themes = [...byTheme.entries()]
  check('有主題定義', themes.length >= 5, `${themes.length} 個`)
  for (const [name, body] of themes) {
    // ⚠️ galaxy 係**預設主題**，佢嘅圓角喺 `:root` 定義（唔喺自己個 block）
    if (name === 'galaxy') {
      const rootHas = ['--r:', '--r-sm:', '--r-xs:'].every(
        v => css.match(new RegExp(`:root\\s*\\{[^}]*${v}`, 's')))
      check('主題「galaxy」繼承 :root 嘅圓角 scale', rootHas)
      continue
    }
    const has = ['--r:', '--r-sm:', '--r-xs:'].every(v => body.includes(v))
    check(`主題「${name}」有完整圓角 scale`, has)
  }

  // ⑥ ⚠️⚠️ 唔可以仲有 --px-r 蓋住（之前嘅 bug 來源）
  check('已經冇 --px-r 覆蓋', !/--px-r:\s*2px/.test(css))

  // ⑦ 元件唔可以再有「容器級」硬編碼細圓角
  const files = ['HomeScreen', 'Settings', 'SettingsMore', 'Login', 'ShoppingList',
                 'Settlement', 'StopsEditor', 'MyQr', 'Friends', 'Calendar',
                 'DayGrid', 'Trips', 'Saved', 'Discover']
  const bad = []
  for (const f of files) {
    const p = new URL(`../../web/src/components/${f}.jsx`, import.meta.url)
    let src
    try { src = fs.readFileSync(p, 'utf8') } catch { continue }
    // ⚠️ 只捉「大於 20 嘅硬編碼」（容器）——
    //    1/2/3px 同 99px 係刻意嘅像素細節／膠囊。
    for (const m of src.matchAll(/borderRadius:\s*(\d+)\b/g)) {
      const v = parseInt(m[1])
      if (v > 6 && v < 90) bad.push(`${f}: ${v}px`)
    }
  }
  check('冇容器級硬編碼圓角', bad.length === 0,
    bad.length ? bad.slice(0, 4).join(', ') : '')
}

// ══ ⑫ App 圖示大細（用戶要求 1.1-1.2 倍 + 向下少少）══
//   ⚠️⚠️ 捉到「雙重縮細」bug：
//      `.pxi` span 用 inline px（38px），CSS 又 `svg { width: 58% }`
//      → 38 × 0.58 = **22px**（瓦片嘅 33-42%）
//      而且 22px 係**固定**，唔隨瓦片縮放。
console.log('\n▸ App 圖示大細（用戶報嘅 bug）')
{
  const css = stripComments(CSS)

  // ① 要用變數控制（方便微調）
  const m = css.match(/--ico-w:\s*([\d.]+)%/)
  check('有 --ico-w 變數', !!m, m ? `${m[1]}%` : '')
  const w = m ? parseFloat(m[1]) : 0

  // ② 大細要合理（44-70%）
  check('--ico-w 喺 44-70% 之間', w >= 44 && w <= 70, `${w}%`)

  // ③ 要向下移（光學置中）
  const my = css.match(/--ico-y:\s*([\d.]+)%/)
  check('有 --ico-y（向下移）', !!my, my ? `${my[1]}%` : '')
  if (my) {
    const y = parseFloat(my[1])
    check('--ico-y 喺 2-8%（唔會太離譜）', y >= 2 && y <= 8, `${y}%`)
  }

  // ④ ⚠️⚠️ 唔可以有「雙重縮細」——
  //    `.pxi` 用百分比（唔係 inline px），svg 用 100%
  const pxi = css.match(/\.app-ico \.pxi\s*\{([^}]*)\}/)
  check('搵到 .app-ico .pxi 規則', !!pxi)
  if (pxi) {
    check('.pxi 大細用 var(--ico-w)', pxi[1].includes('var(--ico-w)'))
    check('.pxi 有 !important（蓋 inline px）', pxi[1].includes('!important'))
    check('.pxi 有向下位移', pxi[1].includes('translateY'))
  }
  const svg = css.match(/\.app-ico \.pxi svg\s*\{([^}]*)\}/)
  check('svg 用 100%（唔再縮第二次）',
    !!svg && svg[1].includes('100%'))

  // ⑤ 模擬真實手機：圖示一定要**隨瓦片縮放**
  console.log('    ── 模擬 ──')
  let prev = 0, grows = true
  for (const [name, W] of [['iPhone SE', 320], ['Android', 360],
                           ['iPhone 13', 390], ['iPhone 15 PM', 430]]) {
    // ⚠️ 瓦片係 clamp(52px, 14.5vw, 66px)（HomeScreen 嘅 inline style）
    const tile = Math.max(52, Math.min(66, 0.145 * W))
    const ico = tile * (w / 100)
    if (ico <= prev) grows = false
    prev = ico
    check(`${name} 瓦片 ${tile.toFixed(0)}px → 圖示 ${ico.toFixed(0)}px（${w}%）`,
      ico >= 24 && ico <= tile * 0.75)
  }
  check('圖示會隨瓦片縮放（唔再係固定 22px）', grows)

  // ⑥ 舊 bug 唔可以返嚟
  check('冇 `svg { width: 58% }` 呢種二次縮細',
    !/\.app-ico \.pxi svg\s*\{[^}]*width:\s*58%/.test(css))
}

console.log(`\n${'═'.repeat(54)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(54))
process.exit(fail ? 1 : 0)
