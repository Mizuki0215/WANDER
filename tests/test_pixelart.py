"""
像素藝術生成器測試
====================
⚠️ 為咩要測一個「產生圖」嘅腳本：
   · 色板索引、尺寸、透明度都係「**錯咗唔會拋錯**」嘅嘢 ——
     出錯只會靜靜產生一張難睇嘅圖
   · 星雲參數（gamma、offset）試過好幾個版本，
     要**鎖住**最後揀嘅值，防止將來改返壞
   · 最重要：**暗部比例**要同參考圖接近（唔可以太光或太暗）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "server"))

PUB = ROOT / "web" / "public"


class TestPalette:
    """色板要同參考圖抽出嘅一致。"""

    @pytest.fixture(scope="class")
    def M(self):
        try:
            import make_pixelart  # noqa
        except ImportError:
            pytest.skip("搵唔到 make_pixelart")
        return make_pixelart

    def test_edge_colors(self, M):
        """
        ⚠️⚠️ 最 signature 嘅特徵 —— 紫左／青右。
           呢兩個色係由參考圖抽出嚟（H≈306° 同 187°），
           改咗就唔係嗰個風格。
        """
        assert M.EDGE_PURPLE == (0xE7, 0x3A, 0xB8)
        assert M.EDGE_CYAN == (0x32, 0xE4, 0xFF)

    def test_rams_monotonic(self, M):
        """色階一定要由暗到亮 —— 唔係嘅話映射會亂。"""
        for name in ("NEBULA_BLUE", "NEBULA_PURPLE"):
            ramp = getattr(M, name)
            lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in ramp]
            for i in range(1, len(lum)):
                # 容許極少波動（±3），但唔可以大幅倒退
                assert lum[i] >= lum[i - 1] - 3, (
                    f"{name} 第 {i} 級比上一級暗：{lum[i-1]:.0f} → {lum[i]:.0f}")

    def test_ramps_same_length(self, M):
        assert len(M.NEBULA_BLUE) == len(M.NEBULA_PURPLE)

    def test_dark_end_is_black(self, M):
        for name in ("NEBULA_BLUE", "NEBULA_PURPLE"):
            r, g, b = getattr(M, name)[0]
            assert r + g + b < 40, f"{name} 最暗一級唔夠黑"


class TestDither:
    def test_bayer_properties(self):
        """Bayer 矩陣要係 0..63 嘅排列（唔可以重複）。"""
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        b = (M.BAYER8 * 64).round().astype(int)
        assert b.shape == (8, 8)
        assert sorted(b.flatten()) == list(range(64)), "Bayer 唔係 0..63 嘅排列"

    def test_dither_range(self):
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        v = np.linspace(0, 1, 64 * 64).reshape(64, 64)
        idx = M.dither(v, levels=26, strength=1.8)
        assert idx.min() >= 0 and idx.max() <= 25
        # 抖動要令相鄰格有差異（唔係的話就係普通量化）
        assert len(set(idx.flatten())) > 15


class TestNebula:
    """
    ⚠️⚠️ 最緊要嘅一組 —— 暗部比例。

       試過三個 gamma：
         1.55 → 太光（成張圖都著色）
         1.75 → 仲係太光
         2.60 → 太暗（只剩一條幼線）
         2.05 → ✓
    """

    @pytest.fixture(scope="class")
    def neb(self):
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        return M.nebula(96, 192, seed=23)

    def test_shape(self, neb):
        assert neb.shape == (192, 96, 3)
        assert neb.dtype == np.uint8

    def test_darkness_matches_reference(self, neb):
        """
        ⚠️⚠️ 參考圖有大約 **47%** 近黑（RGB 總和 < 60）。
           太光 → 冇「深邃星空」感；太暗 → 睇唔到雲。
        """
        dark = (neb.astype(int).sum(axis=2) < 60).mean()
        assert 0.30 < dark < 0.62, (
            f"近黑比例 {dark*100:.0f}%（參考圖 47%）—— "
            f"{'太光' if dark <= 0.30 else '太暗'}")

    def test_has_bright_core(self, neb):
        """要有亮帶，唔可以全部黑。"""
        bright = (neb.astype(int).sum(axis=2) > 380).mean()
        assert bright > 0.005, f"亮部只有 {bright*100:.1f}%，冇星雲"

    def test_blue_and_purple_both_present(self, neb):
        """
        ⚠️ 雙色板混合 —— 要**同時**有藍色區域同紫色區域。
           如果混合參數壞咗，會變成一隻色。
        """
        a = neb.astype(float)
        s = a.sum(axis=2) + 1e-6
        # 用 R/B 比例分辨藍（R 低）同紫（R 高）
        lit = a.sum(axis=2) > 120
        if lit.sum() < 50:
            pytest.skip("太暗，冇足夠亮部判斷")
        rb = (a[:, :, 0] / s)[lit]
        assert rb.max() > 0.32, "冇紫色區域（R/B 比例太低）"
        assert rb.min() < 0.22, "冇藍色區域（R/B 比例太高）"

    def test_deterministic(self):
        """同一個 seed 一定要出同一張圖。"""
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        a = M.nebula(48, 48, seed=99)
        b = M.nebula(48, 48, seed=99)
        assert np.array_equal(a, b)

    def test_different_seeds_differ(self):
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        a = M.nebula(48, 48, seed=1)
        b = M.nebula(48, 48, seed=2)
        assert not np.array_equal(a, b)


class TestChromaticEdge:
    def test_adds_purple_left_cyan_right(self):
        """
        ⚠️ 呢個就係 signature 效果 —— 左邊要偏紫、右邊偏青。
        """
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        # 中間一條白色直條（用 64×64 同 8px 闊 ——
        # ⚠️ 第一版用 32×32 + 2px 闊，邊緣只影響 1px，
        #    效果弱到測試都判斷唔到）
        img = np.zeros((64, 64, 3), np.uint8)
        img[:, 28:36] = 255
        out = M.chromatic_edge(img, 0.95, spread=2)
        left = out[:, 22:28].astype(int)
        right = out[:, 36:42].astype(int)
        # 左邊：紅多過綠（紫）
        assert left[:, :, 0].mean() > left[:, :, 1].mean(), "左邊唔夠紫"
        # 右邊：綠藍多過紅（青）
        assert right[:, :, 2].mean() > right[:, :, 0].mean(), "右邊唔夠青"

    def test_no_change_on_flat(self):
        """全平嘅圖唔應該有變化（唔可以整污糟背景）。"""
        try:
            import make_pixelart as M
        except ImportError:
            pytest.skip("搵唔到")
        img = np.full((16, 16, 3), 40, np.uint8)
        out = M.chromatic_edge(img, 0.9)
        assert abs(int(out.astype(int).sum()) - int(img.astype(int).sum())) < 500


class TestOutputs:
    """⚠️ 產生出嚟嘅檔案要存在、尺寸啱、唔可以係全黑。"""

    FILES = [
        ("icon-192.png", 192), ("icon-512.png", 512), ("icon-180.png", 180),
        ("icon-maskable-192.png", 192), ("icon-maskable-512.png", 512),
        ("comet.png", 256), ("comet-96.png", 96),
    ]

    @pytest.mark.parametrize("name,size", FILES)
    def test_icon_exists_and_square(self, name, size):
        p = PUB / name
        if not p.exists():
            pytest.skip(f"{name} 未產生（跑 make_pixelart.py）")
        im = Image.open(p)
        assert im.size == (size, size), f"{name} 係 {im.size}"

    @pytest.mark.parametrize("name", ["icon-512.png", "comet.png"])
    def test_not_blank(self, name):
        p = PUB / name
        if not p.exists():
            pytest.skip(f"{name} 未產生")
        a = np.asarray(Image.open(p).convert("RGB"))
        assert a.std() > 12, f"{name} 幾乎係純色（std={a.std():.1f}）"
        # 要有亮嘅像素（星星／彗星）
        assert a.max() > 200, f"{name} 完全冇亮部"

    def test_nebula_background(self):
        p = PUB / "nebula.png"
        if not p.exists():
            pytest.skip("nebula.png 未產生")
        im = Image.open(p)
        assert im.width < im.height, "手機背景應該係直向"
        a = np.asarray(im.convert("RGB")).astype(int)
        dark = (a.sum(axis=2) < 60).mean()
        assert 0.25 < dark < 0.68, f"背景近黑 {dark*100:.0f}% 唔啱"


class TestStyleAppliedToCss:
    """CSS 要真係用咗呢批色同背景。"""

    @pytest.fixture(scope="class")
    def css(self):
        return (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")

    def test_edge_vars_defined(self, css):
        for v in ("--edge-purple", "--edge-cyan", "--edge-purple-hi",
                  "--edge-cyan-hi"):
            assert f"{v}:" in css, f"冇定義 {v}"

    def test_uses_nebula_bg(self, css):
        assert "nebula.png" in css, "冇用星雲背景"

    def test_chromatic_filter(self, css):
        assert "drop-shadow(-1px 0 0 var(--edge-purple))" in css
        assert "drop-shadow(1px 0 0 var(--edge-cyan))" in css

    def test_manifest_matches(self):
        import json
        p = ROOT / "web" / "public" / "manifest.webmanifest"
        if not p.exists():
            pytest.skip("冇 manifest")
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["theme_color"].lower() in ("#000018", "#000018ff"), \
            f"manifest theme_color 未更新：{d['theme_color']}"
