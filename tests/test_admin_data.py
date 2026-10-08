"""
後台數據管理
==============
⚠️ 用戶要求：「同埋我想有個後台去管理數據喎，你幾時整呀？」

⚠️ 設計原則（每一條都係用血換返嚟）：
   ① **搜尋先** —— 144 個用戶唔可以一次過列出嚟
   ② ⚠️⚠️ **刪除要打名確認** —— 唔可以撳一下就近冇
      （今日已經試過兩次誤刪用戶資料）
   ③ ⚠️ **唔可以刪自己** —— 會將自己鎖出後台
   ④ 匯出**唔包** `password_hash`
   ⑤ route 一定要喺 SPA catch-all **之前**
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


@pytest.fixture(scope="module")
def srv():
    return (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")


def nocode(s: str) -> str:
    # ⚠️ 剝走**我嘅解釋**（註解 + prose），但**保留 SQL**。
    #
    # ⚠️⚠️ 為咩唔可以一刀切剝三引號字串：
    #    呢個 codebase 嘅 SQL **就係**寫喺三引號入面 ——
    #    剝咗嘅話連 UPDATE items SET created_by 都消失
    #    （實測：測試變咗假失敗）。
    #
    # ✅ 所以只剝：
    #    ① # 開頭嘅行
    #    ② 行尾 # 註解
    #    ③ 含 ⚠️ 嘅行（我用嚟寫解釋）
    out = []
    for line in s.split(chr(10)):
        t = line.strip()
        if t.startswith('#'):
            continue
        if '⚠️' in line:
            continue
        if '#' in line and '--' not in line:
            line = line.split('#')[0]
        out.append(line)
    return chr(10).join(out)

@pytest.fixture(scope="module")
def stripped(srv):
    return "\n".join(l for l in srv.split("\n")
                     if not l.strip().startswith("#"))


class TestAdminEndpoints:
    def test_users_endpoint(self, srv):
        assert '@app.get("/api/admin/users")' in srv

    def test_trips_endpoint(self, srv):
        assert '@app.get("/api/admin/trips")' in srv

    def test_export_endpoint(self, srv):
        assert '@app.get("/api/admin/export")' in srv

    def test_all_require_admin(self, srv):
        """⚠️⚠️ 每一個 admin endpoint 都一定要 `admin_user` 守。"""
        for ep in ["/api/admin/users", "/api/admin/trips",
                   "/api/admin/export", "/api/admin/active-users"]:
            i = srv.index(f'"{ep}"')
            # ⚠️ 搵到下一個 @app 為止
            j = srv.find("@app.", i)
            blk = srv[i:j if j > 0 else i + 1200]
            assert "admin_user" in blk, f"{ep} 冇 admin_user 守"

    def test_routes_before_spa_fallback(self, stripped):
        """⚠️⚠️ catch-all 一定要喺最後（呢個 bug 中過兩次）。"""
        i = stripped.index('@app.get("/{full_path:path}")')
        for ep in ["/api/admin/users", "/api/admin/trips", "/api/admin/export"]:
            assert stripped.index(f'"{ep}"') < i, f"{ep} 喺 catch-all 之後 → 404"


class TestDashboardOnly:
    """
    ⚠️⚠️ 用戶澄清：
       「我淨係想整嘅係有幾多數據？有啲咩用戶用緊咁樣我哋嘅 Dashboard。」

       → **唔需要**刪除功能。Admin 應該係**唯讀**。

    ⚠️ 為咩咁做係好嘅：
       · 少一個**誤刪**風險（今日試過兩次）
       · Dashboard 嘅職責係「睇」，唔係「改」
       · 真係要刪 → `server/tools/manage_account.py`
         （有完整擁有權轉移 + 要打 email 確認）
    """

    def test_no_delete_endpoints(self, srv):
        """⚠️ 刪除 endpoint 應該**完全冇咗**。"""
        assert "admin_delete_user" not in srv, "仲有 admin_delete_user"
        assert "admin_delete_trip" not in srv, "仲有 admin_delete_trip"

    def test_no_delete_api_methods(self):
        s = (WEB / "lib" / "api.js").read_text(encoding="utf-8")
        assert "adminDeleteUser" not in s, "api 仲有 adminDeleteUser"
        assert "adminDeleteTrip" not in s, "api 仲有 adminDeleteTrip"

    def test_frontend_no_delete_buttons(self):
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        assert "del.typed" not in s, "前端仲有刪除確認"
        assert "確定刪除" not in s, "前端仲有刪除掣"

    def test_has_active_users_endpoint(self, srv):
        """⚠️ 核心：要有「邊個用戶用緊」。"""
        assert '@app.get("/api/admin/active-users")' in srv

    def test_active_users_sorted_by_last_seen(self, srv):
        """
        ⚠️ 一定要按**最後活動**排序 ——
           唔係註冊時間（咁先睇到邊個真係用緊）。
        """
        i = srv.index("def admin_active_users(")
        blk = srv[i:i + 3000]
        assert "last_seen" in blk, "冇 last_seen"
        assert "ORDER BY last_seen DESC" in blk, "冇按最後活動排序"

    def test_counts_include_all_data_types(self, srv):
        """⚠️ 「有幾多數據」要包晒所有類型。"""
        i = srv.index("def admin_active_users(")
        blk = srv[i:i + 3000]
        for k in ["users", "trips", "stops", "items", "shopping",
                  "expenses", "friends", "events"]:
            assert f'"{k}"' in blk, f"統計冇「{k}」"

    def test_events_uses_created_at(self, srv):
        """
        ⚠️ `events` 表冇 `at` 欄 —— 係 `created_at`。
           （實測爆過 `no such column: at`）
        """
        i = srv.index("def admin_active_users(")
        blk = srv[i:i + 3000]
        assert "MAX(created_at)" in blk, "用錯欄位（events 冇 'at'）"
        assert "MAX(at)" not in blk, "仲用緊 'at'（會爆）"

    def test_dashboard_component(self):
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        assert "function Dashboard()" in s, "冇 Dashboard 元件"
        assert "<Dashboard />" in s, "Admin 冇用 Dashboard"

    def test_dashboard_is_first(self):
        """⚠️ Dashboard 要排最前（第一眼就見到）。"""
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        i_dash = s.index("<Dashboard />")
        i_other = s.index("<DataManager />")
        assert i_dash < i_other, "Dashboard 唔係排最前"

    def test_shows_relative_time(self):
        """⚠️ 「3 分鐘前」比 ISO 時間一眼睇得明。"""
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        assert "function ago(" in s, "冇相對時間"
        for k in ["分鐘前", "個鐘前", "日前"]:
            assert k in s, f"冇「{k}」"

    def test_color_by_recency(self):
        """⚠️ 用顏色分「幾近期用過」。"""
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        i = s.index("function Dashboard()")
        blk = s[i:i + 5000]
        assert "hrs < 1" in blk, "冇按時間分色"


class TestExportPrivacy:
    def test_export_excludes_password_hash(self, srv):
        """
        ⚠️⚠️ 匯出**唔可以**包含 `password_hash` ——
           就算係 admin 都唔應該見到。
        """
        i = srv.index("def admin_export(")
        j = srv.index("@app.", i + 10)
        blk = srv[i:j]
        # ⚠️ SELECT 清單入面唔可以有 password_hash
        for m in re.finditer(r"SELECT([^;]+?)FROM", blk, re.S):
            cols = m.group(1)
            assert "password_hash" not in cols, \
                "匯出咗 password_hash"
            assert "password" not in cols.lower(), \
                "匯出咗密碼欄位"

    def test_users_list_excludes_password_hash(self, srv):
        """⚠️ 用戶清單都唔可以 leakage。"""
        i = srv.index("def admin_users(")
        j = srv.index("@app.", i + 10)
        # ⚠️ 一定要去註解 —— 我嘅 docstring 解釋「唔好送出 password_hash」
        #    入面就有呢個字，唔去就會 match 到自己（第 N 次中）
        blk = nocode(srv[i:j])
        assert "password_hash" not in blk, "用戶清單 leakage password_hash"

    def test_export_has_multiple_targets(self, srv):
        i = srv.index("def admin_export(")
        blk = srv[i:i + 2000]
        for k in ["users", "trips", "items", "summary"]:
            assert f'"{k}"' in blk, f"匯出冇支援「{k}」"


class TestAdminFrontend:
    def test_data_manager_exists(self):
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        assert "function DataManager()" in s, "冇 DataManager"

    def test_data_manager_module_level(self):
        """⚠️ 喺 render 內定義 → 輸入框每打一個字就失焦。"""
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        i_fn = s.index("function DataManager()")
        i_main = s.index("export default function Admin(")
        assert i_fn != i_main
        # ⚠️ 唔可以喺 Admin 內部（縮排 2 格）
        assert not re.search(r"^  function DataManager\(", s, re.M), \
            "DataManager 喺 Admin 內部（會失焦）"

    def test_used_in_admin(self):
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        assert "<DataManager />" in s, "Admin 冇用 DataManager"

    def test_search_input(self):
        """⚠️ 144 個用戶唔可以一次過列 —— 一定要有搜尋。"""
        s = (WEB / "components" / "Admin.jsx").read_text(encoding="utf-8")
        i = s.index("function DataManager()")
        j = s.index("function Sec(", i)
        blk = s[i:j]
        assert "placeholder" in blk, "冇搜尋輸入"
        assert "搵 email" in blk or "搵旅程" in blk

    def test_api_methods(self):
        s = (WEB / "lib" / "api.js").read_text(encoding="utf-8")
        for m in ["adminUsers", "adminTrips", "adminExport", "adminActiveUsers"]:
            assert f"{m}:" in s, f"冇 api.{m}"


class TestAdminAccess:
    def test_admin_env_is_configurable(self):
        """⚠️ Admin 由 env 控制（唔可以 hardcode）。"""
        conf = (ROOT / "server" / ".env")
        if not conf.exists():
            pytest.skip("冇 .env")
        s = conf.read_text(encoding="utf-8")
        assert "WANDER_ADMIN_EMAILS" in s, "冇設 admin email"

    def test_no_hardcoded_admin_backdoor(self, srv):
        """
        ⚠️⚠️ 唔可以有 hardcode 嘅 admin 後門 ——
           一定要經 `WANDER_ADMIN_EMAILS` 或者 `users.is_admin`。
        """
        i = srv.index("def _admin_emails(")
        blk = srv[i:i + 800]
        assert "WANDER_ADMIN_EMAILS" in blk, "冇讀 env"
        # ⚠️ 唔可以有 hardcode 嘅 email
        assert "@gmail.com" not in blk, "hardcode 咗 email"
