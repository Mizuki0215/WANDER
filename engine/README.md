# Wander 解析引擎

將任何來源（Google Maps link、IG caption、Tabelog 網頁、用戶手打）
轉成一個結構化嘅「旅行收藏項目」。

```
輸入                                     輸出
────────────────────────────────────    ────────────────────────────────
https://www.google.com/maps/place/…  →  name: 一蘭 本社總店
                                        lat/lng: 33.5897, 130.4207
                                        district: 博多
                                        confidence: 100%

【彼岸花祭2026】…🔸地址：〒823-0003  →  name: 犬鳴川河川公園
福岡縣宮若市本城65-1 犬鳴川河川公園      postal_code: 823-0003
                                        city: 宮若市  category: play
                                        dates: 9/24–10/8, 10月上旬, 10/4
                                        confidence: 84%
```

## 快速開始

唔使安裝任何嘢（Anaconda 已經有 requests / bs4 / lxml）。

```bash
cd engine

# 跑自我測試
python -m wander selftest

# 睇範例輸出
python -m wander demo

# 解析一條 link（會上網抓）
python -m wander parse "https://tabelog.com/fukuoka/A4001/A400101/40001234/"

# 只靠 URL 結構解析，唔上網（Google Maps 極準）
python -m wander parse --no-fetch "https://www.google.com/maps/place/…/@33.58,130.42,17z"

# 解析文字（貼 IG caption）
python -m wander text "地址：〒823-0003 福岡縣宮若市本城65-1 犬鳴川河川公園"

# 出 JSON（餵落 app）
python -m wander parse --no-fetch "https://…" --json

# 批量處理
python -m wander batch urls.txt --json-out results.json

# ⭐ 由店名反查完整資料（Photon + DuckDuckGo + JSON-LD）
python -m wander lookup "一蘭 本社総本店" --hint 博多
python -m wander lookup "官兵衛うどん" --hint 粕屋町 -v

# ⭐ caption 解析之後再用搜尋補齊缺欄位
python -m wander enrich "「本家大たこ 道頓堀店」営業時間：10:00〜23:00"
```

用 Python 呼叫：

```python
from wander import parse_caption, parse_url_offline, fetch_item

item = parse_caption("🔸地址：〒823-0003 福岡縣宮若市本城65-1 犬鳴川河川公園")
print(item.name, item.location_display, item.confidence)
# → 犬鳴川河川公園 日本 › 福岡縣 › 宮若市 84

# 合併兩個來源（Google Maps 座標 + IG caption 圖文）
gmaps, _ = parse_gmaps("https://www.google.com/maps/place/Ichiran/@33.59,130.42,17z")
cap      = parse_caption("博多一蘭拉麵 本店\n📍地址：福岡縣福岡市博多区…")
merged   = gmaps.merge(cap)      # 座標唔會被覆蓋，caption 補上分類同圖
```

## ⭐ 由店名反查（lookup）—— 避開 IG 封鎖嘅解法

呢個係最重要嘅設計轉向。**唔需要由 IG 攞資料，只需要由截圖認出店名。**

```
IG / 小紅書截圖
      ↓  OCR（或者用戶手打）
    店名：「一蘭 本社総本店」+ 地區提示「博多」
      ↓
  ① Photon (OSM)          模糊搜尋 → 座標 + 地址
  ② DuckDuckGo (免 key)   搵到 Tabelog / Retty / 官網
  ③ 抓 JSON-LD            電話 + 營業時間 + 價錢 + 評分 + 圖
      ↓
  完整 Item（信心 86%）
```

**實測結果：**

| 輸入 | 結果 |
|---|---|
| `一蘭 本社総本店` + 博多 | 8100801 福岡県福岡市博多区中洲5-3-2 · 33.5932,130.4046 · ☎ 050-3733-2600 · ￥1,000～1,999 |
| `官兵衛うどん` + 粕屋町 | 8112317 福岡県糟屋郡粕屋町長者原東1-12-15 · 33.6153,130.4785 · ☎ 092-938-4051 · ⭐3.34 |
| `太宰府天満宮` + 福岡 | 福岡県太宰府市宰府三丁目 · 33.5213,130.5353 · 神社寺廟 |

