# 部署（Host）指南

> **你問嘅**：「用 GitHub host 佢」

---

## ⚠️⚠️ 先講結論：**GitHub Pages 做唔到呢個 app**

GitHub Pages 只serve**靜態檔案**（HTML/CSS/JS）。
你個 app 有：

| 需要 | GitHub Pages |
|---|---|
| Python + FastAPI 後端 | ❌ 唔支援 |
| SQLite 資料庫（讀寫）| ❌ 冇檔案系統 |
| 圖片上傳 / QR 解碼 | ❌ 冇後端 |
| 悄悄話登入 / session | ❌ 冇 |
| 環境變數（`.env`）| ❌ 冇 |

**如果硬要用 Pages**，你只會得到一個「睇得到但乜都做唔到」嘅空殼 ——
所有 API 都會 404。

---

## ✅ GitHub **做得到**嘅方法：Codespaces

GitHub Codespaces 係一部**真嘅 Linux VM**（唔止靜態檔案），
跑得到 Python + SQLite，而且可以開公開 port。

### 用法

```
1. Push 上 GitHub（見下面）
2. Repo → Code → Codespaces → Create codespace on main
3. 等佢裝完（第一次約 3 分鐘）
4. Ports 分頁 → 搵 8787 → 撳個 Globe 圖示 → 開公開網址
```

⚠️ 已經寫好 `.devcontainer/devcontainer.json`，一開就自動：
- 裝 Python + Node
- 裝前後端依賴
- Build 前端
- 開 8787 port（**set 咗 public**）

### ⚠️⚠️ 但 Codespaces 有兩個大問題

| 問題 | 影響 |
|---|---|
| 免費 60 小時/月（2-core）| 用晒就要等月尾 |
| **30 分鐘冇活動就自動停** | ⚠️ 朋友撳落去會**連唔到** |

→ Codespaces 適合「**你自己試 / 開發**」，
  唔適合「**畀朋友長期用**」。

---

## 🚀 真正 host 嘅建議：Fly.io（免費層）

| | Codespaces | **Fly.io** | Render |
|---|---|---|---|
| 免費 | 60h/月 | 3 部細 VM | 750h/月 |
| 會瞓？ | ⚠️ 30 分鐘 | ✅ 可以設唔瞓 | ⚠️ 15 分鐘 |
| 固定網址 | ⚠️ 要 public port | ✅ `xxx.fly.dev` | ✅ |
| 資料保存 | ⚠️ 重開就冇 | ✅ volume | ❌ 免費層冇 disk |
| 適合 | 開發 | **朋友用** | 試用 |

### Fly.io 步驟（我已經寫好 `fly.toml`）

```bash
# 1. 裝 flyctl
brew install flyctl

# 2. 登入
fly auth signup      # 或者 fly auth login

# 3. 改 fly.toml 第一行做你嘅名（全球唯一）
#    app = "wander-CHANGE-ME"  →  app = "wander-icy"

# 4. 建立 volume（⚠️⚠️ 唔做嘅話每次 deploy 清空所有資料）
fly volume create wander_data --size 1

# 5. 設 secret（⚠️ 唔好寫入 fly.toml —— 會 commit）
fly secrets set WANDER_SIGNUP_MODE=invite
fly secrets set WANDER_ADMIN_EMAILS=你@gmail.com

# 6. Deploy
fly deploy
```

⚠️ 之後 `https://wander-icy.fly.dev` 就係你嘅固定網址。

⚠️ 想唔瞓（朋友隨時撳都連到）：
```toml
# fly.toml
min_machines_running = 1      # ⚠️ 會用多啲免費額度
```

---

## 📤 Push 上 GitHub

⚠️⚠️ **`git` repo root 原本係你嘅 home directory**（`/Users/yeetungchan`）——
   唔可以 push 成個 home 上去。我已經喺 workspace 開咗**獨立 repo**。

### 1. 確認冇秘密

```bash
cd "/Users/yeetungchan/Documents/deepseek-harness/default-workspace"

# ⚠️ 呢四個一定要被擋住
git check-ignore server/wander.db server/.env node_modules backup-*.db
```

### 2. 喺 GitHub 開一個**空** repo

