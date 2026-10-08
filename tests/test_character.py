"""
像素角色測試
==============
⚠️ 為咩要測：
   · 角色係程序化畫嘅（橢圓 + 多邊形 + 光影）——
     參數一改就可能出「冇眼」「大細眼」「瀏海蓋眼」呢類問題，
     而且**唔會拋錯**，只會靜靜畫錯
   · 實測捉到：瀏海（y≈16）蓋住對眼（y≈15.6）→ 角色睇落冇眼
   · 用戶原話：「你個示範教學呢第一就係個人物太樣衰啦」
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
PUB = ROOT / "web" / "public"


@pytest.fixture(scope="module")
def C():
    try:
        import make_character  # noqa
    except ImportError:
        pytest.skip("搵唔到 make_character")
    return make_character


class TestGeometry:
    def test_size(self, C):
        """⚠️ 一定要夠大 —— 16×16 畫唔到眼、鼻、嘴。"""
        assert C.W >= 32 and C.H >= 40, f"{C.W}×{C.H} 太細"

    def test_renders(self, C):
        rgb = C.make_character()
        assert rgb.shape == (C.H, C.W, 3)
        assert rgb.dtype == np.uint8

    def test_not_empty(self, C):
        rgb = C.make_character()
        assert (rgb.sum(axis=2) > 30).mean() > 0.35, "角色佔太少畫面"


class TestFace:
    """
    ⚠️⚠️ 最易出錯嘅部分（實測捉到瀏海蓋眼）。
    """

    def test_eyes_visible(self, C):
        """
        ⚠️⚠️ 眼睛一定要露得出嚟。

           實測 bug：瀏海橢圓最低點 y≈16.1，
           但對眼喺 y≈15.6 → **完全被蓋住**，
           角色睇落「冇眼」，就係用戶話「太樣衰」嘅主因。

           檢查方法：喺眼睛應該喺嘅位置，要搵到「暗色」像素
           （虹膜色嘅亮度遠低於皮膚／頭髮）。
        """
        rgb = C.make_character(mood="smile", arm="wave")
        # 眼睛水平帶
        eye_band = rgb[int(C.H * 0.28):int(C.H * 0.42), :, :]
        lum = eye_band.astype(int).sum(axis=2)
        dark_ratio = (lum < 200).mean()
        assert dark_ratio > 0.04, (
            f"眼睛位置只有 {dark_ratio*100:.1f}% 暗色像素 —— "
            f"可能被瀏海蓋住咗（對眼要夠大夠深色）")

    def test_two_eyes_symmetric(self, C):
        """左右眼要對稱 —— 唔可以一大一細或者位置偏埋一邊。"""
        rgb = C.make_character(mood="smile", arm="wave")
        band = rgb[int(C.H * 0.28):int(C.H * 0.42), :, :]
        lum = band.astype(int).sum(axis=2)
        dark = lum < 200
        left = dark[:, :C.W // 2].sum()
        right = dark[:, C.W // 2:].sum()
        assert left > 0 and right > 0, "有一邊冇眼"
        ratio = min(left, right) / max(left, right)
        assert ratio > 0.7, f"左右眼差太遠（{left} vs {right}）—— 唔對稱"

    def test_eye_not_glasses(self, C):
        """
        ⚠️ 眼**唔可以**係「白色橢圓 + 中間深珠」——
           個白圈會睇落似**眼鏡框**（第一版嘅問題）。
           正確：深色眼眶 → 彩色虹膜 → 高光。
           檢查：眼睛區域唔應該有大量**純白**像素。
        """
        rgb = C.make_character(mood="smile", arm="wave")
        band = rgb[int(C.H * 0.28):int(C.H * 0.42), :, :].astype(int)
        pure_white = (band > 245).all(axis=2).mean()
        assert pure_white < 0.06, \
            f"眼睛帶有 {pure_white*100:.1f}% 純白 —— 似戴眼鏡"

    def test_mouth_present(self, C):
        """嘴要喺眼下面，而且唔可以同眼重疊。"""
        rgb = C.make_character(mood="smile", arm="wave")
        # 嘴應該喺 H 的 40-52%
        mouth_band = rgb[int(C.H * 0.40):int(C.H * 0.54), C.W // 3:C.W * 2 // 3, :]
        lum = mouth_band.astype(int).sum(axis=2)
        assert (lum < 260).mean() > 0.02, "搵唔到嘴"

    @pytest.mark.parametrize("mood", ["smile", "happy", "oh"])
    def test_all_moods_render(self, C, mood):
        rgb = C.make_character(mood=mood)
        assert rgb.shape == (C.H, C.W, 3)

    def test_moods_differ(self, C):
        """唔同表情一定要真係唔同 —— 唔可以全部一樣。"""
        a = C.make_character(mood="smile")
        b = C.make_character(mood="oh")
        assert not np.array_equal(a, b), "唔同表情畫出嚟一樣"


class TestPalette:
    def test_all_materials_have_4_levels(self, C):
        """
        ⚠️ 每個材质最少 4 級色階。
           只有一級 → 變成一嚿色 → 就係第一版「樣衰」嘅主因。
        """
        for mat, ramp in C.RAMP.items():
            if mat in ("eye",):        # 眼白唔需要 4 級
                assert len(ramp) >= 2
            else:
                assert len(ramp) >= 4, f"{mat} 只有 {len(ramp)} 級色階"

    def test_outline_dark(self, C):
        r, g, b = C.OUTLINE
        assert r + g + b < 140, "描邊唔夠黑"

    def test_hair_rim_colors(self, C):
        """⚠️ 頭髮邊緣嘅紫／青係參考圖最 signature 嘅細節。"""
        assert C.HAIR_PURPLE[2] > C.HAIR_PURPLE[1], "紫要藍多過綠"
        assert C.HAIR_CYAN[2] > C.HAIR_CYAN[0] * 2, "青要藍遠多過紅"


class TestOutputs:
    FRAMES = ["mascot-hello", "mascot-point", "mascot-happy",
              "mascot-oh", "mascot-face"]

    @pytest.mark.parametrize("name", FRAMES)
    def test_png_exists(self, name):
        p = PUB / f"{name}.png"
        if not p.exists():
            pytest.skip(f"{name}.png 未產生（跑 make_character.py）")
        im = Image.open(p)
        assert im.width > 60 and im.height > 60, f"{name} 太細 {im.size}"

    @pytest.mark.parametrize("name", ["mascot-hello", "mascot-happy"])
    def test_png_not_blank(self, name):
        p = PUB / f"{name}.png"
        if not p.exists():
            pytest.skip(f"{name}.png 未產生")
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        assert a.std() > 20, f"{name} 幾乎純色（std={a.std():.1f}）"

    def test_different_frames_differ(self):
        """唔同表情嘅 PNG 一定要唔同 —— 唔可以產生咗全部一樣。"""
        paths = [PUB / f"mascot-{n}.png"
                 for n in ("hello", "point", "happy", "oh")]
        if not all(p.exists() for p in paths):
            pytest.skip("未產生")
        arrs = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
        for i in range(len(arrs) - 1):
            assert not np.array_equal(arrs[i], arrs[i + 1]), \
                f"第 {i} 同 {i+1} 個 frame 一樣"


class TestOnboardingUsesImages:
    """⚠️ Onboarding 要用 PNG 角色，唔可以再用 16×16 手畫 SVG。"""

    @pytest.fixture(scope="class")
    def src(self):
        p = ROOT / "web" / "src" / "components" / "Onboarding.jsx"
        if not p.exists():
            pytest.skip("搵唔到 Onboarding.jsx")
        return p.read_text(encoding="utf-8")

    def test_uses_png(self, src):
        assert "mascot-" in src and ".png" in src, "冇用 PNG 角色"

    def test_no_handdrawn_svg(self, src):
        assert "mascotSvg" not in src, "仲用緊 16×16 手畫 SVG"
