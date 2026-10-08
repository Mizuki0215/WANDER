"""
密碼狀態（`has_password`）
===========================

⚠️⚠️ 用戶報：
   「因為我個帳號本身係 set 咗一個密碼嘅，所以呢你去改密碼嘅
    時候呢，例如去 setting，佢冇理由會同你講你仲未有密碼。
    我覺得呢個要改。」

⚠️ 根因：`/api/me` **根本冇回 `has_password`** ——
   前端 `user.has_password` 永遠 `undefined`（falsy）
   → Settings 永遠顯示「未設定」。

⚠️ 而且連帶兩個更嚴重嘅後果：
   ① 「現有密碼」個欄**唔會顯示** → 用戶填極都話「密碼唔啱」
   ② 個掣寫「設定密碼」而唔係「更改密碼」
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

WEB = ROOT / "web" / "src"


def code(path: Path) -> str:
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"`])//.*$', '', line)
        s = re.sub(r'/\*.*?\*/', '', s)
        if s.strip().startswith(('*', '/*')):
            continue
        out.append(s)
    return "\n".join(out)


class TestHasPasswordInApi:
    def test_me_returns_has_password(self):
        """
        ⚠️⚠️ 核心修法 —— `/api/me` 一定要回 `has_password`。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def me(")
        j = s.index("@app.", i + 10)
        blk = s[i:j]
        assert "has_password" in blk, \
            "⚠️⚠️ /api/me 冇回 has_password → Settings 永遠顯示「未設定」"

    def test_has_password_from_db_not_guessed(self):
        """⚠️ 一定要由 `password_hash` 計，唔可以寫死。"""
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def me(")
        blk = s[i:s.index("@app.", i + 10)]
        assert 'bool(user.get("password_hash"))' in blk, \
            "has_password 唔係由 password_hash 計"

    def test_uses_get_not_index(self):
        """
        ⚠️ 要用 `user.get()` 而唔係 `user["..."]` ——
           舊 session 嘅 user dict 可能係舊 schema（冇新欄）→ KeyError。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def me(")
        blk = s[i:s.index("@app.", i + 10)]
        assert 'user["password_hash"]' not in blk, \
            "用咗直接索引（舊 session 會 KeyError）"


class TestChangePasswordRequiresCurrent:
    def test_requires_current_when_has_password(self):
        """
        ⚠️ 有密碼就一定要提供現有密碼 ——
           唔係嘅話有人偷到你部手機就可以改密碼鎖你出嚟。
        """
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def set_password(")
        blk = s[i:i + 900]
        assert "has_pw and not _check_password" in blk, \
            "冇檢查現有密碼"
        assert "現有密碼唔啱" in blk, "冇明確錯誤訊息"

    def test_returns_has_password_true(self):
        s = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = s.index("def set_password(")
        blk = s[i:i + 900]
        assert '"has_password": True' in blk


class TestFrontendRefreshesUser:
    def test_settings_accepts_onrefresh(self):
        """⚠️ 改完密碼要 refresh `/api/me`（唔係嘅話 UI 唔跟）。"""
        s = code(WEB / "components" / "SettingsMore.jsx")
        assert "onRefresh" in s, "SettingsMore 冇 onRefresh"
        assert "onRefresh?.()" in s, "冇叫 onRefresh"

    def test_fallback_when_backend_disagrees(self):
        """
        ⚠️⚠️ Fallback：如果後端話「現有密碼唔啱」但前端以為冇密碼，
           即係 `has_password` 同後端唔一致 →
           強制 refresh 一次，個「現有密碼」欄就會出返。
           ⚠️ 唔係嘅話用戶會卡死（見到「未設定」但點改都話唔啱）。
        """
        s = code(WEB / "components" / "SettingsMore.jsx")
        i = s.index("async function savePassword")
        blk = s[i:i + 1200]
        assert "現有密碼" in blk, "冇處理「現有密碼唔啱」嘅 fallback"
        assert "onRefresh?.()" in blk, "fallback 冇 refresh"

    def test_prop_chained_from_app(self):
        """⚠️ onRefresh 要由 App 一路傳落去（App → Settings → SettingsMore）。"""
        app = code(WEB / "App.jsx")
        assert "const refreshMe" in app, "App 冇 refreshMe"
        assert "onRefresh={refreshMe}" in app, "App 冇傳 onRefresh"
        st = code(WEB / "components" / "Settings.jsx")
        assert "onRefresh" in st, "Settings 冇收／傳 onRefresh"

    def test_refresh_me_updates_user(self):
        """⚠️ refreshMe 一定要 setUser（唔係嘅話 UI 唔會變）。"""
        s = code(WEB / "App.jsx")
        i = s.index("const refreshMe")
        blk = s[i:i + 400]
        assert "setUser(" in blk, "refreshMe 冇 setUser"

    def test_ui_shows_correct_labels(self):
        """⚠️ 有密碼要寫「更改密碼」+ 顯示「現有密碼」欄。"""
        s = (WEB / "components" / "SettingsMore.jsx").read_text(encoding="utf-8")
        assert "更改密碼" in s, "冇「更改密碼」標籤"
        assert "現有密碼" in s, "冇「現有密碼」欄"
        assert "user?.has_password" in s, "冇用 has_password 做判斷"
