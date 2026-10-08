"""
吉祥物「用戶自備圖」機制測試
==============================
⚠️ 用戶揀咗 **A 方案**：「你搵人畫／我自己生成 4 張角色圖，你接入。」

⚠️ 為咩要測呢個：
   呢個機制嘅重點係「**用戶放圖就自動用，唔放就 fallback**」——
   如果 fallback 壞咗，用戶放圖之前教學就冇角色（白格）；
   如果 fallback 邏輯寫錯（例如無限迴圈），就會爆 stack。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

PUB = ROOT / "web" / "public"
PROC = PUB / "proc"

FRAMES = ["hello", "point", "happy", "oh"]


class TestTwoLayerLayout:
    """
    ⚠️⚠️ 一定要**兩層分開**：
         ① web/public/mascot-X.png        ← 用戶自己生成（可選）
         ② web/public/proc/mascot-X.png   ← 程序化 fallback（一定有）
       如果兩個放同一層就會互相覆蓋。
    """

    @pytest.mark.parametrize("frame", FRAMES)
    def test_procedural_exists(self, frame):
        p = PROC / f"mascot-{frame}.png"
        assert p.exists(), \
            f"冇 fallback：{p}（跑 engine/make_character.py）"

    def test_not_in_public_root(self):
        """
        ⚠️ 程序化圖**唔可以**直接放 public/ 根目錄 ——
           否則用戶放自己嗰張就會覆蓋咗 fallback。
        """
        stray = [f for f in FRAMES if (PUB / f"mascot-{f}.png").exists()]
        # 如果存在，應該係**用戶放嘅**，唔係程序化嘅（尺寸會唔同）
        for f in stray:
            from PIL import Image
            im = Image.open(PUB / f"mascot-{f}.png")
            proc = Image.open(PROC / f"mascot-{f}.png")
            assert im.size != proc.size or im.tobytes() != proc.tobytes(), \
                f"public/mascot-{f}.png 同 proc/ 一樣 —— 可能係程序化圖放錯位"

    def test_procedural_has_all_frames(self):
        found = {p.stem.replace("mascot-", "") for p in PROC.glob("mascot-*.png")}
        for f in FRAMES:
            assert f in found, f"proc/ 冇 mascot-{f}.png"


class TestFallbackLogic:
    """⚠️ 前端嘅 fallback 一定要正確。"""

    @pytest.fixture(scope="class")
    def src(self):
        return (ROOT / "web" / "src" / "components" / "Onboarding.jsx").read_text(
            encoding="utf-8")

    def test_tries_user_image_first(self, src):
        assert "'/mascot-${frame}.png'" in src or "/mascot-${frame}.png" in src, \
            "冇試用戶嗰張"

    def test_falls_back_to_proc(self, src):
        assert "/proc/mascot-${frame}.png" in src, "冇 fallback 去 proc/"

    def test_has_onerror(self, src):
        assert "onError" in src, "冇 onError → 用戶未放圖就會爛圖示"

    def test_no_infinite_loop(self, src):
        """
        ⚠️⚠️ onError 一定要有 guard ——
           如果 fallback 都 404，`onError` 會再觸發 →
           無限迴圈 → 爆 stack。
        """
        i = src.index("onError")
        blk = src[i:i + 420]
        assert "data-fb" in blk or "dataset.fb" in blk, \
            "onError 冇防無限迴圈嘅 guard"
        assert "return" in blk, "onError 冇 early return"


class TestChecker:
    """⚠️ `check_mascot.py` 係用戶放圖之前嘅守門員。"""

    @pytest.fixture(scope="class")
    def C(self):
        try:
            import check_mascot  # noqa
        except ImportError:
            pytest.skip("搵唔到 check_mascot")
        return check_mascot

    def test_frames_match(self, C):
        names = [n.replace("mascot-", "") for n, _ in C.FRAMES]
        assert sorted(names) == sorted(FRAMES), \
            f"檢查器嘅 frame 清單同前端唔一致：{names}"

    def test_min_size_sensible(self, C):
        assert C.MIN_W >= 200 and C.MIN_H >= 300, \
            "建議大細太細（用戶生成嘅圖要縮到 90px 用）"

    def test_detects_opaque_background(self, C, tmp_path):
        """⚠️ AI 生成好易出白底 —— 要捉到。"""
        from PIL import Image
        p = tmp_path / "mascot-hello.png"
        Image.new("RGB", (600, 800), (255, 255, 255)).save(p)
        d = C.analyse(p)
        assert d["alpha"] is False, "檢查器睇唔出冇透明通道"
        assert d["format"] == "PNG" or d["format"] == "JPEG"

    def test_detects_tiny_subject(self, C, tmp_path):
        """⚠️ 主角太細 → 縮到 90px 變一粒塵。"""
        import numpy as np
        from PIL import Image
        a = np.zeros((800, 600, 4), np.uint8)
        a[380:420, 280:320] = [255, 100, 150, 255]     # 只佔 0.3%
        p = tmp_path / "mascot-hello.png"
        Image.fromarray(a, "RGBA").save(p)
        d = C.analyse(p)
        assert d["fill_ratio"] < 0.08, \
            f"檢查器計錯主角比例：{d['fill_ratio']}"

    def test_accepts_good_image(self, C, tmp_path):
        import numpy as np
        from PIL import Image
        a = np.zeros((800, 600, 4), np.uint8)
        # 造一個有雜色嘅角色（唔可以單色）
        rng = np.random.default_rng(7)
        a[80:760, 150:450, :3] = rng.integers(0, 255, (680, 300, 3))
        a[80:760, 150:450, 3] = 255
        p = tmp_path / "mascot-hello.png"
        Image.fromarray(a, "RGBA").save(p)
        d = C.analyse(p)
        assert d["alpha"] is True
        assert 0.1 < d["fill_ratio"] < 0.95
        assert d["bottom_gap"] < 0.15

    def test_auto_fix_removes_flat_bg(self, C):
        """
        ⚠️ `--fix` 只可以處理**純色**背景。
           漸變／圖案背景去唔到 —— 要用 remove.bg。
        """
        import inspect
        src = inspect.getsource(C.auto_fix)
        assert "Counter" in src, "auto_fix 應該搵最常見嘅邊緣色做背景"
        assert "--fix" in inspect.getsource(C.main) or "fix" in src


class TestDocs:
    """⚠️ 用戶要一份可以照跟嘅指引。"""

    @pytest.fixture(scope="class")
    def doc(self):
        p = ROOT / "docs" / "mascot" / "README.md"
        if not p.exists():
            pytest.skip("搵唔到指引")
        return p.read_text(encoding="utf-8")

    @pytest.mark.parametrize("frame", FRAMES)
    def test_doc_lists_frame(self, doc, frame):
        assert f"mascot-{frame}.png" in doc, f"指引冇提 mascot-{frame}.png"

    def test_doc_has_prompts(self, doc):
        assert "pixel art character sprite" in doc, "冇提示詞"
        assert doc.count("```") >= 8, "提示詞唔完整"

    def test_doc_has_specs(self, doc):
        for k in ["PNG", "透明", "大細"]:
            assert k in doc, f"指引冇講「{k}」"

    def test_doc_is_honest(self, doc):
        """⚠️ 要老實講「我生成唔到圖」。"""
        assert "生成唔到圖" in doc or "冇圖像生成能力" in doc, \
            "指引冇老實講我生成唔到圖"


class TestSpaFallback:
    """
    ⚠️⚠️ SPA fallback 唔可以食咗「資源」路徑。

       原本：所有搵唔到嘅路徑都回 `index.html`（200）。
       結果：`/mascot-hello.png`（未放）回 **HTML** →
             瀏覽器當佢係圖片 decode → 失敗 → `onError`。
            雖然最後 fallback 成功，但：
              · 白白下載幾 KB index.html
              · 狀態碼係 200 而唔係 404 → 診斷困難
    """

    @pytest.fixture(scope="class")
    def src(self):
        raw = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        # 去 Python 註解（唔可以 match 到自己解釋 bug 嘅註解）
        return "\n".join(
            l for l in raw.split("\n")
            if not re.sub(r'(?<![\'"\"])\s*#.*$', '', l).strip().startswith("#"))

    def test_has_suffix_guard(self, src):
        i = src.index("def spa(")
        blk = src[i:i + 1600]
        assert "raise HTTPException(404" in blk, "spa() 冇回 404 嘅路徑"
        assert "\\.png" in blk or "[a-z0-9]{2,12}$" in blk, \
            "spa() 冇判斷「有副檔名 = 資源」"

    def test_suffix_pattern_behaviour(self):
        """
        ⚠️ 直接測個 pattern 嘅行為 —— 唔靠由 source 抽 regex（太脆弱）。
           呢個 pattern 要同 `main.py` 用嘅一樣。
        """
        pat = re.compile(r"\.[a-z0-9]{2,12}$", re.I)
        for good in ["a.png", "sw.js", "x.css", "manifest.webmanifest",
                     "icon-512.png", "mascot-hello.png", "proc/mascot-hello.png"]:
            assert pat.search(good), f"pattern 捉唔到「{good}」"
        for route in ["settings", "friends", "join", "api/x", "trips/123"]:
            assert not pat.search(route), f"pattern 誤中路由「{route}」"

    def test_proc_path_has_suffix(self):
        """⚠️ fallback 路徑 `/proc/mascot-X.png` 一定要有副檔名（唔會誤中）。"""
        pat = re.compile(r"\.[a-z0-9]{2,12}$", re.I)
        for f in FRAMES:
            assert pat.search(f"proc/mascot-{f}.png")


class TestUserProvidedArt:
    """
    ⚠️⚠️ 用戶畀咗 6 張角色插畫，要求「直接用佢」+「褪背景」。

       呢個 class 守住「白色被褪走」呢個坑 ——
       AI 去背當「白色 = 背景」，食咗角色嘅白髮／白西裝。
    """

    @pytest.mark.parametrize("name", ["mascot-hello", "mascot-point",
                                      "mascot-happy", "mascot-oh"])
    def test_user_art_installed(self, name):
        """4 個 frame 都要有圖（用戶提供）。"""
        assert (PUB / f"{name}.png").exists(), f"冇 {name}.png"

    @pytest.mark.parametrize("name", ["mascot-hello", "mascot-point",
                                      "mascot-happy", "mascot-oh"])
    def test_has_transparency(self, name):
        from PIL import Image
        import numpy as np
        a = np.array(Image.open(PUB / f"{name}.png").convert("RGBA"))
        alpha = a[:, :, 3]
        assert (alpha < 30).mean() > 0.20, \
            f"{name} 透明比例太低（{(alpha<30).mean()*100:.0f}%）—— 背景冇褪？"
        assert (alpha > 200).mean() > 0.05, f"{name} 幾乎全透明 —— 褪多咗？"

    def test_no_opaque_full_frame(self):
        """
        ⚠️ 唔可以四隻角都係實色（= 有背景框）。
        """
        from PIL import Image
        import numpy as np
        for name in ["mascot-hello", "mascot-point", "mascot-happy", "mascot-oh"]:
            a = np.array(Image.open(PUB / f"{name}.png").convert("RGBA"))
            corners = [a[0, 0, 3], a[0, -1, 3], a[-1, 0, 3], a[-1, -1, 3]]
            assert sum(1 for c in corners if c > 200) < 3, \
                f"{name} 四隻角有實色 → 背景未褪"

    def test_size_reasonable(self):
        """⚠️ 太大會拖慢載入（6 張加埋 ~900KB 已經係上限）。"""
        total = sum((PUB / f"{n}.png").stat().st_size
                    for n in ["mascot-hello", "mascot-point",
                              "mascot-happy", "mascot-oh"])
        assert total < 1_500_000, f"4 張圖合計 {total/1024:.0f}KB，太大"

    def test_css_drops_pixelated(self):
        """
        ⚠️⚠️ 插畫唔可以用 `image-rendering: pixelated` ——
           嗰個係為 36×44 低解像像素圖而設；
           高解像插畫用咗會起格仔。
        """
        import re
        css = (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")
        i = css.index(".onb-bubble")
        blk = css[i:i + 900]
        assert "image-rendering: auto" in blk, \
            "⚠️ 仲用緊 pixelated（插畫會起格）"
        # ⚠️ 大細要夠大先睇到插畫細節
        m = re.search(r"height:\s*clamp\((\d+)px", blk)
        assert m and int(m.group(1)) >= 100, \
            f"吉祥物太細（{m.group(1) if m else '?'}px）—— 插畫細節睇唔到"


class TestCutoutTool:
    """⚠️ `engine/cutout.py` —— 去背工具。"""

    @pytest.fixture(scope="class")
    def src(self):
        p = ROOT / "engine" / "cutout.py"
        if not p.exists():
            pytest.skip("搵唔到 cutout.py")
        raw = p.read_text(encoding="utf-8")
        return "\n".join(l for l in raw.split("\n")
                         if not l.strip().startswith("#"))

    def test_smart_bg_rule(self, src):
        """
        ⚠️⚠️ 核心：背景**似白**就只可以 flood fill；
           背景**唔似白**就可以全域褪。
           呢個就係「唔食白西裝」嘅關鍵。
        """
        assert "bg_is_whitish" in src, "冇分辨「白底 vs 非白底」"
        assert "flood" in src.lower() or "ndimage.label" in src, \
            "白底要由邊界 flood fill"
        assert "outside = near_bg" in src, "非白底要全域褪"

    def test_detects_bg_from_edges(self, src):
        """⚠️ 由四邊估背景色（唔可以由全圖 —— 角色可能佔多數）。"""
        i = src.index("def detect_bg(")
        blk = src[i:i + 700]
        assert "a[0]" in blk and "a[-1]" in blk, "冇用四邊估背景"
        assert "Counter" in blk, "應該用「最常見」而唔係「平均」"

    def test_hole_checker(self, src):
        """⚠️ 要捉到「白色被褪走」（實心度太低）。"""
        i = src.index("def check_holes(")
        blk = src[i:i + 1400]
        assert "fill" in blk, "冇計實心度"
        assert "suspicious" in blk, "冇判斷「可疑」"

    def test_feathers_edges(self, src):
        """⚠️ 唔羽化嘅話縮細會有鋸齒。"""
        i = src.index("def cutout(")
        blk = src[i:i + 2600]
        assert "feather" in blk and "distance_transform" in blk, \
            "冇邊緣羽化"
