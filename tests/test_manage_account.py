"""
帳號管理工具測試
==================
⚠️ 用戶情況：「我登入唔返 icychan51@gmail.com，可能係個密碼問題啦，
   你可以幫我重設下，即係冇咗呢個紀錄、注銷咗佢，咁重新註冊一個。」

⚠️⚠️ 但呢個測試守住一件**好重要**嘅事：
   個帳號**冇密碼**（唔係密碼錯）→ 設密碼就得，**唔使刪**。
   而佢有 3 個旅程，其中一個有**其他成員**（朋友嘅資料）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

TOOL = ROOT / "server" / "tools" / "manage_account.py"


def code_only(path: Path) -> str:
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"\"])\s*#.*$', '', line)
        if s.strip().startswith("#"):
            continue
        out.append(s)
    return "\n".join(out)


def func_body(src: str, name: str) -> str:
    """
    攞某個函數嘅**完整** body。

    ⚠️⚠️ 唔可以用固定字數（`src[i:i+4000]`）——
       我加咗一大段解釋 FK CASCADE 嘅註解之後，
       個函數長過 4000 字 → 尾段嘅檢查全部假失敗。
    """
    i = src.index(f"def {name}(")
    j = src.find("\ndef ", i + 10)
    return src[i:j if j > 0 else len(src)]


@pytest.fixture(scope="module")
def src():
    return code_only(TOOL)


class TestToolExists:
    def test_tool_present(self):
        assert TOOL.exists(), "冇帳號管理工具"

    def test_has_all_modes(self, src):
        for mode in ("--show", "--set-password", "--clear-password", "--delete"):
            assert mode in src, f"工具冇「{mode}」"


class TestSafetyFirst:
    """
    ⚠️⚠️ 最重要嘅一組：**刪之前一定要睇清楚**。

       「Before any delete, verify that the resolved absolute target
        is the intended one」—— 同樣道理適用於 DB row。
    """

    def test_show_lists_owned_data(self, src):
        """⚠️ 一定要數得出「刪咗會冇咩」。"""
        i = src.index("def owned_data(")
        blk = func_body(src, "owned_data")
        for k in ("trips", "items", "stops", "members", "expenses", "shopping"):
            assert f'"{k}"' in blk, f"owned_data 冇數「{k}」"

    def test_delete_requires_typed_confirmation(self, src):
        """
        ⚠️⚠️ 唔可以「撳一下就刪」——
           要**打返個 email** 先算確認。
        """
        blk = func_body(src, "cmd_delete")
        assert "input(" in blk, "刪除冇要人確認"
        assert "DELETE {email}" in blk or "DELETE " in blk, \
            "確認唔夠明確（要打返個 email）"
        assert "取消" in blk, "冇取消路徑"

    def test_delete_warns_about_other_members(self, src):
        """
        ⚠️⚠️ 如果有**其他成員**，刪咗會影響朋友嘅資料 ——
           一定要喺確認之前警告。
        """
        blk = func_body(src, "cmd_delete")
        assert "朋友都會受影響" in blk or "成員" in blk, \
            "冇警告「有其他成員」"

    def test_delete_suggests_alternative(self, src):
        """
        ⚠️ 多數情況唔使刪 —— 要主動建議 `--set-password`。
        """
        blk = func_body(src, "cmd_delete")
        assert "--set-password" in blk, \
            "刪除之前應該建議「其實可以只設密碼」"

    def test_show_detects_no_password(self, src):
        """
        ⚠️⚠️ 核心診斷：個帳號**冇密碼**唔等於「密碼錯」。
           要明確講出嚟 + 畀正確做法。
        """
        blk = func_body(src, "cmd_show")
        assert "冇密碼" in blk, "冇偵測「從未設密碼」"
        assert "--set-password" in blk, "冇教點做"


class TestDeleteOrder:
    """
    ⚠️⚠️ 刪除次序好重要：先**子表**（items/expenses/members），
       最後先 trips 同 users。次序錯會被 FK 擋住。
    """

    def test_children_before_parents(self, src):
        """
        ⚠️ 只檢查 `plan = [...]` 嗰個清單 ——
           唔可以喺成個 function 度 index()，
           因為確認訊息入面都有 `t['members']` 呢啲字 →
           會攞到錯嘅位置（我第一版就係咁假失敗）。
        """
        i = src.index("def cmd_delete(")
        j = src.index("plan = [", i)
        k = src.index("]", j)
        plan = src[j:k]
        order = [
            plan.index('"votes"'), plan.index('"shopping_items"'),
            plan.index('"expenses"'), plan.index('"items"'),
            plan.index('"trip_stops"'), plan.index('"members"'),
            plan.index('"sessions"'),
        ]
        assert order == sorted(order), "⚠️ 刪除次序錯（子表要喺父表之前）"
        # users 最後
        blk = func_body(src, "cmd_delete")
        assert blk.index("DELETE FROM users") > blk.index("plan = ["), \
            "users 一定要最後刪"

    def test_deletes_orphan_trips(self, src):
        """⚠️ 刪完用戶之後唔可以留低「冇人嘅旅程」。"""
        blk = func_body(src, "cmd_delete")
        # ⚠️ 容許換行／空白 —— 唔可以寫死一行
        norm = " ".join(blk.split())
        assert "NOT IN (SELECT DISTINCT trip_id FROM members)" in norm, \
            "冇清走孤兒旅程"

    def test_uses_correct_column_names(self, src):
        """
        ⚠️ 我第一版寫錯欄位名（`a` / `b`）→ sqlite3.OperationalError。
           真正嘅 schema 係：
             friends(user_id, friend_id)
             friend_requests(from_id, to_id)
        """
        assert "user_id=? OR friend_id=?" in src, "friends 欄位名唔啱"
        assert "from_id=? OR to_id=?" in src, "friend_requests 欄位名唔啱"
        assert "WHERE a=?" not in src, "仲有錯嘅欄位名「a」"
        assert "WHERE b=?" not in src, "仲有錯嘅欄位名「b」"

    def test_bindings_match_placeholders(self, src):
        """⚠️ `?` 嘅數量一定要等於傳入嘅參數數量。"""
        assert "sql.count" in src, "冇動態計 `?` 數量"


class TestSetPassword:
    def test_clears_old_sessions(self, src):
        """
        ⚠️⚠️ 改密碼一定要清走舊 session ——
           如果帳號被盜用，舊 token 應該即刻失效。
        """
        blk = func_body(src, "cmd_set_password")
        assert "DELETE FROM sessions" in blk, \
            "⚠️ 改密碼冇清舊 session（被盜用都唔會斷）"

    def test_enforces_min_length(self, src):
        blk = func_body(src, "cmd_set_password")
        assert "len(pw) < 6" in blk, "冇檢查密碼長度"

    def test_uses_same_hasher(self, src):
        """⚠️ 一定要用 app 自己嘅 `_hash_password`（唔可以自己寫）。"""
        blk = func_body(src, "cmd_set_password")
        assert "_hash_password" in blk, "冇用 app 嘅雜湊函式"


class TestNoHardcodedPassword:
    """⚠️ 工具唔可以有硬編碼密碼／後門。"""

    def test_no_hardcoded_secret(self, src):
        for bad in ("password123", "admin123", "123456"):
            assert bad not in src, f"⚠️ 有硬編碼密碼「{bad}」"


class TestCascadeTraps:
    """
    ⚠️⚠️⚠️ 呢個 class 守住三個**實際發生過**嘅資料損失。

       我刪 `icychan51@gmail.com` 嗰陣，第一次同第二次都**刪走咗
       朋友旅程嘅資料**。三個唔同嘅 FK CASCADE 各自咬咗一啖：

         ① `trips.owner_id`          → 成個旅程冇咗
         ② `items.created_by`        → 朋友旅程入面嘅景點冇咗
         ③ （`expenses` / `shopping_items` 用 SET NULL，冇事）
    """

    def test_transfers_trip_ownership(self, src):
        """① 轉移 `trips.owner_id`（唔轉移就會 cascade 刪走朋友嘅旅程）。"""
        blk = func_body(src, "cmd_delete")
        assert "UPDATE trips SET owner_id=?" in blk, \
            "⚠️ 冇轉移旅程擁有權 → 朋友嘅旅程會被 cascade 刪走"
        assert "UPDATE members SET role='owner'" in blk, \
            "轉移 owner_id 之後要順便改 members.role"

    def test_transfers_item_author(self, src):
        """② 轉移 `items.created_by`（唔轉移就會 cascade 刪走朋友旅程嘅景點）。"""
        blk = func_body(src, "cmd_delete")
        assert "UPDATE items SET created_by=?" in blk, \
            "⚠️ 冇轉移景點作者 → 朋友旅程嘅景點會被 cascade 刪走"

    def test_keeps_content_of_surviving_trips(self, src):
        """
        ⚠️⚠️ 保住嘅旅程，內容**一個都唔可以刪**。

           我第二版仍然刪咗（`trip_id IN (我參與嘅旅程)`）——
           朋友會見到一個**空旅程**。
        """
        blk = func_body(src, "cmd_delete")
        assert "keep" in blk, "冇記錄「保住嘅旅程」"
        assert "NOT IN" in blk, \
            "⚠️ 刪除範圍冇扣起保住嘅旅程 → 朋友旅程會變空"

    def test_detects_cascade_risk_in_schema(self):
        """
        ⚠️⚠️ Schema 層面：`items.created_by` 用 CASCADE 而
           `expenses` / `shopping_items` 用 SET NULL —— **唔一致**。

           呢個測試**唔會**令你改 schema（要重建表），
           但會記住呢個唔一致，免得將來有人以為三個都一樣。
        """
        db_src = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        # items.created_by → CASCADE（⚠️ 高風險）
        i = db_src.index("CREATE TABLE IF NOT EXISTS items")
        # ⚠️ 呢度係攞 **db.py** 嘅片段（唔係工具）——
        #    唔可以用 func_body（嗰個係攞 tool 嘅 function）
        items_blk = db_src[i:i + 1400]
        assert "created_by" in items_blk
        import re as _re2
        items_cascade = bool(_re2.search(
            r"created_by\s+TEXT\s+NOT NULL\s+REFERENCES\s+users\(id\)\s+ON DELETE CASCADE",
            items_blk))
        # expenses / shopping_items → SET NULL（安全）
        # ⚠️ 唔可以寫死空格 —— 實際碼對齊過（`created_by   TEXT`）
        import re as _re
        safe = len(_re.findall(
            r"created_by\s+TEXT\s+REFERENCES\s+users\(id\)\s+ON DELETE SET NULL",
            db_src))
        assert safe >= 2, f"expenses / shopping_items 應該用 SET NULL（搵到 {safe}）"
        # ⚠️ 記錄風險：如果將來改咗 items 做 SET NULL，呢個 assert 會提你更新
        assert items_cascade, (
            "⚠️ items.created_by 而家係 SET NULL 咗？"
            "咁就可以放寬工具嘅作者轉移邏輯（記得更新呢個測試）"
        )

    def test_warns_before_confirming(self, src):
        """⚠️ 確認**之前**就要講明邊啲轉移、邊啲一齊刪。"""
        blk = func_body(src, "cmd_delete")
        j = blk.index("input(")
        before = blk[:j]
        assert "轉移" in before, "確認之前冇講「會轉移」"
        assert "一齊刪" in before, "確認之前冇講「會一齊刪」"
