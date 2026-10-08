"""
wander.cli — 命令列介面

用法：
    python -m wander parse "https://www.google.com/maps/place/..."   # 解析 link（會上網抓）
    python -m wander parse --no-fetch "https://..."                  # 只靠 URL 結構，唔上網
    python -m wander text "地址：〒823-0003 …"                        # 只解析文字
    python -m wander text --file caption.txt                         # 由檔案讀取
    python -m wander selftest                                        # 跑內建測試
    python -m wander lookup "一蘭 本社総本店" --hint 博多             # 由店名反查完整資料
    python -m wander enrich "地址：〒823-0003 福岡縣宮若市本城65-1 …"   # caption 解析 + 搜尋補完
    python -m wander demo                                            # 睇範例輸出
    python -m wander batch urls.txt                                  # 批量處理

加 --json 出 JSON（方便餵落 app）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .caption import CaptionParser
from .links import classify, parse_gmaps, parse_url_offline, is_short_link
from .models import Item

# ── 顏色 ────────────────────────────────────────────────────
_NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()


class C:
    R = "" if _NO_COLOR else "\033[0m"
    B = "" if _NO_COLOR else "\033[1m"
    DIM = "" if _NO_COLOR else "\033[2m"
    P = "" if _NO_COLOR else "\033[38;5;141m"    # 紫
    CY = "" if _NO_COLOR else "\033[38;5;80m"    # 青
    G = "" if _NO_COLOR else "\033[38;5;78m"     # 綠
    Y = "" if _NO_COLOR else "\033[38;5;221m"    # 黃
    RD = "" if _NO_COLOR else "\033[38;5;203m"   # 紅
    M = "" if _NO_COLOR else "\033[38;5;218m"    # 粉


def conf_color(v: int) -> str:
    return C.G if v >= 85 else C.Y if v >= 65 else C.RD


def bar(v: int, width: int = 20) -> str:
    filled = round(v / 100 * width)
    return "█" * filled + "░" * (width - filled)


# ══════════════════════════════════════════════════════════════
# 輸出
# ══════════════════════════════════════════════════════════════

def print_item(item: Item, *, show_rules: bool = True, show_score: bool = True) -> None:
    w = 66
    print()
    print(f"{C.P}{'═' * w}{C.R}")
    label = item.name or f"{C.RD}（抽唔到名稱）{C.R}"
    print(f"  {C.B}{label}{C.R}")
    print(f"  {C.DIM}{item.source_name or item.source}{C.R}"
          f"  {conf_color(item.confidence)}信心 {item.confidence}%{C.R}"
          f"  {bar(item.confidence)}")
    print(f"{C.P}{'─' * w}{C.R}")

    def row(icon: str, label: str, value, conf=None) -> None:
        if not value:
            value = f"{C.DIM}—{C.R}"
        else:
            value = str(value)
        cf = ""
        if conf is not None:
            cf = f"  {conf_color(conf)}{conf:>3}%{C.R}"
        print(f"  {icon} {C.DIM}{label:<8}{C.R} {value}{cf}")

    fc = item.field_confidence or {}
    row("🏷 ", "名稱", item.name)
    row("📍", "位置", item.location_display or None, fc.get("location"))
    if item.brand_from:
        print(f"  {C.Y}⚠️  品牌來自「{item.brand_from}」，實際位置唔喺嗰度{C.R}")
    row("🏠", "地址", item.address, fc.get("address"))
    if item.postal_code or item.address_tail:
        extra = " · ".join(filter(None, [
            f"〒{item.postal_code}" if item.postal_code else None,
            f"番地 {item.address_tail}" if item.address_tail else None,
        ]))
        row("　 ", "", f"{C.DIM}{extra}{C.R}")
    if item.has_coords:
        row("🗺 ", "座標", f"{item.lat}, {item.lng}", fc.get("location"))
        if item.google_maps_url:
            row("　 ", "", f"{C.CY}{item.google_maps_url}{C.R}")
    row("🗂 ", "分類", item.category_display or None, fc.get("category"))
    if item.category_why:
        row("　 ", "", f"{C.DIM}命中關鍵字「{item.category_why}」{C.R}")
    if item.dates:
        row("📅", "日期", "　|　".join(d.display for d in item.dates), fc.get("dates"))
    row("🕐", "時間", item.hours, fc.get("hours"))
    row("💰", "價錢", item.price, fc.get("price"))
    row("☎️ ", "電話", item.phone, fc.get("phone"))
    if item.tags:
        row("#️⃣ ", f"標籤", " ".join(f"#{t}" for t in item.tags[:8]))
    if item.raw_image:
        row("🖼 ", "封面圖", f"{C.DIM}{str(item.raw_image)[:70]}{C.R}")
    for n in item.notes:
        print(f"  {C.Y}ℹ️  {n}{C.R}")

    if show_score and fc:
        print(f"{C.P}{'─' * w}{C.R}")
        print(f"  {C.DIM}信心分數拆解（邊個欄位拉低分）{C.R}")
        WEIGHTS = [("name", "名稱", .32), ("location", "位置", .26), ("address", "地址", .16),
                   ("category", "分類", .14), ("dates", "日期", .06),
                   ("hours", "時間", .03), ("price", "價錢", .03)]
        for key, lb, wt in WEIGHTS:
            v = fc.get(key, 0)
            contrib = v * wt
            dim = C.DIM if v == 0 else ""
            print(f"    {dim}{lb:<4}{C.R} {conf_color(v) if v else C.DIM}"
                  f"{bar(v, 14)}{C.R} {dim}{v:>3} × {wt} = {contrib:>5.1f}{C.R}")
        total = sum(fc.get(k, 0) * wt for k, _, wt in WEIGHTS)
        print(f"    {C.B}加權總分{C.R} {conf_color(item.confidence)}"
              f"{total:.1f} → {item.confidence}%{C.R}")

    if show_rules and item.rules_matched:
        print(f"{C.P}{'─' * w}{C.R}")
        print(f"  {C.DIM}命中 {len(item.rules_matched)} 條規則{C.R}")
        for r in item.rules_matched:
            m = str(r.get("match", ""))[:52]
            print(f"    {C.CY}{r.get('rule',''):<16}{C.R}{C.DIM}{r.get('note','')}{C.R}")
            if m:
                print(f"      {C.DIM}↳ {m}{C.R}")

    if item.needs_review:
        print(f"{C.P}{'─' * w}{C.R}")
        print(f"  {C.Y}⚠️  needs_review = true{C.R} "
              f"{C.DIM}→ App 應該彈出手動補充，而唔係扮成功{C.R}")
    print(f"{C.P}{'═' * w}{C.R}\n")


# ══════════════════════════════════════════════════════════════
# 內建測試
# ══════════════════════════════════════════════════════════════

SELFTEST_CASES = [
    {
        "name": "彼岸花季（福岡宮若市）· 真實 IG caption",
        "text": """曲「蔓珠沙華」大家都已熟能詳，
