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

OWNER="${GITHUB_OWNER:-Mizuki0215}"
REPO="${GITHUB_REPO:-Wander}"

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
