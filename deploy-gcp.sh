#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  ☁️  Wander → Google Cloud e2-micro（永久免費）
# ══════════════════════════════════════════════════════════════════════
#
#  ⚠️⚠️ 為咩用 GCP e2-micro：
#
#     用戶講得對：「問題你去旅行唔會開電腦」——
#     serveo / cloudflared 要你部電腦開住，**旅行 app 唔可以咁**。
#
#     ✅ GCP Always Free：
#        · 1 × e2-micro VM（永久，唔係 trial）
#        · 1 GB RAM + 2 vCPU（shared）
#        · 30 GB 標準持久磁碟   ← SQLite + 相片都留住
#        · 24/7，唔會 sleep
#        · 💰 $0/月
#        ⚠️ 要信用卡（但唔會收錢，只要唔超免費額度）
#
#     ⚠️ 對比：
#        · Fly.io      —— 2024-10-07 已取消免費 tier，US$3.44/月
#        · Oracle Free —— 12 GB RAM 但要「搶」capacity，好常開唔到
#        · Render      —— 免費版**冇持久磁碟**，SQLite 每次重啟清空
#
#  ⚠️⚠️ 為咩用 sslip.io + Caddy：
#
#     · GCP 只畀你一個 IP，但 **PWA 一定要 HTTPS**
#     · `sslip.io` 係免費 wildcard DNS ——
#       `34.1.2.3.sslip.io` 自動解析去 `34.1.2.3`
#     · `Caddy` 自動由 Let's Encrypt 攞證書（一行 config）
#     ✅ 唔使買 domain、唔使手動 renew 證書
#
#  ⚠️ 喺邊度跑：
#     **Google Cloud Shell**（瀏覽器入面，唔使裝嘢喺你部機）
#       → https://console.cloud.google.com/
#       → 右上角有個 `>_` 圖示
#
#  用法（喺 Cloud Shell 貼）：
#     curl -fsSL https://raw.githubusercontent.com/Mizuki0215/WANDER/main/deploy-gcp.sh | bash
#
#   ⚠️ 或者先 clone 再跑（推薦，可以改）：
#     git clone https://github.com/Mizuki0215/WANDER.git
#     cd WANDER && ./deploy-gcp.sh
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── 設定（可以改）──────────────────────────────────────────────────
VM_NAME="${WANDER_VM:-wander}"
ZONE="${WANDER_ZONE:-us-central1-a}"        # ⚠️ 一定要 us-central1（免費區）
MACHINE="${WANDER_MACHINE:-e2-micro}"       # ⚠️ 一定要 e2-micro
DISK_GB="${WANDER_DISK:-30}"                # ⚠️ 30 GB 係免費上限
REPO="${WANDER_REPO:-https://github.com/Mizuki0215/WANDER.git}"
IP_NAME="${WANDER_IP:-wander-ip}"
FW_NAME="wander-web"

# ── 顏色 ────────────────────────────────────────────────────────
B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
say()  { echo "${B}${G}▶${N} $*"; }
warn() { echo "${B}${Y}⚠${N} $*"; }
die()  { echo "${B}${R}✗${N} $*" >&2; exit 1; }

echo
echo "════════════════════════════════════════════════════════════════"
echo "  ☁️  Wander → GCP e2-micro（永久免費）"
echo "════════════════════════════════════════════════════════════════"
echo

# ── ① 檢查 gcloud ──────────────────────────────────────────────
command -v gcloud >/dev/null 2>&1 || die "搵唔到 gcloud —— 要喺 Google Cloud Shell 跑"

PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  # ⚠️⚠️ 唔好淨係話「冇揀 project」—— 要**列出**有咩揀，
  #    同埋教用戶點建一個。（實測：用戶第一次跑就撞到呢個。）
  warn "Cloud Shell 未揀 project"
  echo
  echo "  ${B}你有嘅 project：${N}"
  gcloud projects list --format="table(projectId,name)" 2>/dev/null \
    | sed 's/^/    /' || echo "    （冇）"
  echo
  echo "  ${B}做法：${N}"
  echo "    ① 揀一個（用 PROJECT_ID，唔係 NAME）："
  echo "         gcloud config set project 你嘅-project-id"
  echo "    ② 冇 project 就建一個："
  echo "         gcloud projects create wander-app-\$RANDOM --name=Wander"
  echo "         gcloud config set project \$(gcloud projects list --format='value(projectId)' --limit=1)"
  echo "    ③ 再跑："
  echo "         bash deploy-gcp.sh"
  echo
  die "請揀咗 project 再跑"
