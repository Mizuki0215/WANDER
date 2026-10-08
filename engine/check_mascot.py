#!/usr/bin/env python3
"""
吉祥物圖檢查器
================

⚠️ 用戶揀咗「A 方案」：佢自己（或者用 AI）生成 4 張角色圖，我接入。

⚠️⚠️ 為咩要有呢個檢查器：
   AI 生成嘅圖好易有呢幾個問題，而且**肉眼睇唔出**（縮到 90px 更加睇唔出）：
     · 出咗白底／格仔底（「透明背景」唔一定真係透明）
     · 大細唔夠（縮小之後糊）
     · 主角佔畫面太少（縮到 90px 變成一粒塵）
     · 有文字／浮水印
   呢啲問題等到放上 app 先發現，就要重新生成 —— 好浪費時間。
   所以放檔案之前先跑呢個檢查。

用法：
    python check_mascot.py            # 檢查
    python check_mascot.py --fix      # 順便自動去背（純色背景）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
PUB = ROOT.parent / "web" / "public"

FRAMES = [
    ("mascot-hello", "打招呼（舉手）"),
    ("mascot-point", "指住（教學用）"),
    ("mascot-happy", "開心（完成）"),
    ("mascot-oh", "驚訝"),
]

MIN_W, MIN_H = 300, 400


def analyse(path: Path) -> dict:
    """分析一張吉祥物圖，回傳一堆指標。"""
    im = Image.open(path)
    fmt = im.format
    has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
    im = im.convert("RGBA")
    a = np.array(im)
    alpha = a[:, :, 3]

    h, w = alpha.shape
    opaque = alpha > 32
    opaque_ratio = float(opaque.mean())

    # 主體嘅 bounding box（唔計透明邊）
    if opaque.any():
        ys, xs = np.nonzero(opaque)
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        bw = bbox[2] - bbox[0] + 1
        bh = bbox[3] - bbox[1] + 1
        fill_ratio = (bw * bh) / (w * h)
        # 主體離底邊幾遠（應該好近 = 貼底）
        bottom_gap = (h - 1 - bbox[3]) / h
    else:
        bbox, bw, bh, fill_ratio, bottom_gap = None, 0, 0, 0.0, 1.0

    # 角落顏色（如果四隻角都係同一個唔透明嘅色 → 應該係去背失敗）
    corners = [a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]
    corner_opaque = sum(1 for c in corners if c[3] > 200)
    corner_same = (corner_opaque >= 3 and
                   len({tuple(c[:3]) for c in corners if c[3] > 200}) == 1)

    # 主體顏色數（粗略：量化之後數唔同色）
    if opaque.any():
        px = a[opaque][:, :3]
        q = (px // 32 * 32)
        uniq = len({tuple(x) for x in q[::max(1, len(q) // 4000)]})
    else:
        uniq = 0

    return {
        "size": (w, h), "format": fmt, "alpha": has_alpha,
        "opaque_ratio": opaque_ratio, "bbox": bbox,
        "bw": bw, "bh": bh, "fill_ratio": fill_ratio,
        "bottom_gap": bottom_gap, "corner_opaque": corner_opaque,
        "corner_same": corner_same, "colors": uniq,
    }


def check_one(name: str, label: str) -> tuple[bool, list[str]]:
    p = PUB / f"{name}.png"
    msgs: list[str] = []
    if not p.exists():
        return False, [f"（未放）web/public/{name}.png"]

    d = analyse(p)
    ok = True

    # ⚠️⚠️ 自動分辨「原圖」同「已處理圖」：
    #    如果主體 bounding box 已經等於成張圖（冇透明邊），
    #    就係已經裁到貼邊嘅處理圖 —— 唔應該再要求「留邊」。
    #   （否則跑完 cutout 再 check 會全部假失敗。）
    tight = (d["bbox"] is not None and
             d["bbox"][0] == 0 and d["bbox"][1] == 0 and
             d["bbox"][2] == d["size"][0] - 1 and
             d["bbox"][3] == d["size"][1] - 1)

    if d["format"] != "PNG":
        msgs.append(f"⚠️ 格式係 {d['format']}，要 PNG")
        ok = False
    if not d["alpha"]:
        msgs.append("⚠️ 冇透明通道（RGBA）—— 背景會係一嚿色")
        ok = False

    # ⚠️ 大細：處理圖可以用細啲（CSS 會縮放）
    min_w, min_h = (120, 240) if tight else (MIN_W, MIN_H)
    if d["size"][0] < min_w or d["size"][1] < min_h:
        msgs.append(f"⚠️ 大細 {d['size'][0]}×{d['size'][1]}，"
                    f"建議最少 {min_w}×{min_h}")
        ok = False

    if d["corner_opaque"] >= 3 and d["corner_same"]:
        msgs.append("⚠️ 四隻角都係同一個實色 —— 去背失敗（有背景）")
        ok = False

    if not tight:
        # 只有「原圖」先檢查留邊
        if d["fill_ratio"] < 0.08:
            msgs.append(f"⚠️ 主角只佔畫面 {d['fill_ratio']*100:.1f}% —— "
                        f"縮到 90px 會變一粒塵")
            ok = False
        if d["fill_ratio"] > 0.95:
            msgs.append(f"⚠️ 主角佔咗 {d['fill_ratio']*100:.0f}% —— "
                        f"可能冇留邊，縮細會貼邊")
            ok = False
        if d["bottom_gap"] > 0.25:
            msgs.append(f"⚠️ 主角離底邊 {d['bottom_gap']*100:.0f}% —— "
                        f"建議 <10%（否則縮細之後會浮）")
            ok = False

    if d["colors"] < 4:
        msgs.append(f"⚠️ 只有 {d['colors']} 隻色 —— 可能係純色塊")

    if ok:
        tag = "已處理" if tight else "原圖"
        msgs.append(f"✓ {d['size'][0]}×{d['size'][1]} · {tag} · "
                    f"{d['colors']} 色")
    return ok, msgs


def auto_fix(name: str) -> bool:
    """
    自動去背（只適用於**純色背景**）。

    ⚠️ 唔係萬能 —— 如果背景有漸變／圖案，去唔到。
       嗰啲要用 remove.bg 之類。
    """
    from collections import Counter
    p = PUB / f"{name}.png"
    if not p.exists():
        return False
    im = Image.open(p).convert("RGBA")
    a = np.array(im)
    h, w = a.shape[:2]
    # 由四條邊抽背景色
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    common = Counter(map(tuple, edge[:, :3])).most_common(1)
    if not common:
        return False
    bg = np.array(common[0][0], dtype=int)
    dist = np.abs(a[:, :, :3].astype(int) - bg).sum(axis=2)
    mask = dist < 40                      # 容忍少少壓縮誤差
    a[mask, 3] = 0
    a[~mask, 3] = 255
    Image.fromarray(a).save(p)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="自動去背（純色背景）")
    args = ap.parse_args()

    print("吉祥物圖檢查")
    print("=" * 60)

    if args.fix:
        print("先自動去背…")
        for name, _ in FRAMES:
            if auto_fix(name):
                print(f"  ↻ 去咗 {name}.png 嘅背景")

    present, ok_count = 0, 0
    for name, label in FRAMES:
        p = PUB / f"{name}.png"
        if p.exists():
            present += 1
        ok, msgs = check_one(name, label)
        if ok:
            ok_count += 1
        mark = "✓" if ok else ("·" if not p.exists() else "✗")
        print(f"\n  {mark} {name}.png  —— {label}")
        for m in msgs:
            print(f"      {m}")

    print()
    print("=" * 60)
    if present == 0:
        print("  ⚠️ 一個都未放 —— App 會用**程序化畫嗰個**做 fallback")
        print()
        print("  要放就放呢 4 個檔入 web/public/：")
        for name, _ in FRAMES:
            print(f"    {name}.png")
        print()
        print("  提示詞同規格：docs/mascot/README.md")
        return 0

    if ok_count == len(FRAMES):
        print(f"  ✅ {ok_count}/{len(FRAMES)} 全部合格 —— App 會自動用你嗰啲")
        return 0

    print(f"  {ok_count}/{len(FRAMES)} 合格，{present} 個已放")
    if present < len(FRAMES):
        print("  ⚠️ 未放齊 —— 未放嗰啲會用程序化 fallback")
    return 1


if __name__ == "__main__":
    sys.exit(main())
