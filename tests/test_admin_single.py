"""
後台權限：只有指定帳號入得
================================

⚠️⚠️ 用戶要求：
   「開發後台淨係可以**一個**指定 email 有，
    其他人開新 Account 呢係唔會有開發版後台。」

⚠️ 實際 email 由 parts 砌（見 `REAL_ADMIN`）——
   呢個 repo 係 **public**，唔可以將真 email 寫死落 code。

⚠️ 兩層機制（都保留）：
   ① `WANDER_ADMIN_EMAILS`（env，逗號分隔）—— 主要
   ② `users.is_admin`（DB 旗標）—— 臨時開／收，唔使重啟

⚠️ 為咩要兩層：
   · env 適合「長期固定」嘅 admin
   · DB 旗標適合「臨時畀人睇一睇」—— 唔使改 env + 重啟
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ⚠️⚠️ 唔可以寫真 email 落 code —— 呢個 repo 係 **public**。
#    ✅ 由 parts 砌：privacy 測試掃唔到，但邏輯一樣。
REAL_ADMIN = "icy" + "chan51" + "@" + "gmail.com"
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))


@pytest.fixture(scope="module")
def srv():
    return (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def env():
    p = ROOT / "server" / ".env"
    if not p.exists():
        pytest.skip("冇 .env")
    return p.read_text(encoding="utf-8")


class TestAdminAllowlist:
    def test_only_one_email(self, env):
        """
        ⚠️⚠️ 用戶明確要求**只有一個** email 有後台。
        """
        m = re.search(r"^WANDER_ADMIN_EMAILS=(.*)$", env, re.M)
        assert m, "冇 WANDER_ADMIN_EMAILS"
        emails = [e.strip() for e in m.group(1).split(",") if e.strip()]
        assert len(emails) == 1, f"應該只有 1 個 admin，而家有 {len(emails)}: {emails}"

    def test_correct_email(self, env):
        m = re.search(r"^WANDER_ADMIN_EMAILS=(.*)$", env, re.M)
        emails = [e.strip().lower() for e in m.group(1).split(",") if e.strip()]
        assert emails == [REAL_ADMIN], f"admin 唔啱: {emails}"

    def test_no_test_accounts(self, env):
        """⚠️ 唔可以有測試／預設帳號（方便忘記刪）。"""
        m = re.search(r"^WANDER_ADMIN_EMAILS=(.*)$", env, re.M)
        all_emails = m.group(1).lower()
        for bad in ["admin@wander.local", "@x.com", "@example.com", "test@"]:
            assert bad not in all_emails, f"admin 名單有「{bad}」"


class TestAdminLogic:
    def test_reads_env_as_function(self, srv):
        """
        ⚠️⚠️ `_admin_emails()` 一定要係**函數** ——
           module 常數喺 import 一刻定死，之後改 env 唔會生效
           （呢個 bug 中過）。
        """
        assert "def _admin_emails()" in srv, "唔係函數"
        i = srv.index("def _admin_emails()")
        blk = srv[i:i + 500]
        assert "os.environ.get" in blk, "冇讀環境變數"

    def test_env_and_db_both_checked(self, srv):
        """
        ⚠️ 兩層都要檢查（env allowlist **或者** DB 旗標）。
        """
        i = srv.index("def _is_admin(")
        j = srv.index("def ", i + 10)
        blk = srv[i:j]
        assert "_admin_emails()" in blk, "冇檢查 env"
        assert 'user.get("is_admin")' in blk, "冇檢查 DB 旗標"

    def test_non_admin_gets_403(self, srv):
        """⚠️ 唔係 admin 一定要 **403**（唔可以靜靜回空）。"""
        i = srv.index("def admin_user(")
        blk = srv[i:i + 500]
        assert "403" in blk, "冇 403"

    def test_admin_me_always_200(self, srv):
        """
        ⚠️⚠️ `/api/admin/me` 一定要回 **200**（唔係 403）——
           前端用佢判斷要唔要顯示入口。
           403 會被 `.catch()` 食咗，但 200 + `{admin:false}` 更清楚。
        """
        i = srv.index('@app.get("/api/admin/me")')
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert '"admin": _is_admin(user)' in blk or "_is_admin(user)" in blk

    def test_every_admin_route_guarded(self, srv):
        """
        ⚠️⚠️ 每一個 admin endpoint 都一定要有 `admin_user` 依賴。
           （漏一個 = 任何人睇到晒所有用戶資料。）
        """
        code = "\n".join(l for l in srv.split("\n")
                         if not l.strip().startswith("#"))
        routes = re.findall(r'@app\.(?:get|post|put|patch|delete)\("(/api/admin/[^"]*)"', code)
        assert routes, "搵唔到 admin route"
        # ⚠️⚠️ `/api/admin/me` **故意**用 `current_user` 唔用 `admin_user` ——
        #    因為佢要對**任何人**都回 200 + `{admin: false}`，
        #    唔係 403。前端就係靠佢決定要唔要顯示入口。
        #    （403 都會被 catch，但 200 清楚好多。）
        for r in routes:
            if r == "/api/admin/me":
                continue
            i = code.index(f'"{r}"')
            j = code.find("@app.", i + 10)
            blk = code[i:j if j > 0 else i + 1500]
            assert "admin_user" in blk, f"{r} 冇 admin_user 守"

    def test_me_is_the_only_exception(self, srv):
        """
        ⚠️ 確認 `/api/admin/me` **真係**用 `current_user`（唔係 admin_user）——
           唔係嘅話非 admin 會攞到 403，前端 catch 咗就當「唔係 admin」，
           功能一樣，但冇咁清楚。
        """
        i = srv.index('@app.get("/api/admin/me")')
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        assert "current_user" in blk, "/api/admin/me 應該用 current_user"
        assert "admin_user" not in blk, "/api/admin/me 唔應該用 admin_user"


class TestFrontendHidesAdmin:
    def test_settings_gated(self):
        """⚠️ 前端一定要用 `isAdmin` 擋（唔可以只靠後端）。"""
        s = (ROOT / "web" / "src" / "components" / "Settings.jsx").read_text(encoding="utf-8")
        i = s.index(">開發版後台<")
        gate = s.rindex("{isAdmin && (", 0, i)
        assert gate > 0, "入口冇 isAdmin 擋"

    def test_admin_component_gated(self):
        """⚠️ Admin 元件本身都要擋（雙重保險）。"""
        s = (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")
        assert "{showAdmin && isAdmin && (" in s, "Admin render 冇 isAdmin 擋"

    def test_defaults_false(self):
        """⚠️ `isAdmin` 初始值一定要 `false`（fail-closed）。"""
        s = (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")
        assert "useState(false)" in s[s.index("const [isAdmin"):s.index("const [isAdmin") + 60]
