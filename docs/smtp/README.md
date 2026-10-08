# 未設定 SMTP 點搞？

## ⚠️⚠️ 最常見嘅坑：`SMTPServerDisconnected`

```
✗ 寄唔到：SMTPServerDisconnected: Connection unexpectedly closed
```

⚠️⚠️ **呢個錯誤訊息完全誤導。**

| 你以為 | 實際 |
|---|---|
| 網絡問題 / server 掛咗 | **憑證唔啱** |

Gmail 收到錯嘅 App Password **唔會講「密碼錯」**——
佢直接**切斷連線**（防止暴力破解）。

### 原因幾乎一定係：App Password 唔係 16 個字

```
✗ 你貼咗 Gmail **登入密碼**（長度唔定，有符號）
✓ App Password 一定係 **16 個**（純英數，例：abcd efgh ijkl mnop）
```

⚠️ Gmail **唔接受**普通密碼做 SMTP
（「低安全性應用程式」Google 已經喺 2022 年停用咗）。

### 診斷

```bash
cd server
python tools/setup_mail.py --doctor
```

會**分層測**，話你邊一步死：

```
  ① 設定
     pass = （11 字）
     ⚠️⚠️ Gmail App Password **一定係 16 個字**，但你係 11 個

  ② 連線 smtp.gmail.com:587
     ✓ TCP 連得到（唔關網絡事）      ← 證明唔關網絡事

  ③ STARTTLS
     ✓ TLS 握手成功

  ④ 登入
     ✗ Server 切斷連線（SMTPServerDisconnected）
       ⚠️⚠️ 呢個錯誤訊息完全誤導…其實係憑證唔啱
```

⚠️ 而家工具會**硬性拒絕**非 16 字嘅密碼（唔會再問「照用？」）——
   實測就係因為嗰個「照用？(y/N)」令人中招。

---

## ⚡ 快速開始（5 分鐘）

```bash
cd server
python tools/setup_mail.py
```

⚠️⚠️ **你嘅密碼只會由鍵盤直接寫入 `server/.env`，
  唔會經過任何對話或者紀錄。**（我唔會知你打咗咩。）

跟著佢問你嘅嘢答就得。然後**重啟 server**，再試寄：

```bash
python tools/setup_mail.py --test 你@gmail.com
```

睇目前設定（⚠️ 唔會顯示密碼）：

```bash
python tools/setup_mail.py --show
```


> **你問嘅**：「未設定 SMTP 你係諗住點搞？」
>
> **誠實答**：冇 SMTP 就**寄唔到 email**，所以寄唔到驗證碼。
> 但「朋友之間用」根本唔需要 email 驗證 —— 所以有三條路。

---

## 先搞清楚：其實幾時先需要 email？

你個 app 而家用 **email + 密碼**登入（驗證碼已經唔係主要路徑）。
所以 email **只係**三個情況需要：

| 情況 | 需要 email？ |
|---|---|
| **日常登入** | ❌ 唔需要（打密碼就得） |
| **註冊新帳號** | ⚠️ 要（或者用邀請碼） |
| **唔記得密碼** | ⚠️ 要（或者你幫佢重設） |
| 朋友邀請 | ❌ 唔需要（分享連結就得） |

> ⚠️ **重點**：如果你用**邀請碼**註冊，就**完全唔使 SMTP**。

---

## 三條路（我推薦第 ② 條）

| | 做法 | 成本 | 時間 | 適合 |
|---|---|---|---|---|
| **①** | 設定 SMTP | 免費 | 5 分鐘 | 想用真 email |
| **②** | **邀請碼** | 免費無限 | **0 分鐘** | **朋友之間用 ← 推薦** |
| **③** | 公開註冊 | 免費 | 0 | ⚠️ 只適合純內網 |

---

## ② 邀請碼（推薦，唔使搞 SMTP）

我已經**做好咗**。你咩都唔使設定：

```
1. 設定 → 開發版後台 → 🔑 註冊邀請碼
2. 撳「產生」→ 出一個 6 位碼（例如 AMBB3L）
3. WhatsApp 畀朋友
4. 朋友註冊時打呢個碼 → 完成
```

### ⚠️ 為咩邀請碼其實**比** email 驗證更好（朋友之間）

| | Email 驗證 | 邀請碼 |
|---|---|---|
| 證明咩？ | 佢控制嗰個信箱 | **你親手畀佢** |
| 成本 | 要 SMTP | 零 |
| 被濫用 | 可以撞 | 一次性 + 有期限 |
| 垃圾帳號 | 可能 | 唔可能（你唔畀就冇） |

> 對朋友之間用嘅 app，**「你親手畀條碼」比「寄 email」更實在**。

### ⚠️ 安全設計

