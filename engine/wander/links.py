"""
wander.links — URL 分類同結構解析（唔使上網就做得）

呢一層嘅價值：Google Maps link 本身就帶住店名 + 精確座標，
完全免費、即時、100% 準。所以永遠要做第一步。

支援嘅 Google Maps 格式：
  1. /maps/place/店名/@lat,lng,17z/data=!3d..!4d..   ← 最完整
  2. /maps/search/?api=1&query=店名
  3. maps.app.goo.gl/xxxx                            ← 短連結，要跟 redirect
  4. ?q=店名
  5. /maps/@lat,lng,17z                              ← 只有視窗中心，冇店名
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from .models import Item

# ══════════════════════════════════════════════════════════════
# 來源分類
# ══════════════════════════════════════════════════════════════

SOURCE_RULES: list[tuple[str, str, str]] = [
    # (regex 對 hostname, 來源 id, 顯示名)
    (r"^(maps\.app\.goo\.gl|goo\.gl|maps\.google\.[a-z.]+|google\.[a-z.]+)$", "gmaps",    "Google Maps"),
    (r"instagram\.com$",                                                        "instagram", "Instagram"),
    (r"(xiaohongshu\.com|xhslink\.com)$",                                       "xiaohongshu", "小紅書"),
    (r"(youtube\.com|youtu\.be)$",                                              "youtube",  "YouTube"),
    (r"tiktok\.com$",                                                           "tiktok",   "TikTok"),
    (r"tabelog\.com$",                                                          "tabelog",  "Tabelog"),
    (r"(tripadvisor\.[a-z.]+)$",                                                "tripadvisor", "TripAdvisor"),
    (r"(hotpepper\.jp|retty\.me|gnavi\.co\.jp|jalan\.net)$",                    "jp_gourmet", "日本美食網"),
    (r"(klook\.com|kkday\.com)$",                                               "ota",      "旅遊平台"),
    (r"(openrice\.com)$",                                                       "openrice", "OpenRice"),
    (r"(dianping\.com|meituan\.com)$",                                          "dianping", "大眾點評"),
    (r"google\.[a-z.]+$",                                                       "web",      "網頁"),
]

# 各來源「理論上」可以攞到嘅資料（用嚟設定用戶期望）
SOURCE_CAPABILITY: dict[str, dict[str, bool]] = {
    "gmaps":       {"name": True,  "address": True,  "coords": True,  "image": False, "text": False},
    "instagram":   {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
    "xiaohongshu": {"name": False, "address": False, "coords": False, "image": False, "text": False},
    "youtube":     {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
    "tabelog":     {"name": True,  "address": True,  "coords": True,  "image": True,  "text": True},
    "tripadvisor": {"name": True,  "address": True,  "coords": False, "image": True,  "text": True},
    "jp_gourmet":  {"name": True,  "address": True,  "coords": False, "image": True,  "text": True},
    "ota":         {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
    "openrice":    {"name": True,  "address": True,  "coords": False, "image": True,  "text": True},
    "web":         {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
}


def classify(url: str) -> dict[str, str]:
    """判斷 URL 屬於邊個來源。"""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return {"id": "invalid", "name": "無法識別", "host": ""}
    host = re.sub(r"^www\.", "", host.lower())
    for pattern, sid, sname in SOURCE_RULES:
        if re.search(pattern, host):
            return {"id": sid, "name": sname, "host": host}
    return {"id": "web", "name": "一般網站", "host": host}


def is_short_link(url: str) -> bool:
    return bool(re.search(r"maps\.app\.goo\.gl|goo\.gl/maps|xhslink\.com|youtu\.be|bit\.ly|tinyurl", url))


# ══════════════════════════════════════════════════════════════
# Google Maps 結構解析
# ══════════════════════════════════════════════════════════════

def parse_gmaps(url: str) -> tuple[Item, list[dict[str, str]]]:
    """
    解析 Google Maps link → Item。
    完全唔使上網：所有資料都喺 URL 入面。
    """
    item = Item(source="gmaps", source_name="Google Maps", url=url)
    steps: list[dict[str, str]] = []
    decoded = unquote(url)

    def step(rule: str, match: str, note: str) -> None:
        steps.append({"rule": rule, "match": match, "note": note})

    if is_short_link(url):
        step("GMAPS_SHORT", url, "短連結 → 需要 HTTP redirect 跟蹤拎最終 URL")
        item.notes.append("短連結需要跟 redirect 才可以解析")

    # ① 精確座標 !3d!4d（最準，優先）
    m34 = re.search(r"!3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)", url)
    if m34:
        item.lat, item.lng = float(m34.group(1)), float(m34.group(2))
        step("GMAPS_COORD_EXACT", f"{item.lat}, {item.lng}", "精確座標 !3d!4d（店舖本身）")

    # ② /place/店名/
    m_place = re.search(r"/place/([^/@?]+)", decoded)
    if m_place:
        item.name = m_place.group(1).replace("+", " ").strip()
        item.name_method = "Google Maps /place/ 路徑"
        step("GMAPS_PLACE", item.name, "由 /place/ 路徑抽店名")
    else:
        step("GMAPS_PLACE", "(無)", "呢條 link 冇 /place/ 路徑")

    # ③ 座標 @lat,lng（視窗中心，唔一定係店舖）
    m_at = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m_at and not m34:
        item.lat, item.lng = float(m_at.group(1)), float(m_at.group(2))
        step("GMAPS_COORD_VIEW", f"{item.lat}, {item.lng}", "視窗中心座標（唔係店舖本身，要小心）")
    elif m_at:
        step("GMAPS_COORD_VIEW", f"{m_at.group(1)}, {m_at.group(2)}", "視窗中心（已有精確座標，忽略）")

    # ④ ?q= / query=
    qs = parse_qs(urlparse(url).query)
    for key in ("q", "query"):
        if key in qs and qs[key]:
            q = qs[key][0].replace("+", " ").strip()
            if q and not q[0].isdigit():
                if not item.name:
                    item.name = q
                    item.name_method = f"Google Maps ?{key}= 參數"
                step(f"GMAPS_QUERY_{key.upper()}", q, "由查詢參數抽店名")
            elif q:
                parts = q.split(",")
                if len(parts) == 2:
                    try:
                        item.lat, item.lng = float(parts[0]), float(parts[1])
                        step("GMAPS_QUERY_COORD", q, "由 query 參數抽座標")
                    except ValueError:
                        pass

    # ⑤ 用地理詞典比對店名／地址
    hay = " ".join(filter(None, [item.name, decoded]))
    from .lexicon import ALL_DISTRICT_WORDS, GROUP_COUNTRY, match_region
    mr = match_region(hay)
    if mr:
        from .lexicon import _WORD_TO_GROUP
        grp = _WORD_TO_GROUP.get(mr[0])
        item.district = mr[0]
        if grp:
            item.country = GROUP_COUNTRY.get(grp)
            if grp == "福岡縣":
                item.prefecture = "福岡縣"
            elif grp == "福岡市":
                item.prefecture = "福岡縣"
                item.city = "福岡市"
            elif grp == "其他日本":
                item.prefecture = item.prefecture or "（日本）"
        step("GEO_MATCH", mr[0], f"地名比對命中「{mr[0]}」（{grp}）")
    else:
        step("GEO_MATCH", "(無命中)", "店名冇地區關鍵字 → 要靠座標反查（Nominatim）")

    # ⑥ 分類
    from .caption import CaptionParser
    if item.name:
        CaptionParser._extract_category(item.name, item, lambda *a: None)
    if item.category:
        step("CATEGORY", item.category_why or "", f"由店名推斷分類：{item.category}")
    else:
        step("CATEGORY", "(無)", "推斷唔到分類 → 標記待分類")

    # 信心分數
    C = {
        "name": 100 if item.name else 0,
        "location": 96 if item.lat else (80 if item.district else 0),
        "address": 0,
        "category": 70 if item.category else 0,
    }
    weights = [("name", 0.32), ("location", 0.26), ("category", 0.14)]
    item.field_confidence = C
    item.confidence = round(sum(C.get(k, 0) * w for k, w in weights)
                            + (26 if item.lat else 0))   # 有精確座標加成
    item.confidence = min(item.confidence, 100)
    item.needs_review = item.confidence < 70 or not item.name
    item.rules_matched = steps
    return item, steps


# ══════════════════════════════════════════════════════════════
# 結構解析入口（唔上網）
# ══════════════════════════════════════════════════════════════

def parse_url_offline(url: str) -> Item:
    """
    只靠 URL 結構解析，唔上網。
    對 Google Maps 極有效；其他來源只做到「識別 + 抽出 ID」。
    """
    kind = classify(url)
    if kind["id"] == "gmaps":
        item, _ = parse_gmaps(url)
        return item

    item = Item(source=kind["id"], source_name=kind["name"], url=url)
    rules = [{"rule": "CLASSIFY", "match": kind["host"], "note": f"識別為 {kind['name']}"}]

    if kind["id"] == "instagram":
        m = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
        if m:
            item.notes.append(f"IG post id: {m.group(1)}")
            rules.append({"rule": "IG_POST_ID", "match": m.group(1), "note": "貼文 ID"})
        rules.append({"rule": "NEEDS_FETCH", "match": "og:title / og:image / caption",
                      "note": "要後端抓 HTML"})

    elif kind["id"] == "xiaohongshu":
        rules.append({"rule": "XHS_BLOCKED", "match": kind["host"],
                      "note": "反爬嚴格 → 建議用戶貼文字或上傳截圖"})
        item.notes.append("小紅書建議改用「貼 caption」或「截圖上傳」")

    elif kind["id"] == "youtube":
        m = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})", url)
        if m:
            item.notes.append(f"YouTube video id: {m.group(1)}")
            rules.append({"rule": "YT_ID", "match": m.group(1), "note": "可用官方 oEmbed（免費）"})

    else:
        rules.append({"rule": "NEEDS_FETCH", "match": "HTML meta / JSON-LD",
                      "note": "要後端抓 HTML 抽結構化資料"})

    item.rules_matched = rules
    item.confidence = 0
    item.needs_review = True
    return item
