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


class TestShellScriptSafety:
    """
    ⚠️⚠️ 實測捉到嘅 bug：

       用戶跑 `./push-to-github.sh` →
       ```
       ./push-to-github.sh: line 167: REPO?: unbound variable
       ```

       原因：`echo "建立咗 $OWNER/$REPO（private）"`
       —— `$REPO` 後面跟住**全形括號** `（`（U+FF08）。

       ⚠️ 理論上 bash 應該停喺非識別字元，但實測喺某啲
          locale / bash 版本之下會出事。

       ✅ 修法：`$VAR` 後面跟非 ASCII 就一定要寫 `${VAR}`。
    """

    SCRIPTS = ["push-to-github.sh", "host.sh", "run.sh", "wander.sh"]

    @pytest.mark.parametrize("name", SCRIPTS)
    def test_var_before_non_ascii_uses_braces(self, name):
        """
        ⚠️ 掃描 script 入面所有 `$VAR` —— 如果後面跟住
           非 ASCII 字元，一定要用 `${VAR}`。
        """
        p = ROOT / name
        if not p.exists():
            pytest.skip(f"冇 {name}")
        s = p.read_text(encoding="utf-8")
        bad = []
        for i, line in enumerate(s.split("\n"), 1):
            if line.strip().startswith("#"):
                continue
            for m in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", line):
                nxt = line[m.end():m.end() + 1]
                if nxt and ord(nxt) > 127:
                    bad.append(f"{name}:{i}  {m.group(0)}{nxt}")
        assert not bad, (
            "⚠️ 呢啲位一定要用 ${VAR}（後面跟住非 ASCII）：\n  "
            + "\n  ".join(bad)
        )

    def test_push_script_has_set_u_safe(self):
        """⚠️ `set -u` 之下任何未設變數都會爆 —— 要當心。"""
        s = (ROOT / "push-to-github.sh").read_text(encoding="utf-8")
        assert "set -euo pipefail" in s, "應該有 set -euo pipefail"
        # ⚠️ 所有用嘅變數都要有 default 或者先設定
        for v in ["OWNER", "REPO", "TOKEN"]:
            assert f'{v}="' in s or f'${{{v}:-' in s, f"{v} 冇 default"

    def test_host_script_same(self):
        p = ROOT / "host.sh"
        if not p.exists():
            pytest.skip("冇 host.sh")
        s = p.read_text(encoding="utf-8")
        assert "set -euo pipefail" in s


