"""
密碼雜湊測試
============
⚠️ 為咩要測試雜湊：
   密碼儲存寫錯係**災難級** bug，但正常使用完全唔會發現
   （登入照樣成功，只係你嘅密碼用 plain text 存咗）。
   所以一定要有測試確認：
     · 唔會存 plain text
     · 同一密碼兩次 hash 唔同（有 salt）
     · 驗證正確／錯誤密碼
     · 用 constant-time compare（防 timing attack）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app.main import _check_password, _hash_password  # noqa: E402


class TestHash:
    def test_not_plaintext(self):
        """⚠️ 最緊要：hash 一定唔可以包含原本密碼。"""
        h = _hash_password("mysecret123")
        assert "mysecret123" not in h

    def test_format(self):
        h = _hash_password("abc123")
        parts = h.split("$")
        assert len(parts) == 4
        assert parts[0] == "pbkdf2_sha256"
        assert int(parts[1]) >= 600_000, "迭代次數要夠（OWASP 建議 60 萬）"

    def test_salted(self):
        """⚠️ 同一個密碼兩次 hash 一定要唔同（唔同 salt）。"""
        a = _hash_password("samepassword")
        b = _hash_password("samepassword")
        assert a != b, "冇 salt —— 兩個用戶同密碼會有同一個 hash"

    def test_deterministic_with_same_salt(self):
        salt = b"0123456789abcdef"
        a = _hash_password("pw", salt)
        b = _hash_password("pw", salt)
        assert a == b


class TestCheck:
    def test_correct(self):
        assert _check_password("hello123", _hash_password("hello123")) is True

    def test_wrong(self):
        assert _check_password("wrong", _hash_password("hello123")) is False

    @pytest.mark.parametrize("stored", [None, "", "garbage", "md5$abc$def$ghi",
                                        "pbkdf2_sha256$notanumber$a$b"])
    def test_bad_stored_safe(self, stored):
        """⚠️ 壞資料唔可以拋錯（否則一個爛 record 就搞死登入）。"""
        assert _check_password("x", stored) is False

    def test_case_sensitive(self):
        assert _check_password("Hello", _hash_password("hello")) is False

    def test_unicode(self):
        h = _hash_password("密碼123🔑")
        assert _check_password("密碼123🔑", h) is True
        assert _check_password("密碼123", h) is False

    def test_empty(self):
        assert _check_password("", _hash_password("")) is True
        assert _check_password("x", _hash_password("")) is False