**三個免費後端嘅實測分工：**

| 服務 | 強項 | 弱項 |
|---|---|---|
| **Photon** (komoot) | 模糊搜尋最強，認得「一蘭 本社総本店」 | 地址可能唔完整（只得「3 2」） |
| **Nominatim** (OSM) | 地址結構最齊 | **唔識模糊搜尋**：「一蘭 本社総本店」→ 搵到「名古屋犬山線」 |
| **DuckDuckGo HTML** | 免 key，搵到 Tabelog（有 JSON-LD 金礦） | 非官方接口，隨時變 |

> ⚠️ **兩個踩過嘅坑（改 code 之前一定要睇）**：
>
> **1. User-Agent 一定要完整**
> ```
> "Wander/0.1"                        → Nominatim 403
> "...Chrome/124.0 Safari/537.36"     → DuckDuckGo 403
> "...Chrome/124.0.0.0 Safari/537.36" → 200 ✅
> ```
> 少一個 ".0.0" 都會被 bot detection 擋。見 `wander/ua.py`。
>
> **2. DuckDuckGo 會因為 `Accept-Language` 而 403**
> ```
> 只有 User-Agent                  → 200 ✅
> UA + Accept-Language            → 403 ❌（"zh-HK" 同 "ja" 都死）
> UA + Accept: text/html          → 200 ✅
> ```
> 所以 `lookup.py` 嘅 session **一定唔可以** 設 `Accept-Language`。

## ⭐ 一帖多店（IG 整理帖）

IG / 小紅書好興一帖列 10 間店。如果當佢係一間店，結果會錯得好離譜。

```python
from wander import parse_caption_multi

items = parse_caption_multi(caption)     # → list[Item]，每間店一個
```

支援嘅格式：

```
⏰ 7:30〜10:30 / 11:30〜23:00
🗺️ エリア：明洞
📝 推しメニュー：冷麺

02｜プルトゥンヌンテジ 풀뜯는돼지
⏰ 11:00〜22:00
🗺️ エリア：弘大
📝 推しメニュー：ミナリサムギョプサル
```

→ 每間店獨立抽出，而且**地區／時間／推介菜會配對返正確嗰間店**
（唔會全部變成「明洞」）。

## ⭐ 唔用 AI 模型都做得起（實測覆蓋率）

**呢個係最重要嘅結論。** 用你真實數據實測（見 `coverage-report.md`）：

| 案例 | 結果 | 使唔使 AI |
|---|---|---|
| Google Maps 短連結 | 波止場食堂 レストハウス店 · 神奈川県横浜市鶴見区 · 座標 ✓ · 〒231-0017 | ❌ |
| IG Reel（貼 caption） | 韓國 › 聖水洞 · 番地 315-71 · 11:00-24:00 | ❌ |
| ＋用戶補一行店名 | 搜尋補完座標／電話 | ❌ |
| 一帖多店 | 拆成 N 間，各自地區＋時間＋推介菜 | ❌ |

**全部功能用嘅服務都係免費、免 key、免 AI：**

| 功能 | 用咩 |
|---|---|
| 文字解析 | 自寫 rule-based（正則 + 詞典） |
| URL 結構解析 | Google Maps / YouTube |
| 短連結展開 | mobile UA → HTTP 302 |
| 網頁結構化資料 | JSON-LD / og:* |
| 地名模糊搜尋 | Photon（komoot / OSM） |
| **座標反查地區** | Nominatim reverse |
| 搵高質來源 | DuckDuckGo HTML |
| 地圖 | Leaflet + OSM |

**唯一缺口：純圖片**（冇 caption、冇 link、冇一個字）。
兩個做法：① 叫用戶打一行店名（5 秒，$0，建議）② OCR。

> ⚠️ **半個缺口**：caption 本身冇寫店名（例如純資料帖「⏰… 🗺️ エリア：明洞」）。
> 唔係做唔到，係需要用戶補一行。**UI 要接受呢件事，唔好當佢係失敗。**

