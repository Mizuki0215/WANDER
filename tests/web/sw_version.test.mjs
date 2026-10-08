/**
 * Service worker 版本自動更新
 * ==============================
 *
 * ⚠️⚠️ 用戶報：「shopping list 入唔到去睇」
 *
 * ⚠️ 根因之一：`web/public/sw.js` 嘅 `VERSION = 'wander-v1'`
 *    **從來冇改過** → 瀏覽器見到 `/sw.js` **一模一樣** →
 *    永遠話「冇更新」→ 用戶一直跑**舊版 bundle**。
 *
 * ✅ 修法：vite build 時會將 `VERSION` 換成帶 build id 嘅值。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
let pass = 0, fail = 0
function check(label, ok, extra = '') {
  console.log(`  ${ok ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  ok ? pass++ : fail++
}

console.log('═'.repeat(60))
console.log('  Service worker 版本')
console.log('═'.repeat(60))

const vite = fs.readFileSync(path.join(ROOT, 'web/vite.config.js'), 'utf8')
const swPub = fs.readFileSync(path.join(ROOT, 'web/public/sw.js'), 'utf8')

// ⚠️ vite config 要有 plugin 換 VERSION
check('vite config 有 build id plugin', vite.includes('wander-build-id'))
check('會換 sw.js 嘅 VERSION', /const VERSION = ['"]wander-\$\{ID\}['"]/.test(vite) ||
  vite.includes("`const VERSION = 'wander-${ID}'`"))
check('會還原 sw.js（唔污染 git）', vite.includes('closeBundle'))
check('注入 __BUILD_ID__', vite.includes('__BUILD_ID__'))

// ⚠️ public/sw.js 本身要保持 'wander-v1'（build 時才換）
check('public/sw.js 保持原版（build 時才換）',
  /const VERSION = ['"]wander-v1['"]/.test(swPub))

// ⚠️ dist/sw.js（如果有 build）要有真 build id
const distSw = path.join(ROOT, 'web/dist/sw.js')
if (fs.existsSync(distSw)) {
  const s = fs.readFileSync(distSw, 'utf8')
  const m = s.match(/const VERSION = '([^']+)'/)
  const id = m ? m[1] : ''
  check('dist/sw.js 有 build id', /^wander-\d{12}/.test(id), id)
  check('dist/sw.js 唔係 v1', id !== 'wander-v1')
} else {
  console.log('  ⚠️ 冇 web/dist/sw.js（跳過 dist 檢查）')
}

// ⚠️ pwa.js 要夠密咁查更新
const pwa = fs.readFileSync(path.join(ROOT, 'web/src/lib/pwa.js'), 'utf8')
check('查更新間隔 ≤ 10 分鐘', /5 \* 60_000|6 \* 60_000|10 \* 60_000/.test(pwa),
  '原本一個鐘太疏')
check('切返 app 就查更新', pwa.includes('visibilitychange'))
check('有 hardReload（清 cache）', pwa.includes('export async function hardReload'))
check('hardReload 會清 caches', pwa.includes('caches.delete'))
check('hardReload 唔會清 localStorage',
  !/localStorage\.(clear|removeItem)/.test(pwa))
check('applyUpdate 有 fallback reload',
  /setTimeout\(\(\) => window\.location\.reload/.test(pwa))

// ⚠️ 設定頁要顯示版本 + 有強制 reload 掣
const sm = fs.readFileSync(path.join(ROOT, 'web/src/components/SettingsMore.jsx'), 'utf8')
check('設定頁顯示版本', sm.includes('__BUILD_ID__'))
check('設定頁有強制重新載入掣', sm.includes('強制重新載入'))
check('強制載入會用 hardReload', sm.includes('hardReload'))

console.log()
console.log('═'.repeat(60))
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(60))
process.exit(fail ? 1 : 0)
