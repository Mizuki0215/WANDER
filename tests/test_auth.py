"""
登入 / 註冊測試
================
⚠️ 用戶要求：
   「delete 驗證碼登入 function。要整兩版：
    一開始就係登入畫面，如果你冇帳號你就要註冊，
    有個 button 去互通。」

⚠️⚠️ 最重要嘅安全性質：**唔可以**「email 存在就當佢係本人」。
   否則任何人打你個 email 就搶到你個帳號。
   舊帳號（未設密碼）一定要**收得到驗證碼**先認領到。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))


def code_only(path: Path) -> str:
    """
    ⚠️⚠️ 去咗**註解**先做源碼檢查。

       呢個係我犯過幾次嘅錯：寫咗個測試檢查「唔可以出現 X」，
       但我自己喺 code 隔離寫咗個註解解釋「唔可以出現 X」
       → 測試 match 到自己嘅註解 → 誤報。

       所以所有源碼檢查都要經過呢個 function。
    """
    import re as _re
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        stripped = _re.sub(r'(?<![\'"\"])\s*#.*$', '', line)
        if stripped.strip().startswith("#"):
            continue
        out.append(stripped)
    return "\n".join(out)


class TestRegisterValidation:
    """⚠️ 註冊之前一定要驗證 —— 呢啲係最基本嘅防線。"""

    @pytest.fixture(scope="class")
    def reg(self):
        # 用 source 檢查（唔想喺測試度真開帳號）
        return code_only(ROOT / "server" / "app" / "main.py")

    def test_email_format_checked(self, reg):
        assert 'if "@" not in email or "." not in email.split("@")[-1]' in reg

    def test_password_min_length(self, reg):
        i = reg.index("def register(")
        blk = reg[i:i + 1500]
        assert "len(pw) < 6" in blk, "註冊冇檢查密碼長度"

    def test_password_max_length(self, reg):
        """
        ⚠️ 一定要有**上限** ——
           PBKDF2 係 CPU-bound，1MB 密碼可以打爆伺服器（DoS）。
        """
        i = reg.index("def register(")
        blk = reg[i:i + 1500]
        assert "len(pw) > 200" in blk, "冇密碼長度上限（DoS 風險）"

    def test_uses_hash(self, reg):
        i = reg.index("def register(")
        # ⚠️ 唔可以用固定字數 —— 加咗功能之後（例如邀請碼檢查）
        #    `_hash_password` 會被推到窗口之外 → 假失敗。
        #    用「到下一個頂層 def」做界線。
        j = reg.find("\n@app.", i + 10)
        blk = reg[i:j if j > 0 else i + 6000]
        assert "_hash_password(pw)" in blk, "註冊冇雜湊密碼"
        assert "password_hash" in blk


class TestClaimSecurity:
    """
    ⚠️⚠️ 呢個 class 係最重要嘅一組。
    """

    @pytest.fixture(scope="class")
    def src(self):
        return code_only(ROOT / "server" / "app" / "main.py")

    def test_claim_requires_code(self, src):
        """認領一定要驗證碼 —— 冇嘅話任何人都搶到帳號。"""
        i = src.index("def claim_account(")
        blk = src[i:i + 1200]
        assert "_consume_code" in blk, "認領冇檢查驗證碼！"
        # ⚠️ 唔可以「有 email 就當係本人」
        assert "password_hash" in blk, "認領冇檢查係唔係已經有密碼"

    def test_register_does_not_auto_claim(self, src):
        """
        ⚠️⚠️ 註冊 API **唔可以**幫一個已存在嘅 email 設密碼。

           否則：任何人打你個 email + 自己嘅密碼 → 就接管咗你個帳號。
        """
        i = src.index("def register(")
        blk = src[i:i + 1600]
        # 見到已存在就要 raise（唔可以繼續 UPDATE password_hash）
        assert "needs_claim" in blk, "register 冇分辨「舊帳號」同「已有密碼」"
        assert "password_hash = ?" not in blk, \
            "⚠️ register 竟然會改已存在帳號嘅密碼 —— 帳號可以被搶！"

    def test_code_verification_shared(self, src):
        """
        ⚠️ 驗證碼邏輯一定要**共用一個 helper** ——
           兩處各寫一份嘅話，將來一定會有一邊改漏
           （例如忘記加次數限制 → 可以暴力破解 6 位數字）。
        """
        assert src.count("def _consume_code(") == 1
        calls = len(re.findall(r"_consume_code\(", src))
        assert calls >= 2, f"_consume_code 只出現 {calls} 次（應該要共用）"

    def test_tries_limit(self, src):
        """⚠️ 冇次數限制 → 可以暴力破解 6 位數字。"""
        i = src.index("def _consume_code(")
        blk = src[i:i + 900]
        assert "tries" in blk and ">= 5" in blk, "驗證碼冇次數限制"

    def test_code_expiry(self, src):
        i = src.index("def _consume_code(")
        blk = src[i:i + 900]
        assert "expires_at" in blk, "驗證碼冇過期檢查"

    def test_constant_time_compare(self, src):
        """⚠️ 用 == 比較驗證碼會洩漏時間（timing attack）。"""
        i = src.index("def _consume_code(")
        blk = src[i:i + 900]
        assert "compare_digest" in blk, "驗證碼比較要用 compare_digest"


class TestLoginEndpoint:
    @pytest.fixture(scope="class")
    def src(self):
        return code_only(ROOT / "server" / "app" / "main.py")

    def test_no_email_enumeration(self, src):
        """
        ⚠️ 登入失敗唔可以講「冇呢個 email」——
           咁樣可以用嚟掃描邊啲 email 註冊過。
        """
        i = src.index("def password_login(")
        blk = src[i:i + 700]
        assert "Email 或密碼唔啱" in blk, "登入錯誤訊息可能洩漏 email 是否存在"
        assert "搵唔到" not in blk and "冇呢個" not in blk

    def test_uses_check_password(self, src):
        i = src.index("def password_login(")
        blk = src[i:i + 700]
        assert "_check_password" in blk

    def test_issues_session(self, src):
        i = src.index("def password_login(")
        blk = src[i:i + 700]
        assert "_issue_session" in blk


class TestIssueSessionShape:
    """
    ⚠️⚠️ 呢個測試捉到一個真 bug：
       `_issue_session` 冇回傳 `onboarded` →
       前端 `!user.onboarded` 係 true（undefined）→
       **每次登入都會出新手教學**。
    """

    @pytest.fixture(scope="class")
    def src(self):
        return code_only(ROOT / "server" / "app" / "main.py")

    def test_returns_onboarded(self, src):
        i = src.index("def _issue_session(")
        blk = src[i:i + 1400]
        assert '"onboarded"' in blk, "登入回應冇 onboarded → 每次登入都出教學"

    def test_returns_username(self, src):
        i = src.index("def _issue_session(")
        blk = src[i:i + 1400]
        assert '"username"' in blk

    def test_returns_has_password(self, src):
        i = src.index("def _issue_session(")
        blk = src[i:i + 1400]
        assert '"has_password"' in blk


class TestFrontendTwoPages:
    """⚠️ 用戶要求嘅「兩頁互通」。"""

    @pytest.fixture(scope="class")
    def login(self):
        import re as _re
        raw = (ROOT / "web" / "src" / "components" / "Login.jsx").read_text(
            encoding="utf-8")
        # JSX 註解
        return _re.sub(r"/\*[\s\S]*?\*/", "", _re.sub(r"^\s*//.*$", "", raw, flags=_re.M))

    def test_starts_on_login(self, login):
        assert "useState('login')" in login, "一開始唔係登入畫面"

    def test_has_two_pages(self, login):
        assert "'login' | 'register'" in login or "login | register" in login

    def test_switch_button(self, login):
        assert "switchTo" in login, "冇兩頁互通嘅掣"
        assert "page === 'login' ? 'register' : 'login'" in login

    def test_no_code_login_ui(self, login):
        """⚠️ 用戶明確要求刪走驗證碼登入。"""
        assert "驗證碼登入" not in login

    def test_keeps_code_for_claim(self, login):
        """但認領舊帳號仲要驗證碼（安全）。"""
        assert "claim" in login and "requestCode" in login

    def test_password_confirmation(self, login):
        """⚠️ 註冊要打兩次密碼 —— 防止打錯。"""
        assert "pw2" in login
        assert "兩次密碼唔一樣" in login


class TestApiCrossCheck:
    """⚠️ 新加嘅 api 方法一定要有定義（防白畫面）。"""

    @pytest.fixture(scope="class")
    def api(self):
        return (ROOT / "web" / "src" / "lib" / "api.js").read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", ["register", "claimAccount", "passwordLogin"])
    def test_defined(self, api, name):
        assert re.search(rf"^\s{{2}}{name}\s*:", api, re.M), \
            f"api.{name} 冇定義 → 會白畫面"

    def test_error_handles_object_detail(self, api):
        """
        ⚠️ FastAPI 嘅 detail 可以係物件（needs_claim）——
           直接 new Error(object) 會變 [object Object]。
        """
        assert "typeof d === 'object'" in api or "typeof d === \"object\"" in api
        assert "Object.assign(err, data)" in api