## 四層 Pipeline（核心設計）

```
Layer 1  URL 結構解析         免費、即時、完全合法
         Google Maps → 店名 + 精確座標（100% 準）
              ↓ 信心 < 70%
Layer 2  抓 HTML 的結構化資料  免費、合法（網站自願公開）
         JSON-LD（schema.org）> og:* > <title>
              ↓ 仲係唔夠
Layer 3  LLM 抽文字           有免費額度
         caption / 正文 → 店名 + 地區 + 分類
              ↓ 仲係唔得
Layer 4  用戶補：貼文字 / 截圖   永遠保留
         ← 呢層係產品設計，唔係失敗
```

## ⚠️ 各來源實測結果（2026-10，唔好靠估）

| 來源 | 實測結果 | 對策 |
|---|---|---|
| **Google Maps link** | ✅ **最強**。店名 + 精確座標，100% 免費合法 | 主力來源，永遠先試 |
| **Tabelog** | ✅ **極強**。JSON-LD 有店名、地址、電話、座標、評分、價錢、圖 | 直接用 |
| **一般網站** | ✅ 好。有 JSON-LD 就 88%+，冇就靠 og:* (~55%) | 直接用，睇有冇 JSON-LD |
| **YouTube** | ✅ 好。官方 oEmbed（免費、合法）攞到標題 + 縮圖 | 直接用 |
| **Instagram** | ❌ **server-side 完全死**。所有請求 302 去 `/accounts/login/`，零 og 標籤 | ① 用戶貼 caption ② 截圖 + AI 睇圖 ③ reader 服務（唔穩） |
| **小紅書** | ❌ 反爬嚴格 | 唔好嘗試繞過，引導用戶貼文字 / 上傳截圖 |

### Instagram 嘅詳細記錄（重要）

```
1. 直接抓 HTML          → 302 → /accounts/login/，645KB login 頁，零資料
2. r.jina.ai reader     → 第一次成功！拎到 caption 全文 + 創作者名
                         → 之後連續 403（Cloudflare rate limit）
3. 其他免費 proxy       → allorigins 522、corsproxy 403
```

**結論**：IG 冇穩定嘅免費 server-side 方案。
呢個係產品設計約束，唔係技術問題 —— 所以 **「貼 caption」同「截圖」必須係一等公民功能**，
唔可以當佢係 fallback。

如果要用 reader：去 <https://jina.ai/reader> 拎免費 API key，
放喺環境變數 `WANDER_JINA_KEY`，會穩定好多。

```bash
export WANDER_JINA_KEY="jina_xxxxxxxx"
python -m wander parse "https://www.instagram.com/p/xxxx/"
```

## ⚠️ 更多踩過嘅坑（改 code 之前必睇）

**1. `[^\s]{0,6}` 唔會 match 夾住空格嘅內容**

```python
re.search(r"(特別市)[^\s]{0,6}(区)", "ソウル特別市 城東区")   # → None ❌
re.search(r"(特別市).{0,6}(区)",      "ソウル特別市 城東区")   # → 命中 ✅
```

原因：quantifier **最左最短優先**，會先試 0 個字元，跟住要求下一個字係「区」，
但撞到空格 → 失敗，而且唔會擴展再試。**凡係中間可能夾空格，就唔可以用 `[^\s]{0,n}`。**

**2. Google Maps 短連結要 mobile UA 先出 redirect**

```
desktop UA → 200 + JS redirect 頁，HTML 完全冇目標 URL
iPhone UA  → 302 + Location header，有店名 + 精確座標 ✅
```

**3. 同名地區會撞板**

「城東区」同時係首爾同大阪嘅地名 → 冇國別快篩就會將首爾地址歸入大阪。
解法：先做國別快篩（諺文／`特別市`／`ソウル`），命中就只掃該國詞典。

**4. 「郡」後面嘅「町」係市級，唔係地區**

```
糟屋郡粕屋町長者原東1-12-15
  → city = 粕屋町（唔係 district）
```

**5. 同長度時要按後綴具體度排序**

