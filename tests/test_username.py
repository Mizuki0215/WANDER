"""
@帳號名 + QR 加朋友測試
========================
⚠️ 為咩要嚴格驗證 username：
   佢係「俾人打嘅身份」。有同形字（l/1/I、O/0）就會有人冒充。
   只准 a-z 0-9 _ + 細階 → 冇大小寫混淆。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.main import (  # noqa: E402
    USERNAME_RE, USERNAME_RESERVED, _check_username, _norm_username,
)


class TestNormalize:
    @pytest.mark.parametrize("raw,want", [
        ("alice", "alice"), ("@alice", "alice"), ("＠alice", "alice"),
        ("  ALICE  ", "alice"), ("Alice_99", "alice_99"),
        ("@@alice", "alice"), ("", ""), (None, ""),
    ])
    def test_norm(self, raw, want):
        assert _norm_username(raw) == want


class TestValidate:
    # ⚠️ 用戶要求：一定要有「英文字母 + 數字」
    @pytest.mark.parametrize("u", [
        "alice99", "alice_2026", "a1b", "user_1", "a_1",
        "abcdefghijklmnopqrs1",       # 20 字（上限）
    ])
    def test_valid(self, u):
        assert _check_username(u) == u

    @pytest.mark.parametrize("u", ["alice", "bob", "alice_", "abcd"])
    def test_needs_digit(self, u):
        """⚠️ 純字母唔得 —— 用戶明確要求要有數字。"""
        with pytest.raises(HTTPException) as e:
            _check_username(u)
        assert e.value.status_code == 400
        assert "數字" in e.value.detail

    def test_needs_letter(self):
        """純數字唔得（而且 regex 已經擋咗，因為要字母開頭）。"""
        with pytest.raises(HTTPException):
            _check_username("123456")

    @pytest.mark.parametrize("u,want", [
        ("alice9", "alice9"), ("@ALICE9", "alice9"), ("Alice_99", "alice_99"),
    ])
    def test_normalizes_case(self, u, want):
        assert _check_username(u) == want

    @pytest.mark.parametrize("u", ["", None])
    def test_empty(self, u):
        """空字串 → 「請填帳號名」（唔係「太短」）。"""
        with pytest.raises(HTTPException) as e:
            _check_username(u)
        assert e.value.status_code == 400
        assert "請填" in e.value.detail

    @pytest.mark.parametrize("u", ["a", "ab"])
    def test_too_short(self, u):
        with pytest.raises(HTTPException) as e:
            _check_username(u)
        assert e.value.status_code == 400
        assert "3" in e.value.detail

    def test_too_long(self):
        with pytest.raises(HTTPException) as e:
            _check_username("a" * 21)
        assert e.value.status_code == 400
        assert "20" in e.value.detail

    @pytest.mark.parametrize("u", [
        "1alice9", "al ice9", "alice9!", "alice9@x", "alicé9",
        "_alice9", "alice-99", "alice.99", "中文名9",
    ])
    def test_invalid_chars(self, u):
        with pytest.raises(HTTPException) as e:
            _check_username(u)
        assert e.value.status_code == 400

    @pytest.mark.parametrize("u", sorted(USERNAME_RESERVED)[:8])
    def test_reserved_blocked(self, u):
        """⚠️ 保留字一定要擋 —— 否則可以冒充官方。"""
        with pytest.raises(HTTPException) as e:
            _check_username(u)
        assert e.value.status_code == 400
        assert "保留" in e.value.detail

    @pytest.mark.parametrize("u", [
        "admin1", "admin_2026", "admin99", "wander99", "support1",
        "official2", "root_1",
    ])
    def test_reserved_prefix_blocked(self, u):
        """
        ⚠️ 唔可以只擋完全相同 —— 「admin1」「admin_2026」呢類前綴冒充
           一樣會令人以為係官方。所以連前綴都要擋。

           ⚠️ 呢個檢查一定要排喺「要數字」**之前**，
              否則「admin」會先被「要數字」擋，訊息會誤導用戶。
        """
        with pytest.raises(HTTPException) as e:
            _check_username(u)
        assert "保留" in e.value.detail, f"{u} 應該報「保留字」，實際：{e.value.detail}"

    def test_reserved_error_priority(self):
        """「admin」（冇數字）應該報「保留字」而唔係「要數字」。"""
        with pytest.raises(HTTPException) as e:
            _check_username("admin")
        assert "保留" in e.value.detail, f"訊息誤導：{e.value.detail}"

    def test_regex_matches_validator(self):
        """regex 同 _check_username 嘅判斷要一致。"""
        for u in ("alice99", "a1b", "a" * 19 + "1"):
            assert USERNAME_RE.match(u), u
        for u in ("ab", "1ab", "a" * 21, "a b", "a-b"):
            assert not USERNAME_RE.match(u), u


class TestSecurity:
    """
    ⚠️ 呢幾個係「唔可以發生」嘅事。
    """

    def test_no_homoglyph_confusion(self):
        """大小寫要統一 —— 唔可以 Alice9 / alice9 / ALICE9 三個都註冊到。"""
        assert _check_username("Alice9") == _check_username("ALICE9") == "alice9"

    @pytest.mark.parametrize("u", ["admin", "wander", "support", "official", "root"])
    def test_cannot_impersonate(self, u):
        with pytest.raises(HTTPException):
            _check_username(u)

    def test_no_whitespace_tricks(self):
        """「ali ce9」唔可以變「alice9」。"""
        with pytest.raises(HTTPException):
            _check_username("ali ce9")
        # 但前後空白要 trim（用戶複製貼上會有）
        assert _check_username("  alice9  ") == "alice9"

    def test_at_prefix_stripped(self):
        """複製「@alice9」貼上要 work。"""
        assert _check_username("@alice9") == "alice9"
        assert _check_username("＠alice9") == "alice9"    # 全形 @


class TestQRDecode:
    """
    ⚠️ 呢個測試係為咗捉一個真 bug：
       `cv2.QRCodeDetector().detectAndDecode()` 回 **3 個值**，
       但 endpoint 寫 `found, _pts = ...` → ValueError → 500。

       我喺測試檔寫啱（`txt, _, _ = ...`），但 endpoint 寫錯。
       **所以「測試通過」唔等於「產品通過」—— 一定要真打 API。**
    """

    @staticmethod
    def _has_cv():
        try:
            import cv2  # noqa
            import numpy  # noqa
            return True
        except ImportError:
            return False

    def test_detectanddecode_returns_three_values(self):
        """⚠️ 記錄 OpenCV 嘅 API 形狀，防止再寫錯。"""
        if not self._has_cv():
            pytest.skip("冇 OpenCV")
        import cv2
        import numpy as np
        img = np.full((200, 200), 255, dtype=np.uint8)
        r = cv2.QRCodeDetector().detectAndDecode(img)
        assert isinstance(r, tuple), "應該回 tuple"
        assert len(r) == 3, f"應該回 3 個值（text, points, straight），實際 {len(r)}"

    def test_endpoint_uses_index_zero(self):
        """endpoint 一定要用 [0] 或者 3 個變數解包。"""
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        assert "detectAndDecode(img)[0]" in src or "detectAndDecode(img2)[0]" in src, \
            "endpoint 應該用 [0] 取文字"
        # 唔應該有「兩個變數」解包 detectAndDecode
        import re as _re
        for m in _re.finditer(r"^(\s*)([\w\s,]+)=\s*\w*\.?detectAndDecode\(([^)]*)\)\s*$",
                              src, _re.M):
            lhs = m.group(2).strip()
            n = len([x for x in lhs.split(",") if x.strip()])
            assert n != 2, f"兩個變數解包 detectAndDecode → ValueError: {m.group(0).strip()}"

    def test_every_function_scan(self):
        """全部 endpoint 都唔可以有 'too many values to unpack' 風險。"""
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        # 搵所有 detectAndDecode 用法，確認每個都係 [0] 或 3 變數
        import re as _re
        for m in _re.finditer(r"^.*detectAndDecode.*$", src, _re.M):
            line = m.group(0).strip()
            if line.startswith("#"):
                continue
            ok = ("[0]" in line or "detectAndDecodeMulti" in line
                  or _re.search(r"\w+,\s*\w+,\s*\w+\s*=", line))
            assert ok, f"呢行解包方式有風險: {line[:90]}"
