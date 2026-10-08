<div align="center">

# Wander

**旅行計劃 app —— 由貼一條 link 到排好每日行程**

貼一個 Google Maps / Instagram 連結，自動抽出地址同座標，
按地理位置分區、排每日行程、分帳、購物清單、雙時區時鐘。

<br>

[**🌍 即時試用**](https://era-apparently-submitted-language.trycloudflare.com) ·
[功能](#-功能) · [技術](#-技術亮點) · [架構](#-架構) · [快速開始](#-快速開始)

<br>

<table>
<tr>
<td><img src="docs/shots/login.png" width="215" alt="登入"><br><sub>登入</sub></td>
<td><img src="docs/shots/app-home.png" width="215" alt="主畫面"><br><sub>主畫面 + 雙時區時鐘</sub></td>
<td><img src="docs/shots/app-saved.png" width="215" alt="收藏"><br><sub>收藏 + 地名 facet</sub></td>
</tr>
</table>

<sub>⚠️ 上面係由真元件 SSR render 出嚟再截圖（唔係設計稿）</sub>

</div>

---

## ⚡ 一句話

> 一個**冇用任何 AI** 嘅旅行計劃工具：所有解析、分區、時區判斷
> 都係**可預測嘅規則引擎**，1,600+ 個測試守住。

---

## 🎯 功能

| App | 做咩 |
|---|---|
| 🗓 **Planner** | 月曆總覽 + 拖放編排（Pointer Events，手機都拖得）|
| 📥 **Organize** | 貼 link → 自動解析地名、地址、座標、圖片 |
| 💸 **Money** | 分帳（整數 cents 運算，冇浮點誤差）|
| 🛒 **Shopping** | 購物清單 + 相框 |
| 🔖 **Saved** | 收藏瀏覽 + 搜尋 + **由地址自動抽出地名 facet** |
| 🗺 **Map** | Leaflet + OSM，顯示每日路線 |
| 👥 **Friends** | 朋友 + QR code（雙向確認，唔可以加自己）|
| ⚙️ **Settings** | 個人檔案、頭像、主題、教學重播 |

### 特別做得好嘅位

- **雙時區時鐘** —— 本地 + 目的地同時顯示，覆蓋 77 個單時區國家
  + 9 個多時區國家（按東界經度分帶）
- **地名 facet** —— 你 save 咗「博多」，因為地址有「福岡市」，
  就自動出一個 `[福岡市 2]` 嘅 chip 畀你 tick 篩選
- **37 個 16×16 像素頭像** —— 程序化生成，唔係用圖檔
- **離線優先 PWA** —— cache-first shell、network-first 導航、
  LRU 圖磚快取（上限 800 塊）

---

## 🔬 技術亮點

### ① 純規則引擎，零 AI

```
engine/wander/
├── caption.py      標題解析（中文地址、店名、地區詞）
├── localgeo.py     134,655 個地名 + 146 個手動整理區
├── tz.py           時區判斷（國家 → 經度分帶 → Etc/GMT±N）
├── zones.py        Haversine 貪婪分群（確定性，唔隨機）
├── qr.py           自己寫嘅 QR 編碼器（版本 1–20，EC level L）
└── lookup.py       Photon → Nominatim → Overpass 三層 fallback
```

**為咩唔用 LLM**：旅行計劃要**可預測**。同樣嘅輸入要出同樣嘅結果，
而且要**解釋得到**為咩分喺嗰區。規則引擎做得到，LLM 唔得。

### ② 自己寫 QR 編碼器

冇用 `qrcode` 套件 —— 純 Python 實作：
Reed-Solomon 糾錯、遮罩模式選擇、版本自動升級。

```python
# engine/wander/qr.py
def encode(text: str, ec_level: str = "L") -> list[list[int]]:
    """版本 1–20，自動揀最細嘅版本。"""
```

### ③ 程序化像素藝術

```python
# engine/make_avatars.py
# 8×8 字串格 + 調色板 → SVG `shape-rendering="crispEdges"`
AVATAR = P(['#outline', '#main', '#light'], [
    '..1111..',
    '..1221..',
    ...
])
```

### ④ 時間軸同步（整合同測試）

Planner 曾有兩個獨立系統（月曆模式 + 時間格模式）各自寫入
`day_index` / `start_time` → **拖咗時間但顯示唔變**。

修法：**刪走一個模式**，全部用同一個 `place()` 寫入
`{day_index, parsed:{start_time, duration}}`。

### ⑤ 免費服務，零成本

| 用途 | 服務 |
|---|---|
| 地理編碼 | Photon (Komoot) · Nominatim (OSM) |
| 圖磚 | OpenStreetMap |
| 地名資料 | GeoNames（本機 DB，134,655 條）|
| 連結解析 | DuckDuckGo HTML · Open Graph |

---

## 🧪 測試

```
後端   pytest        882 通過
前端   node:test     751 通過（12 個套件）
引擎   selftest       10 通過
─────────────────────────────────
                     1,643
```

**測試捉到嘅真 bug**（唔止係「有測試」）：

| Bug | 測試點捉到 |
|---|---|
| `PixelIcon is not defined` → Planner 白畫面 | 靜態「用咗但冇 import」檢查 |
| `useMemo` 冇 import | 同上（`vite build` **捉唔到**）|
| 密碼欄每次打一個字就失焦 | 「組件唔可以喺 render 內定義」檢查 |
| `eye` 圖示用咗唔存在嘅調色板索引 | 像素圖示索引檢查 |
| `--fg` CSS 變數唔存在（應為 `--text`）| CSS 變數完整性檢查 |
| `$VAR` 後面跟全形括號 → bash `unbound variable` | shell script 掃描 |

> ⚠️ 而且**測試會 match 到自己嘅註解** —— 所以所有原始碼檢查
> 都會先剝走註解。呢個陷阱中過好多次。

---

## 🏗 架構

```
                        ┌──────────────┐
   瀏覽器 (PWA)  ──────▶ │  FastAPI     │
   React 19 + Vite      │  port 8787   │
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ SQLite   │    │ 規則引擎  │    │ 免費 API  │
        │ 單一檔案  │    │ 純 Python │    │ Photon…  │
        └──────────┘    └──────────┘    └──────────┘
```

**單一 port** —— 後端直接 serve 前端 build 出嚟嘅檔案。
冇 CORS、冇 nginx、冇 docker-compose。

```
engine/     10,140 行   解析引擎
web/src/    10,273 行   React 前端
tests/       9,729 行   測試
server/app/  3,550 行   API
────────────────────────────
            34,519 行
```

### 安全

- 密碼：PBKDF2-HMAC-SHA256，**600,000 次迭代**、per-user salt、
  `hmac.compare_digest` 比較
- Session token：`secrets.token_urlsafe`
- 刪帳號：**轉移**擁有權（唔會連累朋友嘅旅程）——
  呢個係實測踩過嘅坑，見 [DEVLOG](DEVLOG.md)

---

## 🚀 快速開始

```bash
git clone https://github.com/Mizuki0215/Wander.git
cd Wander

# 前端 build
cd web && npm install && npm run build && cd ..

# 後端
pip install -r server/requirements.txt
cd server && python -m app
```

開 http://localhost:8787

**或者一鍵**：
```bash
./run.sh
```

### 用手機（HTTPS → PWA）

```bash
./host.sh          # cloudflared quick tunnel
```
→ Safari：分享 → 加到主畫面

⚠️ HTTPS 之下 service worker、相機、剪貼板全部用得
（`http://192.168.x.x` 做唔到）。

---

## 📁 文件

| 檔案 | 內容 |
|---|---|
| [DEPLOY.md](DEPLOY.md) | 部署（Fly.io / Codespaces / Docker）|
| [DEVLOG.md](DEVLOG.md) | 開發日誌 —— 每個 bug 嘅根因同修法 |
| [docs/smtp/](docs/smtp/) | 寄信設定（Gmail App Password 陷阱）|
| [docs/mascot/](docs/mascot/) | 角色圖規格 |

---

<div align="center">

**技術**：Python · FastAPI · SQLite · React 19 · Vite · Leaflet ·
純規則引擎（無 AI）

</div>
