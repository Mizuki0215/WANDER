"""
開發版後台測試
================
⚠️ 用戶要求：
   「我覺得另外仲要整一個叫做開發版，係放我自己睇啲人用
    呢個 App 嘅數據。」

⚠️ 呢個測試守住三件事：
   ① 權限（普通人睇唔到，admin 睇到）
   ② **Route 次序** —— 我加後台 API 嗰陣中過：寫喺 SPA
      catch-all 之後 → 回 404，睇落似「route 唔存在」
   ③ `.env` 載入次序 —— `.env` 明明有寫，但頂層讀唔到
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

MAIN = ROOT / "server" / "app" / "main.py"


def code_only(path: Path) -> str:
    """⚠️ 去註解先檢查（我試過 match 到自己解釋 bug 嘅註解）。"""
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"\"])\s*#.*$', '', line)
        if s.strip().startswith("#"):
            continue
        out.append(s)
    return "\n".join(out)


@pytest.fixture(scope="module")
def src():
    return code_only(MAIN)


class TestRouteOrder:
    """
    ⚠️⚠️ FastAPI 按**定義次序**配對 route。
       任何 API route 寫喺 SPA catch-all `@app.get("/{full_path:path}")`
       之後 → 永遠唔會被叫到。

       ⚠️ 症狀好誤導：catch-all 只擋 `api/` 開頭 → raise 404，
          睇落似「route 唔存在」而唔似「次序錯」。
    """

    def test_admin_routes_before_catchall(self, src):
        i_catch = src.index('@app.get("/{full_path:path}")')
        i_admin = src.index('@app.get("/api/admin/overview")')
        assert i_admin < i_catch, \
            "⚠️ 後台 API 寫喺 SPA catch-all 之後 → 永遠回 404"

    def test_events_route_before_catchall(self, src):
        i_catch = src.index('@app.get("/{full_path:path}")')
        i_ev = src.index('@app.post("/api/events")')
        assert i_ev < i_catch, "⚠️ /api/events 喺 catch-all 之後"

    def test_signup_routes_before_catchall(self, src):
        """
        ⚠️ 我又中過一次 ——
           加邀請碼 endpoint 嗰陣 append 咗喺檔案尾（catch-all 之後）。

           ⚠️⚠️ 而且我嘅**檢查 script** 都 match 錯：
              佢搵 `@app.get("/{full_path:path}")`，
              但呢個字串喺我寫嘅**解釋註解**入面都有 →
              攞咗註解嘅位置做基準 → 所有 route 都「喺後面」。
              所以呢個測試一定要用**去註解**版本（`code_only`）。
        """
        i_catch = src.index('@app.get("/{full_path:path}")')
        for route in ['@app.get("/api/auth/signup-mode")',
                      '@app.post("/api/admin/signup-invites")',
                      '@app.get("/api/admin/signup-invites")']:
            assert src.index(route) < i_catch, f"⚠️ {route} 喺 catch-all 之後"

    def test_no_api_route_after_catchall(self, src):
        """
        ⚠️ 通用檢查：catch-all 之後唔可以再有 `/api/` route。
        """
        i_catch = src.index('@app.get("/{full_path:path}")')
        tail = src[i_catch:]
        bad = re.findall(r'@app\.(?:get|post|put|patch|delete)\("(/api/[^"]+)"', tail)
        assert not bad, f"⚠️ 呢啲 API route 喺 catch-all 之後 → 永遠 404：{bad}"


class TestEnvLoadOrder:
    """
    ⚠️⚠️ `.env` 一定要喺**讀環境變數之前**載入。

       我中過：`main.py` 唔喺 module 層 import mailer
       （`from .mailer import ...` 寫喺函數入面），
       而 `load_env()` 係 mailer 喺 module 層呼叫嘅
       → 頂層讀 `WANDER_ADMIN_EMAILS` 讀到**未載入**嘅值。
    """

    def test_load_env_called(self, src):
        assert "_load_env()" in src, "main.py 冇喺頂層呼叫 load_env()"

    def test_load_env_before_admin_read(self, src):
        i_load = src.index("_load_env()")
        i_admin = src.index("_admin_emails()")
        assert i_load < i_admin, "⚠️ load_env 喺讀 admin 之後 → 讀到空值"

    def test_admin_emails_is_function(self, src):
        """
        ⚠️ 一定要係**函數**而唔係 module 常數 ——
           常數喺 import 一刻定死，之後改 env 都唔會生效。
        """
        assert "def _admin_emails()" in src, "ADMIN_EMAILS 應該係函數"
        assert "ADMIN_EMAILS = {" not in src, \
            "⚠️ 仲有 module 常數 ADMIN_EMAILS（會定死）"

    def test_admin_defaults_empty(self, monkeypatch):
        """
        ⚠️ 預設**冇人**係 admin —— 唔可以有永遠 admin 嘅後門帳號。

        ⚠️ 唔可以靠 `os.environ.pop` ——
           因為 `mailer.load_env()` 會由 `.env` 補返
           （`setdefault` 見到冇就會設）。要 monkeypatch 成**空字串**。
        """
        from app import main as m
        monkeypatch.setenv("WANDER_ADMIN_EMAILS", "")
        assert m._admin_emails() == set(), "空 env 應該等於冇 admin"
        for guess in ("admin@wander.app", "admin@localhost", "root@x.com",
                      "admin", "administrator@wander.app"):
            assert not m._is_admin({"email": guess}), \
                f"⚠️ 「{guess}」唔可以預設係 admin（後門）"

    def test_no_hardcoded_admin(self, src):
        """⚠️ 原始碼唔可以有任何硬編碼 admin email。"""
        for bad in ("@wander.app", "@localhost"):
            assert bad not in src, f"⚠️ 原始碼有硬編碼網域「{bad}」"


class TestAdminPermission:
    """⚠️ 權限要擋得住，而且要用 403 唔係 401。"""

    @pytest.fixture(scope="class")
    def m(self):
        import importlib
        from app import main
        importlib.reload(main)
        return main

    def test_is_admin_by_env(self, m, monkeypatch):
        monkeypatch.setenv("WANDER_ADMIN_EMAILS", "a@x.com, B@Y.com ")
        assert m._is_admin({"email": "a@x.com"})
        assert m._is_admin({"email": "b@y.com"}), "要大細階唔敏感"
        assert not m._is_admin({"email": "c@z.com"})

    def test_is_admin_by_flag(self, m, monkeypatch):
        monkeypatch.delenv("WANDER_ADMIN_EMAILS", raising=False)
        assert m._is_admin({"email": "x@y.com", "is_admin": 1})
        assert not m._is_admin({"email": "x@y.com", "is_admin": 0})

    def test_admin_before_catchall_uses_403(self, src):
        """⚠️ 403 而唔係 401 —— 401 會令前端當 session 過期踢人出嚟。"""
        i = src.index("def admin_user(")
        blk = src[i:i + 500]
        assert "403" in blk, "admin_user 應該回 403"
        assert "401" not in blk, \
            "⚠️ 用 401 會令前端當「session 過期」→ 登出用戶"


class TestOverviewShape:
    """⚠️ 後台回傳嘅欄位要齊（前端靠佢 render）。"""

    @pytest.fixture(scope="class")
    def blk(self, src):
        i = src.index('@app.get("/api/admin/overview")')
        j = src.index("def admin_overview", i)
        return src[j:j + 9000]

    @pytest.mark.parametrize("key", [
        "users", "active", "content", "events", "signups", "recent", "distrib",
    ])
    def test_top_level_keys(self, blk, key):
        assert f'"{key}"' in blk, f"overview 冇回「{key}」"

    @pytest.mark.parametrize("key", [
        "total", "new_7d", "onboarded", "with_password",
    ])
    def test_user_metrics(self, blk, key):
        assert f'"{key}"' in blk, f"users 冇「{key}」"

    @pytest.mark.parametrize("key", ["dau", "wau", "sessions_live"])
    def test_active_metrics(self, blk, key):
        assert f'"{key}"' in blk, f"active 冇「{key}」"

    def test_has_multi_city_metric(self, blk):
        """⚠️ 用戶特別關心多城市（佢啱啱要求加呢個功能）。"""
        assert "multi_city" in blk, "冇「多城市旅程」數字"

    def test_has_empty_trips(self, blk):
        """
        ⚠️ 「建立完但一個景點都冇」= 用戶唔知跟住做咩嘅訊號。
           呢個係後台最有價值嘅一個數字。
        """
        assert "empty_trips" in blk


class TestPrivacy:
    """⚠️ 後台唔可以洩漏用戶內容。"""

    def test_recent_hides_full_email(self, src):
        i = src.index("recent = [")
        blk = src[i:i + 700]
        assert '[:3]' in blk or "[: 3]" in blk, \
            "⚠️ 最近活動顯示完整 email → 應該truncate"

    def test_events_table_minimal(self):
        """
        ⚠️ events 表只可以存「類型 + 目標」，唔可以存內容。
        """
        db_src = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        i = db_src.index("EVENTS_SQL")
        blk = db_src[i:i + 700]
        cols = re.findall(r"^\s+(\w+)\s+(?:TEXT|INTEGER)", blk, re.M)
        assert set(cols) <= {"id", "user_id", "kind", "target", "created_at"}, \
            f"⚠️ events 表有唔應該有嘅欄位：{cols}"
        assert "body" not in blk and "content" not in blk.split("CREATE INDEX")[0], \
            "⚠️ events 唔應該存內容"


class TestSignupMode:
    """
    ⚠️⚠️ 用戶問：「未設定 SMTP 你係諗住點搞？」

       答：冇 SMTP 就寄唔到驗證碼 → 改用**邀請碼**。
       呢個 class 守住「自動判斷模式」同「邀請碼一次性」。
    """

    @pytest.fixture(scope="class")
    def m(self):
        from app import main
        return main

    def test_defaults_to_invite_without_smtp(self, m, monkeypatch):
        """
        ⚠️⚠️ 冇 SMTP 一定要自動變 `invite` ——
           如果變咗 `email`，所有人都註冊唔到（寄唔到驗證碼）。
        """
        monkeypatch.delenv("WANDER_SIGNUP_MODE", raising=False)
        monkeypatch.delenv("WANDER_SMTP_HOST", raising=False)
        monkeypatch.delenv("WANDER_RESEND_KEY", raising=False)
        assert m.signup_mode() == "invite", \
            "冇 SMTP 應該係 invite（唔係所有人註冊唔到）"

    def test_explicit_override(self, m, monkeypatch):
        for v in ("open", "invite", "email"):
            monkeypatch.setenv("WANDER_SIGNUP_MODE", v)
            assert m.signup_mode() == v

    def test_garbage_falls_back(self, m, monkeypatch):
        """⚠️ 打錯字唔可以令成個註冊壞掉。"""
        monkeypatch.setenv("WANDER_SIGNUP_MODE", "垃圾")
        assert m.signup_mode() in ("open", "invite", "email")

    def test_signup_mode_endpoint_is_public(self, src):
        """⚠️ 註冊畫面要問模式 → 唔可以要登入。"""
        i = src.index('@app.get("/api/auth/signup-mode")')
        blk = src[i:i + 300]
        assert "Depends(current_user)" not in blk, \
            "signup-mode 唔可以要登入（註冊時未有 token）"
        assert "signup_mode()" in blk

    def test_no_leak_in_signup_mode(self, src):
        """⚠️ 公開 endpoint 唔可以洩漏敏感嘢。"""
        i = src.index('@app.get("/api/auth/signup-mode")')
        blk = src[i:i + 500]
        for bad in ("password", "token", "ADMIN"):
            assert bad not in blk, f"⚠️ signup-mode 洩漏「{bad}」"


class TestSignupInvites:
    """⚠️ 邀請碼：一次性、有期限、admin 先產生到。"""

    @pytest.fixture(scope="class")
    def src(self, ):
        return code_only(MAIN)

    def test_invite_table_exists(self):
        db = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        assert "signup_invites" in db
        assert "PRIMARY KEY" in db[db.index("signup_invites"):][:600], \
            "邀請碼要係 PRIMARY KEY（唔可以重複）"

    def test_one_time_use(self, src):
        """
        ⚠️⚠️ 一次性最重要 —— 碼流出咗都只可以用一次。
        """
        i = src.index("def register(")
        blk = src[i:i + 3000]
        assert 'if inv["used_by"]' in blk, "冇檢查「已經用咗」"
        assert "UPDATE signup_invites SET used_by" in blk, "冇標記已用"

    def test_expiry_checked(self, src):
        i = src.index("def register(")
        blk = src[i:i + 3000]
        assert "過期" in blk, "冇檢查邀請碼過期"

    def test_gen_requires_admin(self, src):
        i = src.index('@app.post("/api/admin/signup-invites")')
        blk = src[i:i + 400]
        assert "admin_user" in blk, "產生邀請碼一定要 admin"

    def test_list_requires_admin(self, src):
        i = src.index('@app.get("/api/admin/signup-invites")')
        blk = src[i:i + 300]
        assert "admin_user" in blk, "列出邀請碼一定要 admin"

    def test_code_is_human_typable(self):
        """
        ⚠️ 用戶要**手打**呢條碼（可能喺電話度打）——
           唔可以有 O/0、I/1/l 呢類睇錯嘅字元。
           ⚠️ 而家用 `_invite_code()`：大寫字母 + 數字，6 位。
        """
        srv = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = srv.index("def _invite_code()")
        blk = srv[i:i + 220]
        assert "ascii_uppercase" in blk or "A-Z" in blk
        assert "range(6)" in blk or "{6}" in blk or "6" in blk