⚠️ Repo 名建議：`wander`
⚠️ **唔好** tick「Add README」/「Add .gitignore」（會撞）

### 3. Push

```bash
git add -A
git commit -m "Wander"

# ⚠️ 改做你嘅 GitHub 用戶名
git remote add origin https://github.com/你嘅名/wander.git
git branch -M main
git push -u origin main
```

⚠️ 冇 `gh` CLI（我 check 過你未裝）：
```bash
brew install gh
gh auth login
# 之後可以： gh repo create wander --private --source=. --push
```

---

## ⚠️⚠️⚠️ Push 之前一定要確認

| 檔案 | 有咩 | 擋咗未 |
|---|---|---|
| `server/wander.db` | **真實用戶資料**（email、密碼 hash、旅程）| ✅ `.gitignore` |
| `server/.env` | `WANDER_ADMIN_EMAILS`、SMTP 密碼 | ✅ `.gitignore` |
| `backup-*.db` | 資料庫備份 | ✅ `.gitignore` |
| `engine/wander/data/geocode_cache.json` | 真實查詢紀錄 | ✅ `.gitignore` |
| `node_modules/` | 幾百 MB | ✅ `.gitignore` |

**如果唔小心 push 咗 `.env` 或者 `wander.db`：**
1. 即刻喺 GitHub **刪咗個 repo**（唔係改 commit —— 歷史仲有）
2. **改晒所有密碼**（`.env` 入面嘅）
3. 重新開一個 repo

⚠️ Git 歷史**永久保留** —— 刪 commit 係唔夠嘅。

---

## ⚠️ GitHub Pages 可以做嘅嘢（但唔係你個 app）

如果你**只想展示**（唔要功能）：

```
1. Build 前端：cd web && npm run build
2. 將 web/dist 推去 gh-pages 分支
3. Settings → Pages → Source: gh-pages
```

⚠️ 但咁樣**冇登入、冇資料、冇 API** ——
登入頁撳落去會死。**唔建議。**

---

## 📋 快速對照

```
只想試下            → Codespaces（已設定好）
想畀朋友長期用       → Fly.io（免費層 + volume）
只想試下一個禮拜     → cloudflared quick tunnel（./host.sh）
想展示但唔要功能     → GitHub Pages（⚠️ 冇用）
想自己部機 24/7      → 開住 ./host.sh（部機唔可以瞓）
```

---

## 🔑 一鍵 Push（`push-to-github.sh`）

⚠️ `brew install gh` 喺呢部機**失敗**（`/opt/homebrew/Cellar` 唔可以寫），
   所以用 **Personal Access Token + git** 代替。

### 用法

```bash
cd "/Users/yeetungchan/Documents/deepseek-harness/default-workspace"
./push-to-github.sh
```

⚠️⚠️ **Token 唔會經過對話** —— 用 `read -s`（唔 echo）收，
   token 只用嚟：
- ① 打 GitHub API 建立 repo
- ② push
- 然後**即刻由 remote URL 移除**

### 步驟

```
1. 去 https://github.com/settings/tokens/new?scopes=repo&description=Wander
2. 揀 scope：☑ repo     （就咁一個就夠）
3. 有效期：建議 7 日    （用完即刻刪）
4. 複製個 token（ghp_... 或者 github_pat_...）
5. 跑 ./push-to-github.sh → 貼 token → Enter
```

### 個 script 會做

```
✅ 安全檢查（166 個檔案，0 個秘密）
✅ 收 token（唔 echo）
✅ 建立 repo（如果未有）→ private
✅ push
✅ ⚠️ 清走 remote URL 入面嘅 token
```

⚠️ **實測**：`printf '' | ./push-to-github.sh` → 正確喺安全檢查之後停下
（冇打 token 就唔會亂做嘢）。

### ⚠️ 用完即刻刪 token

```
https://github.com/settings/tokens
```

⚠️ 因為 token 一度出現喺 process 嘅 argv（`git remote add` 嗰下）——
   喺你自己部機冇問題，但用完刪咗最安全。

### 如果 `gh` 裝得到（喺你自己嘅 terminal）

```bash
brew install gh
gh auth login
gh repo create yeetung-work --private --source=. --push
```