大家可知道「蔓珠沙華」在日本又名為「彼岸花」。
迎接「宮若市」市成立20年，「犬鳴川綠之協會」30周年，
每年除了提供夜間點燈觀賞外，
在10月初更續辦去年大受好評的「放天燈（ランタンリリース），
🔸地址：〒823-0003　福岡縣宮若市本城65-1　犬鳴川河川公園
🔸日期：一般觀賞 9月中至10月初
晚間點燈 9月24日至10月8日
「彼岸花祭2026」10月4日
🔸營業時間：「彼岸花祭2026」下午3時至晚上8時""",
        "expect": {
            "name": "犬鳴川河川公園", "city": "宮若市", "country": "日本",
            "postal_code": "823-0003", "category": "play",
        },
    },
    {
        "name": "長岡博多天婦羅（銅鑼灣）· 真實 IG caption",
        "text": """【開幕快將滿一年！座落銅鑼灣正宗〖#長岡博多天婦羅〗🍤】
正宗鮮製現炸天婦羅在哪吃？
在 #銅鑼灣利園 就吃得到，
從 #福岡 漂洋過海來的 #休閒式天婦羅店 ー長岡博多天婦羅（ #天ぷらながおか）。""",
        "expect": {
            "name": "長岡博多天婦羅", "district": "銅鑼灣",
            "brand_from": "福岡", "category": "food",
        },
    },
    {
        "name": "大阪たこ焼き · 日文 blog 風格",
        "text": """大阪・道頓堀で外せないたこ焼きの名店
「本家大たこ 道頓堀店」
住所：〒542-0071 大阪府大阪市中央区道頓堀1-5-10
電話：06-6211-XXXX
営業時間：10:00〜23:00（年中無休）
予算：500〜1,000円""",
        "expect": {
            "name": "本家大たこ 道頓堀店", "prefecture": "大阪府",
            "district": "道頓堀", "postal_code": "542-0071",
            "category": "food",
        },
    },
    {
        "name": "首爾 cafe（caption 冇店名）· 應該要 needs_review",
        "text": """首爾聖水洞必去！☕
📍地址：서울 성동구 연무장길 47
🕐 11:00 - 22:00
💰 人均 ₩12,000
#首爾 #聖水洞 #cafe""",
        "expect": {"country": "韓國", "category": "food", "needs_review": True},
    },
]

