/**
 * 「呢個係唔係我自己？」判斷
 * ============================
 * ⚠️⚠️ 用戶要求：
 *   「如果當自己 scan 到自己嘅 QR code 嘅話，
 *    應該係要知道係自己嚟嘅，
 *    咁應該你就要同佢講就話『唔可以加自己做朋友』。」
 *
 * ⚠️ 為咩要**共用一個函數**而唔係兩處各寫一份：
 *   而家有兩個地方會掃 QR（設定頁「我嘅 QR」、朋友頁「掃 QR」），
 *   將來可能仲有第三個（例如 deep link）。
 *   兩處各寫一份嘅話，一定會有一邊改漏 —— 例如將來
 *   username 支援大寫，就會有一邊忘記 toLowerCase。
 */

/**
 * @param {string} scanned  掃到嘅 username（可能帶 @）
 * @param {object} me       我嘅 user 物件（有 username 欄位）
 * @returns {boolean}
 */
export function isSelf(scanned, me) {
  const a = String(scanned || '').trim().replace(/^@/, '').toLowerCase()
  const b = String(me?.username || '').trim().replace(/^@/, '').toLowerCase()
  // ⚠️ 如果我未設 username，就唔可能判斷 —— 回 false（當佢唔係自己）
  if (!a || !b) return false
  return a === b
}

/** 掃到自己嗰陣嘅標準訊息（統一講法）。 */
export const SELF_MSG = '唔可以加自己做朋友'
export const SELF_HINT = '呢個係你自己嘅 QR Code'
