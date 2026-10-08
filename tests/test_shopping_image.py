"""
購物清單：加唔到 item（用戶報）
================================

⚠️⚠️ 用戶原話（附手機截圖）：
   「加唔到 item 入 shoppinglist」

截圖見到：
   · 購物清單填好晒（名 "rjdnrb" + 價錢 1000 + 相）
   · 撳「＋」→ 個掣變灰
   · 清單**仲係空嘅**（「購物清單空嘅」）

⚠️ 根因有兩個（都係真 bug）：

   ① `fetch` **冇 timeout**
      → 上傳 4MB base64 相經 5G + tunnel → 卡住
      → `busy` 永遠 `true` → 個掣永遠 disabled
      → 用戶以為「加唔到」，其實係等緊一個永遠唔完嘅請求

   ② `add()` **等相上傳完先加 item**
      → 4MB 相要成分鐘 → 用戶以為壞咗

   ③ 後端 `INSERT` **漏咗 `image` 欄**
      → schema 有、前端有送，但相片無聲無息咁消失

   ④ `PATCH /api/shopping/{id}` 唔支援 `image`
      → 冇得補相
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

WEB = ROOT / "web" / "src"


def code(path: Path) -> str:
    """剝走註解（我嘅解釋註解好易 match 到自己）。"""
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"`])//.*$', '', line)
        s = re.sub(r'/\*.*?\*/', '', s)
        if s.strip().startswith(('*', '/*')):
            continue
        out.append(s)
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════
# ① fetch 逾時
# ══════════════════════════════════════════════════════════════

class TestFetchTimeout:
    def test_has_timeout_constants(self):
        s = code(WEB / "lib" / "api.js")
        assert "TIMEOUT_MS" in s, "冇請求逾時常數"
        assert "UPLOAD_TIMEOUT_MS" in s, "冇上傳逾時常數（上傳要長啲）"

    def test_uses_abort_controller(self):
        """
        ⚠️⚠️ 核心修法 —— `fetch` 一定要有 `signal`。
           唔係嘅話網絡卡住就會**永遠等**。
        """
        s = code(WEB / "lib" / "api.js")
        assert "AbortController" in s, "冇 AbortController"
        assert "ctl.abort()" in s, "冇叫 abort()"
        assert "signal: ctl.signal" in s, "fetch 冇帶 signal"

    def test_clears_timer(self):
        """
        ⚠️ 一定要 `clearTimeout` ——
           唔係嘅話每個請求都留一個 timer（愈積愈多）。
        """
        s = code(WEB / "lib" / "api.js")
        assert "clearTimeout(timer)" in s, "冇 clearTimeout"
        # ⚠️ 要喺 finally（連 error path 都清）
        i = s.index("clearTimeout(timer)")
        assert "finally" in s[max(0, i - 200):i], "clearTimeout 唔喺 finally"

    def test_distinguishes_timeout_from_cancel(self):
        """⚠️ 要分清「逾時」同「用戶自己取消」（AbortError）。"""
        s = code(WEB / "lib" / "api.js")
        assert "AbortError" in s, "冇分辨 AbortError"
        assert "逾時" in code(WEB / "lib" / "api.js") or "逾時" in \
            (WEB / "lib" / "api.js").read_text(encoding="utf-8"), "冇「逾時」訊息"

    def test_upload_uses_longer_timeout(self):
        s = code(WEB / "lib" / "api.js")
        i = s.index("upload:")
        blk = s[i:i + 200]
        assert "UPLOAD_TIMEOUT_MS" in blk, "上傳冇用長啲嘅 timeout"

    def test_network_error_message_is_friendly(self):
        """⚠️ 「Failed to fetch」對用戶冇意義。"""
        s = code(WEB / "lib" / "api.js")
        assert "連唔到伺服器" in s, "冇友善嘅網絡錯誤訊息"


# ══════════════════════════════════════════════════════════════
# ② 先加 item，後補相
# ══════════════════════════════════════════════════════════════

class TestAddDoesNotBlockOnPhoto:
    def test_adds_item_before_upload(self):
        """
        ⚠️⚠️ 核心：`addShopping` 一定要**喺 `api.upload` 之前**。
           唔係嘅話用戶要等成分鐘先見到 item。
        """
        s = code(WEB / "components" / "ShoppingList.jsx")
        i = s.index("async function add()")
        blk = s[i:i + 2600]
        i_add = blk.index("api.addShopping")
        i_up = blk.index("api.upload")
        assert i_add < i_up, "仲係等上傳完先加 item（用戶要等成分鐘）"

    def test_unlocks_button_before_upload(self):
        """
        ⚠️⚠️ 掣要**即刻**解鎖 —— 唔可以等上傳。
           呢個就係用戶見到「個掣變灰郁都唔郁」嘅原因。
        """
        s = code(WEB / "components" / "ShoppingList.jsx")
        i = s.index("async function add()")
        blk = s[i:i + 2600]
        i_up = blk.index("api.upload")
        # ⚠️ upload 之前一定要有 setBusy(false)
        assert "setBusy(false)" in blk[:i_up], \
            "上傳之前冇解鎖個掣（會變灰）"

    def test_patches_image_after_upload(self):
        """⚠️ 上傳完要 patch 返個 item（唔係就算數）。"""
        s = code(WEB / "components" / "ShoppingList.jsx")
        i = s.index("async function add()")
        blk = s[i:i + 2600]
        assert "api.updateShopping" in blk, "上傳完冇 patch 返個 item"
        assert "image: url" in blk, "patch 冇帶 image"

    def test_photo_failure_says_item_was_added(self):
        """
        ⚠️⚠️ 相上傳失敗嘅訊息要講**「item 加咗，只係相冇」**——
           唔係嘅話用戶會以為成項都冇加到（再次報「加唔到」）。
        """
        s = code(WEB / "components" / "ShoppingList.jsx")
        i = s.index("async function add()")
        blk = s[i:i + 2600]
        assert "加咗，但相片上傳失敗" in blk, \
            "相失敗嘅訊息冇講「item 已經加咗」"

    def test_returns_early_if_item_fails(self):
        """⚠️ item 都加唔到就唔應該繼續上傳相（浪費時間）。"""
        s = code(WEB / "components" / "ShoppingList.jsx")
        i = s.index("async function add()")
        blk = s[i:i + 2600]
        # ⚠️ catch 之後要有 return
        i_catch = blk.index("} catch (e) {")
        assert "return" in blk[i_catch:i_catch + 200], \
            "加 item 失敗仲繼續上傳相"


# ══════════════════════════════════════════════════════════════
# ③ 後端一定要存 image
# ══════════════════════════════════════════════════════════════

class TestBackendSavesImage:
    @pytest.fixture(scope="class")
    def srv(self):
        return (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")

    def test_schema_has_image(self):
        """⚠️ 先確認 schema 真係有呢個欄（唔係就要 migration）。"""
        db = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        i = db.index("CREATE TABLE IF NOT EXISTS shopping_items")
        # ⚠️ 唔可以用 `db.index(")", i)` ——
        #    `REFERENCES trips(id)` 有個 `)`，會截斷得太早。
        #    用 ");"（statement 結尾）先啱。
        j = db.index(");", i)
        blk = db[i:j]
        assert "image" in blk, "schema 冇 image 欄"
        assert "created_by" in blk, "block 截斷錯（搵唔到 created_by）"

    def test_has_migration_for_old_dbs(self):
        """
        ⚠️⚠️ 舊資料庫（已經建咗表）唔會自動加新欄 ——
           一定要有 migration，唔係嘅話舊用戶 INSERT 會爆。
        """
        db = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        assert '"shopping_items", "image"' in db or \
               "'shopping_items', 'image'" in db, \
            "冇 shopping_items.image 嘅 migration（舊 DB 會爆）"

    def test_insert_writes_image(self, srv):
        """
        ⚠️⚠️ 真 bug：schema 有、前端有送，但 `INSERT` 漏咗個欄
           → 相片**無聲無息**咁消失。
        """
        i = srv.index("def add_shopping(")
        blk = srv[i:i + 1800]
        # ⚠️ 唔可以寫死 `created_by, image)` ——
        #    後來加咗 `currency` 欄（INSERT 欄位清單你會改）。
        #    改用 regex 檢查 image 真係喺欄位清單入面。
        m = re.search(r"INSERT INTO shopping_items\s*\(([^)]+)\)", blk)
        assert m, "搵唔到 INSERT 欄位清單"
        cols = [c.strip() for c in m.group(1).split(",")]
        assert "image" in cols, f"INSERT 冇 image 欄（欄位：{cols}）"
        assert "currency" in cols, f"INSERT 冇 currency 欄（欄位：{cols}）"
        assert 'body.get("image")' in blk, "INSERT 冇攞 body 嘅 image"

    def test_patch_supports_image(self, srv):
        """⚠️ 前端要「之後補相」→ PATCH 一定要支援 image。"""
        i = srv.index("def update_shopping(")
        blk = srv[i:i + 1200]
        assert '"image" in body' in blk, "PATCH 唔支援 image"

    def test_patch_image_empty_clears(self, srv):
        """⚠️ 空字串 = 移除相片（唔係「唔改」）。"""
        i = srv.index("def update_shopping(")
        blk = srv[i:i + 1400]
        assert "or None" in blk, "空字串應該變 NULL（清除相片）"


# ══════════════════════════════════════════════════════════════
# ④ UI scroll：導航高度 vs 內容 padding
# ══════════════════════════════════════════════════════════════

class TestNavHeightMeasured:
    """
    ⚠️⚠️ 用戶報：「UI scroll 有啲怪」——
       手機截圖見到最底嘅「未排入行程」托盤**被底部導航切走**。

       ⚠️ 根因：CSS 寫死 `--nav-h: 62px`，但實際高度會變：
         · 「HOME」+「主畫面」兩個 span → **兩行**
           （截圖證實：第一格兩行，其他一格一行）
         · 用戶調大系統字體
         · 窄機（320px）label 換行
         · 瀏海機 safe-area
       → 實際 ~80px 但 padding 只留 62px → 內容被切。

       ✅ 修法：`ResizeObserver` **量度真實高度**寫入 `--nav-h`。
          ⚠️ 唔可以「改成 80px」—— 另一部機會再錯。
    """

    def test_app_measures_nav(self):
        s = code(WEB / "App.jsx")
        assert "navRef" in s, "冇 nav 嘅 ref"
        assert "ResizeObserver" in s, "冇量度真實高度"
        assert "getBoundingClientRect().height" in s, "冇攞高度"

    def test_uses_callback_ref_not_hook(self):
        """
        ⚠️⚠️ 一定要用**回呼 ref**，唔可以用 `useRef` + `useEffect`。

           原因：呢個 component 有**條件 return**
              （`if (booting)` / `if (!user)`），
              但 `isHome`（決定有冇 nav）喺條件 return **之後**才定義。

              · 擺前面 → `Cannot access 'isHome' before initialization`
              · 擺後面 → `Rendered more hooks than during the previous render`

           ⚠️ 兩個我都實測爆過。回呼 ref 完全唔使 hook → 冇呢個問題。
        """
        s = code(WEB / "App.jsx")
        # ⚠️ 唔可以有 `useRef(null)` 畀 nav（我哋用 useCallback）
        assert "const navRef = useCallback(" in s or \
               "navRef = useCallback(" in s, "navRef 唔係回呼 ref"
        # ⚠️ 唔可以有依賴 isHome 嘅 hook
        assert "[isHome, tab]" not in s, "仲有依賴 isHome 嘅 hook"

    def test_resizeobserver_guarded(self):
        """
        ⚠️⚠️ `ResizeObserver` 唔存在喺舊 Safari / jsdom ——
           冇檢查就會爆 `ReferenceError` → **成個 app 白畫面**。
           （實測 dom.test.mjs 即刻爆咗。）
        """
        s = code(WEB / "App.jsx")
        assert "typeof ResizeObserver === 'undefined'" in s, \
            "冇檢查 ResizeObserver 存在"
        i = s.index("typeof ResizeObserver")
        blk = s[i:i + 700]
        assert "addEventListener('resize'" in blk, "退化路徑冇聽 resize"
        assert "return" in blk, "退化之後冇 return"

    def test_cleanup_stored_in_ref(self):
        """
        ⚠️ React 18 嘅回呼 ref **唔支援 return cleanup** ——
           cleanup 要自己存（React 19 才有）。
        """
        s = code(WEB / "App.jsx")
        assert "navCleanup" in s, "冇存 cleanup"
        assert "navCleanup.current()" in s, "卸載時冇叫 cleanup"

    def test_writes_nav_h_variable(self):
        s = code(WEB / "App.jsx")
        assert "setProperty('--nav-h'" in s, "冇寫入 --nav-h"

    def test_observes_not_just_once(self):
        """
        ⚠️ 一定要 `observe` —— 唔係嘅話字體載入 / 轉向 /
           label 換行都唔會重新量度。
        """
        s = code(WEB / "App.jsx")
        assert "ro.observe(el)" in s, "冇 observe（只量一次）"
        assert "ro.disconnect()" in s, "冇 disconnect（memory leak）"

    def test_nav_has_ref(self):
        s = code(WEB / "App.jsx")
        assert 'nav className="nav" ref={navRef}' in s, "nav 冇掛 ref"

    def test_zero_when_no_nav(self):
        """
        ⚠️ 主畫面冇 nav → `--nav-h` 應該係 0，
           唔係嘅話會留一段空白。
        """
        s = code(WEB / "App.jsx")
        assert "setProperty('--nav-h', '0px')" in s, \
            "冇 nav 嗰陣冇設 0px"

    def test_handles_orientation_change(self):
        """⚠️ 轉向會改高度。"""
        s = code(WEB / "App.jsx")
        assert "orientationchange" in s, "冇處理轉向"

    def test_cleans_up(self):
        """
        ⚠️ 一定要清 —— 唔係嘅話每次 tab 切換都留一個 observer。
        """
        s = code(WEB / "App.jsx")
        i = s.index("ResizeObserver")
        blk = s[max(0, i - 600):i + 900]
        assert "removeProperty('--nav-h')" in blk, "冇清走 --nav-h"
        assert "removeEventListener" in blk, "冇清 event listener"

    def test_screen_uses_nav_h(self):
        """
        ⚠️ 內容嘅 padding 一定要用 `var(--nav-h)` ——
           寫死數字嘅話量度到都冇用。
        """
        css = (WEB / "styles.css").read_text(encoding="utf-8")
        css = re.sub(r"/\*[\s\S]*?\*/", "", css)
        i = css.index(".screen {")
        blk = css[i:css.index("}", i) + 1]
        assert "var(--nav-h)" in blk, ".screen padding 冇用 var(--nav-h)"


# ══════════════════════════════════════════════════════════════
# ⑤ 朋友請求：收件者撳唔到接受？
# ══════════════════════════════════════════════════════════════

class TestFriendRequestUx:
    """
    ⚠️⚠️ 用戶報：
       「我用另一個帳號加朋友，然後我登入返另一個帳號呢
        都係show緊待確認囉，被邀請嗰個人冇得撳接受呢個掣。」

    ⚠️ 實測 **API 完全正常**：
       · 收件者 `/api/friends` 真係有 `incoming` + `request_id`
       · 撳 accept → 兩邊都成為朋友
       → 用戶當時睇到嘅「等對方確認」係**發出方** section，
         即係 login 咗做發送者，唔係收件者。

    ✅ 修法（令佢唔可能再撈亂）：
       ① 頂部明確顯示「你而家登入緊 @邊個」
       ② 收到嘅請求用 neon 大字提示
       ③ incoming / outgoing section 標題清楚分開
       ④ 切返 app 自動重新載入（stale state）
    """

    @pytest.fixture(scope="class")
    def fr(self):
        return code(WEB / "components" / "Friends.jsx")

    def test_shows_who_you_are(self, fr):
        """
        ⚠️⚠️ 最重要嘅修法 —— 用戶要即刻知自己 login 咗做邊個。
        """
        assert "你而家登入緊" in fr, "冇顯示「你而家登入緊邊個」"
        # ⚠️ 要顯示 @username（用戶用 @名加朋友，唔係 email）
        assert "me.username" in fr, "冇顯示 @帳號名"

    def test_loud_incoming_banner(self, fr):
        """⚠️ 收到嘅請求要**大聲** —— 唔可以同「發出嘅」睇落一樣。"""
        assert "想加你做朋友" in fr, "冇大聲嘅 incoming 提示"
        assert "要你撳「接受」" in fr, "冇講要撳接受"

    def test_sections_clearly_labelled(self, fr):
        """⚠️ 兩個 section 標題要一眼分得出。"""
        assert "📥 收到嘅請求" in fr, "incoming section 標題唔清楚"
        assert "📤 你發出嘅" in fr, "outgoing section 標題唔清楚"
        # ⚠️ 唔可以再用「等對方確認」做 section 標題
        assert '<div className="sec">等對方確認' not in fr, \
            "仲用「等對方確認」做 section 標題（用戶就係咁撈亂）"

    def test_outgoing_says_waiting_for_them(self, fr):
        """⚠️ outgoing 要講「等**佢**撳」，唔係「待確認」。"""
        assert "等佢撳" in fr, "outgoing 冇講「等佢撳」"
        assert "等對方撳接受" in fr, "outgoing section 冇講等對方"

    def test_accept_button_exists(self, fr):
        """⚠️ 收件者一定要有「接受」掣。"""
        assert "acceptFriend" in fr, "冇 acceptFriend"
        assert ">接受</button>" in fr or "接受</button>" in fr, "冇「接受」掣"
        assert ">拒絕</button>" in fr or "拒絕</button>" in fr, "冇「拒絕」掣"

    def test_manual_refresh_button(self, fr):
        """⚠️ 要有一個手動重新載入掣（用戶可以自己 refresh）。"""
        assert "onClick={load}" in fr, "冇手動重新載入掣"
        assert 'title="重新載入朋友同請求"' in fr, "冇 tooltip"

    def test_refetches_on_wake(self, fr):
        """
        ⚠️⚠️ PWA 由背景切返嚟要自動 reload ——
           唔係嘅話會顯示 stale data（另一個帳號撳咗接受都唔知）。
        """
        assert "visibilitychange" in fr, "冇監聽 visibilitychange"
        assert "'focus'" in fr or '"focus"' in fr, "冇監聽 focus"
        assert "removeEventListener" in fr, "冇清 event listener"

    def test_backend_has_request_id(self):
        """
        ⚠️ 後端 `/api/friends` 一定要回 `request_id` ——
           冇嘅話前端撳接受唔知撳邊個。
           （⚠️ 舊 bug：`id` 同時係請求 id 同用戶 id → 前端攞錯。）
        """
        srv = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = srv.index("def list_friends(")
        blk = srv[i:i + 1800]
        assert "AS request_id" in blk, "冇 request_id"
        assert "AS user_id" in blk, "冇 user_id（會同 id 撞）"


# ══════════════════════════════════════════════════════════════
# ⑥ 日數輸入（手機剷唔到個「1」）+ 刪「目的地」欄
# ══════════════════════════════════════════════════════════════

class TestDaysInput:
    """
    ⚠️⚠️ 用戶報（附手機截圖）：
       「我用電腦版，嗰日數係可以撳掣增加／減少；但係手機版嘅話呢，
        我想修改日子嘅話呢，我係唔可以剷咗個『1』⋯變相我只可以改
        個數字就係之後嘅數字，導致到我每次入日子我都係入十幾。」

    ⚠️ 根因兩個：
       ① `Number(v) || 1` → 空字串變 1 → **剷唔到**
       ② `<input type="number">` 嘅 ▲▼ 箭嘴**手機冇**
    """

    @pytest.fixture(scope="class")
    def se(self):
        return code(WEB / "components" / "StopsEditor.jsx")

    def test_no_number_or_one_pattern(self, se):
        """
        ⚠️⚠️ 核心：`Number(v) || 1` 呢個 pattern 一定要消失 ——
           空字串 → 0 → `0 || 1` → 1 → 剷唔到。
        """
        i = se.index("function setDays(")
        blk = se[i:i + 500]
        assert "Number(v) || 1" not in blk, \
            "仲有 `Number(v) || 1`（空字串會變 1 → 剷唔到）"

    def test_has_days_input_component(self, se):
        assert "function DaysInput(" in se, "冇 DaysInput 元件"

    def test_days_input_is_module_level(self, se):
        """
        ⚠️ 一定要喺**模組層** —— 喺 render 入面定義會令
           React 每次 render 當佢係新元件 → 輸入框每打一個字就失焦。
        """
        # ⚠️ 喺 `export default function StopsEditor` 之前
        i_comp = se.index("function DaysInput(")
        i_main = se.index("export default function StopsEditor")
        assert i_comp < i_main, "DaysInput 唔喺模組層"

    def test_keeps_raw_string_while_editing(self, se):
        """
        ⚠️⚠️ 關鍵修法：保留**原始字串** ——
           空字串係合法嘅**過渡狀態**，唔可以即刻 clamp。
        """
        assert "setRaw(" in se, "冇保留原始字串"
        assert "raw !== null ? raw :" in se, "冇用 raw 做顯示值"

    def test_onchange_does_not_clamp(self, se):
        """⚠️ `onChange` 唔可以 clamp —— 要原字串照收。"""
        i = se.index("function DaysInput(")
        blk = se[i:i + 2000]
        # ⚠️ onChange 嗰行唔可以有 Math.max/min
        for line in blk.split("\n"):
            if "onChange={e =>" in line and "setRaw" in line:
                assert "Math.max" not in line and "Math.min" not in line, \
                    "onChange 有 clamp → 剷走個數字會即刻彈返"
                break
        else:
            pytest.fail("搵唔到 onChange")

    def test_clamps_on_blur(self, se):
        """⚠️ 離開個欄先 clamp（1–60）。"""
        i = se.index("function DaysInput(")
        blk = se[i:i + 2000]
        assert "onBlur=" in blk, "冇 onBlur"
        assert "function commit(" in blk, "冇 commit 函數"
        assert "Math.max(1, Math.min(max" in blk, "commit 冇 clamp"

    def test_has_plus_minus_buttons(self, se):
        """
        ⚠️⚠️ 手機冇 ▲▼ 箭嘴 → 一定要有**自己嘅 ＋／− 掣**。
           呢個就係用戶講「電腦版可以撳掣」但手機唔得嘅原因。
        """
        i = se.index("function DaysInput(")
        blk = se[i:i + 2400]
        assert "bump(-1)" in blk, "冇「−」掣"
        assert "bump(1)" in blk, "冇「＋」掣"
        assert 'aria-label="少一日"' in blk, "冇 accessible label"
        assert 'aria-label="多一日"' in blk, "冇 accessible label"

    def test_buttons_disable_at_bounds(self, se):
        """⚠️ 1 嘅時候唔可以再減；60 嘅時候唔可以再加。"""
        i = se.index("function DaysInput(")
        blk = se[i:i + 2400]
        assert "disabled={value <= 1}" in blk, "冇擋 0"
        assert "disabled={value >= max}" in blk, "冇擋上限"

    def test_uses_numeric_keyboard(self, se):
        """⚠️ 手機要彈數字鍵盤。"""
        i = se.index("function DaysInput(")
        blk = se[i:i + 2000]
        assert 'inputMode="numeric"' in blk, "冇 inputMode（手機彈唔到數字鍵盤）"

    def test_handles_nan(self, se):
        """⚠️ 清空晒再離開 → 要還原，唔可以留 NaN。"""
        i = se.index("function DaysInput(")
        blk = se[i:i + 2000]
        assert "Number.isNaN(n)" in blk, "冇處理 NaN"


class TestDestinationFieldRemoved:
    """
    ⚠️ 用戶原話：
       「加入去城市嗰度其實取消咗有個叫做目的地嗰個，
        都冇咩用，淨係要加城市咪得囉。」
    """

    def test_no_destination_input(self):
        """⚠️ 新旅程表單唔應該再有「目的地」輸入。"""
        s = (WEB / "components" / "Trips.jsx").read_text(encoding="utf-8")
        assert '<CityPicker value={form.destination}' not in s, \
            "仲有「目的地」CityPicker"

    def test_destination_still_derived_from_first_city(self):
        """
        ⚠️ 刪咗個欄，但 `destination` 一定要繼續有人填 ——
           唔係嘅話地圖／雙時鐘會冇中心。
        """
        s = code(WEB / "components" / "Trips.jsx")
        assert "form.destination" in s, "destination 完全冇人填"
        # ⚠️ 一定要有「用第一個城市」嘅邏輯
        assert "stops[0]?.city" in s or "stops[0].city" in s, \
            "冇用第一個城市做 destination"

    def test_destination_explained_in_comment(self):
        """⚠️ 要解釋為咩刪（唔可以靜靜咁刪）。"""
        s = (WEB / "components" / "Trips.jsx").read_text(encoding="utf-8")
        assert "「目的地」欄已經" in s, "冇解釋為咩刪"


# ══════════════════════════════════════════════════════════════
# ⚠️⚠️ ShopRow scope bug（用戶報「shopping list 入唔到去睇」）
# ══════════════════════════════════════════════════════════════

class TestShopRowScope:
    """
    🚨🚨 用戶報（報咗兩次）：「shopping list 入唔到去睇」

    ⚠️ 根因：`ShopRow` 入面寫咗 `data?.currency` ——
       但 `data` **唔喺 ShopRow 嘅 scope 入面**！

    ⚠️⚠️ `data?.currency` 只擋 `data` 係 null／undefined，
       **擋唔到 `data` 完全未宣告** ——
       undeclared 變數一定拋 `ReferenceError`，
       optional chaining 都救唔到。

    → **有 item 就爆**（0 個 item 唔會行到嗰行）。

    ⚠️ 為咩之前啲測試捉唔到：
       所有 fixture 都用 `{ items: [] }` —— **永遠行唔到 ShopRow**！
       ✅ 所以呢個 class 一定要用**有 item** 嘅情況檢查。
    """

    @pytest.fixture(scope="class")
    def jsx(self):
        return (WEB / "components" / "ShoppingList.jsx").read_text(encoding="utf-8")

    def test_shoprow_has_no_data_reference(self, jsx):
        """
        ⚠️⚠️ 核心：`ShopRow` 入面**唔可以**出現 `data` ——
           佢冇喺 scope 入面，一定會 ReferenceError。
        """
        import re
        i = jsx.index("function ShopRow(")
        # ⚠️ 搵函數結尾（下一個 module-level function）
        j = jsx.index("\nfunction ", i + 20)
        body = jsx[i:j]
        # ⚠️ 去註解先檢查（我嘅解釋註解有 `data`）
        body = re.sub(r"/\*[\s\S]*?\*/", "", body)
        body = "\n".join(l.split("//")[0] for l in body.split("\n"))
        hits = [m.start() for m in re.finditer(r"(?<![.\w])data\b", body)]
        assert not hits, (
            f"⚠️⚠️ ShopRow 用咗未宣告嘅 `data`（{len(hits)} 處）—— "
            f"有 item 就會 ReferenceError，整個購物清單白畫面。"
            f"要由 parent 傳 prop 入去。")

    def test_trip_currency_is_a_prop(self, jsx):
        """⚠️ 修法：`tripCurrency` 由 parent 傳入。"""
        assert "tripCurrency" in jsx, "冇 tripCurrency prop"
        i = jsx.index("function ShopRow(")
        sig = jsx[i:jsx.index(")", i)]
        assert "tripCurrency" in sig, "tripCurrency 唔係 ShopRow 嘅參數"

    def test_all_shoprow_usages_pass_currency(self, jsx):
        """
        ⚠️ 每個 `<ShopRow>` 都要傳 `tripCurrency` ——
           漏一個嗰個位就會 `undefined`（雖然唔會爆，但換算顯示唔到）。
        """
        import re
        usages = re.findall(r"<ShopRow\b[^>]*>", jsx)
        assert usages, "搵唔到 <ShopRow> 用法"
        for u in usages:
            assert "tripCurrency=" in u, f"呢個 <ShopRow> 冇傳 tripCurrency:\n{u[:120]}"

    def test_optional_chaining_does_not_guard_undeclared(self):
        """
        ⚠️⚠️ 用真 JS 證明呢個陷阱（唔係靠記憶）。

           `x?.y` 喺 `x` **未宣告** 嗰陣一樣拋 ReferenceError。
        """
        import subprocess
        js = """
        try { const r = undeclaredVar?.foo; console.log('NO THROW') }
        catch (e) { console.log('THREW:' + e.constructor.name) }
        """
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True,
                           timeout=30)
        out = (r.stdout + r.stderr).strip()
        assert "THREW:ReferenceError" in out, (
            f"⚠️ 預期 ReferenceError，但得到: {out!r}")

    def test_real_data_test_exists(self):
        """
        ⚠️⚠️ 一定要有「用真數據 + 真 server」嘅測試 ——
           純 SSR + 空 fixture 捉唔到呢類 bug。
        """
        p = ROOT / "tests" / "web" / "shopping_real.test.mjs"
        assert p.exists(), "冇 shopping_real.test.mjs（真數據測試）"
        s = p.read_text(encoding="utf-8")
        assert "127.0.0.1:8787" in s, "唔係打真 server"
        assert "NODE_FETCH" in s, "冇用真 fetch"


class TestTripAutoSelection:
    """
    🚨🚨 同一個 bug 報告嘅**另一個**根因。

    ⚠️ 用戶明明有旅程「Fukuoka」，但主畫面顯示「✈️ 未揀旅程」
       → 撳 Shopping → 彈「先揀一個旅程」+ 旅程選擇器
       → 用戶以為「入唔到去睇」。

    ⚠️ 兩個疊埋嘅 bug：
       ① 開機從來冇「揀旅程」→ `tripId` 永遠 null
       ② 就算 `tripId` 有值，都**冇 effect 去 load 旅程** ——
          `refreshTrip()` 只喺用戶撳 refresh 嗰陣叫
          → header 顯示「0 日 · 👥 0」、清單永遠空
    """

    @pytest.fixture(scope="class")
    def app(self):
        return (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")

    def test_pick_trip_extracted(self, app):
        """⚠️ 要抽做 `pickTrip()` 先可以喺開機都叫。"""
        assert "const pickTrip = useCallback(" in app, "冇抽 pickTrip"

    def test_pick_trip_called_on_boot(self, app):
        """
        ⚠️⚠️ 核心 —— **開機**一定要揀旅程。
           之前只有 `refreshTrips()` 有呢個邏輯，
           但開機行另一條路（直接 `api.me()`），從來冇叫。
        """
        i = app.index("  // 啟動\n  useEffect(() => {")
        j = app.index("}, [setTheme", i)
        blk = app[i:j]
        assert "pickTrip(r.trips)" in blk, (
            "⚠️⚠️ 開機冇 pickTrip —— 只有一個旅程嘅用戶會見到「未揀旅程」")

    def test_pick_trip_defined_before_use(self, app):
        """
        ⚠️⚠️ `useCallback` 用 `const` —— 喺 dep array 用之前一定要定義。
           （dep array 喺 **render 期間**評估，唔係 effect 執行時。）
        """
        i_def = app.index("const pickTrip = useCallback(")
        i_dep = app.index("[setTheme, pickTrip]")
        assert i_def < i_dep, "pickTrip 定義喺 dep array 之後 → TDZ 會爆"

    def test_auto_selects_single_trip(self, app):
        """⚠️ 只有一個旅程 → 自動揀（用戶最常撞到嘅情況）。"""
        i = app.index("const pickTrip = useCallback(")
        blk = app[i:i + 900]
        assert "arr.length === 1" in blk, "冇自動揀單一旅程"
        assert "return arr[0].id" in blk

    def test_restores_saved_trip(self, app):
        """⚠️ 記住上次揀嘅（localStorage）。"""
        i = app.index("const pickTrip = useCallback(")
        blk = app[i:i + 900]
        assert "readSavedTrip()" in blk, "冇還原上次揀嘅旅程"

    def test_effect_loads_trip_on_tripid_change(self, app):
        """
        ⚠️⚠️ `tripId` 一變就要 load 旅程資料 ——
           唔係嘅話 header 顯示「0 日 · 👥 0」、清單永遠空。
        """
        assert "refreshTrip(tripId)" in app, "冇 effect load 旅程"

    def test_refresh_trip_deps_exclude_tripid(self, app):
        """
        ⚠️⚠️ `refreshTrip` 嘅 deps **唔可以**有 `tripId` ——
           上面嘅 effect 依賴 `refreshTrip`，如果佢每次 `tripId`
           變都重新 create，effect 就會**無限 loop**。
        """
        i = app.index("const refreshTrip = useCallback(")
        j = app.index("  }, [", i)
        deps = app[j:app.index(")", j)]
        assert "tripId" not in deps, f"refreshTrip deps 有 tripId → 無限 loop: {deps}"

    def test_no_tdz_for_callbacks(self, app):
        """
        ⚠️⚠️ 所有 `useCallback` 嘅 dep array 唔可以引用未定義嘅 const。
           （呢個 bug 中過：`refreshBadges` 定義喺 `refreshTrip` 之後。）
        """
        import re
        names = [m.group(1) for m in
                 re.finditer(r"^  const (\w+) = useCallback\(", app, re.M)]
        first_def = {}
        for n in names:
            first_def.setdefault(n, app.index(f"const {n} = useCallback("))
        for m in re.finditer(r"^  \}, \[([^\]]*)\]\)", app, re.M):
            for dep in [d.strip() for d in m.group(1).split(",") if d.strip()]:
                if dep in first_def:
                    assert first_def[dep] < m.start(), (
                        f"⚠️ dep `{dep}` 喺用到之後才定義 → TDZ ReferenceError")
