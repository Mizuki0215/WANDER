"""
像素頭像測試
============
⚠️ 為咩要測 avatars.js（一個前端檔案）：
   · 頭像係 8×8 字串陣列 —— **打錯一個字元就會爛咗**，
     而且唔會有錯誤，只會靜靜畫錯
   · 14 個頭像 × 64 格 = 896 格，靠肉眼睇唔晒
   · 所以用 Python 重新 parse 一次，驗證結構
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AVATARS_JS = ROOT / "web" / "src" / "lib" / "avatars.js"


@pytest.fixture(scope="module")
def avatars() -> list[dict]:
    """用 node 匯出 avatars.js 嘅資料（避免喺 Python 重寫 JS parser）。"""
    if not AVATARS_JS.exists():
        pytest.skip("搵唔到 avatars.js")
    script = (
        f"import('{AVATARS_JS.as_uri()}').then(m => "
        "console.log(JSON.stringify(m.PIXEL_AVATARS)))"
    )
    r = subprocess.run(["node", "--input-type=module", "-e", script],
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    if r.returncode != 0:
        pytest.skip(f"node 跑唔到: {r.stderr[:200]}")
    return json.loads(r.stdout)


class TestStructure:
    def test_count(self, avatars):
        """⚠️ 用戶要求「多啲唔同嘅元素」—— 而家有 37 個。"""
        assert len(avatars) >= 30, f"頭像太少: {len(avatars)}"

    def test_has_requested_elements(self, avatars):
        """
        ⚠️ 用戶明確點名要嘅元素：
           「例如豬、狗啦呢啲，之後或者扭計骰啊、手機呀、
            鴨呀、兔仔呀呢啲都可以嘅。」
        """
        ids = {a["id"] for a in avatars}
        for want, label in [("pig", "豬"), ("dog", "狗"),
                            ("rubik", "扭計骰"), ("phone", "手機"),
                            ("duck", "鴨"), ("rabbit", "兔仔")]:
            assert want in ids, f"冇「{label}」（用戶明確要求）"

    def test_unique_ids(self, avatars):
        ids = [a["id"] for a in avatars]
        assert len(ids) == len(set(ids)), f"有重複 id: {ids}"

    @pytest.mark.parametrize("field", ["id", "name", "pal", "grid"])
    def test_has_field(self, avatars, field):
        for a in avatars:
            assert a.get(field), f"{a.get('id')} 冇 {field}"

    def test_grid_is_16x16(self, avatars):
        """
        ⚠️ 一定要 16×16。

           ⚠️ 由 8×8 升到 16×16 嘅原因（用戶要求「再 Q 啲、精緻啲」）：
              · 8×8 嘅眼只可以係 1 格 → 做唔到「大眼 + 高光」= 唔 Q
              · 8×8 做唔到腮紅、鼻、嘴同時存在
        """
        for a in avatars:
            assert len(a["grid"]) == 16, \
                f"{a['id']} 有 {len(a['grid'])} 行（要 16）"
            for i, row in enumerate(a["grid"]):
                assert len(row) == 16, \
                    f"{a['id']} 第 {i} 行有 {len(row)} 格（要 16）: {row!r}"

    def test_grid_chars_valid(self, avatars):
        """
        ⚠️ 只可以用 '.'（透明）同調色板索引（0..len(pal)-1）。
           打錯一個字元就會畫錯或者 crash。
        """
        for a in avatars:
            n = len(a["pal"])
            for i, row in enumerate(a["grid"]):
                for j, ch in enumerate(row):
                    assert ch == "." or ch.isdigit(), \
                        f"{a['id']} ({i},{j}) 有非法字元 {ch!r}"
                    if ch.isdigit():
                        assert int(ch) < n, \
                            f"{a['id']} ({i},{j}) 索引 {ch} 超出調色板（只有 {n} 色）"

    def test_not_empty(self, avatars):
        """每個頭像都要有嘢，唔可以全透明。"""
        for a in avatars:
            filled = sum(1 for row in a["grid"] for c in row if c != ".")
            # ⚠️ 16×16 = 256 格。角色大約佔 120-220，
            #    但**環形**（戒指）天生多透明格（只有 ~90）。
            #    門檻設 70 —— 仍然捉得到「近乎全空」嘅失誤。
            assert filled >= 70, f"{a['id']} 只有 {filled} 格有嘢（太少）"

    def test_palette_size(self, avatars):
        """
        ⚠️ 由上調到 4-8 色 —— 16×16 要更多層次先「精緻」。
           但仍然有上限（>8 色就會睇落亂）。
        """
        for a in avatars:
            assert 4 <= len(a["pal"]) <= 8, \
                f"{a['id']} 有 {len(a['pal'])} 色（要 4-8）"

    def test_colors_are_hex(self, avatars):
        for a in avatars:
            for c in a["pal"]:
                assert re.fullmatch(r"#[0-9a-fA-F]{6}", c), \
                    f"{a['id']} 顏色 {c!r} 唔係 hex"

    def test_has_required_icons(self, avatars):
        """用戶明確要求要有呢幾個。"""
        ids = {a["id"] for a in avatars}
        for want in ("moon", "star", "cloud", "flower", "ring"):
            assert want in ids, f"冇「{want}」（用戶明確要求）"


class TestBackendValidation:
    """後端一定要驗證 avatar 值 —— 唔可以任由用戶塞任意字串。"""

    def test_avatar_ids_match(self, avatars):
        """⚠️ 前端同後端嘅 id 清單一定要一致，否則設定會 400。"""
        import sys
        sys.path.insert(0, str(ROOT / "server"))
        from app.main import AVATAR_IDS
        front = {a["id"] for a in avatars}
        assert front == AVATAR_IDS, (
            f"唔一致！\n  前端多咗: {front - AVATAR_IDS}\n  後端多咗: {AVATAR_IDS - front}")

    def test_svg_generation(self):
        """avatarSvg 要產生有效 SVG。"""
        script = (
            f"import('{AVATARS_JS.as_uri()}').then(m => {{"
            "  const s = m.avatarSvg('star', { size: 40 });"
            "  console.log(JSON.stringify({ ok: s.startsWith('<svg') && s.endsWith('</svg>'),"
            "    len: s.length, empty: m.avatarSvg('nope', { size: 40 }) }));"
            "})"
        )
        r = subprocess.run(["node", "--input-type=module", "-e", script],
                           capture_output=True, text=True, cwd=ROOT, timeout=60)
        assert r.returncode == 0, r.stderr[:200]
        d = json.loads(r.stdout)
        assert d["ok"], "SVG 格式唔啱"
        assert d["len"] > 300
        assert d["empty"] == "", "無效 id 應該回空字串"
