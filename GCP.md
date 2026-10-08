# ☁️ 部署去 Google Cloud（永久免費）

> ⚠️ 為咩要呢個：**旅行 app 就係旅行嗰陣用** —— 嗰時你部電腦喺屋企。
> serveo / cloudflared 要電腦開住，**唔得**。

---

## 💰 成本：**$0/月（永久）**

| | |
|---|---|
| **VM** | 1 × `e2-micro`（永久免費，**唔係 trial**）|
| **RAM** | 1 GB + 2 vCPU（shared）|
| **磁碟** | 30 GB 標準持久磁碟 |
| **24/7** | ✅ 唔會 sleep |
| **要卡** | ⚠️ 要（但唔會收錢）|

> Always Free 包括一部 `e2-micro` VM（`us-west1` / `us-central1` / `us-east1`），
> 連 30 GB 標準持久磁碟。
> — [Google 官方文件](https://docs.cloud.google.com/free/docs/free-cloud-features) · [2026 指南](https://agentdeals.dev/gcp-free-tier-2026)

### ⚠️ 我實測你 app 嘅用量

```
匯入 91 MB（fastapi + numpy + cv2 + scipy）
實際 runtime  ~150–250 MB
GCP e2-micro  1024 MB          ← 綽綽有餘 ✅
```

### ⚠️ 邊度會收錢

| 項目 | 免費額度 | 超出 |
|---|---|---|
| VM | e2-micro × 1 | — |
| 磁碟 | 30 GB pd-standard | $0.04/GB |
| **出流量** | **1 GB/月**（北美）| $0.12/GB |

⚠️ **已自動設 $1 budget alert** —— 一超即刻 email 你。

---

## 🚀 部署（5 分鐘）

### ① 開 Google Cloud account

```
https://console.cloud.google.com/
```
- 用你嘅 Google account 登入
- ⚠️ 要加**信用卡**（免費額度都要 —— 用嚟驗證）
- ⚠️ **唔會收錢**（只要唔超免費額度）

### ② 開一個 project

```
左上角 project 揀選器 → 新增專案 → 名：wander
```

### ③ 開 Cloud Shell

```
右上角有個 `>_` 圖示 —— 撳落去
```

### ④ 貼呢段（一個指令搞掂）

```bash
curl -fsSL https://raw.githubusercontent.com/Mizuki0215/WANDER/main/deploy-gcp.sh | bash
```

⚠️ 或者想睇下先：
```bash
git clone https://github.com/Mizuki0215/WANDER.git
cd WANDER
./deploy-gcp.sh
```

### ⑤ 等 3–5 分鐘

```
⚠️ VM 喺度裝 Python、build 前端、攞 HTTPS 證書
```

**睇進度：**
```bash
gcloud compute ssh wander --zone=us-central1-a \
  --command='sudo tail -f /var/log/wander-setup.log'
```

### ⑥ 完成！

```
🌐 https://<你嘅IP>.sslip.io
```

⚠️ **`sslip.io`** 係免費 wildcard DNS —— `<IP>.sslip.io` 自動解析去嗰個 IP，
所以**唔使買 domain**，Caddy 又可以自動攞 Let's Encrypt 證書。

---

## 📱 加到主畫面（PWA）

```
① Safari 開 https://<你嘅IP>.sslip.io
② 分享 → 加到主畫面
③ ⚠️ 呢個網址**永遠唔變**（靜態 IP）
```

---

## 🔧 日常操作

### 睇 app log
```bash
gcloud compute ssh wander --zone=us-central1-a \
  --command='sudo journalctl -u wander -f'
```

### 更新 code
```bash
gcloud compute ssh wander --zone=us-central1-a --command='
  cd /opt/wander && sudo git pull && sudo systemctl restart wander'
```

### 重新 build 前端
```bash
gcloud compute ssh wander --zone=us-central1-a --command='
  cd /opt/wander/web && sudo npm ci && sudo npm run build &&
  sudo systemctl restart wander'
```

### ⚠️ 備份你嘅資料（重要！）
```bash
gcloud compute ssh wander --zone=us-central1-a \
  --command='sudo tar czf - /var/lib/wander' > wander-backup-$(date +%F).tgz
```

### 💰 唔用嗰陣停 VM（唔收錢，資料留住）
```bash
gcloud compute instances stop wander --zone=us-central1-a
gcloud compute instances start wander --zone=us-central1-a
```

---

## ⚠️ 常見問題

### 「開唔到 HTTPS」
```
⚠️ 等 5 分鐘（Caddy 攞證書要時間）
⚠️ 確認 DNS：nslookup <IP>.sslip.io
⚠️ 確認 80/443 開咗：gcloud compute firewall-rules list
```

### 「話 capacity 唔夠」
```
⚠️ e2-micro 喺 us-central1 好搶手
✅ 換 us-west1 或者 us-east1：
   WANDER_ZONE=us-west1-a ./deploy-gcp.sh
```

### 「收到 Google 話要收錢」
```
⚠️ 睇下邊樣超額：
   https://console.cloud.google.com/billing
✅ 通常係出流量 —— 減少載入大圖
```

### 「app 冇咗資料」
```
🚨 檢查 WANDER_DB 係唔係 /var/lib/wander/wander.db
   （唔係嘅話放咗喺 repo 入面 → git pull 會撞）
```

---

## 🆚 為咩唔用其他

| 方案 | 唔得嘅原因 |
|---|---|
| **serveo / cloudflared** | ⚠️ 要你部電腦開住 —— 旅行時唔得 |
| **Fly.io** | ⚠️ 2024-10-07 取消免費 tier，US$3.44/月 |
| **Render** | ⚠️ 免費版**冇持久磁碟** → SQLite 每次重啟清空 |
| **Koyeb** | ⚠️ 2026-02 起要卡 + $29 hold，而且免費版**冇 volume** |
| **GitHub Pages** | ❌ 只做靜態檔（冇 Python）|
| **Codespaces** | ⚠️ 60 鐘/月（差 12 倍）|
| **Oracle Free** | ⚠️ 12 GB RAM 好吸引，但好常「out of capacity」開唔到 |

---

## 📄 一鍵 script 做咩

`deploy-gcp.sh` 會：

1. ✅ 檢查 `gcloud` + billing
2. ✅ 開 Compute API
3. ✅ **保留靜態 IP**（重要！唔係重開機就換）
4. ✅ 開防火牆 22/80/443
5. ✅ 建 `e2-micro` VM（us-central1、30GB pd-standard）
6. ✅ 喺 VM 入面（startup script）：
   - 裝 Python + Caddy + Node
   - `git clone` 你嘅 repo
   - `pip install` + `npm run build`
   - 建 systemd service（**重開機自動起**）
   - 設 Caddy 自動 HTTPS
7. ✅ 設 **$1 budget alert**
8. ✅ 印出所有日常指令

⚠️ Startup script 係 **idempotent** —— 再跑唔會爆，可以安全重複。
