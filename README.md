# Wander

## 🌍 而家已經上線

```
https://era-apparently-submitted-language.trycloudflare.com
```

⚠️ 呢個係 **cloudflared quick tunnel** —— **臨時**嘅，一閂就冇。
下次跑 `./host.sh` 會出**另一個**網址。

### 一鍵上線

```bash
./host.sh
```

⚠️⚠️ 佢會喺起 tunnel **之前**問你安全選項：

```
⚠️⚠️⚠️  注意  ⚠️⚠️⚠️

你而家係 **open** 模式 —— 註冊只需要 email + 密碼。
一旦放出街，**任何知你網址嘅人都可以註冊**，
而且可以用**任何 email**（包括你朋友嘅）。

  1) 改成 invite 模式（要邀請碼）——  推薦
  2) 照用 open（我知風險）
  3) 唔 host 住，取消
```

⚠️ `open` 模式 + 公開網址 = **冇任何門檻**。
   純內網冇問題，放出街就要考慮。

### 實測（經公開網址）

```
✓ 首頁 200 · HTTPS
✓ manifest 200 · service worker 200
✓ icon-512 200 · 星雲背景 200 · 角色圖 200
✓ 註冊（email+密碼）200
✓ 建立旅程 200
✓ 加城市（要 geocode）200  → 時區 Asia/Tokyo
✓ QR code → 用公開網址（朋友掃到）
15 通過 / 0 失敗
```

⚠️ HTTPS 之下：PWA 安裝、離線、相機、QR 掃描**全部用得**
（LAN 嘅 `http://192.168.x.x` 做唔到）。

### ⚠️ 想永久 host（唔係臨時 URL）

| 方法 | 成本 | 網址 | 適合 |
|---|---|---|---|
| **cloudflared quick tunnel** | 免費 | 每次唔同 | 試用 |
| **cloudflared named tunnel** | 免費（要 Cloudflare 帳號 + 網域）| 固定 | 認真用 |
| **ngrok**（已裝）| 免費版有警告頁 | 每次唔同 | 試用 |
| **VPS**（Fly.io / Railway / Render）| 免費層 | 固定 | 長期 |
| **自己部機 + 固定 IP** | 電費 | 固定 | 進階 |

⚠️ 但記住：**部機一瞓覺，個 app 就冇**。
   要真正 24/7 就要 VPS（或者唔瞓嘅機）。
 — 旅行規劃 Web App

由 IG / 小紅書 / Google Maps link，一鍵變成**可協作嘅行程表**。

```
IG / 小紅書 caption            Google Maps link
        ↓                            ↓
   文字解析引擎                  結構解析（店名＋精確座標）
        └────────────┬───────────────┘
                     ↓
          座標反查 → 搜尋補完 → 統一 Item
                     ↓
        帳號 · Group · 地圖 pin · 拖拽行程表
```

## 快速開始

```bash
cd "/Users/yeetungchan/Documents/deepseek-harness/default-workspace"
./run.sh
```

然後開 <http://127.0.0.1:8787>

**手機用**：連同一個 WiFi，開 server console 印出嘅區網 URL
（例如 `http://192.168.1.23:8787`）。加到主畫面就同 App 一樣。

> ⚠️ **登入驗證碼會印喺 server console**（開發模式，唔使設定 SMTP）。
> 前端亦會自動填入。

## 功能

| 畫面 | 做到啲乜 |
|---|---|
| **登入** | Email 驗證碼（冇密碼），自動註冊 |
| **我嘅旅程** | 開多個 trip、編輯日期／日數、邀請碼加入、倒數、刪除 |
| **收藏** | 貼 link 或 caption → 解析 → 自動分類；🔍 搜尋 + 排序（最新／最多票／信心／名稱） |
| **月曆** | ⭐ 三個模式：**總覽**（真實日期＋城市色帶）／**逐日編排**（拖拽）／**時段格**（時間表） |
| **城市規劃** | ⭐ 多城市（福岡 4 日 → 首爾 3 日），自動計日數、衝突偵測 |
| **地圖** | ⭐ 自動定位去你設定嘅城市；城市標記 + 景點 pin（Leaflet + OSM，免費免 key） |
| **朋友** | ⭐ 加朋友要**對方 accept**；行程邀請都要 accept；invite link 即刻加入 |
| **設定** | 6 個 theme、改顯示名、登出 |

### 月曆細節

```
8/12（星期四）  DAY 1    3 個   ← 撳即入逐日編排
  01  波止場食堂 レストハウス店
  02  プルトゥンヌンテジ 풀뜯는돼지
8/13（星期五）  DAY 2    0 個
8/14（星期六）  DAY 3    1 個
```

· 有 `start_date` 就自動計日數、顯示真實星期
· 改日期會自動同步 `end_date`，唔會唔一致
· 撳「±1 日」即改行程長短
· 拖拽支援：日數掣、時間軸、卡片之間插入
· 手機上可以撳「入 Day N」代替拖拽

### 收藏詳情（撳卡片開啟）

· 補名稱 → **自動用搜尋補完座標／電話／地址**
· 改分類 / 改地區
· 一撳排入任何一日
· 顯示完整資料（郵便番号、營業時間、價錢、標籤、備註）

## 架構

```
engine/         解析引擎（純 Python，唔關 web 事）
  wander/
    caption.py  文字解析（rule-based）
    links.py    URL 分類 + Google Maps 解析
    fetch.py    抓網頁（JSON-LD / og / oEmbed）
    lookup.py   由店名反查（Photon + DuckDuckGo + Nominatim）
    lexicon.py  地名詞典（18 群組）
server/         FastAPI 後端（SQLite，零安裝）
  app/
    main.py     API（auth / trips / items / parse）
    db.py       Schema + DB 存取
web/            React + Vite 前端
  src/
    App.jsx     主程式 + 底部 nav
    components/ Login / Trips / Discover / MapView / Plan / Friends / Settings
    styles.css  Theme 系統（6 個風格，純 CSS 變數）
tests/          解析引擎測試（110 個）
design/         早期 UI 原型（HTML）
```

## 一個 port 搞定

FastAPI 同時 serve API 同前端 build 出嘅檔案 →
**冇 CORS 問題，手機連同一個 WiFi 就用得。**

## 全部用免費服務（零成本）

| 功能 | 服務 |
|---|---|
| 地圖圖磚 | OpenStreetMap |
| 地圖庫 | Leaflet |
| 地名搜尋 | Photon (komoot) |
| 座標反查 | Nominatim |
| 搵高質來源 | DuckDuckGo HTML |
| 資料庫 | SQLite（標準庫） |
| **AI** | **完全冇用** |

## 測試

```bash
./wander.sh selftest                  # 引擎自我測試 10/10
python -m pytest tests                # 101 個引擎測試（唔使上網）
python -m pytest tests -m network     # 9 個要上網嘅測試
node tests/web/sw.test.mjs            # 20 個 service worker 測試（離線策略）
node tests/web/stops.test.mjs         # 31 個多城市／過渡日測試
node tests/web/bookmarklet.test.mjs   # 27 個書籤小工具 payload 測試
node tests/web/bookmarklet-dom.test.mjs  # 28 個 jsdom 真實 DOM 測試
python -m pytest tests/test_zones.py     # 分區演算法測試
python -m pytest tests/test_settle.py    # 分帳測試
python -m pytest tests/test_qr.py        # 41 個 QR 測試（含 OpenCV 真解碼）
python -m pytest tests/test_avatars.py   # 像素頭像結構驗證
python -m pytest tests/test_password.py  # 密碼雜湊
python -m pytest tests/test_nearby.py    # 附近店鋪
node tests/web/ssr.test.mjs              # 31 個真 SSR render 測試
node tests/web/render.test.mjs           # 31 個元件內容測試
python -m pytest tests/test_localgeo.py   # 51 個本地城市庫測試（含同名地方校正）
```

## 🎨 吉祥物（A 方案：用戶自備圖）

**用戶問**：「A …定係你搵人生成？」

### ⚠️ 老實講：**我生成唔到圖**

我冇圖像生成能力 —— 只可以寫程式畫。
亦都冇辦法「搵人」（我冇辦法請人）。

**但我可以做三件事令你 5 分鐘搞完：**

1. ✅ 寫好**提示詞**（直接複製去 ChatGPT / Midjourney 就用得）
2. ✅ 寫好**規格 + 檢查器**（放圖之前跑一次，唔啱即刻知）
3. ✅ 寫好**自動 fallback**（你唔放都得，放咗自動用你嗰個）

### 兩層檔案（唔會互相覆蓋）

```
web/public/mascot-hello.png        ← 你生成（可選）
web/public/mascot-point.png
web/public/mascot-happy.png
web/public/mascot-oh.png

web/public/proc/mascot-hello.png   ← 我程序化畫（fallback，一定有）
web/public/proc/mascot-point.png
...
```

```jsx
<img src={`/mascot-${frame}.png`}
  onError={(e) => {
    if (e.currentTarget.dataset.fb) return      // ⚠️ 防無限迴圈
    e.currentTarget.dataset.fb = '1'
    e.currentTarget.src = `/proc/mascot-${frame}.png`
  }} />
```

⚠️ 用 `onError` 而唔係 build 時判斷 ——
因為你可以**隨時**放圖入 `public/`，唔使重新 build。

### 檢查器（放圖之前跑）

```bash
cd engine && python check_mascot.py
```

會捉到 AI 生成最常見嘅問題：

| 問題 | 為咩要捉 |
|---|---|
| 冇透明通道 | 「透明背景」唔一定真係透明 → 縮細變一嚿色 |
| 大細唔夠（<300×400） | 縮到 90px 會糊 |
| 主角佔畫面 < 8% | 縮到 90px 變一粒塵 |
| 主角離底邊 > 25% | 縮細之後會「浮」 |
| 四隻角同一個實色 | 去背失敗 |

實測：餵已知壞圖 → **✓ 全部捉到**

```bash
python check_mascot.py --fix    # 順便自動去背（純色背景）
```

