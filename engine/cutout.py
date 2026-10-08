#!/usr/bin/env python3
"""
去背工具（Cutout）
====================

⚠️⚠️ 用戶要求：
   「我係覺得呢一啲（角色圖）直接用佢都得嘅，咁可能你
    唔好成張擺上去，即係你可以 cop 咗佢個背景上去。」
   → 即係「幫我去背」。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️⚠️⚠️ 為咩要自己寫（唔係用現成 AI 去背）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   實測用戶畀嘅 6 張圖：

     her-idle   ✅ 完整
     her-give   ✅ 完整
     her-hold   ⚠️ 白頭髮被褪走
     him-idle   ❌ 成套白西裝被褪走
     him-take   ⚠️ 白恤衫被褪走
     him-soft   ⚠️ 白西裝被褪走

   ⚠️ 原因：AI 去背當「**白色 = 背景**」，但角色本身
      **白頭髮 + 白西裝** —— 一樣係白色！

   ⚠️ 而壞咗嘅圖**救唔返**：
      透明區嘅 RGB 係 `(0,0,0)`，即係原本嘅顏色**冇保存**。
      （有啲工具會保留 RGB、只改 alpha，咁就救得返。）

   ✅ 正確做法：生成角色圖嗰陣要**非白色背景**（鮮綠／洋紅），
      咁「背景」同「白西裝」就唔會撞 → 去背 100% 準。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
用法
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 自動偵測背景色（由四邊）
    python cutout.py in.png -o out.png

    # 指定背景色
    python cutout.py in.png -o out.png --bg "#00ff00"

    # 一次過處理成個資料夾
    python cutout.py raw/ -o web/public/ --prefix mascot-

    # 檢查現有圖有冇「白色被褪走」
    python cutout.py --check web/public/*.png
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

# ⚠️ 容差：背景色同像素色差幾多當「一樣」。
#    太低 → 邊緣留低背景碎點；太高 → 食咗角色。
#    實測 60（0-765 範圍，即 RGB 加埋）最好。
DEFAULT_TOL = 60


def detect_bg(a: np.ndarray) -> tuple[int, int, int]:
    """
    由**四條邊**估背景色（唔係由全圖 —— 角色可能佔大多數）。

    ⚠️ 用四邊而唔用四角：角可能被角色擋住（例如長髮垂到角落）。
    """
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    edge = edge[edge[:, 3] > 200]          # 只睇不透明嘅邊
    if len(edge) == 0:
        return (0, 0, 0)
    # ⚠️ 用「最常見」而唔係「平均」——
    #    平均會被角色邊緣嘅顏色拉歪。
    common = Counter(map(tuple, edge[:, :3])).most_common(1)
    return tuple(int(v) for v in common[0][0])


def cutout(im: Image.Image, bg=None, tol: int = DEFAULT_TOL,
           feather: int = 1, keep_alpha: bool = True) -> tuple[Image.Image, dict]:
    """
    去背。

    ⚠️⚠️ 關鍵：用 **flood fill 由四邊**，唔係「所有近背景色嘅像素」。
       為咩：
         · 無腦褪色會食咗角色內部同背景同色嘅部分
           （白西裝 vs 白背景 → 就係用戶嗰 6 張圖嘅問題）
         · flood fill 只褪**連得到邊界**嘅區域 →
           角色內部嘅白色**保得住**

    ⚠️ 但如果角色嘅白色**連住**背景（例如白西裝領口冇封口），
       flood fill 都會漏入去。→ 所以最穩陣係用**非白背景**生成。
    """
    a = np.array(im.convert("RGBA"))
    if bg is None:
        bg = detect_bg(a)
    bg = np.array(bg, dtype=int)

    dist = np.abs(a[:, :, :3].astype(int) - bg).sum(axis=2)
    near_bg = dist < tol
    # 已經透明嘅都當背景
    near_bg |= a[:, :, 3] < 30

    # ⚠️⚠️ 兩條路，睇背景色離「白」幾遠：
    #
    #   ① 背景**唔似白**（例如鮮綠 #00ff00）
    #      → 角色身上冇可能有呢隻色 → 可以**全域**褪走。
    #        連角色**內部**嘅背景碎點都褪得到。
    #
    #   ② 背景**似白**（例如 #ffffff）
    #      → 角色可能有白頭髮／白西裝 → **只可以**由邊界 flood fill。
    #        代價：內部嘅白色碎點褪唔到（但總好過食咗白西裝）。
    #
    #   ⚠️ 就係因為 AI 用咗「②」而角色係白西裝 →
    #      用戶嗰 4 張圖被褪穿。所以最穩陣係用**非白背景**生成。
    bg_is_whitish = all(int(c) > 200 for c in bg)

    if bg_is_whitish:
        # ② 只褪連得到邊界嘅
        lab, _n = ndimage.label(near_bg)
        border = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) | \
                 set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
        border.discard(0)
        outside = np.isin(lab, list(border))
    else:
        # ① 全域褪
        outside = near_bg

    out = a.copy()
    out[outside, 3] = 0

    # ⚠️ 邊緣羽化：唔做嘅話縮細之後會有鋸齒。
    #    只縮 alpha，唔改 RGB。
    if feather > 0:
        solid = (~outside).astype(np.uint8)
        # 距離邊界嘅距離 → 用嚟做 1px 過渡
        d = ndimage.distance_transform_edt(solid)
        ramp = np.clip(d / (feather + 1e-6), 0, 1)
        out[:, :, 3] = (out[:, :, 3] * ramp).astype(np.uint8)

    if not keep_alpha:
        out[out[:, :, 3] < 128] = 0

    stats = {
        "bg": tuple(int(v) for v in bg),
        "removed": float(out[:, :, 3].mean() < 30),
        "kept": float((out[:, :, 3] > 200).mean()),
    }
    return Image.fromarray(out), stats


def check_holes(im: Image.Image, bg=(255, 255, 255),
                tol: int = DEFAULT_TOL) -> dict:
    """
    檢查「有冇白色部分被褪走」。

    ⚠️ 判斷方法：如果原本係白底，角色嘅白色區域會同背景一樣色 →
       去背之後佢會變透明，而且**連住**背景（唔算「洞」）→
       用「洞」檢查捉唔到。

    ✅ 所以改用另一個角度：**透明區域有幾多係「被角色包圍」**，
       再加「角色實心度」（實心度太低 = 中間穿咗）。
    """
    a = np.array(im.convert("RGBA"))
    alpha = a[:, :, 3]
    solid = alpha > 128
    if not solid.any():
        return {"empty": True}

    ys, xs = np.nonzero(solid)
    inner = solid[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # ⚠️ 剪影嘅「實心度」：正常角色 40-60%，穿咗會跌到 15-25%
    fill = float(inner.mean())

    # 洞（被包圍嘅透明）
    trans = ~inner
    lab, _ = ndimage.label(trans)
    border = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) | \
             set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    border.discard(0)
    holes = trans & ~np.isin(lab, list(border))
    hole_ratio = float(holes.sum() / max(1, inner.sum()))

    return {"fill": fill, "holes": hole_ratio,
            "suspicious": fill < 0.30 or hole_ratio > 0.08}


def main() -> int:
    ap = argparse.ArgumentParser(description="去背工具")
    ap.add_argument("src", nargs="+", help="輸入圖（或者資料夾）")
    ap.add_argument("-o", "--out", help="輸出（檔案或者資料夾）")
    ap.add_argument("--bg", help="背景色（#rrggbb）；預設自動偵測")
    ap.add_argument("--tol", type=int, default=DEFAULT_TOL, help="容差")
    ap.add_argument("--no-feather", action="store_true", help="唔做邊緣羽化")
    ap.add_argument("--check", action="store_true", help="只檢查，唔改")
    ap.add_argument("--max-size", type=int, default=520,
                    help="最長邊縮到幾多（0 = 唔縮）")
    ap.add_argument("--prefix", default="", help="輸出檔名前綴")
    a = ap.parse_args()

    bg = None
    if a.bg:
        h = a.bg.lstrip("#")
        bg = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    srcs: list[Path] = []
    for s in a.src:
        p = Path(s)
        if p.is_dir():
            srcs += sorted(x for x in p.iterdir()
                           if x.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"))
        else:
            srcs.append(p)
    if not srcs:
        print("  ✗ 搵唔到輸入圖")
        return 1

    outdir = Path(a.out) if a.out else None
    if outdir and len(srcs) > 1:
        outdir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  去背" + ("（只檢查）" if a.check else ""))
    print("=" * 70)

    bad = 0
    for p in srcs:
        im = Image.open(p)
        chk = check_holes(im)
        flag = ""
        if chk.get("suspicious"):
            bad += 1
            flag = (f"  ⚠️ 可能穿咗（實心度 {chk['fill']*100:.0f}%，"
                    f"洞 {chk['holes']*100:.1f}%）")

        if a.check:
            print(f"  {p.name:22} {im.size[0]:>4}x{im.size[1]:<4}{flag}")
            continue

        out, st = cutout(im, bg=bg, tol=a.tol,
                         feather=0 if a.no_feather else 1)
        # 縮到大細
        if a.max_size:
            bb = out.getbbox()
            if bb:
                out = out.crop(bb)
            if max(out.size) > a.max_size:
                r = a.max_size / max(out.size)
                out = out.resize((max(1, int(out.width * r)),
                                  max(1, int(out.height * r))), Image.LANCZOS)

        if outdir and len(srcs) > 1:
            dst = outdir / f"{a.prefix}{p.stem}.png"
        elif a.out:
            dst = Path(a.out)
        else:
            dst = p.with_name(f"{a.prefix}{p.stem}-cut.png")
        out.save(dst)
        print(f"  {p.name:22} → {dst.name:26} "
              f"背景 {st['bg']}  保留 {st['kept']*100:.0f}%{flag}")

    if a.check and bad:
        print()
        print(f"  ⚠️ {bad} 張可能穿咗 —— 建議用**非白色背景**重新生成")
        print("     提示詞加：solid bright green background (#00ff00)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
