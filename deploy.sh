#!/usr/bin/env bash
#
# 部署上 Fly.io（永久 link）
# ============================
#
# ⚠️⚠️ 為咩要呢個 script 而唔係叫你自己打指令：
#
#   ① `brew install flyctl` 喺呢部機**失敗**（`/opt/homebrew/Cellar`
#      唔可以寫）→ 我直接下載 binary 落 `.tools/bin/flyctl`
#   ② `flyctl` 想寫 `~/.fly`，但 sandbox 唔准 →
#      要設 `FLY_CONFIG_DIR` 去 workspace 入面
#
# 用法：
#     ./deploy.sh              # 登入 + 部署
#     ./deploy.sh --status     # 睇狀態
#     ./deploy.sh --logs       # 睇 log

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ⚠️ 一定要設 —— 唔係嘅話 flyctl 會試寫 ~/.fly 然後爆
export FLY_CONFIG_DIR="$ROOT/.fly"
mkdir -p "$FLY_CONFIG_DIR"

FLY="$ROOT/.tools/bin/flyctl"
if [ ! -x "$FLY" ]; then
  echo "  ✗ 搵唔到 .tools/bin/flyctl"
  echo "     下載："
  echo "     curl -sL -o /tmp/fly.tgz https://github.com/superfly/flyctl/releases/download/v0.4.114/flyctl_0.4.114_macOS_arm64.tar.gz"
  echo "     tar -xzf /tmp/fly.tgz -C .tools/bin"
  exit 1
fi

echo "════════════════════════════════════════════════════════════"
echo "  Wander → Fly.io"
echo "════════════════════════════════════════════════════════════"
echo

case "${1:-}" in
  --status)
    "$FLY" status -a "$("$FLY" config show 2>/dev/null | grep -m1 '^app' | awk '{print $3}' | tr -d "'" || echo wander)"
    exit 0
    ;;
  --logs)
    "$FLY" logs
    exit 0
    ;;
esac

# ── ① 檢查 app 名 ──
APP="$(grep -m1 '^app' fly.toml | sed 's/.*= *"\(.*\)"/\1/')"
if [ "$APP" = "wander-CHANGE-ME" ] || [ -z "$APP" ]; then
  echo "  ⚠️⚠️ fly.toml 個 app 名仲係預設值 —— 一定要改。"
  echo
  echo "     Fly.io 嘅 app 名要**全球唯一**。"
  echo "     開 fly.toml，第一行改成例如："
  echo "         app = \"wander-mizuki\""
  echo
  read -r -p "  而家幫你改成咩名？（留空 = 取消）：" NAME
  [ -z "$NAME" ] && { echo "  取消"; exit 0; }
  # ⚠️ 只准細寫英數同 dash
  NAME="$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')"
  /opt/anaconda3/bin/python3 - "$NAME" <<'PY'
import pathlib, re, sys
p = pathlib.Path("fly.toml"); s = p.read_text(encoding="utf-8")
p.write_text(re.sub(r'^app = .*$', f'app = "{sys.argv[1]}"', s, flags=re.M),
             encoding="utf-8")
PY
  APP="$NAME"
  echo "  ✓ app = \"$APP\""
  echo
fi

# ── ② 登入 ──
echo "  ① 登入 Fly.io"
if "$FLY" auth whoami >/dev/null 2>&1; then
  echo "     ✓ 已經登入：$("$FLY" auth whoami 2>/dev/null)"
else
  echo "     ⚠️ 未登入 —— 會開瀏覽器"
  echo "        （或者用 API token：fly auth token）"
  "$FLY" auth login
fi
echo

# ── ③ volume（⚠️⚠️ 最重要）──
echo "  ② 資料庫 volume"
if "$FLY" volumes list -a "$APP" 2>/dev/null | grep -q wander_data; then
  echo "     ✓ wander_data 已經有"
else
  echo "     ⚠️⚠️ 冇 volume 嘅話**每次 deploy 都會清空所有用戶資料**"
  "$FLY" volumes create wander_data --size 1 -a "$APP" --yes
  echo "     ✓ 建立咗"
fi
echo

# ── ④ secrets ──
echo "  ③ Secrets（⚠️ 唔可以寫入 fly.toml —— 會 commit）"
#
# ⚠️ 預設用 invite 模式 —— 放出街唔應該無門檻（用戶之前用 open）
if ! "$FLY" secrets list -a "$APP" 2>/dev/null | grep -q WANDER_SIGNUP_MODE; then
  echo "  ┌──────────────────────────────────────────────────────┐"
  echo "  │  註冊模式                                            │"
  echo "  └──────────────────────────────────────────────────────┘"
  echo "    1) invite（要邀請碼）——  推薦，放出街"
  echo "    2) open（任何人有網址就註冊到）"
  read -r -p "  揀 (1/2) [1]：" MODE
  [ "$MODE" = "2" ] && SM=open || SM=invite
  "$FLY" secrets set "WANDER_SIGNUP_MODE=$SM" -a "$APP"
  echo "     ✓ WANDER_SIGNUP_MODE=$SM"
else
  echo "     ✓ WANDER_SIGNUP_MODE 已經設定"
fi

if ! "$FLY" secrets list -a "$APP" 2>/dev/null | grep -q WANDER_ADMIN_EMAILS; then
  read -r -p "  你嘅 email（admin，可以入後台）[admin@wander.local]：" AE
  "$FLY" secrets set "WANDER_ADMIN_EMAILS=${AE:-admin@wander.local}" -a "$APP"
  echo "     ✓ WANDER_ADMIN_EMAILS"
fi
echo

# ── ⑤ 部署 ──
echo "  ④ Deploy（第一次要 build image，約 3-6 分鐘）"
echo
"$FLY" deploy -a "$APP"

echo
echo "════════════════════════════════════════════════════════════"
echo "  ✅ 部署完成"
echo "════════════════════════════════════════════════════════════"
echo
echo "  🌍 你嘅永久網址："
echo
echo "     https://$APP.fly.dev"
echo
echo "  ⚠️ 之後更新：改完 code 再跑 ./deploy.sh"
echo "  ⚠️ 睇 log：  ./deploy.sh --logs"
echo "  ⚠️ 睇狀態：  ./deploy.sh --status"
echo
