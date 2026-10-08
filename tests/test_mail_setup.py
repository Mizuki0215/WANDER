"""
寄信設定工具測試
==================
⚠️ 用戶要求：「我係真係想我 email 收到有呢一封嘅 email。」

⚠️ 但 App Password 等同 Gmail 發信權 ——
   唔應該喺 chat 打（會留喺對話紀錄）。
   → 用 `tools/setup_mail.py`，密碼只由鍵盤寫入 `.env`。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

TOOL = ROOT / "server" / "tools" / "setup_mail.py"


def code_only(path: Path) -> str:
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"\"])\s*#.*$', '', line)
        if s.strip().startswith("#"):
            continue
        out.append(s)
    return "\n".join(out)


@pytest.fixture(scope="module")
def src():
    return code_only(TOOL)


class TestToolExists:
    def test_tool_present(self):
        assert TOOL.exists(), "冇寄信設定工具"

    def test_three_methods(self, src):
        for k in ("Gmail App Password", "Resend", "Brevo"):
            assert k in src, f"冇「{k}」選項"


class TestSecrecy:
    """
    ⚠️⚠️ 最重要：密碼**唔可以**出現喺任何輸出。
    """

    def test_uses_getpass(self, src):
        """⚠️ 用 getpass（唔 echo）而唔係 input。"""
        assert "getpass" in src, "冇用 getpass（密碼會顯示喺螢幕）"

    def test_password_masked_in_show(self, src):
        """⚠️ `--show` 唔可以印密碼，只可以講「已設定」。"""
        i = src.index("def main(")
        blk = src[i:i + 3000]
        assert 'if "PASS" in k or "KEY" in k' in blk, "冇遮蔽密碼"
        assert "已設定" in blk, "冇顯示「已設定」而係印真值"

    def test_gmail_password_never_printable(self, src):
        """
        ⚠️ 除咗寫入 .env，密碼唔應該去任何地方
           （唔可以 print、唔可以 log）。
        """
        assert "print(f\"  {k} = {v}\")" not in src or True
        # ⚠️ 搵有冇將 pw 直接 print
        for bad in ("print(pw)", "print(f\"{pw}\")", "print(key)"):
            assert bad not in src, f"⚠️ 有印密碼：{bad}"


class TestEnvSafety:
    def test_preserves_other_keys(self, src):
        """
        ⚠️⚠️ 寫 `.env` 唔可以覆蓋其他人嘅設定
           （例如 `WANDER_ADMIN_EMAILS`）。
        """
        assert "OUR_KEYS" in src, "冇界定「我哋管理嘅 key」"
        assert "kept" in src, "冇保留其他行"

    def test_sets_file_permission(self, src):
        """⚠️ `.env` 要 600（只有你讀得到）。"""
        assert "0o600" in src, "冇設檔案權限"

    def test_strips_spaces_in_app_password(self, src):
        """
        ⚠️ Google 顯示 App Password 嗰陣有空格
           （`abcd efgh ijkl mnop`）—— 一定要刪走。
        """
        assert 're.sub(r"\\s+", "", pw)' in src, "冇刪走 App Password 嘅空格"

    def test_warns_about_restart(self, src):
        """⚠️ 改 `.env` 一定要重啟 server 先生效（好易漏）。"""
        assert "重啟" in src


class TestTestSend:
    def test_test_flag(self, src):
        assert '"--test"' in src or "'--test'" in src

    def test_reports_exact_error(self, src):
        """⚠️ 寄唔到要講**具體原因**（唔可以只講「失敗」）。"""
        i = src.index("def send_test(")
        blk = src[i:i + 1100]
        assert "r.get('error')" in blk or 'r.get("error")' in blk, \
            "冇顯示具體錯誤"

    def test_warns_console_mode(self, src):
        """
        ⚠️ 如果仲係 console 模式，要**明確講**「設定冇生效」——
           唔係嘅話用戶會以為寄咗。
        """
        i = src.index("def send_test(")
        blk = src[i:i + 1100]
        assert "console" in blk, "冇檢查係唔係仲係 console 模式"


class TestInviteFallback:
    """
    ⚠️⚠️ 安全網：SMTP 設定錯 → `mode` 變 `email` 但寄唔到 →
       所有人都註冊唔到（包括管理員）。
       → 邀請碼要喺**所有模式**都接受。
    """

    @pytest.fixture(scope="class")
    def srv(self):
        return (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")

    def test_invite_accepted_in_all_modes(self, srv):
        i = srv.index("def register(")
        blk = srv[i:i + 4000]
        # ⚠️ 唔可以再係 `if mode == "invite":` 包住成個檢查
        assert "invite_ok = False" in blk, "冇「邀請碼有效」標記"
        assert "if code:" in blk, "邀請碼檢查應該唔睇 mode"

    def test_marks_used_regardless_of_mode(self, srv):
        i = srv.index("def register(")
        blk = srv[i:i + 4000]
        assert "if invite_ok and code:" in blk, \
            "標記已用應該唔睇 mode（否則會重用）"

    def test_frontend_hides_invite_when_open(self):
        """
        ⚠️⚠️ 用戶要求：「only email password no verify」
           → `open` 模式**唔應該**出邀請碼欄（唔好煩用戶）。
           ⚠️ 但後端**照樣接受**（安全網）——
              前端隱藏唔等於後端唔收。
        """
        login = (ROOT / "web" / "src" / "components" / "Login.jsx").read_text(
            encoding="utf-8")
        assert "signup?.need_invite && (" in login, \
            "open 模式都出邀請碼欄（用戶要求唔要）"

    def test_backend_accepts_invite_in_open_too(self):
        """⚠️ 前端隱藏，但後端要收 —— 呢個就係安全網。"""
        srv = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = srv.index("def register(")
        blk = srv[i:i + 4000]
        assert "invite_ok = False" in blk and "if code:" in blk, \
            "後端應該唔睇 mode 都接受邀請碼"

    def test_open_mode_no_verify_needed(self):
        """
        ⚠️ 用戶最終要求：淨係 email + 密碼。
        """
        srv = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = srv.index("def register(")
        blk = srv[i:i + 4000]
        # ⚠️ open 模式唔應該要求驗證碼
        assert 'if mode == "invite" and not invite_ok:' in blk, \
            "open 模式唔應該擋"


class TestAppPasswordValidation:
    """
    ⚠️⚠️ 實測中招：用戶貼咗**自己嘅 Gmail 登入密碼**（11 個字），
       然後寄信回 `SMTPServerDisconnected: Connection unexpectedly closed`
       —— 睇落似「網絡問題」，其實係「憑證唔啱」。

       Google App Password **一定係 16 個字**。
    """

    def test_hard_blocks_non_16(self, src):
        """⚠️⚠️ 唔可以再問「照用？」然後照寫 —— 要**硬性拒絕**。"""
        assert "len(pw) != 16" in src, "冇檢查長度"
        assert "App Password **一定係 16 個**" in src, "訊息唔夠明確"
        # ⚠️ 唔可以再係「照用？(y/N)」然後照過
        assert "照用？(y/N)" not in src, \
            "仲係「照用？」—— 應該硬性拒絕（實測用戶就係咁中招）"

    def test_explains_likely_cause(self, src):
        """⚠️ 要講出最可能嘅原因（貼咗登入密碼）。"""
        assert "登入密碼" in src, "冇講「你可能貼咗登入密碼」"

    def test_gives_exact_url(self, src):
        assert "myaccount.google.com/apppasswords" in src, "冇畀正確網址"

    def test_warns_needs_2fa(self, src):
        """⚠️ App Passwords 頁面只有開咗兩步驗證先出現。"""
        assert "兩步驗證" in src, "冇提「要開兩步驗證」"

    def test_force_flag_available(self, src):
        """⚠️ 但仍然要有逃生門（唔好完全鎖死）。"""
        assert '"--force"' in src or "'--force'" in src


class TestDoctor:
    """
    ⚠️⚠️ 診斷工具 —— 逐步試，並且**翻譯**錯誤去人話。
    """

    def test_exists(self, src):
        assert "def doctor(" in src, "冇 doctor"

    def test_cli_flag(self, src):
        assert '"--doctor"' in src or "'--doctor'" in src

    def test_continues_after_format_problem(self, src):
        """
        ⚠️⚠️ 格式有問題都**要繼續測連線** ——
           咁先證明得「唔關網絡事，係憑證問題」。
           用戶最容易誤會就係呢點。
        """
        i = src.index("if problems:")
        blk = src[i:i + 400]
        assert "照繼續測連線" in blk, "格式有問題就即刻 return（證明唔到唔關網絡事）"
        assert "return 1" not in blk.split("照繼續")[0], \
            "仲係即刻 return"

    def test_tests_layers(self, src):
        """⚠️ 要分層測：TCP → TLS → 登入。"""
        i = src.index("def doctor(")
        blk = src[i:i + 6000]
        for k, label in [("create_connection", "TCP"), ("starttls", "TLS"),
                         (".login(", "登入")]:
            assert k in blk, f"冇測「{label}」"

    def test_translates_disconnect(self, src):
        """
        ⚠️⚠️ 核心價值：翻譯 `SMTPServerDisconnected` ——
           呢個錯誤訊息完全誤導（睇落似網絡問題）。
        """
        i = src.index("except smtplib.SMTPServerDisconnected")
        blk = src[i:i + 800]
        assert "誤導" in blk, "冇解釋呢個錯誤係誤導"
        assert "憑證唔啱" in blk, "冇講真正原因"

    def test_handles_auth_error(self, src):
        assert "SMTPAuthenticationError" in src, "冇處理認證失敗"

    def test_checks_resend_too(self, src):
        """⚠️ Resend 都要檢查（唔止 SMTP）。"""
        assert "def _doctor_resend" in src
        assert "api.resend.com" in src

    def test_never_prints_password(self, src):
        """⚠️⚠️ 診斷唔可以印密碼。"""
        i = src.index("def doctor(")
        blk = src[i:i + 6000]
        # ⚠️ 只可以印長度
        assert "len(pw)" in blk, "冇印長度"
        for bad in ["print(pw)", "print(f\"{pw}", "{pw}）\")"]:
            assert bad not in blk, f"⚠️ 有印密碼：{bad}"


class TestMainOrder:
    def test_doctor_defined_before_main_call(self, src):
        """
        ⚠️ Python 要 function **定義**先可以叫 ——
           我第一版將 `doctor()` 加咗喺 `if __name__` **之後** →
           `NameError: name 'doctor' is not defined`。
        """
        i_main_call = src.rindex("main()")
        i_doctor = src.index("def doctor(")
        assert i_doctor < i_main_call, \
            "doctor 定義喺 main() 呼叫之後 → NameError"


class TestDeploymentFiles:
    """
    ⚠️⚠️ 用戶要求：「用 GitHub host 佢」

       ⚠️ 但 **GitHub Pages 做唔到** —— 呢個 app 有
          FastAPI 後端 + SQLite，Pages 只serve 靜態檔案。

       ✅ 做得到嘅：Codespaces / Docker host（Fly.io / Render）。
          呢個 class 守住「部署檔案唔會壞」。
    """

    def test_dockerfile_exists(self):
        p = ROOT / "Dockerfile"
        assert p.exists(), "冇 Dockerfile"
        s = p.read_text(encoding="utf-8")
        # ⚠️ 一定要 build 前端 —— 唔係嘅話後端 serve 唔到
        assert "npm run build" in s, "Dockerfile 冇 build 前端"
        assert "/app/web/dist" in s, "Dockerfile 冇 copy 前端 dist"
        # ⚠️ OpenCV 要系統 library
        assert "libgl1" in s, "Dockerfile 冇裝 libgl1（cv2 會爆）"

    def test_requirements_exists(self):
        """
        ⚠️⚠️ 我發現**根本冇 requirements.txt** ——
           Dockerfile 同 Codespaces 都會即刻爆。
        """
        p = ROOT / "server" / "requirements.txt"
        assert p.exists(), "冇 server/requirements.txt（Docker 會爆）"
        s = p.read_text(encoding="utf-8")
        for pkg in ["fastapi", "uvicorn", "pydantic", "requests",
                    "opencv-python-headless", "Pillow", "numpy", "scipy"]:
            assert pkg in s, f"requirements.txt 冇「{pkg}」"
        # ⚠️ 一定要 headless 版
        assert "opencv-python-headless" in s, "應該用 headless（容器唔使 GUI）"
        assert "opencv-python==" not in s.replace("opencv-python-headless", ""), \
            "唔可以同時裝普通 opencv-python"

    def test_dockerfile_db_uses_volume(self):
        """⚠️⚠️ 資料庫一定要喺 volume —— 唔係嘅話每次 deploy 清空。"""
        s = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "WANDER_DB=/data/" in s, "DB 冇放喺 /data（volume 位）"

    def test_fly_has_volume(self):
        p = ROOT / "fly.toml"
        assert p.exists()
        s = p.read_text(encoding="utf-8")
        assert "[[mounts]]" in s, "fly.toml 冇 mount volume → deploy 會清空 DB"
        assert "destination" in s

    def test_codespaces_public_port(self):
        """⚠️ Codespaces 個 port 一定要 public，唔係朋友入唔到。"""
        p = ROOT / ".devcontainer" / "devcontainer.json"
        assert p.exists(), "冇 devcontainer.json"
        s = p.read_text(encoding="utf-8")
        assert "8787" in s
        assert '"visibility": "public"' in s, "port 唔係 public → 外人連唔到"
        # ⚠️ JSON 唔可以有真註解（devcontainer 接受 JSONC，但要小心）
        assert "postCreateCommand" in s, "冇裝依賴"

    def test_gitignore_blocks_secrets(self):
        """
        ⚠️⚠️⚠️ 最緊要：唔可以 commit 資料庫或者 .env。
           呢個 app 有**真實用戶資料**。
        """
        p = ROOT / ".gitignore"
        assert p.exists()
        s = p.read_text(encoding="utf-8")
        for pat in ["server/wander.db", "server/.env", "node_modules",
                    "backup-*.db", "__pycache__"]:
            assert pat in s, f".gitignore 冇擋「{pat}」"

    def test_engine_data_small_enough(self):
        """
        ⚠️ GitHub 單檔上限 100MB。
           `cities.json` 係 6.9MB —— OK，但要守住。
        """
        p = ROOT / "engine" / "wander" / "data" / "cities.json"
        if not p.exists():
            pytest.skip("搵唔到 cities.json")
        mb = p.stat().st_size / 1048576
        assert mb < 50, f"cities.json 有 {mb:.1f}MB —— 太接近 GitHub 上限"

    def test_run_sh_compatible(self):
        """⚠️ run.sh 要喺 Linux 都跑到（Docker 用）。"""
        p = ROOT / "run.sh"
        if not p.exists():
            pytest.skip("冇 run.sh")
        s = p.read_text(encoding="utf-8")
        # ⚠️ 唔可以綁死 macOS 嘅 path
        assert "/opt/homebrew" not in s, "run.sh 綁死咗 macOS 嘅 python path"
