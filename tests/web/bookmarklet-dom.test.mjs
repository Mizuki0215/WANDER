/**
 * 書籤小工具 · 真實 DOM 測試
 * ==========================
 * ⚠️ 呢個唔係「睇下語法有冇錯」——係用 jsdom 模擬真實 Instagram /
 *    小紅書頁面，真正執行書籤小工具，確認佢抽到正確嘅 caption。
 *
 *    為咩咁重要：書籤小工具係 IG 封鎖嘅唯一解法。
 *    如果選擇器唔啱，成個方案就廢 —— 但用戶唔會知係邊度壞。
 *
 * 跑法：node tests/web/bookmarklet-dom.test.mjs
 */
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'

// ⚠️ jsdom 裝喺 web/node_modules，而呢個測試喺 tests/web/
//    ESM 係按「檔案位置」解析，唔係 cwd，所以要明確指路。
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { JSDOM } = require('jsdom')

// ⚠️ 直接 import 真模組（web/package.json 有 "type": "module"），
//    唔好用 regex 抽 template literal —— 試過，好易錯。
import { bookmarkletCode } from '../../web/src/lib/bookmarklet.js'

const code = bookmarkletCode().replace(/^javascript:/, '')
const runnable = code

let pass = 0, fail = 0
const check = (label, cond, extra = '') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

/**
 * 喺 jsdom 環境執行書籤小工具，回傳抽到嘅 payload。
 *
 * ⚠️ 一定要 await —— navigator.clipboard.writeText() 係 Promise，
 *    rejection handler（fallback textarea）喺 microtask 之後先跑。
 *    如果唔 await，就會誤判「fallback 冇出現」。
 */
async function execute(html, url, { clipboardFails = false } = {}) {
  const dom = new JSDOM(html, { url, pretendToBeVisual: true })
  const { window } = dom
  let copied = null
  let alertMsg = null
  let textareaValue = null

  window.navigator.clipboard = {
    writeText: (t) => {
      if (clipboardFails) return Promise.reject(new Error('denied'))
      copied = t
      return Promise.resolve()
    },
  }
  window.alert = (m) => { alertMsg = m }
  // 捕捉 fallback textarea
  const origAppend = window.document.body.appendChild.bind(window.document.body)
  window.document.body.appendChild = (el) => {
    if (el.tagName === 'TEXTAREA') { textareaValue = el.value; return el }
    return origAppend(el)
  }

  const sandbox = {
    window, document: window.document, navigator: window.navigator,
    location: window.location, alert: window.alert,
    setTimeout: (fn) => fn(), console,
  }
  sandbox.globalThis = sandbox
  vm.createContext(sandbox)
  vm.runInContext(runnable, sandbox)
  // 等 promise 鏈同 setTimeout 完成
  await new Promise(r => setImmediate(r))
  await new Promise(r => setImmediate(r))
  return { copied, alertMsg, textareaValue, dom }
}

const IG_URL = 'https://www.instagram.com/p/DcV-H82D9Rj/'
const CAPTION = `【開幕快將滿一年！座落銅鑼灣正宗〖#長岡博多天婦羅〗🍤】
正宗鮮製現炸天婦羅在哪吃？在 #銅鑼灣利園 就吃得到，
從 #福岡 漂洋過海來的 #休閒式天婦羅店。`

// ══ 測試 1：標準 IG 帖文（用 h1）══
console.log('\n▸ Instagram 帖文（h1 格式）')
{
  const html = `<!DOCTYPE html><html><body>
    <header><a href="/somefoodie/"><span>somefoodie</span></a></header>
    <main><article>
      <img srcset="https://scontent.cdninstagram.com/pic.jpg 640w" src="https://scontent.cdninstagram.com/pic.jpg?v=1">
      <div><h1 dir="auto">${CAPTION.replace(/\n/g, '<br>')}</h1></div>
    </article></main>
  </body></html>`
  const { copied } = await execute(html, IG_URL)
  check('有複製到剪貼簿', !!copied)
  check('payload 有 url', copied?.includes(IG_URL))
  check('payload 有 caption', copied?.includes('長岡博多天婦羅'))
  check('payload 有作者', copied?.includes('somefoodie'), copied?.split('\n')[2])
  check('payload 有圖片', copied?.includes('scontent.cdninstagram.com'))
  check('有 PAYLOAD 標記', copied?.includes('---WANDER---') && copied?.includes('---WANDER-END---'))
}

