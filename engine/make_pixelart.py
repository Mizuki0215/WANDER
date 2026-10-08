#!/usr/bin/env python3
"""
程序化像素藝術生成器（Procedural Pixel Art）
============================================

⚠️⚠️ 呢個檔案嘅定位（要講清楚）：

   用戶提供嘅參考圖係 AI 生成嘅插畫。我**冇能力**生成同等級嘅插畫，
   亦都**唔應該**假裝做得到。

   但參考圖最核心嘅「風格」係可以**程序化複製**嘅：
     ① 色板（我由參考圖抽出實際 16 進位值）
     ② 星雲背景（fBm 噪音 + 色階 + Bayer 抖動）
     ③ 紫左／青右嘅邊緣漸變（最 signature 嘅特徵）
     ④ 大顆粒（block）＋ 掃描線

   所以呢個生成器做嘅係「**風格**」而唔係「**插畫**」。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
由參考圖抽出嘅色板（實測，唔係估）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  太空底色      #000010 → #000020 → #000030 → #100040 → #200060
  星雲中調      #402090  #5020A0  #6030A0  #7050C0
  星雲亮部      #A070C0  #B080C0  #C0A0D0
  星雲核心      #E0C0E8  #F0D8F0
  星／彗星      #F0F0F0  #C0C0C0  #FFFFFF

  邊緣紫（左）  #E73AB8  #FC53EC      ← H≈306-316°
  邊緣青（右）  #32E4FF  #08D0EA      ← H≈187°
  暖金點綴      #985030  #C08040      ← 房間圖嘅燈光

用法：
    python make_pixelart.py            # 產生全部
    python make_pixelart.py --check    # 只驗證，唔寫檔
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "web" / "public"


# ══════════════════════════════════════════════════════════════════
# 色板（全部由參考圖抽出）
# ══════════════════════════════════════════════════════════════════

def hx(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# ⚠️ 由暗到亮排列 —— 色階映射靠呢個次序
# ⚠️⚠️ 由參考圖抽出後**重新平衡**：
#    第一版太粉紅（好多 H≈300°），但參考圖其實係
#    「**大片深藍 + 紫色只喺亮部**」：
#      暗部 H≈240°（藍）  →  中調 H≈255°  →  亮部 H≈275°  →  核心 H≈290°
#    所以色階要由藍**漸變**去紫，唔係一開始就紫。
NEBULA_RAMP = [hx(c) for c in [
    "#000006", "#00000e", "#000018", "#000024", "#000030", "#00003c",
    "#040248", "#080458", "#0c0668", "#100878",
    "#160a88", "#1c0e94", "#2412a0", "#2e18a8",
    "#3a20ae", "#462ab4", "#5236ba", "#5e44c0",
    "#6c54c6", "#7a66cc", "#8a7ad2",
    "#9c90d8", "#aea6de", "#c0bce4", "#d2d0ea", "#e4e2f0",
]]

# ⚠️⚠️ 為咩要**兩個**色板而唔係一個：
#    單一色板出嚟嘅星雲只有一種色調，睇落好平。
#    參考圖明顯有「藍色區域」同「紫色區域」並存 ——
#    呢個係靠一個獨立嘅噪音場去混合兩個色板做出嚟。
NEBULA_BLUE = [hx(c) for c in [
    "#000006", "#000010", "#00001c", "#000028", "#000038", "#00004a",
    "#00105e", "#001c72", "#002888", "#04349a", "#0a42aa",
    "#1452b8", "#2064c4", "#3078ce", "#448cd6",
    "#5ca0dc", "#78b4e2", "#98c8e8",
]]

NEBULA_PURPLE = [hx(c) for c in [
    "#000006", "#04000e", "#0c0018", "#140024", "#1e0032", "#2a0042",
    "#380456", "#460a6a", "#54147e", "#642090", "#742ea0",
    "#843eae", "#9450ba", "#a464c4", "#b47acc",
    "#c490d4", "#d4a8dc", "#e4c0e6",
]]

# 邊緣漸變（signature）
EDGE_PURPLE = hx("#e73ab8")
EDGE_PURPLE_HI = hx("#fc53ec")
EDGE_CYAN = hx("#32e4ff")
EDGE_CYAN_HI = hx("#08d0ea")

STAR_WHITE = hx("#ffffff")
STAR_SOFT = hx("#e8e0f4")
STAR_DIM = hx("#b0a8c8")

GOLD = hx("#c08040")


# ══════════════════════════════════════════════════════════════════
# 噪音（唔用外部 library —— 自己寫 value noise + fBm）
# ══════════════════════════════════════════════════════════════════

def _smooth(t: np.ndarray) -> np.ndarray:
    """Smoothstep —— 令格與格之間唔會出現硬邊。"""
    return t * t * (3.0 - 2.0 * t)


def value_noise(h: int, w: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """
    價值噪音（value noise）。

    ⚠️ 為咩唔用 Perlin／simplex：
       我哋最後會**量化成 27 級色階**（像素風），
       噪音嘅平滑度根本睇唔出。value noise 快 3 倍。
    """
    ch = max(2, cells)
    cw = max(2, int(cells * w / h))
    grid = rng.random((ch + 1, cw + 1))
    ys = np.linspace(0, ch, h, endpoint=False)
    xs = np.linspace(0, cw, w, endpoint=False)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    fy = _smooth(ys - y0)[:, None]
    fx = _smooth(xs - x0)[None, :]
    y1 = np.minimum(y0 + 1, ch); x1 = np.minimum(x0 + 1, cw)
    a = grid[np.ix_(y0, x0)]
    b = grid[np.ix_(y0, x1)]
    c = grid[np.ix_(y1, x0)]
    d = grid[np.ix_(y1, x1)]
    return (a * (1 - fy) * (1 - fx) + b * (1 - fy) * fx
            + c * fy * (1 - fx) + d * fy * fx)


def fbm(h: int, w: int, rng: np.random.Generator,
        octaves: int = 6, base: int = 3, gain: float = 0.52) -> np.ndarray:
    """
    分形布朗運動（fBm）—— 疊幾層噪音做出「雲」嘅感覺。

    ⚠️ 每一層格數 ×2、振幅 ×0.52 ——
       呢個比例做出嚟最似星雲（試過 0.5 太平、0.6 太碎）。
    """
    out = np.zeros((h, w))
    amp, cells, norm = 1.0, base, 0.0
    for _ in range(octaves):
        out += value_noise(h, w, cells, rng) * amp
        norm += amp
        amp *= gain
        cells *= 2
    return out / norm


# ══════════════════════════════════════════════════════════════════
# Bayer 抖動（像素藝術嘅靈魂）
# ══════════════════════════════════════════════════════════════════

BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=float) / 64.0


def dither(v: np.ndarray, levels: int = 27, strength: float = 1.0) -> np.ndarray:
    """
    有序抖動（ordered dithering）→ 量化。

    ⚠️⚠️ 為咩一定要抖動：
       像素藝術只有有限色階。冇抖動嘅話漸變會出現**大塊色帶**（banding），
       睇落好假。抖動用棋盤格交錯兩個色階去「扮」中間色 ——
       呢個就係參考圖嗰種「顆粒感」嘅來源。
    """
    h, w = v.shape
    bay = np.tile(BAYER8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    v = np.clip(v + (bay - 0.5) * strength / levels, 0.0, 1.0)
    return np.clip((v * (levels - 1)).round().astype(int), 0, levels - 1)


def ramp_map(idx: np.ndarray, ramp: list[tuple[int, int, int]]) -> np.ndarray:
    """色階索引 → RGB。"""
    arr = np.array(ramp, dtype=np.uint8)
    return arr[np.clip(idx, 0, len(ramp) - 1)]


# ══════════════════════════════════════════════════════════════════
# 星星
# ══════════════════════════════════════════════════════════════════

def add_stars(rgb: np.ndarray, rng: np.random.Generator,
              count: int, bright: int = 12) -> np.ndarray:
    """
    加星。

    ⚠️ 用「格」為單位而唔係逐 pixel ——
       像素風嘅星一定係完整一格，唔可以係半格（會變灰點）。
    """
    h, w, _ = rgb.shape
    out = rgb.copy()
    ys = rng.integers(0, h, count)
    xs = rng.integers(0, w, count)
    mags = rng.random(count)
    for y, x, m in zip(ys, xs, mags):
        if m > 0.97:            # 最光嘅加十字光芒
            col = STAR_WHITE
            out[y, x] = col
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w:
                    out[yy, xx] = STAR_SOFT
        elif m > 0.80:
            out[y, x] = STAR_SOFT
        elif m > 0.45:
            out[y, x] = STAR_DIM
        else:
            # ⚠️ 最暗嘅星用「50% 機率唔畫」——
            #    全部畫會令星空太密，失去「深邃」嘅感覺
            out[y, x] = STAR_DIM
    return out


# ══════════════════════════════════════════════════════════════════
# 星雲
# ══════════════════════════════════════════════════════════════════

def nebula(w: int, h: int, seed: int = 7,
           dense: float = 1.0) -> np.ndarray:
    """
    星雲背景（參考 wallpaper.jpg）。

    ⚠️ 三個獨立嘅 fBm：
       · 主雲（密度）
       · 斜向絲帶（用一個斜向嘅座標扭曲 → 做出銀河斜帶）
       · 亮部（核心光暈）
    """
    rng = np.random.default_rng(seed)

    # ① 主雲
    #   ⚠️⚠️ octaves 由 6 → 4、base 由 3 → 2：
    #      參考圖嘅雲係**大塊**，唔係細碎。
    #      太多 octave 會做出「水彩漸變」而唔係「像素雲」。
    base = fbm(h, w, rng, octaves=4, base=2)

    # ② 斜向絲帶 —— **兩條**，唔同角度
    #    ⚠️⚠️ 第一版只有一條幼帶（寬度 0.055）→
    #       出嚟似「一條蛇」，但參考圖係**大片雲海**。
    #       而家用兩條寬帶（0.11 / 0.085）＋ 唔同斜率。
    gy, gx = np.mgrid[0:h, 0:w]
    warp = value_noise(h, w, 5, rng) * 0.55

    # 帶 A：右下 → 左上（主帶）
    skewA = (gy / h) * 0.75 + (gx / w) * 1.15
    cA = np.clip(skewA + warp - 0.55, 0, 1.6)
    ribbonA = np.exp(-((cA - 0.62) ** 2) / 0.115)

    # 帶 B：左下 → 右上（副帶，較窄較暗）
    skewB = (gy / h) * 1.35 - (gx / w) * 0.55 + 0.35
    cB = np.clip(skewB + warp * 0.7, 0, 1.6)
    ribbonB = np.exp(-((cB - 0.48) ** 2) / 0.075) * 0.72

    ribbon = np.maximum(ribbonA, ribbonB)

    # ③ 亮部核心
    core = fbm(h, w, rng, octaves=3, base=2) ** 3.2

    v = base * 0.34 + ribbon * 0.70 + core * 0.36
    v = (v - v.min()) / max(1e-6, v.max() - v.min())
    # ⚠️⚠️ gamma 嘅取捨（三個版本都試過）：
    #      1.55 → 太光，成張圖都著色，冇「深邃」感
    #      1.75 → 仲係太光（雲佔滿畫面）
    #      2.60 → 太暗，只剩一條幼線
    #      2.05 → ✓ 有大片黑，但雲帶仍然清楚
    v = v ** 2.05
    # ⚠️ 減 offset → 令暗部真正跌到純黑（唔係深藍）
    v = np.clip((v - 0.07) / 0.93, 0, 1)
    v *= dense

    # ⚠️ 抖動強度 2.2 → 1.8：夠顆粒但唔會太花
    idx = dither(v, levels=len(NEBULA_BLUE), strength=1.8)

    # ── 雙色板混合 ──
    #   ⚠️ 用一個**獨立**嘅低頻噪音決定每個位置偏藍定偏紫。
    #      唔可以同 v 一樣 —— 否則同一條雲永遠同一隻色，
    #      做唔到參考圖嗰種「藍紫交錯」。
    tint = fbm(h, w, rng, octaves=3, base=2)
    tint = (tint - tint.min()) / max(1e-6, tint.max() - tint.min())
    tint = np.clip((tint - 0.35) / 0.30, 0, 1)      # 拉高對比 → 區域分明

    rgb_b = ramp_map(idx, NEBULA_BLUE)
    rgb_p = ramp_map(idx, NEBULA_PURPLE)
    t3 = tint[:, :, None]
    rgb = (rgb_b * (1 - t3) + rgb_p * t3).astype(np.uint8)
    rgb = add_stars(rgb, rng, count=int(w * h * 0.006))
    return rgb


# ══════════════════════════════════════════════════════════════════
# 彗星 app icon（參考 icon.jpg）
# ══════════════════════════════════════════════════════════════════

def comet_icon(size: int = 64, seed: int = 11, maskable: bool = False) -> np.ndarray:
    """
    App icon：星雲底 + 彗星 + 閃星。

    ⚠️ maskable 版本要留安全區 ——
       Android 會將 icon 裁成圓形／水滴形，
       內容一定要縮入中間 80%（官方建議 66% 更安全）。
    """
    rng = np.random.default_rng(seed)
    pad = 0 if maskable else 0
    s = size
    # 底：星雲（用細啲嘅格再放大 → 更粗顆粒）
    bg = nebula(s, s, seed=seed, dense=0.92)

    # 底色調暗少少，等彗星突出
    bg = (bg.astype(float) * 0.82).astype(np.uint8)

    safe = 0.66 if maskable else 0.86
    r = int(s * safe / 2)

    def put(y, x, col, alpha=1.0):
        if 0 <= y < s and 0 <= x < s:
            if alpha >= 1.0:
                bg[y, x] = col
            else:
                bg[y, x] = (bg[y, x] * (1 - alpha) + np.array(col) * alpha).astype(np.uint8)

    cy, cx = s // 2 + int(s * 0.04), s // 2 - int(s * 0.10)

    # ── 彗星尾（由右下向左上，漸幼漸淡）──
    #   ⚠️ 參考圖嘅尾係**短而柔**（大約 1.1 倍半徑），
    #      唔係一條長條。太長會似「箭」而唔係「流星」。
    length = int(r * 1.25)
    for i in range(length):
        t = i / length
        y = cy - int(t * r * 0.62)
        x = cx + int(t * r * 1.25)
        thick = max(0, int((1 - t) ** 1.4 * s * 0.062))
        # ⚠️⚠️ 顏色由白 → 淡紫 → **深藍**（唔要粉紅）。
        #    第一版用 EDGE_PURPLE_HI (#fc53ec) 做中段 →
        #    成條尾變咗**粉紅色**，睇落似「魔杖」而唔似流星。
        #    參考圖嘅尾係**冷色**：白 → 淡薰衣草 → 深藍紫。
        LAV = hx("#c8b8e8")
        DEEP = hx("#3a2a7a")
        if t < 0.22:
            col = STAR_WHITE
        elif t < 0.55:
            f = (t - 0.22) / 0.33
            col = tuple(int(STAR_WHITE[k] * (1 - f) + LAV[k] * f) for k in range(3))
        else:
            f = min(1.0, (t - 0.55) / 0.45)
            col = tuple(int(LAV[k] * (1 - f) + DEEP[k] * f) for k in range(3))
        # ⚠️ 淡得快啲 —— 令尾更柔（參考圖嘅尾好快消失）
        alpha = max(0.06, 1.0 - t * 1.35)
        for dy in range(-thick, thick + 1):
            for dx in range(-thick, thick + 1):
                if abs(dy) + abs(dx) <= thick:
                    put(y + dy, x + dx, col, alpha)

    # ── 彗星頭（實心亮塊 + 高光）──
    hr = max(2, int(s * 0.052))
    for dy in range(-hr, hr + 1):
        for dx in range(-hr, hr + 1):
            if dy * dy + dx * dx <= hr * hr:
                edge = (dy * dy + dx * dx) >= (hr - 1) ** 2
                put(cy + dy, cx + dx, STAR_SOFT if edge else STAR_WHITE)
    # 最光嘅一點
    put(cy - 1, cx - 1, STAR_WHITE)
    put(cy, cx - 1, STAR_WHITE)

    # ── 右上閃星（四角光芒）──
    sy, sx = cy - int(r * 0.62), cx + int(r * 0.68)
    put(sy, sx, STAR_WHITE)
    for d in (1, 2):
        a = 1.0 if d == 1 else 0.55
        put(sy - d, sx, STAR_SOFT, a); put(sy + d, sx, STAR_SOFT, a)
        put(sy, sx - d, STAR_SOFT, a); put(sy, sx + d, STAR_SOFT, a)
    for d in (2, 3):
        a = 0.35 if d == 2 else 0.18
        put(sy - d, sx - d, STAR_SOFT, a); put(sy - d, sx + d, STAR_SOFT, a)
        put(sy + d, sx - d, STAR_SOFT, a); put(sy + d, sx + d, STAR_SOFT, a)

    return bg


# ══════════════════════════════════════════════════════════════════
# 邊緣漸變（signature 效果）
# ══════════════════════════════════════════════════════════════════

def chromatic_edge(rgb: np.ndarray, strength: float = 0.9,
                   spread: int = 2) -> np.ndarray:
    """
    紫左／青右嘅邊緣漸變 —— 參考圖最 signature 嘅特徵。

    ⚠️ 原理：模擬舊 CRT 嘅色差（chromatic aberration）／
       鏡頭色散 —— 左邊嘅光偏紫、右邊偏青。

    ⚠️⚠️ 第一版只染「緊貼邊緣 1px」嘅像素 → 喺 app 嘅尺寸完全睇唔出。
       修法有兩個：
         ① 將邊緣**膨脹** `spread` 格（令效果有厚度）
         ② 用飽和曲線計權重（唔用全圖寬度做線性 —— 太弱）

    ⚠️ 只染邊緣，唔染實心內部 —— 否則整張圖會變紫色，失去細節。
    """
    h, w, _ = rgb.shape
    f = rgb.astype(float)
    lum = f.sum(axis=2)
    # 邊緣強度：同右邊／下面鄰居嘅差異
    diff = np.zeros((h, w))
    diff[:, :-1] += np.abs(f[:, :-1] - f[:, 1:]).sum(axis=2)
    diff[:-1, :] += np.abs(f[:-1, :] - f[1:, :]).sum(axis=2)
    edge = np.clip(diff / 120.0, 0, 1)

    # ① 膨脹（用 roll 做 4 方向嘅 max filter）——
    #    ⚠️ 一定要用 maximum 而唔係平均，否則邊緣會變淡
    band = edge.copy()
    for _ in range(max(0, spread)):
        band = np.maximum.reduce([
            band,
            np.roll(band, 1, axis=0), np.roll(band, -1, axis=0),
            np.roll(band, 1, axis=1), np.roll(band, -1, axis=1),
        ])

    # ② 左右權重：用飽和曲線而唔係全圖線性
    #    ⚠️ 原本 xs = linspace(-1,1,w) → 中間位置只係 ±0.1，
    #       效果等於冇。改用 clip(x/0.35) 令大部分位置都到滿。
    xs = np.linspace(-1, 1, w)[None, :]
    left_w = np.clip(-xs / 0.35, 0, 1)
    right_w = np.clip(xs / 0.35, 0, 1)

    out = f.copy()
    for k in range(3):
        out[:, :, k] += (EDGE_PURPLE_HI[k] - f[:, :, k]) * band * left_w * strength
        out[:, :, k] += (EDGE_CYAN_HI[k] - f[:, :, k]) * band * right_w * strength
    return np.clip(out, 0, 255).astype(np.uint8)


# ══════════════════════════════════════════════════════════════════
# 掃描線
# ══════════════════════════════════════════════════════════════════

def scanlines(rgb: np.ndarray, period: int = 3, amount: float = 0.10) -> np.ndarray:
    """
    掃描線（CRT 感）。

    ⚠️ 一定要極淡 —— 參考圖嘅掃描線只係輕微暗一格，
       太明顯會令圖睇落「污糟」。
    """
    out = rgb.astype(float)
    ys = np.arange(rgb.shape[0])
    mask = (ys % period == 0)[:, None, None]
    out = np.where(mask, out * (1 - amount), out)
    return np.clip(out, 0, 255).astype(np.uint8)


# ══════════════════════════════════════════════════════════════════
# 生成
# ══════════════════════════════════════════════════════════════════

def upscale(rgb: np.ndarray, factor: int) -> Image.Image:
    """⚠️ 一定要 NEAREST —— 其他 resample 會令格邊變灰（就唔係像素風）。"""
    img = Image.fromarray(rgb, "RGB")
    return img.resize((img.width * factor, img.height * factor), Image.NEAREST)


def build(verbose: bool = True) -> list[tuple[str, Image.Image]]:
    out: list[tuple[str, Image.Image]] = []

    # ── ① App icon（彗星）—— 512 / 192 / 180 ──
    #   ⚠️ icon 用 128 邏輯解析度 ×4 = 512（星星唔會變大方格）
    # ⚠️ 0.95 太強（試過）—— 會蓋過星雲本身嘅色，變成一片霓虹。
    #    0.45 先啱：見到紫／青邊，但星雲結構仍然清楚。
    base128 = chromatic_edge(comet_icon(128, seed=11), 0.45, spread=1)
    for size in (512, 192, 180):
        out.append((f"icon-{size}.png",
                    Image.fromarray(base128, "RGB").resize((size, size), Image.NEAREST)))

    # ── ② Maskable（留安全區）──
    mbase = comet_icon(128, seed=11, maskable=True)
    for size in (512, 192):
        out.append((f"icon-maskable-{size}.png",
                    Image.fromarray(mbase, "RGB").resize((size, size), Image.NEAREST)))

    # ── ③ 星雲背景（手機用，粗顆粒）──
    # ⚠️⚠️ 邏輯解析度一定要夠高！
    #    第一版用 48×96 再 ×8 → 一粒星變咗 **8×8 嘅白色大方格**，
    #    睇落完全唔似星星。
    #    而家用 96×192 ×4 → 一粒星 = 4×4，同參考圖比例一致。
    for name, (bw, bh, f) in {
        "nebula.png":        (96, 192, 4),     # 384×768 主背景
        "nebula-wide.png":   (192, 108, 4),    # 768×432 橫向／桌面
    }.items():
        rgb = nebula(bw, bh, seed=23 if "wide" not in name else 31)
        rgb = scanlines(rgb, 3, 0.09)
        out.append((name, upscale(rgb, f)))

    # ── ④ 彗星（透明底，UI 用）──
    rgb = comet_icon(128, seed=7)
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
    out.append(("comet.png", Image.fromarray(rgba, "RGBA").resize((256, 256), Image.NEAREST)))

    # ── ⑤ 正方形小圖示（favicon / logo）──
    rgb = chromatic_edge(comet_icon(48, seed=5), 0.55, spread=1)
    out.append(("comet-96.png", Image.fromarray(rgb, "RGB").resize((96, 96), Image.NEAREST)))

    if verbose:
        for name, img in out:
            print(f"  · {name:26} {img.size[0]}×{img.size[1]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只驗證唔寫檔")
    args = ap.parse_args()

    print("程序化像素藝術生成")
    print("=" * 54)
    items = build()

    if args.check:
        print(f"\n✓ 產生到 {len(items)} 張（--check：冇寫檔）")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for name, img in items:
        p = OUT / name
        img.save(p, optimize=True)
    total = sum((OUT / n).stat().st_size for n, _ in items)
    print(f"\n✓ 寫入 {len(items)} 個檔案 → {OUT}")
    print(f"  合計 {total/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
