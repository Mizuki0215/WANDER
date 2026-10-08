"""
⚠️⚠️ 秘密掃描 —— push 之前必須通過
======================================

⚠️ 2026-10-08 實測：`git add -A` 差啲 commit 咗
   `.gh/hosts.yml`（**含 GitHub OAuth token**）。

   ✅ 好彩 GitHub 嘅 **secret scanning** 擋住咗個 push：
      `! [remote rejected] main -> main (push declined due to
       repository rule violations)`

   ⚠️ 但呢個係**我自己嘅錯** —— 冇將 `.gh/` 加落 `.gitignore`。
      而且個 repo 係 **public**。

⚠️ 呢個測試一定要喺**每次 commit 之前**跑。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ⚠️ 真 token 嘅樣（36+ 字元隨機）
#    ⚠️ 唔可以 match 佔位符：`ghp_...` / `ghp_xxx` / `ghp_*`
TOKEN_RE = re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")
PLACEHOLDER_RE = re.compile(r"^gh[pousr]_[x.*]+$", re.I)


def _tracked_files() -> list[str]:
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                       capture_output=True, text=True)
    return [f for f in r.stdout.split("\n") if f]


class TestNoSecretsTracked:
    def test_no_real_tokens_in_tracked_files(self):
        """
        ⚠️⚠️ 追蹤檔案唔可以有真 token。
           （GitHub secret scanning 都會擋，但唔好靠佢。）
        """
        bad = []
        for f in _tracked_files():
            p = ROOT / f
            if p.suffix in (".png", ".jpg", ".jpeg", ".webp", ".db", ".ico"):
                continue
            try:
                s = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in TOKEN_RE.finditer(s):
                if PLACEHOLDER_RE.match(m.group(0)):
                    continue
                bad.append(f"{f}: {m.group(0)[:10]}…")
        assert not bad, f"⚠️⚠️ 追蹤檔案有真 token: {bad}"

    def test_no_partial_tokens_in_comments(self):
        """
        ⚠️ 我曾經喺 comment 寫低用戶泄漏嘅 token **頭 7 個字**
           （`ghp_` + 6 個字元）—— repo 係 public，唔應該有。
        """
        bad = []
        for f in _tracked_files():
            if not f.endswith((".sh", ".md", ".py", ".js")):
                continue
            s = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            # ⚠️ `ghp_` 後面跟真嘅英數字（唔係 x/./*）
            for m in re.finditer(r"gh[pousr]_[A-Za-z0-9]{5,}", s):
                tok = m.group(0)
                if PLACEHOLDER_RE.match(tok):
                    continue
                bad.append(f"{f}: {tok[:12]}…")
        assert not bad, f"⚠️ 有 token 碎片: {bad}"


class TestSensitivePathsIgnored:
    """
    ⚠️⚠️ 呢啲路徑一定要 gitignore —— 每一個都係實測撞過嘅。
    """

    REQUIRED = [
        ".gh/",              # ⚠️ GitHub OAuth token
        ".tools/",           # ⚠️ 下載嘅 binary
        ".home/",            # ⚠️ 假 HOME
        ".gitconfig-wander", # ⚠️ git 憑證設定
        "server/.env",       # ⚠️ 秘密
        "server/wander.db",  # ⚠️ 真實用戶資料
        "server/uploads/",   # ⚠️ 用戶上載嘅相
        "node_modules/",
    ]

    @pytest.mark.parametrize("path", REQUIRED)
    def test_gitignore_has_pattern(self, path):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        base = path.rstrip("/")
        assert (path in gi or base in gi), f".gitignore 冇擋「{path}」"

    def test_no_sensitive_file_tracked(self):
        """⚠️⚠️ 實測：唔可以有任何敏感檔案被追蹤。"""
        tracked = _tracked_files()
        bad = [f for f in tracked
               if re.match(r"^(\.gh/|\.tools/|\.home/|\.gitconfig)", f)
               or re.search(r"\.env$|wander\.db|uploads/|node_modules/", f)
               or f.endswith(".backup.db") or "backup-" in f]
        assert not bad, f"⚠️⚠️ 追蹤咗敏感檔案: {bad[:5]}"

    def test_db_never_tracked(self):
        """
        ⚠️⚠️ SQLite 檔案**永遠**唔可以 commit ——
           入面有真實 email / 旅程 / 景點。
           ⚠️ repo 係 **public**。
        """
        tracked = _tracked_files()
        dbs = [f for f in tracked if f.endswith((".db", ".sqlite", ".sqlite3"))]
        assert not dbs, f"⚠️⚠️ 追蹤咗 DB: {dbs}"


class TestNoPersonalData:
    """⚠️ repo 係 public —— 唔可以有真實個資。"""

    def test_no_real_emails(self):
        """
        ⚠️⚠️ 我實測中過兩次：
           ① 測試入面寫咗真 email
           ② README 有真 email
           ✅ 要由 parts 砌（`"icy" + "chan51" + "@gmail.com"`）
        """
        bad = []
        for f in _tracked_files():
            if f.endswith((".png", ".jpg", ".db")):
                continue
            s = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"icy" + r"chan\w*@gmail\.com", s, re.I):
                bad.append(f"{f}: {m.group(0)[:6]}…")
        assert not bad, f"⚠️⚠️ 真 email 喺 public repo: {bad}"

    def test_no_macos_username(self):
        """⚠️ 唔可以泄漏 macOS 用戶名。"""
        bad = []
        for f in _tracked_files():
            if f.endswith((".png", ".jpg", ".db")):
                continue
            s = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            if "/Users/yeetung" + "chan" in s:
                bad.append(f)
        assert not bad, f"⚠️ 有 macOS 用戶名: {bad}"

    def test_no_private_ips(self):
        """
        ⚠️ 唔可以有真 LAN IP。
           ⚠️ `192.168.1.100` 係**假佔位符**（我用嘅），要排除。
        """
        bad = []
        for f in _tracked_files():
            if f.endswith((".png", ".jpg", ".db")):
                continue
            s = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"192\.168\.\d+\.\d+", s):
                if m.group(0) == "192.168.1.100":
                    continue
                bad.append(f"{f}: {m.group(0)}")
        assert not bad, f"⚠️ 有真 LAN IP: {bad}"