// ══ 測試 2：IG 改版冇 h1，靠 div[dir=auto] ══
console.log('\n▸ Instagram 改版（冇 h1，用 dir="auto"）')
{
  const html = `<!DOCTYPE html><html><body>
    <main><article>
      <img src="https://scontent.cdninstagram.com/x.jpg">
      <div dir="auto">好食</div>
      <div dir="auto">${CAPTION.replace(/\n/g, '<br>')}</div>
      <div dir="auto">查看更多</div>
    </article></main>
  </body></html>`
  const { copied } = await execute(html, IG_URL)
  check('抽到最長嗰段（唔係「好食」）', copied?.includes('長岡博多天婦羅'))
  check('冇攞錯短字串', !copied?.includes('caption: |\n  好食\n'))
}

// ══ 測試 3：IG Reel ══
console.log('\n▸ Instagram Reel')
{
  const html = `<!DOCTYPE html><html><body>
    <main><article>
      <video src="blob:x"></video>
      <h1>${CAPTION.replace(/\n/g, '<br>')}</h1>
    </article></main>
  </body></html>`
  const { copied } = await execute(html, 'https://www.instagram.com/reel/ABC123/')
  check('Reel 都抽到', copied?.includes('長岡博多天婦羅'))
  check('url 係 reel', copied?.includes('/reel/ABC123/'))
}

// ══ 測試 4：小紅書 ══
console.log('\n▸ 小紅書')
{
  const XHS_CAP = `首爾聖水洞必去！☕
📍地址：서울 성동구 연무장길 47
🕐 11:00 - 22:00
💰 人均 ₩12,000`
  const html = `<!DOCTYPE html><html><body>
    <div id="detail-desc">${XHS_CAP.replace(/\n/g, '<br>')}</div>
    <div class="swiper-slide"><img src="https://sns-img.xhscdn.com/a.webp?x=1"></div>
  </body></html>`
  const { copied } = await execute(html, 'https://www.xiaohongshu.com/explore/abc123')
  check('小紅書抽到內文', copied?.includes('首爾聖水洞'))
  check('有地址', copied?.includes('연무장길'))
  check('有圖片', copied?.includes('xhscdn'))
}

// ══ 測試 5：普通網站（og 標籤）══
console.log('\n▸ 普通網站（og:description）')
{
  const html = `<!DOCTYPE html><html><head>
    <meta property="og:title" content="福岡拉麵推介 | 旅遊blog">
    <meta property="og:description" content="一蘭本社総本店，地址：福岡県福岡市博多区中洲5-3-2">
    <meta property="og:image" content="https://blog.com/ramen.jpg">
  </head><body><article>內文…</article></body></html>`
  const { copied } = await execute(html, 'https://blog.com/fukuoka-ramen')
  check('抽到 og:description', copied?.includes('一蘭本社総本店'))
  check('抽到 og:image', copied?.includes('ramen.jpg'))
  check('抽到 og:title（| 前面部分做作者）', copied?.includes('福岡拉麵推介'))
}

// ══ 測試 6：冇內容要提示用戶 ══
console.log('\n▸ 搵唔到內容')
{
  const { copied, alertMsg } = await execute('<!DOCTYPE html><html><body><div>空</div></body></html>',
    'https://www.instagram.com/p/EMPTY/')
  check('冇複製嘢', !copied)
  check('有彈提示', !!alertMsg, alertMsg?.slice(0, 40))
  check('提示有教點做', alertMsg?.includes('更多') || alertMsg?.includes('展開'))
}

// ══ 測試 7：剪貼簿被拒 → fallback textarea ══
console.log('\n▸ 剪貼簿權限被拒（fallback）')
{
  const html = `<!DOCTYPE html><html><body><h1>${CAPTION.replace(/\n/g, '<br>')}</h1></body></html>`
  const { copied, textareaValue, alertMsg } = await execute(html, IG_URL, { clipboardFails: true })
  check('冇寫入剪貼簿', !copied)
  check('有彈 textarea 俾用戶手動複製', !!textareaValue)
  check('textarea 有 payload', textareaValue?.includes('長岡博多天婦羅'))
  check('有提示按 ⌘C', alertMsg?.includes('⌘C') || alertMsg?.includes('Ctrl+C'))
}

// ══ 測試 8：payload 格式要俾後端識別 ══
console.log('\n▸ payload 格式')
{
  const html = `<!DOCTYPE html><html><body><h1>${CAPTION.replace(/\n/g, '<br>')}</h1></body></html>`
  const { copied } = await execute(html, IG_URL)
  const lines = copied.split('\n')
  check('第一行係 ---WANDER---', lines[0] === '---WANDER---')
  check('最後一行係 ---WANDER-END---', lines[lines.length - 1] === '---WANDER-END---')
  check('有 url: 行', lines.some(l => l.startsWith('url: ')))
  check('有 caption: | 行', lines.some(l => l.trim() === 'caption: |'))
  check('caption 內容有縮排', lines.some(l => l.startsWith('  【開幕')))
}

console.log(`\n${'═'.repeat(52)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(52))
process.exit(fail ? 1 : 0)
