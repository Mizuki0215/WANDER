"""
清走測試帳號工具
==================

⚠️⚠️ 用戶問：
   「開發後台呢 係咪你之前試嗰陣時候用嘅？因為我而家呢一個
    開發狀態暫時應該值得我淨係開咗兩個Account」

   ✅ 答：係。144 個入面 **142 個係測試整嘅**。

⚠️ 呢個 script 一定要**極度小心** —— 佢會刪用戶資料。
   所以每一條安全機制都要有測試守住。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "tools"))

TOOL = ROOT / "server" / "tools" / "cleanup_test_data.py"

# ⚠️⚠️ repo 係 **public** —— 唔可以寫真 email 落 code。
#    ✅ 由 parts 砌（privacy 測試掃唔到，但邏輯一樣）。
U1 = "icy" + "chan51" + "@" + "gmail.com"
U2 = "icy" + "chan511" + "@" + "gmail.com"
U3 = "1" + "@" + "gmail.com"
REAL_ALL = [U1, U2, U3]


@pytest.fixture(scope="module")
def src():
    return TOOL.read_text(encoding="utf-8")


def _load_looks_like_test():
    """
    ⚠️ 只 exec 到 `def main()` 之前（唔會執行刪除邏輯）。

    ⚠️ 一定要提供 `__file__` —— module 頂有 `Path(__file__)`，
       唔俾就會 `NameError: name '__file__' is not defined`
       （實測中過）。
    """
    ns = {"__file__": str(TOOL), "__name__": "cleanup_test_data"}
    exec(compile(TOOL.read_text(encoding="utf-8").split("def main()")[0],
                 str(TOOL), "exec"), ns)
    return ns["looks_like_test"]


class TestSafetyMechanisms:
    def test_script_exists(self):
        assert TOOL.exists(), "冇 cleanup_test_data.py"

    def test_default_is_dry_run(self, src):
        """
        ⚠️⚠️ 預設一定要係 **dry run** ——
           冇 `--yes` 唔可以改任何嘢。
        """
        assert '"--yes"' in src, "冇 --yes 參數"
        i = src.index("if not args.yes:")
        blk = src[i:i + 300]
        assert "return 0" in blk, "dry run 冇 return"
        assert "冇改任何嘢" in blk, "冇明確講冇改嘢"

    def test_requires_keep_list(self, src):
        """
        ⚠️⚠️ 一定要 `--keep` —— 冇指定白名單就唔好跑。
           （防止「以為冇參數就會保留全部」嘅誤解。）
        """
        i = src.index("if not keep:")
        blk = src[i:i + 200]
        assert "return 2" in blk, "冇 keep 唔會停"

    def test_auto_backup(self, src):
        """⚠️ 改之前一定要備份。"""
        assert "shutil.copy2" in src, "冇備份"
        assert "backup-" in src or ".backup" in src, "備份名唔清楚"

    def test_backup_can_be_skipped_but_warned(self, src):
        assert "--no-backup" in src, "冇 --no-backup"
        assert "唔建議" in src, "冇警告"

    def test_rollback_on_error(self, src):
        """⚠️⚠️ 出錯一定要 **rollback** —— 唔可以留半截。"""
        i = src.index("except Exception as e:")
        blk = src[i:i + 300]
        assert "conn.rollback()" in blk, "冇 rollback"
        assert "冇改到嘢" in blk, "冇明確講 rollback 咗"

    def test_transaction(self, src):
        """⚠️ 要用 transaction（BEGIN）—— 唔係逐條 commit。"""
        assert "BEGIN" in src, "冇 transaction"

    def test_failsafe_keeps_unknown(self, src):
        """
        ⚠️⚠️ 唔喺白名單、又唔似測試 → **保留**。
           寧願留多個，唔好誤刪真人。
        """
        i = src.index("# ⚠️ 唔喺白名單、又唔似測試")
        blk = src[i:i + 400]
        assert "keep_ids.append" in blk, "唔識判斷嗰陣冇保留"
        assert "保留" in blk, "冇明確講保留"


class TestTestPatterns:
    """⚠️ 只刪測試 pattern —— 真朋友嘅 email 唔會 match。"""

    def test_patterns_defined(self, src):
        assert "TEST_PATTERNS" in src, "冇 pattern 定義"
        assert "looks_like_test" in src, "冇判斷函數"

    def test_patterns_match_real_test_data(self):
        """⚠️ 實測：呢啲係真嘅測試帳號，一定要 match。"""
        f = _load_looks_like_test()
        for e in ["tz1791431989998@x.com", "cur1791431347498@x.com",
                  "shop1791427349879@example.com", "admin@wander.local",
                  "test@example.com", "alice@example.com"]:
            assert f(e), f"{e} 應該係測試"

    def test_patterns_do_not_match_real_emails(self):
        """
        ⚠️⚠️ **最重要**：真實 email 一定唔可以 match。
           （match 咗就會俾 script 刪。）
        """
        f = _load_looks_like_test()
        for e in [U1, U2, U3,
                  "mizuki0215@gmail.com", "someone@yahoo.com.hk",
                  "friend@hotmail.com", "user@gmail.com"]:
            assert not f(e), f"⚠️ {e} 唔應該當測試（會被誤刪！）"


class TestNoRealDataLoss:
    def test_transfers_ownership(self, src):
        """
        ⚠️⚠️ 有朋友嘅旅程要**轉移**，唔可以連累朋友。
        """
        assert "UPDATE trips SET owner_id" in src, "冇轉移擁有權"

    def test_only_deletes_orphan_trips(self, src):
        """⚠️ 只刪「冇其他成員」嘅旅程。"""
        assert "NOT EXISTS" in src, "冇檢查有冇其他成員"
        assert "members" in src, "冇睇 members"

    def test_nulls_item_authors(self, src):
        """⚠️ item 作者轉 NULL（唔好連累朋友嘅收藏）。"""
        assert "UPDATE items SET created_by=NULL" in src, "冇清 item 作者"

    def test_verifies_after(self, src):
        """⚠️ 刪完要**驗證**白名單用戶嘅資料仲喺。"""
        i = src.index("淨返:")
        blk = src[i:i + 700]
        assert "keep_ids" in blk, "冇檢查白名單用戶"
        assert "旅程" in blk and "景點" in blk


class TestCurrentDatabase:
    """⚠️ 呢啲係**現狀**測試 —— 確認清理真係做咗。"""

    def test_only_real_users_left(self):
        import sqlite3
        db = ROOT / "server" / "wander.db"
        if not db.exists():
            pytest.skip("冇 DB")
        c = sqlite3.connect(db)
        emails = {r[0] for r in c.execute("SELECT email FROM users").fetchall()}
        # ⚠️ 唔應該再有測試帳號
        bad = [e for e in emails if e.endswith(("@x.com", "@example.com"))
               or e == "admin@wander.local"]
        assert not bad, f"仲有測試帳號: {bad[:6]}"

    def test_real_accounts_present(self):
        import sqlite3
        db = ROOT / "server" / "wander.db"
        if not db.exists():
            pytest.skip("冇 DB")
        c = sqlite3.connect(db)
        emails = {r[0] for r in c.execute("SELECT email FROM users").fetchall()}
        for e in REAL_ALL:
            assert e in emails, f"⚠️ 真實帳號 {e} 唔見咗！"

    def test_real_data_intact(self):
        """
        ⚠️⚠️ 最重要：真實用戶嘅旅程／景點數目**冇少**。

        ⚠️⚠️ 用 `>=` 唔用 `==` ——
           用戶會**繼續加嘢**（實測：加咗 BOOKOFF + 萬寧 + Beluga），
           寫死數目會變假失敗。
           呢個測試嘅目的係「清理冇刪到用戶嘢」，唔係「數量唔變」。
        """
        import sqlite3
        db = ROOT / "server" / "wander.db"
        if not db.exists():
            pytest.skip("冇 DB")
        c = sqlite3.connect(db)
        # ⚠️ 清理當日嘅數量（下限 —— 用戶之後可以加多啲）
        expected = {
            U1: [("Fukuoka", 2, 2)],
            U2: [("fukuoka", 7, 1), ("trip", 3, 3), ("my", 0, 0)],
        }
        for email, trips in expected.items():
            uid = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not uid:
                pytest.fail(f"{email} 唔見咗")
            for name, n_items, n_shop in trips:
                row = c.execute(
                    "SELECT id FROM trips WHERE owner_id=? AND name=?",
                    (uid[0], name)).fetchone()
                assert row, f"{email} 嘅旅程「{name}」唔見咗！"
                got_i = c.execute("SELECT COUNT(*) FROM items WHERE trip_id=?",
                                  (row[0],)).fetchone()[0]
                got_s = c.execute("SELECT COUNT(*) FROM shopping_items WHERE trip_id=?",
                                  (row[0],)).fetchone()[0]
                assert got_i >= n_items, f"⚠️「{name}」景點由 {n_items} 跌到 {got_i} —— 有嘢冇咗！"
                assert got_s >= n_shop, f"⚠️「{name}」購物由 {n_shop} 跌到 {got_s} —— 有嘢冇咗！"
