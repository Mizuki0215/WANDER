"""
GCP e2-micro 部署 script
==========================

⚠️⚠️ 用戶講得對：
   「問題你去旅行唔會開電腦」

   ⚠️ serveo / cloudflared 要你部電腦開住 ——
      但旅行 app 就係**旅行嗰陣用**，嗰時電腦喺屋企。
   → **要 cloud**。

⚠️ 為咩 GCP e2-micro：
   · 1 × e2-micro VM（**永久**免費，唔係 trial）
   · 1 GB RAM + 2 vCPU + **30 GB 持久磁碟**
   · 24/7、$0/月
   ⚠️ 對比 Fly.io（2024-10-07 取消免費，US$3.44/月）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "deploy-gcp.sh"


@pytest.fixture(scope="module")
def s():
    return SH.read_text(encoding="utf-8")


class TestExists:
    def test_script_exists(self):
        assert SH.exists(), "冇 deploy-gcp.sh"

    def test_is_executable(self):
        import os, stat
        m = os.stat(SH).st_mode
        assert m & stat.S_IXUSR, "冇執行權限"

    def test_syntax_ok(self):
        """⚠️ `bash -n` 檢查語法（唔會執行）。"""
        import subprocess
        r = subprocess.run(["bash", "-n", str(SH)], capture_output=True, text=True)
        assert r.returncode == 0, f"語法錯:\n{r.stderr}"


class TestFreeTierCompliance:
    """
    ⚠️⚠️ 一定要**完全符合** GCP Always Free 條件 ——
       唔係嘅話會靜靜收錢。
    """

    def test_machine_is_e2_micro(self, s):
        """⚠️⚠️ 只有 e2-micro 先係永久免費！"""
        assert "e2-micro" in s, "唔係 e2-micro → 會收錢"
        # ⚠️ 唔可以有其他 machine type 做預設
        m = re.search(r'MACHINE="\$\{WANDER_MACHINE:-([^}]+)\}"', s)
        assert m and m.group(1) == "e2-micro", f"預設 machine 唔啱: {m.group(1) if m else '?'}"

    def test_zone_is_free_zone(self, s):
        """
        ⚠️⚠️ e2-micro 只喺 **us-west1 / us-central1 / us-east1** 免費。
           （實測：其他 region 會收錢）
        """
        m = re.search(r'ZONE="\$\{WANDER_ZONE:-([^}]+)\}"', s)
        assert m, "冇 ZONE"
        zone = m.group(1)
        region = zone.rsplit("-", 1)[0]
        assert region in ("us-west1", "us-central1", "us-east1"), \
            f"⚠️ {region} 唔喺免費區 → 會收錢"

    def test_disk_max_30gb(self, s):
        """⚠️ 免費上限係 30 GB —— 多咗會收錢。"""
        m = re.search(r'DISK_GB="\$\{WANDER_DISK:-(\d+)\}"', s)
        assert m, "冇 DISK_GB"
        assert int(m.group(1)) <= 30, f"磁碟 {m.group(1)} GB > 30 → 會收錢"

    def test_disk_is_standard(self, s):
        """
        ⚠️⚠️ 一定要 `pd-standard` ——
           `pd-balanced` / `pd-ssd` 都**唔喺**免費額度。
        """
        assert "pd-standard" in s, "唔係 pd-standard → 會收錢"
        assert "pd-balanced" not in s, "用咗 pd-balanced → 收錢"
        assert "pd-ssd" not in s, "用咗 pd-ssd → 收錢"


class TestCostSafety:
    def test_has_budget_alert(self, s):
        """
        ⚠️⚠️ **最重要** —— 一定要設 budget alert。
           唔係嘅話超出免費額度會靜靜收錢，用戶完全唔知。
        """
        assert "billing budgets create" in s, "冇 budget alert"
        assert "budget-amount" in s, "冇設金額"
        assert "threshold-rule" in s, "冇設 threshold"

    def test_budget_is_low(self, s):
        """⚠️ Alert 金額要低（$1）—— 咁一超就知。"""
        assert "1USD" in s, "alert 金額唔係 $1"

    def test_warns_about_egress(self, s):
        """
        ⚠️ 要講清楚邊度會收錢 ——
           免費額度只有 **1 GB/月 出流量**。
        """
        assert "出流量" in s or "egress" in s.lower(), "冇提流量限制"
        assert "1 GB" in s or "1GB" in s, "冇講 1 GB 上限"

    def test_has_stop_hint(self, s):
        """
        ⚠️ 要教用戶「唔用嗰陣停 VM」——
           停咗唔收錢，但資料留住。
        """
        assert "instances stop" in s, "冇停 VM 嘅方法"


class TestPersistence:
    """⚠️⚠️ SQLite + 上載嘅相一定要留住 —— 呢個係核心需求。"""

    def test_disk_persists(self, s):
        assert "--boot-disk-size" in s, "冇指定磁碟"

    def test_data_outside_repo(self, s):
        """
        ⚠️⚠️ 資料一定要放喺 **repo 以外** ——
           唔係嘅話 `git pull` 會撞到，而且 rebuild 會冇咗。
        """
        assert "WANDER_DB" in s, "冇設 WANDER_DB"
        assert "WANDER_UPLOAD_DIR" in s, "冇設 WANDER_UPLOAD_DIR"
        # ⚠️ 路徑唔可以喺 /opt/wander（repo）入面
        assert "/var/lib/wander" in s, "資料唔係放喺 /var/lib"
        m = re.search(r'WANDER_DB=(/var/lib/wander[^\s]*)', s)
        assert m, "WANDER_DB 唔喺 /var/lib"
        assert "/opt/wander" not in m.group(1), "DB 放喺 repo 入面 → git pull 會撞"

    def test_upload_dir_created(self, s):
        assert "mkdir -p /var/lib/wander/uploads" in s, "冇建 uploads 目錄"


class TestHTTPS:
    """
    ⚠️⚠️ PWA **一定**要 HTTPS ——
       唔係嘅話 service worker / 相機 / 剪貼板全部用唔到。
    """

    def test_uses_sslip_io(self, s):
        """
        ⚠️ GCP 只畀 IP，但要 HTTPS 就要 domain。
           ✅ `sslip.io` 係免費 wildcard DNS。
        """
        assert "sslip.io" in s, "冇用 sslip.io"

    def test_static_ip(self, s):
        """
        ⚠️⚠️ 一定要**靜態** IP ——
           唔係嘅話重開機換 IP，`<ip>.sslip.io` 個名就失效，
           PWA 就死（同 serveo 隨機名一樣嘅問題）。
        """
        assert "addresses create" in s, "冇保留靜態 IP"
        assert "addresses describe" in s, "冇讀返 IP"

    def test_uses_caddy_auto_https(self, s):
        """⚠️ Caddy 自動攞 Let's Encrypt 證書（唔使手動 renew）。"""
        assert "caddy" in s.lower(), "冇用 Caddy"
        assert "reverse_proxy" in s, "冇 proxy 去 app"

    def test_caddy_config_valid(self, s):
        """⚠️ Caddyfile 要有 host + reverse_proxy。"""
        i = s.index("CADDYEOF")
        # ⚠️ 搵 Caddyfile 嘅內容
        m = re.search(r"cat > /etc/caddy/Caddyfile <<'CADDYEOF'\n(.*?)\nCADDYEOF",
                      s, re.S)
        assert m, "搵唔到 Caddyfile"
        cfg = m.group(1)
        assert "__HOST__" in cfg, "冇 host"
        assert "reverse_proxy 127.0.0.1:8787" in cfg, "proxy 唔啱"