fi
say "Project：${B}${PROJECT}${N}"

# ⚠️⚠️ 一定要設 budget alert —— 唔係嘅話超出免費額度會靜靜收錢
say "確認 billing…"
if ! gcloud billing projects describe "$PROJECT" >/dev/null 2>&1; then
  warn "冇 billing account —— 要先去 console 開（免費額度都要）"
  warn "  https://console.cloud.google.com/billing"
  die "請開咗 billing 再跑"
fi

# ── ② API ──────────────────────────────────────────────────────
say "開 API（compute）…"
gcloud services enable compute.googleapis.com --quiet

# ── ③ 靜態 IP ──────────────────────────────────────────────────
# ⚠️⚠️ 一定要**靜態** IP —— 唔係嘅話重開機換 IP，
#    `sslip.io` 個名會失效，PWA 就死（同 serveo 一樣嘅問題）。
say "保留靜態 IP…"
if ! gcloud compute addresses describe "$IP_NAME" --region="${ZONE%-*}" >/dev/null 2>&1; then
  gcloud compute addresses create "$IP_NAME" --region="${ZONE%-*}" --quiet
fi
IP="$(gcloud compute addresses describe "$IP_NAME" --region="${ZONE%-*}" \
        --format='get(address)')"
HOST="${IP}.sslip.io"      # ⚠️ 免費 wildcard DNS → 解析去呢個 IP
say "IP：${B}${IP}${N}"
say "網址：${B}https://${HOST}${N}"

# ── ④ 防火牆 ───────────────────────────────────────────────────
say "開防火牆 22 / 80 / 443…"
if ! gcloud compute firewall-rules describe "$FW_NAME" >/dev/null 2>&1; then
  gcloud compute firewall-rules create "$FW_NAME" \
    --allow=tcp:22,tcp:80,tcp:443 \
    --target-tags=wander \
    --description="Wander web" --quiet
fi

# ── ⑤ 啟動 script（喺 VM 入面跑）──────────────────────────────
# ⚠️ 用 startup-script 而唔係 ssh 落去跑命令 ——
#    咁樣 VM 重開機都會自動重新設定好。
STARTUP="$(mktemp)"
cat > "$STARTUP" <<'VMEOF'
#!/usr/bin/env bash
# ⚠️ 唔用 `set -e` —— 一個步驟失敗唔應該令成個開機停低
set -ux
exec > /var/log/wander-setup.log 2>&1
echo "=== Wander setup $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl \
                       libgl1 libglib2.0-0

# ── Caddy（自動 HTTPS）──
if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi

# ── App ──
APP=/opt/wander
if [ ! -d "$APP/.git" ]; then
  git clone __REPO__ "$APP"
fi
cd "$APP"
git pull --ff-only || true

# ⚠️ 資料放喺 /var/lib/wander —— 唔好放喺 /opt（方便備份）
mkdir -p /var/lib/wander/uploads
export WANDER_DB=/var/lib/wander/wander.db
export WANDER_UPLOAD_DIR=/var/lib/wander/uploads

python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/server/requirements.txt"

# ── 前端 build ──
if [ ! -f "$APP/web/dist/index.html" ]; then
  if ! command -v node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
  fi
  cd "$APP/web" && npm ci --silent && npm run build
fi

# ── systemd ──
cat > /etc/systemd/system/wander.service <<'SVCEOF'
[Unit]
Description=Wander
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wander/server
Environment=WANDER_DB=/var/lib/wander/wander.db
Environment=WANDER_UPLOAD_DIR=/var/lib/wander/uploads
Environment=WANDER_PORT=8787
ExecStart=/opt/wander/.venv/bin/python -m app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable --now wander

