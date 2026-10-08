# 吉祥物圖生成指引

> ⚠️ **我（AI 助手）生成唔到圖** —— 我冇圖像生成能力，只可以寫程式畫。
> 所以呢個檔案係**你**用任何 AI 圖生成工具時嘅「提示詞 + 規格」。
> 你生成完放低 4 個 PNG，接入嘅工作我已經做好。

---

## 一、要生成邊 4 張

| 檔名 | 表情 | 用途 |
|---|---|---|
| `mascot-hello.png` | 打招呼（一隻手舉起） | 新手教學第 1 頁 |
| `mascot-point.png` | 指住（手伸向右） | 新手教學逐個 app 講解 |
| `mascot-happy.png` | 開心（雙手舉起） | 教學最後一頁 |
| `mascot-oh.png` | 驚訝（O 嘴） | 備用 |

**另外可選**：`mascot-face.png`（只有頭，正方形）—— 你未必要。

---

## 二、規格（好重要，唔啱就要重做）

```
格式      PNG（透明底）
大細      最少 400×500（或任何 4:5 比例）
           ⚠️ 唔要正方形（人物係直向）
背景      **完全透明**（唔要白色底、唔要背景圖）
內容      一個角色，置中，腳底離底邊約 5%
邊緣      ⚠️ 唔要黑邊框、唔要白邊框、唔要「剪影光暈」
```

⚠️ **唔要**：
- 加文字／水印
- 格仔背景（AI 好易加「透明格仔圖案」）
- 多過一個角色
- 背景嘅房間／風景（我哋自己鋪星雲背景）

---

## 三、提示詞（直接複製去用）

### 共用風格前綴（每張都要有）

```
pixel art character sprite, chibi proportions (head about 1/3 of height),
full body, standing, facing viewer, transparent background,
limited 10-16 color palette,
white silver hair with subtle purple-to-cyan gradient on the hair edges,
dark purple and cyan chromatic aberration outline,
clean hard pixel edges, no anti-aliasing, no dithering,
retro 16-bit game sprite style, no text, no watermark,
centered, feet near bottom edge
```

### ① 打招呼 `mascot-hello.png`

```
pixel art character sprite, chibi proportions, full body, standing,
facing viewer, transparent background, limited 16 color palette,
white silver hair with purple-to-cyan gradient edges,
dark purple and cyan chromatic outline, hard pixel edges,
16-bit retro game sprite,
one arm raised up beside the head in a friendly wave,
warm smile, small friendly eyes with white highlights,
pink and cyan outfit, small backpack strap,
no text, no watermark, centered
```

### ② 指住 `mascot-point.png`

```
pixel art character sprite, chibi proportions, full body, standing,
facing viewer, transparent background, limited 16 color palette,
white silver hair with purple-to-cyan gradient edges,
dark purple and cyan chromatic outline, hard pixel edges,
16-bit retro game sprite,
one arm extended straight out to the right pointing with index finger,
confident smile, small friendly eyes with white highlights,
pink and cyan outfit, small backpack strap,
no text, no watermark, centered
```

### ③ 開心 `mascot-happy.png`

```
pixel art character sprite, chibi proportions, full body, standing,
facing viewer, transparent background, limited 16 color palette,
white silver hair with purple-to-cyan gradient edges,
dark purple and cyan chromatic outline, hard pixel edges,
16-bit retro game sprite,
both arms raised up in the air celebrating,
big happy open smile, eyes slightly squinted in joy,
pink and cyan outfit, small backpack strap,
no text, no watermark, centered
```

### ④ 驚訝 `mascot-oh.png`

```
pixel art character sprite, chibi proportions, full body, standing,
facing viewer, transparent background, limited 16 color palette,
white silver hair with purple-to-cyan gradient edges,
dark purple and cyan chromatic outline, hard pixel edges,
16-bit retro game sprite,
small round open mouth shaped like an O, wide surprised eyes,
both hands slightly raised near chest,
pink and cyan outfit,
no text, no watermark, centered
```

---

## 四、用邊個工具

| 工具 | 好處 | 注意 |
|---|---|---|
| **ChatGPT / Gemini 內置圖生成** | 免費、最易 | 要明確講「透明背景」 |
| **Midjourney** | 質素最好 | 付費；`--no background` |
| **Stable Diffusion + pixel-art LoRA** | 最似像素風 | 要本地裝 |
| **Adobe Firefly** | 商業安全 | 免費額度 |
| **Remove.bg**（後製） | 去背 | 如果 AI 出咗背景 |

