"""
密碼狀態（`has_password`）
===========================

⚠️⚠️ 用戶報：
   「因為我個帳號本身係 set 咗一個密碼嘅，所以呢你去改密碼嘅
    時候呢，例如去 setting，佢冇理由會同你講你仲未有密碼。
    我覺得呢個要改。」

⚠️ 根因：`/api/me` **根本冇回 `has_password`** ——
   前端 `user.has_password` 永遠 `undefined`（falsy）
   → Settings 永遠顯示「未設定」。

⚠️ 而且連帶兩個更嚴重嘅後果：
   ① 「現有密碼」個欄**唔會顯示** → 用戶填極都話「密碼唔啱」
   ② 個掣寫「設定密碼」而唔係「更改密碼」
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
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"`])//.*$', '', line)
        s = re.sub(r'/\*.*?\*/', '', s)
        if s.strip().startswith(('*', '/*')):
            continue
        out.append(s)
    return "\n".join(out)


class TestHasPasswordInApi:
    def test_me_returns_has_password(self):
        """
        ⚠️⚠️ 核心修法 —— `/api/me` 一定要回 `has_password`。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def me(")
        j = s.index("@app.", i + 10)
        blk = s[i:j]
        assert "has_password" in blk, \
            "⚠️⚠️ /api/me 冇回 has_password → Settings 永遠顯示「未設定」"

    def test_has_password_from_db_not_guessed(self):
        """⚠️ 一定要由 `password_hash` 計，唔可以寫死。"""
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def me(")
        blk = s[i:s.index("@app.", i + 10)]
        assert 'bool(user.get("password_hash"))' in blk, \
            "has_password 唔係由 password_hash 計"

    def test_uses_get_not_index(self):
        """
        ⚠️ 要用 `user.get()` 而唔係 `user["..."]` ——
           舊 session 嘅 user dict 可能係舊 schema（冇新欄）→ KeyError。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def me(")
        blk = s[i:s.index("@app.", i + 10)]
        assert 'user["password_hash"]' not in blk, \
            "用咗直接索引（舊 session 會 KeyError）"


class TestChangePasswordRequiresCurrent:
    def test_requires_current_when_has_password(self):
        """
        ⚠️ 有密碼就一定要提供現有密碼 ——
           唔係嘅話有人偷到你部手機就可以改密碼鎖你出嚟。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def set_password(")
        blk = s[i:i + 900]
        assert "has_pw and not _check_password" in blk, \
            "冇檢查現有密碼"
        assert "現有密碼唔啱" in blk, "冇明確錯誤訊息"

    def test_returns_has_password_true(self):
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def set_password(")
        blk = s[i:i + 900]
        assert '"has_password": True' in blk


class TestFrontendRefreshesUser:
    def test_settings_accepts_onrefresh(self):
        """⚠️ 改完密碼要 refresh `/api/me`（唔係嘅話 UI 唔跟）。"""
        s = code(WEB / "components" / "SettingsMore.jsx")
        assert "onRefresh" in s, "SettingsMore 冇 onRefresh"
        assert "onRefresh?.()" in s, "冇叫 onRefresh"

    def test_fallback_when_backend_disagrees(self):
        """
        ⚠️⚠️ Fallback：如果後端話「現有密碼唔啱」但前端以為冇密碼，
           即係 `has_password` 同後端唔一致 →
           強制 refresh 一次，個「現有密碼」欄就會出返。
           ⚠️ 唔係嘅話用戶會卡死（見到「未設定」但點改都話唔啱）。
        """
        s = code(WEB / "components" / "SettingsMore.jsx")
        i = s.index("async function savePassword")
        blk = s[i:i + 1200]
        assert "現有密碼" in blk, "冇處理「現有密碼唔啱」嘅 fallback"
        assert "onRefresh?.()" in blk, "fallback 冇 refresh"

    def test_prop_chained_from_app(self):
        """⚠️ onRefresh 要由 App 一路傳落去（App → Settings → SettingsMore）。"""
        app = code(WEB / "App.jsx")
        assert "const refreshMe" in app, "App 冇 refreshMe"
        assert "onRefresh={refreshMe}" in app, "App 冇傳 onRefresh"
        st = code(WEB / "components" / "Settings.jsx")
        assert "onRefresh" in st, "Settings 冇收／傳 onRefresh"

    def test_refresh_me_updates_user(self):
        """⚠️ refreshMe 一定要 setUser（唔係嘅話 UI 唔會變）。"""
        s = code(WEB / "App.jsx")
        i = s.index("const refreshMe")
        blk = s[i:i + 400]
        assert "setUser(" in blk, "refreshMe 冇 setUser"

    def test_ui_shows_correct_labels(self):
        """⚠️ 有密碼要寫「更改密碼」+ 顯示「現有密碼」欄。"""
        s = (WEB / "components" / "SettingsMore.jsx").read_text(encoding="utf-8")
        assert "更改密碼" in s, "冇「更改密碼」標籤"
        assert "現有密碼" in s, "冇「現有密碼」欄"
        assert "user?.has_password" in s, "冇用 has_password 做判斷"


# ══════════════════════════════════════════════════════════════
# ⑥ 世界時鐘（用戶要求：上面手機時間，下面自選城市）
# ══════════════════════════════════════════════════════════════

class TestWorldClocks:
    """
    ⚠️⚠️ 用戶要求（我原本做錯方向，佢糾正咗）：
       「Show 兩個時區囉，第一個最上面嗰個係**手機時間**，
        第二個就係有得比你揀 —— 你可以輸入嗰個城市嘅名，
        用英文或者中文都可以，之後呢例如你揀咗，
        然後就會有對應嘅時區。」

    ⚠️ 之前係反過嚟（**目的地**做大字）—— 用戶話唔啱。
    """

    @pytest.fixture(scope="class")
    def wc(self):
        p = WEB / "components" / "WorldClocks.jsx"
        assert p.exists(), "冇 WorldClocks.jsx"
        return code(p)

    def test_exists_and_used(self):
        home = code(WEB / "components" / "HomeScreen.jsx")
        assert "<WorldClocks" in home, "HomeScreen 冇用 WorldClocks"
        assert "DualClock" not in home, "仲用緊 DualClock（舊設計）"

    def test_phone_time_is_big_first(self, wc):
        """
        ⚠️⚠️ 核心：**手機時間**做大字（`fontSize: 46`），
           唔可以係目的地做大字。
        """
        # ⚠️ 大鐘嗰段要喺細鐘之前
        assert "你嘅時間" in wc, "冇標明「你嘅時間」"
        i_big = wc.index("你嘅時間")
        i_small = wc.index("target && !editing")
        assert i_big < i_small, "手機時間唔係喺最上面"

    def test_second_clock_is_pickable(self, wc):
        """⚠️ 第二個鐘要**揀得**（用 CityPicker）。"""
        assert "CityPicker" in wc, "冇 CityPicker"
        assert "setEditing(true)" in wc, "冇得撳去改城市"

    def test_persists_pick(self, wc):
        """⚠️ 揀咗嘅城市要記住（唔使每次再揀）。"""
        assert "localStorage" in wc, "冇存 localStorage"
        assert "wander.worldclock" in wc, "冇固定 key"

    def test_hides_when_same_zone(self, wc):
        """⚠️ 同一時區唔應該出兩個一樣嘅鐘。"""
        assert "sameZone" in wc, "冇用 sameZone"
        assert "同你同一個時區" in wc, "冇處理同時區"

    def test_no_trip_needed(self, wc):
        """
        ⚠️ 世界時鐘**唔應該**一定要有旅程 ——
           冇旅程都想睇其他城市幾點。
        """
        assert "加世界時鐘" in wc, "冇「加世界時鐘」掣（一定要有旅程？）"

    def test_shows_offset(self, wc):
        """⚠️ 要顯示快／慢幾個鐘（一眼睇到差幾多）。"""
        assert "快 " in wc and "慢 " in wc, "冇顯示時差"


class TestTimezoneApi:
    """
    ⚠️ 為咩要獨立 `/api/tz`：
       · 世界時鐘唔一定要有旅程
       · ⚠️ 唔應該為咗攞個時區而建立 trip_stop
       · ⚠️ `/api/lookup` 係「店名反查」（會打 Photon/Nominatim，貴）
         `/api/tz` 用本機 134k 城市庫，唔使網絡
    """

    def test_endpoint_exists(self):
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        assert '@app.get("/api/tz")' in s, "冇 /api/tz"

    def test_before_spa_fallback(self):
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        stripped = "\n".join(l for l in s.split("\n")
                             if not l.strip().startswith("#"))
        assert stripped.index('"/api/tz"') < \
               stripped.index('@app.get("/{full_path:path}")'), \
            "/api/tz 喺 SPA catch-all 之後 → 404"

    def test_uses_local_db_not_network(self):
        """
        ⚠️ 要用本機城市庫（快、唔使網絡）——
           唔好為咗時區去打 Photon。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def api_tz(")
        blk = s[i:i + 1600]
        assert "localgeo" in blk, "冇用本機城市庫"
        assert "Photon" not in blk and "nominatim" not in blk.lower()

    def test_returns_iana_name(self):
        """
        ⚠️⚠️ 要回 **IANA** 名（`Asia/Tokyo`）而唔係 `Etc/GMT-9`。
           ⚠️ 我第一版寫錯 `_zh_to_cc()` 用法（佢係函數唔係 dict），
              搞到成日 fallback 去 `Etc/GMT-9` —— 功能啱但前端
              顯示唔到「東京」。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def api_tz(")
        blk = s[i:i + 1600]
        # ⚠️ 一定要用中文國名反查 cc（唔係就 fallback）
        assert '_zh_to_cc(c.get("country")' in blk, \
            "_zh_to_cc 用法錯（會 fallback 去 Etc/GMT±N）"

    def test_handles_missing_city(self):
        """⚠️ 搵唔到城市要 404（唔可以回 null 時區）。"""
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def api_tz(")
        blk = s[i:i + 1600]
        assert "404" in blk, "搵唔到城市冇報錯"

    def test_frontend_api_method(self):
        s = code(WEB / "lib" / "api.js")
        assert "tz:" in s, "冇 api.tz"


# ══════════════════════════════════════════════════════════════
# ⑦ 拖放 + 城市分組（用戶要求）
# ══════════════════════════════════════════════════════════════

class TestDragToTimeslot:
    """
    ⚠️ 用戶要求：
       「排行程嗰陣時候呢，我覺得係可以手動拖上去囉，
        除咗有個 button 你撳入去之後可以話你放上去之外，
        你仲可以用你隻手咁樣拖上去囉？」

    ⚠️ 兩種操作要**同時**有：
       · 撳 → 開彈層揀時長（手機單手用）
       · 拖 → 直接放上時段格
    """

    @pytest.fixture(scope="class")
    def dg(self):
        return code(WEB / "components" / "DayGrid.jsx")

    def test_uses_pointer_events(self, dg):
        """
        ⚠️⚠️ 一定要用 **Pointer Events** ——
           HTML5 drag-and-drop（`draggable` + `dragstart`）
           **手機完全唔 work**。
        """
        assert "onPointerDown" in dg, "冇 onPointerDown"
        assert "pointermove" in dg, "冇 pointermove"
        assert "pointerup" in dg, "冇 pointerup"

    def test_no_html5_dnd(self, dg):
        """⚠️ 唔可以用 HTML5 DnD（手機唔支援）。"""
        assert "onDragStart" not in dg, "用咗 HTML5 DnD（手機唔 work）"
        assert "draggable=" not in dg, "用咗 draggable（手機唔 work）"

    def test_touch_action_none(self, dg):
        """
        ⚠️⚠️ 拖嘅元素一定要 `touch-action: none` ——
           唔係嘅話手機當佢係**捲動**，pointermove 唔會觸發。
        """
        # ⚠️ 唔好用字數窗口 —— 我嘅解釋註解好長，會推走目標（中過）。
        #    改用**區塊邊界**：托盤項 render 由 `shownPool.map` 開始。
        i = dg.index("shownPool.map(it =>")
        j = dg.index("</div>", dg.index("touchAction") if "touchAction" in dg[i:] else i)
        blk = dg[i:i + 2500]
        assert "touchAction: 'none'" in blk, "冇 touch-action: none（手機拖唔到）"

    def test_no_pointer_capture(self, dg):
        """
        ⚠️ 唔可以用 `setPointerCapture` ——
           一格住 pointer，`pointermove` 就唔會喺格上面觸發，
           判斷唔到拖到邊一行。
        """
        assert "setPointerCapture" not in dg, "用咗 setPointerCapture（判斷唔到位）"

    def test_tap_opens_picker(self, dg):
        """⚠️ 撳一下要開彈層（唔可以淨係靠拖）。"""
        assert "setShowPicker" in dg, "冇 PickerSheet"
        i = dg.index("shownPool.map(it =>")
        blk = dg[i:i + 2500]
        assert "setShowPicker" in blk, "撳一下冇彈層"

    def test_drag_does_not_open_picker(self, dg):
        """
        ⚠️⚠️ 實測捉到嘅 bug：
           手機拖完（pointerdown→move→up）瀏覽器**照樣**發 `click`
           → 彈層會彈出嚟（用戶唔想要）。
           ✅ 用 `trayMoved` flag 吞咗個 click。
        """
        assert "trayMoved" in dg, "冇 trayMoved flag"
        i = dg.index("if (trayMoved.current)")
        assert "return" in dg[i:i + 80], "冇吞咗個 click"

    def test_drag_places_at_dropped_time(self, dg):
        """⚠️ 放手嗰陣要**用拖到嗰個時間**（唔係默認時間）。"""
        i = dg.index("const trayUp")
        blk = dg[i:i + 800]
        assert "place(d.item, d.minutes" in blk, "放手冇用拖到嘅時間"

    def test_no_place_if_not_dropped_in_grid(self, dg):
        """
        ⚠️ 冇拖入格就唔應該放（唔可以當「撳一下」就亂放）。
        """
        i = dg.index("const trayUp")
        blk = dg[i:i + 800]
        assert "d.minutes == null" in blk, "冇檢查有冇拖入格"


class TestTrayCityGrouping:
    """
    ⚠️ 用戶要求：
       「例如就係我哋知道嗰一日帶佢去邊度，例如係去福岡嘅咁，
        可唔可以就係你 show 出嚟嘅時候，先優先喺下面未排入嘅
        行程係可以整理咗 —— 例如 show 嘅係多嘅地址呢？
        或者未入嘅行程可以 show 埋係邊一個城市嘅，
        例如係香港嘅、福岡嘅、東京嘅。」
    """

    @pytest.fixture(scope="class")
    def dg(self):
        return code(WEB / "components" / "DayGrid.jsx")

    def test_shows_city_per_item(self, dg):
        """⚠️ ① 每項要顯示**佢喺邊個城市**。"""
        assert "cityOf" in dg, "冇 cityOf"
        i = dg.index("cityOf(it)") if "cityOf(it)" in dg else -1
        assert i > 0, "冇用 cityOf"

    def test_city_of_falls_back(self, dg):
        """⚠️ 城市可以由 `city` / `district` / `location_path[0]` 攞。"""
        i = dg.index("function cityOf")
        blk = dg[i:i + 300]
        assert "it.city" in blk, "冇用 it.city"
        assert "it.district" in blk, "冇用 it.district"
        assert "location_path" in blk, "冇用 location_path"

    def test_groups_by_city(self, dg):
        """⚠️ ② 要**按城市分組**。"""
        assert "const groups" in dg, "冇 groups"
        assert "new Map()" in dg[dg.index("const groups"):dg.index("const groups") + 900]

    def test_today_city_first(self, dg):
        """
        ⚠️⚠️ 核心：**今日嘅城市排最前** ——
           用戶排 Day 3（福岡）嗰陣，最想見到福岡嘅景點。
        """
        assert "isToday" in dg, "冇 isToday"
        i = dg.index("arr.sort")
        blk = dg[i:i + 400]
        assert "a.isToday !== b.isToday" in blk, "冇按「今日」排序"
        assert "a.isToday ? -1 : 1" in blk, "排序方向錯"

    def test_today_city_marked(self, dg):
        """⚠️ 今日嘅城市要有視覺標記（📍）。"""
        assert "📍" in dg, "冇 📍 標記"
        assert "var(--neon)" in dg, "冇用 accent 色"

    def test_uncategorised_last(self, dg):
        """⚠️ 「未分類」擺最後（唔係擺最前阻住）。"""
        i = dg.index("arr.sort")
        blk = dg[i:i + 500]
        assert "未分類" in blk, "冇將「未分類」排最後"

    def test_filter_chips(self, dg):
        """⚠️ 要有城市篩選 chip。"""
        assert "cityFilter" in dg, "冇 cityFilter"
        assert "setCityFilter" in dg, "冇 setCityFilter"

    def test_filter_limits_shown(self, dg):
        """⚠️ 篩選要真係限制顯示嘅項。"""
        i = dg.index("const shownPool")
        blk = dg[i:i + 300]
        assert "filter(" in blk, "shownPool 冇 filter"

    def test_shows_address(self, dg):
        """⚠️ 用戶問「可以 show 嘅係多嘅地址呢？」→ 有地址就顯示。"""
        assert "it.address" in dg, "冇顯示地址"

    def test_uses_build_day_cities(self, dg):
        """⚠️ 要由旅程嘅城市清單計「今日係邊個城市」。"""
        assert "buildDayCities" in dg, "冇用 buildDayCities"
