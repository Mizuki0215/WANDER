"""
像素圖示結構測試
================
⚠️ 為咩要測（同頭像一樣嘅道理）：
   · 圖示係 8×8 字串陣列 —— **打錯一個字元就會靜靜畫錯**
   · 19 個圖示 × 64 格 = 1216 格，肉眼睇唔晒
   · 調色板索引超出 → 程式 fallback 去 pal[0]，唔會有錯誤但顏色錯
     （實測捉到 5 個！money / map / plus / pin / globe）
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ICONS_JS = ROOT / "web" / "src" / "lib" / "pixelicons.js"


@pytest.fixture(scope="module")
def icons() -> dict:
    if not ICONS_JS.exists():
        pytest.skip("搵唔到 pixelicons.js")
    script = (
        f"import('{ICONS_JS.as_uri()}').then(m => "
        "console.log(JSON.stringify({app: m.APP_ICONS, ui: m.UI_ICONS})))"
    )
    r = subprocess.run(["node", "--input-type=module", "-e", script],
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    if r.returncode != 0:
        pytest.skip(f"node 跑唔到: {r.stderr[:200]}")
    return json.loads(r.stdout)


def _all(icons):
    return {**icons["app"], **icons["ui"]}


class TestStructure:
    def test_count(self, icons):
        assert len(_all(icons)) >= 15, f"圖示太少: {len(_all(icons))}"

    @pytest.mark.parametrize("field", ["pal", "grid"])
    def test_has_field(self, icons, field):
        for name, ic in _all(icons).items():
            assert ic.get(field), f"{name} 冇 {field}"

    def test_square_grid(self, icons):
        """⚠️ 一定要正方形 —— 唔係嘅話排列會歪。"""
        for name, ic in _all(icons).items():
            n = len(ic["grid"])
            assert 6 <= n <= 12, f"{name} 有 {n} 行（應該 6-12）"
            for i, row in enumerate(ic["grid"]):
                assert len(row) == n, \
                    f"{name} 第 {i} 行有 {len(row)} 格（應該 {n}）: {row!r}"

    def test_chars_valid(self, icons):
        """
        ⚠️⚠️ 只可以用 '.' 同調色板索引 —— 呢個測捉到 5 個真 bug。
        """
        bad = []
        for name, ic in _all(icons).items():
            n = len(ic["pal"])
            for i, row in enumerate(ic["grid"]):
                for j, ch in enumerate(row):
                    if ch == ".":
                        continue
                    if not ch.isdigit():
                        bad.append(f"{name} ({i},{j}) 非法字元 {ch!r}")
                    elif int(ch) >= n:
                        bad.append(
                            f"{name} ({i},{j}) 索引 {ch} 超出（只有 {n} 色）")
        assert not bad, "圖示有問題：\n  " + "\n  ".join(bad[:12])

    def test_not_empty(self, icons):
        for name, ic in _all(icons).items():
            filled = sum(1 for row in ic["grid"] for c in row if c != ".")
            assert filled >= 8, f"{name} 只有 {filled} 格有嘢"

    def test_colors_hex(self, icons):
        for name, ic in _all(icons).items():
            for c in ic["pal"]:
                assert re.fullmatch(r"#[0-9a-fA-F]{6}", c), \
                    f"{name} 顏色 {c!r} 唔係 hex"

    def test_palette_size(self, icons):
        for name, ic in _all(icons).items():
            assert 1 <= len(ic["pal"]) <= 5, \
                f"{name} 有 {len(ic['pal'])} 色（太多會亂）"


class TestAppIconsComplete:
    """⚠️ 每個 app 都要有圖示 —— 冇嘅話前端出問號。"""

    # ⚠️ 用戶要求：刪走 Trips、Zones 改名做 Saved
    REQUIRED = ["calendar", "discover", "money", "shopping", "saved",
                "map", "friends", "settings"]

    @pytest.mark.parametrize("app_id", REQUIRED)
    def test_app_has_icon(self, icons, app_id):
        assert app_id in icons["app"], f"app「{app_id}」冇像素圖示"

    def test_matches_home_apps(self, icons):
        """
        ⚠️ 圖示 id 一定要同 HomeScreen 嘅 APPS 一致 ——
           唔係嘅話主畫面會出問號（而 build 唔會捉到）。
        """
        home = (ROOT / "web" / "src" / "components" / "HomeScreen.jsx").read_text(
            encoding="utf-8")
        ids = re.findall(r"\{\s*id:\s*'([a-z]+)'", home)
        assert ids, "喺 HomeScreen 搵唔到 APPS"
        missing = [i for i in ids if i not in icons["app"]]
        assert not missing, f"呢啲 app 冇像素圖示: {missing}"

    def test_matches_nav_tabs(self, icons):
        """底部 nav 嘅圖示 id 都要存在。"""
        app = (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")
        # TABS 係 [[id, iconId, label], ...]
        # ⚠️ 只需要第 2 個 group（圖示 id）—— 唔好 unpack 3 個
        ids = [m.group(2) for m in
               re.finditer(r"\['(\w+)',\s*'(\w+)',\s*'[^']+'\]", app)]
        assert ids, "搵唔到 TABS"
        missing = [ic for ic in ids if ic not in _all(icons)]
        assert not missing, f"nav 圖示唔存在: {missing}"


class TestNoEmoji:
    """
    ⚠️ 像素風 UI 唔可以靠 emoji ——
       emoji 每部機唔同樣（Apple 立體、Google 平面、Samsung 又一款），
       而且冇得控制線條，做唔到點陣感。
    """

    def test_appicon_no_emoji(self):
        home = (ROOT / "web" / "src" / "components" / "HomeScreen.jsx").read_text(
            encoding="utf-8")
        # 唔可以再 render {app.icon}（emoji 欄位）
        assert "{app.icon}" not in home, "AppIcon 仲用緊 emoji"

    def test_appicon_uses_pixelicon(self):
        home = (ROOT / "web" / "src" / "components" / "HomeScreen.jsx").read_text(
            encoding="utf-8")
        assert "PixelIcon" in home

    def test_nav_uses_pixelicon(self):
        app = (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")
        assert "<PixelIcon name={icon}" in app, "底部 nav 仲用緊 emoji"