⚠️ **如果生成出嚟有背景** → 用 [remove.bg](https://remove.bg) 或者 macOS 內置「移除背景」去背就得。

---

## 五、放去邊

```bash
# 放呢 4 個檔案入：
web/public/mascot-hello.png
web/public/mascot-point.png
web/public/mascot-happy.png
web/public/mascot-oh.png
```

然後跑：

```bash
cd engine && python check_mascot.py
```

會檢查：
- ✓ 4 個檔案都存在
- ✓ 係 PNG 而且有透明通道
- ✓ 大細夠（≥ 300×400）
- ✓ 透明背景比例合理（唔係全白底）
- ✓ 主角佔畫面嘅比例合理

---

## 六、接入（唔使你改 code）

我已經寫好**自動切換**：

```
如果 web/public/mascot-hello.png 存在
   → 用你生成嗰張
否則
   → 用我自己程序化畫嗰張（做 fallback）
```

所以你**唔放都得** —— 會用返我畫嗰個。
你放咗就自動用你嗰個，唔使改任何 code。

---

## ⚠️⚠️⚠️ 重要教訓：唔好用**白色背景**生成！

### 實測你畀嘅 6 張圖

| 圖 | 狀態 | 問題 |
|---|---|---|
| `her-idle` | ✅ 完整 | — |
| `her-give` | ✅ 完整 | — |
| `her-hold` | ⚠️ | **白頭髮**被褪走 |
| `him-idle` | ❌ | **成套白西裝**被褪走 |
| `him-take` | ⚠️ | **白恤衫**被褪走 |
| `him-soft` | ⚠️ | **白西裝**被褪走 |

### ⚠️ 原因

AI 去背嘅邏輯係「**白色 = 背景**」——
但你嘅角色**白頭髮 + 白西裝**，一樣係白色。

```
背景白  ┐
        ├── 一樣色 → AI 分唔清 → 兩樣都褪走
白西裝  ┘
```

### ⚠️⚠️ 而壞咗嘅圖**救唔返**

我檢查過透明區嘅 RGB：

```
him-idle  透明區 RGB 平均 (16, 17, 21)   ← 近黑，唔係白
her-hold  透明區 RGB 平均 (3, 2, 7)      ← 同上
```

即係原本嘅顏色**冇保存**（好多工具會保留 RGB、只改 alpha，
咁就救得返；但呢 6 張冇）。

我試過用「最近像素填補」修補 —— **冇用**，
因為西裝嘅透明區連住外面背景（經領口），唔算「洞」。

### ✅ 正確做法：用**非白色**背景生成

提示詞加一句：

```
solid bright green background (#00ff00), flat color background
```

⚠️ 唔好用白色、唔好用「透明背景」——
AI 出嘅「透明背景」通常就係白底 + 假透明。

然後跑：

```bash
cd engine
python cutout.py 你嘅圖/ -o ../web/public/ --prefix mascot-
python cutout.py --check ../web/public/mascot-*.png
```

### ⚠️ 去背工具嘅智能判斷

```python
bg_is_whitish = all(int(c) > 200 for c in bg)

if bg_is_whitish:
    # 白底 → 只可以由**邊界 flood fill**
    # （保住角色內部同色嘅部分，但內部碎點褪唔到）
else:
    # 非白底（鮮綠／洋紅）→ 可以**全域**褪
    # （連角色內部嘅背景碎點都褪得到）
```

**實測（合成圖）：**
```
鮮綠底 + 白西裝  →  背景透明 76.9% ✅   白西裝 alpha 255 ✅   綠洞 alpha 0 ✅
白底   + 白西裝  →  白西裝 alpha 170 ⚠️ 被食咗一部分
```

### 💡 意外嘅好消息

你嗰 4 張「白西裝透明」嘅圖，喺**深色星雲底**上面
睇落似**深色西裝** —— 竟然合理。

但呢個係好彩，唔係設計。想根治就重新生成。

## 七、如果唔想搞

完全可以 —— 用返我程序化畫嗰個（36×44）。
佢款式統一、細細粒、唔會出錯，只係唔夠你參考圖咁精緻。

**新手教學只係 4 格，唔值得為咗佢卡住成個 project。**
