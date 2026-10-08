"""
私隱：購物清單私人 + 收藏景點 public／private
=================================================

⚠️⚠️ 用戶要求：
   ① 「shopping list 係自己嘅，就算人哋加落去加咗落去呢個
       planner 度呢，佢哋應該係睇唔到嘅。」
   ② 「你 Save 低嘅景點呢應該有分可以作 public 同埋 Private。
       Public 就係大家喺呢個 group 裏面嘅都見到，
       而 Private 就係得自己睇到呢一張。」

⚠️⚠️ 安全原則（每一條都要有測試守住）：
   · **預設 private** —— 唔會唔小心公開
   · **只有作者可以改** —— 唔可以將朋友嘅私人嘢變公開
   · **值一定要驗** —— 唔可以任人寫任意字串
   · **舊 row（NULL）當 private** —— migration 之前加嘅唔會突然公開
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


@pytest.fixture(scope="module")
def srv():
    return (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dbpy():
    return (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")


class TestSchema:
    def test_shopping_has_visibility(self, dbpy):
        i = dbpy.index("CREATE TABLE IF NOT EXISTS shopping_items")
        blk = dbpy[i:i + 900]
        assert "visibility" in blk, "shopping_items 冇 visibility"

    def test_items_has_visibility(self, dbpy):
        i = dbpy.index("CREATE TABLE IF NOT EXISTS items")
        blk = dbpy[i:i + 900]
        assert "visibility" in blk, "items 冇 visibility"

    def test_shopping_default_private(self, dbpy):
        """⚠️⚠️ 預設一定要 `private` —— 唔可以唔小心公開。"""
        i = dbpy.index("CREATE TABLE IF NOT EXISTS shopping_items")
        blk = dbpy[i:i + 900]
        assert "visibility TEXT DEFAULT 'private'" in blk, "shopping 預設唔係 private"

    def test_items_default_private(self, dbpy):
        i = dbpy.index("CREATE TABLE IF NOT EXISTS items")
        blk = dbpy[i:i + 900]
        assert "DEFAULT 'private'" in blk, "items 預設唔係 private"

    def test_migrations(self, dbpy):
        """⚠️ 舊 DB 都要加欄位（migration）。"""
        assert '("shopping_items", "visibility", "TEXT")' in dbpy
        assert '("items", "visibility", "TEXT")' in dbpy


class TestShoppingPrivacy:
    def test_list_filters_by_owner(self, srv):
        i = srv.index("def list_shopping(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "created_by = ?" in blk, "冇按作者過濾"
        assert "visibility = 'group'" in blk, "冇處理共用"

    def test_list_shows_assigned_items(self, srv):
        """
        ⚠️ 指派畀我嘅一定要見到 —— 唔係嘅話朋友叫你買嘢
           你反而睇唔到。
        """
        i = srv.index("def list_shopping(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "assignee" in blk, "冇處理「指派畀我」"

    def test_list_returns_mine_flag(self, srv):
        """⚠️ 前端要知可唔可以改可見度。"""
        i = srv.index("def list_shopping(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert '"mine"' in blk, "冇回 mine"

    def test_default_is_private_on_add(self, srv):
        i = srv.index("def add_shopping(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert '"private"' in blk, "新增唔係預設 private"

    def test_visibility_value_validated(self, srv):
        """⚠️⚠️ 唔可以任人寫任意值。"""
        i = srv.index("def update_shopping(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert '("private", "group")' in blk, "冇驗 visibility 值"
        assert "400" in blk, "冇 400"

    def test_only_owner_can_change(self, srv):
        """
        ⚠️⚠️ 只有**加嗰個人**可以改 ——
           唔可以將朋友嘅私人清單變成共用（咁係泄漏）。
        """
        i = srv.index("def update_shopping(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "created_by" in blk, "冇檢查作者"
        assert "403" in blk, "冇 403 擋"


class TestItemVisibility:
    def test_list_filters(self, srv):
        i = srv.index("def list_items(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "COALESCE(visibility, 'private') = 'public'" in blk, \
            "冇過濾 public"
        assert "created_by = ?" in blk, "冇處理「自己嘅」"

    def test_old_rows_treated_as_private(self, srv):
        """
        ⚠️⚠️ 舊 row 係 NULL（migration 之前加嘅）——
           一定要當 `private`，唔可以當 public。
           （用戶加咗好多嘢，唔可以突然全部公開。）
        """
        i = srv.index("def list_items(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "COALESCE(visibility, 'private')" in blk, \
            "舊 row 冇當 private → 會突然公開"

    def test_visibility_endpoint_exists(self, srv):
        assert '@app.patch("/api/item/{item_id}/visibility")' in srv

    def test_only_owner_can_change(self, srv):
        i = srv.index("def set_item_visibility(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert 'it.get("created_by") != user["id"]' in blk, "冇檢查作者"
        assert "403" in blk, "冇 403"

    def test_value_validated(self, srv):
        i = srv.index("def set_item_visibility(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert '("public", "private")' in blk, "冇驗值"

    def test_api_returns_visibility_and_mine(self, dbpy):
        i = dbpy.index("def item_row_to_api(")
        # ⚠️ 呢個係 `db.py` **最後**一個函數 —— 所以唔會有下一個
        #    `\ndef `。（實測：`index()` 拋 ValueError。）
        blk = dbpy[i:]
        assert '"visibility"' in blk, "item API 冇回 visibility"
        assert '"mine"' in blk, "item API 冇回 mine"


class TestFrontendUI:
    def test_saved_has_toggle(self):
        s = (WEB / "components" / "Saved.jsx").read_text(encoding="utf-8")
        assert "onToggleVis" in s, "Saved 冇可見度掣"
        assert "🌍 公開" in s and "🔒 私人" in s, "冇清楚標示"

    def test_saved_only_own_clickable(self):
        """
        ⚠️ 唔可以撳朋友嘅（後端都會擋，但 UI 都要）。

           ⚠️ 要搵**真正嘅 usage**（`onToggleVis?.(it)`），
              唔係 props 宣告 —— `index()` 會回第一個。
        """
        s = (WEB / "components" / "Saved.jsx").read_text(encoding="utf-8")
        i = s.index("onToggleVis?.(it)")
        blk = s[max(0, i - 700):i]
        assert "it.mine" in blk, "冇檢查係唔係自己嘅"

    def test_shopping_has_toggle(self):
        s = (WEB / "components" / "ShoppingList.jsx").read_text(encoding="utf-8")
        assert "onToggleVis" in s, "ShoppingList 冇可見度掣"
        assert "👥 共用" in s and "🔒 私人" in s

    def test_optimistic_update_rolls_back(self):
        """
        ⚠️ 樂觀更新失敗要**彈返轉頭** ——
           唔好靜靜呃用戶話改咗。

           ⚠️ `App.jsx` 有**兩個** onToggleVis（Shopping + Saved）——
              要搵有 rollback 嗰個。
        """
        s = (WEB / "App.jsx").read_text(encoding="utf-8")
        # ⚠️ Saved 嗰個有 rollback（`visibility: it.visibility`）
        i = s.index("visibility: it.visibility")
        blk = s[max(0, i - 900):i + 300]
        assert "catch" in blk, "冇 catch"
        assert "setItems" in blk, "冇 rollback（要 setItems 彈返轉頭）"


class TestWallpaper:
    """⚠️⚠️ 用戶要求：可以加自己嘅相做背景。"""

    def test_schema(self, dbpy):
        i = dbpy.index("CREATE TABLE IF NOT EXISTS users")
        blk = dbpy[i:i + 700]
        assert "wallpaper" in blk, "users 冇 wallpaper"

    def test_migration(self, dbpy):
        assert '("users", "wallpaper", "TEXT")' in dbpy

    def test_me_returns_wallpaper(self, srv):
        i = srv.index('"theme": user.get("theme")')
        blk = srv[i:i + 200]
        assert "wallpaper" in blk, "/api/me 冇回 wallpaper"

    def test_value_validated(self, srv):
        """
        ⚠️⚠️ 一定要驗格式 —— 唔係嘅話可以寫入
           `javascript:...` 或者路徑穿越。
        """
        i = srv.index("wallpaper = ?")
        blk = srv[max(0, i - 900):i]
        assert "背景格式唔啱" in blk, "冇驗格式"
        assert "/uploads/" in blk, "冇驗上載路徑"

    def test_component_exists(self):
        p = WEB / "components" / "Wallpaper.jsx"
        assert p.exists(), "冇 Wallpaper.jsx"

    def test_has_scrim(self):
        """
        ⚠️⚠️ 相上面一定要有**暗罩** ——
           唔係嘅話放一張白雲相，啲白字會完全睇唔到。
        """
        s = (WEB / "components" / "Wallpaper.jsx").read_text(encoding="utf-8")
        assert "wallpaper-scrim" in s, "冇暗罩"
        css = (WEB / "styles.css").read_text(encoding="utf-8")
        assert ".wallpaper-scrim" in css, "CSS 冇暗罩"

    def test_z_index_negative(self):
        """⚠️ 背景唔可以蓋住 app 內容。"""
        css = (WEB / "styles.css").read_text(encoding="utf-8")
        i = css.index(".wallpaper-img")
        blk = css[i:i + 300]
        assert "z-index: -2" in blk, "wallpaper-img z-index 唔係負"

    def test_picker_shrinks_photo(self):
        """
        ⚠️⚠️ 上載之前一定要**縮圖** ——
           手機影相 4–8MB，base64 之後再大 33% → 上傳要好耐。
        """
        s = (WEB / "components" / "WallpaperPicker.jsx").read_text(encoding="utf-8")
        assert "function shrink(" in s, "冇縮圖"
        assert "canvas" in s.lower() or "createElement('canvas')" in s
        assert "1600" in s, "縮圖尺寸唔啱"

    def test_uses_jpeg_not_png(self):
        """⚠️ 相片用 PNG 會大 5–10 倍。"""
        s = (WEB / "components" / "WallpaperPicker.jsx").read_text(encoding="utf-8")
        assert "image/jpeg" in s, "冇用 JPEG"

    def test_presets(self):
        s = (WEB / "components" / "Wallpaper.jsx").read_text(encoding="utf-8")
        assert "PRESETS" in s, "冇 preset"
        assert s.count("label:") >= 5, "preset 太少"


class TestQrCamera:
    """⚠️⚠️ 用戶要求：用相機掃 QR。"""

    def test_component_exists(self):
        p = WEB / "components" / "QrCamera.jsx"
        assert p.exists(), "冇 QrCamera.jsx"

    def test_uses_getusermedia(self):
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "getUserMedia" in s, "冇開相機"

    def test_uses_back_camera(self):
        """⚠️ 掃 QR 一定用後置鏡頭。"""
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "environment" in s, "冇指定後置鏡頭"

    def test_throttles(self):
        """
        ⚠️⚠️ 一定要 throttle —— 唔係嘅話一秒送 60 張，
           手機發熱 + 後端爆。
        """
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "INTERVAL_MS" in s, "冇 throttle"
        m = re.search(r"INTERVAL_MS\s*=\s*(\d+)", s)
        assert m and int(m.group(1)) >= 300, "throttle 太快"

    def test_prevents_overlap(self):
        """⚠️ 上一次仲未返就唔好再送（busyRef）。"""
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "busyRef" in s, "冇防重疊"

    def test_stops_tracks_on_unmount(self):
        """
        ⚠️⚠️ 一定要**熄相機** ——
           唔係嘅話離開之後鏡頭燈仲亮，好嚇人。
        """
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "getTracks().forEach(t => t.stop())" in s, "冇熄相機"
        assert "clearInterval" in s, "冇清 timer"

    def test_reuses_backend_decoder(self):
        """⚠️ 重用後端 OpenCV decoder（唔加 library）。"""
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "decodeQr" in s, "冇用後端 decoder"

    def test_handles_permission_denied(self):
        """⚠️ 用戶拒絕權限要**講清楚**（唔同「冇相機」）。"""
        s = (WEB / "components" / "QrCamera.jsx").read_text(encoding="utf-8")
        assert "NotAllowed" in s or "Permission" in s, "冇分開處理拒絕"

    def test_wired_in_friends(self):
        s = (WEB / "components" / "Friends.jsx").read_text(encoding="utf-8")
        assert "QrCamera" in s, "Friends 冇用 QrCamera"
        assert "開相機掃" in s, "冇相機掣"
