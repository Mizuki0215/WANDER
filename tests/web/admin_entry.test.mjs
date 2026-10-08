/**
 * ⚠️⚠️ 後台入口 render 測試
 *
 *   用戶報：「入到 Dashboard 未？nooo」
 *
 *   ⚠️ 實測捉到：`Settings` 喺 isAdmin=true 同 false
 *      係 **10302 bytes 完全一樣** —— 即係個掣根本冇 render。
 *
 *   呢個測試守住「admin 同非 admin 一定 render 唔同」。
 */
import { createRequire } from 'node:module'
import fs from 'node:fs'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const React = require('react')
const { renderToString } = require('react-dom/server')
const esbuild = require('esbuild')
const WEB = new URL('../../web/src/', import.meta.url)

function load(rel) {
  const out = esbuild.buildSync({
    entryPoints: [new URL(rel, WEB).pathname], bundle: true, write: false,
    format: 'cjs', platform: 'node', target: 'es2020', jsx: 'transform',
    loader: { '.jsx': 'jsx', '.js': 'jsx' },
    external: ['react', 'react-dom', 'react/jsx-runtime'], logLevel: 'silent',
  })
  const mod = { exports: {} }
  new Function('require', 'module', 'exports', 'React', out.outputFiles[0].text)(
    require, mod, mod.exports, React)
  return mod.exports.default || mod.exports
}

let pass = 0, fail = 0
function check(label, ok, extra = '') {
  console.log(`  ${ok ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  ok ? pass++ : fail++
}

const USER = {
  id: 'u1', email: 'icychan51@gmail.com', display_name: 'icyyy',
  username: 'icyyy215', avatar: 'star', theme: 'galaxy',
}
const BASE = {
  user: USER, theme: 'galaxy', setTheme() {}, onLogout() {},
  onUserUpdate() {}, onOpenAdmin() {},
}

console.log('═'.repeat(60))
console.log('  後台入口 render')
console.log('═'.repeat(60))

const S = load('components/Settings.jsx')
const asAdmin = renderToString(React.createElement(S, { ...BASE, isAdmin: true }))
const asUser = renderToString(React.createElement(S, { ...BASE, isAdmin: false }))

const textAdmin = asAdmin.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
const textUser = asUser.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')

check('admin 見到「開發版後台」', textAdmin.includes('開發版後台'))
check('普通用戶見唔到', !textUser.includes('開發版後台'))
check('兩者 render 唔同', asAdmin.length !== asUser.length,
  `${asAdmin.length} vs ${asUser.length} bytes`)
check('admin 版本大啲（多咗個掣）', asAdmin.length > asUser.length)
check('入口喺「更多設定」之前（唔使撳）',
  asAdmin.indexOf('開發版後台') < asAdmin.indexOf('更多設定'),
  '⚠️ 收埋咗就搵唔到')

console.log()
console.log('═'.repeat(60))
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(60))
process.exit(fail ? 1 : 0)