⚠️ `--fix` 只處理**純色**背景。漸變／圖案要去 [remove.bg](https://remove.bg)。

### 提示詞同規格

📄 **`docs/mascot/README.md`** —— 有齊：
- 4 個 frame 嘅英文提示詞（直接複製）
- 規格（PNG / 透明 / ≥300×400 / 唔要文字）
- 用邊個工具（ChatGPT / Midjourney / SD / Firefly）

## 🖱️ 所有 Button 都要撳得（真 DOM 測試）

**用戶要求**：
> 「你要確保所有嘅 button，都係可以撳完之後可以去到其他嘅頁面。」

### ⚠️⚠️ 呢個測試捉到一個**白畫面級**嘅 bug

```
Calendar.jsx 用咗 <PixelIcon>，但 import 從來冇加到
→ 撳 Planner 直接 ReferenceError: PixelIcon is not defined
→ React unmount 成棵樹 → 白畫面
```

**⚠️ 點解 `vite build` 捉唔到**：
esbuild 見到 `<PixelIcon>` 只當佢係一個**未定義嘅變數**，
而 JS 嘅未定義變數係**合法**嘅（runtime 先拋）→ build 通過。

**⚠️ 呢個同「`api.myQr` 冇定義」係同一類 bug**：
呼叫方寫咗，定義方冇 → 只有 runtime 先爆。

### 測試做四件事

```js
① 每個 app icon    撳完要開到對應嘅 app（9 個）
② 底部 nav         每一格撳完要轉頁（7 格）
③ 每頁嘅返回掣      撳完要返到主畫面（9 個 app）
④ 未揀旅程撳 app   要有反應（提示揀旅程，唔可以係死掣）
```

實測：**32 個全部通過**

### ⚠️ 測試教訓：reference 會失效

```js
// ❌ 錯：先收集 button，再逐個撳
const btns = [...nav.querySelectorAll('button')]
for (const b of btns) await click(b)     // 撳「主畫面」之後 nav 消失
                                          // → 之後嘅 b 變 detached，撳咩都冇反應

// ✅ 啱：每次重新 query
for (const label of labels) {
  const b = [...document.querySelectorAll('.nav button')].find(...)
  await click(b)
}
```

### ⚠️ 要分清楚「死掣」同「正確嘅冇反應」

| 情況 | 判斷 |
|---|---|
| 撳 Planner 但冇揀旅程 | ✅ **唔係死掣** —— 有 toast + 跳去旅程頁 |
| 撳**正在顯示**嘅 tab | ✅ 正常 —— tab 唔會「重新載入」 |
| 撳完完全冇任何變化 | ❌ 死掣 |

### 加咗**靜態檢查**（唔使等 runtime）

```js
// 對每個檔案：JSX 用到嘅大寫標籤 → 一定要有 import 或者本地定義
for (const m of code.matchAll(/<([A-Z]\w*)[\s/>]/g)) used.add(m[1])
const missing = [...used].filter(n => !imported.has(n) && !local.has(n))
```

驗證：移除 `Calendar.jsx` 嘅 import → **✓ 捉到**
```
✗ components/Calendar.jsx —— 用咗但冇 import：PixelIcon
```

**40 個檔案全部通過。**

## 🔖 Zones → Saved（收藏）

**用戶原話：**
> 「Zones 嘅 function 你唔好寫 Zone，寫 **Saved**。
>  入面有一個 list 寫係你 saved 嘅景，仲可以上面有一個
>  bar for searching —— 有啲 search 字 like：如果有 saved
>  博多景，因為本身 address 有，佢會 show **福岡**畀你 tick。」

### ⚠️ 為咩要「由地址抽出地名 facet」

| 情況 | 冇 facet | 有 facet |
|---|---|---|
| 用戶唔記得景點名 | 打「福」可能中「福砂屋」又可能中「福岡」| tick「福岡市」→ **精確** |
| 想睇「博多區有咩」 | 要自己識打「博多区」| chip 已經列出 |
| 唔知有咩地名 | 冇提示 | 列出所有**出現過**嘅地名 + 數量 |

### 點運作

```js
// ⚠️ facet 由 `location_path` 抽（貼 link 嗰陣解析器已經拆好）
//    博多嘅 location_path = ['福岡県','福岡市','博多区']
//    → 三個地名各 +1
const facets = useMemo(() => {
  const count = new Map()
  for (const it of items) {
    const names = new Set()        // ⚠️ 去重：同景點唔加兩次
    for (const p of (it.location_path || [])) { ... }
    for (const k of ['city','district','country']) { ... }
    for (const n of names) count.set(n, (count.get(n) || 0) + 1)
  }
  return [...count.entries()]
    .sort((a, b) => b.n - a.n)     // 最多嘢嗰區排最前
    .slice(0, 24)                  // ⚠️ 上限 —— 再多就逼爆畫面
}, [items])
```

⚠️ 篩選要**中晒所有 tick 咗嘅地名**（`picked.every`）——
唔係嘅話 tick 兩個會變成「是但中一個」（OR），同用戶預期相反。

### ⚠️ 唔係「分區規劃」

分區排行程已經搬入 **Planner 嘅「編排」**。
呢度係「**睇返／搵返你收藏咗嘅嘢**」。

---

## 🗑️ 刪走 Trips app

**用戶原話：**「Trips（同主頁重疊 70%）delete」

| 之前 | 而家 |
|---|---|
| 主頁面有「轉旅程」+ Trips app | 只剩主頁面 |
| nav 有「旅程」tab | nav 用「主畫面」代替 |
| `TRIP_APPS` 9 個 app | 8 個 |

⚠️ 但 **`Trips.jsx` 冇刪** —— 佢仲負責
「＋ 開新旅程 / 編輯 / 加入（by code） / 退出」，
只係**冇咗 app icon**（由主頁面嘅「＋ 開新旅程」入去）。

---

## ✅ 而家嘅註冊：淨係 email + 密碼（唔驗證）

**用戶最後決定：**
> 「唔[搞]本[身]了，only email password no verify」

```bash
# server/.env
WANDER_SIGNUP_MODE=open
```

| | 之前 | 而家 |
|---|---|---|
| 註冊要 | 邀請碼（或者 email 驗證碼）| **淨係 email + 密碼** |
| 前端顯示 | 邀請碼窄欄 + 「驗證」掣 | **冇**（唔好煩用戶）|
| 打錯密碼 | ~~「登入已過期」~~ | ✅「Email 或密碼唔啱」|

實測：
```
① 註冊模式 → mode=open  need_invite=False  mail=False   ✅
② 註冊（只填 email + password）→ 200 ✅
③ 登入 → 200 ✅
```

### ⚠️ 但你要知呢個嘅代價

| 情境 | 風險 |
|---|---|
| 純內網（192.168.x.x）| ✅ 冇問題 |
| **cloudflared 放出街** | ⚠️ **任何知你網址嘅人都可以註冊** |

⚠️ 冇 email 驗證 = 有人可以打**你朋友嘅 email** 註冊。
⚠️ 冇邀請碼 = 冇得控制邊個入到嚟。

### ⚠️ 但安全網仲喺度（隱形）

就算前端唔顯示邀請碼，**後端照樣接受**：

```python
invite_ok = False
if code:                      # ← 唔睇 mode
    ...
if mode == "invite" and not invite_ok:
    raise ...
```

→ 將來想收緊，只要改 `.env` 做 `WANDER_SIGNUP_MODE=invite`
   然後喺後台產生邀請碼就得（**唔使改 code**）。

### ⚠️ SMTP 憑證已清走

你之前貼嘅（11 個字，唔係 App Password）已經**由 `.env` 刪除**。
如果想將來再搞：

```bash
python tools/setup_mail.py --doctor    # 診斷
python tools/setup_mail.py             # 重新設定
```

## 📧 真 email（歡迎信 + 測試掣）

**用戶原話：**
> 「我係真係想我 email 收到有呢一封嘅 email。」

### ⚠️ 我冇你嘅 email 憑證 —— 但我做咗個工具

⚠️⚠️ **唔好喺 chat 打密碼** —— 佢會留喺對話紀錄。
App Password 等同你 Gmail 嘅**發信權**。

✅ 用呢個工具，密碼只由你嘅鍵盤寫入 `server/.env`：

```bash
cd server
python tools/setup_mail.py
```

```
  1. Gmail App Password       500 封/日
     Google 帳號要開咗兩步驗證
     https://myaccount.google.com/apppasswords
  2. Resend                   100 封/日
     ⚠️ 未驗證網域之下只可以寄去你自己
     https://resend.com/api-keys
  3. Brevo（可以寄去任何人）   300 封/日
     https://app.brevo.com → SMTP & API

  揀邊個？(1/2/3)：
```

工具會做：
- ✅ 用 `getpass`（**唔 echo**）收密碼
- ✅ 自動刪走 App Password 嘅空格（Google 顯示嗰陣有）
- ✅ **保留** `.env` 其他設定（例如 `WANDER_ADMIN_EMAILS`）
- ✅ 設 `.env` 權限 `600`（只有你讀得到）
- ✅ `--show` 只顯示「已設定，16 字」——**唔會印密碼**

然後：
```bash
python tools/setup_mail.py --test 你@gmail.com   # 即刻試寄
python tools/setup_mail.py --show                 # 睇狀態
```

⚠️ **改咗 `.env` 一定要重啟 server 先生效。**

### ⚠️⚠️ 最常見嘅坑：`SMTPServerDisconnected`

```
✗ 寄唔到：SMTPServerDisconnected: Connection unexpectedly closed
```

⚠️⚠️ **呢個錯誤訊息完全誤導** —— 睇落似「網絡問題」，
其實係「**憑證唔啱**」。Gmail 收到錯嘅 App Password
**唔會講「密碼錯」**，佢直接切斷連線（防止暴力破解）。

**原因幾乎一定係：App Password 唔係 16 個字**

```
✗ 你貼咗 Gmail 登入密碼（長度唔定）
✓ App Password 一定係 16 個（純英數）
```

診斷（**分層測，話你邊一步死**）：
```bash
python tools/setup_mail.py --doctor
```
```
② 連線 smtp.gmail.com:587
   ✓ TCP 連得到（唔關網絡事）      ← 證明唔關網絡事
③ STARTTLS   ✓
④ 登入       ✗ Server 切斷連線
```

⚠️ 而家工具會**硬性拒絕**非 16 字嘅密碼 ——
實測就係因為嗰個「照用？(y/N)」令人中招。

### ⚠️⚠️ 順手補咗一個大坑：SMTP 設定錯 = 冇人註冊到

```
管理員設定咗 SMTP 但打錯 App Password
  → signup_mode() 見到「有設定」→ 變 'email'
  → 但驗證碼**寄唔到**
  → ⚠️ **所有人都註冊唔到**，包括管理員自己
```

⚠️ 原因：`signup_mode()` 只睇「**有冇設定**」，
   唔會知「**寄唔寄得到**」（唯一知道嘅方法就係真寄一封）。

**✅ 修法：邀請碼喺所有模式都接受** ——

```python
# ⚠️ 唔再係 `if mode == "invite":` 包住成個檢查
invite_ok = False
if code:                      # ← 唔睇 mode
    inv = 查邀請碼
    if 有效: invite_ok = True

if mode == "invite" and not invite_ok:
    raise HTTPException(403, "呢個 app 要邀請碼先註冊得到")
```

→ 管理員**永遠**可以用「開發版後台 → 產生邀請碼」解鎖。
前端都跟住：邀請碼欄喺**所有模式**都出。

### 已經做好嘅嘢

```python
# ⚠️ 註冊完自動寄歡迎信
try:
    _wr = send_welcome_email(email, email.split("@")[0])
except Exception as _e:
    print(f"⚠️ 歡迎信例外：{_e}")   # ⚠️ 寄唔到唔可以令註冊失敗
```

⚠️ **一定要喺 `with db.connect()` 之外寄** ——
寄信要幾百 ms，唔好霸住個 DB connection。

新增 endpoint：
```
GET  /api/admin/mail         → 寄信狀態（含 from / to，⚠️ 唔含密碼）
POST /api/admin/test-mail    → 寄測試信（admin）
```

## 🔑 邀請碼：窄欄 + 「驗證」掣

**用戶原話：**
> 「你真係要搞邀請碼個位，應該係一欄 —— 寫邀請碼嗰欄
>  應該係**冇咁闊**，然後旁邊落返一個掣叫做**『驗證』**。」

### 之前 vs 而家

```
之前：成行闊嘅輸入框，下面一堆字
      ┌──────────────────────────────────┐
      │        邀請碼（6 個字）            │
      └──────────────────────────────────┘
      🔑 呢個 app 要邀請碼先註冊得到（未設定 SMTP…）
      …跟住先填 email + 密碼 + 確認密碼

而家：窄欄 + 掣，而且係**最前面**
      ⚠️ 用戶要求次序：email → 驗證 → password → password again
      [you@example.com]
      ┌──────────┐ ┌──────────────────┐
      │  KVWHW2  │ │      驗證         │
      └──────────┘ └──────────────────┘
      ✓ 邀請碼有效（阿明）—— 可以繼續註冊
      [密碼]
      [再打一次]
```

### ⚠️ 為咩要「窄」同「先驗證」

| 問題 | 為咩 |
|---|---|
| 成行闊 | 6 個字用成行 → 睇落似「要打好多嘢」，嚇親人 |
| 掣喺好遠 | 視線要由左掃到右先撳到 → 手機一隻手好難 |
| 冇獨立驗證 | 打錯一個字要填晒 email + 密碼 + 確認密碼**先知錯** → 好蝕 |

### 修法

```css
.invite-input {
  flex: 0 0 auto;          /* ⚠️ 唔可以 flex:1 —— 會撐到滿 */
  width: 132px;            /* 6 個字 × 字距 ≈ 118px */
  letter-spacing: 4px;
}
.invite-btn { flex: 1; }   /* ⚠️ 掣食剩低嘅位 → 大手位好撳 */
@media (max-width: 360px) { .invite-input { width: 112px } }
```

**後端**：`POST /api/auth/check-invite`（公開 endpoint）

```python
@app.post("/api/auth/check-invite")
def check_invite(body: InviteCheck) -> dict:
    """⚠️ 只回「有效／唔有效」+ 備註 ——
       唔可以洩漏「邊個產生」（否則可以追查人際關係）。"""
```

實測：
```
✓ KVWHW2   → 有效（阿明）
✓ kvwhw2   → 有效（大細階唔敏感）
✗ ZZZZZZ   → 冇呢個邀請碼
✗ (空)     → 請輸入邀請碼
✗ ab       → 邀請碼格式唔啱
✗ KVWHW2   → 呢個邀請碼已經用咗   ← 用咗之後即刻失效
回傳欄位: ['reason', 'valid']      ← 冇 created_by ✓
```

### ⚠️ 實作陷阱

| 陷阱 | 為咩 |
|---|---|
| 掣要 `type="button"` | 喺 `<form>` 入面，預設 type 會**提交表單**（用未填完嘅資料註冊）|
| 改咗碼要 `setInviteChk(null)` | 唔係嘅話會沿用舊結果 → 「✓ 有效」但其實打錯咗 |
| 冇輸入就 disable 掣 | 唔好俾人撳一個一定失敗嘅掣 |
| Enter 都要驗證 | 桌面用戶打完自然撳 Enter |

## 🎓 重看教學跳過「改名」

**用戶原話：**
> 「因為你係第一次創建呢個 Account 嘅時候，你先至叫你去改名。
>  所以之後呢…喺 setting 嗰度如果你再想睇多次嗰個示範教學，
>  係唔需要再 show 多次叫你去打自己個名嘅嗰一版。
>  **淨係教佢啲 Apps 點用就 OK。**」

### 之前 vs 而家

```
之前（第一次同重看都一樣）
  歡迎 → Planner → … → 改名 ← ⚠️ 重看都叫你打名 → 完成
                          （個名明明已經有！）

而家
  第一次：歡迎 → Planner → … → 改名 → 完成
  重看：         Planner → … →          完成 ✓
                 （跳走歡迎同改名）
```

### ⚠️⚠️ 順便重構：索引算術 → 明確步驟清單

```js
// ❌ 舊：一改步驟數就要改好多處
const NAME_STEP = TOUR.length + 1
const DONE_STEP = TOUR.length + 2
const total = TOUR.length + 3
// …同埋每個條件都要寫 `step < NAME_STEP`

// ✅ 新：清單 + kind 判斷
const steps = useMemo(() => {
  const out = []
  if (!replay) out.push('welcome')
  TOUR.forEach((_, i) => out.push(`tour:${i}`))
  if (!replay) out.push('name')      // ← 呢一行就係用戶要嘅嘢
  out.push('done')
  return out
}, [replay])

const kind = steps[Math.min(step, total - 1)]
const isWelcome = kind === 'welcome'
const isTour    = kind.startsWith('tour')
const isName    = kind === 'name'
const isDone    = kind === 'done'
```

**`total` 自動跟** —— 唔使再手動維護。

### ⚠️ 兩個陷阱

**① 重看完成時**唔可以**再叫 `finishOnboard`**
```js
if (replay) { onDone?.(name.trim()); return }   // ← 直接閂 overlay
```
唔係嘅話會用**輸入框嘅舊值**蓋返用戶喺設定改過嘅名。

**② 「跳過教學」掣要跟住變**
```js
setStep(steps.findIndex(k => k === 'name' || k === 'done'))
// replay 時搵唔到 'name' → 自動去 'done' ✓
```

### 測試守住（21 個）

```
✓ 第一次有 welcome + name
✓ 重看冇 welcome
✓ 重看冇 name ← 用戶要求
✓ 重看仲有全部 app 導覽（冇少到）
✓ render 用 isName 而唔係 step === NAME_STEP
✓ replay 完成唔寫名
```

⚠️ 而且 `dom.test.mjs` 嗰個測試**本身就行緊重看流程**
（`onboarded: true` + 撳「重新播放教學」）——
改完之後即刻變成「⚠️ 重看冇改名步 ← 用戶要求」✓

## 🗓️ Planner 合併（用戶要求 ①）

**用戶原話：**
> 「三個 function 都要同步更新活動時間」
> 「擺活動上去 + 將活動拖去唔同時間 —— 呢兩個 combine 埋一個，
>  即係你將啲活動擺喺最下低嘅，然後可以直接拖上去 timeslot 度改時間」

### ⚠️⚠️ 捉到「唔同步」嘅根因

```
DayGrid（時段格）  寫入  parsed.start_time + duration    ✅
Calendar day mode  只寫  day_index + sort_order         ❌ 完全冇寫時間！
```

→ 喺「逐日編排」拖完，去「時段格」睇 → **時間冇變**。
（`buildTimeline` 讀 `start_time`，但 day mode 從來冇設過 → 永遠當「自動接落去」）

### 修法：3 個 view → 2 個，時間只有一個寫入點

| 之前 | 而家 |
|---|---|
| 總覽 / **逐日編排** / 時段格 | **總覽 / 編排** |
| day mode 用 HTML5 DnD（⚠️ **手機完全用唔到**）| 刪走 |
| day mode 唔寫 `start_time` | 刪走 |
| 加活動（彈層揀）+ 拖時間（拖 block）分開 | **合併** |

### ⚠️ 為咩 HTML5 Drag & Drop 一定要刪

```
day mode:  draggable + onDragStart  → 桌面 work、手機**完全唔 work**
DayGrid:   Pointer Events           → 桌面 + 手機都 work
```

手機用戶根本拖唔到 —— 但 UI 仲寫住「💡 桌面：直接拖。手機：長按再拖」
**呢個係假承諾**（手機長按只會彈系統選單）。

### 合併後嘅操作

```
┌─ 時段格 ────────────────────┐
│ 08:00  ┌──────────────┐     │
│ 09:00  │ 🍜 一蘭拉麵   │     │  ← 拖 block = 改開始時間
│ 10:00  └──────────────┘     │     拖底部橫線 = 改時長
│ 11:00  ╭ ─ ─ ─ ─ ─ ─ ─╮    │  ← 拖托盤上嚟時嘅**鬼影**
│ 12:00  ╰ ─ ─ ─ ─ ─ ─ ─╯    │
└─────────────────────────────┘
  未排入行程 · 3     拖上格 → 排時間
  ┌────────┐ ┌────────┐
  │ 🏛 太宰府│ │ 🛍 天神  │   ← 拖呢度上格 = 直接排時間
  └────────┘ └────────┘
```

⚠️ **兩種操作都保留**：
- **拖**上格 → 自己揀時間（Pointer Events，手機都用得）
- **撳** → 開彈層揀時長（手機單手用，唔使拖）

> ⚠️ 唔可以淨係靠拖 —— 手機拖落一個 62px 高嘅格好易失手。

### ⚠️ 實作陷阱

| 陷阱 | 為咩 |
|---|---|
| 唔可以用 `setPointerCapture` | 一格住 pointer，`pointermove` 就唔會再喺格上面觸發 → 判斷唔到位置 |
| 鬼影要 `pointerEvents: 'none'` | 唔係嘅話鬼影會擋住 `pointermove` |
| 托盤要 `touchAction: 'none'` | 唔係嘅話手機當佢係捲動，一拖就變捲頁 |
| 冇拖入格就唔做嘢 | 唔好當「撳一下」就亂放 |

## 🚫 行程選擇只喺主頁面（用戶要求 ③）

**用戶原話：**
> 「只可以喺主頁面度揀你想要嘅行程…需要唔需要令我開一個頁面
>  就係話你要揀一個行程？」

**→ 唔要。**

```
之前：撳 Planner 而未有旅程 → toast + 跳去「旅程」app
                            （= 一個獨立嘅「請揀旅程」頁）

而家：撳 Planner 而未有旅程 → toast + **留喺主頁**
                            + 自動打開旅程選擇器
```

⚠️ 主頁面本身已經有齊：
- 「當前旅程」卡 + **轉旅程 (N) ▼**
- 「＋ 開新旅程」
- 「未揀旅程 —— 撳呢度揀一個」

→ 想改旅程就返主頁，唔使去第二個 app。

## 🔍 App 審查（用戶要求 ②：刪走冇用嘅）

⚠️ **老實講：我搵唔到「完全冇用」嘅 app。**

你原本嘅 spec 已經包含晒：
> 「完整：登入 + group + 貼 link + **地圖** + 行程表」
> 「like **分區** plan 行程時幫你分好啲區」

| App | 行數 | 寫入 | 判斷 |
|---|---|---|---|
| Planner | 314 | ✅ | 核心 |
| Organize | 394 | ✅ | 核心（貼 link）|
| Money | 348 | ✅ | 核心（分帳）|
| Shopping | 487 | ✅ | 核心（購物）|
| **Zones** | 185 | ✅ 1 個 | ⚠️ 同 Planner 重疊（但「一鍵排行程」係獨有）|
| **Map** | 185 | ❌ 0 個 | ⚠️ 只讀（但係你 spec 要嘅「地圖」）|
| Friends | 387 | ✅ | 核心 |
| **Trips** | 391 | ✅ | ⚠️ 同主頁面「轉旅程」重疊 **70%** |
| Settings | 189 | ✅ | 核心 |

### ⚠️ 但係我**已經刪咗** 3 個重複功能

| 刪咗 | 為咩 |
|---|---|
| Planner「逐日編排」mode | HTML5 DnD 手機用唔到 + 唔寫時間 |
| 「先揀旅程」獨立頁 | 主頁面已經有 |
| （半個）Planner 嘅 mode 切換 | 3 個 → 2 個 |

**審查數據**（`app_open` 事件）太稀疏（只 12 個），唔夠判斷邊個真係冇人用。
如果要刪 app，我建議由你話我知 —— 因為呢個係產品決定，唔應該我估。

## 🎨 角色圖（用戶提供嘅插畫）

**用戶要求**：
> 「角色嘅話我係覺得呢一啲直接用佢都得嘅，咁可能你
>  唔好成張擺上去，即係你可以 cop 咗佢個背景上去。」

→ 即係「直接用 + 幫我去背」。

### ⚠️⚠️⚠️ 最大嘅發現：AI 去背**食咗白色部分**

你畀嘅 6 張圖，**本身已經係透明底**（唔使我褪）。
但一檢查之下發現：

| 圖 | 狀態 | 問題 |
|---|---|---|
| `her-idle` | ✅ | — |
| `her-give` | ✅ | — |
| `her-hold` | ⚠️ | **白頭髮**被褪走 |
| `him-idle` | ❌ | **成套白西裝**被褪走 |
| `him-take` | ⚠️ | **白恤衫**被褪走 |
| `him-soft` | ⚠️ | **白西裝**被褪走 |

**原因**：AI 去背邏輯係「白色 = 背景」，
但角色**白頭髮 + 白西裝**一樣係白色 → 分唔清 → 兩樣都褪。

**⚠️ 救唔返**：透明區嘅 RGB 平均係 `(16,17,21)` —— 近黑。
即係原本顏色**冇保存**。（有啲工具會保留 RGB 只改 alpha，咁就救得返。）

我試過「最近像素填補」修補 —— **冇用**，
因為西裝嘅透明區連住外面背景（經領口），唔算「洞」。

### ✅ 已安裝（4 個 frame）

```
mascot-hello.png   ← her-idle   217×520  ✅ 乾淨
mascot-point.png   ← her-hold   356×520  ⚠️
mascot-happy.png   ← her-give   265×520  ✅ 乾淨
mascot-oh.png      ← him-take   340×520  ⚠️
```
另加 `mascot-him-idle.png` · `mascot-him-soft.png` 做備用。合計 **901 KB**。

### 💡 意外嘅好消息

嗰 4 張「白西裝透明」嘅圖，喺**深色星雲底**上面
睇落似**深色西裝** —— 竟然合理。

但呢個係好彩，唔係設計。

### 🔧 寫咗個去背工具：`engine/cutout.py`

```bash
python cutout.py 你嘅圖/ -o ../web/public/ --prefix mascot-
python cutout.py --check ../web/public/mascot-*.png
```

**⚠️ 智能判斷（呢個係關鍵）：**
```python
bg_is_whitish = all(int(c) > 200 for c in bg)

if bg_is_whitish:
    outside = flood_fill_from_border   # 白底 → 只褪連到邊界嘅
else:
    outside = near_bg                  # 非白底 → 全域褪（連內部碎點）
```

**實測（合成圖）：**
```
鮮綠底 + 白西裝  →  背景 76.9% 透明 ✅  白西裝 alpha 255 ✅  綠洞 alpha 0 ✅
白底   + 白西裝  →  白西裝 alpha 170 ⚠️  被食咗一部分
```

### ⚠️ 想根治：用**非白色**背景重新生成

提示詞加：
```
solid bright green background (#00ff00), flat color background
```

⚠️ 唔好用白色、唔好用「透明背景」——
AI 出嘅「透明背景」通常就係白底 + 假透明。

之後：`python cutout.py 新圖/ -o ../web/public/ --prefix mascot-`

### CSS 都要改（由像素圖 → 插畫）

| | 之前（36×44 程序化） | 而家（插畫） |
|---|---|---|
| 大細 | 72-108px | **120-200px** |
| `image-rendering` | `pixelated` | **`auto`**（插畫用 pixelated 會起格） |
| 陰影 | 冇 | 貼身暗邊 + 紫色柔光 |

## 👁️ 密碼眼仔（顯示／隱藏）

> 「設定密碼嗰個應該係隔離正常係會有一個眼仔，俾你去睇個密碼
>  係咪正確？撳一下就會 show 密碼，再撳多一下就會唔 show。」

### ⚠️ 眼仔唔係裝飾，係**必要**

- 密碼打錯自己睇唔到 → 用戶會以為「個 app 壞咗」，然後試第啲密碼
- 手機自動首字母大寫 → `Icychan` vs `icychan` 睇唔出
- 「再打一次」對唔上嗰陣，冇眼仔根本冇得查
- 密碼管理器填入嘅值可能多咗空格

### ⚠️ 實作陷阱（都中過）

| 陷阱 | 為咩 |
|---|---|
| 一定要係**模組層**元件 | 喺 render 入面定義 → 每次 render 都係新元件類型 → **每次打字都失焦** |
| 眼仔要 `type="button"` | 喺 `<form>` 入面，預設 type 會**提交表單**（用未打完嘅密碼登入） |
| 要 `autoCapitalize="off"` | 輸入法自動大寫 = **靜靜改咗你個密碼** |
| 要 `padding-right` | 唔留位嘅話文字會打喺眼仔下面 |
| 眼仔 ≥ 36px | 細過呢個手指撳唔中 |

覆蓋 **6 個**密碼欄：登入 · 註冊 ×2 · 認領 ×1 · 設定 現有/新/確認 ×3

---

## 🗑️ 帳號重設／刪除工具

`server/tools/manage_account.py`

```bash
python tools/manage_account.py someone@gmail.com --show
python tools/manage_account.py someone@gmail.com --set-password 新密碼
python tools/manage_account.py someone@gmail.com --delete     # ⚠️ 破壞性
```

### ⚠️⚠️⚠️ 三個 FK CASCADE 陷阱（實測造成資料損失）

我刪 `icychan51@gmail.com` 嗰陣，**頭兩次都刪走咗朋友嘅資料**。
三個唔同嘅 FK 各自咬咗一啖：

| # | FK | 後果 |
|---|---|---|
| ① | `trips.owner_id → users(id) ON DELETE CASCADE` | **成個旅程冇咗**，就算仲有其他成員 |
| ② | `items.created_by → users(id) ON DELETE CASCADE` | **朋友旅程入面嘅景點冇咗**（3 個變 1 個） |
| ③ | `expenses` / `shopping_items` 用 `SET NULL` | ✅ 冇事 |

**⚠️ 第 ② 個揭露咗 schema 唔一致** —— 三個 `created_by` 應該都係 `SET NULL`，
但 `items` 用咗 `CASCADE`。

### 修法（工具層面）

```
1. 轉移 trips.owner_id  → 同旅程最早加入嘅其他成員
2. 轉移 items.created_by → 同上
3. 只刪「冇其他成員」嘅旅程嘅內容
4. 清走孤兒旅程
5. 最後先刪用戶
```

**實測對比備份：**
```
「trip」旅程          ✅ 保住（擁有權轉移）
  items              3 → 3  ✅ 完全保住
  trip_stops         2 → 2  ✅ 完全保住
  shopping_items     3 → 3  ✅ 完全保住
朋友 icychan511       ✅ 仲喺
```

### ⚠️ 安全設計

- 確認要**打返個 email**（`DELETE someone@gmail.com`）先算
- 確認**之前**就列出：邊啲旅程會轉移、邊啲會一齊刪
- 冇其他成員嘅旅程先真係刪
- 工具**唔會**自己備份 —— ⚠️ **你自己先 `cp wander.db backup.db`**

### ⚠️ 我做咗嘅備份

```
server/backup-20261008-073417-before-delete-icychan51.db   ← 刪之前
server/backup-20261008-073454-damaged.db                   ← 中途損壞嗰陣
```

如果發現咩唔妥，可以直接 copy 返做 `wander.db`。

## 📧 未設定 SMTP 點搞？

> **你問嘅**：「未設定 SMTP 你係諗住點搞？」

### 誠實答：冇 SMTP 就寄唔到驗證碼

但**朋友之間用根本唔需要 email 驗證**。所以有三條路：

| | 做法 | 成本 | 時間 | 適合 |
|---|---|---|---|---|
| **①** | 設定 SMTP | 免費 | 5 分鐘 | 想用真 email |
| **②** | **邀請碼** | 免費無限 | **0 分鐘** | **朋友之間 ← 推薦** |
| **③** | 公開註冊 | 免費 | 0 | ⚠️ 只適合純內網 |

### ⚠️ 先搞清楚：其實幾時真係需要 email？

| 情況 | 需要 email？ |
|---|---|
| **日常登入** | ❌ 唔需要（打密碼就得） |
| **註冊新帳號** | ⚠️ 要（**或者用邀請碼**） |
| 唔記得密碼 | ⚠️ 要（或者你幫佢重設） |
| 朋友邀請 | ❌ 唔需要（分享連結） |

### ② 邀請碼（我已經做好，你咩都唔使設定）

```
1. 設定 → 開發版後台 → 🔑 註冊邀請碼
2. 撳「產生」→ 出 6 位碼（例：7OPDCP）
3. WhatsApp 畀朋友
4. 朋友註冊時打呢個碼 → 完成
```

**⚠️ 為咩邀請碼其實比 email 驗證更好（朋友之間）：**

| | Email 驗證 | 邀請碼 |
|---|---|---|
| 證明咩？ | 佢控制嗰個信箱 | **你親手畀佢** |
| 成本 | 要 SMTP | 零 |
| 被濫用 | 可以撞 | 一次性 + 有期限 |
| 垃圾帳號 | 可能 | 唔可能（你唔畀就冇） |

**安全設計**：一次性（用咗標記 `used_by`）· 有期限（預設 30 日）·
撇除易混淆字元（`O/0`、`I/1/l`）

### ① 設定 SMTP（想用真 email 先做）

📄 **`docs/smtp/README.md`** —— 三個選項逐步教學：

| 服務 | 免費額度 | 注意 |
|---|---|---|
| **Gmail App Password** | 500 封/日 | 要開兩步驗證 |
| **Resend** | 100 封/日 | 未驗證網域只可以寄自己 |
| **Brevo** | 300 封/日 | 要驗證寄件人，但可寄任何人 |

### ⚠️⚠️ 而家（未設定）嘅狀態：有安全洞

```
mode: "console"
驗證碼會顯示喺登入畫面
```

⚠️ **任何人都可以用任何人嘅 email 註冊／認領帳號** ——
只要佢知你個網址。

| 情境 | 風險 |
|---|---|
| 純內網（192.168.x.x） | ✅ 冇問題 |
| cloudflared 放出街 | ⚠️ **危險** |

✅ **所以而家預設係 `invite`** —— 有邀請碼先註冊得到。

### 自動判斷（你咩都唔使設定）

```python
def signup_mode() -> str:
    """
    ⚠️ 預設：有 SMTP 就 `email`，冇就 `invite` ——
       因為冇 SMTP 就寄唔到驗證碼，
       `email` 模式會令**所有人都註冊唔到**。
    """
```

實測：
```
① 註冊模式 → {mode: 'invite', need_invite: True}   ✓ 自動判斷
② 產生邀請碼 → ['7OPDCP', 'JZ8WC7']
③ 用邀請碼註冊 → 200 ✓
④ 再用同一個碼 → 403 ✓ 一次性
⑤ 之後用密碼登入 → 200 ✓
```

### ⚠️ 又中一次 route 次序陷阱

加邀請碼 endpoint 嗰陣 **append 咗喺 catch-all 之後** → 404。
⚠️ 而且我嘅**檢查 script 都 match 錯** ——
佢搵 `@app.get("/{full_path:path}")`，但呢個字串喺我寫嘅**解釋註解**入面都有
→ 攞咗註解嘅位置做基準。
→ 所以測試一定要用**去註解**版本。

## 🔐 登入「已過期」誤報

**用戶報**：
> 「我登入嘅時候佢同我講登入已過期重新登入…
>  正常都係用 20 秒之內去登入，但佢同我講話過期唔得喎」

### ⚠️⚠️ 401 唔一定係「session 過期」

```python
# 後端：密碼唔啱 → 401
raise HTTPException(401, "Email 或密碼唔啱")
```
```js
// 前端：所有 401 都當過期 → 清 token + 登出
if (res.status === 401) {
  auth.clear()
  window.dispatchEvent(new Event('wander:logout'))
  throw new Error('登入已過期，請重新登入')   // ← 完全誤導
}
```

**打錯密碼 → 見到「登入已過期」+ 被登出。**

### 修法：睇有冇帶 token

```js
const hadToken = !!auth.token
if (hadToken) headers.Authorization = `Bearer ${auth.token}`
...
//  · 有帶 token 而 401 → 真係 session 過期
//  · 冇帶 token 而 401 → 係「憑證唔啱」（登入 API）→ 照拋後端訊息
if (res.status === 401 && hadToken) { auth.clear(); ... }
```

### ⚠️ 順便修「舊帳號冇密碼」

用戶之前用**驗證碼**開嘅帳號冇密碼 → 打咩都 401。
而家後端會分開講：

```python
if user and not user["password_hash"]:
    raise HTTPException(401, "未設密碼")     # → 前端自動轉「認領帳號」
raise HTTPException(401, "Email 或密碼唔啱")
```

實測：
```
① 舊帳號（未設密碼）→ 401 「未設密碼」      ✓ 自動轉認領
② 唔存在嘅 email    → 401 「Email 或密碼唔啱」
③ 有密碼但打錯      → 401 「Email 或密碼唔啱」✓ 唔再係「已過期」
④ 正確密碼          → 200 + token
```

> ⚠️ 代價：「未設密碼」會洩漏「邊個 email 註冊過」。
> 對一個朋友之間用嘅旅行 app，**用戶體驗 > 呢個風險**。

---

## 🛠 開發版後台

**用戶要求**：
> 「我覺得另外仲要整一個叫做開發版，係放我自己睇啲人用
>  呢個 App 嘅數據。」

### ⚠️ 為咩要有「事件表」而唔係由現有表反推

`Items` / `Expenses` 只記錄**結果**（加咗 3 個景點），唔記錄**過程**：
- 邊個 app 最多人開？（Planner？Shopping？）
- 用戶登入完有冇真係做嘢？（激活率）
- 邊個功能**開過但冇用**？（= 唔知點用，要改 UI）

```sql
CREATE TABLE events (
  id, user_id, kind, target, created_at
);
CREATE INDEX idx_events_time ON events(created_at);
```

⚠️ **私隱**：只記「類型 + 目標」，**唔記內容**。
最近活動只顯示 email 前 3 個字。

### 後台睇到咩

| 區塊 | 內容 |
|---|---|
| 👥 用戶 | 總數、期間新增、教學完成率、設密碼率 |
| ⚡ 活躍 | DAU、WAU、黏性（DAU/WAU）、有效 session |
| 📦 內容 | 旅程、城市、景點、開支、購物、**多城市旅程** |
| 📈 每日活動 | 純 CSS 柱狀圖（唔加 chart library） |
| 🎯 功能使用 | 每個 app 開幾多次（排序） |
| 🌱 新用戶 | 每日走勢 |
| 🕐 最近活動 | 最新 40 條 |
| 📐 規模 | 平均日數、平均城市、**冇景點嘅旅程** |

> ⚠️ `empty_trips`（建立完但一個景點都冇）係最有價值嘅數字 ——
> 代表用戶唔知跟住做咩。

### 權限：兩種方法

```
① WANDER_ADMIN_EMAILS=you@gmail.com   （.env，逗號分隔）
② users.is_admin = 1                  （DB 欄位，臨時開權限）
```

⚠️ **預設冇人係 admin** —— 唔可以有永遠 admin 嘅後門帳號
（例如 `admin@wander.app`），一旦公開就即刻被撞。
有測試守住呢點。

### ⚠️⚠️ 捉到兩個「次序」bug

**① FastAPI route 次序**

```python
@app.get("/{full_path:path}")     # SPA catch-all
def spa(...): ...
```
我加嘅後台 API 寫喺 catch-all **之後** → 永遠回 404。
⚠️ 症狀好誤導：catch-all 只擋 `api/` 開頭 → raise 404，
睇落似「route 唔存在」而唔似「次序錯」。

**② `.env` 載入次序**

```python
# main.py 原本冇喺 module 層 import mailer
from .mailer import send_code_email   # ← 寫喺函數入面（lazy）
```
而 `load_env()` 係 mailer 喺 module 層呼叫嘅
→ `main.py` 頂層讀 `WANDER_ADMIN_EMAILS` 讀到**未載入**嘅值。

修法：
```python
from .mailer import load_env as _load_env
_load_env()                        # ← 喺 import 之後即刻做

def _admin_emails() -> set: ...    # ← 用函數，唔用 module 常數
```

## 🏙️ 新增旅程時就可以加多個城市

> 「新增旅程嘅時候…應該有一個 button 俾你去加城市，
>  而唔係當你去編輯嘅時候先至可以加新增多於一個城市，
>  而係你一開行程就已經有得加多於一個城市。」

### ⚠️ 之前嘅流程（要行三步）

```
建立旅程 → 入 Planner → 撳城市編輯器 → 加第二個城市
```
用戶做到第二步已經會以為「唔支援多城市」。

### 而家

「新旅程」表單入面直接有 **「去邊幾個城市」** 區塊：

```
去邊幾個城市 （唔加就淨係用上面嗰個目的地）
 1  福岡    [3] 日  ✕
 2  由布院  [2] 日  ✕
 3  熊本    [2] 日  ✕
[加城市（打中文／英文）      ] [＋ 加]

共 3 個城市 · 7 日
```

### ⚠️ 幾個唔一致嘅陷阱（已處理）

| 陷阱 | 處理 |
|---|---|
| 清單同 `destination` 唔一致 | 目的地自動用**清單第一個** |
| 旅程日數同城市日數加埋唔同 | 有清單就用**清單總和** |
| **編輯**時清單空白 → 一儲存清走晒城市 | 開啟編輯時**載入現有城市** |
| 城市寫入失敗 → 當成個建立失敗 | 旅程照建立，只提示「城市未寫入」 |
| 同一個城市加兩次 | 擋重複 |

---

## 🕐 順手捉到：`Etc/GMT-9` 而唔係 `Asia/Tokyo`

加多城市時發現「由布院」「鹿兒島」嘅時區係 `Etc/GMT-9`（經度估算）
而唔係 `Asia/Tokyo`。**三個原因疊埋：**

```
① 地區庫（districts.json）只存中文國名「日本」，冇 ISO 碼
② 快取係**舊版**寫落嘅，冇 country_code 欄位
   ⚠️ 快取命中率 >99% → 大部分查詢行呢條路
   ⚠️ 新查詢反而冇事 → 極難重現
③ Photon / Nominatim 路徑冇讀 countrycode
```

**修法：**
```python
_ZH_TO_CC = {"日本": "JP", "韓國": "KR", ...}   # 中文國名 → ISO

# Photon 用 countrycode；Nominatim 用 country_code
cc=(p.get("countrycode") or "").upper() or None

# ⚠️ 舊快取讀取時 backfill（唔止修 8 條，任何用戶嘅快取都修到）
if hit and not hit.get("country_code") and hit.get("country"):
    hit["country_code"] = _zh_to_cc(hit["country"])
```

⚠️ 兩者都係 UTC+9，但**標籤**唔同（「東京」vs「GMT-9」）→ 用戶會覺得錯。

實測：
```
✓ 福岡    3日  Asia/Tokyo
✓ 由布院  2日  Asia/Tokyo   ← 之前係 Etc/GMT-9
✓ 熊本    2日  Asia/Tokyo
✓ 鹿兒島  2日  Asia/Tokyo   ← 之前係 Etc/GMT-9
```

## 🔧 用戶報嘅 4 個問題（全部修好）

### ① 揀咗旅程之後，出返 Home 變「未揀旅程」

> 「揀咗旅程之後…整理 organize 呢啲…再出返去撳返旅程出返去個
>  Home 度…佢就同我講未揀旅程。」

**兩個原因：**

```js
// ❌ 原因 1：`‹ 旅程` 個掣會清空揀選
const backToTrips = () => {
  setTripId(null)      // ← 呢行就係 bug
  setTab('home')
}

// ❌ 原因 2：tripId 從來冇存過
const [tripId, setTripId] = useState(null)   // refresh 就冇
```

**修法：**

| 之前 | 而家 |
|---|---|
| `‹ 旅程` → 清空揀選 | `‹ 旅程` → 去清單，**保留**揀選 |
| refresh → 冇咗 | 存 `localStorage` |
| 要自己再揀 | 只有 1 個旅程 → **自動揀** |
| 唔知而家喺邊個 | 清單標示 **「✓ 當前」** + 橫幅 |
| 冇得退出 | 加咗明確嘅 **「退出」** 掣 |

> **⚠️ 為咩「去清單」唔等於「退出旅程」**：
> 用戶嘅心智模型係「我而家喺福岡之旅入面」——
> 撳「旅程」只係**睇下我仲有咩旅程**，唔係放棄福岡。

### ② 密碼欄打字會斷（每打一個字要重新點擊）

> 「打 Password 嘅時候…我打緊嘅同時我要點擊佢先至可以打下一個。」

**⚠️⚠️ 原因：React 經典陷阱 —— 喺 render 入面定義元件**

```jsx
export default function SettingsMore(...) {
  const Sec = ({...}) => (...)    // ⚠️ 每次 render 都係「新元件類型」
  ...
}
```

React 見到**新元件類型** → **unmount + remount** 成個子樹 →
入面嘅 `<input>` 被拆走重建 → **focus 消失**。

✅ 搬去**模組層**，用 props 傳 `open` / `onToggle`。

> ⚠️ build **完全唔會警告**呢個問題。所以加咗測試掃全 codebase：
> 「唔可以有任何 render 入面定義嘅元件」。

### ③ App icon 跟主題色調

> 「因為我哋有唔同嘅主題啦，所以 Apps 嘅 icon 應該都要
>  跟返類似嗰個對應嘅主題，即係色調可能要改少少。」

**⚠️ 之前**：漸變色**寫死喺 JS**（`app.grad`）→ CSS 主題蓋唔到。
切去 `minimal`（米白底）之後，霓虹紫／青喺淺底上面刺眼。

**而家**：每個 app 攞一個色位 `--app-a` … `--app-g`，由每個主題自訂。

```css
:root            { --app-a: #a855f7; /* 霓虹 */ }
[data-theme='tech']    { --app-a: #e4e4e7; /* 單色 */ }
[data-theme='minimal'] { --app-a: #1c1917; /* 深色（米白底要深） */ }
[data-theme='khaki']   { --app-a: #8a7048; /* 卡其 */ }
[data-theme='macaron'] { --app-a: #f472b6; /* 馬卡龍 */ }
[data-theme='wafu']    { --app-a: #b03a48; /* 朱紅 */ }
```

⚠️ 用 `color-mix()` 由**單色**推漸變 —— 由 42 個值減到 21 個：
```css
.app-ico {
  background: linear-gradient(140deg,
    color-mix(in srgb, var(--c) 62%, white), var(--c));
}
```

⚠️ 圖示本身都要調（tech 灰階、minimal 反白、和風降飽和）。

### ④ Shopping list 相框

> 「我想有一個框架…upload 相之後有一個框架咁然後會 show 個相出嚟…
>  一碌落去你就知道嗰個商品係有乜嘢圖案係點嘅樣，
>  而唔係剩係得個名。」

**⚠️ 為咩要「框」而唔係單純一張圖：**
- 超市貨架相通常白底 → 冇框會同淺色主題嘅卡片底**融為一體**
- 有框 = 一眼認得出「呢度有實物相」
- 一碌落去，**圖先入眼、名先入腦** —— 買嘢係認樣唔係認字

| | 之前 | 而家 |
|---|---|---|
| 大細 | 52-68px | **62-84px** |
| 框 | 1px 單層 | **3px 外框 + 內幼邊 + 內陰影**（相框厚度）|
| 冇相 | **唔顯示** | **虛線空框**（提示你影相）|
| 詳情頁 | 冇 | **4:3 大相框**（`object-fit: contain` 唔裁走）|

**⚠️⚠️ 順手捉到 `::after` 相撞**：
`✓ 完成` 同 `⤢ 放大` 都想用 `.thumb::after` ——
一個元素**得一個** `::after`，後定義嘅會蓋前面。
→ 完成用 `::before`。

## 🐷 頭像 2.0（16×16，37 個）

**用戶要求**：
> 「頭像嗰度…你嗰啲塑像風可唔可以整得**再 Q 啲**？
>  或者唔好咁簡陋啦，你整得再**精緻啲**都可以㗎。
>  同埋想要**多啲唔同嘅元素**都得㗎，例如豬、狗啦呢啲，
>  之後或者扭計骰啊、手機呀、鴨呀、兔仔呀呢啲都可以嘅。」

### ⚠️ 為咩一定要由 8×8 升到 16×16

| | 8×8 | 16×16 |
|---|---|---|
| 眼 | **只有 1 格** → 做唔到高光 = 唔 Q | 3×2 + 高光 ✓ |
| 腮紅 | 冇位 | ✓ |
| 鼻 + 嘴 | 唔可能同時有 | ✓ |
| 色數 | 2-5 | 4-8 |

### ⚠️ 為咩用**模板化生成**而唔係逐個手畫

37 個 × 256 格 = **9472 格**。逐個手畫一定會唔一致
（有啲眼大、有啲眼細、有啲冇腮紅）→ 睇落唔似一套。

模板保證**所有動物臉一致地 Q**，只變耳朵同色：
```python
add('cat', '貓', pal(...), animal(ears='cat', mouth='w', nose=10))
add('dog', '狗', pal(...), animal(ears='floppy', mouth='w', nose=10))
add('pig', '豬', pal(...), animal(ears='cat', mouth='w', nose=10))
add('rabbit', '兔', pal(...), animal(ears='long', mouth='w', nose=10))
```

### 37 個元素

| 類別 | 內容 |
|---|---|
| **動物** | 貓 狗 豬 兔 鴨 熊 熊貓 狐狸 青蛙 企鵝 倉鼠 獨角獸 |
| **自然** | 月亮 星星 雲 花 心 閃電 波浪 太陽 樹 山 鑽石 彩虹 |
| **物品** | 戒指 扭計骰 手機 相機 行李箱 飛機 火箭 雪糕 蛋糕 咖啡 |
| **角色** | 小幽靈 外星人 機械人 |

### ⚠️⚠️ 捉到三個 bug

**① `head()` 嘅圓角處理刪咗成條側邊描邊**
```python
# ❌ 想切角，但 (top+1, left) 係側邊描邊嘅其中一格
g[top + 1][left] = '.'
# → 成條側邊喺嗰行斷開 → 個頭睇落「冇邊」，似一嚿色
```
✅ 正確做法：用「每行縮入幾多格」砌圓角（top 縮 2、top+1 縮 1、之後 0）。

**② 企鵝調色板順序錯** → `index 3`（五官）用咗白色 → 對眼變成發光白塊。
✅ 五官一定要係**深色**，白色身用 `index 2`。

**③ 手打 grids 混入空格** —— 驗證器捉到 11 個。
✅ `obj()` 自動將空格當透明。

### ⚠️ 有啲形狀 16×16 做唔到，要換角度

| 原本 | 問題 | 改為 |
|---|---|---|
| 飛機（側面） | 機身 + 上下機翼疊成一嚿白色十字 | **俯視角**大三角翼 |
| 鴨（模板） | 嘴同腮紅撞位 → 隻鴨冇眼 | **手畫**（扁嘴 + 眼喺上） |
| 咖啡（模板） | 一嚿橙色長方形 | **手畫**（杯 + 耳 + 熱氣） |

### ⚠️ 有啲形狀天生多透明格

`ring`（戒指）只有 88 格有嘢（環形嘛）——
測試門檻設 70，仍然捉得到「近乎全空」。

## 🎨 像素頭像（舊版 8×8）

設定頁揀自己嘅頭像 —— **14 個像素圖案**，同開機動畫同一個風格。

```
設定 → 頭像
┌──────────────────────────────────────┐
│ ▣  星星                              │
│    撳下面任何一個即刻換               │
├──────────────────────────────────────┤
│ ▣星  ▣月  ▣雲  ▣花  ▣戒  ▣心  ▣電    │
│ ▣貓  ▣浪  ▣日  ▣樹  ▣山  ▣鑽  ▣鬼    │
└──────────────────────────────────────┘
```

**⚠️ 為咩用「像素格」而唔用 emoji 或者上傳相：**

| 做法 | 問題 |
|---|---|
| **Emoji** | 每部機唔同樣（Apple / Google / Samsung 全部唔同），開發者控制唔到 |
| **上傳相** | 要 storage + 縮圖 + 審內容，對「旅行 app 頭像」嚟講太重 |
| **像素格** ✅ | **deterministic** —— 同一組數字喺任何機都一模一樣，8×8 就夠辨識 |

格式：8×8 字串陣列 + 每個頭像自己嘅調色板
```js
{ id: 'cat', name: '貓', pal: ['#c2410c', '#fb923c', '#fdba74', '#0b0518'],
  grid: ['11....11', '111..111', '11111111', '11222211',
         '13222231', '11222211', '.122221.', '..1111..'] }
```

### ⚠️ 測試捉到嘅 bug

`tests/test_avatars.py` 用 Python 重新 parse 一次 JS 資料：

```
檢查索引超出調色板：
  ✓ moon   pal=3  用 [1]
  ✗ cat    pal=3 色  用到索引 [3]（超出）
      第 4 行: 13222231
  ✗ tree   pal=3 色  用到索引 [3]（超出）
  ✗ ghost  pal=3 色  用到索引 [3]（超出）
```

**3 個頭像用咗調色板冇嘅索引** —— 程式會 fallback 去 `pal[0]`，
所以「貓嘅眼」會變咗橙色，但**唔會有任何錯誤**。
896 格（14 × 64）靠肉眼睇唔晒，一定要程式檢查。

## @帳號名（加朋友用，唔使 email）

每個用戶有兩個名：

| | 係咩 | 例 |
|---|---|---|
| **帳號名** `username` | 唯一嘅 handle，**加朋友用** | `@alice_99` |
| **顯示名** `display_name` | 朋友見到嘅名，可以重複 | `Alice` |

設定頁可以隨時改兩個。改帳號名之後舊嘅即刻失效。

### ⚠️ 為咩要嚴格驗證帳號名

帳號名係「**俾人打嘅身份**」—— 有同形字（`l`/`1`/`I`、`O`/`0`）就會有人冒充。

```
只准 a-z 0-9 _      → 冇大小寫混淆（Alice9 / ALICE9 / alice9 全部 = alice9）
一定要字母開頭       → 唔會同純數字（例如電話號碼）撞
3-20 個字
⭐ 一定要有字母 + 數字 → 防止「alice」「bob」呢類純字詞（易撞名、易估）
擋保留字 + 前綴      → admin / admin1 / admin_2026 / wander99 …
```

實測：
```
✓ 'alice99'      → 'alice99'
✓ 'alice_2026'   → 'alice_2026'
✗ 'alice'        → 帳號名要有埋數字（例如 alice99）
✗ '123456'       → 要字母開頭
✗ 'alice_'       → 要有埋數字
✗ 'admin1'       → 「admin」係保留字（或者太似）
✗ '  ALICE99  '  → 'alice99'（前後空白會 trim）
```

⚠️ **保留字檢查一定要排喺「要數字」之前** ——
否則「admin」會先被「要數字」擋，訊息變成「要有埋數字」而唔係
「呢個係保留字」→ 誤導用戶。

⚠️ **唔可以只擋完全相同** ——「admin1」「admin_2026」呢類前綴冒充
一樣會令人以為係官方。

## ⚠️ 用戶報嘅 bug：設完帳號名 QR 冇出

```
「當我 Save 低咗自己嘅帳號名，同埋顯示名稱之後呢，
  個 QR code 係冇 show 出嚟㗎囉」
```

**原因**：`MyQr` 原本只有撳「產生我嘅 QR Code」個掣先會載入。
用戶改完帳號名之後，以為 QR 會自動出，但其實要再撳一次。

**修法**：`useEffect` 監住 `username` ——
```js
useEffect(() => {
  if (mode !== 'mine') return
  if (!uname) { setQr(null); return }   // 冇帳號名 → 清走舊 QR
  api.myQr().then(setQr)                 // 有就自動產生
}, [uname, mode])
```

⚠️ **`username` 一變就要重新產生** —— 舊 QR 編碼舊 username，一定要換。

### 加朋友流程

```
加朋友
┌────────────────────────────────────────┐
│ @ [alice_99                  ] [加]    │
└────────────────────────────────────────┘
   ↓ 打 3 個字就自動查
┌────────────────────────────────────────┐
│ ▣  Alice                    [加好友]    │  ← 即時預覽，確認係唔係嗰個人
│    @alice_99                            │
└────────────────────────────────────────┘
```

⚠️ **`/api/users/lookup` 唔會回 email** —— 否則可以用嚟掃描邊啲 email 註冊過。

## 📷 個人 QR Code

```
設定 → 我嘅 QR Code
   [📤 我嘅 QR]  [📷 掃人哋]

┌──────────────────┐
│ █▀▀▀█ ▄▀ █▀▀▀█   │
│ █ ▄▄▄█ ▀▄ █ ▄▄▄█  │   ▣ Alice
│ █▄▄▄█ █▀ █▄▄▄█   │   @alice_99
└──────────────────┘
   [下載 QR] [複製連結]
```

**QR 內容係一條 URL**（唔係淨係個 username）：
```
http://192.168.1.83:8787/?add=alice_99
```
| 邊個掃 | 會點 |
|---|---|
| **手機原生相機** | 直接開到 Wander，自動跳去朋友頁預填 @alice_99 |
| **app 內「掃人哋」** | 上傳圖 → 解出 username → 自動填 |

如果只編碼 `alice`，原生相機掃到只會顯示文字，做唔到任何嘢。

### ⚠️⚠️ 為咩用「上傳圖」而唔用「即時相機」

```
getUserMedia（相機）需要 secure context（HTTPS）
http://192.168.x.x 唔算 secure context → 開唔到相機
```

但「**影相 → 上傳**」完全冇呢個限制：用手機原生相機影（或者揀相簿），再上傳。

### ⚠️ 前端一定要用無損 PNG

```js
readAndResize()  // 1200px + JPEG 0.82  ← ❌ QR 會糊成一團
readForQr()      // 1600px + PNG 無損   ← ✅
```

QR 解碼最怕**壓縮失真**。JPEG 0.82 會令細格糊埋，OpenCV 就解唔到。

### 實測：模擬真實手機影相

```
✓ 原圖 PNG                 → alice14436
✓ 放大 2.5x                → alice14436
✓ 放大 + 輕微模糊            → alice14436
✓ 縮細到 60%               → alice14436
✓ 影相比較斜（旋轉 8°）        → alice14436
✓ 有背景（灰色底）            → alice14436
✓ JPEG 85% 放大 2x         → alice14436
✓ JPEG 60% 放大 2x         → alice14436

8/8 成功
```

### ⚠️ 捉到嘅 bug：OpenCV 回 3 個值

```python
# ❌ 錯：ValueError: too many values to unpack (expected 2)
found, _pts = cv2.QRCodeDetector().detectAndDecode(img)

# ✅ 啱：回 (text, points, straight_qrcode)
found = cv2.QRCodeDetector().detectAndDecode(img)[0]
```

**我喺測試檔寫啱（`txt, _, _ = ...`），但 endpoint 寫錯。**
所以「測試通過」唔等於「產品通過」—— 一定要真打 API。

而家有測試直接檢查 `main.py` 嘅源碼，唔准有 2 個變數解包。

## 🎨 交友邀請 email（可選，已改為次要）

```
加朋友
┌──────────────────────────────────────┐
│ [friend@example.com        ] [邀請]  │
│ [留句話（可選）                      ] │
└──────────────────────────────────────┘
📧 會真寄 email 去呢個地址：
 · 對方已經有帳號 → app 內收到請求 + email 通知
 · 對方未有帳號 → 收到註冊連結，註冊完自動做朋友
```

**⚠️ 三種情況分清楚：**

| 情況 | 做啲咩 |
|---|---|
| 已經係朋友 | 唔使做嘢 |
| 有帳號，未係朋友 | 建 `friend_request`（app 內通知）**+ 都寄 email** |
| **冇帳號** | 建 30 日一次性連結 **+ 寄 email** |

**⭐ 關鍵：用連結註冊 → 自動成為朋友**

```
對方撳 email 連結 → 去到我哋個 app → 未註冊
      ↓ 註冊（第一次登入）
後端憑 email 對返個邀請 → 自動雙向加朋友
```

冇呢步嘅話，用戶要「撳連結 → 註冊 → 再加一次」＝ 3 步。

**⚠️ 無論 email 寄唔寄到，邀請本身都會建立** ——
寄信失敗唔應該令「加朋友」失敗。UI 會顯示：
```
✅ Email 已寄出（透過 smtp）去 xxx@example.com
或
⚠️ Email 未寄出（未設定 SMTP → 內容印喺 server console）
   可以複製下面條連結自己傳畀對方 👇
```

## 🕐 時區（雙時鐘）

**用戶問**：
> 「呢個時間係點樣抽取㗎？如果我正常去旅行我就會帶手機啦，
>  咁係手機顯示咩時間你就顯示咩時間，定係點樣？
>  因為你去旅行嘅話就會入唔同嘅時區呀嘛。」

### 答：**兩個都要** —— 佢哋答緊唔同嘅問題

| | 邊個時間 | 答緊咩 |
|---|---|---|
| ① | **手機時間**（`new Date()`） | 你**身處**邊度。手機跟網絡／GPS 自動調整 → 「我而家幾點？」 |
| ② | **目的地時間**（`Intl` + IANA） | 旅程城市。⚠️ **手機唔會話你知** → 「嗰度而家幾點？」 |

⚠️ 為咩「目的地時間」重要：
- 你喺香港計劃去東京 → 想知東京幾點（排行程／訂位）
- 你喺東京想打返香港 → 想知香港幾點（唔好半夜打）
- 行程寫「Day 3 早上 9 點」→ 係**嗰度**嘅 9 點

### 顯示邏輯

```
⚠️ 同時區（香港 → 澳門）        ⚠️ 唔同時區（香港 → 東京）
┌──────────────────┐          ┌──────────────────┐
│      23:36       │          │      00:36       │  ← 目的地（大）
│  星期四 · 10月8日 │          │  🌏 東京  UTC+9  │
└──────────────────┘          │ ──────────────   │
                              │ 你嗰邊 23:36     │  ← 你身處（細）
                              │ （快 1 個鐘）     │
                              └──────────────────┘
```

**⚠️ 同時區唔會顯示兩個一樣嘅鐘** —— 否則用戶以為睇錯。

### ⚠️⚠️ 城市 → 時區（唔用外部 library）

`timezonefinder` 要一個 ~50MB 邊界資料庫。我哋用三層策略：

```
① 單一時區國家     → 查表（77 個國家，最準）
② 多時區國家       → 按經度分帶（美／加／澳／俄／巴西／印尼／墨西哥／西／葡）
③ 未知國家         → 經度估算（nautical tz）
```

### ⚠️⚠️ 捉到嘅 bug：多時區國家嘅經度分帶方向反轉

```python
# ❌ 錯：寫成「西邊界」
"US": [(-124, "LA"), (-114, "Phoenix"), ...]
# 條件 lng < upper → 全部向東串移一格：
#   紐約(-74) → Halifax ❌   芝加哥(-87.6) → 紐約 ❌

# ✅ 啱：寫成「東邊界」，由西向東排，最後一條係大正數
"US": [(-114, "LA"), (-109, "Phoenix"), (-102, "Denver"),
       (-87, "Chicago"), (-65, "New_York"), (999, "Halifax")]
```
19 個測試案例由 **14/19 → 19/19**。

### ⚠️⚠️ `Etc/GMT` 嘅正負號係**反轉**嘅

```python
_by_longitude(139.69)  # 東京 UTC+9 → "Etc/GMT-9"（負號！）
_by_longitude(-74.01)  # 紐約 UTC-5 → "Etc/GMT+5"（正號！）
```
呢個係 POSIX 遺留約定，好易寫錯 → 有測試專門守住。

### ⚠️ 日期唔可以因為時區而偏移

```js
new Date('2026-11-19')          // ❌ 當做 UTC 午夜
                                //    喺 UTC-5 嘅機會顯示 11-18！
new Date(2026, 10, 19)          // ✅ 當做「日曆日」（local）
```

`parseDate()` 已經用正確做法（`web/src/lib/dates.js`）。
**行程日期係「日曆日」，冇時區** —— 呢個係啱嘅。

### ⚠️ 一定要用 `Intl` 而唔係自己計 offset

| 自己計 | `Intl` |
|---|---|
| 夏令時間每年唔同日子轉，各國規則唔一樣 | 瀏覽器處理，永遠最新 |
| 澳洲南半球 DST 反轉 | ✅ |
| 印度 +5:30、尼泊爾 +5:45、南澳 +9:30 | ✅ |

## 👤 設定 = 個人檔案（Profile）

**用戶要求**：
> 「你要 del 不過個 setting 有睇唔到任何嘅嘢啦。
>  其實 setting 好簡單，你只需要講嘅就係：
>   ① 改名（有你個名喺度）
>   ② 有你 icon
>   ③ QR code —— 喺 setting 度整個 QR code
>  **朋友嘅呢啲係 Profile 嘅嘢嚟㗎嘛**。」

### ⚠️⚠️ 之前嘅問題：543 行、11 個區塊**全部平鋪**

```
教學 / 頭像 / 帳號名 / QR / 顯示名 / 主題 / 密碼 /
手機連線 / IG 匯入 / IG 抓取 / 快取 / 關於 / 登出
```

用戶要嘅 3 樣嘢（改名、換 icon、出 QR）**散落喺其中 5 個位**，
中間隔住一堆佢未需要嘅設定 → **搵唔到**（「睇唔到任何嘅嘢」）。

> ⚠️ 呢個係典型嘅「**開發者盲點**」：
>   每一樣都係我親手加嘅，所以我知喺邊；
>   但用戶只係想改名 / 換 icon / 出 QR。

### 修法：**分層**

```
第一層（預設見到）＝ 純 Profile
┌─────────────────────────────────┐
│  ▣  小明                        │  ← 撳頭像換 icon
│     @ming99                     │  ← 撳個名改名
│  撳個頭像可以換 icon；撳個名可以改 │
└─────────────────────────────────┘

我嘅 QR Code
┌─────────────────────────────────┐
│  ┌───────────┐                  │
│  │  █▀▀█ ▄▀  │  畀朋友掃        │
│  │  █▄▄█ █▀  │  就加到你        │
│  └───────────┘                  │
│  [📤 我嘅 QR] [📷 掃人哋]        │
└─────────────────────────────────┘

[▼ 更多設定（密碼 · 主題 · 教學 · 進階）]
```

```
第二層（撳「更多設定」先展開）＝ 每個都係**摺疊**
▸ 🔑 密碼          ▸ 💾 離線 / 儲存
▸ 🎨 主題          ▸ ℹ️ 關於
▸ ▶️ 指導教學       [登出]
▸ 📱 手機連線
▸ 🔖 IG / 小紅書 匯入
```

### ⚠️ 測試守住「第一層唔可以再塞嘢」

```js
// 第一層一定要有嘅 3 樣
['AvatarPicker', 'display_name', 'MyQr']

// 第一層**唔可以**有嘅（要收埋）
['cacheStatus', 'bookmarkletCode', 'THEMES']

// 第一層要夠短
assert lines < 220     // 實際 187 行（舊版 543）
```

## 🔐 登入 / 註冊（兩頁互通）

**用戶要求**：
> 「login function plzzz。**delete 驗證碼登入 function**。
>  要整兩版：一開始就係登入畫面，如果你冇帳號你就要註冊，
>  有個 button 俾你去撳去註冊…總之兩頁啦，係應該有個 button 去互通嘅。」

```
┌─ 登入 ─────────────────────┐   ┌─ 註冊 ─────────────────────┐
│ WANDER                     │   │ WANDER                     │
│ ╭────────────────────────╮ │   │ ╭────────────────────────╮ │
│ │ 歡迎返嚟                │ │   │ │ 開一個帳號              │ │
│ │ 用你嘅 email 同密碼登入  │ │   │ │ 只需要 email 同密碼     │ │
│ │ [you@example.com     ] │ │   │ │ [you@example.com     ] │ │
│ │ [密碼                ] │ │   │ │ [設定密碼（最少 6 字）] │ │
│ │ [      登入       ]    │ │   │ │ [再打一次密碼        ] │ │
│ │ ────────────────────── │ │   │ │ [      註冊       ]    │ │
│ │ 仲未有帳號？ [註冊一個] │ │   │ │ 已經有帳號？ [去登入]  │ │
│ ╰────────────────────────╯ │   │ ╰────────────────────────╯ │
└────────────────────────────┘   └────────────────────────────┘
```

### ⚠️ 為咩刪走驗證碼登入

| 問題 | 影響 |
|---|---|
| 「打 email → 收信 → 打 6 位數字」**每次**登入都要做 | 手機要跳去郵件 app 再跳返嚟 → 流失率高 |
| 冇「密碼」概念 | 冇「改密碼」嘅需要，用戶亦冇「帳號被盜」意識 |
| 唔係用戶預期 | 密碼登入係標準做法 |

### ⚠️⚠️ 但驗證碼**冇完全刪** —— 保留做「認領舊帳號」

舊帳號（驗證碼年代開嘅）**冇密碼**。如果註冊時打嘅 email 已經存在
但未設密碼，就要寄驗證碼去確認身份先可以設密碼。

```
註冊打舊 email
      ↓ 409 + needs_claim
┌────────────────────────────────┐
│ 呢個 email 已經有帳號           │
│ 我哋寄咗驗證碼去呢個 email ——   │
│ 打返落嚟就可以設定新密碼         │
│ [6 位驗證碼              ]      │
│ [設定新密碼              ]      │
│ [      確認並登入       ]       │
└────────────────────────────────┘
```

### ⚠️⚠️ 安全性質：唔可以「email 存在就當佢係本人」

```python
# ❌ 災難：任何人打你個 email + 自己嘅密碼 → 接管你個帳號
if user: conn.execute("UPDATE users SET password_hash=? WHERE email=?", ...)

# ✅ 正確：分三種情況
① email 全新                   → 直接建立
② 已存在**而且有密碼**          → 409「已經註冊，去登入」
③ 已存在**但冇密碼**（舊帳號）  → 409 + needs_claim → 要驗證碼
```

**測試**：
```python
def test_register_does_not_auto_claim(self, src):
    assert "password_hash = ?" not in blk, \
        "⚠️ register 竟然會改已存在帳號嘅密碼 —— 帳號可以被搶！"
```

實測：
```
錯驗證碼 → 400 驗證碼唔啱或者過期  ✓ 拒絕
用黑客密碼登入 → 401  ✓ 唔得
```

### ⚠️ 驗證碼邏輯一定要共用一個 helper

```python
def _consume_code(email, code) -> bool:   # ← 唯一一份
```
兩處各寫一份嘅話，將來一定會有一邊改漏
（例如忘記加**次數限制** → 可以暴力破解 6 位數字）。

### ⚠️ 密碼長度要**上限**

PBKDF2 係 CPU-bound，1MB 密碼可以打爆伺服器（DoS）。
```python
if len(pw) > 200: raise HTTPException(400, "密碼太長")
```

### ⚠️ 捉到嘅 bug：`_issue_session` 冇回傳 `onboarded`

前端用 `!user.onboarded` 決定要唔要出新手教學。
漏咗嘅話 `undefined` 係 falsy → **每次登入都會出教學**。

### ⚠️ 捉到嘅 bug：錯誤訊息變 `[object Object]`

FastAPI 嘅 `detail` 可以係**物件**：
```python
raise HTTPException(409, {"detail": "...", "needs_claim": True})
```
前端直接 `new Error(object)` → 用戶見到 `[object Object]`，
而且攞唔到 `needs_claim`。

```js
const d = data?.detail
const msg = typeof d === 'string' ? d
  : (d && typeof d === 'object' && typeof d.detail === 'string') ? d.detail
  : (data?.message || `HTTP ${res.status}`)
const err = new Error(msg)
Object.assign(err, data); if (d && typeof d === 'object') Object.assign(err, d)
```

## 🔑 密碼登入

兩種登入方式並存，自己揀：

```
┌─────────────────────────────────────┐
│  [📧 驗證碼登入]  [🔑 密碼登入]      │
├─────────────────────────────────────┤
│  Email   [you@example.com        ]  │
│  密碼     [••••••••              ]  │
│           [      登入      ]        │
└─────────────────────────────────────┘
```

**⚠️ 密碼儲存嘅設計**（呢啲位寫錯係災難級，但正常用完全唔會發現）：

```python
# PBKDF2-HMAC-SHA256，60 萬次迭代（OWASP 建議）
# 每個用戶獨立 16 bytes 隨機 salt
"pbkdf2_sha256$600000$<salt>$<hash>"
```

| 做啱嘅嘢 | 為咩 |
|---|---|
| **PBKDF2 + 60 萬迭代** | md5/sha1/單次 sha256 一秒撞幾十億次 |
| **每人獨立 salt** | 冇 salt → 兩個同密碼嘅用戶 hash 一樣 |
| **`hmac.compare_digest`** | 用 `==` 會洩漏時間資訊（timing attack） |
| **改密碼要填現有密碼** | 否則有人偷到你部手機就鎖你出嚟 |
| **唔講「冇呢個 email」** | 否則會洩漏邊啲 email 註冊過 |

**測試守住呢啲**（`tests/test_password.py`）：
```python
def test_not_plaintext(self):
    """⚠️ 最緊要：hash 一定唔可以包含原本密碼。"""
    assert "mysecret123" not in _hash_password("mysecret123")

def test_salted(self):
    """⚠️ 同一密碼兩次 hash 一定要唔同。"""
    assert _hash_password("same") != _hash_password("same")
```

## 🏪 附近邊度買得到

購物清單打「合利他命」→ 話你知附近邊幾間藥妝店有得買。

```
🏪 「合利他命」附近邊度買得到
   27 間 · 半徑 1500m · JP · 1 間你收藏咗
─────────────────────────────────────
⭐ 你收藏嘅   ドラッグイレブン 博多店      1113m
💊 藥局      野間薬局                   396m
💊 藥局      マツモトキヨシ               414m
💊 藥局      大賀薬局                   829m
```

貨品名 → 類別 → 用**當地語言**搜尋：

| 輸入 | 判斷類別 | 搜尋關鍵字（日本） |
|---|---|---|
| 合利他命 / 休足時間 / 面膜 | 藥妝 | ドラッグストア・薬局 |
| 白色戀人 / 手信 / 和菓子 | 手信 | お土産・銘品館 |
| 電飯煲 / 吹風機 | 電器 | 家電量販店 |
| Uniqlo 外套 | 衣物 | 衣料品・ユニクロ |

### ⚠️⚠️ 三個服務嘅要求係**相反**嘅

呢個係實測踩過嘅坑，唔可以一個 UA 走天涯：

| 服務 | 要求 | 錯咗會點 |
|---|---|---|
| **DuckDuckGo** | 一定要**完整瀏覽器 UA** | 403 Forbidden |
| **Overpass API** | 一定要**自訂 UA** | **406 Not Acceptable** |
| **Nominatim** | 一定要**當地語言**關鍵字 | 搵到 0 間 |

```
「ドラッグストア」（日文）→ 福岡搵到 20 間  ✅
「drugstore」（英文）    → 福岡搵到 0 間   ❌
```

### ⚠️ Overpass 唔穩定 → 改用 Nominatim 主力

```
逐個 tag 查（10 個 subquery）→ HTTP 504 超時
regex 合併成 1 個           → HTTP 200，快 9 秒
```

但就算合併咗，Overpass 都仍然會一時 200 一時 504。
所以最後設計係：**Nominatim 一回就返，Overpass 用背景 thread 補**。

```
原本順序查：22.5 秒  →  改並行：10.6 秒  →  改「先返」：2.2 秒
```

## ⚠️⚠️ 捉到嘅 bug：`api.myQr is not a function` → 白畫面

**用戶報**：
> 「朋友 QR code 嗰度…生成嗰陣時…佢個畫面一路之後就冇咗」

### 原因

`MyQr.jsx` 喺 `useEffect` 入面叫 `api.myQr()`，
但 `lib/api.js` **從來冇定義過** `myQr`：

```js
// api.js 實際只有：
qr: (url) => req('GET', '/api/qr', ...)

// 但元件叫：
api.myQr()        // ← TypeError!
```

**`TypeError` 喺 `useEffect` 入面拋 → React unmount 成棵樹 → 白畫面。**

同一批仲有 3 個都冇定義：
`lookupUser` / `requestFriendByName` / `decodeQr`（加朋友都用唔到）。

### ⚠️⚠️ 點解測試捉唔到（最重要嘅教訓）

| 檢查 | 內容 | 結果 |
|---|---|---|
| SSR 測試 | 檢查 **MyQr.jsx** 有冇寫 `api.myQr` | ✓ 有寫 → 通過 |
| **冇人檢查** | **api.js** 有冇定義 `api.myQr` | ✗ 冇 → 白畫面 |

> **一個只睇一邊嘅檢查，比冇檢查更危險 ——
>  它會令你以為已經檢查過。**

### 修法：加**雙向交叉檢查**（`tests/web/api.test.mjs`）

```js
// ① 元件用到嘅每一個 api.X → api.js 一定要有
const missing = [...used].filter(k => !defined.has(k))

// ② 反向：定義咗但冇人用（捉死碼）
const unused = [...defined].filter(k => !used.has(k))

// ③ 特別檢查：喺 useEffect 入面叫嘅方法（拋錯 = 白畫面）
```

實測驗證：刪走 `myQr` → **✓ 捉到**
```
✗ api.myQr —— 喺 components/MyQr.jsx 用到，但 api.js 冇定義！
```

### ⚠️ 我犯嘅錯：patch 印「✓」但靜靜失敗

我上次用字串替換加呢四個方法，印咗「✓ api.js: lookupUser / ... / decodeQr」，
但個 anchor 對唔上 → **乜都冇加到**。

> **字串替換 patch 一定要驗證結果**，唔可以信自己印嘅 ✓。

## ⚠️⚠️ 捉到嘅 bug：nav 蓋住彈出嘅表單

**用戶報**（附截圖）：「你見到擺位有啲怪怪地」——
截圖見到「加一筆開支」表單被底部導航欄**劏開兩截**。

### 原因

我為咗令內容浮喺星雲背景上面，加咗：
```css
.app::before { z-index: 0; }                      /* 星雲 */
.app > *:not(.stars) { position: relative; z-index: 2; }   /* 推高內容 */
```

**但 `.nav` 都係 `.app` 嘅直接子元素** → 佢都變成 `z-index: 2`。
而 sheet 喺 `.screen` 入面（都係 2）→ **同一層** → DOM 次序決定：
nav 喺後面 → **nav 蓋住個 sheet**。

### 修法：唔好搶疊層

```css
.app::before { z-index: -1; }   /* ⚠️ 背景沉底，所有內容自然喺上面 */
/* 完全唔需要 `.app > * { z-index }` */
.app::after  { z-index: 500; }  /* 掃描線係純視覺覆蓋層，要喺最上 */
```

實測驗證（DOM 測試）：
```
✓ nav 有 z-index  z-index: 40
✓ 冇「.app > * { z-index }」一刀切規則
✓ 星雲背景 z-index = -1
```

## 🧪 新測試：真 DOM（jsdom）

**用戶報嘅兩個 bug 都係 SSR 捉唔到嘅：**
| 類型 | 為咩 SSR 捉唔到 |
|---|---|
| 點擊之後嘅狀態 | SSR 唔會行 `useEffect`、唔會撳掣 |
| z-index 疊層 | SSR 冇 layout |

`tests/web/dom.test.mjs` 用 **jsdom 掛載真 App**，
行完整流程：開機 → 撳設定 → 撳「重新播放教學」→ 走完教學。

```
✓ 已經過咗開機動畫（booted）
✓ 搵到設定 app icon
✓ 入到設定頁
✓ 撳到「重新播放教學」
✓ 教學彈咗出嚟
✓ 掣唔喺滾動區入面
✓ 去到改名嗰步
✓ 改名嗰步要求必填
```

## 🔁 教學只出一次（DB flag）

**用戶描述**（完全正確）：
> 「你可以喺個 database 度 mark 低，果欄就係零咁解。
>  你一登入去嗰陣時就會有嗰個指令喺度，然後有指令之後佢就會加返一。
>  **只要係零嗰先至會 show** 嗰個顯示出嚟。
>  所以我呢一個帳號登入咗嘅話呢，其實正常就唔應該會有指示嘅出現囉」

### 實際做法

```
users.onboarded = 0  →  登入會出教學
users.onboarded = 1  →  登入唔會出
```

```python
# 完成教學（改名成功）先設 1
conn.execute("UPDATE users SET display_name = ?, onboarded = 1 WHERE id = ?")
```

```jsx
if (user && booted && (!user.onboarded || replayTour)) { … }
```

### ⚠️⚠️ 用戶提醒咗我一個真 bug

加咗 `users.onboarded` 欄位之後，**所有舊用戶都係 NULL** ——
而 NULL 係 falsy → **全部現有帳號登入都會被逼睇新手教學**。

實測：**80 個用戶有 77 個中招**。

修法：一次性 **backfill**（同 schema migration 分開）
```python
BACKFILLS = [
    ("2026-10-08-onboarded-grandfather",
     "UPDATE users SET onboarded = 1 WHERE onboarded IS NULL"),
]
```
配合一個 `_applied_migrations` 表記錄邊啲跑過 ——
⚠️ **唔可以靠「欄位存在就當跑過」**，因為欄位同 backfill 係兩件事。
如果每次啟動都跑，會蓋掉新用戶嘅 `0`。

### ⚠️ 新用戶要**明確**寫 0，唔好靠 NULL

```sql
INSERT INTO users (id, email, display_name, onboarded) VALUES (?, ?, ?, 0)
```
`0 = 未睇教學` 係一個**明確嘅狀態**；靠 NULL 將來加其他欄位好易撞。

實測結果：
```
① 舊帳號  → onboarded=True   ✓ 唔會出教學
② 新帳號  → onboarded=False  ✓ 會出（DB 實際值 0，唔係 NULL）
③ 完成後  → onboarded=True   ✓ 再登入都唔會出
④ NULL 數量: 0 ✓
```

## ▶️ 設定頁「指導教學」

**用戶要求**：
> 「之後嘅話或者你可能整一個喺 setting 有個不同位
>  叫做指導教學，你撳嗰陣時候先至會再出現」

```
設定 → 指導教學
┌────────────────────────────────────┐
│ 新手教學只會喺第一次登入嗰陣出一次。 │
│ 想再睇一次點用？撳下面。             │
│         [▶ 重新播放教學]             │
└────────────────────────────────────┘
```

### ⚠️⚠️ 重看**唔可以**將 onboarded 設返 0

```jsx
onDone={(name) => {
  setUser(prev => ({ ...prev, display_name: name, onboarded: true }))
  if (replayTour) {
    setReplayTour(false)      // 淨係閂 overlay
    setTab('settings')
  } else {
    setTab('trips'); setNewTrip(true)   // 第一次 → 引導開旅程
  }
}}
```

如果重看會設返 0，用戶**重看中途閂咗 app**，下次登入又會強制彈教學。

## 🧑‍🎨 像素角色（程序化生成）

**用戶原話**：「你個示範教學呢第一就係個人物太樣衰啦，
我俾咗啲圖你，你可以參考吓啦」

### ⚠️ 老實講：呢個係「風格」，唔係「插畫」

參考圖嘅角色係**手繪／AI 生成嘅像素插畫**（100+ px、幾十隻色、
分層光影）。我**程序化做唔到同等級**。

但可以做一個**同風格嘅 Q 版角色**：

| | 第一版 | 而家 |
|---|---|---|
| 大細 | 16×16（256 格） | **36×44（1584 格）** |
| 色數 | 1 隻色 | **6 個材質 × 4-5 級 = 26 色** |
| 面 | 冇 | 眼（4 層）＋ 嘴 ＋ 腮紅 |
| 光影 | 冇 | 統一光源（左上）＋ 每格計色階 |
| 描邊 | 冇 | ✓ |
| 頭髮漸變邊 | 冇 | 紫左／青右 |

![像素角色](/tmp/chars_final2.png)

### ⚠️ 點做（唔係手畫）

```python
① 用 PIL 喺**邏輯解析度**畫硬邊橢圓／多邊形
   （⚠️ PIL 喺 1x 冇抗鋸齒 —— 正好就係像素藝術要嘅嘢）
② 每個部件有自己嘅色階（4-5 級）
③ 統一光源方向決定每格用邊一級
④ 加描邊（向外擴一格，唔係向內）
⑤ 套用紫左／青右邊緣漸變
```

### ⚠️⚠️ 捉到嘅 bug：瀏海蓋住對眼

```
瀏海橢圓最低點  y ≈ 16.1
對眼中心        y ≈ 15.6      ← 完全被蓋住！
```

**結果：角色睇落「冇眼」—— 就係用戶話「太樣衰」嘅主因。**

修法：瀏海推高到 `-0.66*ry`、壓扁到 `0.46*ry` → 最低點 y≈12，
眼睛露返出嚟。

**測試**：檢查眼睛帶有足夠嘅暗色像素
```python
band = rgb[int(H*0.28):int(H*0.42), :, :]
dark_ratio = (band.sum(axis=2) < 200).mean()
assert dark_ratio > 0.04, "可能被瀏海蓋住咗"
```

### ⚠️ 第二個 bug：眼似「戴眼鏡」

第一版係「白色橢圓 + 中間深色珠」→ 個白圈睇落似**眼鏡框**。

正確做法（參考圖嘅眼）：
```
① 深色眼眶（眼線）
② 彩色虹膜（填 74%）
③ 瞳孔
④ 大高光（左上）+ 小高光（右下）
```

測試：眼睛帶唔可以有大量純白
```python
assert pure_white < 0.06, "似戴眼鏡"
```

### 重新產生

```bash
cd engine && python make_character.py
python make_character.py --preview   # 出並排預覽
```

## ⚠️⚠️ 捉到嘅 bug：新手教學撳唔到「下一步」

**用戶原話**：「撳到去第一版佢介紹 planner 嗰陣時候呢，
冇一個 button 或者個 bug 太下面啦，
所以導致到你撳唔到之後介紹嘅嘢」

### 原因

```css
.onb-box { max-height: 82vh; overflow-y: auto; }
```
內容同**掣喺同一個滾動區** → 內容長（介紹 Planner 嗰版文字多）
就捲走咗個掣。

而且用咗 `marginTop: -120px` 推個盒 → 內容長會推出畫面外。

### 修法

```css
.onb-box    { display: flex; flex-direction: column; max-height: 78vh; }
.onb-scroll { flex: 1 1 auto; min-height: 0; overflow-y: auto; }  /* 內容可捲 */
.onb-actions{ flex: 0 0 auto; }                                    /* 掣永遠可見 */
```

```jsx
<div className="onb-box" style={{ alignSelf: /* 目標在上半 → 盒喺下 */ }}>
  <div className="onb-scroll"> …內容… </div>
  <div className="onb-actions"> …掣… </div>   ← 喺滾動區外面
</div>
```

## ⚠️⚠️ 百分比排版（用戶要求）

**用戶原話**：「因為每部手機啦個電腦嗰個比例唔一樣嘅話，
我唔建議你嗰個 Apps 係整到係用數量囉，
你應該用 percentage 表達」

### 修法：純百分比 grid

```css
.app-grid {
  /* ⚠️ 完全冇 px */
  grid-template-columns: repeat(auto-fit, minmax(22%, 1fr));
  gap: 3.5% 1.5%;
}
.app-ico { width: 100%; aspect-ratio: 1; }      /* 填滿格 */
.app-ico .pxi svg { width: 58%; height: 58%; }  /* 格嘅 58% */
```

**22% 係計出嚟嘅**：
```
4 欄 × 22% + 3 × 1.5% = 92.5%  ≤ 100%  ✓
5 欄 × 22% + 4 × 1.5% = 116%   > 100%  ✗
```

實測：
| 手機 | 闊 | 欄數 | 每格 | 圖示(58%) |
|---|---|---|---|---|
| iPhone SE | 320px | 4 | 70px | 41px |
| Android 細機 | 360px | 4 | 79px | 46px |
| iPhone 13/14 | 390px | 4 | 86px | 50px |
| iPhone 15 PM | 430px | 4 | 94px | 55px |

⚠️ 我**故意反轉**咗一個舊測試 ——
之前檢查「固定 4 欄」，而家檢查「**唔可以**寫死欄數」。

## 🧭 新手教學（Onboarding）

**用戶要求**：
> 「如果你去註冊一個新用戶，首先登入咗之後出現咗個 Animation 之後呢，
>  然後就會第一次用嘅話呢係可以會有一個示範教學點樣去用嘅，
>  就例如你可能有一個提示啊，例如圈出嚟點樣去用啊，
>  或者可能你可以用嗰「Pixel 風」風格嘅人物去介紹呢個 Apps 係點用啦，
>  咁然後之後呢佢就會同你講話你叫乜嘢名，咁呢個時候呢你就可以改你嘅名叫乜嘢名，
>  **呢個係必做嘅**。」

### 流程

```
登入 → 開機動畫 → ① 吉祥物打招呼
                → ② 逐個 app「圈出嚟」講解 ×4
                → ③ 你叫乜嘢名？（必填）
                → ④ 搞掂
```

![新手教學流程](/tmp/onboarding.png)

### ⚠️⚠️ 為咩「圈出嚟」而唔係彈一段文字

```
❌ 彈一段文字：「Planner 可以幫你排行程…」
   → 手機用戶唔會睇，直接撳「下一步」

✅ 用聚光燈圈住實際嗰粒掣 + 一句解釋
   → 用戶一眼就知邊度撳
```

做法係 **SVG mask 挖窿**：
```jsx
<mask id="onb-hole">
  <rect width="100%" height="100%" fill="white" />
  <rect x={rect.left} y={rect.top}
        width={rect.width} height={rect.height} fill="black" />  {/* 挖窿 */}
</mask>
<rect width="100%" height="100%" fill="rgba(4,2,10,.86)" mask="url(#onb-hole)" />
```

位置用 `getBoundingClientRect()` 即時量度，跟住 `resize` / `scroll` 重新量。

### ⚠️⚠️ 為咩最後一定要填名（用戶明確要求）

冇名嘅話：
```
行程成員   →  you@example.com
分帳       →  usr_x7Kd9 要比 $200 畀 usr_p2Nm4
購物清單   →  （空白）
```
完全唔知邊個係邊個。所以寧願喺呢一步逼一逼。

**⚠️ 關鍵設計**：`onboarded = 1` **只有喺改名成功之後**先設定。
```python
name = (body.display_name or "").strip()
if not name:
    raise HTTPException(400, "請填你嘅名")
with db.connect() as conn:
    conn.execute("UPDATE users SET display_name = ?, onboarded = 1 WHERE id = ?", ...)
```
→ 用戶中途閂咗個 app，下次登入會**再見到教學**
→ 唔會出現「未改名但當佢完成咗」嘅狀態

### ⚠️⚠️ 為咩用後端 flag 而唔用 localStorage

| 做法 | 換機／清 cache |
|---|---|
| `localStorage` | ❌ 冇咗 → 用戶**再睇一次**教學 |
| `users.onboarded` ✅ | ✓ 跨機都準確 |

### ⚠️ 一定要喺開機動畫**之後**先出

```jsx
if (user && !booted) return <BootScreen />          // ① 先播動畫
if (user && booted && !user.onboarded) return <... />  // ② 再出教學
```
同時出嘅話，兩個全螢幕組件會**疊埋一齊**。

### ⚠️ 捉到嘅 bug：吉祥物雙手係「孤立嘅島」

`happy` frame 第一版：
```
row 1  '..1..........1..'   ← 手
row 2  '..1..........1..'
row 3  '...1111111111...'   ← 身（唔接！）
```
結果隻手係兩個**同身體斷開嘅島**，睇落似飛出嚟嘅碎片。

**修法**：加 `row 2` 嘅 x=3 同 x=12 斜住連返膊頭。

**測試**：用 flood fill 檢查所有像素連成一體。
```python
# 由最頂嘅像素開始 flood fill
seen, stack = {start}, [start]
while stack:
    x, y = stack.pop()
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):     # ⚠️ 斜角唔算連通
        q = (x+dx, y+dy)
        if q in filled and q not in seen:
            seen.add(q); stack.append(q)
islands = filled - seen
assert not islands, f"有 {len(islands)} 格係孤立嘅島"
```

驗證：還原成壞版本 → **✓ 捉到**。

## 📷 QR Code 唯一性 + 「唔可以加自己做朋友」

### ① 每個 account 嘅 QR 都唔同 ✅

**用戶問**：
> 「我要確定嘅就係係咪每一個 Account 都係有唔同嘅 QR code？」

**答：係。** QR 內容 = `http://<ip>:8787/?add=<username>`，
而 `username` 有 **UNIQUE 約束**：

```sql
username  TEXT UNIQUE        -- ⚠️ QR 唯一性完全依賴呢個
```

⚠️ 如果冇 UNIQUE，兩個 account 可以有同一個 QR。

實測（6 個 account）：
```
@za91172  hash=4799335fce   ...?add=za91172
@zb91172  hash=a8ad2c8806   ...?add=zb91172
@zc91172  hash=04dbfcadee   ...?add=zc91172
URL 唔重複: 6/6     SVG 唔重複: 6/6
```

⚠️ QR **唔含** token / email —— 只含 username。
（QR 會畀人截圖／貼上網，唔可以有敏感資料。）

### ② 掃到自己 → 「唔可以加自己做朋友」

**用戶要求**：
> 「如果當自己 scan 到自己嘅 QR code 嘅話，
>  應該係知道係自己嚟嘅，
>  咁你就要同佢講就話『唔可以加自己做朋友』。」

### ⚠️⚠️ 四個入口都要檢查

| # | 入口 | 情況 |
|---|---|---|
| ① | 設定 → 我嘅 QR → 掃人哋 | 你上傳自己嘅 QR 圖 |
| ② | 朋友 → 掃 QR Code | 同上 |
| ③ | 朋友 → 打 @名 | 你打自己個 @名 |
| ④ | **手機原生相機**掃自己個 QR | 開 app 帶住 `?add=自己` |

⚠️ ④ 最易漏 —— 因為唔經我哋個 app 嘅掃描器。

### ⚠️⚠️ 一定要共用一個函數

```js
// web/src/lib/selfcheck.js
export function isSelf(scanned, me) {
  const a = norm(scanned), b = norm(me?.username)
  if (!a || !b) return false
  return a === b
}
export const SELF_MSG = '唔可以加自己做朋友'
```

四個入口各寫一份嘅話，將來一定會有一邊改漏
（例如支援大寫之後有一邊忘記 `toLowerCase`）。

### ⚠️ 檢查一定要喺「動作」**之前**

```js
if (isSelf(r.username, user)) {
  setSelfHit(r.username); toast(`⚠️ ${SELF_MSG}`); return   // ← 先
}
onFound?.(r.username)                                        // ← 後
```
否則會照樣複製 `@自己` 然後叫你去加自己。

### ⚠️ 後端都要擋（前端可以被繞過）

```python
if target["id"] == user["id"]:
    raise HTTPException(400, "唔可以加自己做朋友")
```
用 `curl` 可以直接打 API —— 前端檢查擋唔到。

實測：
```
加自己        → 400  唔可以加自己做朋友   ✓
用 @大寫加自己 → 400  唔可以加自己做朋友   ✓
```

### 測試守住「所有入口都有檢查」

```python
@pytest.mark.parametrize("f,label", [
    ("components/MyQr.jsx", "① 設定頁掃人哋"),
    ("components/Friends.jsx", "② 朋友頁掃 QR"),
    ("App.jsx", "④ Deep link ?add="),
])
def test_entry_points_check_self(self, f, label):
    assert "isSelf(" in src
```

## 🌌 星雲風格（由參考圖抽出嘅色板）

**用戶要求**：提供參考圖（星雲手機壁紙、彗星 app icon、
紫調房間插畫、紫青邊緣嘅像素角色），並講明「**我要呢一種風格**」。

### ⚠️⚠️ 首先要講清楚（唔可以含糊）

參考圖係 **AI 生成嘅插畫**。我**冇能力**生成同等級嘅插畫，
亦都**唔應該**假裝做得到。

但參考圖最核心嘅「**風格**」係可以**程序化複製**嘅：

| 可以複製 | 唔可以複製 |
|---|---|
| ✅ 色板（由參考圖統計抽出） | ❌ 手繪角色插畫（100+ px 細節） |
| ✅ 星雲結構（fBm 噪音） | ❌ 房間場景構圖 |
| ✅ 大顆粒 + Bayer 抖動 | ❌ 光影敍事 |
| ✅ 紫左／青右邊緣漸變 | |
| ✅ 掃描線 | |

所以我做嘅係「**風格**」而唔係「**插畫**」——
`engine/make_pixelart.py` 係一個**程序化生成器**。

### 抽出嚟嘅實際色板（唔係估）

```
太空底色      #000010 → #000020 → #000030 → #100040 → #200060
星雲中調      #402090  #5020A0  #6030A0  #7050C0
星雲亮部      #A070C0  #B080C0  #C0A0D0
星雲核心      #E0C0E8  #F0D8F0

⭐ 邊緣紫（左）  #E73AB8  #FC53EC      ← H≈306-316°
⭐ 邊緣青（右）  #32E4FF  #08D0EA      ← H≈187°
暖金點綴        #985030  #C08040      ← 房間圖嘅燈光
```

**紫左／青右邊緣漸變**係最 signature 嘅特徵 ——
模擬舊 CRT 嘅色差（chromatic aberration）。

### ⚠️ 調參試過嘅版本（全部記錄低，防止將來改返壞）

| 參數 | 試過 | 結果 |
|---|---|---|
| gamma | 1.55 | 太光，成張圖都著色 |
| | 1.75 | 仲係太光（雲佔滿畫面） |
| | 2.60 | 太暗，只剩一條幼線 |
| | **2.05** ✅ | 大片黑 + 雲帶清楚 |
| 星帶數 | 1 條幼帶 | 似「一條蛇」 |
| | **2 條寬帶** ✅ | 似雲海 |
| 色板 | 單一 | 一種色調，好平 |
| | **藍 + 紫雙色板混合** ✅ | 藍紫交錯 |
| 邏輯解析度 | 48×96 ×8 | 一粒星變 **8×8 白色大方格** |
| | **96×192 ×4** ✅ | 4×4，比例正確 |

### ⚠️ 量化驗證：暗部比例

唔可以靠肉眼判斷「夠唔夠暗」—— 用數字：

```
參考圖 近黑比例（RGB 總和 < 60）: 47%
生成圖 近黑比例:                  45%   ✓
```

### ⚠️ 捉到嘅 bug：邊緣效果喺 app 完全睇唔出

第一版 `chromatic_edge` 只染「緊貼邊緣 1px」嘅像素，
而且權重用全圖寬度做線性 → 中間位置只係 ±0.1，等於冇效果。

**修法**：
1. 將邊緣**膨脹** 2 格（用 4 方向 max filter）
2. 改用飽和曲線 `clip(x/0.35)` 計權重
3. 強度由 0.95 調到 0.45（0.95 會蓋過星雲本身嘅色，變一片霓虹）

### 產生嘅檔案

```
web/public/icon-512.png          app icon（彗星 + 星雲）
web/public/icon-192.png          PWA
web/public/icon-180.png          iOS apple-touch-icon
web/public/icon-maskable-*.png   Android（留 66% 安全區）
web/public/nebula.png            手機背景 384×768
web/public/nebula-wide.png       橫向／桌面 768×432
web/public/comet.png             透明彗星（UI 用）
web/public/comet-96.png          小圖示
```

重新產生：
```bash
cd engine && python make_pixelart.py
```

## 🔍 App 圖示大細

**用戶要求**：
> 「你個圖可以帶少少帶 **1.1 倍至 1.2 倍**，
>  同埋**要下少少**，咁就會好睇好多。」

### ⚠️⚠️ 一查之下發現「雙重縮細」bug

```jsx
<PixelIcon size={38} />                    // ① .pxi span = 38px（inline style）
```
```css
.app-ico .pxi svg { width: 58%; }          /* ② svg = 38 × 58% = 22px */
```

**縮咗兩次** → 圖示實際只有 **22px**，佔瓦片嘅 **33-42%**。

而且 22px 係**固定**嘅 —— 瓦片由 52px 變到 66px，
圖示永遠 22px → **唔會隨瓦片縮放**（第二個 bug）。

### 修法

```css
:root {
  --ico-w: 52%;   /* 圖示佔瓦片嘅百分比 */
  --ico-y: 4%;    /* 向下移（光學置中）*/
}

.app-ico .pxi {
  width: var(--ico-w) !important;    /* ⚠️ !important 蓋 inline px */
  height: var(--ico-w) !important;
  transform: translateY(var(--ico-y));
}
.app-ico .pxi svg {
  width: 100% !important;            /* ⚠️ 唔再縮第二次 */
  height: 100% !important;
}
```

### ⚠️ 為咩要「向下移少少」

圖示嘅**視覺重心偏上** —— 尤其係有「腳」嘅圖案（Trips 文件夾、
Friends 兩個人）。幾何置中會睇落「浮起」。

移低 **4%** 就啱（唔可以太多，否則又會覺得「沉」）。

### 實際效果

| 手機 | 瓦片 | 之前 | 而家 | 倍數 |
|---|---|---|---|---|
| iPhone SE | 52px | 22px | **27px** | 1.23× |
| Android | 52px | 22px | **27px** | 1.23× |
| iPhone 13 | 57px | 22px | **29px** | 1.33× |
| iPhone 15 PM | 62px | 22px | **32px** | 1.47× |

![圖示大細選項](/tmp/icon_options.png)

### ⚠️ 一條變數就調到

想再大／細？改 `--ico-w` 就得（唔使搵散落各處嘅 px）：
```css
--ico-w: 62%;   /* 更似 app icon */
--ico-w: 44%;   /* 保守 */
```

## 🔘 圓角系統（iPhone 風格）

**用戶要求**：
> 「不過框框嘅弧度你可以參考吓 iPhone 嗰種弧度囉，
>  因為正方形長方形呢個好難睇，或者係想要有少少弧度嘅感覺。
>  所以你應該要將**所有嘅嘢**啦，唔好淨係一個長方形，
>  而係真係要有少少嘅弧度。」

### ⚠️ 呢個唔止係審美 —— 係**可讀性**問題

| 直角框 | 圓角框 |
|---|---|
| 深色背景上「拮眼」，眼睛要處理 4 個硬轉角 | 視線自然流向中間 |
| 內容同邊框嘅視覺張力唔平均 | 內容更易讀 |

### ⚠️⚠️ 之前嘅問題：**三個圓角來源，唔一致**

```css
--r: 14px;        /* 原本嘅 */
--r-sm: 9px;      /* 原本嘅 */
--px-r: 2px;      /* 像素風 CSS 加嘅，仲要用 !important 蓋 */
```

結果：**有啲位圓（9px）、有啲位方（2px）** ——
用戶唔會識講「呢度圓嗰度方」，只會覺得「怪」。

### 修法：一套 scale（跟 iPhone 實際數值）

```css
:root {
  --r-xs:   8px;    /* 細標籤：chip / badge / 縮圖 */
  --r-sm:  12px;    /* 中：按鈕 / 輸入框 */
  --r:     18px;    /* 大：卡片 / 面板 */
  --r-lg:  26px;    /* 特大：modal / sheet 頂 */
  --r-full: 999px;  /* 膠囊 */
  --r-ico:  24%;    /* ⚠️ App icon 用**百分比** */
}
```

![圓角對比](/tmp/radius.png)

### ⚠️ App icon 一定要用**百分比**

```css
.app-ico { border-radius: var(--r-ico); }   /* 24% */
```
iPhone app icon 係 **22.37%**（squircle）。用百分比而唔係 px ——
因為百分比會隨 icon 大細自動縮放，
固定 px 會喺細 icon（41px）睇落太圓、喺大 icon（55px）睇落太方。

### ⚠️ 但呢啲**故意**保持細圓角

| 元素 | 圓角 | 為咩 |
|---|---|---|
| `.stars i` 星星點 | 1px | 係「點」唔係「框」 |
| `.thumb::after` ⤢ 標記 | 4px | 細標記 |
| 進度條 / 分隔線 | 99px | 膠囊（線） |

> **唔可以一刀切全部改大** —— 否則會失去像素感。

### ⚠️ 內層 card 用小一級

```css
.card .card     { border-radius: var(--r-sm); }
.card .card .card { border-radius: var(--r-xs); }
```
唔係嘅話會出現「框中有框同一個圓角」嘅笨重感。

### ⚠️ Sheet 只圓上面兩隻角

```css
border-radius: var(--r-lg) var(--r-lg) 0 0;
```
下面貼住螢幕邊，圓咗會露出背景。

### 測試守住一致性

```js
// scale 要遞增 + 每個都唔可以細過某個值（唔會睇落係方角）
--r-xs ≥ 6px   --r-sm ≥ 10px   --r ≥ 14px   --r-lg ≥ 20px

// App icon 用百分比，而且要喺 iPhone 範圍
pct >= 20 && pct <= 26

// 元件唔可以再有「容器級」硬編碼圓角
if (v > 6 && v < 90) bad.push(...)
```

實測：**99 個響應式／圓角測試全部通過**

## 🎮 Pixel Art UI（像素／點陣風格）

**用戶要求**：
> 「Pixel Art（像素藝術 / 點陣圖）… 廣東話通常會叫呢種風格做
>  「Pixel 風」或者「點陣風格」，UI 係呢種嘅風格」

### 像素風嘅四條規則（缺一不可）

| # | 規則 | 為咩 |
|---|---|---|
| ① | **冇圓角** | 圓角係「現代扁平」嘅語言，同像素硬邊相反 |
| ② | **硬邊陰影（0 blur）** | `0 4px 12px` = 模糊 = 唔像素；`4px 4px 0` = 硬偏移 |
| ③ | **粗邊框 2-3px 實線** | 像素圖一定有黑邊 |
| ④ | **冇毛玻璃／漸變模糊** | `backdrop-filter` 同像素風衝突 |

```css
:root { --px: 3px; --px-r: 2px; }   /* ⚠️ 一定用偶數 px */

.card  { border-radius: var(--px-r) !important; border-width: var(--px) !important;
         box-shadow: var(--px) var(--px) 0 rgba(0,0,0,.45) !important; }
.btn:active { transform: translate(var(--px), var(--px));
              box-shadow: 0 0 0; }   /* 撳落去「沉一格」 */
```

### ⚠️⚠️ 最大工程：app icon 由 emoji 換成像素圖

原本主畫面係 **emoji**（🗓 📥 💸 🛒 🧭 🗺 👥 ⚙️ 🗂）。
Emoji 同像素風**根本衝突**：

| 問題 | 影響 |
|---|---|
| 每部機完全唔同樣 | Apple 立體彩色、Google 平面、Samsung 又一款 |
| **冇得控制線條粗細** | 唔可能做到點陣感 |
| 舊 Android 出黑白／豆腐格 | 直接睇唔到 |

所以自己畫咗 **19 個 8×8 像素圖示**（`web/src/lib/pixelicons.js`）。

### ⚠️ 兩個一定要做嘅細節

**① `shape-rendering="crispEdges"`**
```xml
<svg shape-rendering="crispEdges">
```
冇佢瀏覽器會做 anti-aliasing → 格與格之間出現灰邊 → 就唔係「硬邊像素」。

**② 像素字體唔可以套用中文**
```css
.pix { font-family: var(--font-pix); }   /* Press Start 2P */
```
**Press Start 2P 冇中文字** —— 中文用佢會出豆腐格（□□□）。
所以只套用喺純英文（`Planner`、`Money`），中文留返系統字體。

### ⚠️ 捉到嘅 bug：5 個圖示調色板索引超出

同頭像一樣嘅問題 —— 程式會 fallback 去 `pal[0]`，
**唔會有任何錯誤**，只係顏色靜靜錯咗。

```
✗ money    pal=3色  用 [1,2,3]  超出 [3]
✗ map      pal=3色  用 [1,2,3]  超出 [3]
✗ plus     pal=1色  用 [1]      超出 [1]
✗ pin      pal=2色  用 [1,2]    超出 [2]
✗ globe    pal=3色  用 [1,2,3]  超出 [3]
```

1216 格（19 × 64）靠肉眼睇唔晒 —— 一定要程式檢查。

### ⚠️ 仲要「測試個測試」

```
驗證測試真係捉得到（餵已知壞 input）：
  ✓ 捉到  索引超出調色板     → test_chars_valid
  ✓ 捉到  行少一格          → test_square_grid
  ✓ 捉到  非法字元          → test_chars_valid
  ✓ 捉到  顏色唔係 hex      → test_colors_hex
  ✓ 捉到  刪走 money 圖示   → test_app_has_icon
```

## ⚠️⚠️ 捉到嘅 bug：撳「設定」出「先揀一個旅程」

**用戶報**：「點解而家整極個 setting 撳入去都係冇嘢嘅？」

### 原因

```jsx
{!isHome && tab !== 'trips' && !inTrip && (
  <div className="h1">先揀一個旅程</div>     ← 撳「設定」都出呢個！
```

**⚙️ 設定同 👥 朋友完全唔需要旅程**（改頭像、加朋友、改密碼
全部係帳號層面嘅事），但都被呢個閘擋住。

### 修法：抽出 `TRIP_APPS` 做單一真相來源

```js
const TRIP_APPS = ['discover', 'calendar', 'money', 'shopping', 'zones', 'map']

// 兩處共用：
//   ① openApp() 撳 app icon 嗰陣
//   ② render 決定要唔要出「先揀一個旅程」
```

⚠️ 如果兩處各寫一份清單，將來一定會唔同步。

### 順手捉到：`!inTrip` 分支漏傳 `onUserUpdate`

```jsx
{!inTrip && tab === 'settings' && (
  <Settings ... />       ← 冇 onUserUpdate！
)}
```
改頭像／帳號名會叫 `onUserUpdate?.()` 但係 `undefined`
→ **靜靜咁失敗**（「`?.` 令佢唔會拋錯，所以更難發現」）。

## ⚠️⚠️ 捉到嘅 bug：香港行程顯示福岡地圖

**用戶報**：開咗個香港 trip，地圖出福岡。

### 原因

```
trip「hk」  destination = '香港'      ← 用戶打喺「目的地」欄
            trip_stops  = （空）      ← 但地圖只讀呢個！
                    ↓
            地圖跌落硬編碼 fallback（33.59, 130.40 = 福岡）
```

**用戶嘅資料冇錯，係我哋冇將「目的地」當一回事。**

### 修法（三層）

| 層 | 改咗咩 |
|---|---|
| **後端** | `destination` 自動推導成 `trip_stops`（查座標 + 寫入） |
| **地圖** | 移除硬編碼福岡 → 冇座標時用中立世界視角 |
| **UI** | 目的地改用 **CityPicker**（揀，唔係打字） |

### ⚠️ 順手捉到第二個 bug：幽靈城市

舊 code 喺冇城市時**合成**一個假嘅：
```python
rows = [{"id": None, "city": trip["destination"], ...}]   # 冇 lat/lng
```

兩個問題：
1. `id: None` → React key 撞、撳「刪除」會亂、地圖 `filter(s => s.lat != null)` 剔走佢 → **地圖仍然冇中心**
2. 用戶見到城市名喺清單度，以為設定好咗 → **唔會知要再設定**

**寧願誠實咁顯示「未設定城市」，都唔好顯示一個假嘅。**

## 🌏 城市選擇器（CityPicker）

**用戶要求**：
> 「會唔會你個 planner 你嘅城市係俾人選擇而唔係打字入去囉。
>  例如你可以打英文或者打中文繁中，然後打某些字就會出對應近似嘅答案，
>  咁你就去撳佢囉。例如你打到 Hong Kong，打到個 hong 呢個字之後
>  就可能會出現到原來有香港呢個城市」

```
┌────────────────────────────────────┐
│ 🌏 [hong              ]            │
├────────────────────────────────────┤
│ 📍 Hong Kong  hongkong             │  ← Enter ↵
│    香港 · 740萬人                   │
├────────────────────────────────────┤
│ 📍 Hongkou                          │
│    中國 · 75萬人                    │
└────────────────────────────────────┘
```

用**本地 134,655 個城市名索引**（中／英／日／韓／諺文），
搜尋 0.03ms，唔使上網。

### ⚠️⚠️ 排序：打 `hong` 唔可以出 Hangzhou

索引係「**任何語言嘅別名** → 記錄」。Hangzhou 有個韓文羅馬拼音別名
`hongchusu`，所以 `startswith("hong")` 都會中 —— 而且佢人口（750萬）
**仲多過香港**（740萬），單靠人口排序就會出錯。

```python
if   canonical == key:  sc = 100   # 打 "tokyo" → Tokyo
elif canonical.startswith(key): sc = 80   # 打 "hong"  → Hong Kong  ← 關鍵
elif matched == key:    sc = 60   # 打 "香港"  → Hong Kong
else:                   sc = 35   # 打 "hong"  → Hangzhou（別名）
sc += min(20, log10(pop) * 2.2)   # ⚠️ 用 log，否則東京壓死一切
sc -= min(6, (len(matched) - len(key)) * 0.35)
```

實測：
```
hong   → Hong Kong(hongkong) | Hongkou | Hongjiang | Honghe   ✓
香港    → Hong Kong(香港) | Hong Kong Island(香港岛) | Aberdeen(香港仔)
香     → Hong Kong(香港) | Hong Kong Island | Aberdeen
tok    → Tokyo(tokio) | Tokat | Tokushima | Tokoza
台     → Taipei(台北) | Taichung(台中) | Tainan(台南) | Taizhou(台州)
```

**⚠️ 單一個字都要搜到** —— 原本 ≥2 個字先搜，但咁樣用戶打第一個字
冇反應，會以為壞咗。

## ⚠️ 捉到嘅 bug：畫面上多咗個 `)}`

**用戶報（附截圖）**：主畫面 Planner 上面有個 `)}` 符號。

### 原因

`HomeScreen.jsx` 有個**多餘嘅 `)}`**：
```jsx
      )}
      )}      ← 呢行變成純文字！
```

喺 JSX 入面，**括號外面嘅任何文字都會原樣 render**。
所以 `)}` 就變成畫面上面嘅文字。

### ⚠️⚠️ 為咩 build 同測試都捉唔到

| 檢查 | 為咩捉唔到 |
|---|---|
| `vite build` | 只做語法／import 解析 —— `)}` 係**合法嘅 JSX 文字** |
| 我原本嘅 SSR 測試 | 只檢查「有冇預期字串」—— **多咗字唔會發現** |

### 修法唔止刪走嗰兩行

加咗一個**通用 JSX 殘留檢查**，每次 render 都自動掃：

```js
const JSX_LEAKS = [
  /\)\}/, /\]\}/, /\/>/, /\{"/, /"\}/, /className=/,
  /style=\{\{/, /React\.createElement/,
  /\bundefined\b/, /(?<![A-Za-z])NaN(?![A-Za-z])/, /\[object Object\]/,
]

function findLeaks(html) {
  // 去 <script>/<style> → 去所有 tag → 解 entity → 掃殘留
}
```

### ⚠️ 仲要「測試個測試」

一個永遠話「通過」嘅檢查**比冇檢查更差**。所以先餵已知壞 input：

```
▸ ⚠️ 驗證 JSX 殘留檢查器（餵已知壞 input）
    ✓ 捉到「多餘 )}」        )} @ …Planner )} Organize…
    ✓ 捉到「多餘 ]}」        ]} @ …清單]}…
    ✓ 捉到「漏咗 tag 結尾」    /> @ …Hello/>…
    ✓ 捉到「className 漏咗」  className= @ …文字 className= 殘…
    ✓ 捉到「undefined」      undefined @ …名字：undefined…
    ✓ 捉到「[object Object]」
    ✓ 捉到「NaN」
    ✓ 唔會誤報「正常內容」
    ✓ 唔會誤報「含符號但正常」
    ✓ 唔會誤報「百分比」
    ✓ 唔會誤報「Undefined 品牌名」   ← word boundary 好重要
    ✓ 唔會誤報「Nan 地名」
```

**⚠️ word boundary 嘅重要性**：用 `includes('undefined')` 會令
「**Undefined** Coffee」（真店名）誤報。要用 `\bundefined\b`。

## 📱 手機排版（響應式）

⚠️ 用戶報：「每一部手機佢哋嘅大細闊度都唔一樣」

真實手機闊度範圍好大：
```
320px  iPhone SE (1st)      390px  iPhone 13/14
360px  大部分 Android        414px  iPhone 11/XR
375px  iPhone SE2/8         430px  iPhone 15 Pro Max
```

### ⚠️ 為咩用 `clamp()` 而唔係 media query

media query 只可以喺**斷點跳級** —— 360px 同 430px 之間用同一個 size。
但手機闊度係**連續變化**嘅，所以用 `clamp(最少, 隨闊度, 最多)`。

```css
.item .ic { width: clamp(42px, 12.5vw, 54px); }
.thumb    { width: clamp(52px, 15vw, 68px); }
.h1       { font-size: clamp(19px, 5.6vw, 23px); }
```

實際效果：
| 手機 | 闊 | 縮圖 | 圖示格 | 邊距 |
|---|---|---|---|---|
| iPhone SE | 320px | 52px | 42px | 12.8px |
| Android 細機 | 360px | 54px | 45px | 14.4px |
| iPhone 13/14 | 390px | 58.5px | 48.8px | 15.6px |
| iPhone 15 PM | 430px | 64.5px | 53.8px | 17.2px |

### ⚠️⚠️ 兩個「靜靜死」嘅陷阱

**① CSS 用咗 `var(--safe-t)` 但冇定義**
```css
.lightbox { padding: calc(12px + var(--safe-t)) ...; }  /* --safe-t 冇定義 */
```
→ **成個 declaration 被丟棄** → 個 ✕ 掣被 iPhone 動態島遮住。
（實測踩過！）

**② 固定 px 喺 320px 機會爆，但喺 430px 睇落正常**
```
主畫面：padding 22px×2 = 44px → 剩 276px
        4 個 icon × 62px + gap 30px = 278px  →  爆 2px ❌
```
開發者用大機測試**永遠唔會發現**。

### 測試守住呢兩點

`tests/web/responsive.test.mjs`（33 個）：
```js
// 用咗嘅 CSS 變數一定要有定義
const missing = [...used].filter(v => !defined.has(v))
check('全部 27 個變數都有定義', missing.length === 0)

// 每個真實手機闊度都要夠位放文字
for (const [name, w] of PHONES) {
  const text = avail - thumb - checkbox - delBtn - gap*3
  check(`${name} (${w}px) 文字有 ${text}px`, text >= 110)
}
```

實測結果：
```
✓ 320px  文字有 147px   縮圖 52px
✓ 375px  文字有 183px   縮圖 56px
✓ 430px  文字有 221px   縮圖 65px
✓ 320px: 4 欄 × 52px 夠位  231px / 288px
```

## 📷 購物清單相片

```
[要買咩？          ] [數量] [＋]
🎁手信 💊藥妝 🍫食品 👕衣物 …
[單價] [邊個買 ▼]
[📷 加相]  [🏪 附近邊度買]
```

**⚠️ 列表用正方形縮圖，撳一下睇全圖**：
```
┌──────────────────────────────────────┐
│ ┌────┐ ☐ 🎁 白色戀人 × 3 盒  ¥1,200  │
│ │相片│                         ✕     │
│ └────┘                               │
└──────────────────────────────────────┘
     ↑ 撳一下
┌──────────────────────────────────────┐
│                                      │
│         （全圖，唔會被裁）             │
│                                      │
│           白色戀人                    │
│      3 盒 · Alice 買                  │
└──────────────────────────────────────┘
```

**⚠️ 為咩列表用正方形**：手機影嘅相通常係 3:4 或 9:16（直向）。
直接擺入列表 → 一係拉長成條 row（好樣衰），一係裁到剩中間。
正方形縮圖令**每行高度一致，列表整齊**，再用 `object-position: center 45%`
（主體通常中間偏上）避免裁到主體。想睇清楚就撳一下開全圖（`object-fit: contain`）。

**⚠️ 前端一定要縮圖**：
```
手機影相 4MB → base64 5.3MB → 上傳十幾秒
縮到 1200px + JPEG 0.82 → 約 250KB → 快 15 倍
```
（購物清單嘅相只係用嚟認貨，唔需要原相）

**⚠️ 後端用 magic bytes 驗證，唔用大小**：
```python
raw[:8] == b"\x89PNG\r\n\x1a\n"          # PNG
or raw[:3] == b"\xff\xd8\xff"              # JPEG
or (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
```
原因：1×1 PNG 只有 70 bytes，用大小判斷會誤殺；而且防止有人
上傳 `.php` / `.html` 改名做 `.png`（SVG 直接拒絕，因為可以帶 script = XSS）。

## 📱 手機用得到嗎？

**得，但要同一個 WiFi。** 電腦同手機連同一個網絡，然後：

### 最簡單：掃 QR Code

設定頁 →「📱 手機連線」→ 出一個 QR Code → 手機相機掃一下。

```
┌──────────────────┐
│ █▀▀▀█ ▄▀ █▀▀▀█   │
│ █ ▄▄▄█ ▀▄ █ ▄▄▄█  │   http://192.168.1.150:8787
│ █▄▄▄█ █▀ █▄▄▄█   │
└──────────────────┘
      [複製連結] [重新產生]
```

> ⚠️ 唔使喺手機打 `192.168.1.150:8787` 呢串嘢 —— 掃一下就得。

### ⚠️ http:// 嘅限制（老實講）

| 功能 | http://192.168.x.x | https:// |
|---|---|---|
| 開得到、用到 | ✅ | ✅ |
| 加到主畫面有正確 icon | ✅（PNG apple-touch-icon） | ✅ |
| **離線功能** | ❌ | ✅ |
| **剪貼簿 API**（書籤小工具用） | ❌ | ✅ |
| Web Share Target（IG 分享 → Wander） | ❌ | ✅ |

原因：瀏覽器規定 **service worker 同 clipboard API 只喺「secure context」先准用**，
而 `http://` 區網 IP **唔算** secure context（`localhost` 同 `https://` 才算）。

**想全部功能都用得 → 要 HTTPS。** 免費方法：
```bash
# cloudflared（免費 tunnel，唔使註冊）
brew install cloudflared
cloudflared tunnel --url http://localhost:8787
# → 會俾你一個 https://xxx.trycloudflare.com
```

### 手機專用設定（已做好）

```html
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />

<!-- ⚠️ iOS 完全唔支援 SVG icon -->
<link rel="apple-touch-icon" sizes="180x180" href="/icon-180.png" />
```

```
web/public/
  icon-180.png            ← iOS 加到主畫面
  icon-192.png            ← Android
  icon-512.png            ← PWA splash
  icon-maskable-192/512   ← Android 自適應（留咗安全邊）
  icon.svg                ← 向量版（桌面 browser tab）
```

**⚠️ 踩過嘅坑**：iOS **完全唔支援 SVG icon**。
如果冇 `apple-touch-icon`，iOS「加到主畫面」會用**網頁截圖**做 icon（好難睇）。
所以一定要 PNG 180×180。

### QR Code 係自己寫嘅（零依賴）

```
engine/wander/qr.py   ← 純 Python QR encoder，冇用任何套件
```

自己寫 QR encoder 最恐怖嘅地方：**錯咗唔會有錯誤訊息，只會「掃唔到」**。
結構檢查（finder pattern 啱唔啱）完全捉唔到 format info transpose、
mask 冇應用到、資料放置次序錯 呢類 bug。

所以測試用 **OpenCV 真解碼**驗證：
```python
@pytest.mark.parametrize("text", SAMPLES)
def test_roundtrip(self, text):
    """⚠️ 最重要：真解碼。「畫得出」同「掃得到」係兩件事。"""
    mx = Q.matrix(text)
    assert _decode(mx) == text     # OpenCV 解返出嚟
```

**實測捉到 3 個 bug**（如果冇呢個測試，永遠唔會知）：
1. **format info 位置 transpose**（row/col 掉轉）→ 掃唔到
2. **`_place_data` 污染 reserved map** → mask 完全冇應用到 → 掃唔到
3. version 選擇太保守（v1 裝得落都揀 v2）

## 📱 手機 OS 介面（App-first）

Wander 唔係「一個網站」，而係**一部旅行裝置**：

```
① 登入（驗證碼 或 密碼）
        ↓
② 開機動畫
   ▮▮▮▮▮▮▮▮▮▮▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯
        087%          ← 像素字體（Press Start 2P）
    同步旅程資料_       ← 閃爍 cursor
        ↓
③ 主畫面 —— 直接入 app，唔使先揀旅程
   👥 你有一個交友邀請        ← 通知 banner
   ┌──────────────────────┐
   │ 當前旅程：福岡 4 日      │  ← 撳一下喺 app 內轉旅程
   │ 2027-08-12 · 福岡→首爾  │
   └──────────────────────┘
   🗓 Planner  📥 Organize  💸 Money   🛒 Shopping
   🧭 Zones    🗺 Map       👥 Friends ⚙️ Settings
   🗂 Trips
```

**⚠️ App-first 流程**（用戶要求）：
```
❌ 舊：登入 → 揀旅程 → 入 app
✅ 新：登入 → 開機動畫 → **直接入 app** → 喺 app 內揀旅程
```

撳需要旅程嘅 app（Planner / Money / Shopping…）但未揀旅程 →
會提示「先揀一個旅程」並帶你去旅程列表。

### 開機動畫（BootScreen）

**⚠️ 老實講：呢個係「扮」嘅 loading —— 冇真正嘢喺度載入。**
但佢有真實作用：
- 遮住 app 初始化（讀 `/api/me`、攞 trips）嘅空窗
- 建立「呢個係一部裝置」嘅心理暗示
- 睇落專業（產品感）

進度係**故意設計過嘅節奏**，唔係隨機：
```
0   → 14   開機自檢      （慢）
14  → 58   連線／同步     （快）
58  → 92   準備地圖      （中）
92  → 100  就緒          （微慢，等一等再彈入）
```
配合：像素分段進度條（28 格）＋ 等寬像素字體百分比 ＋ 閃爍 cursor ＋
背景掃描線，撳畫面可以跳過。

### 購物清單（Shopping List）

旅行買嘢同平時唔同：
| 需要 | 做法 |
|---|---|
| 分「邊個負責買」 | 指派 dropdown（一班人分工） |
| 記「邊度買」 | 備註欄（藥妝／手信／機場） |
| 估預算 | 單價 × 數量自動加總 |
| 唔好買雙份 | 剔咗就變灰 + 可一鍵清走 |

分類：🎁 手信 · 💊 藥妝 · 🍫 食品 · 👕 衣物 · 🔌 電器
可以**貼一整份清單**（每行一項）一次加入。

## 🧭 分區行程規劃（唔靠 scraping）

**你入資料 → App 幫你整理 → 分區 → 排行程。**

| 步驟 | 做啲咩 |
|---|---|
| **1. 你入資料** | 名 + 地址（例如「一蘭本社総本店」+「福岡県福岡市博多区中洲5-3-2」） |
| **2. App 自動整理** | 查座標、抽地區名、分類、估停留時間 |
| **3. 分區** | 按地理位置分組（行得到嘅擺一齊） |
| **4. 排行程** | 建議「Day 1 去中洲，Day 2 去天神…」 |

### ⚠️ 為咩分區用數學而唔用 AI

分區係**幾何問題**。兩個地方距離 300 米就係同區，距離 8 公里就唔係 —— 純數學。

用 AI 做呢件事有三個問題：
1. **唔穩定** —— 同一個 input 跑兩次可能唔同答案（行程規劃唔可以咁）
2. **慢 + 要錢**
3. **冇得測** —— 你唔可以 assert「AI 應該話係同一區」

所以用 **Haversine 距離 + 確定性貪心聚類**：
```
① 揀最密集嘅點做種子
② 吸納 1100m 內所有未分組嘅點
③ 細區（< 3 個景點）併入最近大區
④ 冇座標嘅按地區名分組
⑤ 完全冇資料嘅入「未定位」（永遠排最後）
```

**排日子用評分制**（唔係硬規則）：
```python
cost = 距離總和（>4km 懲罰 ×3） + 負載 ×1.5
揀最低分嗰日
```
硬規則踩過坑：太宰府同博多相距 7.9km，但因為「搵唔到更好選擇」就照塞同一日。
評分制永遠有答案，而且一定係最合理嗰個。

**跨區會提醒**：「⚠️『中洲』同『宰府』相距 14.0km，建議安排半日以上」

**地址自動抽地區名**：
```
福岡県福岡市博多区上川端町1-41  →  上川端町 → 博多区 → 福岡市  (逐級退)
福岡県福岡市博多区中洲5-3-2     →  中洲        (精準命中)
서울 성동구 연무장길 47        →  성동구
```
> ⚠️ 踩過坑：完整地址查唔到座標 → 前端 fallback 去查店名
> → 「櫛田神社」攞到**三重縣**嘅同名神社 ❌
> 修法：由地址抽地區名，逐級退（町名 → 區名 → 市名）。

## 💸 分帳（最少轉帳次數）

**你入開支 → App 自動計返邊個俾幾多俾邊個。**

### ⚠️ 為咩分帳用數學而唔用 AI

分帳係**算術**。用 AI 做算術係災難 —— 會出現「大概 $523 左右」，
但分帳要**準確到仙**（差一蚊都會嘈交）。

### 三個關鍵設計

**① 內部全部用整數（仙）運算**
```python
0.1 + 0.2 = 0.30000000000000004   # 浮點數係事實
```
用 float 計錢會出現「明明應該 $0 但顯示 $0.0000001」→ 用戶唔信個 app。

**② 餘數唔可以消失**
```
$100 / 3 = 33.333…  →  每人 33.33 就總和 99.99，差 $0.01
正確做法：先每人攞 floor，餘數逐個派（每次 1 仙）
→ 總和一定準確
```

**③ 最少轉帳次數（核心價值）**
```
4 個人互相欠 → 逐對計要 6 次轉帳
實際只需要 3 次（= n-1，理論下限）
```
貪心法：每次攞最大債仔同最大債主配對，轉 `min(欠, 應收)`。

**實測結果：**
```
總額 ¥79,000（6 筆，4 人）
  Alice  收 ¥30,633.33
  Bob    俾  ¥3,466.67
  Dave   俾 ¥12,500.00
  Carol  俾 ¥14,666.66

最少轉帳 3 次（理論下限 3 次）：
  Carol → Alice  ¥14,666.66
  Dave  → Alice  ¥12,500.00
  Bob   → Alice   ¥3,466.67

賬目: ✓ 平
```

**支援「邊個唔分呢筆」** —— Dave 冇搭的士，可以剔走佢。

## 🔓 破解 Instagram 封鎖（書籤小工具）

### 先講事實：IG 完全封死 server-side 存取

實測（2026-10），所有方法都失敗：

| 方法 | 結果 |
|---|---|
| 直接抓 HTML | 302 → `/accounts/login/`，630KB 空殼，**零 og 標籤** |
| `/embed/captioned/` | 630KB JS 空殼，冇 caption |
| `/api/v1/oembed/` | **401** |
| `?__a=1&__d=dis` | **404** |
| r.jina.ai reader | 第一次成功，之後 Cloudflare **403** |

### ⚠️ 網上流傳嘅兩個「解決方法」都唔得

**❌ 方法一：WebView 偷 Cookie**
- **Web App 技術上做唔到** —— 瀏覽器 Same-Origin Policy，你嘅 JS 讀唔到 instagram.com 嘅 cookie，一行都讀唔到
- 原生 App 做到，但會令**用戶帳號被鎖**（cookie 綁 IP + 裝置指紋）
- 要儲存用戶 IG session → server 一被入侵就洩漏晒所有人嘅 IG 帳號
- 違反 IG ToS

**❌ 方法二：官方 Instagram API**
我查證咗（[Storrito 2026 分析](https://storrito.com/resources/instagram-api-2026/)）：
- **Basic Display API 已經喺 2024年12月4日停止** —— 個人帳號完全冇 public API
- Graph API **只俾 Business/Creator 帳號**，而且**只讀到你**自己**發佈**嘅 media
- 官方明文：**冇 public discovery endpoint**，讀唔到其他人嘅帖
- 「讀取自己儲存（Saved）嘅貼文」→ **API 冇呢個功能**

> 原文：「official APIs in 2026 only allow access to accounts authorized by the user」
> 「Any service asserting otherwise is either caching stale data or using unsupported scraping methods」

### ✅ 正解：書籤小工具（Bookmarklet）

**用你自己嘅瀏覽器、你自己嘅登入狀態，由你主動撳一下。**

```
你喺 Instagram 開住個帖（已登入，見得到內容）
      ↓ 撳書籤欄嘅「🔖 匯入到 Wander」
喺你自己嘅分頁讀取 DOM（唔關 server 事）
      ↓
抽出 url + author + image + caption → 放入剪貼簿
      ↓ 去 Wander 貼上
自動識別 → 解析 → 76% 信心
```

| | 直接貼 IG link | 書籤小工具 |
|---|---|---|
| 信心 | **0%** | **76%** |
| 名稱 | ❌ | ✅ 長岡博多天婦羅 |
| 地區 | ❌ | ✅ 香港 › 銅鑼灣 |
| 分類 | ❌ | ✅ 🍜 天婦羅 |
| 品牌來源 | ❌ | ✅ 福岡（唔會歸錯行程） |

**點解呢個合法又安全：**
- ✅ 用戶自己嘅瀏覽器、自己嘅登入狀態、自己主動撳
- ✅ 唔需要 cookie、唔需要密碼、唔需要 API key
- ✅ Server 完全唔參與抓取 —— 法律上等同「用戶自己複製文字」
- ✅ 唔會被鎖帳號

**支援：** Instagram（帖文／Reel）× 小紅書 × 任何網站（og 標籤）

**點安裝（3 步）：**

1. **睇到書籤欄** —— 喺網址欄下面，通常預設隱藏
   ```
   Mac Chrome / Edge / Safari / Firefox  →  ⌘ + Shift + B
   Windows                              →  Ctrl + Shift + B
   ```
2. **拖個掣上去** —— 設定頁用滑鼠**撳住**「🔖 匯入到 Wander」**拖**去書籤欄
   > ⚠️ 唔係「撳」佢 —— 撳只會出提示，因為要拖
3. **去 IG 用** —— Instagram 開個帖 → 撳書籤欄嗰個掣 → 見紫色提示 = 已複製 → 返 Wander 貼上

**手機：** 設定頁「複製書籤碼」→ 加一個任意書籤 → 網址改成嗰段。

### ⚠️ 開發者注意：書籤小工具原始碼唔可以用 `//` 註解

```js
// ❌ 錯：壓縮成一行之後，個 // 會吞掉成行後面所有程式碼
var h1 = document.querySelector('h1');  // 主 caption
if (!out.caption) { ... }               // ← 呢行永遠唔會執行

// ✅ 啱：只可以用 /* */ 塊註解
var h1 = document.querySelector('h1');  /* 主 caption */
```

呢個 bug 會令成個書籤小工具直接壞掉（`SyntaxError: Unexpected end of input`），
**但 `node --check` 捉唔到** —— 一定要真跑一次先發現。
所以有兩個測試守住：`bookmarklet.test.mjs`（語法）+ `bookmarklet-dom.test.mjs`（jsdom 真跑）。

### 🔮 將來（部署上 HTTPS 之後）

`manifest.webmanifest` 已經配好 **Web Share Target**：

```
IG 撳「分享」→ 揀「Wander」→ 自動解析 → 完成（唔使複製貼上）
```

⚠️ 需要 PWA 已安裝 + HTTPS。而家 `http://192.168.x.x` 係 insecure context，用唔到。

### ❓「點解人哋啲 app 可以直程 copy 到 IG？」

**因為佢哋俾錢。** 第三方抓取服務自己養住宅代理 + 帳號池 + 反偵測，
成本轉嫁落用家身上。市場實價（2026）：

| 服務 | 免費額度 | 之後價格 |
|---|---|---|
| **HikerAPI** | ~100 次 | 約 **$0.60–1.00 / 1000 次**（最平） |
| **Social Fetch** | 100 credits | 約 $1.65 / 1000 次 |
| **ScrapeCreators** | 100 次 | 約 $1.88 / 1000 次 |
| Apify | ~$5/月 credit | $29/月起 + 用量 |
| Bright Data | trial | ~$1.50/1000 + $100/月最低消費 |

其他「免費」app 通常係：
- **帳號農場**（買幾百個小號輪流用）→ 帳號不停被封，要持續補貨
- **快取舊資料**（IG 收緊之前抓落嘅）
- **收咗你嘅 IG session cookie**（= 你嘅帳號有風險）

### Wander

## 🌍 而家已經上線

```
https://era-apparently-submitted-language.trycloudflare.com
```

⚠️ 呢個係 **cloudflared quick tunnel** —— **臨時**嘅，一閂就冇。
下次跑 `./host.sh` 會出**另一個**網址。

### 一鍵上線

```bash
./host.sh
```

⚠️⚠️ 佢會喺起 tunnel **之前**問你安全選項：

```
⚠️⚠️⚠️  注意  ⚠️⚠️⚠️

你而家係 **open** 模式 —— 註冊只需要 email + 密碼。
一旦放出街，**任何知你網址嘅人都可以註冊**，
而且可以用**任何 email**（包括你朋友嘅）。

  1) 改成 invite 模式（要邀請碼）——  推薦
  2) 照用 open（我知風險）
  3) 唔 host 住，取消
```

⚠️ `open` 模式 + 公開網址 = **冇任何門檻**。
   純內網冇問題，放出街就要考慮。

### 實測（經公開網址）

```
✓ 首頁 200 · HTTPS
✓ manifest 200 · service worker 200
✓ icon-512 200 · 星雲背景 200 · 角色圖 200
✓ 註冊（email+密碼）200
✓ 建立旅程 200
✓ 加城市（要 geocode）200  → 時區 Asia/Tokyo
✓ QR code → 用公開網址（朋友掃到）
15 通過 / 0 失敗
```

⚠️ HTTPS 之下：PWA 安裝、離線、相機、QR 掃描**全部用得**
（LAN 嘅 `http://192.168.x.x` 做唔到）。

### ⚠️ 想永久 host（唔係臨時 URL）

| 方法 | 成本 | 網址 | 適合 |
|---|---|---|---|
| **cloudflared quick tunnel** | 免費 | 每次唔同 | 試用 |
| **cloudflared named tunnel** | 免費（要 Cloudflare 帳號 + 網域）| 固定 | 認真用 |
| **ngrok**（已裝）| 免費版有警告頁 | 每次唔同 | 試用 |
| **VPS**（Fly.io / Railway / Render）| 免費層 | 固定 | 長期 |
| **自己部機 + 固定 IP** | 電費 | 固定 | 進階 |

⚠️ 但記住：**部機一瞓覺，個 app 就冇**。
   要真正 24/7 就要 VPS（或者唔瞓嘅機）。
 嘅做法：可選，預設關閉

```ini
# server/.env（唔填 = 完全免費，用書籤小工具）
WANDER_IG_PROVIDER=scrapecreators   # 或 socialfetch / hikerapi
WANDER_IG_KEY=your_api_key
```

| | 免費方法 | 第三方 API |
|---|---|---|
| 成本 | $0 | ~$1 / 1000 次 |
| 風險 | 零 | IG ToS 灰色地帶 |
| 操作 | 撳一下書籤 | **IG link 一貼即抽** |

**⚠️ 預設一定係關閉** —— 唔可以喺用戶唔知情嘅情況吓用收費服務。
有測試守住呢點（`tests/test_igprovider.py::TestDefaultsOff`）。

### 如果連書籤小工具都唔想用

Wander 仲有**內置引導**：貼 IG link → 偵測到封鎖 → 彈出面板教你
「IG 撳 ⋯ → 複製文字 → 貼落嚟」，一撳「📋 從剪貼簿貼上」就搞掂。

## 🌍 本地城市庫（0.03ms 定位）

**用戶提議（好正確）**：
> 「你可以收集晒全世界嘅重點城市，佢嘅英文中文縮寫，
>   然後只要佢修改你嗰個 input 嘅城市，然後之後就睇吓係有冇中到咁咪得囉」

完全正確 —— 世界重點城市嘅座標係**唔會變**嘅，冇理由每次上網查。

| | 每次查 API | 本地庫 |
|---|---|---|
| 速度 | 200–800ms | **0.03ms** |
| Rate limit | 會（實測連續查十幾個就冇反應） | 唔會 |
| 離線 | 唔得 | **可以** |
| 準確度 | 同名地方會攞錯 | **人工校正** |

```
engine/wander/data/
  cities.json     7.0 MB   GeoNames 34,153 個城市
                          過濾：人口 >= 50000 或首都／行政中心
                          134,655 個名稱索引（中／英／日／韓／諺文…）
  districts.json  146 個   重點旅遊地區，人工校正
                          博多 · 天神 · 中洲 · 明洞 · 弘大 · 聖水洞
                          銅鑼灣 · 中環 · 尖沙咀 · 西門町 · 永康街
                          心齋橋 · 梅田 · 祇園 · 嵐山 · 新宿 · 渋谷…
```

### ⚠️ 為咩地區要人工校正（唔可以靠 API）

同名地方全世界都有，API 靠「熱門度」排序，唔知你講邊個。
**實測踩過嘅坑：**

| 地名 | API 攞到 | 應該係 |
|---|---|---|
| 梅田 | 埼玉縣嘅梅田 (35.77, 139.80) ❌ | 大阪 (34.70, 135.50) |
| 安平 | 河北安平縣 (38.23, 115.51) ❌ | 台南 (23.00, 120.17) |
| 祇園 | 広島附近 (34.43, 132.47) ❌ | 福岡 (33.59, 130.42) |
| 西門町 | 日本某處 (34.97, 138.38) ❌ | 台北 (25.04, 121.51) |
| 明洞 | 中國 (40.39, 116.18) ❌ | 首爾 (37.56, 126.98) |
| 釜山 | 中國 (32.67, 118.71) ❌ | 韓國 (35.10, 129.03) |

所以地區庫**優先過**城市庫（人工校正嘅答案一定比 GeoNames 準）。

### 查詢次序

```
① 本地地區庫（人工校正）    ← 博多、明洞、銅鑼灣呢類
② 本地城市庫（GeoNames）    ← 福岡、首爾、Paris、London
③ 永久 cache（Photon 查過）  ← 查一次之後永久存本地
④ Photon（fallback）        ← 本地真係冇，查完寫入 ③
```

### 地圖行為

設定城市之後（例如「福岡 4 日 → 首爾 3 日」）：
- 城市自動 geocode（3ms）
- 地圖**自動 fit 到兩個城市**
- 城市有標記（紫色膠囊 + 日數）
- 頂部有城市快跳掣，撳一下飛去嗰個城市
- 城市座標存落 DB，重新載入都用得

城市輸入有**自動完成**（打「福」／「seo」即刻出建議）。

## ⭐ 時段格日曆（時間表）

```
      ┌──────────────────────────┐
09:00 │  🍜 一蘭本社総本店         │  ← 高度 = 時長
      │  09:30–11:00 · 1 小時 30 分│
10:00 │                          │
      ├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
11:00 │  🛍 イオンモール筑紫野  ══  │  ← 底部橫線可以拖
      │  11:30–14:00 · 2 小時 30 分│
12:00 │                          │
```

**操作：**
| 動作 | 效果 |
|---|---|
| **撳空白格** | 彈出揀景點 → 再揀佔幾多個鐘（30分／1h／1.5h／2h／3h／自訂） |
| **拖 block 上下** | 改開始時間（15 分鐘對齊） |
| **拖 block 底部橫線** | 改佔幾多個鐘（你要求嘅功能） |
| **撳 block** | 開詳情，可以改名稱／分類／時間 |
| 左邊時間軸 | 06:00–24:00，每個鐘一格，半個鐘虛線 |
| 紅線 | 今日嘅現在時間（只有 Day 1 顯示） |

**⚠️ 用 Pointer Events 而唔用 HTML5 Drag & Drop** —— HTML5 DnD 喺手機完全唔 work。

未設時間嘅活動會自動由上一站接落去（預設 1 小時），
所以你可以先排順序，再微調時間。

## 🌐 跨語言店名抽取

用戶明確要求：**「information 唔一定係中文，可以係其他 language」**。

| 輸入 | 抽出 |
|---|---|
| `🔸住所：〒810-0801 福岡県福岡市博多区中洲5-3-2 一蘭本社総本店` | `一蘭本社総本店` |
| `住所：… 一蘭 本社総本店`（有空格） | `一蘭 本社総本店` |
| `📍住所：〒818-0056 福岡県筑紫野市紫二丁目 イオンモール筑紫野1階` | `イオンモール筑紫野`（剝樓層） |
| `🔹주소：서울 성동구 연무장길 47 어니언 성수` | `어니언` |
| `📍주소：부산 해운대구 해운대해변로 264 씨클라우드 호텔` | `씨클라우드 호텔` |
| `#BillsFukuoka #福岡 世界一の朝食` | `BillsFukuoka` |
| `#福岡 #博多 #美食` | *(冇名，正確)* |

### ⚠️⚠️ 呢度踩過一個嚴重嘅坑

原本 `normalize()` 會將**所有漢數字轉阿拉伯**（一→1、二→2…），
結果：

```
一蘭本社総本店  →  1蘭本社総本店   ❌ 店名壞晒
三代目 鳥メロ    →  3代目 鳥メロ     ❌
```

**教訓**：店名入面嘅漢數字係**名字嘅一部分**，唔係數值。
而家只喺明確係數值嘅情況先轉（〇/零），其餘一律保留原文。

### 由地址行切店名（唔可以攞成句）

```
❌ 舊：抽出「🔸住所：〒810-0801 福岡県…一蘭本社総本店」成句
✅ 新：剝標籤 → 去郵便番号 → 由右邊連續收集「似名」token，
       撞到地址 token 就停
```

判斷「係唔係地址 token」要**用結構特徵，唔可以用長度**：
```
「福岡県福岡市博多区中洲5-3-2」有 15 個字
  → 舊守衛 len<=9 認唔到 → 被當店名收集 ❌
  → 新規則：看到「県…市」結構 / 「番地+行政區」就當地址 ✅
```

韓國行政後綴一定要齊：`구 동 시 군 읍 면 리` 同 `-gu -dong -ro -gil`
（漏咗「구」就會將「성동구」當成店名）。

## ⭐ 多城市規劃 + 衝突偵測

一個 trip 可以去多個城市：

```
福岡 4 日  →  首爾 3 日        總共 7 日
Day 1-4 福岡     Day 5-7 首爾
```

撳月曆右上「🧭 城市」就可以加減城市、改日數。改完之後如果行程同新安排唔夾，
會彈一個電腦 style 嘅對話框問你：

> ⚠️ **行程有衝突** — 因為地區改變咗，有 N 個行程同新嘅城市安排唔夾。要幫你刪除佢哋嗎？
> **［係，刪除佢哋］［唔使，標記做 warning］［取消］**

### ⚠️ 過渡日唔算衝突（重要規則）

用戶明確要求：**去另一個城市嘅嗰一日，兩邊嘅行程都合理，唔應該報衝突。**

```
福岡 4 日 + 首爾 3 日
  Day 4 = 福岡最後一日  ┐ 過渡日 → 福岡／首爾行程都接受
  Day 5 = 首爾第一日    ┘
```

判定規則：
| 情況 | 處理 |
|---|---|
| 一日只屬於一個城市 | 該城市行程 OK；其他城市 = **衝突** |
| 一日橫跨兩個城市（過渡日） | **兩邊都接受，唔報衝突** |
| 行程完全冇地區資料 | 唔報（避免誤報） |

改城市仲會自動同步 `trips.days` 同 `end_date`，所以唔會出現
「7 日行程但月曆得 4 格」。

**測試**：`node tests/web/stops.test.mjs` → 31 個測試，涵蓋過渡日規則。

## ⚠️ 地址／座標一致性檢查

真實案例（用戶提供）：

```
店名  イオンモール筑紫野        → 暗示 福岡
地址  福岡県筑紫野市立明寺434-1  → 福岡
〒    110-0015                 → 東京都台東区
座標  35.70982, 139.77868      → 東京都台東区東上野
```

**地址係福岡，座標係東京** —— 唔檢查就會令用戶搭幾個鐘車去錯地方。

解析完會自動反查座標做比對，唔一致就：
- 寫入 `notes`：「⚠️ 地址寫『福岡県 筑紫野市』，但座標喺『台東区 東上野二丁目』」
- 設 `needs_review = true`，前端顯示黃色虛線框

**比對策略係保守評分制** —— 寧願唔報，都唔好誤報（誤報會令用戶唔信任警告）：
- 只用「地區／市」層比對，**district 唔參與判定**（街名 vs 洞名本質唔同層）
- 郵便番号只做加權，唔可以單獨判衝突（實測：橫濱鶴見区 〒230-0054 反查到 〒231-0017）

## 真實 Email 驗證碼（Gmail）

```bash
cd server
cp .env.example .env
# 填 Gmail App Password（⚠️ 唔係登入密碼）
```

```ini
WANDER_SMTP_HOST=smtp.gmail.com
WANDER_SMTP_PORT=587
WANDER_SMTP_USER=yourname@gmail.com
WANDER_SMTP_PASS=abcd efgh ijkl mnop    # App Password
```

**Gmail App Password 產生方法**：<https://myaccount.google.com/apppasswords>
（要先開兩步驗證；普通密碼 Google 已經封鎖。）

未設定 → 自動 fallback 印喺 server console（App 照用）。
設定咗但寄失敗 → **唔會**靜靜俾你用 dev_code 登入（免掩蓋設定問題），
而係喺登入畫面顯示錯誤原因。

亦支援 **Resend**（`WANDER_RESEND_KEY`），唔使自己開 SMTP。

## PWA 離線（去旅行救命功能）

```bash
node tests/web/sw.test.mjs      # 20 個測試，真跑 cache 策略
```

**三層 cache 策略：**

| 資源 | 策略 | 原因 |
|---|---|---|
| app shell (js/css) | cache-first | 檔名有 hash，永不變 |
| 導航 | network-first | 拎最新版；離線食 index.html |
| **OSM 地圖圖磚** | cache-first + LRU 800 塊 | **離線睇地圖** |
| 外部 CDN（字體） | stale-while-revalidate | 有就用，冇就用舊 |
| **API** | **network-only（唔快取）** | 私隱：唔可以俾 A 嘅行程出現喺 B 度 |

**兩個踩過嘅坑：**

1. **`*/` 喺註解入面會提早閂註解區塊**
   我喺檔頭寫 `**/api 一定要 network-only**` → 個 `*/` 令成個 SW 語法爆。
   （`node --check` 捉到。）
2. **`trimCache` 唔 await 會有 race condition**
   多個並發 `put` 同時跑 trim，互相覆蓋 → 圖磚超額（實測 801 > 800）。要 `await`。

**手機要先「加到主畫面」先有離線**
`http://192.168.x.x` 唔係 secure context，瀏覽器唔會註冊 service worker。
呢個係安全限制，唔係 bug —— 設定畫面有提示。

## 已知限制

1. **IG / 小紅書 server-side 完全封死** —— IG 所有請求 302 去登入頁，零 og 標籤。
   對策：叫用戶貼 caption 文字（零成本、零法律風險、資料最齊）。
2. **純圖片做唔到** —— 冇 caption、冇 link 就冇字可以解析。
   對策：叫用戶打一行店名（5 秒），或者將來加 OCR。
3. **caption 本身冇店名** 嘅情況需要用戶補一行 —— UI 要接受呢件事。
4. 地圖 tile 同 Photon 都要上網；離線要另外做快取。

## 下一步（可選）

- [ ] PWA service worker（真正離線）
- [ ] 交通接駁（先做估算，後接 Google Routes API）
- [ ] 截圖 OCR（Gemini 免費額度 或 本地 PaddleOCR）
- [ ] 部署上線（Vercel + Supabase，或 Railway）