# ── Caddy ──
# ⚠️ `__HOST__` 由 deploy 時替換
cat > /etc/caddy/Caddyfile <<'CADDYEOF'
__HOST__ {
    encode gzip
    reverse_proxy 127.0.0.1:8787
}
CADDYEOF
systemctl restart caddy

echo "=== 完成 $(date) ==="
VMEOF

# ⚠️ 替換 placeholder（heredoc quoted 所以唔會自動展開）
sed -i "s|__REPO__|${REPO}|g; s|__HOST__|${HOST}|g" "$STARTUP"

# ── ⑥ 建 VM ────────────────────────────────────────────────────
say "建 VM（第一次要 3–5 分鐘）…"
if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" >/dev/null 2>&1; then
  warn "VM 已經有 —— 更新 startup script + 重開機"
  gcloud compute instances add-metadata "$VM_NAME" --zone="$ZONE" \
    --metadata-from-file=startup-script="$STARTUP" --quiet
  gcloud compute instances reset "$VM_NAME" --zone="$ZONE" --quiet
else
  gcloud compute instances create "$VM_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE" \
    --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
    --boot-disk-size="${DISK_GB}GB" \
    --boot-disk-type=pd-standard \
    --address="$IP" \
    --tags=wander \
    --metadata-from-file=startup-script="$STARTUP" \
    --quiet
fi
rm -f "$STARTUP"

# ── ⑦ Budget alert ─────────────────────────────────────────────
# ⚠️⚠️ 呢個好重要 —— 超出免費額度嘅話，冇 alert 就會靜靜收錢
say "設 budget alert（$1）…"
BILLING="$(gcloud billing projects describe "$PROJECT" \
            --format='value(billingAccountName)' 2>/dev/null | sed 's|billingAccounts/||')"
if [ -n "$BILLING" ]; then
  if ! gcloud billing budgets list --billing-account="$BILLING" \
        --format='value(displayName)' 2>/dev/null | grep -q "Wander"; then
    gcloud billing budgets create \
      --billing-account="$BILLING" \
      --display-name="Wander \$1 alert" \
      --budget-amount=1USD \
      --threshold-rule=percent=0.5 \
      --threshold-rule=percent=0.9 \
      --threshold-rule=percent=1.0 \
      --quiet 2>/dev/null || warn "budget alert 建立失敗（可以手動設）"
  fi
fi

# ── ⑧ 完成 ─────────────────────────────────────────────────────
cat <<EOF

════════════════════════════════════════════════════════════════
  ✅ 搞掂！
════════════════════════════════════════════════════════════════

  🌐 你嘅網址（永久）：
     ${B}https://${HOST}${N}

  ⚠️ 第一次開要等 3–5 分鐘（VM 裝緊嘢 + 攞 HTTPS 證書）

  ── 睇進度 ──
     gcloud compute ssh ${VM_NAME} --zone=${ZONE} \\
       --command='sudo tail -f /var/log/wander-setup.log'

  ── 睇 app log ──
     gcloud compute ssh ${VM_NAME} --zone=${ZONE} \\
       --command='sudo journalctl -u wander -f'

  ── 更新 code ──
     gcloud compute ssh ${VM_NAME} --zone=${ZONE} \\
       --command='cd /opt/wander && sudo git pull && sudo systemctl restart wander'

  ── 重新 build 前端 ──
     gcloud compute ssh ${VM_NAME} --zone=${ZONE} --command='
       cd /opt/wander/web && sudo npm ci && sudo npm run build &&
       sudo systemctl restart wander'

  ── ⚠️ 備份你嘅資料 ──
     gcloud compute ssh ${VM_NAME} --zone=${ZONE} \\
       --command='sudo tar czf - /var/lib/wander' > wander-backup-\$(date +%F).tgz

  ── 💰 成本 ──
     VM + 30GB 磁碟：  \$0/月（Always Free）
     ⚠️ 超出 1 GB/月 出流量會收錢 —— 已設 \$1 budget alert

  ── ⚠️ 慳錢貼士 ──
     唔用嗰陣可以停 VM（唔會收錢，但資料留住）：
       gcloud compute instances stop ${VM_NAME} --zone=${ZONE}
     再開：
       gcloud compute instances start ${VM_NAME} --zone=${ZONE}

════════════════════════════════════════════════════════════════
EOF
