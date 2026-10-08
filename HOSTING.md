# 免費 Host 選擇（要一個 link 畀朋友）

> ⚠️ **重點**：GitHub 只**存 code**，唔會跑你個 app。
> 要一個「撳得入去用」嘅 link，一定要一部**真嘅 server**。

---

## 🎯 你而家已經有嘅

```
✅ cloudflared quick tunnel
   https://known-ideal-arizona-highlight.trycloudflare.com
```
```bash
./host.sh          # 重新起（網址會變）
```

| 好 | 唔好 |
|---|---|
| ✓ 免費、唔使註冊 | ✗ 網址**每次唔同** |
| ✓ HTTPS（PWA / 相機 / QR 都用得）| ✗ **部機瞓覺就冇** |
| ✓ 唔使信用卡 | ✗ 要開住個 script |

---

## 📊 全部選擇（按「使唔使錢」分）

### 🟢 完全免費（唔使信用卡）

| 方法 | 網址 | 會瞓？ | 資料保存 | 難度 |
|---|---|---|---|---|
| **cloudflared quick** | 每次唔同 | 部機瞓就冇 | ✅ 本機 DB | ⭐ |
| **ngrok**（已裝 + 已 authtoken）| 每次唔同 | 部機瞓就冇 | ✅ 本機 DB | ⭐ |

⚠️ **實測 ngrok**：有時成功、有時撞 `ERR_NGROK_802`（免費版 agent 限制）。
   而且第一次喺瀏覽器開會有**警告頁**（要撳「Visit Site」）。
   → 所以 **`./host.sh` 預設用 cloudflared**。

```bash
./host.sh                 # cloudflared（推薦）
./host.sh --ngrok         # ngrok（⚠️ 唔穩定）
```
| **GitHub Codespaces** | `xxx-8787.app.github.dev` | ⚠️ 30 分鐘 | ⚠️ 重開就冇 | ⭐⭐ |
| **Render 免費層** | `xxx.onrender.com` | ⚠️ 15 分鐘 | ❌ **冇 disk → 清空** | ⭐⭐ |
| **Koyeb 免費層** | `xxx.koyeb.app` | ⚠️ 會瞓 | ⚠️ 要 check | ⭐⭐⭐ |
| **Deta / Glitch** | — | — | — | ❌ 已經收咗 |

⚠️ **Codespaces** 其實幾好：
- 免費 60 小時/月
- 係一部**真 Linux VM**（跑得到 Python + SQLite）
- 我已經寫好 `.devcontainer/devcontainer.json`（port 設咗 public）
- ⚠️ 但 30 分鐘冇活動就停 → **朋友撳落去會連唔到**

⚠️ **Render 免費層有個大問題**：冇 persistent disk →
   **每次 deploy / 重啟都清空所有用戶資料**。只適合試用。

### 🟡 免費但要**信用卡**（唔會收錢，但要綁）

| 方法 | 網址 | 會瞓？ | 資料保存 | 難度 |
|---|---|---|---|---|
| **Fly.io** | `wander-mizuki.fly.dev` | ✅ 可設唔瞓 | ✅ volume | ⭐⭐ |

⚠️ Fly.io 而家**新用戶要綁卡**（免費額度內唔收錢）。
✅ 但係**最適合畀朋友用**：固定網址 + 可以設到唔瞓 + volume 保存資料。
→ 我已經寫好 `fly.toml` + `./deploy.sh` + 下載咗 flyctl

### 🔵 要少少錢，但**永久固定網址**（推薦長期用）

| 方法 | 成本 | 網址 | 備註 |
|---|---|---|---|
| **買網域 + cloudflared named tunnel** | 網域 ~US$1-10/年 | `wander.你個名.com` | ⚠️ **唔使 VPS**，你部機行就得 |
| **VPS**（DigitalOcean / Vultr）| US$4-6/月 | 你嘅 | 部機唔瞓 |

⚠️ **named tunnel 係最抵嘅永久方案**：
- 你只需要一個網域（`.xyz` 首年 ~US$1）
- Cloudflare 免費幫你出 HTTPS
- 你部機繼續行個 app（唔使 VPS）
- ⚠️ 但部機瞓覺就冇（同 quick tunnel 一樣）

### ❌ 做唔到嘅

| 方法 | 為咩 |
|---|---|
| **GitHub Pages** | 只 serve 靜態檔，冇後端 |
| **Vercel / Netlify** | 同上（除非改寫做 serverless，但 SQLite 做唔到）|
| **Replit** | 免費層已經冇咗 public port |

---

## 🚀 建議路線

### 想即刻試 → 你而家已經有

```bash
./host.sh
```

### 想畀朋友用（免費，要綁卡）→ Fly.io

```bash
./deploy.sh
```
→ `https://wander-mizuki.fly.dev`（永久）

### 想畀朋友用（完全免費）→ Codespaces

```
1. Push 上 GitHub（./push-to-github.sh）
2. Repo → Code → Codespaces → Create codespace
3. Ports 分頁 → 搵 8787 → 撳 Globe 圖示
4. 開出嚟嘅 URL 就係（⚠️ 記得 set public）
```
⚠️ 30 分鐘瞓 → 朋友撳落去可能要等佢起身（約 10 秒）

### 想長期認真用 → 買網域 + named tunnel

```bash
# ① 買個網域（Cloudflare Registrar 最平，成本價）
# ② 喺 Cloudflare 加個網域
cloudflared tunnel login
cloudflared tunnel create wander
cloudflared tunnel route dns wander wander.你個名.com
cloudflared tunnel run --url http://localhost:8787 wander
```
→ `https://wander.你個名.com`（永久固定，你部機行住就有）

---

## ⚠️ 唔好處：放出街之前一定要做

| 檢查 | 點做 |
|---|---|
| **註冊模式** | `WANDER_SIGNUP_MODE=invite`（唔好 `open`）|
| **Admin email** | 改成你真正嘅 email（唔好 `admin@wander.local`）|
| **`.env` 唔會 commit** | ✅ 已經 gitignore |
| **資料庫備份** | `cp server/wander.db server/backup-$(date +%s).db` |

⚠️ `./host.sh` 會**問你一次**（open 模式會警告）。

---

## 📋 快速對照

```
只想自己試下          → ./host.sh（cloudflared quick）
想畀朋友用、免費       → Codespaces（⚠️ 30 分鐘瞓）
想畀朋友用、穩定       → ./deploy.sh（Fly.io，要綁卡）
想長期認真             → 買網域 + cloudflared named tunnel
想展示 code 做 CV      → GitHub repo（public）+ README 截圖
```