「糟屋郡」同「粕屋町」都係 3 個字，字典順序會令「郡」贏 → 錯。
要 `区 > 市 > 町 > 村 > 郡` 咁排。

**6. 韓國地址用諺文，詞典用漢字**

`성수동` ↔ `聖水洞`、`명동` ↔ `明洞`。
要 alias 表，統一存漢字，否則同一個地方有兩個名，去重會爆。

**7. 唔可以用貪婪 regex 由左邊剝都道府縣**

```
"東京都渋谷区神宮前1-2-3"
 貪婪剝 → "京都渋谷区神宮前1-2-3"   ❌（由位置 1 開始匹配「京都」）
 明確清單 → "神宮前1-2-3"           ✅
```

## 檔案結構

```
engine/
  wander/
    __init__.py     對外 API
    models.py       Item / DateRange 資料模型（整個系統嘅合約）
    lexicon.py      地名詞典 + 分類規則 ← 加國家只需要改呢個檔
    caption.py      文字解析引擎（rule-based，有解釋性）
    links.py        URL 分類 + Google Maps 結構解析（唔使上網）
    fetch.py        真正抓網頁：JSON-LD / og:* / oEmbed / reader
    lookup.py       ⭐ 由店名反查（Photon + Nominatim + DuckDuckGo）
    ua.py           共用 User-Agent（踩過三次坑先寫成）
    cli.py          命令列介面
tests/
  test_parser.py    用真實 caption 做 golden test（用户 2026-10 提供）
  test_lookup.py    lookup 模組（唔使上網 + network 兩類）
```

## 設計決定（同原因）

**1. 規則為先，LLM 為 fallback**
解釋性好（用戶睇得到「點解抽出呢個答案」）、零成本、快、可審計。
LLM 只用嚟救規則 miss 嘅 case，控制成本。

**2. 保留所有 `raw_*` 欄位**
將來改進算法時可以將所有舊 link 重新跑一次，唔會蝕資料。
做 data product 最重要嘅習慣。

**3. 分類永遠存英文 enum**
`food` 而唔係「美食」。顯示時先翻譯（`CATEGORY_LABELS`）。
加語言只係加翻譯，唔會動到資料。

**4. 「品牌來源」同「實際位置」一定要分開**
「長岡**博多**天婦羅」實際喺**銅鑼灣**。
如果見到「博多」就歸類福岡，用戶去到銅鑼灣就撲空。
→ `brand_from` 欄位專門處理，有測試守住。

**5. 唔穩定嘅外部服務唔可以做主力**
r.jina.ai 第一次成功、第二次 403。
所以 IG 對策係「用戶提供內容」而唔係「靠第三方服務」。

## 已知限制

- 地名詞典只有日本（福岡為主）、香港、韓國、台灣。其他國家要加 `lexicon.py` 或者用 OSM Nominatim。
- 「品牌來源」判斷靠店名關鍵字，日文店名冇「福岡／博多／九州」字眼就會 miss。
- 分類係關鍵字比對，`「食」` 呢種太闊嘅字會誤中。
- Instagram 冇穩定免費方案（見上）。
- 未做：robots.txt 快取、rate limit、重試、OCR 截圖、Nominatim 座標反查。

## 下一步

1. ~~Nominatim 反查~~ ✅ **做完**（`reverse_geocode` + `apply_reverse_geocode`）
2. **併入 app** —— 用 FastAPI 包成 `/api/parse` + `/api/lookup` ← **建議下一步**
   （唔使 AI 已經夠做起點，先做產品，有真實用戶先考慮加 AI）
3. **OCR（可選）** —— 只為「純圖片」呢個缺口；Gemini 免費額度或本地 PaddleOCR
4. **LLM fallback（可選）** —— 規則 miss 時抽地名
5. **加國家 config** —— 泰國、越南深度支援

## 用 pytest 跑測試

```bash
python -m pytest tests              # 97 個唔使上網嘅測試（0.5 秒）
python -m pytest tests -m network   # 8 個要上網嘅測試（~1 分鐘）
```
