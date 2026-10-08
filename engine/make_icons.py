"""
將 icon.svg 嘅設計畫成 PNG（iOS 完全唔支援 SVG icon）。
⚠️ iOS 加主畫面一定要 apple-touch-icon（180×180 PNG），
   冇嘅話 iOS 會用網頁截圖做 icon —— 好難睇。
"""
from PIL import Image, ImageDraw
import math, pathlib

OUT = pathlib.Path("web/public")
BG = (11, 5, 24, 255)          # #0b0518
PURPLE = (168, 85, 247)
CYAN = (34, 211, 238)

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def star(draw, cx, cy, outer, inner, points, fill):
    """
    畫 N 角星。

    ⚠️ 角度間距係 2π / (points*2)，即每個頂點隔 360/(2N) 度。
       原本寫 `(π/2)*i` → 隔 90 度，8 個頂點就繞咗 720 度，
       自己疊返自己 → 變成一個直菱形（唔係星）❌
    """
    verts = []
    step = math.pi / points          # = 2π / (points*2)
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        ang = step * i - math.pi / 2  # 由正上方開始
        verts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(verts, fill=fill)

def make(size: int, *, maskable=False, name="icon"):
    SS = 4                                   # 超取樣（抗鋸齒）
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 背景圓角方塊
    #   maskable 要留 10% 安全邊（Android 會裁圓／squircle）
    pad = int(S * 0.10) if maskable else 0
    r = int((S - pad * 2) * (0.218 if not maskable else 0.5))
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=r, fill=BG)

    # 外框（漸變色感 → 用純色近似）
    bw = max(2, int(S * 0.016))
    d.rounded_rectangle([pad + bw, pad + bw, S - pad - bw, S - pad - bw],
                        radius=max(2, r - bw), outline=PURPLE + (140,), width=bw)

    # 中央四角星
    cx = cy = S / 2
    star(d, cx, cy, S * 0.33, S * 0.062, 4, PURPLE + (255,))
    star(d, cx, cy, S * 0.255, S * 0.046, 4, lerp(PURPLE, CYAN, 0.6) + (255,))
    # 中心圓
    cr = S * 0.051
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=BG)
    cr2 = S * 0.023
    d.ellipse([cx - cr2, cy - cr2, cx + cr2, cy + cr2], fill=(239, 234, 255, 255))

    img = img.resize((size, size), Image.LANCZOS)
    path = OUT / f"{name}-{size}.png"
    img.save(path, "PNG", optimize=True)
    return path, path.stat().st_size

print("產生 PNG icons:")
for sz in (180, 192, 512):          # 180=iOS, 192=Android, 512=PWA
    p, b = make(sz, name="icon")
    print(f"  ✓ {p.name:18} {sz}×{sz}  {b/1024:.1f} KB")
for sz in (192, 512):
    p, b = make(sz, maskable=True, name="icon-maskable")
    print(f"  ✓ {p.name:18} {sz}×{sz}  {b/1024:.1f} KB（maskable）")