class TestAutostart:
    """⚠️ VM 重開機之後 app 要自己起返。"""

    def test_systemd_service(self, s):
        assert "systemd/system/wander.service" in s, "冇 systemd service"
        assert "systemctl enable --now wander" in s, "冇 enable"

    def test_service_restarts(self, s):
        assert "Restart=always" in s, "冇自動重啟"

    def test_service_sets_env(self, s):
        """⚠️ systemd 一定要設 DB / uploads（唔係嘅話用返 repo 路徑）。"""
        i = s.index("[Service]")
        j = s.index("[Install]", i)
        blk = s[i:j]
        assert "WANDER_DB=" in blk, "service 冇設 DB"
        assert "WANDER_UPLOAD_DIR=" in blk, "service 冇設 uploads"

    def test_startup_script_idempotent(self, s):
        """
        ⚠️ 啟動 script 要**可以重複跑** ——
           VM reset 或者改 script 之後會再跑一次。
        """
        assert '[ ! -d "$APP/.git" ]' in s, "clone 唔係 idempotent"
        assert "[ ! -f " in s, "build 唔係 idempotent"
        assert "git pull" in s, "冇 pull 更新"


class TestPlaceholders:
    def test_placeholders_replaced(self, s):
        """
        ⚠️⚠️ `__REPO__` / `__HOST__` 一定要喺 heredoc **外面** 替換 ——
           因為 heredoc 用咗 `<<'VMEOF'`（quoted）唔會自動展開。
        """
        assert "__REPO__" in s, "冇 __REPO__ placeholder"
        assert "__HOST__" in s, "冇 __HOST__ placeholder"
        assert "sed -i" in s, "冇替換 placeholder"
        i = s.index("sed -i")
        line = s[i:i + 120].split("\n")[0]
        assert "__REPO__" in line and "__HOST__" in line, "sed 冇換兩個 placeholder"

    def test_heredoc_is_quoted(self, s):
        """
        ⚠️⚠️ 一定要 `<<'VMEOF'`（有引號）——
           唔係嘅話 Cloud Shell 會**提早展開** `$(date)` 之類，
           而且 `$APP` 會用錯值。
        """
        assert "<<'VMEOF'" in s, "heredoc 冇 quote → 會提早展開"

    def test_real_substitution_works(self):
        """⚠️ **實測**：模擬替換，確認冇 placeholder 剩。"""
        import subprocess
        r = subprocess.run(
            ["sed", "s|__REPO__|https://x/y.git|g; s|__HOST__|1.2.3.4.sslip.io|g",
             str(SH)], capture_output=True, text=True)
        out = r.stdout
        assert "__REPO__" not in out, "仲有 __REPO__"
        assert "__HOST__" not in out, "仲有 __HOST__"


class TestCloudShellReady:
    """⚠️ 用戶要喺 **Google Cloud Shell** 一鍵跑 —— 唔使本機設定。"""

    def test_mentions_cloud_shell(self, s):
        assert "Cloud Shell" in s, "冇講喺邊度跑"

    def test_has_one_liner(self, s):
        """⚠️ 要有 `curl | bash` 一行（最方便）。"""
        assert "curl -fsSL" in s and "| bash" in s, "冇一行安裝"

    def test_checks_gcloud(self, s):
        assert "command -v gcloud" in s, "冇檢查 gcloud"

    def test_checks_billing(self, s):
        """
        ⚠️ 冇 billing account 就跑唔到 ——
           要早啲檢查同埋講清楚點開。
        """
        assert "billing projects describe" in s, "冇檢查 billing"
        assert "console.cloud.google.com/billing" in s, "冇講點開 billing"


class TestDocs:
    def test_gcp_md_exists(self):
        p = ROOT / "GCP.md"
        assert p.exists(), "冇 GCP.md 指南"
        s = p.read_text(encoding="utf-8")
        assert "e2-micro" in s, "冇講 machine type"
        assert "$0" in s or "免費" in s, "冇講成本"
