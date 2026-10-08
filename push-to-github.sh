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
#     · repo 名：yeetung-work
#     · 一個 Personal Access Token（classic，要 `repo` scope）
#         https://github.com/settings/tokens/new?scopes=repo

set -euo pipefail

OWNER="${GITHUB_OWNER:-Mizuki0215}"
REPO="${GITHUB_REPO:-yeetung-work}"

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
cat <<'EOF'
  ⚠️ 需要一個 GitHub Personal Access Token：
      https://github.com/settings/tokens/new?scopes=repo&description=Wander

      揀 scope：☑ repo    （就咁一個就夠）
      有效期：   建議 7 日（用完即刻刪）

  ⚠️ Token 只會用嚟建 repo + push，**唔會**經對話或者 log。
EOF
echo
read -r -s -p "  貼 token 然後撳 Enter（唔會顯示）：" TOKEN
echo
echo

if [ -z "$TOKEN" ]; then
  echo "  ✗ 冇打 token"
  exit 1
fi

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
    echo "  ✅ 建立咗 $OWNER/$REPO（private）"
  else
    echo "  ✗ 建立失敗："
    echo "$RESP" | head -c 400 | sed 's/^/      /'
    echo
    echo "  ⚠️ token 有冇 ☑ repo scope？"
    exit 1
  fi
elif [ "$CODE" = "200" ]; then
  echo "  ✅ Repo 已經存在"
else
  echo "  ⚠️ HTTP $CODE —— 檢查 token"
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
