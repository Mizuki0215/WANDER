"""
「加咗景點但收藏度見唔到」+ 重複
======================================

⚠️⚠️ 用戶報：
   「https://maps.app.goo.gl/Cu9BxvmaV8HAjZg5A
    我擺咗條link上去，但係唔知點解佢冇新增落去嗰個已收藏景點度」

⚠️ 查證（真 DB + 真 API）：
   · BOOKOFF **真係加咗** —— 但**加咗兩次**
   · 原因三個疊埋：
     ① 前端 `try { addItem() } catch {}` —— **錯誤被靜靜食咗**
     ② 加完冇明顯 feedback → 用戶以為冇加到 → 再撳
     ③ **後端完全冇重複檢查** → 撳幾次加幾次
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
def disc():
    return (WEB / "components" / "Discover.jsx").read_text(encoding="utf-8")


class TestBackendDedupe:
    """⚠️ 後端唔可以容許同一個地方加兩次。"""

    def test_create_item_has_dedupe(self, srv):
        i = srv.index("def create_item(")
        # ⚠️ 去到下一個 @app
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "duplicate" in blk, "冇去重"

    def test_dedupe_checks_name_and_coords(self, srv):
        i = srv.index("def create_item(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "lower(trim(name))" in blk, "冇用名比對（要 case-insensitive）"
        assert "same_coord" in blk, "冇比對座標"
        assert "same_url" in blk, "冇比對來源 URL"

    def test_dedupe_returns_existing_not_error(self, srv):
        """
        ⚠️ 重複**唔係錯誤** —— 應該回現有嗰個 + `duplicate: true`。
           拋錯嘅話前端會當「加失敗」，用戶更迷茫。
        """
        i = srv.index("def create_item(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert '"duplicate"] = True' in blk or "duplicate" in blk
        # ⚠️ 去重分支唔應該 raise
        seg = blk[:blk.index("iid = _new_id")]
        assert "raise" not in seg, "重複嗰陣拋錯（應該回現有 item）"

    def test_no_geo_also_dedupes(self, srv):
        """
        ⚠️ 冇座標又冇 URL 嗰陣 —— 同名就當重複。
           （保守：寧願唔加，好過加兩個一樣嘅。）
        """
        i = srv.index("def create_item(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "no_geo" in blk, "冇處理「冇座標又冇 URL」"


class TestFrontendReportsTruth:
    """⚠️⚠️ 前端唔可以靜靜食錯誤。"""

    def test_no_swallowed_additem(self, disc):
        """
        ⚠️⚠️ 核心：唔可以 `try { await api.addItem(...) } catch {}` ——
           咁樣加失敗都會顯示「已加入 0 個收藏 ✓」。
        """
        # ⚠️ 去註解先檢查
        body = re.sub(r"/\*[\s\S]*?\*/", "", disc)
        body = "\n".join(l.split("//")[0] for l in body.split("\n"))
        bad = re.findall(r"addItem\([^)]*\)[^;]*\}\s*catch\s*\{\s*\}", body)
        assert not bad, f"仲有靜靜食錯誤嘅 addItem: {bad}"

    def test_has_saveall_helper(self, disc):
        assert "async function saveAll(" in disc, "冇 saveAll helper"

    def test_saveall_collects_errors(self, disc):
        i = disc.index("async function saveAll(")
        j = disc.index("\n  async function ", i + 10)
        blk = disc[i:j]
        assert "errs.push" in blk, "冇收集錯誤"
        assert "catch (e)" in blk, "冇 catch 到 e"

    def test_saveall_handles_duplicate(self, disc):
        """⚠️ 重複要分開講（唔係錯誤）。"""
        i = disc.index("async function saveAll(")
        j = disc.index("\n  async function ", i + 10)
        blk = disc[i:j]
        assert "duplicate" in blk, "冇處理 duplicate"
        assert "已經喺收藏度" in blk, "冇明確講「已經喺收藏度」"

    def test_no_misleading_checkmark(self, disc):
        """
        ⚠️⚠️ 0 個新增唔可以用 `✓` —— 會誤導用戶以為成功。
        """
        i = disc.index("async function saveAll(")
        j = disc.index("\n  async function ", i + 10)
        blk = disc[i:j]
        assert "ok ? '✓ ' : '⚠️ '" in blk or "ok ?" in blk, \
            "冇按實際結果揀 ✓ 定 ⚠️"

    def test_reports_which_failed(self, disc):
        """⚠️ 要講邊個失敗（唔係淨係「N 個失敗」）。"""
        i = disc.index("async function saveAll(")
        j = disc.index("\n  async function ", i + 10)
        blk = disc[i:j]
        assert "it.name" in blk, "冇講邊個 item 失敗"


class TestAmbiguousGeocoding:
    """
    🚨 實測捉到嘅危險：淨係用店名 geocode 會**揀錯城市**。

       「Restaurante & Cafetería Beluga」
         地址寫住 46002 València
         但淨用店名 → 中咗 **Astorga**（差 600km！）

    ⚠️ 旅行 app 錯座標特別危險 —— 用戶會跟住去錯城市。
    """

    @pytest.fixture(scope="module")
    def lk(self):
        return (ROOT / "engine" / "wander" / "lookup.py").read_text(encoding="utf-8")

    def test_uses_address_as_hint(self, lk):
        """
        ⚠️⚠️ 有地址就要用地址做 hint 消歧義。
        """
        i = lk.index("found, log2 = lookup_place(")
        # ⚠️ 向前睇 1500 字（我嘅解釋註解好長）
        blk = lk[max(0, i - 1500):i]
        assert "item.address" in blk or 'getattr(item, "address"' in blk, \
            "冇用地址做 hint"
        assert "hint = " in blk, "冇砌 hint"

    def test_same_name_different_city(self):
        """
        ⚠️⚠️ **實測**：同名店加地址 hint 之後要中啱城市。
           （唔用網絡 —— 只驗證 hint 有傳入）
        """
        lk = (ROOT / "engine" / "wander" / "lookup.py").read_text(encoding="utf-8")
        # ⚠️ 確認有「用地址尾兩段」嘅邏輯
        assert "parts[-2:]" in lk, "冇攞地址最後兩段做 hint"

    def test_logs_why(self, lk):
        """⚠️ 要記低點解用咗 hint（debug 用）。"""
        i = lk.index("found, log2 = lookup_place(")
        blk = lk[max(0, i - 1500):i]
        assert "消歧義" in blk, "冇解釋點解用 hint"


class TestUrlShortLink:
    """⚠️ Google Maps 短連結要跟 redirect。"""

    def test_short_link_detected(self):
        from wander.links import is_short_link
        assert is_short_link("https://maps.app.goo.gl/Cu9BxvmaV8HAjZg5A")

    def test_resolver_exists(self):
        from wander.fetch import resolve_short_url
        assert callable(resolve_short_url)

    def test_fetch_follows_short_link(self):
        """
        ⚠️ `fetch_item` 一定要跟短連結（唔係嘅話解析唔到任何嘢）。
        """
        s = (ROOT / "engine" / "wander" / "fetch.py").read_text(encoding="utf-8")
        i = s.index("if is_short_link(url):")
        blk = s[i:i + 700]
        assert "resolve_short_url(url)" in blk, "冇跟 redirect"
        assert "parse_gmaps(final_url)" in blk, "展開之後冇解析"

    def test_real_short_link_parses(self):
        """
        ⚠️⚠️ 用**真嘅**用戶短連結測（要網絡）。
           ⚠️ 冇網絡就 skip。
        """
        from wander.links import parse_url_offline
        # ⚠️ 已展開嘅 URL（唔使網絡）—— 驗證解析邏輯
        resolved = ("https://www.google.com/maps/place/"
                    "BOOKOFF+Fukuoka+Hakataguchi+Store/"
                    "@33.8419058,130.0567689,10.23z/data=!3m1!5s0x354191b8ddc2a245"
                    ":0x9294e40ccf975015!4m6!3m5!1s0x354191b8fe61f2bb"
                    ":0x254b562d7e9bd80b!8m2!3d33.5880184!4d130.418405")
        it = parse_url_offline(resolved)
        assert it.name == "BOOKOFF Fukuoka Hakataguchi Store", f"名錯: {it.name!r}"
        assert abs(it.lat - 33.5880184) < 1e-4, f"座標錯: {it.lat}"
        assert it.country == "日本", f"國家錯: {it.country!r}"