OFFLINE_URL_CASES = [
    {
        "name": "Google Maps · /place/ 完整格式",
        "url": ("https://www.google.com/maps/place/Ichiran+Hakata+Shop/"
                "@33.5897,130.4207,17z/data=!4m6!3m5!1s0x35419:0x8b8f"
                "!8m2!3d33.5897!4d130.4207"),
        "expect": {"name": "Ichiran Hakata Shop", "lat": 33.5897, "lng": 130.4207},
    },
    {
        "name": "Google Maps · ?q= 格式",
        "url": "https://www.google.com/maps/search/?api=1&query=Canal+City+Hakata",
        "expect": {"name": "Canal City Hakata"},
    },
    {
        "name": "Google Maps · 短連結",
        "url": "https://maps.app.goo.gl/xK9mQ2vLp8TnR4wY7",
        "expect": {"source": "gmaps", "confidence": 0},
    },
    {
        "name": "Instagram Reel",
        "url": "https://www.instagram.com/reel/C9aB3nRwZq1/",
        "expect": {"source": "instagram"},
    },
    {
        "name": "小紅書",
        "url": "https://www.xiaohongshu.com/explore/665f2a1b000000001e02c3d4",
        "expect": {"source": "xiaohongshu"},
    },
    {
        "name": "Tabelog",
        "url": "https://tabelog.com/fukuoka/A4001/A400101/40001234/",
        "expect": {"source": "tabelog"},
    },
]


