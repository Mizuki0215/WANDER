#!/usr/bin/env bash
#
# 一鍵對外開放（cloudflared quick tunnel）
# =========================================
#
# ⚠️⚠️ 用戶要求：「host 佢」
#
# ⚠️⚠️⚠️ 但 open 註冊 + 公開網址 = **任何知你網址嘅人都可以註冊**
#
#    呢個 script 會喺起 tunnel **之前**問你一次，
#    而且預設建議你用 invite 模式。
#
# 用法：
#     ./host.sh              # 起 server + tunnel（會問安全選項）
#     ./host.sh --open       # 唔問，直接用 open（⚠️ 唔建議）
#
# ⚠️ cloudflared quick tunnel 嘅網址**每次都會變** ——
#    所以每次都要重新跑呢個 script（佢會自動更新 WANDER_BASE_URL）。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
PORT="${WANDER_PORT:-8787}"
SKIP_ASK="${1:-}"

echo "════════════════════════════════════════════════════════════"
echo "  Wander 對外開放"
echo "════════════════════════════════════════════════════════════"
echo

# ── ① 檢查工具 ──
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "  ✗ 冇 cloudflared"
  echo "     brew install cloudflared"
  exit 1
fi
echo "  ✓ cloudflared"

# ── ② 安全檢查 ──
MODE="$("$PY" - <<'EOF' 2>/dev/null || echo "?"
import sys
sys.path.insert(0, "server"); sys.path.insert(0, "engine")
try:
    from app import main
    print(main.signup_mode())
except Exception:
    print("?")
EOF
)"
echo "  註冊模式：$MODE"
echo

if [ "$MODE" = "open" ] && [ "$SKIP_ASK" != "--open" ]; then
  echo "  ⚠️⚠️⚠️  注意  ⚠️⚠️⚠️"
  echo
  echo "  你而家係 **open** 模式 —— 註冊只需要 email + 密碼。"
  echo "  一旦放出街，**任何知你網址嘅人都可以註冊**，"
  echo "  而且可以用**任何 email**（包括你朋友嘅）。"
  echo
  echo "  純內網（192.168.x.x）冇問題，但放出街就要考慮。"
  echo
  echo "  選項："
  echo "    1) 改成 invite 模式（要邀請碼）——  推薦"
  echo "    2) 照用 open（我知風險）"
  echo "    3) 唔 host 住，取消"
  echo
  read -r -p "  揀 (1/2/3) [1]: " CHOICE
  CHOICE="${CHOICE:-1}"
  case "$CHOICE" in
    1)
      if grep -q "^WANDER_SIGNUP_MODE" server/.env 2>/dev/null; then
        "$PY" - <<'EOF'
import pathlib, re
p = pathlib.Path("server/.env"); s = p.read_text(encoding="utf-8")
p.write_text(re.sub(r"^WANDER_SIGNUP_MODE=.*$", "WANDER_SIGNUP_MODE=invite",
                    s, flags=re.M), encoding="utf-8")
EOF
      else
        echo "WANDER_SIGNUP_MODE=invite" >> server/.env
      fi
      echo "  ✓ 改成 invite 模式"
      echo "     ⚠️ 去「設定 → 開發版後台 → 🔑 註冊邀請碼」產生邀請碼"
      ;;
    2)
      echo "  ⚠️ 照用 open —— 記住你嘅網址唔好亂 share"
      ;;
    *)
      echo "  取消"
      exit 0
      ;;
  esac
  echo
fi

# ── ③ 起 tunnel ──
echo "  起 tunnel…"
LOG="$(mktemp -t wander-cf)"
cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG" 2>&1 &
CF_PID=$!
trap 'kill $CF_PID 2>/dev/null || true' EXIT

URL=""
for _ in $(seq 1 40); do
  sleep 1
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1 || true)"
  [ -n "$URL" ] && break
done

if [ -z "$URL" ]; then
  echo "  ✗ 攞唔到公開網址。cloudflared 輸出："
  tail -20 "$LOG"
  exit 1
fi
echo "  ✓ $URL"

# ── ④ 更新 WANDER_BASE_URL（QR code 要用）──
"$PY" - "$URL" <<'EOF'
import pathlib, re, sys
url = sys.argv[1]
p = pathlib.Path("server/.env")
s = p.read_text(encoding="utf-8") if p.exists() else ""
if "WANDER_BASE_URL=" in s:
    s = re.sub(r"^WANDER_BASE_URL=.*$", f"WANDER_BASE_URL={url}", s, flags=re.M)
else:
    s = s.rstrip() + f"\n\n# ── 對外網址（QR code 用）──\nWANDER_BASE_URL={url}\n"
p.write_text(s, encoding="utf-8")
EOF
echo "  ✓ WANDER_BASE_URL 已更新"

# ── ⑤ 起 server ──
echo
echo "  起 server…"
cd server
"$PY" -m app &
SRV_PID=$!
trap 'kill $CF_PID $SRV_PID 2>/dev/null || true' EXIT

sleep 6
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL/" || echo 000)"

echo
echo "════════════════════════════════════════════════════════════"
if [ "$CODE" = "200" ]; then
  echo "  ✅ 上線！"
else
  echo "  ⚠️ 本地 server 未 ready（HTTP ${CODE}）—— 等幾秒再試"
fi
echo "════════════════════════════════════════════════════════════"
echo
echo "  🌍 公開網址（畀朋友）："
echo
echo "     $URL"
echo
echo "  ⚠️ 呢個網址係**臨時**嘅 —— 一閂呢個 script 就冇。"
echo "     下次再跑會出**另一個**網址。"
echo
echo "  ⚠️ 手機可以直接用（HTTPS → PWA / 相機 / 離線都用得）"
echo "     Safari：分享 → 加到主畫面"
echo
echo "  按 Ctrl+C 停。"
echo
wait
