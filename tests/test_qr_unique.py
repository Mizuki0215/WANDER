"""
QR 唯一性 + 「唔可以加自己做朋友」測試
========================================
⚠️ 用戶問：
   「我要確定嘅就係係咪每一個 Account 都係有唔同嘅 QR code？
    即係佢哋唔同 Account 嘅 QR code 都係唔一樣。」

⚠️ 用戶要求：
   「如果當自己 scan 到自己嘅 QR code 嘅話，
    應該係知道係自己嚟嘅，咁你就要同佢講
    『唔可以加自己做朋友』。」
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))


def code_only(path: Path) -> str:
    """⚠️ 去註解先檢查（我試過 match 到自己解釋 bug 嘅註解）。"""
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"\"])\s*#.*$', '', line)
        if s.strip().startswith("#"):
            continue
        out.append(s)
    return "\n".join(out)


class TestQrUnique:
    """
    ⚠️ 用戶明確要求確認：「每一個 Account 都係有唔同嘅 QR code？」

    答案：**係** —— 因為 QR 內容係 `?add=<username>`，
          而 `username` 有 UNIQUE 約束。
    """

    @pytest.fixture(scope="class")
    def src(self):
        return code_only(ROOT / "server" / "app" / "main.py")

    def test_qr_encodes_username(self, src):
        i = src.index("def my_qr(")
        blk = src[i:i + 1400]
        assert '"/?add=' in blk or "/?add=" in blk, "QR 唔係用 ?add=<username>"
        assert "uname" in blk, "QR 冇用 username"

    def test_username_is_unique(self):
        """
        ⚠️⚠️ QR 唯一性**完全依賴** username 唯一性。如果 username
           冇 UNIQUE 約束，兩個 account 可以有同一個 QR。
        """
        schema = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        m = re.search(r"username\s+TEXT\s+UNIQUE", schema)
        assert m, "⚠️ username 冇 UNIQUE 約束 → 兩個 account 可以有同一個 QR！"

    def test_no_secrets_in_qr(self, src):
        """
        ⚠️ QR 會畀人掃／截圖／貼上網 —— 唔可以有敏感資料。
        """
        i = src.index("def my_qr(")
        blk = src[i:i + 1400]
        for bad in ("token", "password", "email="):
            assert bad not in blk.lower().replace("username", ""), \
                f"⚠️ QR URL 含「{bad}」—— 唔應該有敏感資料"

    def test_qr_requires_username(self, src):
        """⚠️ 未設 username 就唔應該出 QR（否則全部人都係 ?add=None）。"""
        i = src.index("def my_qr(")
        blk = src[i:i + 1400]
        assert "要先設定帳號名" in blk, "未設 username 都出 QR → 會撞"


class TestSelfAdd:
    """
    ⚠️ 用戶要求：掃到自己 → 「唔可以加自己做朋友」。

    呢個測試守住**四個入口**都要檢查。
    """

    @pytest.fixture(scope="class")
    def srv(self):
        return code_only(ROOT / "server" / "app" / "main.py")

    @pytest.fixture(scope="class")
    def selfcheck(self):
        p = ROOT / "web" / "src" / "lib" / "selfcheck.js"
        if not p.exists():
            pytest.skip("搵唔到 selfcheck.js")
        return p.read_text(encoding="utf-8")

    def test_backend_blocks_self(self, srv):
        """⚠️⚠️ 後端一定要擋 —— 前端檢查可以用 curl 繞過。"""
        i = srv.index("def send_friend_request")
        blk = srv[i:i + 2000]
        assert "唔可以加自己做朋友" in blk, "後端冇擋加自己！"

    def test_backend_message_matches_ui(self, srv, selfcheck):
        """⚠️ 前後端訊息要一致，否則用戶會見到兩種講法。"""
        assert "唔可以加自己做朋友" in selfcheck
        assert "唔可以加自己做朋友" in srv

    def test_shared_helper(self, selfcheck):
        """
        ⚠️⚠️ 一定要**共用一個函數** ——
           四個入口各寫一份嘅話，將來一定會有一邊改漏
           （例如支援大寫 email 之後有一邊忘記 toLowerCase）。
        """
        assert "export function isSelf" in selfcheck
        assert "SELF_MSG" in selfcheck

    @pytest.mark.parametrize("f,label", [
        ("components/MyQr.jsx", "① 設定頁掃人哋"),
        ("components/Friends.jsx", "② 朋友頁掃 QR"),
        # ⚠️ App.jsx 喺 src/ 根目錄，唔喺 components/
        ("App.jsx", "④ Deep link ?add="),
    ])
    def test_entry_points_check_self(self, f, label):
        src = (ROOT / "web" / "src" / f).read_text(encoding="utf-8")
        assert "isSelf(" in src, f"{label}：冇檢查係唔係自己"

    def test_friends_has_me_prop(self):
        """⚠️ Friends 要有 me 先判斷到自己 —— 之前漏咗。"""
        src = (ROOT / "web" / "src" / "components" / "Friends.jsx").read_text(
            encoding="utf-8")
        assert re.search(r"function Friends\(\{[^}]*\bme\b", src), \
            "Friends 冇 me prop → 判斷唔到自己"
        app = (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")
        assert "me={user}" in app, "App 冇傳 user 落 Friends"

    def test_check_before_action(self):
        """
        ⚠️⚠️ 檢查一定要喺「動作」（onFound / 複製）**之前** ——
           否則會照樣複製 @自己 然後叫你去加自己。
        """
        src = (ROOT / "web" / "src" / "components" / "MyQr.jsx").read_text(
            encoding="utf-8")
        blk = src[src.index("async function scan"):]
        i_self = blk.index("isSelf(")
        i_found = blk.index("onFound?.(")
        assert i_self < i_found, "自我檢查喺 onFound 之後 —— 太遲"

    def test_self_message_is_explicit(self, selfcheck):
        """⚠️ 用戶要嘅字眼就係「唔可以加自己做朋友」。"""
        assert "唔可以加自己做朋友" in selfcheck