def run_selftest(verbose: bool = True) -> int:
    passed = failed = 0
    print(f"\n{C.P}{'═' * 66}{C.R}")
    print(f"  {C.B}Wander 解析引擎 · 自我測試{C.R}")
    print(f"{C.P}{'═' * 66}{C.R}")

    print(f"\n  {C.CY}▸ 文字解析（{len(SELFTEST_CASES)} 個案例）{C.R}")
    for case in SELFTEST_CASES:
        item = CaptionParser().parse(case["text"])
        errs = []
        for k, want in case["expect"].items():
            got = getattr(item, k, None)
            if got != want:
                errs.append(f"{k}: 想 {want!r} → 實際 {got!r}")
        ok = not errs
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        mark = f"{C.G}✓{C.R}" if ok else f"{C.RD}✗{C.R}"
        print(f"    {mark} {case['name']}")
        print(f"      {C.DIM}信心 {item.confidence}% · "
              f"{item.location_display} · {item.category_display}{C.R}")
        for e in errs:
            print(f"      {C.RD}↳ {e}{C.R}")

    print(f"\n  {C.CY}▸ URL 結構解析（{len(OFFLINE_URL_CASES)} 個案例）{C.R}")
    for case in OFFLINE_URL_CASES:
        item = parse_url_offline(case["url"])
        errs = []
        for k, want in case["expect"].items():
            got = getattr(item, k, None)
            if isinstance(want, float):
                if got is None or abs(got - want) > 0.01:
                    errs.append(f"{k}: 想 {want} → 實際 {got}")
            elif got != want:
                errs.append(f"{k}: 想 {want!r} → 實際 {got!r}")
        ok = not errs
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        mark = f"{C.G}✓{C.R}" if ok else f"{C.RD}✗{C.R}"
        print(f"    {mark} {case['name']}")
        print(f"      {C.DIM}{item.name or '（無名）'} · "
              f"{item.location_display} · {item.confidence}%{C.R}")
        for e in errs:
            print(f"      {C.RD}↳ {e}{C.R}")

    total = passed + failed
    color = C.G if failed == 0 else C.RD
    print(f"\n{C.P}{'═' * 66}{C.R}")
    print(f"  {color}{C.B}{passed}/{total} 通過{C.R}"
          f"{'' if failed == 0 else f'  {C.RD}{failed} 個失敗{C.R}'}")
    print(f"{C.P}{'═' * 66}{C.R}\n")
    return 1 if failed else 0


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wander", description="Wander 解析引擎 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd")

    p_url = sub.add_parser("parse", help="解析 URL")
    p_url.add_argument("url")
    p_url.add_argument("--no-fetch", action="store_true", help="唔上網，只靠 URL 結構")
    p_url.add_argument("--caption", help="用戶自己貼嘅 caption（會蓋過抓到嘅文字）")
    p_url.add_argument("--ignore-robots", action="store_true")
    p_url.add_argument("--json", action="store_true")
    p_url.add_argument("--quiet", action="store_true", help="唔顯示規則同分數拆解")

    p_txt = sub.add_parser("text", help="解析文字")
    p_txt.add_argument("text", nargs="?")
    p_txt.add_argument("--file")
    p_txt.add_argument("--json", action="store_true")
    p_txt.add_argument("--quiet", action="store_true")

    p_batch = sub.add_parser("batch", help="批量處理 URL 清單（每行一個）")
    p_batch.add_argument("file")
    p_batch.add_argument("--json-out")
    p_batch.add_argument("--no-fetch", action="store_true")

    p_look = sub.add_parser("lookup", help="由店名反查完整資料（Photon + DuckDuckGo + JSON-LD）")
    p_look.add_argument("name", help="店名／地標名，例如「一蘭 本社総本店」")
    p_look.add_argument("--hint", help="地區提示，例如「博多」—— 大幅提升準確度")
    p_look.add_argument("--no-search", action="store_true", help="只用 Photon，唔搜尋網頁")
    p_look.add_argument("--no-fetch", action="store_true", help="唔抓詳細頁")
    p_look.add_argument("--verbose", "-v", action="store_true", help="顯示過程")
    p_look.add_argument("--json", action="store_true")

    p_enrich = sub.add_parser("enrich", help="攞一段 caption，解析之後再用搜尋補齊缺欄位")
    p_enrich.add_argument("text", nargs="?")
    p_enrich.add_argument("--file")
    p_enrich.add_argument("--hint")
    p_enrich.add_argument("--json", action="store_true")

    p_demo = sub.add_parser("demo", help="睇範例輸出")
    p_demo.add_argument("--json", action="store_true")

    sub.add_parser("selftest", help="跑內建測試")

    args = ap.parse_args(argv)

    # ── selftest ──
    if args.cmd == "selftest" or args.cmd is None:
        return run_selftest()

    # ── text ──
    if args.cmd == "text":
        if args.file:
            text = Path(args.file).read_text(encoding="utf-8")
        elif args.text:
            text = args.text
        else:
            text = sys.stdin.read()
        if not text.strip():
            print("冇輸入文字。", file=sys.stderr)
            return 2
        item = CaptionParser().parse(text)
        if args.json:
            print(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_item(item, show_rules=not args.quiet, show_score=not args.quiet)
        return 0

    # ── parse ──
    if args.cmd == "parse":
        url = args.url
        if args.no_fetch:
            item = parse_url_offline(url)
            trace = []
        else:
            from .fetch import fetch_item
            item, trace, meta = fetch_item(
                url,
                respect_robots=not args.ignore_robots,
                caption_override=args.caption,
            )
        if args.json:
            print(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_item(item, show_rules=not args.quiet, show_score=not args.quiet)
        return 0

    # ── lookup ──
    if args.cmd == "lookup":
        from .lookup import lookup_place
        item, log = lookup_place(args.name, hint=args.hint,
                                 use_search=not args.no_search,
                                 fetch_details=not args.no_fetch,
                                 verbose=args.verbose)
        if args.verbose and not args.json:
            print(f"\n{C.DIM}── 過程 ──{C.R}")
            for l in log:
                print(f"  {C.DIM}{l}{C.R}")
        if args.json:
            print(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_item(item, show_rules=args.verbose, show_score=True)
        return 0

    # ── enrich（caption + 搜尋補完）──
    if args.cmd == "enrich":
        from .lookup import enrich_caption_item
        if args.file:
            text = Path(args.file).read_text(encoding="utf-8")
        elif args.text:
            text = args.text
        else:
            text = sys.stdin.read()
        if not text.strip():
            print("冇輸入文字。", file=sys.stderr)
            return 2
        item = CaptionParser().parse(text)
        print(f"{C.DIM}── 第一步：caption 解析 ──{C.R}")
        print(f"  {item.name or '（抽唔到名）'} · {item.location_display} · {item.confidence}%")
        if not item.name:
            print(f"{C.Y}冇店名，無法用搜尋補完。{C.R}")
            print_item(item, show_rules=False, show_score=False)
            return 0
        item, log = enrich_caption_item(item, verbose=args.verbose)
        if not args.json:
            print(f"\n{C.DIM}── 第二步：搜尋補完 ──{C.R}")
            for l in log:
                print(f"  {C.DIM}{l}{C.R}")
        if args.json:
            print(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_item(item, show_rules=False, show_score=True)
        return 0

    # ── batch ──
    if args.cmd == "batch":
        urls = [u.strip() for u in Path(args.file).read_text(encoding="utf-8").splitlines()
                if u.strip() and not u.strip().startswith("#")]
        results = []
        for i, u in enumerate(urls, 1):
            print(f"{C.DIM}[{i}/{len(urls)}] {u[:70]}{C.R}")
            try:
                if args.no_fetch:
                    item = parse_url_offline(u)
                else:
                    from .fetch import fetch_item
                    item, _, _ = fetch_item(u)
                results.append(item)
                if not args.json_out:
                    print(f"    → {item.name or '（無名）'} · {item.location_display}"
                          f" · {item.confidence}%")
            except Exception as e:
                print(f"    {C.RD}✗ {e}{C.R}")
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"\n寫入 {args.json_out}（{len(results)} 個項目）")
        return 0

    # ── demo ──
    if args.cmd == "demo":
        items = [CaptionParser().parse(c["text"]) for c in SELFTEST_CASES]
        if args.json:
            print(json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2))
        else:
            for it in items:
                print_item(it, show_rules=False, show_score=True)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
