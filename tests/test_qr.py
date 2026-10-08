"""
QR Code 產生器測試
==================
⚠️⚠️ 為咩一定要用**真正解碼器**驗證：
   自己寫 QR encoder 最恐怖嘅地方係 ——
   錯咗唔會有錯誤訊息，只會「掃唔到」。
   結構檢查（finder pattern 啱唔啱）完全捉唔到 format info transpose、
   mask 冇應用到、資料放置次序錯 呢類 bug。

   所以呢個測試用 OpenCV 嘅 QRCodeDetector 真解碼，
   確認「畫出嚟嘅 QR 係真嘅掃得到」。

⚠️ 實測捉到嘅 bug（如果冇呢個測試，永遠唔會知）：
   ① format info 位置 transpose（row/col 掉轉）→ 掃唔到
   ② _place_data 污染 reserved map → mask 完全冇應用到 → 掃唔到
   ③ version 選擇太保守（v1 裝得落都揀 v2）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander import qr as Q  # noqa: E402

# OpenCV 係可選嘅驗證工具（冇都跑得，只係 skip 真解碼）
try:
    import numpy as np
    import cv2
    HAS_CV = True
except ImportError:
    HAS_CV = False


def _decode(mx) -> str:
    """畫成圖再用 OpenCV 真解碼。"""
    scale, border = 10, 4
    n = len(mx)
    size = (n + border * 2) * scale
    img = np.full((size, size), 255, dtype=np.uint8)
    for y, row in enumerate(mx):
        for x, v in enumerate(row):
            if v:
                y0, x0 = (y + border) * scale, (x + border) * scale
                img[y0:y0 + scale, x0:x0 + scale] = 0
    txt, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    return txt


SAMPLES = [
    "http://192.168.1.100:8787",
    "http://192.168.1.100:8787",
    "https://wander.example.com",
    "A",
    "福岡旅行 2027",
    "http://192.168.1.100:8787/join/ABCD1234",
    "Wander — 一齊計劃旅行",
    "https://wander.app/share/abcdefghijklmnop",
    "🛒 購物清單",
    "0" * 100,
]


@pytest.mark.skipif(not HAS_CV, reason="冇 OpenCV，做唔到真解碼驗證")
class TestRealDecode:
    """
    ⚠️ 最重要嘅測試：真解碼。
       「畫得出」同「掃得到」係兩件事。
    """

    @pytest.mark.parametrize("text", SAMPLES)
    def test_roundtrip(self, text):
        mx = Q.matrix(text)
        assert mx, f"產生唔到 QR: {text[:40]}"
        assert _decode(mx) == text, f"解碼唔一致: {text[:40]}"


class TestStructure:
    """唔靠 OpenCV 嘅結構檢查（OpenCV 冇裝都跑得）。"""

    def test_finder_patterns(self):
        mx = Q.matrix("https://example.com")
        n = len(mx)
        for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
            for i in range(7):
                for j in range(7):
                    want = (i in (0, 6) or j in (0, 6)
                            or (2 <= i <= 4 and 2 <= j <= 4))
                    assert mx[r0 + i][c0 + j] == want, f"finder ({r0},{c0}) 錯"

    def test_separators_are_light(self):
        mx = Q.matrix("https://example.com")
        n = len(mx)
        for i in range(8):
            assert mx[7][i] is False, "左上 separator 應該係白"
            assert mx[i][7] is False, "左上 separator 應該係白"
        assert mx[n - 8][8] is True, "固定暗模組應該係黑"

    def test_timing_patterns(self):
        mx = Q.matrix("https://example.com")
        n = len(mx)
        for i in range(8, n - 8):
            assert mx[6][i] == (i % 2 == 0), f"橫 timing 第 {i} 格錯"
            assert mx[i][6] == (i % 2 == 0), f"直 timing 第 {i} 格錯"

    def test_dark_ratio_reasonable(self):
        """黑白比例要合理 —— 一面倒係邊個都掃唔到。"""
        mx = Q.matrix("https://example.com/quite/a/long/path/here")
        n = len(mx)
        dark = sum(1 for r in mx for v in r if v) / (n * n)
        assert 0.3 < dark < 0.7, f"黑白比例 {dark:.0%} 唔合理"


class TestVersionSelection:
    def test_smallest_version(self):
        """⚠️ 唔可以無謂用大 version（大 16% 已經好明顯）。"""
        # v1-L 容量 17 bytes；"A" 一定係 v1
        assert len(Q.matrix("A")) == 21
        # 17 bytes 都應該係 v1（實測踩過：粗略估 overhead 會誤判成 v2）
        assert len(Q.matrix("x" * 17)) == 21

    def test_grows_with_content(self):
        sizes = [len(Q.matrix("x" * n)) for n in (5, 50, 200, 500)]
        assert sizes == sorted(sizes), f"應該隨內容增長: {sizes}"

    def test_too_long_returns_none(self):
        assert Q.matrix("x" * 5000) is None

    def test_empty_returns_none(self):
        assert Q.matrix("") is None


class TestDeterminism:
    def test_same_input_same_output(self):
        """⚠️ 同一 input 一定要同一 output（唔可以有隨機 mask）。"""
        a = Q.matrix("https://example.com")
        b = Q.matrix("https://example.com")
        assert a == b

    def test_different_input_different_output(self):
        assert Q.matrix("https://a.com") != Q.matrix("https://b.com")


class TestECC:
    """Reed-Solomon 用標準測試向量驗證。"""

    def test_known_vector(self):
        # Thonky 教學嘅標準例子（v1-M）
        data = [0x40, 0xD2, 0x75, 0x47, 0x76, 0x17, 0x32, 0x06,
                0x27, 0x26, 0x96, 0xC6, 0xC6, 0x96, 0x70, 0xEC]
        want = [0xBC, 0x2A, 0x90, 0x13, 0x6B, 0xAF, 0xEF, 0xFD, 0x4B, 0xE0]
        assert Q._rs_encode(data, 10) == want

    def test_generator_polynomial(self):
        g = Q._rs_generator(10)
        assert g == [0x1, 0xD8, 0xC2, 0x9F, 0x6F, 0xC7,
                     0x5E, 0x5F, 0x71, 0x9D, 0xC1]

    def test_gf_field(self):
        assert Q._EXP[0] == 1
        assert Q._EXP[8] == 29
        assert Q._LOG[3] == 25

    def test_byte_mode_encoding(self):
        """手算驗證：'A' v1-L = 0x40 0x14 0x10 + pad。"""
        got = Q._encode_data("A", 1, "L")[:3]
        assert got == [0x40, 0x14, 0x10]


class TestFormatInfo:
    """
    ⚠️⚠️ Format info 位置係最易錯嘅位 —— 實測踩過 transpose bug。
       錯咗唔會有錯誤訊息，只係「掃唔到」。

       標準表（ISO/IEC 18004 Table C.1）EC level L 嘅 8 個值：
    """

    TABLE_L = {
        0: "111011111000100", 1: "111001011110011",
        2: "111110110101010", 3: "111100010011101",
        4: "110011000101111", 5: "110001100011000",
        6: "110110001000001", 7: "110100101110110",
    }

    @staticmethod
    def _read(mx):
        """
        讀返第一份 format info。

        ⚠️ 要**反轉**先等於標準表 ——
           標準表（ISO 18004 Table C.1）係 MSB 先寫（bit14…bit0），
           但 QR 擺位係 bit0 擺第一格。所以讀出嚟係反轉嘅。
        """
        pts = ([(i, 8) for i in range(6)]
               + [(7, 8), (8, 8), (8, 7)]
               + [(8, 14 - i) for i in range(9, 15)])
        return "".join("1" if mx[r][c] else "0" for r, c in pts)[::-1]

    @pytest.mark.parametrize("text", [
        "A", "https://example.com", "http://192.168.1.100:8787",
        "福岡旅行", "x" * 60,
    ])
    def test_matches_standard_table(self, text):
        """⚠️ 寫出嚟嘅 format 一定要係標準表入面其中一個。"""
        bits = self._read(Q.matrix(text))
        assert bits in self.TABLE_L.values(), \
            f"format {bits} 唔喺標準表入面 → 位置一定錯"

    @pytest.mark.parametrize("text", ["A", "https://example.com"])
    def test_both_copies_identical(self, text):
        """兩份 format info 一定要一樣（唔一樣 = 一定有 bug）。"""
        mx = Q.matrix(text)
        n = len(mx)
        copy1 = ([(i, 8) for i in range(6)]
                 + [(7, 8), (8, 8), (8, 7)]
                 + [(8, 14 - i) for i in range(9, 15)])
        copy2 = ([(8, n - 1 - i) for i in range(8)]
                 + [(n - 15 + i, 8) for i in range(8, 15)])
        b1 = "".join("1" if mx[r][c] else "0" for r, c in copy1)[::-1]
        b2 = "".join("1" if mx[r][c] else "0" for r, c in copy2)[::-1]
        assert b1 == b2, f"兩份 format 唔一致:\n  1: {b1}\n  2: {b2}"

    def test_encodes_correct_level(self):
        """format 頭 2 bit 要係 L = 01。"""
        bits = self._read(Q.matrix("https://example.com", ec="L"))
        data = (int(bits, 2) >> 10) ^ 0b10101   # 還原 XOR mask
        assert data >> 3 == 0b01, f"EC level 應該 L(01)，實際 {data>>3:02b}"

    @pytest.mark.parametrize("ec", ["M", "Q", "H"])
    def test_unsupported_level_raises(self, ec):
        """
        ⚠️ 誠實：只實作咗 EC level L（容量最大，URL 用最啱）。
           其他 level 要明確報錯，唔可以靜靜當 L ——
           否則會產生「格式話 M 但資料用 L 嘅 EC」嘅壞 QR。
        """
        with pytest.raises(ValueError, match="只支援"):
            Q.matrix("https://example.com", ec=ec)


class TestMasking:
    def test_mask_is_actually_applied(self):
        """
        ⚠️ 實測踩過：_place_data 污染 reserved map → mask 完全冇應用。
           檢測方法：唔同 mask 應該產生唔同嘅矩陣。
        """
        n = 5
        m, r = Q._new_matrix(n)
        for i in range(n):
            for j in range(n):
                m[i][j] = 1
        outs = set()
        for mid in range(8):
            out = Q._apply_mask(m, r, mid)
            outs.add(tuple(tuple(row) for row in out))
        assert len(outs) == 8, "8 個 mask 應該產生 8 個唔同結果"

    def test_function_patterns_not_masked(self):
        """finder / timing 一定唔可以被 mask 改到。"""
        n = 21
        m, r = Q._new_matrix(n)
        Q._place_finder(m, r, 0, 0)
        before = [row[:] for row in m]
        out = Q._apply_mask(m, r, 1)
        for i in range(7):
            for j in range(7):
                assert out[i][j] == before[i][j], "finder 被 mask 改咗"


class TestOutput:
    def test_svg(self):
        svg = Q.svg("https://example.com")
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "rect" in svg
        assert len(svg) > 500

    def test_svg_empty_for_too_long(self):
        assert Q.svg("x" * 5000) == ""

    def test_text_output(self):
        t = Q.text_qr("https://example.com")
        assert "██" in t
        assert len(t.split("\n")) > 20

    def test_text_too_long(self):
        assert "裝唔落" in Q.text_qr("x" * 5000)
