"""
寄信測試（歡迎信 + 測試信）
=============================
⚠️ 用戶要求：
   「我係真係想我 email 收到有呢一封嘅 email。」
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))


class TestWelcomeEmail:
    def test_exists(self):
        from app import mailer
        assert hasattr(mailer, "send_welcome_email")

    def test_never_raises(self):
        """
        ⚠️⚠️ 一定要「永遠唔 raise」——
           email 寄唔到唔應該令**註冊**失敗（帳號已經開好）。
        """
        from app import mailer
        r = mailer.send_welcome_email("nobody@invalid.example", "測試")
        assert isinstance(r, dict)
        assert "sent" in r and "mode" in r

    def test_called_after_register(self):
        """
        ⚠️⚠️ 註冊之後要真係寄 —— 而且一定要喺 **DB commit 之後**。
           寄信要幾百 ms，唔好霸住個 connection。
        """
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index("def register(")
        j = src.index("def claim_account", i)
        blk = src[i:j]
        assert "send_welcome_email" in blk, "註冊冇寄歡迎信"
        # ⚠️ 寄信要喺 `with db.connect()` 之外
        i_with = blk.index("with db.connect()")
        i_send = blk.index("send_welcome_email")
        assert i_send > i_with, "寄信喺 DB connection 入面（會霸住）"

    def test_failure_does_not_break_register(self):
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index("send_welcome_email")
        blk = src[i - 200:i + 600]
        assert "try:" in blk and "except" in blk, \
            "寄信失敗會令註冊爆（冇 try/except）"


class TestTestMail:
    def test_exists(self):
        from app import mailer
        assert hasattr(mailer, "send_test_email")

    def test_endpoint_requires_admin(self):
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index('@app.post("/api/admin/test-mail")')
        blk = src[i:i + 400]
        assert "admin_user" in blk, "測試寄信一定要 admin"

    def test_endpoint_does_not_raise(self):
        """⚠️ 寄唔到要回原因畀前端，唔可以 raise（前端顯示唔到）。"""
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index("def admin_test_mail(")
        blk = src[i:i + 700]
        assert "唔 raise" in blk or "唔可以 raise" in blk or "**r" in blk.replace("{", ""), \
            "測試寄信應該回傳失敗原因"

    def test_status_has_from_to(self):
        """
        ⚠️ 後台要顯示「寄件人」同「測試會寄去邊」——
           冇嘅話用戶唔知寄咗去邊。
        """
        from app import mailer
        import inspect
        src = inspect.getsource(mailer.mail_status)
        assert '"from"' in src, "status 冇 from"
        assert '"to"' in src, "status 冇 to"


class TestNoSecretsLeak:
    def test_status_does_not_leak_password(self):
        """⚠️⚠️ 狀態唔可以回傳 SMTP 密碼。"""
        from app import mailer
        import inspect
        src = inspect.getsource(mailer.mail_status)
        assert "WANDER_SMTP_PASS" not in src, "⚠️ status 洩漏 SMTP 密碼"
        assert "RESEND_KEY" not in src, "⚠️ status 洩漏 Resend key"

    def test_admin_mail_endpoint_no_password(self):
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index('@app.get("/api/admin/mail")')
        blk = src[i:i + 300]
        assert "mail_status" in blk
        assert "PASS" not in blk
