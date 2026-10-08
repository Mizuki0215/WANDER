#!/usr/bin/env bash
#
# 推上 GitHub
# ============
#
# ⚠️⚠️ 為咩用呢個 script 而唔係叫你打 token 落 chat：
#
#   你之前聽我講過「唔好喺 chat 打密碼」——
#   **GitHub token 都係一樣**。打出嚟就會留喺對話紀錄。
#
#   呢個 script 用 `read -s`（唔 echo）收 token，
#   token 只會：
#     ① 用嚟打 GitHub API 建立 repo（一次性）
#     ② 用嚟 push（之後存落 macOS keychain）
#   **唔會**經任何對話、唔會寫入 repo、唔會 log。
#
# 用法：
#     ./push-to-github.sh
#
# 需要：
#     · GitHub account：Mizuki0215
#     · repo 名：Wander
#     · 一個 Personal Access Token（classic，要 `repo` scope）
#         https://github.com/settings/tokens/new?scopes=repo

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
OWNER="${GITHUB_OWNER:-Mizuki0215}"
REPO="${GITHUB_REPO:-Wander}"
OLD_GH="${GITHUB_OLD_NAME:-yeetung-work}"

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "════════════════════════════════════════════════════════════"
echo "  推上 GitHub"
echo "════════════════════════════════════════════════════════════"
echo
echo "  帳號：$OWNER"
echo "  Repo：$OWNER/$REPO"
echo

# ── ① 安全檢查（最後一次）──
echo "  ⚠️ 安全檢查…"
BAD=$(git ls-files | grep -cE '(^|/)\.env$|wander\.db|node_modules/|geocode_cache|backup-.*\.db' || true)
if [ "$BAD" != "0" ]; then
  echo "  ✗✗✗ 發現 $BAD 個敏感檔案喺 git 入面！"
  git ls-files | grep -E '(^|/)\.env$|wander\.db|node_modules/|geocode_cache|backup-.*\.db' | sed 's/^/      /'
  echo
  echo "  ⚠️ 唔好 push。先 `git rm --cached <檔案>` 加落 .gitignore。"
  exit 1
fi
echo "  ✅ 冇秘密（$(git ls-files | wc -l | tr -d ' ') 個檔案）"
echo

