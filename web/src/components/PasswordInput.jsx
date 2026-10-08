import { useState } from 'react'
import PixelIcon from './PixelIcon'

/**
 * 密碼欄（連眼仔）
 * =================
 *
 * ⚠️⚠️ 用戶要求：
 *   「設定密碼嗰個應該係隔離正常係會有一個眼仔，
 *    俾你去睇個密碼係咪正確？即係個眼仔就係你撳一下
 *    就會 show 密碼，再撳多一下就會唔 show 個密碼。」
 *
 * ⚠️ 為咩眼仔唔係「裝飾」而係**必要**：
 *   · 密碼打錯自己睇唔到 → 用戶會以為「個 app 壞咗」，
 *     然後去試第啲密碼 → 甚至以為帳號被鎖（我哋收過呢種反饋）
 *   · 手機自動首字母大寫 → 「Icychan」vs「icychan」睇唔出
 *   · 「再打一次」對唔上嗰陣，冇眼仔根本冇得查
 *   · 密碼管理器填入嘅值可能多咗空格
 *
 * ⚠️⚠️ 呢個元件一定要喺**模組層** ——
 *    如果喺 render 入面定義，每次 render 都係「新元件類型」
 *    → React unmount + remount → **每次打字都失焦**。
 *    （我哋就係因為呢個原因收到「打密碼要逐個字撳」嘅反饋。）
 *
 * ⚠️ 用 `type="button"` ——
 *    如果呢個元件喺 `<form>` 入面而個掣係預設 type，
 *    撳眼仔會**提交表單**（= 用未打完嘅密碼登入）。
 */
export default function PasswordInput({
  value, onChange, placeholder, autoComplete, autoFocus, disabled,
  style, inputMode,
}) {
  const [show, setShow] = useState(false)

  return (
    <div className="pw-wrap" style={style}>
      <input
        className="input pw-input"
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        disabled={disabled}
        inputMode={inputMode}
        // ⚠️ 唔可以俾瀏覽器／輸入法自動首字母大寫 ——
        //    密碼係大細階敏感，自動大寫 = 靜靜改咗你個密碼。
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
      />
      <button
        type="button"
        className="pw-eye"
        onClick={() => setShow(s => !s)}
        disabled={disabled}
        // ⚠️ 無障礙：讀屏要知「而家係顯示定隱藏」
        aria-label={show ? '隱藏密碼' : '顯示密碼'}
        aria-pressed={show}
        title={show ? '隱藏密碼' : '顯示密碼'}
      >
        <PixelIcon name={show ? 'eyeoff' : 'eye'} size={17} />
      </button>
    </div>
  )
}
