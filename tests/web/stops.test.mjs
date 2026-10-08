/**
 * 多城市行程邏輯測試
 * ==================
 * ⚠️ 最重要嘅斷言：**過渡日唔算衝突**（用戶明確要求）。
 *    福岡 4 日 + 首爾 3 日 → Day 4/5 交界，兩邊行程都合理。
 */
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'

const src = fs.readFileSync(new URL('../../web/src/lib/stops.js', import.meta.url), 'utf8')
const sandbox = { console, Map, Set, Array, String, Number, Math, Boolean, Object }
sandbox.globalThis = sandbox
vm.createContext(sandbox)
vm.runInContext(src.replace(/^export\s+/gm, ''), sandbox)
const { buildDayCities, cityMatches, findConflicts, checkItemConflict, stopsSummary } = sandbox

let pass = 0, fail = 0
const check = (label, cond, extra = '') => {
  console.log(`  ${cond ? '✓' : '✗'} ${label}${extra ? '  ' + extra : ''}`)
  cond ? pass++ : fail++
}

const item = (id, day, props = {}) => ({
  id, day_index: day, name: id, ...props,
})

// ══ 日子 ↔ 城市 ══
console.log('\n▸ 日子分配')
{
  const stops = [{ city: '福岡', days: 4 }, { city: '首爾', days: 3 }]
  const days = buildDayCities(stops, 7)
  const by = Object.fromEntries(days.map(d => [d.day, d]))
  check('總共 7 日', days.length === 7, `實際 ${days.length}`)
  check('Day 1 = 福岡', by[1].cities.includes('福岡'))
  check('Day 4 = 福岡', by[4].cities.includes('福岡'))
  check('Day 5 = 首爾', by[5].cities.includes('首爾'))
  check('Day 7 = 首爾', by[7].cities.includes('首爾'))
  check('Day 1 唔係過渡日', by[1].transition === false)
  check('Day 4 係過渡日（交界）', by[4].transition === true)
  check('Day 5 係過渡日（交界）', by[5].transition === true)
  check('Day 7 唔係過渡日', by[7].transition === false)
}

console.log('\n▸ 三個城市')
{
  const stops = [{ city: '福岡', days: 2 }, { city: '首爾', days: 2 }, { city: '釜山', days: 2 }]
  const by = Object.fromEntries(buildDayCities(stops, 6).map(d => [d.day, d]))
  check('Day 1-2 = 福岡', by[1].cities[0] === '福岡' && by[2].cities[0] === '福岡')
  check('Day 3-4 = 首爾', by[3].cities[0] === '首爾' && by[4].cities[0] === '首爾')
  check('Day 5-6 = 釜山', by[5].cities[0] === '釜山' && by[6].cities[0] === '釜山')
  check('Day 2 同 Day 3 都係過渡', by[2].transition && by[3].transition)
  check('Day 4 同 Day 5 都係過渡', by[4].transition && by[5].transition)
  check('Day 1 唔係過渡', !by[1].transition)
}

// ══ 城市名比對 ══
console.log('\n▸ 城市名比對')
check('福岡 ↔ 福岡市', cityMatches('福岡', '福岡市'))
check('福岡縣 ↔ 福岡', cityMatches('福岡県', '福岡'))
check('首爾 ↔ 서울（唔應該配到）', !cityMatches('首爾', '서울'))
check('福岡 ↔ 東京', !cityMatches('福岡', '東京'))
check('空字串', !cityMatches('', '福岡'))

// ══ 衝突偵測 ══
console.log('\n▸ 衝突偵測')
{
  const stops = [{ city: '福岡', days: 4 }, { city: '首爾', days: 3 }]
  const items = [
    item('博多拉麵', 1, { city: '福岡', district: '博多', location_path: ['日本', '福岡県', '博多区'] }),
    item('明洞烤肉', 5, { city: '首爾', district: '明洞', location_path: ['韓國', '明洞'] }),
    item('首爾cafe', 2, { city: '首爾', district: '弘大', location_path: ['韓國', '弘大'] }),   // ← 錯！Day 2 應該喺福岡
  ]
  const cf = findConflicts(items, stops, 7)
  const ids = cf.map(c => c.item.id)
  check('正確嘅行程唔報衝突', !ids.includes('博多拉麵'))
  check('首爾行程排喺首爾日唔報衝突', !ids.includes('明洞烤肉'))
  check('首爾行程排喺福岡日 → 報衝突', ids.includes('首爾cafe'), `實際 ${JSON.stringify(ids)}`)
  check('衝突有解釋原因', cf[0]?.reason?.includes('福岡') && cf[0]?.reason?.includes('弘大'))
}

// ══ ⭐ 過渡日唔算衝突 ══
console.log('\n▸ ⭐ 過渡日（用戶核心要求）')
{
  const stops = [{ city: '福岡', days: 4 }, { city: '首爾', days: 3 }]
  // Day 4 = 福岡最後一日（過渡）；Day 5 = 首爾第一日（過渡）
  const items = [
    item('福岡景點排Day4', 4, { city: '福岡', location_path: ['福岡県', '博多区'] }),
    item('首爾景點排Day4', 4, { city: '首爾', location_path: ['韓國', '明洞'] }),   // 早一晚飛過去／或者同日飛
    item('福岡景點排Day5', 5, { city: '福岡', location_path: ['福岡県', '中洲'] }), // 朝早先走
    item('首爾景點排Day5', 5, { city: '首爾', location_path: ['韓國', '弘大'] }),
  ]
  const cf = findConflicts(items, stops, 7)
  check('過渡日：兩邊城市嘅行程都唔報衝突', cf.length === 0,
    cf.length ? JSON.stringify(cf.map(c => c.item.id)) : '')
}

// ══ 冇地區資料唔應該報 ══
console.log('\n▸ 資料不足時唔報（避免誤報）')
{
  const stops = [{ city: '福岡', days: 4 }, { city: '首爾', days: 3 }]
  const items = [item('神秘景點', 5, {})]
  const cf = findConflicts(items, stops, 7)
  check('完全冇地區資料 → 唔報衝突', cf.length === 0)
  const items2 = [item('有address', 2, { address: '福岡県福岡市博多区中洲5-3-2' })]
  const cf2 = findConflicts(items2, stops, 7)
  check('靠 address 都判斷到（唔會誤報）', cf2.length === 0)
}

// ══ 單城市 ══
console.log('\n▸ 單一城市（常見情況）')
{
  const stops = [{ city: '福岡', days: 5 }]
  const by = Object.fromEntries(buildDayCities(stops, 5).map(d => [d.day, d]))
  check('5 日都係福岡', [1,2,3,4,5].every(d => by[d].cities[0] === '福岡'))
  check('冇過渡日', [1,2,3,4,5].every(d => !by[d].transition))
  const cf = findConflicts([
    item('福岡店', 1, { city: '福岡' }),
    item('東京店', 3, { city: '東京', location_path: ['東京都', '台東区'] }),
  ], stops, 5)
  check('唔屬於任何城市嘅行程 → 報衝突', cf.length === 1 && cf[0].item.id === '東京店')
}

// ══ 摘要 ══
console.log('\n▸ 摘要文字')
check('摘要格式', stopsSummary([{ city: '福岡', days: 4 }, { city: '首爾', days: 3 }])
  === '福岡 4日 → 首爾 3日')

console.log(`\n${'═'.repeat(50)}`)
console.log(`  ${pass} 通過 / ${fail} 失敗`)
console.log('═'.repeat(50))
process.exit(fail ? 1 : 0)