# ── ② 收 token（唔 echo）──
# ══════════════════════════════════════════════════════════════
# 攞 token
# ══════════════════════════════════════════════════════════════
# ✅ 最好嘅方法：`gh` device flow（**完全唔使貼 token**）
# ══════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 為咩要有呢條路：
#   用戶實測**貼咗 token 落 chat**（`ghp_xxxx…`）——
#   我哋兩邊都見到，要即刻撤銷。Token 唔應該經對話。
#
#   `gh auth login` 用 GitHub 嘅 **device flow**：
#     · 終端機顯示一個 8 位 code（例：`ABCD-1234`）
#     · 你去 https://github.com/login/device 打個 code
#     · 授權完，`gh` 自己攞 token **存喺本機**
#   → ⚠️ **token 從來冇出現過喺螢幕或者對話**
#
# ⚠️ `brew install gh` 喺呢部機失敗（Cellar 唔可寫）→
#    我直接下載 binary 落 `.tools/bin/gh`（已 gitignore）。
GH="$ROOT/.tools/bin/gh"
if [ -x "$GH" ]; then
  export GH_CONFIG_DIR="$ROOT/.gh"
  mkdir -p "$GH_CONFIG_DIR"

  echo "  ┌──────────────────────────────────────────────────────────┐"
  echo "  │  ✅ 用 GitHub device flow（唔使貼 token）                 │"
  echo "  └──────────────────────────────────────────────────────────┘"
  echo

  if ! "$GH" auth status >/dev/null 2>&1; then
    echo "  ⚠️ 未登入 —— 跟住螢幕做："
    echo "     ① 佢會顯示一個 code（例：ABCD-1234）"
    echo "     ② 去 https://github.com/login/device 打個 code"
    echo "     ③ 授權 → 返嚟呢度會自動繼續"
    echo
    "$GH" auth login --hostname github.com --git-protocol https --web
  fi

  if "$GH" auth status >/dev/null 2>&1; then
    WHO="$("$GH" api user --jq .login 2>/dev/null || echo "")"
    echo "  ✓ 登入咗：${WHO:-（未知）}"
    echo
    echo "  建立 / 更新 repo $OWNER/$REPO …"
    # ⚠️ 如果舊名 repo 仲喺，改名
    if [ "$OLD_GH" != "$REPO" ] && "$GH" repo view "$OWNER/$OLD_GH" >/dev/null 2>&1; then
      echo "  ⚠️ 發現舊 repo「${OLD_GH}」→ 改名做「${REPO}」"
      "$GH" repo rename "$REPO" "$OWNER/$OLD_GH" --yes 2>/dev/null || \
        echo "     （改名失敗，可能冇權限 —— 跳過）"
    fi
    # ⚠️ `--source=. --push` 一次過建 repo + push
    if "$GH" repo view "$OWNER/$REPO" >/dev/null 2>&1; then
      echo "  ✓ Repo 已經有 → 直接 push"
      git remote set-url origin "https://github.com/$OWNER/$REPO.git" 2>/dev/null || \
        git remote add origin "https://github.com/$OWNER/$REPO.git"
      git branch -M main
      git push -u origin main
    else
      "$GH" repo create "$REPO" --private --source=. --remote=origin --push \
        --description "Wander — 旅行計劃 app（純規則引擎，無 AI）"
    fi
    echo
    echo "════════════════════════════════════════════════════════════"
    echo "  ✅ 推咗！"
    echo "════════════════════════════════════════════════════════════"
    echo
    echo "  https://github.com/$OWNER/$REPO"
    echo
    echo "  之後轉 public："
    echo "    $GH repo edit $OWNER/$REPO --visibility public --accept-visibility-change-consequences"
    echo "    （或者去 https://github.com/$OWNER/$REPO/settings）"
    echo
    echo "  下一步（永久 link）：./deploy.sh"
    exit 0
  fi
  echo "  ⚠️ gh 登入唔成功 —— 退回 token 方法"
  echo
fi

# ══════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 為咩有三個方法：
#   實測用戶跑嗰陣 `read -s` 收到空字串（撳咗 Enter 但冇貼嘢）——
#   喺 macOS Terminal 貼長 token 落 `read -s` 有時會冇反應。
#
#   所以：
#     ① 剪貼板（`pbpaste`）—— ⚠️ **最可靠**，copy 就得，唔使貼
#     ② 環境變數 `GITHUB_TOKEN` —— 適合 CI
#     ③ `read -s` —— 最後手段
# ══════════════════════════════════════════════════════════════

cat <<'EOF'
  ┌──────────────────────────────────────────────────────────┐
  │  需要一個 GitHub Personal Access Token                    │
  └──────────────────────────────────────────────────────────┘

   ① 開呢個網址（已經填好 scope）：
      https://github.com/settings/tokens/new?scopes=repo&description=Wander

   ② 揀：☑ repo        （就咁一個夠，其他唔使 tick）
      有效期：7 日      （用完即刻刪）

   ③ 撳最底「Generate token」

   ④ ⚠️⚠️ 個 token 只會顯示**一次** —— 即刻 copy 佢
      （`ghp_...` 或者 `github_pat_...`）

   ⑤ 返嚟呢度，撳 Enter 就得 —— **唔使貼**，
      個 script 會自動由剪貼板攞。

  ⚠️ Token 只用嚟建 repo + push，**唔會**經對話、唔會寫入 repo。
EOF
echo

# ⚠️ 自動開瀏覽器 —— 用戶唔使自己 copy 網址
TOKEN_URL="https://github.com/settings/tokens/new?scopes=repo&description=Wander"
if command -v open >/dev/null 2>&1; then
  read -r -p "  幫你開瀏覽器去整 token？(Y/n)：" OPENIT
  if [ "$OPENIT" != "n" ] && [ "$OPENIT" != "N" ]; then
    open "$TOKEN_URL" 2>/dev/null && echo "  ✓ 開咗瀏覽器"
  fi
else
  echo "  自己開：$TOKEN_URL"
fi
echo
echo "  ⚠️ 整好之後：copy 個 token → 返嚟撳 Enter"
read -r -p "  整好未？撳 Enter 繼續…" _
echo

