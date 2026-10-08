#!/usr/bin/env python3
"""
程序化像素角色生成器（Pixel Character）
========================================

⚠️⚠️ 為咩要重寫：

   用戶原話：「你個示範教學呢第一就係個人物太樣衰啦，
              我俾咗啲圖你，你可以參考吓啦」

   第一版係一個 16×16 手畫嘅 blob —— 只有一隻色、冇面、冇衫、
   冇光影。參考圖嘅角色係**幾十隻色 + 分層光影 + 漸變邊**。

   手畫一個 36×44（1584 格）嘅角色唔現實，所以改用**程序化**：

     ① 用 PIL 喺**邏輯解析度**直接畫硬邊橢圓／多邊形
        （⚠️ PIL 嘅 ellipse 喺 1x 係硬邊嘅 —— 正好就係像素藝術要嘅嘢）
     ② 每個部件有自己嘅**色階**（3-5 級）
     ③ 統一光源（左上）決定每格用邊一級
     ④ 加描邊（outline）
     ⑤ 最後套用紫左／青右邊緣漸變

   呢個做法嘅好處：可以快速試唔同比例，而唔使逐格數。

用法：
    python make_character.py --preview     # 出預覽圖
    python make_character.py               # 寫入 web/public
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
# ⚠️⚠️ 程序化角色放喺 `public/proc/`，**唔係** `public/` ——
#    因為 `public/mascot-*.png` 係留畀**用戶自己生成**嗰啲。
#    前端會先試 `public/mascot-X.png`，404 就 fallback 去 `public/proc/mascot-X.png`。
#    如果兩個都放喺同一層就會互相覆蓋。
OUT = ROOT.parent / "web" / "public" / "proc"

sys.path.insert(0, str(ROOT))
from make_pixelart import chromatic_edge  # noqa: E402


def hx(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# ══════════════════════════════════════════════════════════════════
# 邏輯解析度
# ══════════════════════════════════════════════════════════════════
# ⚠️ 36×44 —— 比第一版（16×16）大 5.5 倍。
#    16×16 根本畫唔到眼、鼻、嘴、衫領。
W, H = 36, 44

# ══════════════════════════════════════════════════════════════════
# 色階（由參考圖抽出 + 調整）
# ══════════════════════════════════════════════════════════════════
# ⚠️⚠️ 每個材质要有 **至少 4 級**（高光／亮／中／暗）——
#    只有一級嘅話會變成一嚿色，就係第一版「樣衰」嘅主因。

RAMP = {
    # 頭髮：白 → 淡薰衣草（參考圖嘅 her-idle 就係咁）
    "hair": [hx(c) for c in ["#ffffff", "#f4eeff", "#e0d4f8", "#c4b0e8", "#a088cc"]],

    # 皮膚：暖調（參考圖 her-hold 嘅膚色）
    "skin": [hx(c) for c in ["#f8d4b8", "#eec0a0", "#dca888", "#c08868", "#9c6c50"]],

    # 衫：粉紅（her 嘅裙）—— 4 級
    "cloth": [hx(c) for c in ["#ff9ad4", "#fc53ec", "#e73ab8", "#b8208c"]],

    # 青（點綴／腰帶）
    "cyan": [hx(c) for c in ["#a8f4ff", "#32e4ff", "#08b8d8", "#067a94"]],

    # 眼白 / 眼珠
    "eye": [hx(c) for c in ["#ffffff", "#e8e0f4"]],
    #   ⚠️ 4 級（唔係 3 級）—— 眼嘅層次係可愛度嘅關鍵：
    #      最亮（虹膜反光）→ 虹膜 → 瞳孔 → 眼線
    "iris": [hx(c) for c in ["#8a5ad0", "#6a3ab8", "#3a1a6e", "#12071f"]],
}

# 描邊色
OUTLINE = hx("#1a0b2e")
# 頭髮邊緣嘅紫／青挑染（參考圖最 signature 嘅嘢）
HAIR_PURPLE = hx("#a855f7")
HAIR_CYAN = hx("#22d3ee")


# ══════════════════════════════════════════════════════════════════
# 繪圖工具
# ══════════════════════════════════════════════════════════════════

class Canvas:
    """
    邏輯解析度畫布。

    ⚠️ 用 "material id" 做 mask 而唔係直接填色 ——
       因為要**之後**先計光影（同一個 mask 要填唔同色階）。
    """

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        # 每格記住 (material, 深度 0..1)  —— 深度用嚟揀色階
        self.mat = np.full((h, w), "", dtype=object)
        self.depth = np.zeros((h, w))

    def _stamp(self, mask: Image.Image, mat: str, depth: np.ndarray):
        m = np.array(mask, dtype=bool)
        self.mat[m] = mat
        self.depth[m] = depth[m]

    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                mat: str, light: tuple[float, float] = (-0.55, -0.75),
                curve: float = 1.6):
        """
        畫硬邊橢圓。

        ⚠️⚠️ PIL 喺 1x 解析度畫 ellipse 係**冇抗鋸齒**嘅 ——
           正好就係像素藝術要嘅硬邊。
           （如果畫喺 4x 再縮，邊緣會變灰，就唔係像素風。）

        light：光源方向（預設左上）
        curve：光影對比（大 = 對比強）
        """
        mask = Image.new("L", (self.w, self.h), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
        # 深度：由光源方向計一個 -1..1 嘅梯度，再 map 到 0..1
        gy, gx = np.mgrid[0:self.h, 0:self.w]
        nx = (gx - cx) / max(1e-6, rx)
        ny = (gy - cy) / max(1e-6, ry)
        v = (nx * light[0] + ny * light[1])
        dep = np.clip((v + 1) / 2, 0, 1) ** curve
        self._stamp(mask, mat, dep)

    def poly(self, pts: list[tuple[float, float]], mat: str,
             light: tuple[float, float] = (-0.55, -0.75), curve: float = 1.6,
             cx: float | None = None, cy: float | None = None,
             rx: float | None = None, ry: float | None = None):
        """畫多邊形（衫身、手、腳）。"""
        mask = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        if cx is None:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            rx = rx or max(1e-6, (max(xs) - min(xs)) / 2)
            ry = ry or max(1e-6, (max(ys) - min(ys)) / 2)
        gy, gx = np.mgrid[0:self.h, 0:self.w]
        nx = (gx - cx) / max(1e-6, rx)
        ny = (gy - cy) / max(1e-6, ry)
        v = (nx * light[0] + ny * light[1])
        dep = np.clip((v + 1) / 2, 0, 1) ** curve
        self._stamp(mask, mat, dep)

    # ── 輸出 ──
    def shade(self, ramp: list[tuple[int, int, int]]) -> np.ndarray:
        """深度 → 色階索引 → RGB。"""
        n = len(ramp)
        idx = np.clip((self.depth * (n - 1)).round().astype(int), 0, n - 1)
        arr = np.array(ramp, dtype=np.uint8)
        return arr[idx]

    def to_rgb(self) -> np.ndarray:
        out = np.zeros((self.h, self.w, 3), np.uint8)
        for mat, ramp in RAMP.items():
            m = self.mat == mat
            if m.any():
                out[m] = self.shade(ramp)[m]
        return out

    def mask_of(self, *mats: str) -> np.ndarray:
        m = np.zeros((self.h, self.w), bool)
        for x in mats:
            m |= (self.mat == x)
        return m


# ══════════════════════════════════════════════════════════════════
# 角色
# ══════════════════════════════════════════════════════════════════

def make_character(*, mood: str = "smile", arm: str = "wave",
                   seed: int = 3) -> np.ndarray:
    """
    畫一個角色。

    mood: smile | happy | oh
    arm : wave | point | up | hold

    ⚠️ 比例：**Q 版（chibi）**—— 頭大約佔 45% 高度。
       真實比例嘅角色喺 36×44 只會變成一條火柴人。
    """
    c = Canvas(W, H)

    # ── 座標（全部用比例計，唔寫死 pixel）──
    #   ⚠️ 頭由 0.205 → 0.182（第一版個頭太大，佔咗 55% 高度，
    #      身體變成一嚿。0.182 仍然 Q 版但身體有返空間。
    cx = W * 0.5
    head_cy = H * 0.275
    head_rx = W * 0.215
    head_ry = H * 0.182

    # ── ① 後髮（喺頭後面，所以先畫）──
    c.ellipse(cx, head_cy + H * 0.03, head_rx * 1.16, head_ry * 1.22,
              "hair", curve=1.35)
    # 兩邊長髮（垂落膊頭）
    for sx in (-1, 1):
        c.ellipse(cx + sx * head_rx * 1.05, head_cy + H * 0.16,
                  head_rx * 0.40, head_ry * 1.15, "hair", curve=1.3)

    # ── ①b 頸（⚠️ 冇頸嘅話個頭會「浮」喺身上面）──
    c.poly([(cx - W * 0.055, head_cy + head_ry * 0.72),
            (cx + W * 0.055, head_cy + head_ry * 0.72),
            (cx + W * 0.060, head_cy + head_ry * 1.10),
            (cx - W * 0.060, head_cy + head_ry * 1.10)],
           "skin", curve=1.3)

    # ── ② 身（衫）—— 梯形 ──
    body_top = head_cy + head_ry * 0.95
    body_bot = H * 0.905
    bw_top, bw_bot = W * 0.185, W * 0.335
    c.poly([
        (cx - bw_top, body_top), (cx + bw_top, body_top - H * 0.012),
        (cx + bw_bot, body_bot), (cx - bw_bot, body_bot),
    ], "cloth", curve=1.45)

    # ── ③ 手臂 ──
    sh_y = body_top + H * 0.06
    for sx in (-1, 1):
        if sx < 0 and arm in ("wave", "up"):
            # 舉起（左上）
            c.poly([(cx + sx * bw_top * 0.85, sh_y),
                    (cx + sx * bw_top * 0.55, sh_y + H * 0.03),
                    (cx + sx * W * 0.30, sh_y - H * 0.16),
                    (cx + sx * W * 0.34, sh_y - H * 0.13)],
                   "cloth", curve=1.4)
            c.ellipse(cx + sx * W * 0.325, sh_y - H * 0.155,
                      W * 0.045, H * 0.040, "skin", curve=1.3)
        elif sx > 0 and arm == "point":
            # 指向右
            c.poly([(cx + bw_top * 0.85, sh_y),
                    (cx + bw_top * 0.85, sh_y + H * 0.055),
                    (cx + W * 0.44, sh_y + H * 0.035),
                    (cx + W * 0.44, sh_y - H * 0.005)],
                   "cloth", curve=1.4)
            c.ellipse(cx + W * 0.455, sh_y + H * 0.017,
                      W * 0.045, H * 0.038, "skin", curve=1.3)
        elif sx > 0 and arm == "up":
            c.poly([(cx + sx * bw_top * 0.85, sh_y),
                    (cx + sx * bw_top * 0.55, sh_y + H * 0.03),
                    (cx + sx * W * 0.30, sh_y - H * 0.16),
                    (cx + sx * W * 0.34, sh_y - H * 0.13)],
                   "cloth", curve=1.4)
            c.ellipse(cx + sx * W * 0.325, sh_y - H * 0.155,
                      W * 0.045, H * 0.040, "skin", curve=1.3)
        else:
            # 自然垂落
            c.poly([(cx + sx * bw_top * 0.90, sh_y),
                    (cx + sx * bw_top * 1.20, sh_y + H * 0.20),
                    (cx + sx * bw_top * 0.95, sh_y + H * 0.21),
                    (cx + sx * bw_top * 0.62, sh_y + H * 0.03)],
                   "cloth", curve=1.4)
            c.ellipse(cx + sx * bw_top * 1.06, sh_y + H * 0.215,
                      W * 0.040, H * 0.035, "skin", curve=1.3)

    # ── ③b 背囊帶（旅行主題 —— 一眼睇出係「去旅行」）──
    for sx in (-1, 1):
        #   ⚠️ 第一版太闊（0.30→1.05）→ 睇落似背心。
        #      收窄到 0.55→0.80 先似「帶」。
        c.poly([(cx + sx * bw_top * 0.55, body_top + H * 0.008),
                (cx + sx * bw_top * 0.82, body_top + H * 0.014),
                (cx + sx * bw_top * 0.90, body_top + H * 0.27),
                (cx + sx * bw_top * 0.64, body_top + H * 0.26)],
               "cyan", curve=1.2)

    # ── ④ 腰帶（青色點綴）──
    c.poly([(cx - bw_top * 1.30, body_top + H * 0.30),
            (cx + bw_top * 1.30, body_top + H * 0.285),
            (cx + bw_top * 1.36, body_top + H * 0.355),
            (cx - bw_top * 1.36, body_top + H * 0.37)],
           "cyan", curve=1.2)

    # ── ⑤ 面 ──
    c.ellipse(cx, head_cy + H * 0.055, head_rx * 0.82, head_ry * 0.90,
              "skin", curve=1.5)

    # 前髮（瀏海）
    #   ⚠️⚠️ bug：第一版 bangs 喺 head_cy - 0.30*ry、高 0.62*ry
    #      → 覆蓋到 y≈16，但對眼喺 y≈15.6 → **瀏海蓋住對眼**！
    #      所以角色睇落「冇眼」，成個樣衰。
    #      修法：bangs 推高到 -0.66*ry、壓扁到 0.46*ry → 
    #      最低點 y≈12，眼睛（y≈15.6）露返出嚟。
    c.ellipse(cx, head_cy - head_ry * 0.66, head_rx * 0.98, head_ry * 0.46,
              "hair", curve=1.2)
    # 側髮（框住塊面，但唔可以蓋到眼）
    for sx in (-1, 1):
        c.ellipse(cx + sx * head_rx * 0.86, head_cy + H * 0.055,
                  head_rx * 0.20, head_ry * 0.78, "hair", curve=1.3)

    # ── ⑥ 五官 ──
    #   ⚠️⚠️ 眼睛一定要**大** —— 像素角色嘅可愛度 90% 嚟自眼。
    #      第一版 eye_rx=W*0.058（=2.1 格）太細，睇落似兩點污漬。
    #      而家 W*0.085（=3.1 格）＋ 加埋高光同眉毛。
    #   ⚠️ W*0.085 太大（試過）—— 對眼蓋咗塊面 2/3，睇落似外星人。
    #      W*0.068 先啱：大眼但仲有面頰同嘴嘅空間。
    eye_y = head_cy + H * 0.048
    eye_dx = head_rx * 0.44
    eye_rx, eye_ry = W * 0.068, H * 0.060
    #   ⚠️⚠️ bug：第一版係「白色橢圓 + 中間深色珠」——
    #      個白圈睇落**似眼鏡框**，唔似眼。
    #      正確做法（參考圖嘅眼）：
    #        ① 先畫**深色**眼形（做眼線／眼眶）
    #        ② 再畫**彩色虹膜**填滿大部分
    #        ③ 高光壓喺上面
    #      咁樣就冇白圈。
    for sx in (-1, 1):
        ex = cx + sx * eye_dx
        # ① 眼眶（深）
        c.ellipse(ex, eye_y, eye_rx, eye_ry, "iris", curve=1.0)
        # ② 虹膜（中紫）—— 填 74%，留一圈深色做眼線
        c.ellipse(ex, eye_y + eye_ry * 0.06,
                  eye_rx * 0.74, eye_ry * 0.76, "iris", curve=0.35)
        # ③ 瞳孔（最暗）
        c.ellipse(ex, eye_y + eye_ry * 0.10,
                  eye_rx * 0.40, eye_ry * 0.44, "iris", curve=0.15)
        # ④ 高光（左上，大）—— 冇高光嘅眼會變「死魚眼」
        c.ellipse(ex - eye_rx * 0.34, eye_y - eye_ry * 0.40,
                  eye_rx * 0.32, eye_ry * 0.30, "eye", curve=0.3)
        # ⑤ 小高光（右下）
        c.ellipse(ex + eye_rx * 0.30, eye_y + eye_ry * 0.40,
                  eye_rx * 0.17, eye_ry * 0.16, "eye", curve=0.3)

    # 嘴
    if mood == "happy":
        c.poly([(cx - W * 0.042, eye_y + H * 0.068),
                (cx, eye_y + H * 0.096),
                (cx + W * 0.042, eye_y + H * 0.068),
                (cx, eye_y + H * 0.078)], "iris", curve=0.5)
    elif mood == "oh":
        c.ellipse(cx, eye_y + H * 0.086, W * 0.030, H * 0.027, "iris", curve=0.5)
    else:
        c.poly([(cx - W * 0.036, eye_y + H * 0.076),
                (cx, eye_y + H * 0.096),
                (cx + W * 0.036, eye_y + H * 0.076),
                (cx, eye_y + H * 0.083)], "iris", curve=0.5)

    # 腮紅 —— ⚠️ 要細（第一版太大，變成兩塊粉紅藥水膠布）
    for sx in (-1, 1):
        c.ellipse(cx + sx * head_rx * 0.82, eye_y + H * 0.055,
                  W * 0.030, H * 0.018, "cloth", curve=0.6)

    rgb = c.to_rgb()

    # ── ⑦ 頭髮邊緣嘅紫／青挑染（signature）──
    hair_mask = c.mask_of("hair")
    rgb = hair_rim(rgb, hair_mask)

    # ── ⑧ 描邊 ──
    rgb = outline(rgb, c.mask_of(*RAMP.keys()))

    return rgb


def hair_rim(rgb: np.ndarray, hair: np.ndarray) -> np.ndarray:
    """
    頭髮嘅**外緣**染紫（左）／青（右）——
    呢個係參考圖最 signature 嘅細節（her-idle 嘅頭髮邊）。

    ⚠️ 只染頭髮**最外**一圈，唔染成個頭 ——
       否則會變成一頂紫青色帽。
    """
    out = rgb.astype(float)
    # 邊緣 = 頭髮 ∩ 唔係頭髮嘅鄰居
    edge = np.zeros_like(hair)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        edge |= hair & ~np.roll(np.roll(hair, dy, 0), dx, 1)
    edge &= hair

    h, w = hair.shape
    xs = np.linspace(-1, 1, w)[None, :]
    lw = np.clip(-xs / 0.5, 0, 1) * edge
    rw = np.clip(xs / 0.5, 0, 1) * edge
    for k in range(3):
        out[:, :, k] += (HAIR_PURPLE[k] - out[:, :, k]) * lw * 0.45
        out[:, :, k] += (HAIR_CYAN[k] - out[:, :, k]) * rw * 0.45
    return np.clip(out, 0, 255).astype(np.uint8)


def outline(rgb: np.ndarray, solid: np.ndarray) -> np.ndarray:
    """
    加描邊（像素藝術一定有黑邊）。

    ⚠️ 描邊要畫喺角色**外面**（向外擴一格），
       唔係喺裏面 —— 畫喺裏面會令角色縮水一圈。
    """
    h, w = solid.shape
    grown = solid.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        grown |= np.roll(np.roll(solid, dy, 0), dx, 1)
    ring = grown & ~solid
    out = rgb.copy()
    out[ring] = OUTLINE
    return out


# ══════════════════════════════════════════════════════════════════
# 生成
# ══════════════════════════════════════════════════════════════════

FRAMES = {
    # (檔名, mood, arm)
    "mascot-hello": ("smile", "wave"),
    "mascot-point": ("smile", "point"),
    "mascot-happy": ("happy", "up"),
    "mascot-oh":    ("oh",    "hold"),
}


def build(scale: int = 4) -> list[tuple[str, Image.Image]]:
    out = []
    for name, (mood, arm) in FRAMES.items():
        rgb = make_character(mood=mood, arm=arm)
        rgb = chromatic_edge(rgb, 0.24, spread=1)
        img = Image.fromarray(rgb, "RGB")
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        out.append((f"{name}.png", img))

    # 頭像版本（只有頭）—— 設定頁揀名嗰陣用
    rgb = make_character(mood="smile", arm="hold")
    head = rgb[0:int(H * 0.56), int(W * 0.13):int(W * 0.87)]
    head = chromatic_edge(head, 0.24, spread=1)
    img = Image.fromarray(head, "RGB")
    out.append(("mascot-face.png",
                img.resize((img.width * 6, img.height * 6), Image.NEAREST)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--scale", type=int, default=4)
    args = ap.parse_args()

    items = build(args.scale)
    if args.preview:
        # 砌一張並排圖
        pad = 16
        Wt = sum(i.width for _, i in items) + pad * (len(items) + 1)
        Ht = max(i.height for _, i in items) + pad * 2
        canvas = Image.new("RGB", (Wt, Ht), (10, 5, 24))
        x = pad
        for _, im in items:
            canvas.paste(im, (x, pad))
            x += im.width + pad
        canvas.save("/tmp/mascot_new.png")
        print("✓ /tmp/mascot_new.png")
        for n, i in items:
            print(f"  · {n:18} {i.size[0]}×{i.size[1]}")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for name, img in items:
        img.save(OUT / name, optimize=True)
        print(f"  · {name:22} {img.size[0]}×{img.size[1]}")
    print(f"\n✓ 寫入 {len(items)} 個檔案 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
