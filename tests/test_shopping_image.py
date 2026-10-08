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
        blk = srv[i:i + 1400]
        assert "created_by, image)" in blk, "INSERT 冇寫 image 欄"
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