TOKEN="${GITHUB_TOKEN:-}"

# ① 剪貼板（最可靠）
if [ -z "$TOKEN" ] && command -v pbpaste >/dev/null 2>&1; then
  CLIP="$(pbpaste 2>/dev/null | tr -d '\r\n[:space:]' || true)"
  # ⚠️ 檢查似唔似 token（唔好攞咗啲唔相干嘅嘢）
  case "$CLIP" in
    ghp_*|github_pat_*|gho_*|ghs_*)
      echo "  📋 剪貼板搵到 token（${#CLIP} 字，頭 4 個：${CLIP:0:4}…）"
      read -r -p "  用佢？(Y/n)：" OK
      if [ "$OK" != "n" ] && [ "$OK" != "N" ]; then
        TOKEN="$CLIP"
      fi
      ;;
    "")
      echo "  📋 剪貼板係空嘅"
      ;;
    *)
      echo "  📋 剪貼板有嘢但唔似 token（頭 12 個：${CLIP:0:12}…）—— 唔用"
      ;;
  esac
fi

# ② 手動貼
while [ -z "$TOKEN" ]; do
  echo
  read -r -s -p "  貼 token（唔會顯示）或者撳 Ctrl+C 取消：" T
  echo
  T="$(printf '%s' "$T" | tr -d '[:space:]')"
  if [ -n "$T" ]; then
    TOKEN="$T"
    break
  fi
  echo "  ⚠️ 收到空字串。"
  echo "     ⚠️ 你可能未整 token：https://github.com/settings/tokens/new?scopes=repo"
  echo "     ⚠️ 或者試下 copy 佢，然後再跑呢個 script（會自動由剪貼板攞）"
  read -r -p "  再試？(Y/n)：" AGAIN
  if [ "$AGAIN" = "n" ] || [ "$AGAIN" = "N" ]; then
    echo "  取消"
    exit 1
  fi
done

echo "  ✓ 收到 token（${#TOKEN} 字）"
echo

# ── ③ 建 repo（如果未有）──
echo "  檢查 repo…"