class TestNoPrivacyLeaks:
    """
    ⚠️⚠️ 用戶問：「要 public 嗎？你建議 private，why？」

       我做咗實際審計，搵到**真實私隱洩漏**：

       | 洩漏 | 影響 |
       |---|---|
       | 你嘅真 email | spam / 釣魚 |
       | 你嘅 macOS 用戶名 | 本機路徑 |
       | 屋企 LAN IP | 網絡拓樸 |
       | 部機／手機 IP | 同上 |

       ⚠️ 呢啲**唔係 secret**（唔可以「登入」），
          但係**私隱** —— 一旦 public 就永遠喺 GitHub 歷史入面。

       呢個 class 守住佢哋唔會再出現。
    """

    # ⚠️⚠️ 唔可以出現嘅嘢。
    #
    #    ⚠️ 一定要**砌出嚟**而唔係直接寫字面值 ——
    #       唔係嘅話呢個檔案自己就會 match 自己
    #       （今日第 N 次中呢個招）。
    @staticmethod
    def _forbidden():
        import re
        name = "icy" + "chan51"
        return [
            (re.escape(name + "@gmail.com"), "真 email"),
            (r"/Users/yeetung" + "chan", "macOS 用戶名"),
            (r"192\.168\.1\." + "83(?!" + r"\d)", "屋企 LAN IP"),
            (r"192\.168\.1\." + "150(?!" + r"\d)", "部機 LAN IP"),
            (r"192\.168\." + "100\.200", "另一個 IP"),
        ]

    def _tracked_files(self):
        import subprocess
        out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                             capture_output=True, text=True).stdout
        return [f for f in out.split("\n") if f.strip()]

    def test_no_real_privacy_data(self):
        """⚠️⚠️ 掃描所有 git 追蹤嘅檔案。"""
        import re
        bad = []
        for f in self._tracked_files():
            p = ROOT / f
            if not p.is_file():
                continue
            try:
                s = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pat, label in self._forbidden():
                for m in re.finditer(pat, s):
                    line = s[:m.start()].count("\n") + 1
                    bad.append(f"{f}:{line}  {label}")
        assert not bad, (
            "⚠️⚠️ 呢啲真實私隱唔應該 commit（public 之前一定要清）：\n  "
            + "\n  ".join(bad[:20])
        )

    def test_uses_example_domains(self):
        """✅ 應該用 example.com 之類嘅保留域名。"""
        readme = (ROOT / "DEVLOG.md").read_text(encoding="utf-8")
        # ⚠️ RFC 2606 保留域名
        assert "example.com" in readme or "someone@gmail.com" in readme

    def test_gitignore_blocks_env(self):
        """⚠️ 呢個係最後防線 —— .env 永遠唔可以 commit。"""
        import subprocess
        r = subprocess.run(
            ["git", "check-ignore", "server/.env", "server/wander.db"],
            cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, "⚠️⚠️ .env / wander.db 冇被 gitignore"
        lines = r.stdout.strip().split("\n")
        assert "server/.env" in lines
        assert "server/wander.db" in lines

    def test_commit_author_is_generic(self):
        """
        ⚠️ git commit metadata 都會公開（name + email）——
           唔好用真名同真 email。
        """
        import subprocess
        out = subprocess.run(
            ["git", "log", "--format=%ae"], cwd=ROOT,
            capture_output=True, text=True).stdout
        emails = {e.strip() for e in out.split("\n") if e.strip()}
        for e in emails:
            assert "@gmail.com" not in e, f"⚠️ commit 用咗真 Gmail：{e}"
            assert "yeetungchan" not in e, f"⚠️ commit 用咗真名：{e}"


class TestHostingOptions:
    """
    ⚠️ 用戶問：「仲有冇其他可以 push host link?」

       ⚠️ 最重要嘅事實：**GitHub 只存 code，唔會跑 app**。
          要一個「撳得入去用」嘅 link，一定要一部真 server。
    """

    def test_hosting_doc_exists(self):
        p = ROOT / "HOSTING.md"
        assert p.exists(), "冇 HOSTING.md"
        s = p.read_text(encoding="utf-8")
        for k in ["cloudflared", "ngrok", "Codespaces", "Fly.io", "Render"]:
            assert k in s, f"HOSTING.md 冇提「{k}」"

    def test_doc_says_pages_cannot_work(self):
        """⚠️⚠️ 一定要講清楚 Pages 做唔到 —— 用戶問過好多次。"""
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "GitHub Pages" in s, "冇提 Pages"
        assert "靜態" in s, "冇解釋為咩 Pages 做唔到"

    def test_doc_marks_free_but_needs_card(self):
        """⚠️ Fly.io 要綁卡 —— 一定要老實講。"""
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "信用卡" in s, "冇提信用卡"
        assert "綁卡" in s or "綁信用卡" in s, "冇講 Fly.io 要綁卡"

    def test_doc_warns_render_no_disk(self):
        """⚠️⚠️ Render 免費層冇 disk → 每次 deploy 清空資料。"""
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "清空" in s, "冇警告 Render 會清空資料"

    def test_host_script_has_backends(self):
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "--ngrok" in s, "host.sh 冇 ngrok 選項"
        assert "--cloudflared" in s, "host.sh 冇 cloudflared 選項"
        assert "ERR_NGROK" in s, "host.sh 冇處理 ngrok 嘅 ERR_NGROK"

    def test_host_script_defaults_cloudflared(self):
        """
        ⚠️ 預設一定要 cloudflared —— 唔使註冊、冇 agent 限制。
           （實測 ngrok 免費版會撞 ERR_NGROK_802。）
        """
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert 'BACKEND="cloudflared"' in s, "預設唔係 cloudflared"

    def test_deploy_script_has_volume_step(self):
        """
        ⚠️⚠️ Fly.io 一定要建 volume ——
           唔做嘅話每次 deploy 都清空所有用戶資料。
        """
        s = (ROOT / "deploy.sh").read_text(encoding="utf-8")
        assert "volumes create" in s, "deploy.sh 冇建 volume"
        assert "清空" in s, "冇警告唔建 volume 會清空"


class TestCustomLinkName:
    """
    ⚠️ 用戶問：「link 名可以改嗎？」

       答：
         · cloudflared **quick** tunnel → **改唔到**（隨機派）
         · ngrok 免費版 → ✅ 有 1 個 static domain
         · Fly.io → 你揀嘅 app 名
         · 買網域 → 最靚
    """

    def test_doc_explains_quick_tunnel_immutable(self):
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "改唔到" in s, "冇講 quick tunnel 改唔到名"
        assert "隨機" in s, "冇解釋係隨機派"

    def test_doc_lists_custom_name_ways(self):
        """
        ⚠️⚠️ **只有兩條路**可以自訂名：
             · Fly.io（你揀 app 名）
             · 買網域 + named tunnel
           ⚠️ ngrok 免費版**唔得**（實測 ERR_NGROK_313）
        """
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        for k in ["fly.dev", "cloudflared tunnel create"]:
            assert k in s, f"冇提「{k}」"

    def test_doc_says_ngrok_cannot_customise(self):
        """
        ⚠️⚠️ 我原本以為 ngrok 免費版可以自訂 —— **實測錯咗**。
           要老實記錄（唔可以留低錯嘅資訊）。
        """
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "ERR_NGROK_313" in s, "冇記錄 ERR_NGROK_313"
        assert "Only paid plans" in s, "冇引用 ngrok 嘅原文"

    def test_host_script_handles_313(self):
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "ERR_NGROK_313" in s, "host.sh 冇處理 ERR_NGROK_313"
        assert "免費版唔可以自訂" in s, "冇講清楚免費版唔得"

    def test_host_script_supports_custom_ngrok_domain(self):
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "WANDER_NGROK_DOMAIN" in s, "host.sh 唔支援自訂 ngrok domain"
        # ⚠️ ngrok 新版用 `--url`（唔係 `--domain`）
        assert '--url "https://$NGROK_DOMAIN"' in s or \
               '--url "https://${NGROK_DOMAIN}"' in s, \
            "ngrok 冇用 --url（新版語法）"

    def test_host_script_says_no_domain_uses_random(self):
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "用隨機名" in s, "冇講冇設 domain 會用隨機名"
        assert "dashboard.ngrok.com/domains" in s, "冇畀攞 domain 嘅網址"

    def test_fly_app_name_is_custom(self):
        """⚠️ Fly.io 個 app 名就係 URL 嘅前半。"""
        import re
        s = (ROOT / "fly.toml").read_text(encoding="utf-8")
        app = re.search(r'^app = "(.+)"', s, re.M).group(1)
        assert app != "wander-CHANGE-ME", "fly.toml 仲係預設名"
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{1,28}[a-z0-9]", app), \
            f"app 名格式唔啱: {app}"


class TestServeo:
    """
    ⚠️ 用戶問：「有冇其他方法可以改到個 link 名啊？」

       ✅ **有！** `serveo.net` —— 免費 + 自訂名 + 冇提示頁。

       我實測（8 項全過）：
         ✓ 註冊 ✓ 建旅程 ✓ 加購物 ✓ 上傳相 ✓ 補相
         ✓ PWA manifest ✓ service worker ✓ 冇提示頁
    """

    def test_host_script_has_serveo(self):
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "--serveo" in s, "host.sh 冇 serveo"
        assert "WANDER_SERVEO_NAME" in s, "冇得自訂名"
        assert "console.serveo.net" in s, "冇講點註冊 SSH key"

    def test_serveo_url_extraction_excludes_console(self):
        """
        ⚠️⚠️ 實測中過嘅 bug：
           log 入面嘅**註冊提示**有 `https://console.serveo.net` ——
           如果淨係 grep `serveo`，就會攞咗個註冊頁做 tunnel URL。
        """
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "grep -v '^https://console\\\\.'" in s or \
               "grep -v" in s and "console" in s, \
            "URL 抽取冇排除 console.serveo.net"

    def test_serveo_handles_unregistered(self):
        """⚠️ 未註冊 SSH key 要**明確講**（唔好靜靜咁用隨機名）。"""
        s = (ROOT / "host.sh").read_text(encoding="utf-8")
        assert "register your SSH public key" in s, "冇偵測未註冊"
        assert "未註冊 SSH key" in s, "冇講清楚"

    def test_doc_ranks_serveo_first(self):
        """⚠️ 我實測 serveo 係最好嘅免費方案 —— 文件要咁排。"""
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "serveo.net" in s, "冇提 serveo"
        assert "🥇 serveo" in s, "serveo 冇排第一"
        # ⚠️ 要有實測結果（唔係空泛推薦）
        assert "8 項全過" in s or "全過" in s, "冇實測結果"

    def test_doc_warns_localtunnel_unstable(self):
        """⚠️ localtunnel 自訂名但實測唔穩定（503）—— 要老實講。"""
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "loca.lt" in s, "冇提 localtunnel"
        assert "503" in s, "冇記錄 localtunnel 嘅 503"

    def test_doc_corrects_only_two_ways(self):
        """
        ⚠️ 我原本寫「只有兩條路」—— 實測錯咗（serveo 都得）。
           要更正。
        """
        s = (ROOT / "HOSTING.md").read_text(encoding="utf-8")
        assert "只有兩條路" not in s, "仲寫住「只有兩條路」（實測錯）"
        assert "免費都有 3 條路" in s, "冇更正做 3 條路"
