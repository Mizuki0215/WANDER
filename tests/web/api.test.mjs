/**
 * ⚠️⚠️ API 交叉檢查
 * ==================
 * 呢個測試捉到一個**白畫面**級嘅 bug：
 *
 *   元件呼叫 `api.myQr()`，但 `lib/api.js` **從來冇定義過** myQr。
 *   → `TypeError: api.myQr is not a function`
 *   → 喺 useEffect 入面拋錯 → React unmount 成棵樹 → **白畫面**
 *
 *   用戶報：「朋友 QR code 嗰度…生成嗰陣時…個畫面一路之後就冇咗」
 *
 * ⚠️⚠️ 點解舊測試捉唔到：
 *
 *   SSR 測試只檢查「**呼叫方**（MyQr.jsx）有冇寫 api.myQr」——
 *   有寫，所以通過。
 *   但**定義方**（api.js）冇 —— 呢個先係問題所在。
 *
 *   一個只睇一邊嘅檢查，比冇檢查更危險：**它會令你以為已經檢查過**。
 *
 * 所以呢個測試做雙向交叉檢查：
 *   ① 元件用到嘅每一個 `api.X` → api.js 一定要有
 *   ② api.js 定義嘅每一個 key → 至少要有一個地方用（捉死碼）
 */
import fs from 'node:fs'
import path from 'node:path'

const ROOT = new URL('../../', import.meta.url)
const SRC = new URL('web/src/', ROOT)
const API_JS = new URL('web/src/lib/api.js', ROOT)

let pass = 0, fail = 0
const check = (label, cond, extra = '') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

/** 去註解（唔可以 match 到自己解釋 bug 嘅註解）。 */
const strip = (s) => s
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/(^|[^:])\/\/.*$/gm, '$1')

/** 收集所有元件檔案。 */
function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p, out)
    else if (/\.jsx?$/.test(e.name)) out.push(p)
  }
  return out
}

const files = walk(SRC.pathname)
const apiSrc = strip(fs.readFileSync(API_JS, 'utf8'))

// ══ ① api.js 定義咗乜 ══
const m = apiSrc.match(/export const api = \{([\s\S]*?)\n\}/)
if (!m) { console.log('✗ 搵唔到 export const api'); process.exit(1) }
const defined = new Set(
  [...m[1].matchAll(/^\s{2}([a-zA-Z_][\w]*)\s*:/gm)].map(x => x[1]))

console.log(`\n▸ api.js 定義咗 ${defined.size} 個方法`)

