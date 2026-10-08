#!/usr/bin/env python3
"""
生成前端用嘅「城市 → 時區」數據檔
====================================

⚠️⚠️ 用戶要求：
   「一係你就整一個 File for 放低市區城市時間呢一啲嘅 data，
    佢感應到原來係另一個時區，就將你而家嘅時間做加減。」

⚠️ 為咩要（而唔係每次問後端）：
   ① **唔使網絡** —— 飛機上、地鐵、外國漫遊都用得
   ② **即時** —— 打「福岡」即刻出時區，唔使等 round-trip
   ③ ⚠️ 用戶揀咗嘅城市**記住**（localStorage），之後完全離線都用得

⚠️ 為咩唔放晒 134,655 個城市：
   個 JSON 會 ~8MB → 手機下載唔合理。
   ✅ 只放**人口最多嘅 N 個** + 所有中文名嘅城市
      （用戶打中文嘅機會高，而且中文名通常係大城市）。

⚠️ 時區由座標 + 國家代碼計（`wander/tz.py`）——
   同 `/api/tz` 用**同一個**邏輯，所以兩邊一定一致。

用法：
    python engine/make_city_tz.py
    → web/public/city-tz.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from wander import localgeo                      # noqa: E402
from wander.tz import lookup as tz_lookup        # noqa: E402

OUT = ROOT / "web" / "public" / "city-tz.json"

# ⚠️ 上限 —— 平衡「夠用」同「下載大細」。
#    2000 個城市 ≈ 120KB（gzip 後 ~35KB）—— 可以接受。
TOP_N = 2000


def main() -> int:
    cities = localgeo._cities()
    print(f"  全部城市: {len(cities):,}")

    # ⚠️ 同一個城市有好多別名（拼音、英文、中文…）指向同一條記錄。
    #    先用座標去重，攞最高人口嗰個名做 canonical。
    by_coord: dict[tuple, dict] = {}
    for key, v in cities.items():
        try:
            lat, lng, cc, pop, name = v
        except (TypeError, ValueError):
            continue
        k = (round(float(lat), 4), round(float(lng), 4))
        pop = int(pop or 0)
        if k not in by_coord or pop > by_coord[k]["pop"]:
            by_coord[k] = {"lat": float(lat), "lng": float(lng), "cc": cc,
                           "pop": pop, "name": name, "aliases": [key]}
        else:
            by_coord[k]["aliases"].append(key)

    uniq = sorted(by_coord.values(), key=lambda x: -x["pop"])
    print(f"  去重之後: {len(uniq):,}")

    # ⚠️ 一定要包晒「有中文名」嘅城市 ——
    #    用戶打中文嘅機會高，而且中文名通常唔喺人口 top N。
    def has_cjk(s: str) -> bool:
        return any('\u4e00' <= ch <= '\u9fff' for ch in (s or ''))

    picked = uniq[:TOP_N]
    picked_keys = {(round(c["lat"], 4), round(c["lng"], 4)) for c in picked}
    extra = 0
    for c in uniq:
        k = (round(c["lat"], 4), round(c["lng"], 4))
        if k in picked_keys:
            continue
        if any(has_cjk(a) for a in c["aliases"]) or has_cjk(c["name"]):
            picked.append(c)
            picked_keys.add(k)
            extra += 1
    print(f"  加埋中文名城市: +{extra:,}  → 總共 {len(picked):,}")

    # ⚠️ 輸出格式要好細：
    #    { "alias 細寫": [tzIndex, 中文國名] }
    #    時區用 index（唔好每個城市重複寫 "Asia/Tokyo"）
    tz_list: list[str] = []
    tz_idx: dict[str, int] = {}
    out: dict[str, list] = {}

    for c in picked:
        tz = tz_lookup(c["lat"], c["lng"], c["cc"])
        name = tz.get("tz")
        if not name:
            continue
        if name not in tz_idx:
            tz_idx[name] = len(tz_list)
            tz_list.append(name)
        cc = c["cc"] or ""
        zh = localgeo.COUNTRY_ZH.get(cc, cc)

        # ⚠️⚠️ **唔可以**每個別名都入 ——
        #    實測 6,798 個城市 × ~15 個別名 = 105,980 個名 = **2.7 MB**，
        #    手機下載唔合理。
        #
        # ✅ 每個城市留：
        #    ① canonical（GeoNames 嘅正名）
        #    ② **最短**嘅純 ASCII 別名（通常係英文／拼音 ——
        #       用戶打英文鍵盤最可能打呢個）
        #    ③ **全部**中文別名
        #
        # ⚠️⚠️ 為咩「最短 ASCII」而唔係第一個：
        #    別名表次序唔可靠。實測 `fukuoka` / `fukuokashi` 兩個都有，
        #    最短嘅先係用戶會打嘅。
        #
        # ⚠️⚠️ 為咩中文要**全部**（唔係最長嗰個）：
        #    實測 `福岡` 同 `福岡市` 都係別名 ——
        #    我第一版用 `max(..., key=len)` 揀咗 `福岡市`，
        #    但用戶打嘅係**`福岡`** → 24 個測試城市只中 11 個！
        #    ✅ 中文別名每個城市只有 1–3 個，全放都唔會大。
        names = {str(c["name"] or "").strip().lower()}
        al = [str(a or "").strip().lower() for a in c["aliases"]]
        ascii_al = [a for a in al if a and a.isascii()]
        if ascii_al:
            names.add(min(ascii_al, key=len))
        # ⚠️ 全部中文（唔係最長嗰個）
        names.update(a for a in al if a and not a.isascii())

        for key in names:
            # ⚠️ 太長嘅名用戶**唔會打**（實測最長 39 字！）——
            #    刪走 >=14 字嘅可以省 ~15% 大細。
            #    （中文地名通常 2–5 字，英文 3–12 字。）
            if not key or len(key) > 14 or key in out:
                continue
            out[key] = [tz_idx[name], zh]

    payload = {
        # ⚠️ 版本 —— 前端可以檢查有冇新資料
        "v": 1,
        "tz": tz_list,
        "cities": out,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(raw, encoding="utf-8")
    mb = len(raw.encode("utf-8")) / 1024
    print(f"  ✓ {OUT.relative_to(ROOT)}  {len(out):,} 個名  {len(tz_list)} 個時區  {mb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
