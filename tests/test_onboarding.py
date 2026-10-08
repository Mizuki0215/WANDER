"""
新手教學（Onboarding）測試
============================
⚠️ 用戶明確要求：「你叫乜嘢名…呢個係必做嘅」

   所以呢個測試最重要嘅係驗證：
     · 名字空白 → 一定失敗
     · **失敗之後 onboarded 唔可以變 True**
       （否則用戶會卡喺「未改名但當佢完成咗」嘅狀態，
         以後每次登入都見到 email 而唔係名）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def _frames(src: str) -> dict:
    """
    抽出所有 frame。

    ⚠️ 一定要容忍**註解** ——
       第一版 regex 寫死 `pal: [...],\n    grid: [`，
       但 `happy` 中間加咗解釋手臂 bug 嘅註解就對唔上。
    """
    out = {}
    for m in re.finditer(
            r"\n  (\w+): \{(.*?)\n  \},", src, re.S):
        body = m.group(2)
        pm = re.search(r"pal:\s*\[([^\]]+)\]", body)
        gm = re.search(r"grid:\s*\[(.*?)\]", body, re.S)
        if not (pm and gm):
            continue
        out[m.group(1)] = {
            "pal": [c.strip().strip("'\"") for c in pm.group(1).split(",")],
            "grid": re.findall(r"'([^']*)'", gm.group(1)),
        }
    return out


class TestMascot:
    """
    ⚠️ 吉祥物係 16×16 字串陣列 —— 打錯一個字元就會靜靜畫錯。
    """

    @pytest.fixture(scope="class")
    def mascot(self):
        js = ROOT / "web" / "src" / "lib" / "mascot.js"
        if not js.exists():
            pytest.skip("搵唔到 mascot.js")
        src = js.read_text(encoding="utf-8")
        fr = _frames(src)
        return {"names": sorted(fr), "src": src, "frames": fr}

    def test_has_frames(self, mascot):
        assert len(mascot["names"]) >= 2, f"太少 frame: {mascot['names']}"

    def test_required_frames(self, mascot):
        for f in ("hello", "point", "happy"):
            assert f in mascot["names"], f"冇「{f}」frame"

    def test_all_16x16(self, mascot):
        """
        ⚠️⚠️ 一定要 16×16 —— 唔係嘅話 SVG viewBox 會對唔上，
           角色會變形。用 8×8 做唔到表情，所以用 16×16。
        """
        for name, fr in mascot["frames"].items():
            rows = fr["grid"]
            assert len(rows) == 16, f"{name} 有 {len(rows)} 行（要 16）"
            for i, row in enumerate(rows):
                assert len(row) == 16, \
                    f"{name} 第 {i} 行有 {len(row)} 格（要 16）: {row!r}"

    def test_palette_index_valid(self, mascot):
        """⚠️ 索引超出 → fallback 去 pal[0] → 靜靜畫錯顏色。"""
        bad = []
        for name, fr in mascot["frames"].items():
            n = len(fr["pal"])
            for i, row in enumerate(fr["grid"]):
                for j, ch in enumerate(row):
                    if ch == ".":
                        continue
                    if not ch.isdigit():
                        bad.append(f"{name} ({i},{j}) 非法字元 {ch!r}")
                    elif int(ch) >= n:
                        bad.append(f"{name} ({i},{j}) 索引 {ch} 超出 {n}")
        assert not bad, "吉祥物有問題：\n  " + "\n  ".join(bad[:10])

    def test_not_empty(self, mascot):
        for name, fr in mascot["frames"].items():
            filled = sum(1 for r in fr["grid"] for c in r if c != ".")
            # 16×16 = 256，角色大約佔 90-160 格
            assert filled > 80, f"{name} 只有 {filled} 格有嘢（16×16=256）"

    def test_all_pixels_connected(self, mascot):
        """
        ⚠️⚠️ 所有像素一定要**連成一體**（唔可以有孤立嘅島）。

           呢個測試捉到一個真 bug：
             `happy` 嘅雙手係兩個孤立嘅島 ——
             睇落似「飛出嚟嘅碎片」而唔係舉起嘅手。

           做法：由最頂嘅一個像素開始 flood fill，
                 數下總共去到幾多格，同全部有格數比較。
        """
        for name, fr in mascot["frames"].items():
            rows = fr["grid"]
            n = len(rows)
            filled = {(x, y) for y, row in enumerate(rows)
                      for x, c in enumerate(row) if c != "."}
            assert filled, f"{name} 全空"

            # flood fill（4-方向，正交；斜角唔算連通）
            start = min(filled, key=lambda p: (p[1], p[0]))
            seen, stack = {start}, [start]
            while stack:
                x, y = stack.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (x + dx, y + dy)
                    if q in filled and q not in seen:
                        seen.add(q)
                        stack.append(q)

            islands = filled - seen
            assert not islands, (
                f"{name} 有 {len(islands)} 格係孤立嘅島（同身體斷開）："
                f"{sorted(islands)[:6]} —— 睇落會似碎片")


class TestOnboardingSource:
    """新手教學嘅關鍵性質。"""

    @pytest.fixture(scope="class")
    def src(self):
        p = ROOT / "web" / "src" / "components" / "Onboarding.jsx"
        if not p.exists():
            pytest.skip("搵唔到 Onboarding.jsx")
        return p.read_text(encoding="utf-8")

    def test_uses_mascot(self, src):
        """
        ⚠️ 由 16×16 手畫 SVG 改成 **36×44 程序化角色 PNG** ——
           用戶原話：「你個示範教學呢第一就係個人物太樣衰啦」。
           手畫版只有一隻色、冇面、冇光影。
        """
        assert "mascot-" in src and ".png" in src, "新手教學冇用像素角色圖"
        assert "mascotSvg" not in src, "仲用緊 16×16 手畫 SVG"

    def test_highlights_elements(self, src):
        """⚠️ 用戶要求「圈出嚟點樣去用」→ 一定要有高亮機制。"""
        assert "data-tour" in src, "冇搵目標元素（圈出嚟）"
        assert "mask" in src, "冇用 mask 挖窿做聚光燈"

    def test_name_step_mandatory(self, src):
        """
        ⚠️⚠️ 用戶明確要求名字係「必做」——
           所以：
             · 空白唔可以過
             · 「跳過教學」只可以跳到改名嗰步，唔可以跳過改名
        """
        # 有 trim 檢查
        assert "name.trim()" in src
        assert "必填" in src
        # 撳掣要 disabled
        assert "disabled={busy || !name.trim()}" in src

    def test_skip_only_skips_tour(self, src):
        """
        「跳過」只可以跳去改名，唔可以跳過改名。

        ⚠️ 用戶要求改過之後，步驟用**字串清單**而唔再係索引算術
           （`NAME_STEP = TOUR.length + 1`）——
           因為 replay 要跳步，算術會變地獄。
           所以跳過掣而家搵 `'name'` 或者 `'done'` 呢個 kind。
        """
        assert "跳過教學，直接改名" in src
        # 跳過要去 name 步（第一次）或者 done（replay）
        m = re.search(r"setStep\(steps\.findIndex\(k => k === 'name' \|\| k === 'done'\)\)",
                      src)
        assert m, "「跳過」冇跳去改名嗰步"

    def test_calls_finish_onboard(self, src):
        assert "api.finishOnboard" in src

    def test_skips_missing_targets(self, src):
        """⚠️ 搵唔到目標要自動跳過，唔可以卡住喺黑幕。"""
        assert "搵唔到" in src, "冇處理「搵唔到目標」嘅情況"


class TestAppIntegration:
    """App.jsx 要正確咁接駁新手教學。"""

    @pytest.fixture(scope="class")
    def app(self):
        return (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")

    def test_onboarding_after_boot(self, app):
        """
        ⚠️⚠️ 一定要 `booted` 之後先出教學 ——
           唔可以同開機動畫同時，否則兩個全螢幕組件疊埋一齊。

           ⚠️ 條件仲要包 `replayTour`（設定頁手動重看）。
        """
        m = re.search(
            r"if \(user && booted && \(!user\.onboarded \|\| replayTour\)\)", app)
        assert m, ("教學嘅條件唔啱 —— 應該係 "
                   "user && booted && (!user.onboarded || replayTour)")

    def test_uses_backend_flag_not_localstorage(self, app):
        """
        ⚠️⚠️ 用 `user.onboarded`（後端）而唔係 localStorage ——
           localStorage 一換機／一清 cache 就冇，
           用戶會**再睇一次**教學。
        """
        i = app.find("user && booted && (!user.onboarded || replayTour)")
        blk = app[i:i + 500]
        assert "localStorage" not in blk, "用咗 localStorage 判斷，換機會再出教學"


class TestOnboardedFlag:
    """
    ⚠️⚠️ 用戶描述嘅正確行為：

       「你可以喺個 database 度 mark 低，果欄就係零咁解。
        你一登入去嗰陣時就會有嗰個指令喺度，
        然後有指令之後佢就會加返一。
        只要係零嗰先至會 show 嗰個顯示出嚟。
        所以我呢一個帳號登入咗嘅話呢，
        其實正常就唔應該會有指示嘅出現囉」

       即係：
         onboarded = 0  →  登入會出教學
         onboarded = 1  →  登入**唔會**出（就算係你現有嘅帳號）
    """

    @pytest.fixture(scope="class")
    def db(self):
        import importlib
        import app.db as dbmod
        importlib.reload(dbmod)
        return dbmod

    def test_backfill_exists(self, db):
        """
        ⚠️⚠️ 呢個測試捉到一個真 bug：

           加咗 `users.onboarded` 欄位之後，**所有舊用戶都係 NULL**，
           而 NULL 係 falsy → 全部現有帳號登入都會被逼睇新手教學。

           實測：80 個用戶有 **77 個**中招。

           修法：一次性 backfill 將舊用戶設做 1。
        """
        names = [n for n, _ in db.BACKFILLS]
        assert any("onboarded" in n for n in names), \
            f"冇 onboarded 嘅 backfill：{names}"
        sql = dict(db.BACKFILLS)["2026-10-08-onboarded-grandfather"]
        assert "SET onboarded = 1" in sql
        assert "WHERE onboarded IS NULL" in sql, \
            "backfill 要只針對 NULL（唔可以覆蓋已設定嘅值）"

    def test_backfill_is_recorded(self, db):
        """⚠️ 一定要記錄跑過 —— 唔可以每次啟動都跑（會蓋掉新用戶嘅 0）。"""
        import inspect
        src = inspect.getsource(db._run_backfills)
        assert "_applied_migrations" in src
        assert "INSERT INTO _applied_migrations" in src

    def test_new_user_explicit_zero(self):
        """⚠️ 新用戶要**明確**寫 0，唔好靠 NULL 做預設。"""
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        assert "onboarded)" in src and "VALUES (?, ?, ?, 0)" in src, \
            "新用戶建立時冇明確設 onboarded = 0"

    def test_live_db_no_nulls(self):
        """實際 DB 應該已經冇 NULL（backfill 跑過）。"""
        import sqlite3
        p = ROOT / "server" / "wander.db"
        if not p.exists():
            pytest.skip("冇 DB")
        con = sqlite3.connect(p)
        try:
            n = con.execute(
                "SELECT COUNT(*) FROM users WHERE onboarded IS NULL").fetchone()[0]
            total = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        except sqlite3.OperationalError:
            pytest.skip("未 migrate")
        finally:
            con.close()
        if total == 0:
            pytest.skip("冇用戶")
        assert n == 0, f"仲有 {n}/{total} 個用戶 onboarded 係 NULL → 會被逼睇教學"


class TestReplayFromSettings:
    """⚠️ 用戶要求：設定頁要有「指導教學」可以再播一次。"""

    @pytest.fixture(scope="class")
    def settings(self):
        # ⚠️ 「指導教學」搬咗去 SettingsMore（第二層）——
        #    第一層淨係 Profile（用戶要求）
        return (ROOT / "web" / "src" / "components" / "SettingsMore.jsx").read_text(
            encoding="utf-8")

    @pytest.fixture(scope="class")
    def app(self):
        return (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")

    def test_settings_has_section(self, settings):
        assert "指導教學" in settings, "設定頁冇「指導教學」"
        assert "重新播放教學" in settings

    def test_settings_calls_callback(self, settings):
        assert "onReplayTour" in settings

    def test_app_has_replay_state(self, app):
        assert "replayTour" in app

    def test_replay_shows_tour(self, app):
        """條件要包埋 replayTour。"""
        assert "!user.onboarded || replayTour" in app, \
            "重看教學嘅條件唔啱"

    def test_replay_does_not_reset_flag(self, app):
        """
        ⚠️⚠️ 重看**唔可以**將 onboarded 設返 0 ——
           否則用戶重看中途閂咗 app，下次登入又會強制彈教學。
        """
        idx = app.find("replayTour")
        # 搵 onDone handler
        i = app.find("onDone={(name) => {")
        blk = app[i:i + 600]
        assert "setReplayTour(false)" in blk, "重看完冇收返 overlay"
        # 唔應該喺重看分支入面將 onboarded 設 false
        assert "onboarded: false" not in blk, \
            "重看竟然將 onboarded 設返 false —— 會再強制彈教學"
