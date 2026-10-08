import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * ⚠️⚠️ 每次 build 都換 service worker 版本 + 注入 build id
 * ==========================================================
 *
 * ⚠️ 用戶報：「shopping list 入唔到去睇」
 *
 * ⚠️ 根因之一：`web/public/sw.js` 嘅 `VERSION = 'wander-v1'`
 *    **從來冇改過** → 瀏覽器見到 `/sw.js` **一模一樣** →
 *    永遠話「冇更新」→ 唔會裝新 service worker。
 *
 *    ⚠️ 而且**冇辦法知用戶跑緊邊個版本** ——
 *       debug 嗰陣完全靠猜。
 *
 * ✅ 修法：
 *    ① build 時計算一個 `BUILD_ID`
 *    ② 寫入 `sw.js` 嘅 `VERSION`
 *    ③ 注入 `__BUILD_ID__` 落前端（設定頁可以睇到）
 */

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SW = path.join(HERE, 'public', 'sw.js')

/** ⚠️ 由時間戳 + 可選嘅 CI 值砌一個 id。 */
function buildId() {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '')
  const extra = process.env.VITE_BUILD_ID || ''
  return `${stamp}${extra ? '-' + extra : ''}`
}

const ID = buildId()

export default defineConfig({
  plugins: [
    react(),

    /**
     * ⚠️ 將 build id 寫入 `sw.js`。
     *
     * ⚠️ 一定要喺 Vite copy `public/` **之前**改個檔 ——
     *    所以用 `buildStart`（最早嘅 hook）。
     * ⚠️ `closeBundle` 要還原返 —— 唔好將 build id 留喺 git 入面。
     */
    {
      name: 'wander-build-id',
      apply: 'build',
      buildStart() {
        if (fs.existsSync(SW)) {
          const src = fs.readFileSync(SW, 'utf8')
          this.__orig = src
          // ⚠️ 只換 VERSION 嗰行（唔好整份重寫）
          const out = src.replace(
            /^const VERSION = ['"][^'"]*['"]/m,
            `const VERSION = 'wander-${ID}'`)
          if (out !== src) {
            fs.writeFileSync(SW, out, 'utf8')
            console.log(`\n  ✓ sw.js VERSION → wander-${ID}`)
          } else {
            console.warn('\n  ⚠️ sw.js 搵唔到 VERSION 行（唔會自動更新）')
          }
        }
        console.log(`  ✓ build id: ${ID}\n`)
      },
      closeBundle() {
        // ⚠️ 還原 `sw.js` —— 唔好將 build id 留喺 git 入面
        if (this.__orig != null) {
          fs.writeFileSync(SW, this.__orig, 'utf8')
        }
      },
    },
  ],

  // ⚠️ `__BUILD_ID__` 喺 code 入面用得（設定頁顯示）
  define: {
    __BUILD_ID__: JSON.stringify(ID),
  },

  server: {
    host: true,
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8787' },   // dev 時 proxy 去 FastAPI
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