- **一次性** —— 用咗就標記 `used_by`，流出咗都只可以用一次
- **有期限** —— 預設 30 日
- **可加備註** —— 記住邊條碼畀咗邊個
- ⚠️ 碼用 `_invite_code()`（撇除 `O/0`、`I/1/l`）—— **要手打好多次**

---

## ① 設定 SMTP（想用真 email 先做）

### 選項 A：Gmail App Password（最易）

⚠️ **前提**：你嘅 Google 帳號要開咗 **兩步驗證**。

```
1. 去 https://myaccount.google.com/apppasswords
   （要先開兩步驗證先見到呢頁）
2. 應用程式選「郵件」、裝置選「其他」→ 打「Wander」
3. 撳「產生」→ 出一個 16 位密碼（例：abcd efgh ijkl mnop）
4. 放落 server/.env：

WANDER_SMTP_HOST=smtp.gmail.com
WANDER_SMTP_PORT=587
WANDER_SMTP_USER=你嘅email@gmail.com
WANDER_SMTP_PASS=abcdefghijklmnop        ← 空格要刪走
WANDER_MAIL_FROM=你嘅email@gmail.com

5. 重啟 server → 設定入面會顯示「已設定」
```

⚠️ **限制**：免費 Gmail 每日 **500 封**。
對朋友之間用綽綽有餘。

⚠️ **風險**：呢個 App Password 等於你 Gmail 嘅發信權。
唔好 commit `.env`（已經喺 `.gitignore`）。

---

### 選項 B：Resend（唔使開兩步驗證）

⚠️ 免費 **100 封/日、3000 封/月**。

```
1. 去 https://resend.com 註冊（免費）
2. API Keys → Create API Key → 複製
3. 放落 server/.env：

WANDER_RESEND_KEY=re_xxxxxxxxxxxx
WANDER_MAIL_FROM=onboarding@resend.dev

4. 重啟 server
```

⚠️ **未驗證網域**之下，只可以寄去**你自己註冊嘅 email**。
要寄去任何人就要驗證一個網域（要你有網域）。

**適合**：你自己一個人測試。
**唔適合**：真係畀朋友用（要網域）。

---

### 選項 C：Brevo（免費 300 封/日，可以寄去任何人）

```
1. 去 https://brevo.com 註冊
2. SMTP & API → SMTP → 攞 host / login / key
3. 放落 server/.env（同 Gmail 一樣嘅欄位）

WANDER_SMTP_HOST=smtp-relay.brevo.com
WANDER_SMTP_PORT=587
WANDER_SMTP_USER=你嘅login
WANDER_SMTP_PASS=你嘅SMTP key
WANDER_MAIL_FROM=你驗證咗嘅email
```

⚠️ 要**驗證寄件人 email**（免費版）。
好處：可以寄去任何地址，唔使自己有網域。

---

## ③ 公開註冊（⚠️ 唔建議）

```bash
# server/.env
WANDER_SIGNUP_MODE=open
```

⚠️ **任何人都可以註冊** —— 只要你個網址流出咗就有人入到。
只適合：純內網、臨時測試。

---

## ⚠️⚠️ 而家（未設定）嘅狀態：有安全洞

```
mode: "console"
hint: "未設定 SMTP → 驗證碼只會印喺 console"
```

**驗證碼會顯示喺登入畫面**（因為前端收到 `dev_code`）。

⚠️ **即係任何人都可以用任何人嘅 email 註冊／認領帳號** ——
只要佢知你個網址。

| 情境 | 風險 |
|---|---|
| 純內網（192.168.x.x） | ✅ 冇問題 |
| 用 cloudflared 放出街 | ⚠️ **危險** |

✅ **所以而家預設係 `invite` 模式** —— 有邀請碼先註冊得到。
驗證碼只保留做「認領舊帳號」。

---

## 我幫你做好咗嘅嘢

```python
def signup_mode() -> str:
    """
    · `open`   —— 任何人都可以註冊（⚠️ 公開上網有風險）
    · `invite` —— 要邀請碼（**推薦**，唔使 SMTP）
    · `email`  —— 要 email 驗證碼（要設定 SMTP）

    ⚠️ 預設：有 SMTP 就 `email`，冇就 `invite` ——
       因為冇 SMTP 就寄唔到驗證碼，`email` 模式會令所有人都註冊唔到。
    """
```

**自動判斷**，你咩都唔使設定：
- 未設定 SMTP → `invite`（要邀請碼）
- 設定咗 SMTP → `email`（寄驗證碼）

想強制就用 `WANDER_SIGNUP_MODE`。

---

## 快速對照

```
想 5 分鐘搞完，唔想碰 SMTP     → 用邀請碼（咩都唔使做，已經係預設）
想朋友自己註冊，唔想手動派碼   → 設定 Gmail App Password
想寄去任何人又冇網域           → Brevo
只想自己一個人測試             → Resend
純內網、唔理安全               → WANDER_SIGNUP_MODE=open
```
