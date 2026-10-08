#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  🌐 固定網址 Tunnel（serveo + 自動重連）
# ══════════════════════════════════════════════════════════════
#
#  ⚠️⚠️ 為咩要呢個 script：
#
#     2026-10-08 用戶報「我宜家入唔到去，用我 email 佢話 load failed」。
#
#     ⚠️ 根因：cloudflared quick tunnel **死咗** ——
#        而且 quick tunnel 每次重啟都**換 URL**。
#        用戶部 PWA 指住嗰個舊 URL → Safari 就話「load failed」。
#
#     ✅ 用 serveo **註冊咗嘅固定名**：
#          https://wander-mizuki.serveousercontent.com
#        ⚠️ 唔係 `wander-mizuki.serveo.net` ——
#           嗰個名會 **302 跳去 serveo 官網**（唔 work）！
#           要測過先用（我實測捉到）。
#
#     ✅ 呢個 script 會**自動重連**（serveo 有時斷線）。
#
#  用法：
#     ./keep-tunnel.sh          # 前景（Ctrl-C 停）
#     nohup ./keep-tunnel.sh &  # 背景
# ══════════════════════════════════════════════════════════════
set -u

NAME="${WANDER_SERVEO_NAME:-wander-mizuki}"
PORT="${WANDER_PORT:-8787}"
URL="https://${NAME}.serveousercontent.com"
LOG="/tmp/wander-tunnel.log"

echo "════════════════════════════════════════════════════════════"
echo "  🌐 固定網址 Tunnel"
echo "════════════════════════════════════════════════════════════"
echo
echo "  網址：$URL"
echo "  本機：http://localhost:$PORT"
echo "  Log ：$LOG"
echo
echo "  ⚠️ 保持呢個窗口開住 —— 閂咗就斷線。"
echo "     Ctrl-C 停止。"
echo

# ⚠️ 一定要 `ServerAliveInterval` —— 唔係嘅話網絡一閃就斷，
#    而且 ssh 唔會自己 reconnect。
while true; do
  echo "[$(date '+%H:%M:%S')] 連線中…"
  ssh -o StrictHostKeyChecking=no \
      -o ServerAliveInterval=20 \
      -o ServerAliveCountMax=3 \
      -o ExitOnForwardFailure=yes \
      -o TCPKeepAlive=yes \
      -R "${NAME}:80:localhost:${PORT}" serveo.net 2>&1 | tee -a "$LOG"

  # ⚠️ 斷咗 → 等 3 秒再連（唔好狂重試，serveo 會 ban）
  echo "[$(date '+%H:%M:%S')] ⚠️ 斷線 —— 3 秒後重連…"
  sleep 3
done
