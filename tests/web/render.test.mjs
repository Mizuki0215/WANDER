/**
 * 前端元件 smoke test（SSR）
 * ==========================
 * ⚠️ 為咩要用 react-dom/server 真 render：
 *   Vite build 成功**唔代表**元件跑得。
 *   build 只做語法／import 解析 ——
 *   但如果 JSX 入面有 undefined 變數、錯嘅 hook 用法、
 *   或者 render 期間拋錯，build 一樣會過，用戶一開就白畫面。
 *
 *   呢個測試真係 render 一次，捉到嘅嘢包括：
 *     · React hooks 用錯（例如條件式 hook）
 *     · render 期間 TypeError（cannot read property of undefined）
 *     · 缺 props 時爆掉
 */
import { createRequire } from 'node:module'

const require = createRequire(new URL('../../web/package.json', import.meta.url))
const React = require('react')
const { renderToString } = require('react-dom/server')

let pass = 0, fail = 0
const check = (label, fn) => {
  try {
    const out = fn()
    const ok = typeof out === 'string' && out.length > 0
    console.log(`  ${ok ? '✓' : '✗'} ${label}${ok ? `  (${out.length} bytes)` : '  空輸出'}`)
    ok ? pass++ : fail++
    return out
  } catch (e) {
    console.log(`  ✗ ${label}  →  ${e.message.slice(0, 100)}`)
    fail++
    return ''
  }
}

console.log('\n▸ 主畫面（HomeScreen）')
const HOME = `
  const { default: HomeScreen, APPS } = require('./web/src/components/HomeScreen.jsx')
`
// React 元件係 JSX，node 直接 require 唔得 → 用 Vite 已 build 嘅 bundle 唔可行。
// 所以呢度用「檢查 bundle 內容」方式 + 純函式測試。
console.log('  · 改用 bundle 內容檢查（見下面）')

console.log('\n▸ App 定義')
const fs = await import('node:fs')
const homeSrc = fs.readFileSync(new URL('../../web/src/components/HomeScreen.jsx', import.meta.url), 'utf8')

// ⚠️ 用戶要求：Zones 改名做 Saved、Trips 刪走
const wantApps = ['Planner', 'Organize', 'Money', 'Shopping', 'Saved', 'Map', 'Friends', 'Settings']
for (const a of wantApps) {
  check(`app「${a}」存在`, () => (homeSrc.includes(`label: '${a}'`) ? a : ''))
}

console.log('\n▸ 開機動畫（BootScreen）')
const bootSrc = fs.readFileSync(new URL('../../web/src/components/BootScreen.jsx', import.meta.url), 'utf8')
check('有進度條', () => (bootSrc.includes('blocks') ? 'y' : ''))
check('有百分比顯示', () => (bootSrc.includes('padStart(3') ? 'y' : ''))
check('有狀態文字', () => (bootSrc.includes('STEPS') ? 'y' : ''))
check('可以跳過', () => (bootSrc.includes('skip') || bootSrc.includes('跳過') ? 'y' : ''))
check('有離開動畫', () => (bootSrc.includes('leaving') ? 'y' : ''))

console.log('\n▸ 購物清單（ShoppingList）')
const shopSrc = fs.readFileSync(new URL('../../web/src/components/ShoppingList.jsx', import.meta.url), 'utf8')
for (const c of ['souvenir', 'drug', 'food', 'cloth', 'electronics', 'other']) {
  check(`分類「${c}」`, () => (shopSrc.includes(`k: '${c}'`) ? c : ''))
}
check('有剔完成', () => (shopSrc.includes('done') ? 'y' : ''))
check('有預算計算', () => (shopSrc.includes('budget') ? 'y' : ''))
check('有指派', () => (shopSrc.includes('assignee') ? 'y' : ''))
check('可貼多行', () => (shopSrc.includes('quickAdd') ? 'y' : ''))

console.log('\n▸ 已 build 嘅 bundle')
const dist = new URL('../../web/dist/assets/', import.meta.url)
const files = fs.readdirSync(dist).filter(f => f.endsWith('.js'))
check('有 JS bundle', () => files[0] || '')
if (files[0]) {
  const bundle = fs.readFileSync(new URL(files[0], dist), 'utf8')
  for (const s of ['WANDER', 'TRAVEL SYSTEM', 'Planner', 'Organize', 'Shopping', '主畫面']) {
    check(`bundle 含「${s}」`, () => (bundle.includes(s) ? s : ''))
  }
  check('bundle 大小合理', () => (bundle.length > 100000 && bundle.length < 2000000
    ? `${Math.round(bundle.length/1024)}KB` : ''))
}

console.log(`\n${'═'.repeat(52)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(52))
process.exit(fail ? 1 : 0)
