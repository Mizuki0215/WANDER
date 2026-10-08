/**
 * 書籤小工具 payload 測試
 * ======================
 * ⚠️ 呢個係 IG 封鎖嘅正解：
 *    用用戶自己嘅瀏覽器、自己嘅登入狀態，由用戶主動撳一下。
 *    唔需要 cookie、唔需要 API、唔會被鎖帳號、法律乾淨。
 */
import fs from 'node:fs'
import vm from 'node:vm'

const src = fs.readFileSync(new URL('../../web/src/lib/bookmarklet.js', import.meta.url), 'utf8')
const sb = { console, navigator: {}, document: {}, location: { hostname: '' } }
sb.globalThis = sb
vm.createContext(sb)
vm.runInContext(src.replace(/^export\s+/gm, '').replace(/^const PAYLOAD_START/m, 'var PAYLOAD_START')
  .replace(/^const PAYLOAD_END/m, 'var PAYLOAD_END')
  .replace(/^const BOOKMARKLET_SRC/m, 'var BOOKMARKLET_SRC')
  .replace(/^export function/g, 'function'), sb)
const { parsePayload, bookmarkletCode, PAYLOAD_START } = sb

let pass = 0, fail = 0
const check = (label, cond, extra='') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

const IG = 'https://www.instagram.com/p/DcV-H82D9Rj/'
const CAPTION = `【開幕快將滿一年！座落銅鑼灣正宗〖#長岡博多天婦羅〗🍤】
在 #銅鑼灣利園 就吃得到，
從 #福岡 漂洋過海來的 #休閒式天婦羅店。`

const payload = `${PAYLOAD_START}
url: ${IG}
author: somefoodie
image: https://scontent.cdninstagram.com/abc.jpg
caption: |
  【開幕快將滿一年！座落銅鑼灣正宗〖#長岡博多天婦羅〗🍤】
  在 #銅鑼灣利園 就吃得到，
  從 #福岡 漂洋過海來的 #休閒式天婦羅店。
---WANDER-END---`

console.log('\n▸ 解析 payload')
const r = parsePayload(payload)
check('認得 payload', r !== null)
check('抽到 url', r?.url === IG, r?.url)
check('抽到 author', r?.author === 'somefoodie')
check('抽到 image', r?.image?.includes('scontent'))
check('caption 多行完整', r?.caption === CAPTION, JSON.stringify(r?.caption?.slice(0, 40)))
check('caption 冇咗縮排', !r?.caption?.includes('  【'))
check('caption 有 hashtag', r?.caption?.includes('#長岡博多天婦羅'))

console.log('\n▸ 唔係 payload 要回 null')
check('普通文字', parsePayload('一蘭拉麵 好好食') === null)
check('普通 link', parsePayload('https://maps.app.goo.gl/abc') === null)
check('空字串', parsePayload('') === null)
check('null', parsePayload(null) === null)

console.log('\n▸ 前後有雜訊都要認得（用戶可能連其他文字一齊貼）')
const noisy = `啲嘢好好食呀\n${payload}\n下次再去`
const r2 = parsePayload(noisy)
check('有前後文字都認到', r2?.caption === CAPTION)

console.log('\n▸ caption 冇縮排都要處理')
const flat = `${PAYLOAD_START}
url: ${IG}
caption: 一蘭拉麵本店
---WANDER-END---`
const r3 = parsePayload(flat)
check('單行 caption', r3?.caption === '一蘭拉麵本店', JSON.stringify(r3?.caption))

console.log('\n▸ bookmarklet 碼')
const code = bookmarkletCode()
check('以 javascript: 開頭', code.startsWith('javascript:'))
check('冇換行（bookmarklet 必須一行）', !code.includes('\n'))
check('長度合理', code.length > 500 && code.length < 8000, `${code.length} bytes`)
check('包含 Instagram 選擇器', code.includes('instagram'))
check('包含小紅書選擇器', code.includes('xiaohongshu'))
check('有 clipboard 寫入', code.includes('clipboard.writeText'))
check('有 fallback（剪貼簿唔得時彈 textarea）', code.includes('textarea'))

// ══ ⚠️⚠️ 最重要嘅防 regression 測試 ══
//    曾經出現過：書籤原始碼用 `//` 行註解，壓縮成一行之後
//    個 `//` 吞掉成行後面所有程式碼 → 成個書籤小工具壞掉
//    （SyntaxError: Unexpected end of input），但語法檢查捉唔到。
console.log('\n▸ ⚠️ 防 regression：壓縮之後一定要可以執行')
{
  // 真瀏覽器會點做：new Function(code) 睇下跑唔跑得
  let ok = true, err = null
  try {
    new Function(code.replace(/^javascript:/, ''))
  } catch (e) { ok = false; err = e.message }
  check('new Function() 成功（真瀏覽器執行得）', ok, err || '')

  // 明確檢查：一行註解唔可以吞掉後面嘅碼
  const body = code.replace(/^javascript:/, '')
  const afterComment = body.split('//').length
  check('壓縮後係一行', !body.includes('\n'))
  check('冇剩低未閉合嘅 // 註解', afterComment <= 1 || !/(^|[^:])\/\/[^\n]*$/.test(body.split('\n')[0]))

  // 關鍵函式一定要喺壓縮後仲存在
  check('壓縮後仲有 querySelector', body.includes('querySelector'))
  check('壓縮後仲有 writeText', body.includes('writeText'))
  check('壓縮後仲有 Instagram 分支', body.includes('instagram'))
  check('壓縮後仲有封尾 })();', body.trim().endsWith('})();'))
}

console.log(`\n${'═'.repeat(50)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(50))
process.exit(fail ? 1 : 0)