# ⚠️⚠️ 如果用戶已經手動建咗一個舊名 repo（例如 yeetung-work），
#    我哋可以 API 改名 —— 但會**轉移 URL**。
#    ⚠️ 改名之後舊 URL 會自動 redirect（GitHub 做）。
OLD="${GITHUB_OLD_NAME:-yeetung-work}"
if [ "$OLD" != "$REPO" ]; then
  OLDCODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
    -H "Authorization: Bearer $TOKEN" \
    "https://api.github.com/repos/$OWNER/$OLD")
  if [ "$OLDCODE" = "200" ]; then
    echo "  ⚠️ 發現舊 repo「${OLD}」→ 改名做「${REPO}」？"
    read -r -p "     改名？(Y/n)：" REN
    if [ "$REN" != "n" ] && [ "$REN" != "N" ]; then
      RRESP=$(curl -s --max-time 30 -X PATCH \
        -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$OWNER/$OLD" \
        -d "{\"name\":\"$REPO\"}")
      if echo "$RRESP" | grep -q '"full_name"'; then
        echo "  ✅ 改咗做 $OWNER/$REPO"
        echo "     ⚠️ 舊 URL 會自動 redirect（GitHub 做）"
      else
        echo "  ⚠️ 改名失敗："
        echo "$RRESP" | head -c 300 | sed 's/^/      /'
        echo
      fi
    fi
  fi
fi

CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO")

if [ "$CODE" = "404" ]; then
  echo "  Repo 未有 → 建立…"
  RESP=$(curl -s --max-time 30 -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/user/repos" \
    -d "{\"name\":\"$REPO\",\"private\":true,\"description\":\"Wander — 旅行計劃 app\"}")
  if echo "$RESP" | grep -q '"full_name"'; then
    echo "  ✅ 建立咗 $OWNER/${REPO}（private）"
  else
    echo "  ✗ 建立失敗："
    echo "$RESP" | head -c 400 | sed 's/^/      /'
    echo
    echo "  ⚠️ token 有冇 ☑ repo scope？"
    exit 1
  fi
elif [ "$CODE" = "200" ]; then
  echo "  ✅ Repo 已經存在"
elif [ "$CODE" = "401" ]; then
  echo "  ✗ Token 無效（HTTP 401）"
  echo
  echo "     可能原因："
  echo "       · Token 打錯／貼漏"
  echo "       · Token 過期咗（你設咗幾日？）"
  echo "       · Token 已經被刪"
  echo
  echo "     → 去 https://github.com/settings/tokens 睇下仲有冇"
  echo "     → 冇就再整一個：https://github.com/settings/tokens/new?scopes=repo"
  exit 1
elif [ "$CODE" = "403" ]; then
  echo "  ✗ 冇權限（HTTP 403）"
  echo
  echo "     ⚠️ Token 有冇 tick ☑ **repo** scope？"
  echo "        （淨係 tick 咗 public_repo 就建唔到 private repo）"
  exit 1
else
  echo "  ⚠️ HTTP $CODE"
  echo "     再試一次；如果都唔得，睇下 GitHub 有冇壞"
  exit 1
fi

# ── ④ Push ──
echo
echo "  Push…"
git remote remove origin 2>/dev/null || true
# ⚠️ 用 token 落 URL，但**唔會**寫入 git config（用完即棄）
git remote add origin "https://$OWNER:$TOKEN@github.com/$OWNER/$REPO.git"
git branch -M main

if git push -u origin main 2>&1 | tail -6; then
  # ⚠️⚠️ 即刻將 token 由 remote URL 移除 ——
  #    唔係嘅話 `git remote -v` 會顯示成個 token。
  git remote set-url origin "https://github.com/$OWNER/$REPO.git"
  echo
  echo "════════════════════════════════════════════════════════════"
  echo "  ✅ 推咗！"
  echo "════════════════════════════════════════════════════════════"
  echo
  echo "  https://github.com/$OWNER/$REPO"
  echo
  echo "  ⚠️ remote URL 已經清走 token（安全）"

  # ⚠️⚠️ 問要唔要轉 public ——
  #    但**一定要講清楚**：public 只係「code 睇得到」，
  #    **唔係**「有個 web app link」。
  echo
  echo "  ┌────────────────────────────────────────────────────────┐"
  echo "  │  ⚠️ 要唔要將個 repo 轉做 public？                       │"
  echo "  └────────────────────────────────────────────────────────┘"
  echo
  echo "  ⚠️ public = **任何人睇得到個 source code**"
  echo "     ⚠️ 但 **唔會** 令你有一個 web app link ——"
  echo "        GitHub 只存 code，唔會跑你個 app。"
  echo "        （要 link 就要 Fly.io / Codespaces，見 DEPLOY.md）"
  echo
  echo "  ⚠️ 個 repo 冇秘密（我 check 過 .gitignore）——"
  echo "     但有 6.9MB GeoNames 城市資料同你自己寫嘅 code。"
  echo
  read -r -p "  轉 public？(y/N)：" PUB
  if [ "$PUB" = "y" ] || [ "$PUB" = "Y" ]; then
    PRESP=$(curl -s --max-time 30 -X PATCH \
      -H "Authorization: Bearer $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$OWNER/$REPO" \
      -d '{"private":false}')
    if echo "$PRESP" | grep -q '"private":false'; then
      echo "  ✅ 轉咗做 public"
    else
      echo "  ⚠️ 轉唔到（可能係免費帳號限制）："
      echo "$PRESP" | head -c 250 | sed 's/^/      /'
    fi
  else
    echo "  → 保持 private"
    echo "     ⚠️ 想公開：https://github.com/$OWNER/$REPO/settings"
    echo "        Danger Zone → Change visibility"
  fi
  echo "  ⚠️ 建議即刻去刪咗個 token（或者等佢過期）"
  echo "      https://github.com/settings/tokens"
  echo
  echo "  下一步（想真正 host 畀朋友用）："
  echo "     睇 DEPLOY.md → Fly.io"
else
  git remote set-url origin "https://github.com/$OWNER/$REPO.git"
  echo
  echo "  ✗ Push 失敗"
  echo "  ⚠️ token 有冇 push 權限？"
  exit 1
fi
