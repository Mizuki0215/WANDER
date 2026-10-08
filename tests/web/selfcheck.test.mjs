/**
 * 「唔可以加自己做朋友」測試
 * ============================
 * ⚠️⚠️ 用戶要求：
 *   「如果當自己 scan 到自己嘅 QR code 嘅話，
 *    應該係知道係自己嚟嘅，
 *    咁應該你就要同佢講就話『唔可以加自己做朋友』。」
 *
 * ⚠️ 呢個測試同時守住「有冇喺所有入口都檢查」：
 *     ① 設定頁「我嘅 QR」→ 掃人哋
 *     ② 朋友頁「掃 QR」
 *     ③ 朋友頁打 @名（即時預覽）
 *     ④ Deep link ?add=（手機原生相機掃自己）
 */
import fs from 'node:fs'

const ROOT = new URL('../../', import.meta.url)
let pass = 0, fail = 0
const check = (label, cond, extra = '') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

const read = (p) => fs.readFileSync(new URL(p, ROOT), 'utf8')

// ══ ① 共用函數嘅邏輯 ══
console.log('\n▸ isSelf 邏輯')
{
  const src = read('web/src/lib/selfcheck.js')
  // 抽出函數體做真測試
  const isSelf = (scanned, me) => {
    const a = String(scanned || '').trim().replace(/^@/, '').toLowerCase()
    const b = String(me?.username || '').trim().replace(/^@/, '').toLowerCase()
    if (!a || !b) return false
    return a === b
  }
  const cases = [
    ['alice99', { username: 'alice99' }, true, '完全相同'],
    ['@alice99', { username: 'alice99' }, true, '前面有 @'],
    ['ALICE99', { username: 'alice99' }, true, '大寫'],
    ['@Alice99', { username: 'alice99' }, true, '@ + 大寫'],
    ['  alice99  ', { username: 'alice99' }, true, '有空格'],
    ['bob2026', { username: 'alice99' }, false, '唔同人'],
    ['alice99', { username: null }, false, '我未設 username'],
    ['alice99', {}, false, 'me 冇 username 欄'],
    ['', { username: 'alice99' }, false, '空字串'],
    [null, { username: 'alice99' }, false, 'null'],
  ]
  for (const [a, b, want, label] of cases) {
    const got = isSelf(a, b)
    check(label, got === want, `→ ${got}`)
  }
  // ⚠️ 一定要用共用函數（唔可以兩處各寫一份）
  check('有 export isSelf', src.includes('export function isSelf'))
  check('有統一訊息 SELF_MSG', src.includes("SELF_MSG = '唔可以加自己做朋友'"))
  check('訊息係用戶要嘅字眼', src.includes('唔可以加自己做朋友'))
}

// ══ ② 每個入口都要檢查 ══
console.log('\n▸ 所有入口都要檢查自己')
{
  const myqr = read('web/src/components/MyQr.jsx')
  check('① 設定頁「我嘅 QR」→ 掃人哋', myqr.includes('isSelf(r.username, user)'))
  check('   掃到自己顯示訊息', myqr.includes('SELF_MSG'))
  check('   有自己嗰張提示卡', myqr.includes('selfHit'))

  const fr = read('web/src/components/Friends.jsx')
  check('② 朋友頁「掃 QR」', fr.includes('isSelf(r.username, me)'))
  check('③ 朋友頁打 @名（即時）', fr.includes('isSelf(u, me)'))
  check('   收到 me prop', /export default function Friends\(\{[^}]*\bme\b/.test(fr))
  check('   顯示 SELF_MSG', fr.includes('SELF_MSG'))

  const app = read('web/src/App.jsx')
  check('④ Deep link ?add=', app.includes('isSelf(pendingAdd, user)'))
  check('   傳 me 落 Friends', app.includes('me={user}'))

  // ⚠️⚠️ 檢查一定要喺「動作」之前 ——
  //    否則會照樣複製 @自己 然後叫你去加自己
  const myqrScan = myqr.slice(myqr.indexOf('async function scan'))
  const iSelf = myqrScan.indexOf('isSelf(')
  const iFound = myqrScan.indexOf('onFound?.(')
  check('設定頁：檢查喺 onFound 之前',
    iSelf > 0 && iFound > 0 && iSelf < iFound, `self@${iSelf} found@${iFound}`)
}

// ══ ③ 後端都要擋（前端檢查可以被繞過）══
console.log('\n▸ 後端都要擋')
{
  const srv = read('server/app/main.py')
  const i = srv.indexOf('def send_friend_request')
  const blk = srv.slice(i, i + 2000)
  check('後端有擋「加自己」', /唔可以加自己/.test(blk))
  // ⚠️ 唔可以只靠前端 —— curl 可以繞過
  check('後端錯誤訊息一致', blk.includes('唔可以加自己做朋友'))
}

// ══ ④ QR 每個 account 都唔同 ══
console.log('\n▸ QR 唯一性（設計層面）')
{
  const srv = read('server/app/main.py')
  const i = srv.indexOf('def my_qr')
  const blk = srv.slice(i, i + 1400)
  // ⚠️ QR 一定要用 username（唯一）而唔係 email 或者其他可撞嘅嘢
  check('QR 用 username（唯一）', blk.includes('username'))
  check('QR URL 用 ?add=', blk.includes('/?add='))
  // ⚠️ 唔可以將 token / email 放入 QR
  check('QR 唔含 token', !/token=/.test(blk))
  check('QR 唔含 email', !/\?.*email=/.test(blk))
}

console.log(`\n${'═'.repeat(54)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(54))
process.exit(fail ? 1 : 0)