// ══ ② 元件用到乜 ══
const used = new Map()      // name -> [files]
for (const f of files) {
  if (/lib\/api\.js$/.test(f)) continue
  const src = strip(fs.readFileSync(f, 'utf8'))
  for (const mm of src.matchAll(/\bapi\.([a-zA-Z_][\w]*)\s*\(/g)) {
    const name = mm[1]
    if (!used.has(name)) used.set(name, [])
    used.get(name).push(path.relative(SRC.pathname, f))
  }
}

console.log(`\n▸ 元件用到 ${used.size} 個 api 方法`)

// ══ ③ 交叉檢查：用咗嘅一定要有定義 ══
console.log('\n▸ ⚠️ 用到但冇定義（會白畫面）')
{
  const missing = [...used.keys()].filter(k => !defined.has(k))
  for (const k of missing) {
    const where = [...new Set(used.get(k))].slice(0, 3).join(', ')
    console.log(`  ✗ api.${k}  —— 喺 ${where} 用到，但 api.js 冇定義！`)
    fail++
  }
  check('全部用到嘅 api 方法都有定義', missing.length === 0,
    missing.length ? `缺 ${missing.length} 個：${missing.join(', ')}` : '')
}

// ══ ④ 反向：定義咗但冇人用（死碼）══
console.log('\n▸ 定義咗但冇人用')
{
  const unused = [...defined].filter(k => !used.has(k))
  // ⚠️ 呢個只係提示，唔算失敗 —— 有啲係刻意留低嘅 API
  if (unused.length) {
    console.log(`  · 冇人用（可能係刻意留低）：${unused.join(', ')}`)
  } else {
    console.log('  · （全部都有用到）')
  }
  pass++
}

// ══ ⑤ 特別檢查：會喺 useEffect 叫嘅方法 ══
//   ⚠️⚠️ useEffect 拋錯 = 整個 app unmount = 白畫面。
//      呢啲方法一定要存在。
console.log('\n▸ ⚠️ 喺 useEffect 入面呼叫嘅方法（拋錯 = 白畫面）')
{
  const critical = []
  for (const f of files) {
    const src = strip(fs.readFileSync(f, 'utf8'))
    // 粗略：搵 useEffect(...) 塊入面嘅 api.X(
    for (const mm of src.matchAll(/useEffect\(\(\)\s*=>\s*\{([\s\S]{0,900}?)\n\s*\},/g)) {
      for (const c of mm[1].matchAll(/\bapi\.([a-zA-Z_][\w]*)\s*\(/g)) {
        critical.push({ name: c[1], file: path.relative(SRC.pathname, f) })
      }
    }
  }
  const bad = critical.filter(c => !defined.has(c.name))
  const uniq = [...new Set(critical.map(c => c.name))]
  for (const n of uniq) {
    check(`useEffect 用嘅 api.${n} 有定義`, defined.has(n))
  }
  if (!uniq.length) {
    console.log('  · （冇喺 useEffect 直接叫 api）')
    pass++
  }
}



// ══════════════════════════════════════════════════════════════
// ⚠️⚠️ 元件「用咗但冇 import」檢查
// ══════════════════════════════════════════════════════════════
//
// 呢個測試捉到一個**真 bug**：
//   `Calendar.jsx` 用咗 `<PixelIcon>`，但 import 從來冇加到
//   → 撳 Planner 直接 `ReferenceError: PixelIcon is not defined`
//   → React unmount 成棵樹 → **白畫面**。
//
// ⚠️ 點解 build 捉唔到：
//   esbuild 見到 `<PixelIcon>` 只當佢係一個**未定義嘅變數**，
//   而 JS 嘅未定義變數係合法嘅（runtime 先拋）→ build 通過。
//
// ⚠️ 呢個 bug 同「api.myQr 冇定義」係同一類：
//   呼叫方寫咗，定義方冇 → 只有 runtime 先爆。
console.log('\n▸ 元件「用咗但冇 import」')

/** 常見嘅 HTML 標籤（大寫開頭但唔係元件）。 */
const HTML_OK = new Set([
  'Fragment', 'StrictMode', 'Suspense', 'React', 'Symbol', 'Promise',
  'Array', 'Object', 'Math', 'JSON', 'Date', 'Set', 'Map', 'Error',
  'String', 'Number', 'Boolean', 'RegExp', 'Infinity', 'NaN',
])

function checkImports(file, src) {
  const code = strip(src)
  // 收集 import 嘅名
  const imported = new Set()
  for (const m of code.matchAll(/import\s+([^;]+?)\s+from/g)) {
    const spec = m[1]
    // default import
    const d = spec.match(/^\s*(\w+)/)
    if (d) imported.add(d[1])
    // named imports
    const named = spec.match(/\{([^}]*)\}/)
    if (named) {
      for (const n of named[1].split(',')) {
        const nm = n.trim().split(/\s+as\s+/).pop().trim()
        if (nm) imported.add(nm)
      }
    }
  }
  // 本地定義（function X / const X =）
  const local = new Set()
  for (const m of code.matchAll(/function\s+(\w+)/g)) local.add(m[1])
  for (const m of code.matchAll(/(?:const|let|var)\s+(\w+)\s*=/g)) local.add(m[1])

  // JSX 用到嘅大寫開頭標籤
  const used = new Set()
  for (const m of code.matchAll(/<([A-Z]\w*)[\s/>]/g)) used.add(m[1])

  const missing = [...used].filter(n =>
    !imported.has(n) && !local.has(n) && !HTML_OK.has(n))
  return missing
}

{
  let bad = 0, total = 0
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8')
    const missing = checkImports(f, src)
    total += 1
    if (missing.length) {
      const rel = path.relative(SRC.pathname, f)
      console.log(`  ✗ ${rel} —— 用咗但冇 import：${missing.join(', ')}`)
      bad++
    }
  }
  check(`全部 ${total} 個檔案嘅 JSX 元件都有 import`, bad === 0,
    bad ? `${bad} 個檔案有問題` : '')
}

// ⚠️ 驗證檢查器本身（餵已知壞 input）
console.log('\n▸ 驗證 import 檢查器')
{
  const bad1 = "import React from 'react'\nexport default function X(){ return <PixelIcon name='a'/> }"
  check('捉到冇 import 嘅 <PixelIcon>', checkImports('/x.jsx', bad1).includes('PixelIcon'))
  const ok1 = "import React from 'react'\nimport PixelIcon from './P'\nexport default function X(){ return <PixelIcon/> }"
  check('唔會誤報有 import 嘅', checkImports('/x.jsx', ok1).length === 0)
  const ok2 = "import React from 'react'\nfunction Local(){ return null }\nexport default function X(){ return <Local/> }"
  check('唔會誤報本地定義嘅', checkImports('/x.jsx', ok2).length === 0)
}

console.log(`\n${'═'.repeat(54)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(54))
process.exit(fail ? 1 : 0)
